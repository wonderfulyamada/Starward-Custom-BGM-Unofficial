
from dataclasses import dataclass


@dataclass
class DetectorScores:
    go: float = 0.0
    victory: float = 0.0
    defeat: float = 0.0


class BattleStateMachine:
    IDLE = "IDLE"
    BATTLE = "BATTLE"
    AWAKENING = "AWAKENING"
    RESULT = "RESULT"

    def __init__(self, cfg, on_event):
        self.cfg = cfg
        self.on_event = on_event
        self.state = self.IDLE
        self.active_streak = 0
        self.normal_streak = 0
        self.result_cooldown = 0
        self.victory_streak = 0
        self.defeat_streak = 0
        self.last_emblem_timestamp = None
        self.emblem_absence_elapsed = 0.0
        self.last_burst_timestamp = None

    def _reset_emblem_absence(self):
        self.last_emblem_timestamp = None
        self.emblem_absence_elapsed = 0.0
        self.last_burst_timestamp = None

    def update(self, timestamp, scores, burst):
        # Result gets priority over all other states.
        if self.state in (self.BATTLE, self.AWAKENING):
            if scores.victory >= self.cfg["victory_threshold"]:
                self.victory_streak += 1
            else:
                self.victory_streak = 0

            if scores.defeat >= self.cfg["defeat_threshold"]:
                self.defeat_streak += 1
            else:
                self.defeat_streak = 0

            if self.victory_streak >= self.cfg["result_confirm_frames"]:
                self.state = self.RESULT
                self.active_streak = self.normal_streak = 0
                self.victory_streak = self.defeat_streak = 0
                self._reset_emblem_absence()
                self.on_event(timestamp, "VICTORY")
                return

            if self.defeat_streak >= self.cfg["result_confirm_frames"]:
                self.state = self.RESULT
                self.active_streak = self.normal_streak = 0
                self.victory_streak = self.defeat_streak = 0
                self._reset_emblem_absence()
                self.on_event(timestamp, "DEFEAT")
                return

        if self.state in (self.IDLE, self.RESULT):
            if scores.go >= self.cfg["go_threshold"]:
                self.state = self.BATTLE
                self.active_streak = self.normal_streak = 0
                self.victory_streak = self.defeat_streak = 0
                self._reset_emblem_absence()
                self.on_event(timestamp, "BATTLE_START")
            return

        if burst.classification == "active":
            self.active_streak += 1
            self.normal_streak = 0
        elif burst.classification == "normal":
            self.normal_streak += 1
            self.active_streak = 0
        else:
            # Unknown means "HUD is obscured / cut-in / effects".
            # Do not change the logical state from one uncertain frame.
            self.active_streak = 0
            self.normal_streak = 0

        if (
            self.state == self.BATTLE
            and self.active_streak >= self.cfg["burst_emblem_confirm_frames"]
        ):
            self.state = self.AWAKENING
            self.active_streak = 0
            self.last_emblem_timestamp = timestamp
            self.emblem_absence_elapsed = 0.0
            self.last_burst_timestamp = timestamp
            self.on_event(timestamp, "AWAKENING_START")
            return

        if self.state == self.AWAKENING:
            elapsed = (
                max(0.0, timestamp - self.last_burst_timestamp)
                if self.last_burst_timestamp is not None else 0.0
            )
            self.last_burst_timestamp = timestamp
            if burst.emblem_score >= self.cfg["burst_emblem_score_min"]:
                self.last_emblem_timestamp = timestamp
                self.emblem_absence_elapsed = 0.0
            elif (
                burst.classification != "unknown"
                and burst.ring_edge >= self.cfg["burst_normal_outer_edge_min"]
            ):
                # Count emblem absence only while the HUD rim proves that the
                # HUD is actually visible. Cut-ins and occlusion pause it.
                self.emblem_absence_elapsed += elapsed

        emblem_timeout = (
            self.state == self.AWAKENING
            and self.last_emblem_timestamp is not None
            and self.emblem_absence_elapsed >= self.cfg["burst_emblem_absence_timeout_seconds"]
        )
        result_pending = self.victory_streak > 0 or self.defeat_streak > 0
        if (
            self.state == self.AWAKENING
            and not result_pending
            and (
                self.normal_streak >= self.cfg["burst_normal_confirm_frames"]
                or emblem_timeout
            )
        ):
            self.state = self.BATTLE
            self.normal_streak = 0
            self._reset_emblem_absence()
            self.on_event(timestamp, "AWAKENING_END")
