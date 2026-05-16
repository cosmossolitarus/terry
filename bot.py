import logging
import re

import discord
from discord.ext import commands

import config
import gating
import llm
import memory
import slash
from context import ChannelContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("terry")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Matches "terry" as a standalone word, case insensitive.
# Word boundaries mean "terrycloth" won't match but "terry's" and "Terry!" will.
_TERRY_NAME_RE = re.compile(r"\bterry\b", re.IGNORECASE)

_contexts: dict[int, ChannelContext] = {}


def get_context(guild_id: int) -> ChannelContext:
    if guild_id not in _contexts:
        _contexts[guild_id] = ChannelContext(buffer_size=config.BUFFER_SIZE)
    return _contexts[guild_id]


@bot.event
async def on_ready():
    log.info(f"terry online as {bot.user} (id: {bot.user.id})")
    for guild in bot.guilds:
        log.info(f"  guild: {guild.name} (id: {guild.id})")
        monitored = config.MONITORED_CHANNELS.get(guild.id, [])
        if monitored:
            log.info(f"    monitoring {len(monitored)} channel(s)")
        else:
            log.warning(f"    NOT in channels.yml — terry will ignore this guild")
    try:
        synced = await bot.tree.sync()
        log.info(f"synced {len(synced)} slash command(s)")
    except Exception:
        log.exception("failed to sync slash commands")


@bot.event
async def on_message(message: discord.Message):
    if message.author.id == bot.user.id:
        return
    if message.guild is None:
        return
    if message.guild.id not in config.MONITORED_CHANNELS:
        return
    if message.channel.id not in config.MONITORED_CHANNELS[message.guild.id]:
        return

    ctx = get_context(message.guild.id)
    ctx.add(message)
    log.info(
        f"[{message.guild.name} #{message.channel.name}] "
        f"{message.author.display_name}: {message.content[:80]}"
    )

    # Detect forced triggers: @mention or "terry" in content
    is_mention = bot.user.mentioned_in(message)
    is_named = bool(_TERRY_NAME_RE.search(message.content))
    forced = is_mention or is_named

    state = gating.get_state(message.guild.id)
    if not state.should_call_llm(forced):
        return

    if is_mention:
        trigger = "@mention - terry must respond"
    elif is_named:
        trigger = "terry's name was used in chat - terry must respond"
    else:
        trigger = "organic check - decide whether to respond"

    state.is_thinking = True
    try:
        result = await llm.call_terry(
            buffer_text=ctx.render_for_prompt(),
            memories_text=memory.read(message.guild.id),
            trigger=trigger,
        )
    finally:
        state.is_thinking = False

    if result is None:
        log.warning("no usable response from llm")
        state.record_decision(did_respond=False)
        return

    if result.get("add_memory"):
        memory.append(message.guild.id, result["add_memory"])
        log.info(f"memory added: {result['add_memory'][:80]}")

    should_respond = bool(result.get("respond"))
    msg_text = result.get("message")

    # Safety net: anything directed at terry must produce a reply if a message was generated
    if forced and msg_text and not should_respond:
        log.warning("directed at terry but respond=false; forcing send")
        should_respond = True

    if should_respond and msg_text:
        msg_text = msg_text[:1900]
        try:
            sent = await message.channel.send(msg_text)
            ctx.add(sent, is_terry=True)
            log.info(f"terry replied: {msg_text[:80]}")
        except Exception:
            log.exception("failed to send terry's message")
            state.record_decision(did_respond=False)
            return
        state.record_decision(did_respond=True)
    else:
        log.info("terry stayed silent")
        state.record_decision(did_respond=False)

slash.setup(bot)

if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            log.info("attempting to connect to discord...")
            async with bot:
                await bot.start(config.DISCORD_BOT_TOKEN)
        except Exception:
            log.exception("bot startup failed")

    asyncio.run(main())