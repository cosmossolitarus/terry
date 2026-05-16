import json
import logging
from pathlib import Path

from anthropic import AsyncAnthropic

import config

log = logging.getLogger("terry.llm")

_PERSONA = (Path(__file__).parent / "prompts" / "system.txt").read_text(encoding="utf-8")
_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)


def _system_blocks(memories_text: str) -> list[dict]:
    body = (
        _PERSONA.strip()
        + f"\n\n<cosmos_user_id>{config.COSMOS_USER_ID}</cosmos_user_id>\n\n"
        + "<memories>\n"
        + (memories_text.strip() or "(no memories yet)")
        + "\n</memories>"
    )
    return [
        {
            "type": "text",
            "text": body,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _user_message(buffer_text: str, trigger: str) -> str:
    return (
        "recent chat buffer in the channels terry watches:\n\n"
        f"<buffer>\n{buffer_text}\n</buffer>\n\n"
        f"trigger reason: {trigger}\n\n"
        "decide whether to respond. output the json now."
    )


def _extract_text(response) -> str:
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _extract_json_object(s: str) -> str | None:
    """
    Find the first complete top-level JSON object in s.
    Returns None if no balanced object is found (e.g. truncated output).
    Handles braces inside strings correctly.
    """
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _parse_json(raw: str) -> dict | None:
    obj = _extract_json_object(raw)
    if obj is None:
        log.warning(f"no balanced json object found; raw response: {raw[:300]!r}")
        return None
    try:
        return json.loads(obj)
    except json.JSONDecodeError as e:
        log.warning(f"json parse failed: {e}; extracted: {obj[:300]!r}")
        return None


def _user_message(buffer_text: str, trigger: str) -> str:
    return (
        "recent chat buffer in the channels terry watches:\n\n"
        f"<buffer>\n{buffer_text}\n</buffer>\n\n"
        f"trigger reason: {trigger}\n\n"
        "decide whether to respond. output ONLY the json object — no preamble, "
        "no explanation, no narration of any tool use. "
        "start with `{` and end with `}`."
    )


async def call_terry(buffer_text: str, memories_text: str, trigger: str) -> dict | None:
    """
    One combined LLM call. Returns parsed JSON:
        {"respond": bool, "message": str|None, "add_memory": str|None}
    or None on any error.
    """
    try:
        response = await _client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_OUTPUT_TOKENS,
            system=_system_blocks(memories_text),
            messages=[{"role": "user", "content": _user_message(buffer_text, trigger)}],
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
        )
    except Exception:
        log.exception("anthropic api call failed")
        return None

    raw = _extract_text(response)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict) or "respond" not in parsed:
        log.warning(f"unexpected response shape: {parsed}")
        return None

    parsed.setdefault("message", None)
    parsed.setdefault("add_memory", None)
    return parsed