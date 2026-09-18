from __future__ import annotations

import sys
from urllib.request import urlopen

from stt_hotkey import config, lifecycle
from stt_hotkey.audio import wav_bytes
from stt_hotkey.transcribe import is_usable_transcript


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    action = args[0] if args else "ensure"
    if action == "ensure":
        return lifecycle.ensure()
    if action == "run":
        from stt_hotkey.app import run

        return run()
    if action == "stop":
        return lifecycle.stop()
    if action == "status":
        return lifecycle.status()
    if action == "selftest":
        return selftest()
    print("användning: python -m stt_hotkey [ensure|run|stop|status|selftest]", file=sys.stderr)
    return 2


def selftest() -> int:
    wav = wav_bytes(b"\x00\x00" * 1600)
    assert wav[:4] == b"RIFF", "wav-header"
    assert is_usable_transcript("hej du")
    assert not is_usable_transcript("musik")
    print("kärna: ok")

    if sys.platform != "win32":
        try:
            from Xlib import display

            dpy = display.Display(config.DISPLAY)
            dpy.close()
            print(f"X11 {config.DISPLAY}: ok")
        except Exception as exc:
            print(f"X11: FEL {exc}")
            return 1
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            print(f"ljudenheter: {len(devices)}")
        except Exception as exc:
            print(f"sounddevice: {exc}")

    for label, url in (("whisper", config.WHISPER_URL), ("azure", config.AZURE_URL)):
        try:
            with urlopen(f"{url.rstrip('/')}/health", timeout=2) as resp:
                print(f"{label} {url}: HTTP {resp.status}")
        except Exception as exc:
            print(f"{label} {url}: nere ({exc.__class__.__name__})")
    print("selftest klar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
