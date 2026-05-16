from collections import deque
from dataclasses import dataclass
from datetime import datetime

import discord


@dataclass
class BufferedMessage:
    author_id: int
    author_name: str
    content: str
    timestamp: datetime
    channel_id: int
    channel_name: str
    is_terry: bool

    @classmethod
    def from_discord(cls, message: discord.Message, is_terry: bool = False) -> "BufferedMessage":
        channel_name = getattr(message.channel, "name", "unknown")
        return cls(
            author_id=message.author.id,
            author_name=message.author.display_name,
            content=message.content,
            timestamp=message.created_at,
            channel_id=message.channel.id,
            channel_name=channel_name,
            is_terry=is_terry,
        )


class ChannelContext:
    """Per-guild rolling message buffer."""

    def __init__(self, buffer_size: int):
        self.buffer: deque[BufferedMessage] = deque(maxlen=buffer_size)

    def add(self, message: discord.Message, is_terry: bool = False) -> None:
        self.buffer.append(BufferedMessage.from_discord(message, is_terry=is_terry))

    def render_for_prompt(self) -> str:
        """Format the buffer for inclusion in the LLM prompt."""
        if not self.buffer:
            return "(no recent messages)"
        lines = []
        for msg in self.buffer:
            label = "terry" if msg.is_terry else f"{msg.author_name} (id:{msg.author_id})"
            time = msg.timestamp.strftime("%H:%M")
            channel = f"#{msg.channel_name}"
            content = msg.content.replace("\n", " ")
            lines.append(f"[{time}] {channel} {label}: {content}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.buffer)