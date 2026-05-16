from dataclasses import dataclass
from datetime import datetime

import config


@dataclass
class GatingState:
    messages_since_check: int = 0
    in_high_freq_mode: bool = False
    consecutive_silent_decisions: int = 0
    last_response_at: datetime | None = None
    is_thinking: bool = False

    def should_call_llm(self, forced: bool) -> bool:
        """
        forced=True means this message is directed at terry (@mention or name in content);
        bypass message-count gating and the cooldown.
        """
        if self.is_thinking:
            return False

        # Cooldown applies only to organic baseline checks.
        # Skip it for forced triggers AND for high-freq continuation mode,
        # since both represent "terry should be engaging right now."
        apply_cooldown = (
            not forced
            and not self.in_high_freq_mode
            and self.last_response_at is not None
        )
        if apply_cooldown:
            elapsed = (datetime.now() - self.last_response_at).total_seconds()
            if elapsed < config.RESPONSE_COOLDOWN_SECONDS:
                return False

        if forced:
            return True

        self.messages_since_check += 1
        threshold = 1 if self.in_high_freq_mode else config.BASELINE_GATING_INTERVAL
        if self.messages_since_check >= threshold:
            self.messages_since_check = 0
            return True
        return False

    def record_decision(self, did_respond: bool) -> None:
        if did_respond:
            self.in_high_freq_mode = True
            self.consecutive_silent_decisions = 0
            self.last_response_at = datetime.now()
        else:
            if self.in_high_freq_mode:
                self.consecutive_silent_decisions += 1
                if self.consecutive_silent_decisions >= config.HIGH_FREQ_DECAY:
                    self.in_high_freq_mode = False
                    self.consecutive_silent_decisions = 0


_states: dict[int, GatingState] = {}


def get_state(guild_id: int) -> GatingState:
    if guild_id not in _states:
        _states[guild_id] = GatingState()
    return _states[guild_id]