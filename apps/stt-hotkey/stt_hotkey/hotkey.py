from __future__ import annotations

import os
import select
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

HOTKEY_LABEL = "Ctrl+Alt+A"


class HotkeyBackend:
    def run(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


def open_backend(on_press: Callable[[], None], on_release: Callable[[], None]) -> HotkeyBackend:
    if sys.platform == "win32":
        return WindowsHotkey(on_press, on_release)
    return LinuxFifoHotkey(on_press, on_release)


def tap_path() -> Path:
    from stt_hotkey.lifecycle import runtime_dir

    return runtime_dir() / "tap"


class LinuxFifoHotkey(HotkeyBackend):
    """GNOME-genväg skriver 'toggle' till en FIFO. Ingen X-grab."""

    def __init__(self, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._stop = threading.Event()
        self._down = False
        self._fd = -1
        self._last_toggle = 0.0

    def run(self) -> None:
        path = tap_path()
        if path.exists():
            path.unlink()
        os.mkfifo(path, 0o600)
        self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        poller = select.poll()
        poller.register(self._fd, select.POLLIN)
        buf = b""
        print(f"FIFO {path}", flush=True)
        try:
            while not self._stop.is_set():
                if not poller.poll(200):
                    continue
                chunk = os.read(self._fd, 4096)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip() == b"toggle":
                        self._toggle()
        finally:
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1
            if path.exists():
                path.unlink()

    def _toggle(self) -> None:
        now = time.monotonic()
        if now - self._last_toggle < 0.45:
            print("toggle: ignorerar repeat", flush=True)
            return
        self._last_toggle = now
        if not self._down:
            self._down = True
            print("toggle: starta inspelning", flush=True)
            self._on_press()
        else:
            self._down = False
            print("toggle: stoppa och transkribera", flush=True)
            self._on_release()

    def stop(self) -> None:
        self._stop.set()
        try:
            path = tap_path()
            fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
            os.write(fd, b"\n")
            os.close(fd)
        except OSError:
            pass


class WindowsHotkey(HotkeyBackend):
    def __init__(self, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._stop = threading.Event()
        self._hook = None
        self._thread_id = 0
        self._down = False
        self._combo_held = False

    def run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        WH_KEYBOARD_LL = 13
        WM_KEYDOWN = 0x0100
        WM_SYSKEYDOWN = 0x0104
        WM_QUIT = 0x0012
        VK_CONTROL = 0x11
        VK_MENU = 0x12
        VK_A = 0x41
        self._thread_id = kernel32.GetCurrentThreadId()

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )

        def _ctrl_alt() -> bool:
            return bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) and bool(
                user32.GetAsyncKeyState(VK_MENU) & 0x8000
            )

        def _proc(n_code, w_param, l_param):
            if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.vkCode == VK_A and _ctrl_alt():
                    if not self._combo_held:
                        self._combo_held = True
                        if not self._down:
                            self._down = True
                            self._on_press()
                        else:
                            self._down = False
                            self._on_release()
                    return 1
                self._combo_held = False
            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        callback = LowLevelKeyboardProc(_proc)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, None, 0)
        if not self._hook:
            raise RuntimeError("kunde inte installera tangent-hook")
        msg = wintypes.MSG()
        while not self._stop.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or msg.message == WM_QUIT:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        _ = callback

    def stop(self) -> None:
        self._stop.set()
        if sys.platform == "win32" and self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
