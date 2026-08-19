"""Minimal native Windows global-hotkey listener."""
import ctypes
import ctypes.wintypes
import threading


WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_CONTROL = 0x0002
VK_F8 = 0x77


class GlobalPauseHotkey:
    def __init__(self, callback):
        self.callback = callback
        self.thread = None
        self.thread_id = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)

    def _run(self):
        user32 = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL, VK_F8):
            print("Global hotkey unavailable: Ctrl+F8 could not be registered")
            return
        try:
            message = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == WM_HOTKEY:
                    self.callback()
        finally:
            user32.UnregisterHotKey(None, 1)
            self.thread_id = None
