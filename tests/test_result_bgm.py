from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from audio import PygameAudio
from gui import App
from state_machine import BattleStateMachine, DetectorScores


class ResultBgmAudioTests(unittest.TestCase):
    def make_audio(self, enabled):
        audio = PygameAudio.__new__(PygameAudio)
        audio.cfg = {
            "result_bgm_enabled": enabled,
            "victory_bgm": "victory.ogg",
            "defeat_bgm": "defeat.ogg",
        }
        audio.library = SimpleNamespace(root=Path("BGM"))
        audio.fadeout = Mock()
        audio.stop = Mock()
        audio._play = Mock()
        return audio

    def test_disabled_result_bgm_preserves_fadeout(self):
        audio = self.make_audio(False)
        audio.on_event("VICTORY")
        audio.fadeout.assert_called_once_with()
        audio.stop.assert_not_called()
        audio._play.assert_not_called()

    def test_victory_plays_one_shot_result_bgm(self):
        audio = self.make_audio(True)
        audio.on_event("VICTORY")
        audio.stop.assert_not_called()
        audio.fadeout.assert_called_once_with(0)
        audio._play.assert_called_once_with(Path("BGM") / "victory.ogg", loops=0)

    def test_defeat_plays_one_shot_result_bgm(self):
        audio = self.make_audio(True)
        audio.on_event("DEFEAT")
        audio.stop.assert_not_called()
        audio.fadeout.assert_called_once_with(0)
        audio._play.assert_called_once_with(Path("BGM") / "defeat.ogg", loops=0)

    def test_result_end_stops_result_bgm(self):
        audio = self.make_audio(True)
        audio.on_event("RESULT_END")
        audio.stop.assert_called_once_with()

    def test_grouped_victory_setting_resolves_within_selected_group(self):
        audio = self.make_audio(True)
        selected = Path("BGM/Results/victory.ogg")
        audio.cfg.update({"victory_bgm_group": "Results", "victory_bgm_track": "Results/victory.ogg"})
        audio.library.resolve_track = Mock(return_value=selected)
        audio.on_event("VICTORY")
        audio.library.resolve_track.assert_called_once_with("Results/victory.ogg", "Results")
        audio._play.assert_called_once_with(selected, loops=0)

    def test_victory_plays_from_its_saved_track_offset(self):
        audio = self.make_audio(True)
        track = Path("BGM/Results/victory.ogg")
        audio.library.resolve_track = Mock(return_value=track)
        audio.library.awakening_offset = Mock(return_value=12.5)
        audio.on_event("VICTORY")
        audio._play.assert_called_once_with(track, loops=0, start_seconds=12.5)

    def test_defeat_plays_from_its_saved_track_offset(self):
        audio = self.make_audio(True)
        track = Path("BGM/Results/defeat.ogg")
        audio.library.resolve_track = Mock(return_value=track)
        audio.library.awakening_offset = Mock(return_value=8.0)
        audio.on_event("DEFEAT")
        audio._play.assert_called_once_with(track, loops=0, start_seconds=8.0)

    def test_lobby_event_starts_enabled_lobby_bgm(self):
        audio = self.make_audio(True)
        audio.cfg.update({"lobby_bgm_enabled": True, "lobby_bgm_group": "Lobby", "lobby_bgm_track": "Lobby/lobby.ogg"})
        track = Path("BGM/Lobby/lobby.ogg")
        audio.library.resolve_track = Mock(return_value=track)
        audio.library.awakening_offset = Mock(return_value=3.0)
        audio.on_event("LOBBY")
        audio.stop.assert_not_called()
        audio._play.assert_called_once_with(track, loops=-1, start_seconds=0.0)
        audio.library.awakening_offset.assert_not_called()

    def test_only_confirmed_starts_match_bgm(self):
        audio = self.make_audio(True)
        audio.cfg.update({"match_bgm_enabled": True, "match_bgm_group": "Match", "match_bgm_track": "Match/match.ogg"})
        track = Path("BGM/Match/match.ogg")
        audio.library.resolve_track = Mock(return_value=track)
        audio.library.awakening_offset = Mock(return_value=0.0)
        audio.on_event("MATCH_MATCHING")
        audio.on_event("MATCH_CONFIRMING")
        audio._play.assert_not_called()
        audio.on_event("MATCH_CONFIRMED")
        audio._play.assert_called_once_with(track, loops=-1, start_seconds=0.0)

    def test_screen_go_replaces_match_bgm_with_battle_bgm(self):
        audio = self.make_audio(True)
        audio.context_track = "match"
        battle = Path("BGM/Default/battle.ogg")
        audio.library.choose = Mock(return_value=battle)
        audio.cfg.update({"bgm_playback_mode": "Fixed", "bgm_playback_scope": "All BGM"})
        audio.on_event("BATTLE_START")
        audio.fadeout.assert_called_once_with(0)
        audio._play.assert_called_once_with(battle)

    def test_lobby_modes_choose_only_the_configured_group_and_use_offset(self):
        audio = self.make_audio(True)
        track = Path("BGM/Lobby/random.ogg")
        audio.library.choose = Mock(return_value=track)
        audio.library.awakening_offset = Mock(return_value=4.0)
        for mode in ("Fixed", "Balanced Random", "True Random"):
            audio.context_track = None
            audio._play.reset_mock()
            audio.cfg.update({"lobby_bgm_enabled": True, "lobby_bgm_group": "Lobby", "lobby_bgm_track": "Lobby/fixed.ogg", "lobby_bgm_playback_mode": mode})
            audio.on_event("LOBBY")
            audio.library.choose.assert_called_with(mode, "Lobby", "Lobby/fixed.ogg")
            audio._play.assert_called_once_with(track, loops=-1, start_seconds=0.0)

    def test_match_modes_choose_only_the_configured_group_and_use_offset(self):
        audio = self.make_audio(True)
        track = Path("BGM/Match/random.ogg")
        audio.library.choose = Mock(return_value=track)
        audio.library.awakening_offset = Mock(return_value=6.0)
        for mode in ("Fixed", "Balanced Random", "True Random"):
            audio.context_track = None
            audio._play.reset_mock()
            audio.cfg.update({"match_bgm_enabled": True, "match_bgm_group": "Match", "match_bgm_track": "Match/fixed.ogg", "match_bgm_playback_mode": mode})
            audio.on_event("MATCH_CONFIRMED")
            audio.library.choose.assert_called_with(mode, "Match", "Match/fixed.ogg")
            audio._play.assert_called_once_with(track, loops=-1, start_seconds=0.0)

    def test_duplicate_lobby_and_match_events_do_not_restart_context_audio(self):
        audio = self.make_audio(True)
        audio.cfg.update({"lobby_bgm_enabled": True, "lobby_bgm_group": "Lobby", "match_bgm_enabled": True, "match_bgm_group": "Match"})
        audio.library.choose = Mock(return_value=Path("BGM/context.ogg"))
        audio.library.awakening_offset = Mock(return_value=0.0)
        audio.on_event("LOBBY")
        audio.on_event("LOBBY")
        self.assertEqual(audio._play.call_count, 1)
        audio.on_event("MATCH_CONFIRMED")
        audio.on_event("MATCH_CONFIRMED")
        self.assertEqual(audio._play.call_count, 2)

    def test_lobby_to_match_uses_delayed_handoff(self):
        audio = self.make_audio(True)
        audio.context_track = "lobby"
        audio.cfg.update({"match_bgm_enabled": True, "match_bgm_group": "Match", "awakening_crossfade_ms": 250})
        audio.library.choose = Mock(return_value=Path("BGM/Match/match.ogg"))
        timer = Mock()
        with patch("audio.threading.Timer", return_value=timer) as timer_class:
            audio.on_event("MATCH_CONFIRMED")
        audio.fadeout.assert_called_once_with(250)
        audio._play.assert_not_called()
        timer.start.assert_called_once_with()
        timer_class.call_args.args[1]()
        audio._play.assert_called_once_with(Path("BGM/Match/match.ogg"), loops=-1, start_seconds=0.0)

    def test_screen_go_cancels_pending_match_and_delays_battle(self):
        audio = self.make_audio(True)
        audio.cfg.update({"match_bgm_enabled": True, "match_bgm_group": "Match", "awakening_crossfade_ms": 250, "bgm_playback_scope": "All BGM"})
        match = Path("BGM/Match/match.ogg")
        battle = Path("BGM/Default/battle.ogg")
        audio.library.choose = Mock(side_effect=[match, battle])
        timers = [Mock(), Mock()]
        with patch("audio.threading.Timer", side_effect=timers) as timer_class:
            audio.on_event("MATCH_CONFIRMED")
            stale_callback = timer_class.call_args_list[0].args[1]
            audio.on_event("BATTLE_START")
            battle_callback = timer_class.call_args_list[1].args[1]
        timers[0].cancel.assert_called_once_with()
        stale_callback()
        audio._play.assert_not_called()
        battle_callback()
        audio._play.assert_called_once_with(battle)

    def test_result_to_lobby_fades_before_delayed_start(self):
        audio = self.make_audio(True)
        audio.cfg.update({"lobby_bgm_enabled": True, "lobby_bgm_group": "Lobby", "awakening_crossfade_ms": 250})
        lobby = Path("BGM/Lobby/lobby.ogg")
        audio.library.choose = Mock(return_value=lobby)
        timer = Mock()
        with patch("audio.threading.Timer", return_value=timer) as timer_class:
            audio.on_event("LOBBY")
        audio.stop.assert_not_called()
        audio.fadeout.assert_called_once_with(250)
        audio._play.assert_not_called()
        timer_class.call_args.args[1]()
        audio._play.assert_called_once_with(lobby, loops=-1, start_seconds=0.0)


class AwakeningBgmAudioTests(unittest.TestCase):
    def make_audio(self, enabled=True, group="Awakening"):
        audio = PygameAudio.__new__(PygameAudio)
        audio.cfg = {
            "awakening_bgm_enabled": enabled,
            "awakening_bgm_group": group,
            "result_bgm_enabled": True,
            "victory_bgm": "victory.ogg",
            "battle_bgm_volume": 1.0,
        }
        audio.library = SimpleNamespace(
            root=Path("BGM"),
            choose=Mock(return_value=Path("BGM/Awakening/awake.ogg")),
            awakening_offset=Mock(return_value=0.0),
        )
        audio.pygame = SimpleNamespace(mixer=SimpleNamespace(music=SimpleNamespace(get_pos=Mock(return_value=1234))))
        audio.normal_battle_track = Path("BGM/Default/battle.ogg")
        audio.normal_battle_position_ms = None
        audio.awakening_active = False
        audio.crossfade_timer = None
        audio._play = Mock()
        audio.stop = Mock()
        audio.fadeout = Mock()
        return audio

    def test_disabled_awakening_events_do_not_change_audio(self):
        audio = self.make_audio(enabled=False)
        audio.on_event("AWAKENING_START")
        audio.on_event("AWAKENING_END")
        audio._play.assert_not_called()
        audio.stop.assert_not_called()

    def test_enabled_awakening_start_plays_selected_group(self):
        audio = self.make_audio()
        audio.on_event("AWAKENING_START")
        audio.library.choose.assert_called_once_with("Balanced Random", "Awakening")
        audio._play.assert_called_once_with(Path("BGM/Awakening/awake.ogg"), start_seconds=0.0)
        self.assertTrue(audio.awakening_active)
        self.assertEqual(audio.normal_battle_position_ms, 1234)

    def test_awakening_end_resumes_normal_battle_audio(self):
        audio = self.make_audio()
        audio.on_event("AWAKENING_START")
        audio.on_event("AWAKENING_END")
        self.assertEqual(audio._play.call_args_list[-1], call(Path("BGM/Default/battle.ogg"), start_seconds=1.234, fade_ms=0))
        audio.fadeout.assert_called_once_with(0)
        self.assertFalse(audio.awakening_active)

    def test_crossfade_uses_configured_duration_and_saved_position(self):
        audio = self.make_audio()
        audio.cfg["awakening_crossfade_ms"] = 250
        audio.normal_battle_position_ms = 5000
        audio.awakening_active = True
        timer = Mock()
        with patch("audio.threading.Timer", return_value=timer) as timer_class:
            audio.on_event("AWAKENING_END")
        audio.fadeout.assert_called_once_with(250)
        timer_class.assert_called_once_with(0.25, audio._resume_normal_battle, args=(Path("BGM/Default/battle.ogg"), 250))
        timer.start.assert_called_once_with()
        audio._resume_normal_battle(Path("BGM/Default/battle.ogg"), 250)
        audio._play.assert_called_once_with(Path("BGM/Default/battle.ogg"), start_seconds=5.0, fade_ms=250)

    def test_missing_saved_position_restarts_safely(self):
        audio = self.make_audio()
        audio.awakening_active = True
        audio.normal_battle_position_ms = None
        audio.on_event("AWAKENING_END")
        audio._play.assert_called_once_with(Path("BGM/Default/battle.ogg"), start_seconds=0.0, fade_ms=0)

    def test_result_cancels_pending_crossfade(self):
        audio = self.make_audio()
        timer = Mock()
        audio.crossfade_timer = timer
        audio.on_event("VICTORY")
        timer.cancel.assert_called_once_with()

    def test_configured_offset_is_used_for_awakening_and_preview(self):
        audio = self.make_audio()
        audio.library.awakening_offset.return_value = 12.5
        audio.on_event("AWAKENING_START")
        audio._play.assert_called_once_with(Path("BGM/Awakening/awake.ogg"), start_seconds=12.5)
        audio._play.reset_mock()
        audio.preview_awakening_track(Path("BGM/Awakening/awake.ogg"), 12.5)
        audio._play.assert_called_once_with(Path("BGM/Awakening/awake.ogg"), loops=0, start_seconds=12.5)

    def test_negative_preview_offset_is_clamped_to_zero(self):
        audio = self.make_audio()
        audio.preview_awakening_track(Path("BGM/Awakening/awake.ogg"), -3)
        audio._play.assert_called_once_with(Path("BGM/Awakening/awake.ogg"), loops=0, start_seconds=0.0)

    def test_result_during_awakening_clears_resume_and_result_wins(self):
        audio = self.make_audio()
        audio.awakening_active = True
        audio.on_event("VICTORY")
        self.assertFalse(audio.awakening_active)
        audio.stop.assert_not_called()
        audio.fadeout.assert_called_once_with(0)
        audio._play.assert_called_once_with(Path("BGM") / "victory.ogg", loops=0)

    def test_invalid_awakening_group_does_not_crash(self):
        audio = self.make_audio(group="missing")
        audio.library.choose.return_value = None
        audio.on_event("AWAKENING_START")
        audio._play.assert_not_called()
        self.assertFalse(audio.awakening_active)


class ResultBlackoutTests(unittest.TestCase):
    def make_state(self):
        self.events = []
        return BattleStateMachine(
            {
                "result_bgm_enabled": True,
                "result_blackout_confirm_frames": 2,
                "victory_threshold": 0.38,
                "defeat_threshold": 0.38,
                "result_confirm_frames": 1,
                "go_threshold": 0.42,
                "burst_hud_loss_confirm_frames": 2,
                "burst_gauge_delta_min": 0.04,
                "burst_gauge_decrease_confirm_frames": 3,
                "burst_gauge_recovery_confirm_frames": 3,
            },
            lambda timestamp, event: self.events.append(event),
        )

    def test_two_result_blackout_samples_stop_result_bgm_and_return_to_idle(self):
        state = self.make_state()
        state.state = state.BATTLE
        burst = SimpleNamespace(classification="normal", gauge_level=1.0)
        state.update(0.0, DetectorScores(victory=1.0), burst)
        for timestamp in (0.1, 0.2):
            state.update(timestamp, DetectorScores(blackout=True), burst)
        self.assertEqual(state.state, state.IDLE)
        self.assertEqual(self.events, ["VICTORY", "RESULT_END"])

    def test_blackout_outside_result_does_nothing(self):
        state = self.make_state()
        burst = SimpleNamespace(classification="normal", gauge_level=1.0)
        for timestamp in (0.0, 0.1, 0.2):
            state.update(timestamp, DetectorScores(blackout=True), burst)
        self.assertEqual(state.state, state.IDLE)
        self.assertEqual(self.events, [])


class GuiStopTests(unittest.TestCase):
    def test_stop_fades_active_audio_before_stopping_capture(self):
        app = App.__new__(App)
        app.audio = SimpleNamespace(fadeout=Mock())
        app.stop_event = Mock()
        app.set_runtime_status = Mock()
        app.pause_requested = True
        app.resume_pending = True

        app.stop()

        app.audio.fadeout.assert_called_once_with()
        app.stop_event.set.assert_called_once_with()
        app.set_runtime_status.assert_called_once_with("STOPPED")
        self.assertFalse(app.pause_requested)
        self.assertFalse(app.resume_pending)
