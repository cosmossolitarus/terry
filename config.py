import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# --- secrets / env ---
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
COSMOS_USER_ID = int(os.environ["COSMOS_USER_ID"])
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))

# --- tunables ---
BUFFER_SIZE = 50
BASELINE_GATING_INTERVAL = 10   # check every N messages by default
HIGH_FREQ_DECAY = 3             # silent checks before reverting to baseline
QUIET_TIME_SILENCE_HOURS = 3    # silent this long before considering a quiet-time ping
QUIET_TIME_COOLDOWN_HOURS = 48  # min hours between quiet-time pings per guild
RESPONSE_COOLDOWN_SECONDS = 20  # min seconds between terry messages, safety valve

MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 1024

# --- guild/channel config ---
_CONFIG_FILE = Path(__file__).parent / "channels.yml"
with open(_CONFIG_FILE) as f:
    _channel_config = yaml.safe_load(f) or {}

MONITORED_CHANNELS: dict[int, list[int]] = {
    int(guild_id): [int(c) for c in channels]
    for guild_id, channels in (_channel_config.get("guilds") or {}).items()
}

ADMIN_USERS: dict[int, list[int]] = {
    int(guild_id): [int(u) for u in users]
    for guild_id, users in (_channel_config.get("admins") or {}).items()
}

# --- ensure data dirs exist ---
(DATA_DIR / "memories").mkdir(parents=True, exist_ok=True)