import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

import main
from game_log_monitor import GameLogMonitor, events_for_line
from state_machine import BattleStateMachine


class GameLogMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.logs = Path(self.temp.name)
        self.events = []
        self.monitor = GameLogMonitor(self.logs, self.events.append, poll_interval=0.1)
        self.now = 0.0

    def tearDown(self):
        self.temp.cleanup()

    def poll(self):
        self.monitor.poll(self.now)
        self.now += 0.1

    def append(self, path, text):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)

    def test_attach_seeks_eof_and_switches_to_newest_log(self):
        first = self.logs / "Log_1.txt"
        first.write_text("FightingState: True\n", encoding="utf-8")
        self.poll()
        self.assertEqual(self.events, [])

        self.append(first, "Battle-9\n")
        self.poll()
        self.assertEqual(self.events, ["BATTLE_HINT"])

        second = self.logs / "Log_2.txt"
        second.write_text("ON BATTLE END PUSH\n", encoding="utf-8")
        self.poll()
        self.assertEqual(self.events, ["BATTLE_HINT"])

        self.append(second, "StateLobby\n")
        self.poll()
        self.assertEqual(self.events, ["BATTLE_HINT", "LOBBY"])

    def test_truncation_resets_offset_and_reads_new_content(self):
        log = self.logs / "Log_1.txt"
        log.write_text("old data that makes the initial offset longer\n", encoding="utf-8")
        self.poll()

        log.write_text("FightingState: True\n", encoding="utf-8")
        self.poll()
        self.assertEqual(self.events, ["BATTLE_HINT"])

    def test_detects_only_supported_signals(self):
        self.assertEqual(events_for_line("FightingState: True"), ["BATTLE_HINT"])
        self.assertEqual(events_for_line("Battle-9"), ["BATTLE_HINT"])
        self.assertEqual(events_for_line("ON BATTLE END PUSH"), ["BATTLE_END"])
        self.assertEqual(events_for_line("UpdateMatchDataInGamePush State:Matching"), ["MATCH_MATCHING"])
        self.assertEqual(events_for_line("UpdateMatchDataInGamePush State:Confirming"), ["MATCH_CONFIRMING"])
        self.assertEqual(events_for_line("UpdateMatchDataInGamePush State:Confirmed"), ["MATCH_CONFIRMED"])
        self.assertEqual(events_for_line("Load State StateLobby False"), ["LOBBY"])
        self.assertEqual(events_for_line("unrelated StateLobbyish message"), [])

    def test_debug_logs_each_supported_signal_with_a_timestamp(self):
        log = self.logs / "Log_1.txt"
        log.write_text("old\n", encoding="utf-8")
        monitor = GameLogMonitor(self.logs, self.events.append, debug=True)
        monitor.poll(0.0)
        self.append(
            log,
            "FightingState: True\nBattle-9\nON BATTLE END PUSH\nStateLobby\n",
        )
        with patch("game_log_monitor.time.perf_counter", return_value=12.345), \
             patch("builtins.print") as printed:
            monitor.poll(0.1)
        output = "\n".join(str(call.args[0]) for call in printed.call_args_list)
        for signal in ("FightingState: True", "Battle-9", "ON BATTLE END PUSH", "StateLobby"):
            self.assertIn(f"timestamp=12.345 signal={signal}", output)

    def test_log_events_use_existing_state_machine_flow(self):
        events = []
        state = BattleStateMachine({}, lambda _timestamp, event: events.append(event))

        state.handle_log_event(1.0, "BATTLE_START")
        state.handle_log_event(2.0, "BATTLE_END")
        self.assertEqual(state.state, state.BATTLE)
        self.assertEqual(events, ["BATTLE_START", "BATTLE_END"])

        state.handle_log_event(3.0, "LOBBY")
        self.assertEqual(state.state, state.IDLE)
        self.assertEqual(events, ["BATTLE_START", "BATTLE_END", "LOBBY"])

    def test_runtime_does_not_create_a_monitor_when_disabled(self):
        with patch("main.GameLogMonitor") as monitor_class:
            monitor = main.create_game_log_monitor(
                {"game_log_monitor_enabled": False}, object(),
            )
        self.assertIsNone(monitor)
        monitor_class.assert_not_called()

    def test_runtime_creates_a_monitor_when_enabled(self):
        state = type("State", (), {"handle_log_event": lambda *_: None})()
        with patch("main.GameLogMonitor") as monitor_class:
            main.create_game_log_monitor(
                {
                    "game_log_monitor_enabled": True,
                    "starward_logs_dir": str(self.logs),
                    "_debug": True,
                },
                state,
            )
        monitor_class.assert_called_once()
        self.assertTrue(monitor_class.call_args.kwargs["debug"])

    def test_runtime_does_not_create_a_monitor_for_an_empty_folder(self):
        with patch("main.GameLogMonitor") as monitor_class:
            monitor = main.create_game_log_monitor(
                {"game_log_monitor_enabled": True, "starward_logs_dir": ""}, object(),
            )
        self.assertIsNone(monitor)
        monitor_class.assert_not_called()

    def test_runtime_does_not_create_a_monitor_for_an_invalid_folder(self):
        missing = self.logs / "missing"
        with patch("main.GameLogMonitor") as monitor_class:
            monitor = main.create_game_log_monitor(
                {"game_log_monitor_enabled": True, "starward_logs_dir": str(missing)}, object(),
            )
        self.assertIsNone(monitor)
        monitor_class.assert_not_called()

    def test_old_config_defaults_lobby_and_match_to_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps({"ui_language": "ja", "battle_bgm_volume": 0.25}),
                encoding="utf-8",
            )
            with patch("main.ROOT", root):
                cfg = main.load_config()
        self.assertFalse(cfg.get("lobby_bgm_enabled", False))
        self.assertFalse(cfg.get("match_bgm_enabled", False))
        self.assertEqual(cfg["ui_language"], "ja")
        self.assertEqual(cfg["battle_bgm_volume"], 0.25)
