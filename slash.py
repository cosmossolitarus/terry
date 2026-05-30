"""Slash commands for terry. Admin-only, scoped per guild."""
import io
import logging

import discord
from discord import app_commands

import config
import memory

log = logging.getLogger("terry.slash")


def _is_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is None:
        return False
    admins = config.ADMIN_USERS.get(interaction.guild_id, [])
    return interaction.user.id in admins


def setup(bot) -> None:
    """Register the /terry command group on the bot's command tree."""
    group = app_commands.Group(name="terry", description="terry admin commands")

    @group.command(name="memory", description="add a long-term memory for terry")
    @app_commands.describe(text="the memory to append")
    async def add_memory_cmd(interaction: discord.Interaction, text: str):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        memory.append(interaction.guild_id, text)
        log.info(
            f"admin {interaction.user} added memory in guild "
            f"{interaction.guild_id}: {text[:80]}"
        )
        await interaction.response.send_message(
            f"added: `{text[:200]}`", ephemeral=True
        )

    @group.command(name="memories", description="view terry's memory file")
    async def view_memories_cmd(interaction: discord.Interaction):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        lines = memory.get_lines(interaction.guild_id)
        if not lines:
            await interaction.response.send_message(
                "no memories yet", ephemeral=True
            )
            return
        numbered = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))
        if len(numbered) <= 1900:
            await interaction.response.send_message(
                f"```\n{numbered}\n```", ephemeral=True
            )
        else:
            f = discord.File(
                io.BytesIO(numbered.encode("utf-8")),
                filename=f"terry_memories_{interaction.guild_id}.txt",
            )
            await interaction.response.send_message(file=f, ephemeral=True)

    @group.command(name="editmemory", description="edit a memory by its line number")
    @app_commands.describe(index="line number from /terry memories", text="replacement text")
    async def edit_memory_cmd(interaction: discord.Interaction, index: int, text: str):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        if not memory.edit_line(interaction.guild_id, index, text):
            await interaction.response.send_message(
                f"no memory at line {index}", ephemeral=True
            )
            return
        log.info(
            f"admin {interaction.user} edited memory #{index} in guild "
            f"{interaction.guild_id}: {text[:80]}"
        )
        await interaction.response.send_message(
            f"line {index} updated: `{text[:200]}`", ephemeral=True
        )

    @group.command(name="deletememory", description="delete a memory by its line number")
    @app_commands.describe(index="line number from /terry memories")
    async def delete_memory_cmd(interaction: discord.Interaction, index: int):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "this command is admin-only", ephemeral=True
            )
            return
        lines = memory.get_lines(interaction.guild_id)
        if index < 1 or index > len(lines):
            await interaction.response.send_message(
                f"no memory at line {index}", ephemeral=True
            )
            return
        deleted = lines[index - 1]
        memory.delete_line(interaction.guild_id, index)
        log.info(
            f"admin {interaction.user} deleted memory #{index} in guild "
            f"{interaction.guild_id}: {deleted[:80]}"
        )
        await interaction.response.send_message(
            f"deleted line {index}: `{deleted[:200]}`", ephemeral=True
        )

    bot.tree.add_command(group)
    log.info("slash commands registered")