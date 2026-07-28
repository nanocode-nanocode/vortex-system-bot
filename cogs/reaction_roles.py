import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import json, uuid
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA_FILE = BASE / "data" / "reaction_roles.json"


# ── Data helpers ────────────────────────────────────────────────────────────

def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def save_data(data):
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2))


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


# ── Persistent View ─────────────────────────────────────────────────────────

class ReactionRoleView(View):
    """Dynamically built view — one button per role entry."""

    def __init__(self, panel_data: dict):
        super().__init__(timeout=None)
        self.panel_data = panel_data  # kept for reference if needed

        for idx, entry in enumerate(panel_data.get("roles", [])):
            role_id = entry["role_id"]
            label = entry.get("label", "Unknown")
            emoji_str = entry.get("emoji", "")

            custom_id = f"rr:{panel_data['id']}:{role_id}"
            row = idx // 5  # max 5 buttons per row, discord allows 5 rows

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
                return await interaction.response.send_message(
                    "❌ | This command can only be used in a server.",
                    ephemeral=True,
                )

            role = guild.get_role(role_id)
            if not role:
                return await interaction.response.send_message(
                    "❌ | That role no longer exists on this server.",
                    ephemeral=True,
                )

            member = interaction.user
            if not isinstance(member, discord.Member):
                return await interaction.response.send_message(
                    "❌ | Could not resolve your member data.",
                    ephemeral=True,
                )

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
    """Reaction role panels using discord.ui buttons."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def cog_load(self):
        """Re-register persistent views after a restart."""
        data = load_data()
        for guild_id, guild_data in data.items():
            for panel in guild_data.get("panels", []):
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
        """Send an empty panel, store it, and tell the admin how to add roles."""
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        gid = str(interaction.guild.id)
        data.setdefault(gid, {"panels": []})

        panel_id = uuid.uuid4().hex[:8]

        panel = {
            "id": panel_id,
            "channel_id": channel.id,
            "message_id": 0,  # filled after send
            "title": title,
            "roles": [],
        }

        embed = discord.Embed(
            title=f"🎯 | {title}",
            description="*No roles configured yet.*\nAn admin can add roles with "
            f"`/reaction-roles add`.",
            color=0x5865F2,
        )
        embed.set_footer(text=f"Panel ID: {panel_id} • VØRTΞX System")

        view = ReactionRoleView(panel)
        msg = await channel.send(embed=embed, view=view)
        panel["message_id"] = msg.id

        data[gid]["panels"].append(panel)
        save_data(data)

        # Register for persistence
        self.bot.add_view(view, message_id=msg.id)

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
        data = load_data()
        gid = str(interaction.guild.id)
        panel = self._find_panel(data, gid, panel_id)
        if panel is None:
            return await interaction.response.send_message(
                f"❌ | No panel with ID `{panel_id}` found in this server.",
                ephemeral=True,
            )

        # Duplicate check
        if any(e["role_id"] == role.id for e in panel["roles"]):
            return await interaction.response.send_message(
                "❌ | That role is already in this panel.",
                ephemeral=True,
            )

        panel["roles"].append(
            {"role_id": role.id, "label": label, "emoji": emoji}
        )
        save_data(data)

        await self._refresh_panel(interaction.guild, panel)

        await interaction.response.send_message(
            f"✅ | Added {role.mention} as **{label}** {emoji} "
            f"to panel `{panel_id}`.",
            ephemeral=True,
        )

    # ── remove ────────────────────────────────────────────────────────────

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
        data = load_data()
        gid = str(interaction.guild.id)
        panel = self._find_panel(data, gid, panel_id)
        if panel is None:
            return await interaction.response.send_message(
                f"❌ | No panel with ID `{panel_id}` found in this server.",
                ephemeral=True,
            )

        original_len = len(panel["roles"])
        panel["roles"] = [e for e in panel["roles"] if e["role_id"] != role.id]

        if len(panel["roles"]) == original_len:
            return await interaction.response.send_message(
                "❌ | That role is not in this panel.",
                ephemeral=True,
            )

        save_data(data)
        await self._refresh_panel(interaction.guild, panel)

        await interaction.response.send_message(
            f"✅ | Removed {role.mention} from panel `{panel_id}`.",
            ephemeral=True,
        )

    # ── list ──────────────────────────────────────────────────────────────

    @rr.command(name="list", description="📋 List all reaction role panels")
    @app_commands.default_permissions(administrator=True)
    async def rr_list(self, interaction: discord.Interaction):
        data = load_data()
        gid = str(interaction.guild.id)

        panels = data.get(gid, {}).get("panels", [])
        if not panels:
            return await interaction.response.send_message(
                "❌ | No reaction role panels exist in this server.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="🎯 | Reaction Role Panels",
            color=0x5865F2,
        )

        for p in panels:
            ch = interaction.guild.get_channel(p["channel_id"])
            ch_mention = ch.mention if ch else "*#deleted-channel*"
            n_roles = len(p["roles"])
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
            "Available prefix subcommands: `create`, `add`, `remove`, `list`.\n"
            "Example: `!reactionroles create #general \"My Panel\"`"
        )

    @rr_prefix.command(name="create")
    @commands.has_permissions(administrator=True)
    async def rr_create_prefix(
        self, ctx: commands.Context,
        channel: discord.TextChannel,
        *,
        title: str,
    ):
        data = load_data()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"panels": []})

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

        data[gid]["panels"].append(panel)
        save_data(data)
        self.bot.add_view(view, message_id=msg.id)

        await ctx.send(
            f"✅ | Panel created in {channel.mention} — ID: `{panel_id}`"
        )

    @rr_prefix.command(name="add")
    @commands.has_permissions(administrator=True)
    async def rr_add_prefix(
        self, ctx: commands.Context,
        panel_id: str,
        role: discord.Role,
        label: str,
        emoji: str,
    ):
        data = load_data()
        gid = str(ctx.guild.id)
        panel = self._find_panel(data, gid, panel_id)
        if panel is None:
            return await ctx.send(f"❌ | No panel with ID `{panel_id}`.")

        if any(e["role_id"] == role.id for e in panel["roles"]):
            return await ctx.send("❌ | That role is already in this panel.")

        panel["roles"].append(
            {"role_id": role.id, "label": label, "emoji": emoji}
        )
        save_data(data)
        await self._refresh_panel(ctx.guild, panel)
        await ctx.send(f"✅ | Added {role.mention} ({label}) to panel.")

    @rr_prefix.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def rr_remove_prefix(
        self, ctx: commands.Context,
        panel_id: str,
        role: discord.Role,
    ):
        data = load_data()
        gid = str(ctx.guild.id)
        panel = self._find_panel(data, gid, panel_id)
        if panel is None:
            return await ctx.send(f"❌ | No panel with ID `{panel_id}`.")

        before = len(panel["roles"])
        panel["roles"] = [e for e in panel["roles"] if e["role_id"] != role.id]
        if len(panel["roles"]) == before:
            return await ctx.send("❌ | That role is not in this panel.")

        save_data(data)
        await self._refresh_panel(ctx.guild, panel)
        await ctx.send(f"✅ | Removed {role.mention} from panel.")

    @rr_prefix.command(name="list")
    @commands.has_permissions(administrator=True)
    async def rr_list_prefix(self, ctx: commands.Context):
        data = load_data()
        gid = str(ctx.guild.id)
        panels = data.get(gid, {}).get("panels", [])
        if not panels:
            return await ctx.send("❌ | No panels exist in this server.")

        lines = []
        for p in panels:
            ch = ctx.guild.get_channel(p["channel_id"])
            ch_mention = ch.mention if ch else "*#deleted*"
            lines.append(
                f"📦 **{p['title']}** — ID: `{p['id']}` — {ch_mention} "
                f"({len(p['roles'])} roles)"
            )

        await ctx.send("**🎯 Reaction Role Panels**\n" + "\n".join(lines))

    # ── internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _find_panel(data: dict, guild_id: str, panel_id: str):
        """Return the panel dict or None."""
        for p in data.get(guild_id, {}).get("panels", []):
            if p["id"] == panel_id:
                return p
        return None

    async def _refresh_panel(self, guild: discord.Guild, panel: dict):
        """Edit the panel message to reflect current roles + re-register view."""
        channel = guild.get_channel(panel["channel_id"])
        if not channel:
            return
        try:
            msg = await channel.fetch_message(panel["message_id"])
        except Exception:
            return  # message deleted or inaccessible

        if panel["roles"]:
            desc = "\n".join(
                f"{r['emoji']} **{r['label']}** — <@&{r['role_id']}>"
                for r in panel["roles"]
            )
        else:
            desc = "*No roles configured yet.*"

        embed = discord.Embed(
            title=f"🎯 | {panel['title']}",
            description=desc,
            color=0x5865F2,
        )
        embed.set_footer(
            text=f"Panel ID: {panel['id']} • Click a button to get/remove the role"
        )

        view = ReactionRoleView(panel)
        await msg.edit(embed=embed, view=view)
        self.bot.add_view(view, message_id=panel["message_id"])


# ── setup ──────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
