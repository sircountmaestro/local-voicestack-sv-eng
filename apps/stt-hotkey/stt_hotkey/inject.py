from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time


TERMINAL_HINTS = (
    "terminal",
    "kitty",
    "alacritty",
    "xterm",
    "tilix",
    "konsole",
    "ptyxis",
    "wezterm",
    "foot",
    "ghostty",
)


def inject_text(text: str) -> None:
    if not text:
        return
    if sys.platform == "win32":
        _inject_windows(text)
        return
    _inject_linux(text)


def _inject_linux(text: str) -> None:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    if wayland and shutil.which("wl-copy"):
        old = _wl_read()
        _wl_write(text)
        _paste_keys(wayland=True)
        if old is None:
            return

        def restore() -> None:
            time.sleep(0.45)
            _wl_write(old)

        threading.Thread(target=restore, daemon=True).start()
        return
    xclip = shutil.which("xclip")
    if not xclip:
        raise RuntimeError("xclip eller wl-clipboard krävs för att klistra in text")
    old = _xclip_read(xclip)
    _xclip_write(xclip, text)
    _paste_keys(wayland=False)
    if old is None:
        return

    def restore() -> None:
        time.sleep(0.45)
        _xclip_write(xclip, old)

    threading.Thread(target=restore, daemon=True).start()


def _paste_keys(*, wayland: bool) -> None:
    if wayland:
        wtype = shutil.which("wtype")
        if wtype:
            subprocess.run(
                [wtype, "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                check=False,
                timeout=3,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        ydotool = shutil.which("ydotool")
        if ydotool:
            subprocess.run(
                [ydotool, "key", "29:1", "47:1", "47:0", "29:0"],
                check=False,
                timeout=3,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    xdotool = shutil.which("xdotool")
    if not xdotool:
        raise RuntimeError("xdotool, wtype eller ydotool krävs för att klistra in")
    paste = ["ctrl+shift+v"] if _active_is_terminal(xdotool) else ["ctrl+v"]
    subprocess.run(
        [xdotool, "key", "--clearmodifiers", *paste],
        check=False,
        timeout=3,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wl_write(text: str) -> None:
    subprocess.run(
        ["wl-copy"],
        input=text.encode("utf-8"),
        check=False,
        timeout=2,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wl_read() -> str | None:
    try:
        proc = subprocess.run(
            ["wl-paste", "-n"],
            check=False,
            timeout=1,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace")


def _active_is_terminal(xdotool: str) -> bool:
    try:
        wid = subprocess.check_output(
            [xdotool, "getactivewindow"], timeout=1, stderr=subprocess.DEVNULL
        ).decode().strip()
        cls = subprocess.check_output(
            ["xprop", "-id", wid, "WM_CLASS"],
            timeout=1,
            stderr=subprocess.DEVNULL,
        ).decode().lower()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return any(hint in cls for hint in TERMINAL_HINTS)


def _xclip_write(xclip: str, text: str) -> None:
    subprocess.run(
        [xclip, "-selection", "clipboard"],
        input=text.encode("utf-8"),
        check=False,
        timeout=2,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _xclip_read(xclip: str) -> str | None:
    try:
        proc = subprocess.run(
            [xclip, "-selection", "clipboard", "-o"],
            check=False,
            timeout=1,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace")


def _inject_windows(text: str) -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        raise RuntimeError("kunde inte öppna urklipp")
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        locked = kernel32.GlobalLock(handle)
        ctypes.memmove(locked, data, len(data))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
    finally:
        user32.CloseClipboard()

    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_V = 0x56
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    _ = wintypes
