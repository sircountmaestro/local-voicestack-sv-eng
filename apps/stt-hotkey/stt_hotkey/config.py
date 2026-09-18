from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or not value.strip() else value.strip()


APP_NAME = "stt-hotkey"
LANGUAGE = _env("STT_LANGUAGE", "sv")
SAMPLE_RATE = int(_env("STT_SAMPLE_RATE", "16000"))
CHANNELS = 1
MIN_SECONDS = float(_env("STT_MIN_SECONDS", "0.28"))
MAX_SECONDS = float(_env("STT_MAX_SECONDS", "60"))
WHISPER_URL = _env("STT_WHISPER_URL", "http://127.0.0.1:9000")
AZURE_URL = _env("STT_AZURE_URL", "http://127.0.0.1:5050")


def _default_whisper_compose() -> Path:
    override = os.environ.get("STT_WHISPER_COMPOSE")
    if override and override.strip():
        return Path(override.strip())
    root = os.environ.get("TTSPRO_ROOT")
    if root and root.strip():
        return Path(root.strip()) / "apps/whisper-stt-sv/compose.yml"
    # config.py → stt_hotkey → stt-hotkey → apps
    apps = Path(__file__).resolve().parents[2]
    return apps / "whisper-stt-sv" / "compose.yml"


WHISPER_COMPOSE = _default_whisper_compose()
TRANSCRIBE_TIMEOUT = int(_env("STT_TRANSCRIBE_TIMEOUT", "90"))
DISPLAY = _env("DISPLAY", ":0")
