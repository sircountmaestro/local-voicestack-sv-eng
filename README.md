# Local voicestack (sv/eng)

Engelska och svenska uppläsning plus svensk diktering. Ett kommando: `tts`.

```bash
git clone https://github.com/sircountmaestro/local-voicestack-sv-eng.git
cd local-voicestack-sv-eng
./install.sh          # Linux
# dubbelklicka tts.cmd  eller  .\install.ps1   # Windows
```

Ingen Azure-nyckel medföljer. Engelska (Kokoro) och diktering (Whisper) fungerar utan moln. Svensk uppläsning kräver en egen Speech-nyckel.

**Innehåll:** [Vad det är](#vad-det-är) · [Azure-nyckel](#azure-nyckel-svensk-tts) · [Linux](#installation-linux) · [Windows](#installation-windows) · [Användning](#användning) · [Felsökning](#felsökning)

---

## Vad det är

| Del | Sökväg | Roll |
|---|---|---|
| `tts` / `ttsoff` | `bin/` | Startar och stoppar stacken |
| Markerad text | `bin/tts-sel` | Ctrl+Alt+W engelska, Ctrl+Alt+E svenska |
| Kokoro | `apps/kokoro-fastapi/` | Lokal engelsk TTS på `127.0.0.1:8880` |
| Azure-gateway | `apps/azure-speech-gateway/` | Svensk TTS på `127.0.0.1:5050` (loopback) |
| Whisper | `apps/whisper-stt-sv/` | Svensk STT på CPU, `127.0.0.1:9000` |
| Diktering | `apps/stt-hotkey/` | Ctrl+Alt+A spela in → klistra in |
| Brave | `apps/kokoro-fastapi/brave-extension/` | Högerklick, EN eller SV |

Python-beroenden för diktering: `apps/stt-hotkey/requirements.txt`. Azure och Whisper installeras via Docker (egna `Dockerfile`).

Containrar publiceras bara på `127.0.0.1`. `restart: unless-stopped` så Docker tar upp dem efter reboot. Linux-install kan slå på systemd-användartjänsten `local-voicestack.service` vid inloggning.

---

## Azure-nyckel (svensk TTS)

1. [Azure-konto](https://azure.microsoft.com/free/) (gratisnivå finns).
2. [Azure-portalen](https://portal.azure.com) → **Skapa en resurs** → **Speech**.
3. Region t.ex. Sweden Central (`swedencentral`). Pris **Free F0** för att prova, **S0** för mer trafik.
4. Resursen → **Keys and Endpoint** → kopiera **KEY 1**.
5. I `apps/azure-speech-gateway/.env` (skapas tom av install):

```
AZURE_SPEECH_KEY=din-nyckel
AZURE_SPEECH_REGION=swedencentral
AZURE_SPEECH_VOICE=sv-SE-HilleviNeural
```

Checka aldrig in `.env`. Officiellt: [Text to speech](https://learn.microsoft.com/azure/ai-services/speech-service/get-started-text-to-speech).

---

## Installation Linux

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2 python3 python3-venv python3-pip \
  ffmpeg curl xclip xdotool wl-clipboard wtype python3-gi gir1.2-gtk-3.0
sudo usermod -aG docker "$USER"
# ny inloggning
git clone https://github.com/sircountmaestro/local-voicestack-sv-eng.git
cd local-voicestack-sv-eng
./install.sh
```

Installationen lägger `tts` på `~/.local/bin` och i PATH, väljer Kokoro GPU om `nvidia-smi` + Docker `--gpus` fungerar (annars CPU), sätter genvägar på GNOME, KDE, Hyprland och Sway när de finns, och slår på användar-systemd.

Wayland: `wl-clipboard` + `wtype` (eller `ydotool`). X11: `xclip` + `xdotool`.

---

## Installation Windows

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/), [Python 3.12+](https://www.python.org/downloads/) (Add to PATH), [Git](https://git-scm.com/download/win), [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) på PATH.
2. PowerShell:

```powershell
git clone https://github.com/sircountmaestro/local-voicestack-sv-eng.git
cd local-voicestack-sv-eng
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\install.ps1
```

3. **Starta:** dubbelklicka `tts.cmd` eller skrivbordslänken *Starta röststack*. Stoppa med `ttsoff.cmd`.
4. Git Bash `tts` finns kvar om du vill ha samma skript som Linux.

---

## Användning

1. `tts` (eller `tts.cmd`). Första Whisper-starten laddar modell till `~/.cache/huggingface` och kan ta ett par minuter.
2. Markera text → **Ctrl+Alt+W** (EN) eller **Ctrl+Alt+E** (SV, Azure).
3. Diktera: klicka i en ruta → **Ctrl+Alt+A** → prata → **Ctrl+Alt+A** igen.
4. Kokoro-UI: http://127.0.0.1:8880/web
5. `ttsoff` / `ttsoff.cmd`

Brave: `brave://extensions` → Load unpacked → `apps/kokoro-fastapi/brave-extension`.

---

## Felsökning

| Symptom | Åtgärd |
|---|---|
| `tts` hittas inte | Ny terminal, eller `export PATH="$HOME/.local/bin:$PATH"` |
| Kokoro :8880 död | GPU-toolkit? Annars ska `.use-cpu` finnas. `docker compose logs` |
| Svensk TTS tyst | Fyll `.env`, region måste matcha portalen |
| Tom markering på Wayland | Installera `wl-clipboard`. Utan den krävs XWayland |
| Ctrl+Alt+A tyst | Kör `tts`. KDE/Hypr/Sway: logga ut/in efter install |
| Whisper trög första gången | CPU-modell + nedladdning. Vänta på health `:9000` |
| Windows | Docker Desktop igång. Använd `tts.cmd`, inte bara Git Bash |

Images: Kokoro `v0.9.0` / `v0.9.0-cu128`. Egna gatewayer `local-voicestack-azure:1.0.0` och `local-voicestack-whisper:1.0.0`.

---

Licens: [MIT](LICENSE).
