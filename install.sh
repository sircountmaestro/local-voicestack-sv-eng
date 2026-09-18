#!/usr/bin/env bash
# Installation på en ny Linux-dator. Ingen Azure-nyckel medföljer.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"

echo "== local-voicestack-sv-eng install $ROOT =="

need=()
for cmd in docker curl python3 ffmpeg; do
  command -v "$cmd" >/dev/null || need+=("$cmd")
done
if ((${#need[@]})); then
  echo "Saknas: ${need[*]}"
  echo "  Debian/Ubuntu/Zorin: sudo apt install docker.io docker-compose-v2 python3 python3-venv python3-pip ffmpeg curl xclip xdotool wl-clipboard wtype python3-gi gir1.2-gtk-3.0"
fi
command -v docker >/dev/null || echo "Docker krävs för Kokoro/Azure/Whisper." >&2

if [[ ! -f "$ROOT/apps/azure-speech-gateway/.env" ]]; then
  cp "$ROOT/apps/azure-speech-gateway/.env.example" "$ROOT/apps/azure-speech-gateway/.env"
  chmod 600 "$ROOT/apps/azure-speech-gateway/.env"
  echo "Skapade tom apps/azure-speech-gateway/.env (ingen nyckel i git)."
fi
if [[ ! -f "$ROOT/apps/whisper-stt-sv/.env" ]]; then
  cp "$ROOT/apps/whisper-stt-sv/.env.example" "$ROOT/apps/whisper-stt-sv/.env"
fi

chmod +x "$ROOT"/bin/* "$ROOT/apps/stt-hotkey/scripts/"stt-* || true

if "$ROOT/bin/detect-gpu.sh"; then
  rm -f "$ROOT/apps/kokoro-fastapi/.use-cpu"
  echo "Kokoro: GPU-image (v0.9.0-cu128)."
else
  touch "$ROOT/apps/kokoro-fastapi/.use-cpu"
  echo "Kokoro: CPU-image (v0.9.0)."
fi

STT="$ROOT/apps/stt-hotkey"
if [[ ! -x "$STT/.venv/bin/python" ]]; then
  if command -v uv >/dev/null; then
    uv venv --python 3.12 "$STT/.venv"
    uv pip install --python "$STT/.venv/bin/python" -r "$STT/requirements.txt"
  else
    python3 -m venv "$STT/.venv"
    "$STT/.venv/bin/python" -m pip install -U pip
    "$STT/.venv/bin/python" -m pip install -r "$STT/requirements.txt"
  fi
fi

for name in tts ttsoff tts-sel tts-en tts-sv; do
  ln -sfn "$ROOT/bin/$name" "$BIN/$name"
done
ln -sfn "$STT/scripts/stt-ensure" "$BIN/stt-ensure"
ln -sfn "$STT/scripts/stt-stop" "$BIN/stt-stop"
ln -sfn "$STT/scripts/stt-tap" "$BIN/stt-tap"

_ensure_path_line() {
  local file="$1"
  local line='export PATH="$HOME/.local/bin:$PATH"'
  [[ -f "$file" ]] || return 0
  grep -qF '.local/bin' "$file" 2>/dev/null && return 0
  printf '\n# local-voicestack-sv-eng\n%s\n' "$line" >>"$file"
  echo "Lade PATH i $file"
}
_ensure_path_line "$HOME/.profile"
_ensure_path_line "$HOME/.bashrc"
_ensure_path_line "$HOME/.zshrc"
export PATH="$BIN:$PATH"

if [[ -x "$STT/.venv/bin/python" ]]; then
  set +e
  desktops="$(PYTHONPATH="$STT" "$STT/.venv/bin/python" -c 'from stt_hotkey.desktop_hotkeys import install; print(", ".join(install()) or "inga")')"
  set -e
  echo "Genvägar: ${desktops:-ok} (Ctrl+Alt+A/W/E)"
fi

if command -v systemctl >/dev/null && [[ "$(ps -p 1 -o comm= 2>/dev/null || true)" == systemd ]]; then
  unitdir="$HOME/.config/systemd/user"
  mkdir -p "$unitdir"
  cp "$ROOT/contrib/systemd/local-voicestack.service" "$unitdir/"
  systemctl --user daemon-reload 2>/dev/null || true
  systemctl --user enable local-voicestack.service 2>/dev/null \
    && echo "systemd --user: local-voicestack.service (startar vid inloggning)" \
    || true
fi

if command -v docker >/dev/null; then
  echo "Bygger Whisper-image (CPU, första modellnedladdning sker vid tts)…"
  docker compose -f "$ROOT/apps/whisper-stt-sv/compose.yml" build >/dev/null \
    && echo "Whisper-image: local-voicestack-whisper:1.0.0" \
    || echo "Kunde inte bygga Whisper nu. tts bygger den senare."
fi

echo
echo "Klart. Ny terminal, eller: export PATH=\"$BIN:\$PATH\""
echo "Svensk TTS: egen nyckel i apps/azure-speech-gateway/.env  (README)"
echo "Starta: tts     Stoppa: ttsoff"
echo "Brave unpacked: $ROOT/apps/kokoro-fastapi/brave-extension"
