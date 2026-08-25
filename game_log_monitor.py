"""Tail the active Starward game log without replaying its old contents."""
from __future__ import annotations

import re
import time
from pathlib import Path


_SIGNALS = (
    (re.compile(r"FightingState:\s*True\b"), "FightingState: True", "BATTLE_HINT"),
    (re.compile(r"\bBattle-9\b"), "Battle-9", "BATTLE_HINT"),
    (re.compile(r"ON BATTLE END PUSH"), "ON BATTLE END PUSH", "BATTLE_END"),
    (re.compile(r"(?:Load State )?StateLobby(?:\s+False)?\b"), "StateLobby", "LOBBY"),
    (re.compile(r"UpdateMatchDataInGamePush State:Matching"), "State:Matching", "MATCH_MATCHING"),
    (re.compile(r"UpdateMatchDataInGamePush State:Confirming"), "State:Confirming", "MATCH_CONFIRMING"),
    (re.compile(r"UpdateMatchDataInGamePush State:Confirmed"), "State:Confirmed", "MATCH_CONFIRMED"),
)


def starward_logs_dir(cfg):
    """Return the explicitly configured Logs directory, if any."""
    configured = str(cfg.get("starward_logs_dir", "")).strip()
    return Path(configured) if configured else None


def events_for_line(line):
    """Return the supported state signal(s) present in one log line."""
    return [event for pattern, _signal, event in _SIGNALS if pattern.search(line)]


def _signals_for_line(line):
    return [
        (signal, event)
        for pattern, signal, event in _SIGNALS
        if pattern.search(line)
    ]


class GameLogMonitor:
    """Polling tail reader for the newest ``Log_*.txt`` file in a directory."""

    def __init__(self, logs_dir, on_event, poll_interval=0.1, debug=False):
        self.logs_dir = Path(logs_dir)
        self.on_event = on_event
        self.poll_interval = poll_interval
        self.debug = debug
        self.path = None
        self.offset = 0
        self._partial = b""
        self._next_poll_at = 0.0

    def _newest_log(self):
        try:
            files = list(self.logs_dir.glob("Log_*.txt"))
        except OSError:
            return None
        try:
            return max(files, key=lambda path: path.stat().st_mtime_ns, default=None)
        except OSError:
            return None

    def _attach(self, path):
        try:
            self.offset = path.stat().st_size
        except OSError:
            return
        self.path = path
        self._partial = b""

    def poll(self, now=None):
        """Read newly appended complete lines and deliver their recognized events."""
        now = time.monotonic() if now is None else now
        if now < self._next_poll_at:
            return
        self._next_poll_at = now + self.poll_interval

        newest = self._newest_log()
        if newest is None:
            return
        if newest != self.path:
            self._attach(newest)
            return

        try:
            size = newest.stat().st_size
            if size < self.offset:
                self.offset = 0
                self._partial = b""
            with newest.open("rb") as log_file:
                log_file.seek(self.offset)
                data = log_file.read()
                self.offset = log_file.tell()
        except OSError:
            return

        if not data:
            return
        lines = (self._partial + data).splitlines(keepends=True)
        self._partial = b""
        if lines and not lines[-1].endswith((b"\n", b"\r")):
            self._partial = lines.pop()
        for raw_line in lines:
            line = raw_line.decode("utf-8", errors="replace")
            for signal, event in _signals_for_line(line):
                if self.debug:
                    print(
                        "GAME_LOG detected "
                        f"timestamp={time.perf_counter():.3f} signal={signal} event={event}"
                    )
                self.on_event(event)
