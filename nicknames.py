import json
from pathlib import Path

import config


def _path(guild_id: int) -> Path:
    return config.DATA_DIR / "nicknames" / f"{guild_id}.json"


def _load(guild_id: int) -> dict[str, list[str]]:
    p = _path(guild_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(guild_id: int, data: dict[str, list[str]]) -> None:
    _path(guild_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


def render_for_prompt(guild_id: int) -> str:
    data = _load(guild_id)
    lines = [
        f"user {uid}: {', '.join(nicks)}"
        for uid, nicks in data.items()
        if nicks
    ]
    return "\n".join(lines) if lines else "(no nicknames yet)"


def add_nickname(guild_id: int, user_id: int | str, nickname: str) -> None:
    nickname = nickname.strip()
    if not nickname:
        return
    user_id = str(user_id)
    data = _load(guild_id)
    if user_id not in data:
        data[user_id] = []
    if nickname not in data[user_id]:
        data[user_id].append(nickname)
        _save(guild_id, data)


def remove_nickname(guild_id: int, user_id: int | str, nickname: str) -> bool:
    """Remove a specific nickname. Returns True if found and removed."""
    user_id = str(user_id)
    nickname = nickname.strip()
    data = _load(guild_id)
    if user_id not in data or nickname not in data[user_id]:
        return False
    data[user_id].remove(nickname)
    if not data[user_id]:
        del data[user_id]
    _save(guild_id, data)
    return True


def get_all(guild_id: int) -> dict[str, list[str]]:
    return _load(guild_id)


def get_for_user(guild_id: int, user_id: int | str) -> list[str]:
    return _load(guild_id).get(str(user_id), [])
