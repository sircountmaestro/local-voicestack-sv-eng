#!/usr/bin/env bash
# Installation på en ny Linux-dator. Ingen Azure-nyckel medföljer.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"

echo "== lokal-roststack install $ROOT =="

need=()
for cmd in docker curl python3 ffmpeg; do
  command -v "$cmd" >/dev/null || need+=("$cmd")
done
if ((${#need[@]})); then
  echo "Saknas: ${need[*]}"
  echo "  Debian/Ubuntu/Zorin: sudo apt install docker.io docker-compose-v2 python3 python3-venv python3-pip ffmpeg curl xclip xdotool python3-gi gir1.2-gtk-3.0"
  echo "  Fedora: sudo dnf install docker python3 ffmpeg curl xclip xdotool python3-gobject gtk3"
fi
command -v docker >/dev/null || echo "Docker krävs för Kokoro/Azure/Whisper." >&2

# Tom .env — användarens egen nyckel, skriv inte över ifylld fil
if [[ ! -f "$ROOT/apps/azure-speech-gateway/.env" ]]; then
  cp "$ROOT/apps/azure-speech-gateway/.env.example" "$ROOT/apps/azure-speech-gateway/.env"
  chmod 600 "$ROOT/apps/azure-speech-gateway/.env"
  echo "Skapade tom apps/azure-speech-gateway/.env (ingen nyckel i git)."
fi
if [[ ! -f "$ROOT/apps/whisper-stt-sv/.env" ]]; then
  cp "$ROOT/apps/whisper-stt-sv/.env.example" "$ROOT/apps/whisper-stt-sv/.env"
fi

# Kokoro: GPU om Docker ser NVIDIA, annars CPU-image
if docker info 2>/dev/null | grep -qi nvidia; then
  rm -f "$ROOT/apps/kokoro-fastapi/.use-cpu"
  echo "Kokoro: GPU-image (cu128)."
else
  touch "$ROOT/apps/kokoro-fastapi/.use-cpu"
  echo "Kokoro: CPU-image (ingen NVIDIA i Docker)."
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

chmod +x "$ROOT"/bin/* "$STT"/scripts/stt-ensure "$STT"/scripts/stt-stop "$STT"/scripts/stt-tap

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
  printf '\n# lokal-roststack\n%s\n' "$line" >>"$file"
  echo "Lade PATH i $file"
}

_ensure_path_line "$HOME/.profile"
_ensure_path_line "$HOME/.bashrc"
_ensure_path_line "$HOME/.zshrc"
export PATH="$BIN:$PATH"

if command -v gsettings >/dev/null; then
  PYTHONPATH="$STT" "$STT/.venv/bin/python" -c 'from stt_hotkey.gnome_hotkey import install; install()' 2>/dev/null \
    && echo "GNOME: Ctrl+Alt+A STT, Ctrl+Alt+W EN, Ctrl+Alt+E SV" \
    || true
fi

echo
echo "Klart. Öppna en ny terminal så att PATH gäller, eller: export PATH=\"$BIN:\$PATH\""
echo "Svensk TTS: sätt din egen nyckel i apps/azure-speech-gateway/.env  (se README.md)"
echo "Starta: tts"
echo "Brave unpacked: $ROOT/apps/kokoro-fastapi/brave-extension"
