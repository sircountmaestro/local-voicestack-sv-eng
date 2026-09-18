from __future__ import annotations

import os
import subprocess
from pathlib import Path

LIST_KEY = "org.gnome.settings-daemon.plugins.media-keys"
ITEM_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"

SHORTCUTS = (
    ("<Primary><Alt>a", "STT svenska", "stt-tap"),
    ("<Primary><Alt>w", "TTS engelska", "tts-en"),
    ("<Primary><Alt>e", "TTS svenska", "tts-sv"),
)


def install() -> None:
    bin_dir = Path.home() / ".local/bin"
    listed = _gsettings_get(LIST_KEY, "custom-keybindings")
    paths = _parse_list(listed)
    for binding, name, cmd in SHORTCUTS:
        command = str(bin_dir / cmd)
        slot = _slot_for_name(name, paths) or _next_slot(paths)
        if slot not in paths:
            paths.append(slot)
        _gsettings_set(f"{ITEM_SCHEMA}:{slot}", "name", name)
        _gsettings_set(f"{ITEM_SCHEMA}:{slot}", "binding", binding)
        _gsettings_set(f"{ITEM_SCHEMA}:{slot}", "command", command)
    rendered = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
    _gsettings_set(LIST_KEY, "custom-keybindings", rendered)


def _parse_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw in ("", "@as []", "[]"):
        return []
    return [p.strip(" '\"") for p in raw.strip("[]").split(",") if p.strip()]


def _slot_for_name(name: str, paths: list[str]) -> str | None:
    for p in paths:
        got = _gsettings_get(f"{ITEM_SCHEMA}:{p}", "name").strip().strip("'\"")
        if got == name:
            return p
    return None


def _next_slot(paths: list[str]) -> str:
    used = set(paths)
    for i in range(0, 40):
        p = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom{i}/"
        if p not in used:
            return p
    raise RuntimeError("inga lediga GNOME custom-keybindings")


def _gsettings_get(schema: str, key: str) -> str:
    proc = subprocess.run(
        ["gsettings", "get", schema, key],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
    )
    return (proc.stdout or "").strip()


def _gsettings_set(schema: str, key: str, value: str) -> None:
    if not (value.startswith("[") or value.startswith("'") or value.startswith('"')):
        value = f"'{value}'"
    subprocess.run(["gsettings", "set", schema, key, value], check=False)
