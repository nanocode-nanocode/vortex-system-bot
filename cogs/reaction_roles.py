import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import uuid

from db import (
    add_reaction_role,
    remove_reaction_role,
    get_reaction_panels,
    add_audit,
)

# ── Sentinel — we store a row with role_id=0 to keep panel metadata
#    (channel_id, message_id, title) in the DB even when the panel has no
#    real roles yet.  No real Discord role will ever have id 0.
_PANEL_SENTINEL_ROLE = 0
_PANEL_SENTINEL_LABEL = "__panel__"


# ── helpers ──────────────────────────────────────────────────────────────────


def parse_emoji(emoji_str: str):
    """Return a PartialEmoji for custom emojis, or the raw str for unicode."""
    if not emoji_str:
        return None
    s = emoji_str.strip()
    if s.startswith("<") and s.endswith(">"):
        try:
            return discord.PartialEmoji.from_str(s)
        except Exception:
            pass
    return s


def _strip_sentinel(roles: list) -> list:
    """Filter out the sentinel placeholder that stores panel metadata."""
    return [r for r in roles if r["role_id"] != _PANEL_SENTINEL_ROLE]


# ── Persistent View ─────────────────────────────────────────────────────────


class ReactionRoleView(View):
    """Dynamically built view — one button per role entry."""

    def __init__(self, panel_data: dict):
        super().__init__(timeout=None)
        self.panel_data = panel_data

        for idx, entry in enumerate(panel_data.get("roles", [])):
            role_id = entry["role_id"]
            if role_id == _PANEL_SENTINEL_ROLE:
                continue  # skip the metadata placeholder

            label = entry.get("label", "Unknown")
            emoji_str = entry.get("emoji", "")

            custom_id = f"rr:{panel_data['id']}:{role_id}"
            row = idx // 5

            btn = Button(
                label=label,
                emoji=parse_emoji(emoji_str),
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id,
                row=row,
            )
            btn.callback = self._make_callback(role_id)
            self.add_item(btn)

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_callback(role_id: int):
        async def callback(interaction: discord.Interaction):
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "❌ | This command can only be used in a server.",
                    ephemeral=True,
                )
                return

            role = guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "❌ | That role no longer exists on this server.",
                    ephemeral=True,
                )
                return

            member = interaction.user
            if not isinstance(member, discord.Member):
                await interaction.response.send_message(
                    "❌ | Could not resolve your member data.",
                    ephemeral=True,
                )
                return

            if role in member.roles:
                await member.remove_roles(role, reason="Reaction Roles: removed")
                await interaction.response.send_message(
                    f"✅ | Removed {role.mention}",
                    ephemeral=True,
                )
            else:
                await member.add_roles(role, reason="Reaction Roles: added")
                await interaction.response.send_message(
                    f"✅ | Added {role.mention}",
                    ephemeral=True,
                )

        return callback


# ── Cog ─────────────────────────────────────────────────────────────────────


class ReactionRoles(commands.Cog):
    """Reaction role panels using discord.ui buttons + PostgreSQL."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def cog_load(self):
        """Re-register persistent views after a restart."""
        for guild in self.bot.guilds:
            panels = get_reaction_panels(guild.id)
            for panel in panels:
                mid = panel.get("message_id")
                if not mid:
                    continue
                ch = self.bot.get_channel(panel["channel_id"])
                if not ch:
                    continue
                try:
                    await ch.fetch_message(mid)
                except Exception:
                    continue  # message gone — skip
                view = ReactionRoleView(panel)
                self.bot.add_view(view, message_id=mid)

    # ── slash command group ───────────────────────────────────────────────

    rr = app_commands.Group(
        name="reaction-roles",
        description="🎯 Reaction role panel management",
    )

    # ── create ────────────────────────────────────────────────────────────

    @rr.command(name="create", description="🎯 Create a reaction role panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        channel="Channel to send the panel to",
        title="Panel title / heading",
    )
    async def rr_create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
    ):
        """Send an empty panel, store metadata via sentinel, tell admin how to add roles."""
        await interaction.response.defer(ephemeral=True)

        panel_id = uuid.uuid4().hex[:8]

        panel = {
            "id": panel_id,
            "channel_id": channel.id,
            "message_id": 0,
            "title": title,
            "roles": [],
        }

        embed = discord.Embed(
            title=f"🎯 | {title}",
            description=(
                "*No roles configured yet.*\n"
                "An admin can add roles with `/reaction-roles add`."
            ),
            color=0x5865F2,
        )
        embed.set_footer(text=f"Panel ID: {panel_id} • VØRTΞX System")

        view = ReactionRoleView(panel)
        msg = await channel.send(embed=embed, view=view)
        panel["message_id"] = msg.id

        # Store panel metadata in DB via sentinel row (no real roles yet)
        add_reaction_role(
            interaction.guild.id,
            panel_id,
            channel.id,
            msg.id,
            title,
            _PANEL_SENTINEL_ROLE,
            _PANEL_SENTINEL_LABEL,
            "",
        )

        # Register for persistence
        self.bot.add_view(view, message_id=msg.id)

        add_audit(
            "reaction_role_create",
            f"Panel {panel_id} in {channel.id}",
            interaction.guild.id,
            interaction.user.id,
        )

        await interaction.followup.send(
            f"✅ | Panel created in {channel.mention}\n"
            f"**Panel ID:** `{panel_id}`\n\n"
            f"Add roles with:\n"
            f"`/reaction-roles add role:@Role label:\"Button Label\" "
            f"emoji:😀 panel_id:{panel_id}`",
            ephemeral=True,
        )

    # ── add ───────────────────────────────────────────────────────────────

    @rr.command(name="add", description="➕ Add a role button to an existing panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        role="The role to assign",
        label="Text shown on the button",
        emoji="Emoji shown on the button (unicode or custom)",
        panel_id="ID of the panel (see /reaction-roles list)",
    )
    async def rr_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        label: str,
        emoji: str,
        panel_id: str,
    ):
        await interaction.response.defer(ephemeral=True)

        panels = get_reaction_panels(interaction.guild.id)
        panel = next((p for p in panels if p["id"] == panel_id), None)

        if panel is None:
            await interaction.followup.send(
                f"❌ | No panel with ID `{panel_id}` found in this server.",
                ephemeral=True,
            )
            return

        # Duplicate check
        if any(e["role_id"] == role.id for e in panel["roles"]):
            await interaction.followup.send(
                "❌ | That role is already in this panel.",
                ephemeral=True,
            )
            return

        add_reaction_role(
            interaction.guild.id,
            panel_id,
            panel["channel_id"],
            panel["message_id"],
            panel["title"],
            role.id,
            label,
            emoji,
        )

        # Refresh the panel message with up-to-date data
        await self._refresh_panel(interaction.guild, panel_id)

        add_audit(
            "reaction_role_add",
            f"Role {role.id} to panel {panel_id}",
            interaction.guild.id,
            interaction.user.id,
        )

        await interaction.followup.send(
            f"✅ | Added {role.mention} as **{label}** {emoji} "
            f"to panel `{panel_id}`.",
            ephemeral=True,
        )

    # ── remove (single role from panel) ───────────────────────────────────

    @rr.command(name="remove", description="➖ Remove a role button from a panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        role="The role to remove",
        panel_id="ID of the panel (see /reaction-roles list)",
    )
    async def rr_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        panel_id: str,
    ):
        await interaction.response.defer(ephemeral=True)

        panels = get_reaction_panels(interaction.guild.id)
        panel = next((p for p in panels if p["id"] == panel_id), None)

        if panel is None:
            await interaction.followup.send(
                f"❌ | No panel with ID `{panel_id}` found in this server.",
                ephemeral=True,
            )
            return

        real_roles = _strip_sentinel(panel["roles"])
        original_len = len(real_roles)

        # Filter to find if the role is actually present
        if not any(r["role_id"] == role.id for r in real_roles):
            await interaction.followup.send(
                "❌ | That role is not in this panel.",
                ephemeral=True,
            )
            return

        remove_reaction_role(
            interaction.guild.id, panel_id, role.id
        )

        # Refresh the panel message
        await self._refresh_panel(interaction.guild, panel_id)

        add_audit(
            "reaction_role_remove",
            f"Role {role.id} from panel {panel_id}",
            interaction.guild.id,
            interaction.user.id,
        )

        await interaction.followup.send(
            f"✅ | Removed {role.mention} from panel `{panel_id}`.",
            ephemeral=True,
        )

    # ── delete (entire panel) ─────────────────────────────────────────────

    @rr.command(name="delete", description="🗑️ Delete an entire reaction role panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        panel_id="ID of the panel to delete",
    )
    async def rr_delete(
        self,
        interaction: discord.Interaction,
        panel_id: str,
    ):
        await interaction.response.defer(ephemeral=True)

        panels = get_reaction_panels(interaction.guild.id)
        panel = next((p for p in panels if p["id"] == panel_id), None)

        if panel is None:
            await interaction.followup.send(
                f"❌ | No panel with ID `{panel_id}` found in this server.",
                ephemeral=True,
            )
            return

        # Remove all role rows (including sentinel)
        for entry in panel["roles"]:
            remove_reaction_role(
                interaction.guild.id, panel_id, entry["role_id"]
            )
        # Also explicitly remove the sentinel (belt-and-suspenders)
        remove_reaction_role(
            interaction.guild.id, panel_id, _PANEL_SENTINEL_ROLE
        )

        # Try to clean up the panel message
        channel = interaction.guild.get_channel(panel["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(panel["message_id"])
                await msg.delete()
            except Exception:
                pass

        add_audit(
            "reaction_role_delete",
            f"Panel {panel_id}",
            interaction.guild.id,
            interaction.user.id,
        )

        await interaction.followup.send(
            f"✅ | Deleted panel `{panel_id}`.",
            ephemeral=True,
        )

    # ── list ──────────────────────────────────────────────────────────────

    @rr.command(name="list", description="📋 List all reaction role panels")
    @app_commands.default_permissions(administrator=True)
    async def rr_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        panels = get_reaction_panels(interaction.guild.id)
        if not panels:
            await interaction.followup.send(
                "❌ | No reaction role panels exist in this server.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🎯 | Reaction Role Panels",
            color=0x5865F2,
        )

        for p in panels:
            ch = interaction.guild.get_channel(p["channel_id"])
            ch_mention = ch.mention if ch else "*#deleted-channel*"
            real_roles = _strip_sentinel(p["roles"])
            n_roles = len(real_roles)

            embed.add_field(
                name=f"📦 {p['title']}",
                value=(
                    f"**ID:** `{p['id']}`\n"
                    f"**Channel:** {ch_mention}\n"
                    f"**Roles:** {n_roles}"
                ),
                inline=False,
            )

        embed.set_footer(text=f"Total: {len(panels)} panel(s) • VØRTΞX System")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── prefix fallback commands ──────────────────────────────────────────

    @commands.group(
        name="reactionroles",
        aliases=["rr"],
        invoke_without_command=True,
    )
    @commands.has_permissions(administrator=True)
    async def rr_prefix(self, ctx: commands.Context):
        """Prefix fallback — show subcommand help."""
        await ctx.send(
            "📋 **Reaction Roles** — use `/reaction-roles` for the full "
            "slash interface.\n"
            "Available prefix subcommands: `create`, `add`, `remove`, `list`. "
            "Also `/reaction-roles delete` for full panel deletion.\n"
            "Example: `!reactionroles create #general \"My Panel\"`"
        )

    @rr_prefix.command(name="create")
    @commands.has_permissions(administrator=True)
    async def rr_create_prefix(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *,
        title: str,
    ):
        panel_id = uuid.uuid4().hex[:8]

        panel = {
            "id": panel_id,
            "channel_id": channel.id,
            "message_id": 0,
            "title": title,
            "roles": [],
        }

        embed = discord.Embed(
            title=f"🎯 | {title}",
            description="*No roles configured yet.*\nUse `rr add` to add roles.",
            color=0x5865F2,
        )
        embed.set_footer(text=f"Panel ID: {panel_id} • VØRTΞX System")

        view = ReactionRoleView(panel)
        msg = await channel.send(embed=embed, view=view)
        panel["message_id"] = msg.id

        add_reaction_role(
            ctx.guild.id,
            panel_id,
            channel.id,
            msg.id,
            title,
            _PANEL_SENTINEL_ROLE,
            _PANEL_SENTINEL_LABEL,
            "",
        )
        self.bot.add_view(view, message_id=msg.id)

        add_audit(
            "reaction_role_create",
            f"Panel {panel_id} in {channel.id}",
            ctx.guild.id,
            ctx.author.id,
        )

        await ctx.send(
            f"✅ | Panel created in {channel.mention} — ID: `{panel_id}`"
        )

    @rr_prefix.command(name="add")
    @commands.has_permissions(administrator=True)
    async def rr_add_prefix(
        self,
        ctx: commands.Context,
        panel_id: str,
        role: discord.Role,
        label: str,
        emoji: str,
    ):
        panels = get_reaction_panels(ctx.guild.id)
        panel = next((p for p in panels if p["id"] == panel_id), None)

        if panel is None:
            await ctx.send(f"❌ | No panel with ID `{panel_id}`.")
            return

        if any(e["role_id"] == role.id for e in panel["roles"]):
            await ctx.send("❌ | That role is already in this panel.")
            return

        add_reaction_role(
            ctx.guild.id,
            panel_id,
            panel["channel_id"],
            panel["message_id"],
            panel["title"],
            role.id,
            label,
            emoji,
        )

        await self._refresh_panel(ctx.guild, panel_id)

        add_audit(
            "reaction_role_add",
            f"Role {role.id} to panel {panel_id}",
            ctx.guild.id,
            ctx.author.id,
        )

        await ctx.send(f"✅ | Added {role.mention} ({label}) to panel.")

    @rr_prefix.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def rr_remove_prefix(
        self,
        ctx: commands.Context,
        panel_id: str,
        role: discord.Role,
    ):
        panels = get_reaction_panels(ctx.guild.id)
        panel = next((p for p in panels if p["id"] == panel_id), None)

        if panel is None:
            await ctx.send(f"❌ | No panel with ID `{panel_id}`.")
            return

        real_roles = _strip_sentinel(panel["roles"])
        if not any(r["role_id"] == role.id for r in real_roles):
            await ctx.send("❌ | That role is not in this panel.")
            return

        remove_reaction_role(ctx.guild.id, panel_id, role.id)
        await self._refresh_panel(ctx.guild, panel_id)

        add_audit(
            "reaction_role_remove",
            f"Role {role.id} from panel {panel_id}",
            ctx.guild.id,
            ctx.author.id,
        )

        await ctx.send(f"✅ | Removed {role.mention} from panel.")

    @rr_prefix.command(name="list")
    @commands.has_permissions(administrator=True)
    async def rr_list_prefix(self, ctx: commands.Context):
        panels = get_reaction_panels(ctx.guild.id)
        if not panels:
            await ctx.send("❌ | No panels exist in this server.")
            return

        lines = []
        for p in panels:
            ch = ctx.guild.get_channel(p["channel_id"])
            ch_mention = ch.mention if ch else "*#deleted*"
            real_roles = _strip_sentinel(p["roles"])
            lines.append(
                f"📦 **{p['title']}** — ID: `{p['id']}` — {ch_mention} "
                f"({len(real_roles)} roles)"
            )

        await ctx.send("**🎯 Reaction Role Panels**\n" + "\n".join(lines))

    # ── internal helpers ──────────────────────────────────────────────────

    async def _refresh_panel(self, guild: discord.Guild, panel_id: str):
        """Re-fetch panel from DB and edit its message + re-register view."""
        # Re-fetch so we always have the latest state
        panels = get_reaction_panels(guild.id)
        panel = next((p for p in panels if p["id"] == panel_id), None)
        if panel is None:
            return

        channel = guild.get_channel(panel["channel_id"])
        if not channel:
            return
        try:
            msg = await channel.fetch_message(panel["message_id"])
        except Exception:
            return  # message deleted or inaccessible

        real_roles = _strip_sentinel(panel["roles"])

        if real_roles:
            desc = "\n".join(
                f"{r['emoji']} **{r['label']}** — <@&{r['role_id']}>"
                for r in real_roles
            )
        else:
            desc = "*No roles configured yet.*"

        embed = discord.Embed(
            title=f"🎯 | {panel['title']}",
            description=desc,
            color=0x5865F2,
        )
        embed.set_footer(
            text=(
                f"Panel ID: {panel['id']} • "
                "Click a button to get/remove the role"
            )
        )

        view = ReactionRoleView(panel)
        await msg.edit(embed=embed, view=view)
        self.bot.add_view(view, message_id=panel["message_id"])


# ── setup ──────────────────────────────────────────────────────────────────


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
