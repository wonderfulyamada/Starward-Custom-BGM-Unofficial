
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import cv2

from audio import NullAudio, PygameAudio
from detector import ScreenDetector, TemplateBank
from gamepad_input import GamepadInputAssist
from game_log_monitor import GameLogMonitor, starward_logs_dir
from paths import ROOT
from state_machine import BattleStateMachine, DetectorScores


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def save_config(cfg):
    (ROOT / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def create_game_log_monitor(cfg, state):
    """Create the optional log input only when explicitly enabled."""
    if not cfg.get("game_log_monitor_enabled", False):
        return None
    logs_dir = starward_logs_dir(cfg)
    if logs_dir is None or not logs_dir.is_dir():
        if cfg.get("_debug", False):
            reason = "path_empty" if logs_dir is None else f"path_invalid path={logs_dir}"
            print(f"GAME_LOG monitor_not_started reason={reason}")
        return None
    return GameLogMonitor(
        logs_dir,
        lambda event: state.handle_log_event(time.perf_counter(), event),
        debug=cfg.get("_debug", False),
    )


def run_video(path, cfg, detector, state, show_debug, stop_event=None):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    scan_interval = 1.0 / cfg["scan_hz"]
    next_scan_time = 0.0
    frame_index = 0

    while not (stop_event and stop_event.is_set()):
        timestamp = frame_index / fps
        if timestamp + 1e-9 >= next_scan_time:
            ok, frame = cap.read()
            if not ok:
                break

            process_frame(frame, timestamp, cfg, detector, state, show_debug)
            next_scan_time += scan_interval

            if show_debug and cv2.waitKey(1) & 0xFF == 27:
                break
        else:
            # Skip expensive BGR conversion for frames we do not analyze.
            ok = cap.grab()
            if not ok:
                break

        frame_index += 1

    cap.release()
    cv2.destroyAllWindows()


def run_window(hwnd, cfg, detector, state, show_debug, stop_event=None):
    import ctypes
    import ctypes.wintypes
    import mss
    import numpy as np

    client_rect = ctypes.wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
        raise RuntimeError("Cannot get the selected window's client bounds")
    top_left = ctypes.wintypes.POINT(client_rect.left, client_rect.top)
    bottom_right = ctypes.wintypes.POINT(client_rect.right, client_rect.bottom)
    if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
        raise RuntimeError("Cannot convert the selected window's client origin")
    if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
        raise RuntimeError("Cannot convert the selected window's client bounds")
    region = {"left": top_left.x, "top": top_left.y,
              "width": bottom_right.x - top_left.x,
              "height": bottom_right.y - top_left.y}
    interval = 1.0 / cfg["scan_hz"]
    log_monitor = create_game_log_monitor(cfg, state)
    print(f"Window capture worker started: hwnd={hwnd}")
    try:
        with mss.mss() as sct:
            while not (stop_event and stop_event.is_set()):
                started = time.perf_counter()
                if log_monitor is not None:
                    log_monitor.poll()
                raw = sct.grab(region)
                if raw is None:
                    raise RuntimeError("Window capture returned no frame")
                frame = np.asarray(raw)[:, :, :3].copy()
                process_frame(frame, time.perf_counter(), cfg, detector, state, show_debug)
                delay = interval - (time.perf_counter() - started)
                if delay > 0:
                    time.sleep(delay)
    except Exception:
        print("Window capture worker error:")
        traceback.print_exc()
        raise
    cv2.destroyAllWindows()


def run_live(cfg, detector, state, show_debug):
    try:
        import mss
        import numpy as np
    except ImportError:
        raise RuntimeError("Live capture requires: pip install mss numpy")

    interval = 1.0 / cfg["scan_hz"]
    log_monitor = create_game_log_monitor(cfg, state)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            started = time.perf_counter()
            if log_monitor is not None:
                log_monitor.poll()
            raw = sct.grab(monitor)
            frame = np.asarray(raw)[:, :, :3].copy()
            timestamp = time.perf_counter()

            process_frame(frame, timestamp, cfg, detector, state, show_debug)

            if show_debug and cv2.waitKey(1) & 0xFF == 27:
                break

            delay = interval - (time.perf_counter() - started)
            if delay > 0:
                time.sleep(delay)

    cv2.destroyAllWindows()


def process_frame(frame, timestamp, cfg, detector, state, show_debug):
    burst = detector.burst_metrics(
        frame,
        calibrate=state.state in (state.BATTLE, state.READY, state.AWAKENING),
        mode=state.state.lower(),
    )
    previous_state = state.state

    # GO only matters outside the current match.
    if state.state in (state.IDLE, state.RESULT):
        go = detector.go_score(frame)
    else:
        go = 0.0

    # Result only matters during a match.
    if state.state in (state.BATTLE, state.READY, state.AWAKENING):
        victory = detector.victory_score(frame)
        defeat = detector.defeat_score(frame)
    else:
        victory = defeat = 0.0

    blackout_brightness = float(frame.mean()) if state.state == state.RESULT else None
    blackout = (
        blackout_brightness is not None
        and blackout_brightness <= cfg.get("result_blackout_luminance_max", 8)
    )
    scores = DetectorScores(
        go=go,
        victory=victory,
        defeat=defeat,
        blackout=blackout,
        blackout_brightness=blackout_brightness,
    )
    input_assist = getattr(state, "input_assist", None)
    input_active = input_assist.poll() if input_assist is not None else False
    input_recent = input_assist.recent if input_assist is not None else False
    consume_input = input_assist.consume_recent if input_assist is not None else None
    state.update(timestamp, scores, burst, input_active, input_recent, consume_input)
    if state.state == state.BATTLE and previous_state in (state.IDLE, state.RESULT):
        detector.reset_burst_calibration()

    if show_debug:
        debug = frame.copy()
        cv2.putText(
            debug,
            f"STATE: {state.state}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            debug,
            f"burst={burst.classification} gauge={burst.gauge_level} glow={burst.glow_classification}:{burst.glow_score}",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            debug,
            f"go={go:.3f} victory={victory:.3f} defeat={defeat:.3f}",
            (20, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        geometry = detector.burst_geometry
        if geometry is not None:
            cv2.circle(debug, geometry.center, int(round(geometry.radius)), (255, 255, 255), 2)

        cv2.imshow("Starward BGM detector - ESC to quit", debug)


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--video", help="Analyze a recorded match")
    source.add_argument("--live", action="store_true", help="Analyze the primary monitor live")
    parser.add_argument("--gui", action="store_true", help="Open the input-source GUI")
    parser.add_argument("--debug", action="store_true", help="Show detector overlay")
    parser.add_argument("--audio", action="store_true", help="Enable pygame audio backend")
    args = parser.parse_args()

    if args.gui:
        from gui import launch
        launch(debug=args.debug)
        return
    if not (args.video or args.live):
        parser.error("one of --video, --live, or --gui is required")

    cfg = load_config()
    cfg["_debug"] = args.debug
    templates = TemplateBank(ROOT / "templates")
    detector = ScreenDetector(cfg, templates)

    audio = PygameAudio(cfg) if args.audio else NullAudio()
    source_name = Path(args.video).name if args.video else "LIVE"
    state = None

    def on_event(timestamp, event):
        print(f"{source_name}  {timestamp:9.3f}  {event}  state={state.state}")
        audio.on_event(event)

    state = BattleStateMachine(cfg, on_event)
    state.input_assist = GamepadInputAssist(cfg)

    if args.video:
        run_video(args.video, cfg, detector, state, args.debug)
    else:
        run_live(cfg, detector, state, args.debug)


if __name__ == "__main__":
    main()
