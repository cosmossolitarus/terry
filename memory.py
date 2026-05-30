import re
from datetime import datetime, timezone
from pathlib import Path

import config

_DATE_PREFIX_RE = re.compile(r"^(\[\d{4}-\d{2}-\d{2}\] )")


def _path(guild_id: int) -> Path:
    return config.DATA_DIR / "memories" / f"{guild_id}.txt"


def read(guild_id: int) -> str:
    """Return the full memories file for this guild, or empty string."""
    p = _path(guild_id)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def get_lines(guild_id: int) -> list[str]:
    """Return all non-empty memory lines as a list."""
    content = read(guild_id)
    return [l for l in content.splitlines() if l.strip()]


def _write_lines(guild_id: int, lines: list[str]) -> None:
    _path(guild_id).write_text(
        ("\n".join(lines) + "\n") if lines else "", encoding="utf-8"
    )


def append(guild_id: int, line: str) -> None:
    """Append one memory line. No-op on empty/whitespace input."""
    line = (line or "").replace("\n", " ").strip()
    if not line:
        return
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(_path(guild_id), "a", encoding="utf-8") as f:
        f.write(f"[{date_str}] {line}\n")


def edit_line(guild_id: int, index: int, new_text: str) -> bool:
    """Replace the text of memory at 1-based index, preserving its date prefix.
    Returns False if index is out of range."""
    lines = get_lines(guild_id)
    if index < 1 or index > len(lines):
        return False
    new_text = new_text.replace("\n", " ").strip()
    existing = lines[index - 1]
    m = _DATE_PREFIX_RE.match(existing)
    lines[index - 1] = (m.group(1) if m else "") + new_text
    _write_lines(guild_id, lines)
    return True


def delete_line(guild_id: int, index: int) -> bool:
    """Remove the memory at 1-based index.
    Returns False if index is out of range."""
    lines = get_lines(guild_id)
    if index < 1 or index > len(lines):
        return False
    lines.pop(index - 1)
    _write_lines(guild_id, lines)
    return True