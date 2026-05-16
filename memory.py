from datetime import datetime, timezone
from pathlib import Path

import config


def _path(guild_id: int) -> Path:
    return config.DATA_DIR / "memories" / f"{guild_id}.txt"


def read(guild_id: int) -> str:
    """Return the full memories file for this guild, or empty string."""
    p = _path(guild_id)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def append(guild_id: int, line: str) -> None:
    """Append one memory line. No-op on empty/whitespace input."""
    line = (line or "").replace("\n", " ").strip()
    if not line:
        return
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(_path(guild_id), "a", encoding="utf-8") as f:
        f.write(f"[{date_str}] {line}\n")