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
_ttpro = _env("TTSPRO_ROOT", "")
_default_compose = (
    str(Path(_ttpro) / "apps/whisper-stt-sv/compose.yml")
    if _ttpro
    else str(Path.home() / "apps/whisper-stt-sv/compose.yml")
)
WHISPER_COMPOSE = Path(_env("STT_WHISPER_COMPOSE", _default_compose))
TRANSCRIBE_TIMEOUT = int(_env("STT_TRANSCRIBE_TIMEOUT", "90"))
DISPLAY = _env("DISPLAY", ":0")
