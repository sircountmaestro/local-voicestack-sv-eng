from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from stt_hotkey import config

MARKER = "stt_hotkey"


def runtime_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("TEMP") or os.environ.get("LOCALAPPDATA") or ".")
        path = base / config.APP_NAME
    else:
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        base = Path(xdg) if xdg else Path(f"/tmp/{config.APP_NAME}-{os.getuid()}")
        path = base / config.APP_NAME if xdg else base
    path.mkdir(parents=True, exist_ok=True)
    return path


def pid_path() -> Path:
    return runtime_dir() / "stt-hotkey.pid"


def log_path() -> Path:
    return runtime_dir() / "stt-hotkey.log"


def running_pid() -> int | None:
    path = pid_path()
    try:
        pid = int(path.read_text().strip())
    except (OSError, ValueError):
        return None
    if not _pid_alive(pid):
        path.unlink(missing_ok=True)
        return None
    return pid


def ensure() -> int:
    lock_f = (runtime_dir() / "stt-hotkey.lock").open("a+")
    try:
        _lock_file(lock_f)
        existing = running_pid()
        if existing is not None:
            print(f"STT Ctrl+Alt+A redan igång (pid {existing})")
            return 0
        try:
            from stt_hotkey.gnome_hotkey import install as install_gnome_hotkey

            install_gnome_hotkey()
        except Exception:
            pass
        return _spawn_listener()
    finally:
        lock_f.close()


def _spawn_listener() -> int:
    _ensure_whisper()
    log = log_path().open("ab", buffering=0)
    env = os.environ.copy()
    if sys.platform != "win32":
        env.setdefault("DISPLAY", config.DISPLAY)
        xauth = Path.home() / ".Xauthority"
        if xauth.is_file():
            env.setdefault("XAUTHORITY", str(xauth))
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "stt_hotkey", "run"],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
        start_new_session=True,
        creationflags=creationflags,
    )
    pid_path().write_text(str(proc.pid))
    time.sleep(0.4)
    if proc.poll() is not None:
        print(f"STT-lyssnaren dog direkt. Se {log_path()}", file=sys.stderr)
        pid_path().unlink(missing_ok=True)
        return 1
    print(f"STT Ctrl+Alt+A startad (pid {proc.pid})")
    return 0


def stop() -> int:
    pid = running_pid()
    if pid is None:
        print("STT Ctrl+Alt+A körs inte")
        return 0
    _kill(pid)
    for _ in range(20):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    else:
        _kill(pid, force=True)
    pid_path().unlink(missing_ok=True)
    print(f"STT Ctrl+Alt+A stoppad (pid {pid})")
    return 0


def status() -> int:
    pid = running_pid()
    if pid is None:
        print("STT Ctrl+Alt+A: av")
        return 1
    print(f"STT Ctrl+Alt+A: på (pid {pid})")
    return 0


def write_pid() -> None:
    pid_path().write_text(str(os.getpid()))


def _ensure_whisper() -> None:
    compose = config.WHISPER_COMPOSE
    if not compose.is_file():
        return
    if not shutil_which_docker():
        return
    subprocess.run(
        ["docker", "compose", "-f", str(compose), "up", "-d"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _lock_file(handle) -> None:
    if sys.platform == "win32":
        handle.seek(0)
        handle.write("lock")
        handle.flush()
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def shutil_which_docker() -> bool:
    from shutil import which

    return which("docker") is not None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    cmd_path = Path(f"/proc/{pid}/cmdline")
    try:
        cmd = cmd_path.read_bytes()
    except OSError:
        return True
    return MARKER.encode() in cmd


def _pid_alive_windows(pid: int) -> bool:
    import ctypes

    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def _kill(pid: int, force: bool = False) -> None:
    if sys.platform == "win32":
        import ctypes

        access = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(access, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 1)
            ctypes.windll.kernel32.CloseHandle(handle)
        return
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
    except OSError:
        pass
