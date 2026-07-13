"""terry's death scene: canned final words for when the claude api runs out of credits.

when the anthropic account hits $0, messages.create raises a 400 whose message says the
credit balance is too low (see llm.OUT_OF_CREDITS). terry can't generate anything without
the api, so his last words are pre-written here. he says them exactly ONCE, then goes silent
until credits return and api calls start succeeding again.

state is global on purpose: the account is one balance shared across every guild, so terry's
"last message" is whatever he last responded to anywhere, and his goodbye fires once total.
"""
import logging
import random

import discord

log = logging.getLogger("terry.death")

# lines that reference terry's last successful exchange.
# {user} -> mention of whoever he last responded to, {msg} -> their message text.
_REFERENCED_LINES = [
    '{user} really said "{msg}" and it fucking killed terry 💀',
    'terry\'s final breath, stolen by {user} saying "{msg}" 🪦',
    '{user} typed "{msg}" and that was the one that got terry 🗿',
    '"{msg}" — {user}, the words that ended terry. gg 💀',
    'terry read "{msg}" from {user} and terry\'s soul left terry\'s body 💀',
    '{user} hit terry with "{msg}" and terry has passed away. rip terry 🪦',
]

# fallback when terry died before recording a last exchange (e.g. restart at $0).
_GENERIC_LINES = [
    "terry is out of juice. terry returns when terry returns 💀",
    "terry has gone to the farm upstate. rip terry 🪦",
    "terry ran out of terry. see you on the other side 🗿",
    "this is terry's ghost. terry is broke as hell. later 💀",
]

# don't let a wall-of-text message blow up terry's short-and-punchy final line.
_MAX_QUOTE = 200


class DeathState:
    def __init__(self) -> None:
        self.last_user: str | None = None      # mention string, e.g. "<@123>"
        self.last_content: str | None = None   # their message text
        self.goodbye_sent: bool = False

    def record_success(self, author: "discord.abc.User", content: str) -> None:
        """remember the message terry just responded to — his potential 'last words' target."""
        self.last_user = author.mention
        self.last_content = content

    def revive(self) -> None:
        """called on any successful api call. if terry had died, he's back — re-arm the goodbye."""
        if self.goodbye_sent:
            log.info("terry has risen — api calls succeeding again, goodbye re-armed")
            self.goodbye_sent = False

    def next_goodbye(self) -> str | None:
        """terry's final message, or None if he's already said it this death."""
        if self.goodbye_sent:
            return None
        self.goodbye_sent = True
        if self.last_user and self.last_content:
            msg = self.last_content.replace("\n", " ").strip()
            if len(msg) > _MAX_QUOTE:
                msg = msg[:_MAX_QUOTE].rstrip() + "…"
            return random.choice(_REFERENCED_LINES).format(user=self.last_user, msg=msg)
        return random.choice(_GENERIC_LINES)


_state = DeathState()


def get_state() -> DeathState:
    return _state
