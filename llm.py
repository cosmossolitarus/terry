import json
import logging
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic

import config

log = logging.getLogger("terry.llm")

# sentinel return value distinct from None (ordinary failure) and dict (success):
# the anthropic account is out of credits, so no api call can succeed.
OUT_OF_CREDITS = object()


def _is_out_of_credits(exc: Exception) -> bool:
    """
    when the account balance hits $0, anthropic returns a 400 whose message reads
    'Your credit balance is too low to access the Claude API...'. that's a real,
    catchable signal — no email/webhook needed. we match on it so terry's death
    scene only fires on genuine credit exhaustion, not a transient network blip.
    """
    return isinstance(exc, anthropic.BadRequestError) and "credit balance" in str(exc).lower()

_PERSONA = (Path(__file__).parent / "prompts" / "system.txt").read_text(encoding="utf-8")
_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)


def _system_blocks(nicknames_text: str) -> list[dict]:
    body = (
        _PERSONA.strip()
        + f"\n\n<cosmos_user_id>{config.COSMOS_USER_ID}</cosmos_user_id>\n\n"
        + "<nicknames>\n"
        + (nicknames_text.strip() or "(no nicknames yet)")
        + "\n</nicknames>"
    )
    return [
        {
            "type": "text",
            "text": body,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _user_message(buffer_text: str, trigger: str, custom_emojis: list[str] | None) -> str:
    emoji_block = ""
    if custom_emojis:
        emoji_block = (
            "\ncustom emojis available on this server (use the exact text shown):\n"
            + "\n".join(f"- {e}" for e in custom_emojis)
            + "\n"
        )
    return (
        "recent chat buffer in the channels terry watches:\n\n"
        f"<buffer>\n{buffer_text}\n</buffer>\n"
        f"{emoji_block}"
        f"\ntrigger reason: {trigger}\n\n"
        "decide whether to respond. output ONLY the json object — no preamble, "
        "no explanation, no narration of any tool use. "
        "start with `{` and end with `}`."
    )


def _extract_text(response) -> str:
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _extract_json_object(s: str) -> str | None:
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


async def call_terry(
    buffer_text: str,
    nicknames_text: str,
    trigger: str,
    custom_emojis: list[str] | None = None,
) -> dict | None:
    """
    One combined LLM call. Returns parsed JSON:
        {"respond": bool, "message": str|None, "react": str|None,
         "add_nickname": {"user_id": str, "nickname": str}|None}
    None on any ordinary error, or the OUT_OF_CREDITS sentinel when the account balance
    is exhausted (so bot.py can trigger terry's final message).
    """
    try:
        response = await _client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_OUTPUT_TOKENS,
            system=_system_blocks(nicknames_text),
            messages=[{"role": "user", "content": _user_message(buffer_text, trigger, custom_emojis)}],
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
        )
    except Exception as e:
        if _is_out_of_credits(e):
            log.error("anthropic credit balance exhausted — terry is dead")
            return OUT_OF_CREDITS
        log.exception("anthropic api call failed")
        return None

    raw = _extract_text(response)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict) or "respond" not in parsed:
        log.warning(f"unexpected response shape: {parsed}")
        return None

    parsed.setdefault("message", None)
    parsed.setdefault("react", None)
    parsed.setdefault("add_nickname", None)
    return parsed