
from dataclasses import dataclass


@dataclass
class DetectorScores:
    go: float = 0.0
    victory: float = 0.0
    defeat: float = 0.0
    blackout: bool = False
    blackout_brightness: float | None = None


class BattleStateMachine:
    IDLE = "IDLE"
    BATTLE = "BATTLE"
    READY = "READY"
    AWAKENING = "AWAKENING"
    RESULT = "RESULT"

    def __init__(self, cfg, on_event):
        self.cfg = cfg
        self.on_event = on_event
        self.state = self.IDLE
        self.hud_lost_streak = 0
        self.gauge_decrease_streak = 0
        self.gauge_recovery_streak = 0
        self.result_cooldown = 0
        self.victory_streak = 0
        self.defeat_streak = 0
        self.last_visible_gauge = None
        self.ready_gauge = None
        self.ready_decrease_samples = []
        self.awakening_started_at = None
        self.awakening_gauge_samples = []
        self.glow_confirmed = False
        self.glow_absence_count = 0
        self.awakening_end_streak = 0
        self.pending_awakening_input_at = None
        self.pending_awakening_normal_seen = False
        self.pending_awakening_last_cutin_status = None
        self._last_input_assist_active = False
        self._last_input_assist_recent = False
        self.result_blackout_streak = 0
        self.result_sample_count = 0
        self.debug = bool(cfg.get("_debug", False))

    def _debug(self, message):
        if self.debug:
            print(message)

    def _set_state(self, state, reason):
        previous = self.state
        self.state = state
        logger = getattr(self, "diagnostic_logger", None)
        if logger and previous != state:
            logger.info("state_transition from=%s to=%s reason=%s", previous, state, reason)

    def _reset_gauge_tracking(self, reason="unspecified"):
        if any((
            self.hud_lost_streak,
            self.gauge_decrease_streak,
            self.gauge_recovery_streak,
            self.last_visible_gauge is not None,
            self.ready_gauge is not None,
            self.ready_decrease_samples,
            self.awakening_started_at is not None,
            self.awakening_gauge_samples,
            self.glow_confirmed,
            self.glow_absence_count,
            self.awakening_end_streak,
            self.pending_awakening_input_at is not None,
            self.pending_awakening_normal_seen,
        )):
            self._debug(f"GAUGE history reset reason={reason}")
        self.hud_lost_streak = 0
        self.gauge_decrease_streak = 0
        self.gauge_recovery_streak = 0
        self.last_visible_gauge = None
        self.ready_gauge = None
        self.ready_decrease_samples = []
        self.awakening_started_at = None
        self.awakening_gauge_samples = []
        self.glow_confirmed = False
        self.glow_absence_count = 0
        self.awakening_end_streak = 0
        self.pending_awakening_input_at = None
        self.pending_awakening_normal_seen = False
        self.pending_awakening_last_cutin_status = None

    def _begin_awakening_tracking(self, timestamp, gauge=None):
        """Start end-detection history without affecting start confirmation."""
        self.awakening_started_at = timestamp
        self.awakening_gauge_samples = []
        if gauge is not None:
            self.awakening_gauge_samples.append((timestamp, gauge))

    def _awakening_end_condition(self, gauge, burst):
        """Require one current, observable gauge-and-glow end sample."""
        classification = getattr(burst, "glow_classification", None)
        observable = bool(getattr(burst, "hud_observable", False))
        score = getattr(burst, "glow_score", None)
        required = max(2, int(self.cfg.get("burst_end_confirm_frames", 4)))
        combined = (
            observable
            and classification == "ABSENT"
        )
        self.awakening_end_streak = self.awakening_end_streak + 1 if combined else 0
        self._debug(
            "AWAKENING_END evaluate "
            f"gauge={gauge:.3f} gauge_ignored=true "
            f"glow_score={score if score is not None else 'n/a'} "
            f"classification={classification} hud_observable={observable} "
            f"combined={combined} consecutive={self.awakening_end_streak}/{required}"
        )
        return self.awakening_end_streak >= required

    def _gauge_delta(self, gauge):
        if self.last_visible_gauge is None or gauge is None:
            return 0.0
        return gauge - self.last_visible_gauge

    def handle_log_event(self, timestamp, event):
        """Apply a game-log state signal alongside the screen-driven updates."""
        previous_state = self.state
        if event == "BATTLE_START":
            if self.state not in (self.IDLE, self.RESULT):
                self._debug(
                    f"GAME_LOG transition timestamp={timestamp:.3f} event={event} "
                    f"state={previous_state}->{self.state} ignored=already_active"
                )
                return
            self._set_state(self.BATTLE, "log_battle_start")
            self._reset_gauge_tracking("log_battle_start")
            self.result_blackout_streak = 0
            self.result_sample_count = 0
            self.victory_streak = self.defeat_streak = 0
            self.on_event(timestamp, "BATTLE_START")
        elif event == "BATTLE_END" and self.state in (self.BATTLE, self.READY, self.AWAKENING):
            # The log does not identify victory versus defeat. Leave screen
            # recognition in control of that existing transition.
            self.on_event(timestamp, "BATTLE_END")
        elif event == "LOBBY":
            self._set_state(self.IDLE, "log_lobby")
            self._reset_gauge_tracking("log_lobby")
            self.result_blackout_streak = 0
            self.result_sample_count = 0
            self.on_event(timestamp, "LOBBY")
        elif event in ("MATCH_MATCHING", "MATCH_CONFIRMING", "MATCH_CONFIRMED", "BATTLE_HINT"):
            self.on_event(timestamp, event)
        self._debug(
            f"GAME_LOG transition timestamp={timestamp:.3f} event={event} "
            f"state={previous_state}->{self.state}"
        )

    def update(self, timestamp, scores, burst, input_assist_active=False, input_assist_recent=False, consume_input_assist=None):
        input_active_rising = input_assist_active and not self._last_input_assist_active
        input_recent_rising = input_assist_recent and not self._last_input_assist_recent
        self._last_input_assist_active = input_assist_active
        self._last_input_assist_recent = input_assist_recent
        if self.state == self.RESULT and self.cfg.get("result_bgm_enabled", False):
            self.result_sample_count += 1
            brightness = (
                f"{scores.blackout_brightness:.2f}"
                if scores.blackout_brightness is not None else "n/a"
            )
            if scores.blackout:
                self.result_blackout_streak += 1
                self._debug(
                    "RESULT blackout "
                    f"brightness={brightness} sample={self.result_sample_count} "
                    f"consecutive={self.result_blackout_streak}"
                )
                if self.result_blackout_streak >= self.cfg.get("result_blackout_confirm_frames", 2):
                    self._set_state(self.IDLE, "result_blackout")
                    self.result_blackout_streak = 0
                    self._debug("RESULT_END transition=IDLE")
                    self.on_event(timestamp, "RESULT_END")
                    return
            else:
                if self.result_blackout_streak or self.result_sample_count == 1:
                    self._debug(
                        "RESULT blackout "
                        f"brightness={brightness} sample={self.result_sample_count} "
                        "consecutive=0"
                    )
                self.result_blackout_streak = 0

        # Result gets priority over all other states.
        if self.state in (self.BATTLE, self.READY, self.AWAKENING):
            if scores.victory >= self.cfg["victory_threshold"]:
                self.victory_streak += 1
            else:
                self.victory_streak = 0

            if scores.defeat >= self.cfg["defeat_threshold"]:
                self.defeat_streak += 1
            else:
                self.defeat_streak = 0

            if self.victory_streak >= self.cfg["result_confirm_frames"]:
                self._set_state(self.RESULT, "victory")
                self._reset_gauge_tracking("result_victory")
                self.result_blackout_streak = 0
                self.result_sample_count = 0
                self._debug("RESULT enter event=VICTORY")
                self.victory_streak = self.defeat_streak = 0
                self.on_event(timestamp, "VICTORY")
                return

            if self.defeat_streak >= self.cfg["result_confirm_frames"]:
                self._set_state(self.RESULT, "defeat")
                self._reset_gauge_tracking("result_defeat")
                self.result_blackout_streak = 0
                self.result_sample_count = 0
                self._debug("RESULT enter event=DEFEAT")
                self.victory_streak = self.defeat_streak = 0
                self.on_event(timestamp, "DEFEAT")
                return

        if self.state in (self.IDLE, self.RESULT):
            if scores.go >= self.cfg["go_threshold"]:
                self._set_state(self.BATTLE, "battle_start")
                self._reset_gauge_tracking("battle_start")
                self.result_blackout_streak = 0
                self.result_sample_count = 0
                self.victory_streak = self.defeat_streak = 0
                self.on_event(timestamp, "BATTLE_START")
            return

        ready = self.state == self.READY
        input_enabled = self.cfg.get("gamepad_input_assist_enabled", False)
        cut_in_status = getattr(burst, "classification", None)
        cut_in_unknown = cut_in_status == "unknown"
        pending_window = max(0.0, float(self.cfg.get("gamepad_awakening_recent_ms", 500))) / 1000.0
        if (
            self.pending_awakening_input_at is not None
            and timestamp - self.pending_awakening_input_at > pending_window
        ):
            self._debug("AWAKENING_START pending_input expired")
            self.pending_awakening_input_at = None
            self.pending_awakening_normal_seen = False
            self.pending_awakening_last_cutin_status = None
        had_pending_input = self.pending_awakening_input_at is not None
        pending_previous_status = self.pending_awakening_last_cutin_status
        new_input = input_active_rising or input_recent_rising
        if ready and input_enabled and new_input and not had_pending_input:
            self.pending_awakening_input_at = timestamp
            # The input sample is the normal-before-cut-in baseline when the
            # combo is pressed while the HUD is still normally visible.
            self.pending_awakening_normal_seen = cut_in_status == "normal"
            self.pending_awakening_last_cutin_status = cut_in_status
            self._debug(
                "AWAKENING_START pending_input latched "
                f"source={'active' if input_active_rising else 'recent'} "
                f"normal_baseline={self.pending_awakening_normal_seen}"
            )
        normal_to_unknown = (
            had_pending_input
            and self.pending_awakening_normal_seen
            and pending_previous_status == "normal"
            and cut_in_unknown
        )
        if had_pending_input:
            if cut_in_status == "normal":
                self.pending_awakening_normal_seen = True
            self.pending_awakening_last_cutin_status = cut_in_status
        if ready:
            reasons = []
            if not input_enabled:
                reasons.append("gamepad_assist_disabled")
            if not normal_to_unknown:
                reasons.append("normal_to_unknown_transition_missing")
            if not had_pending_input:
                reasons.append("pending_input_missing")
            self._debug(
                "AWAKENING_START gate "
                f"ready={ready} cutin_status={cut_in_status} "
                f"gamepad_active={input_assist_active} gamepad_recent={input_assist_recent} "
                f"pending_input={had_pending_input} "
                f"pending_normal_seen={self.pending_awakening_normal_seen} "
                f"pending_previous_status={pending_previous_status} "
                f"decision={'accept' if not reasons else 'reject'} "
                f"reason={','.join(reasons) if reasons else 'all_conditions_met'}"
            )
        if ready and input_enabled and normal_to_unknown:
            self._set_state(self.AWAKENING, "awakening_start")
            self.gauge_recovery_streak = 0
            self._begin_awakening_tracking(timestamp, self.last_visible_gauge)
            reason = "ready_pending_input_normal_to_unknown"
            self._debug(f"AWAKENING_START confirmed reason={reason}")
            self.pending_awakening_input_at = None
            self.pending_awakening_normal_seen = False
            self.pending_awakening_last_cutin_status = None
            if consume_input_assist is not None:
                consume_input_assist()
            self.on_event(timestamp, "AWAKENING_START")
            return

        visible = (
            bool(getattr(burst, "hud_observable", False))
            and burst.gauge_level is not None
            if self.state == self.AWAKENING
            else burst.classification == "normal" and burst.gauge_level is not None
        )
        if not visible:
            if self.state == self.BATTLE:
                self.hud_lost_streak += 1
                self._debug(
                    "BATTLE -> READY candidate "
                    f"hud=missing consecutive={self.hud_lost_streak} "
                    f"required={self.cfg['burst_hud_loss_confirm_frames']}"
                )
                if self.hud_lost_streak >= self.cfg["burst_hud_loss_confirm_frames"]:
                    self._set_state(self.READY, "hud_missing_confirmed")
                    self.ready_gauge = self.last_visible_gauge
                    self.gauge_decrease_streak = 0
                    self.ready_decrease_samples = []
                    self._debug(
                        "BATTLE -> READY enter "
                        "reason=hud_missing_confirmed "
                        f"hud=missing consecutive={self.hud_lost_streak} "
                        f"ready_gauge={self.ready_gauge}"
                    )
            if self.state == self.AWAKENING:
                self.awakening_end_streak = 0
                self._debug("AWAKENING_END reject reason=hud_or_icon_unavailable consecutive=0")
            # HUD obstruction never ends an existing awakening.
            return

        gauge = burst.gauge_level
        if self.state == self.BATTLE and self.hud_lost_streak:
            self._debug(
                "BATTLE -> READY candidate "
                f"hud=visible consecutive=0 reason=hud_recovered"
            )
        self.hud_lost_streak = 0
        if self.state == self.READY:
            # READY is a latch: a recovered HUD is not evidence that the
            # player cancelled it.  Only gamepad evidence above can consume
            # this state and begin Awakening.
            self._debug(
                "READY latched "
                f"gauge={gauge:.3f} input_active={input_assist_active} "
                f"input_recent={input_assist_recent}"
            )
        elif self.state == self.AWAKENING:
            if self._awakening_end_condition(gauge, burst):
                self._debug("AWAKENING_END confirmed reason=near_zero_gauge_and_glow_absent")
                self._set_state(self.BATTLE, "awakening_end")
                self._reset_gauge_tracking("awakening_end")
                self.on_event(timestamp, "AWAKENING_END")

        self.last_visible_gauge = gauge
