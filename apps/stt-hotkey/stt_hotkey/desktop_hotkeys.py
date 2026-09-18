from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from stt_hotkey.gnome_hotkey import install as install_gnome

BIN = Path.home() / ".local/bin"
DESKTOP_DIR = Path.home() / ".local/share/applications"
MARK_BEGIN = "# local-voicestack-sv-eng begin"
MARK_END = "# local-voicestack-sv-eng end"

SHORTCUTS = (
    ("stt-tap", "STT svenska", "<Primary><Alt>a", "CTRL ALT, A", "Ctrl+Alt+A"),
    ("tts-en", "TTS engelska", "<Primary><Alt>w", "CTRL ALT, W", "Ctrl+Alt+W"),
    ("tts-sv", "TTS svenska", "<Primary><Alt>e", "CTRL ALT, E", "Ctrl+Alt+E"),
)


def install() -> list[str]:
    done: list[str] = []
    _write_desktop_files()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "") + ";" + os.environ.get(
        "XDG_SESSION_DESKTOP", ""
    )
    desktop = desktop.lower()
    try:
        install_gnome()
        done.append("GNOME")
    except Exception:
        pass
    if "kde" in desktop or "plasma" in desktop:
        if _install_kde():
            done.append("KDE")
    if _install_hyprland():
        done.append("Hyprland")
    if _install_sway():
        done.append("Sway")
    return done


def _write_desktop_files() -> None:
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    for cmd, name, _g, _h, _k in SHORTCUTS:
        path = DESKTOP_DIR / f"local-voicestack-{cmd}.desktop"
        path.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    f"Name={name}",
                    f"Exec={BIN / cmd}",
                    "Terminal=false",
                    "Categories=Utility;Audio;",
                    "",
                ]
            )
        )


def _install_kde() -> bool:
    kwrite = _which("kwriteconfig6") or _which("kwriteconfig5")
    if not kwrite:
        return False
    for cmd, name, _g, _h, kde in SHORTCUTS:
        desktop = f"local-voicestack-{cmd}.desktop"
        group = f"services][{desktop}"
        subprocess.run(
            [kwrite, "--file", "kglobalshortcutsrc", "--group", group, "--key", "_launch", kde],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                kwrite,
                "--file",
                "kglobalshortcutsrc",
                "--group",
                group,
                "--key",
                "_k_friendly_name",
                name,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return True


def _install_hyprland() -> bool:
    conf = Path.home() / ".config/hypr/hyprland.conf"
    if not conf.is_file():
        return False
    lines = [
        MARK_BEGIN,
        *[
            f"bind = {hypr}, exec, {BIN / cmd}"
            for cmd, _n, _g, hypr, _k in SHORTCUTS
        ],
        MARK_END,
    ]
    _upsert_block(conf, "\n".join(lines) + "\n")
    return True


def _install_sway() -> bool:
    conf = Path.home() / ".config/sway/config"
    if not conf.is_file():
        return False
    lines = [
        MARK_BEGIN,
        f"bindsym Ctrl+Alt+a exec {BIN / 'stt-tap'}",
        f"bindsym Ctrl+Alt+w exec {BIN / 'tts-en'}",
        f"bindsym Ctrl+Alt+e exec {BIN / 'tts-sv'}",
        MARK_END,
    ]
    _upsert_block(conf, "\n".join(lines) + "\n")
    return True


def _upsert_block(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"\n?",
        re.S,
    )
    if pattern.search(text):
        text = pattern.sub(block, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n" + block
    path.write_text(text, encoding="utf-8")


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)
