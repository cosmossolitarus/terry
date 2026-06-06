"""Slash commands for terry. Admin-only, scoped per guild."""
import logging

import discord
from discord import app_commands

import config
import nicknames

log = logging.getLogger("terry.slash")


def _is_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is None:
        return False
    admins = config.ADMIN_USERS.get(interaction.guild_id, [])
    return interaction.user.id in admins


def setup(bot) -> None:
    """Register the /terry command group on the bot's command tree."""
    group = app_commands.Group(name="terry", description="terry admin commands")

    @group.command(name="nicks", description="view all player nicknames")
    async def view_nicks_cmd(interaction: discord.Interaction):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        all_nicks = nicknames.get_all(interaction.guild_id)
        if not all_nicks:
            await interaction.response.send_message(
                "no nicknames yet", ephemeral=True
            )
            return
        lines = []
        for user_id_str, nicks in all_nicks.items():
            member = interaction.guild.get_member(int(user_id_str))
            name = member.display_name if member else f"id:{user_id_str}"
            lines.append(f"{name}: {', '.join(nicks)}")
        contents = "\n".join(lines)
        await interaction.response.send_message(
            f"```\n{contents}\n```", ephemeral=True
        )

    @group.command(name="setnick", description="add a nickname for a user")
    @app_commands.describe(user="the user to nickname", nickname="nickname to add")
    async def set_nick_cmd(interaction: discord.Interaction, user: discord.Member, nickname: str):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        nicknames.add_nickname(interaction.guild_id, user.id, nickname)
        log.info(
            f"admin {interaction.user} added nickname for {user} ({user.id}) "
            f"in guild {interaction.guild_id}: {nickname}"
        )
        await interaction.response.send_message(
            f"added nickname `{nickname}` for {user.display_name}", ephemeral=True
        )

    @group.command(name="removenick", description="remove a nickname from a user")
    @app_commands.describe(user="the user", nickname="nickname to remove")
    async def remove_nick_cmd(interaction: discord.Interaction, user: discord.Member, nickname: str):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        if not nicknames.remove_nickname(interaction.guild_id, user.id, nickname):
            await interaction.response.send_message(
                f"`{nickname}` is not a nickname for {user.display_name}", ephemeral=True
            )
            return
        log.info(
            f"admin {interaction.user} removed nickname for {user} ({user.id}) "
            f"in guild {interaction.guild_id}: {nickname}"
        )
        await interaction.response.send_message(
            f"removed nickname `{nickname}` from {user.display_name}", ephemeral=True
        )

    bot.tree.add_command(group)
    log.info("slash commands registered")
