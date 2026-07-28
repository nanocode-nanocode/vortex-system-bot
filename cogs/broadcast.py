#!/usr/bin/env python3
"""
VØRTΞX System Bot — Broadcast (DB)
DB-backed broadcast system with history.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

from db import add_broadcast, get_broadcast_history

class Broadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="broadcast", description="📢 أرسل رسالة لكل القنوات في السيرفر")
    @app_commands.describe(title="العنوان", message="الرسالة")
    @app_commands.checks.has_permissions(administrator=True)
    async def broadcast(self, interaction: discord.Interaction, title: str, message: str):
        await interaction.response.defer(ephemeral=True)
        channels = [c for c in interaction.guild.text_channels if c.permissions_for(interaction.guild.me).send_messages]
        sent = 0
        for ch in channels:
            try:
                embed = discord.Embed(
                    title=f"📢 {title}",
                    description=message,
                    color=CONFIG.get("color", 5793266)
                )
                embed.set_footer(text=f"من {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                await ch.send(embed=embed)
                sent += 1
            except:
                pass
        # Save to DB
        add_broadcast(
            interaction.guild_id,
            [c.id for c in channels],
            title, message,
            interaction.user.id, sent
        )
        await interaction.followup.send(f"✅ تم الإرسال لـ **{sent}** قناة!", ephemeral=True)

    @app_commands.command(name="broadcast_history", description="📋 سجل البث السابق")
    @app_commands.checks.has_permissions(administrator=True)
    async def hist(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        records = get_broadcast_history(interaction.guild_id, 10)
        if not records:
            await interaction.followup.send("📭 لا يوجد سجل بث!", ephemeral=True)
            return
        embed = discord.Embed(title="📢 سجل البث", color=CONFIG.get("color", 5793266))
        for r in records:
            embed.add_field(
                name=f"{r['title']} | 🕐 {r['time']}",
                value=f"📨 {r['sent_to']} قناة\n📝 {r['message'][:80]}...",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Broadcast(bot))
