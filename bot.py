import logging
import re

import discord
from discord.ext import commands

import config
import death
import gating
import llm
import nicknames
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

    # Build the custom emoji list for this guild
    custom_emojis = [
        f"<{'a' if e.animated else ''}:{e.name}:{e.id}>"
        for e in message.guild.emojis
    ]

    state.is_thinking = True
    try:
        result = await llm.call_terry(
            buffer_text=ctx.render_for_prompt(),
            nicknames_text=nicknames.render_for_prompt(message.guild.id),
            trigger=trigger,
            custom_emojis=custom_emojis,
        )
    finally:
        state.is_thinking = False

    # credits exhausted: terry can't use the api, so he says his one canned goodbye
    # (referencing the last message he responded to) and then goes silent until credits
    # return and calls start succeeding again.
    if result is llm.OUT_OF_CREDITS:
        goodbye = death.get_state().next_goodbye()
        if goodbye:
            try:
                sent = await message.channel.send(
                    goodbye,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False, roles=False, users=True
                    ),
                )
                ctx.add(sent, is_terry=True)
                log.info(f"terry's final message sent: {goodbye[:80]}")
            except Exception:
                log.exception("failed to send terry's final message")
        else:
            log.info("terry is dead and already said goodbye — staying silent")
        state.record_decision(did_respond=False)
        return

    if result is None:
        log.warning("no usable response from llm")
        state.record_decision(did_respond=False)
        return

    # a successful call means terry is alive — clears the death latch if he'd died.
    death.get_state().revive()

    nick_data = result.get("add_nickname")
    if isinstance(nick_data, dict):
        user_id = nick_data.get("user_id")
        nickname = nick_data.get("nickname")
        if user_id and nickname:
            nicknames.add_nickname(message.guild.id, user_id, nickname)
            log.info(f"nickname added: {user_id} -> {nickname}")

    should_respond = bool(result.get("respond"))
    msg_text = result.get("message")
    react_str = result.get("react")

    # Safety net: anything directed at terry must produce a reply if a message was generated.
    # Reaction-only responses to forced triggers are fine.
    if forced and msg_text and not should_respond:
        log.warning("directed at terry but respond=false; forcing send")
        should_respond = True

    did_act = False

    # React first (quicker visual ack)
    if react_str:
        try:
            await message.add_reaction(react_str.strip())
            log.info(f"terry reacted: {react_str}")
            did_act = True
        except Exception:
            log.exception(f"failed to react with: {react_str!r}")

    # Then send the message
    if should_respond and msg_text:
        msg_text_short = msg_text[:1900]
        try:
            sent = await message.channel.send(msg_text_short)
            ctx.add(sent, is_terry=True)
            log.info(f"terry replied: {msg_text_short[:80]}")
            did_act = True
        except Exception:
            log.exception("failed to send terry's message")

    if did_act:
        # remember what terry just responded to, in case this is his last act before death.
        death.get_state().record_success(message.author, message.content)
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