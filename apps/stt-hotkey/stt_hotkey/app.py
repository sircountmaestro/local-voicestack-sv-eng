from __future__ import annotations

import signal
import sys
import threading
import time
import traceback

from stt_hotkey import config, lifecycle
from stt_hotkey.audio import Recorder
from stt_hotkey.inject import inject_text
from stt_hotkey.hotkey import HOTKEY_LABEL, HotkeyBackend, open_backend
from stt_hotkey.notify import notify
from stt_hotkey.transcribe import transcribe


def log(message: str) -> None:
    print(message, flush=True)


def run() -> int:
    lifecycle.write_pid()
    recorder = Recorder()
    backend_holder: dict[str, HotkeyBackend | None] = {"backend": None}
    state_lock = threading.Lock()
    recording = {"on": False, "t0": 0.0, "gen": 0}
    busy = threading.Lock()

    def press() -> None:
        with state_lock:
            if recording["on"]:
                return
            recording["on"] = True
            recording["t0"] = time.monotonic()
            recording["gen"] += 1
            gen = recording["gen"]
        try:
            recorder.start()
        except Exception as exc:
            with state_lock:
                recording["on"] = False
            log(f"inspelning fel: {exc}")
            notify("STT", f"Mikrofonfel: {exc}")
            return
        notify("STT", "Lyssnar… Tryck Ctrl+Alt+A igen när du är klar.", 4000)
        threading.Thread(target=_watchdog, args=(gen,), daemon=True).start()

    def release() -> None:
        with state_lock:
            if not recording["on"]:
                return
            recording["on"] = False
            started = recording["t0"]
        try:
            wav = recorder.stop()
        except Exception as exc:
            log(f"stopp fel: {exc}")
            notify("STT", f"Inspelningsfel: {exc}")
            return
        held = time.monotonic() - started
        if held < config.MIN_SECONDS:
            log(f"för kort ({held:.2f}s), hoppar över")
            return
        threading.Thread(target=_finish, args=(wav, held), daemon=True).start()

    def _watchdog(gen: int) -> None:
        deadline = time.monotonic() + config.MAX_SECONDS
        while time.monotonic() < deadline:
            time.sleep(0.2)
            with state_lock:
                if not recording["on"] or recording["gen"] != gen:
                    return
        log("maxlängd, stoppar")
        release()

    def _finish(wav: bytes, held: float) -> None:
        if not busy.acquire(blocking=False):
            notify("STT", "Väntar — en transkribering pågår redan")
            return
        try:
            notify("STT", "Transkriberar…", 2000)
            log(f"transkriberar {len(wav)} bytes, {held:.1f}s")
            text = transcribe(wav)
            if not text:
                log("ingen tal igenkänd")
                notify("STT", "Ingen tal igenkänd")
                return
            inject_text(text)
            preview = text if len(text) <= 80 else text[:77] + "…"
            notify("STT", preview, 4000)
            log(f"inmatad: {preview}")
        except Exception as exc:
            log(f"transkribering fel: {exc}")
            traceback.print_exc()
            notify("STT", f"Fel: {exc}")
        finally:
            busy.release()

    def shutdown(*_args) -> None:
        log("stänger")
        try:
            recorder.stop()
        except Exception:
            pass
        backend = backend_holder["backend"]
        if backend is not None:
            backend.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, shutdown)

    backend = open_backend(press, release)
    backend_holder["backend"] = backend
    log(
        f"lyssnar på {HOTKEY_LABEL} display={config.DISPLAY!r} "
        f"whisper={config.WHISPER_URL} azure={config.AZURE_URL}"
    )
    try:
        backend.run()
    except Exception as exc:
        log(f"hotkey fel: {exc}")
        traceback.print_exc()
        notify("STT", f"STT-lyssnare dog: {exc}")
        return 1
    finally:
        shutdown()
    return 0
