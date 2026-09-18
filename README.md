# Lokal röststack

Engelska och svenska uppläsning plus svensk diktering. Ett kommando: `tts`.

GitHub-reponamn: **`lokal-roststack`**. Ingen API-nyckel medföljer. Svensk uppläsning kräver att **du** skaffar en Azure Speech-nyckel (gratisnivå finns). Engelska och diktering fungerar utan Azure.

```bash
git clone https://github.com/<användare>/lokal-roststack.git
cd lokal-roststack
./install.sh          # Linux
# .\install.ps1       # Windows PowerShell
```

**Innehåll:** [Kartläggning](#kartläggning) · [Summering](#summering) · [Azure-nyckel](#azure-nyckel-svensk-tts) · [Linux](#installation-linux) · [Windows](#installation-windows) · [Användning](#användning) · [Felsökning](#felsökning)

---

## Kartläggning

| Del | Sökväg i repot | Roll |
|---|---|---|
| Start/stopp | `bin/tts`, `bin/ttsoff` | Hela stacken |
| Markerad text → tal | `bin/tts-sel`, `tts-en`, `tts-sv` | Ctrl+Alt+W engelska, Ctrl+Alt+E svenska |
| Kokoro EN | `apps/kokoro-fastapi/` | Lokal TTS, `127.0.0.1:8880` |
| Azure SV | `apps/azure-speech-gateway/` | Proxy till Azure Speech, `127.0.0.1:5050` |
| Whisper SV | `apps/whisper-stt-sv/` | Lokal STT på CPU, `127.0.0.1:9000` |
| Diktering | `apps/stt-hotkey/` | Ctrl+Alt+A: spela in → transkribera → klistra in |
| Brave | `apps/kokoro-fastapi/brave-extension/` | Högerklick, Kokoro EN eller Azure SV |

```
tts
 ├─ Kokoro (GPU om NVIDIA finns, annars CPU)  → :8880
 ├─ Azure-gateway om AZURE_SPEECH_KEY är satt → :5050
 └─ Whisper + STT-lyssnare                    → :9000 + Ctrl+Alt+A
```

`install.sh` / `install.ps1` lägger `tts` på `~/.local/bin` och ser till att katalogen finns i PATH.

---

## Summering

Engelska läses upp lokalt (Kokoro). Svenska läses upp via Azure om du lagt in en nyckel. Svenskt tal blir text med Whisper på CPU. I webbläsaren: unpacked Brave-tillägg. Data lämnar datorn bara när svensk Azure-TTS används.

---

## Azure-nyckel (svensk TTS)

Utan nyckel fungerar Kokoro (engelska) och Whisper-diktering. Svensk uppläsning och Brave «Azure SV» kräver nyckel.

1. Skapa ett Microsoft-konto och ett [Azure-abonnemang](https://azure.microsoft.com/free/) om du inte har ett. Det finns **gratisnivå**.
2. Öppna [Azure-portalen](https://portal.azure.com).
3. **Skapa en resurs** → sök **Speech** (Azure AI Speech / Cognitive Services Speech).
4. Fyll i:
   - **Region:** t.ex. `Sweden Central` (i `.env` skrivs `swedencentral`)
   - **Prisnivå:** **Free F0** räcker för att prova (begränsad trafik). **Standard S0** för mer användning.
5. Skapa resursen. Öppna den → **Keys and Endpoint** (Nycklar och slutpunkt).
6. Kopiera **KEY 1** och notera **Location/Region**.
7. I repon, filen `apps/azure-speech-gateway/.env` (skapas tom av install):

```
AZURE_SPEECH_KEY=klistra-in-nyckeln-här
AZURE_SPEECH_REGION=swedencentral
AZURE_SPEECH_VOICE=sv-SE-HilleviNeural
```

8. Spara. Kör `tts` igen (eller `docker compose -f apps/azure-speech-gateway/compose.yml up -d`).

Nyckeln ska **aldrig** checkas in i git. Dela den inte. Rotera den i portalen om den läckt.

Officiellt: [Get started with text to speech](https://learn.microsoft.com/azure/ai-services/speech-service/get-started-text-to-speech).

---

## Installation Linux

Förutsättningar: Docker (med Compose), Python 3.12, git, ffmpeg, curl. För diktering: xclip, xdotool. För GPU-Kokoro: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

Debian/Ubuntu/Zorin:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2 python3 python3-venv python3-pip \
  ffmpeg curl xclip xdotool python3-gi gir1.2-gtk-3.0
sudo usermod -aG docker "$USER"
# logga ut och in igen så docker-gruppen gäller
```

```bash
git clone https://github.com/<användare>/lokal-roststack.git
cd lokal-roststack
./install.sh
```

Installationen:

- skapar **tom** `apps/azure-speech-gateway/.env` (ingen nyckel från någon annan dator)
- bygger Python-venv för STT
- symlinkar `tts`, `ttsoff`, `tts-en`, `tts-sv` till `~/.local/bin`
- lägger `~/.local/bin` i `~/.profile`, `~/.bashrc` och `~/.zshrc` om det saknas
- väljer Kokoro **GPU** om Docker ser NVIDIA, annars **CPU**
- på GNOME: Ctrl+Alt+A (diktera), Ctrl+Alt+W (läs engelska), Ctrl+Alt+E (läs svenska)

Öppna **ny terminal**, fyll ev. Azure-nyckel, sedan:

```bash
tts
curl -sS http://127.0.0.1:8880/health
ttsoff
```

---

## Installation Windows

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) — starta det efter install.
2. [Python 3.12+](https://www.python.org/downloads/) — bocka i **Add python.exe to PATH**.
3. [Git for Windows](https://git-scm.com/download/win) — ger **Git Bash**.
4. [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) — packa upp och lägg `bin` på PATH.
5. Valfritt: NVIDIA-drivrutin om du vill ha Kokoro på GPU. Annars används CPU-imagen.

PowerShell:

```powershell
git clone https://github.com/<användare>/lokal-roststack.git
cd lokal-roststack
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\install.ps1
```

Eller dubbelklicka `install.bat`.

Sedan:

- **Git Bash:** `tts` / `ttsoff` (samma skript som Linux).
- **PowerShell:** `tts.ps1` / `ttsoff.ps1`.
- Öppna ny terminal så PATH gäller.
- Svensk TTS: redigera `apps\azure-speech-gateway\.env` enligt avsnittet Azure-nyckel.

Ctrl+Alt+A på Windows går via Python-hook (inte GNOME). Testa efter `tts`.

---

## Användning

1. `tts` — vänta på Kokoro. Azure startas bara om nyckeln är ifylld. Whisper laddar i bakgrunden första gången.
2. Markera text → **Ctrl+Alt+W** (engelska) eller **Ctrl+Alt+E** (svenska, kräver Azure).
3. Diktera: klicka i en textruta → **Ctrl+Alt+A** → prata → **Ctrl+Alt+A** igen. Texten klistras in.
4. Web-UI (bara Kokoro): http://127.0.0.1:8880/web
5. `ttsoff` när du är klar. Efter omstart: `tts` igen.

### Brave-extension

`apps/kokoro-fastapi/brave-extension`

1. `tts` så API:erna är uppe.
2. `brave://extensions` → Developer mode → **Load unpacked** → den mappen.
3. Popup: **Kokoro EN** eller **Azure SV** (Azure kräver nyckel).
4. Markera text → högerklick, eller Alt+A för artikel.

### Felsökning

| Symptom | Åtgärd |
|---|---|
| `tts` hittas inte | Ny terminal, eller `export PATH="$HOME/.local/bin:$PATH"`. Körde du `./install.sh`? |
| Kokoro :8880 död | `docker compose logs` i `apps/kokoro-fastapi`. Utan GPU ska `.use-cpu` finnas (install skapar den). |
| Svensk TTS tyst | Tom nyckel? Fyll `.env` och starta om `tts`. Fel region? Måste matcha resursen i portalen. |
| Ctrl+Alt+A tyst | `tts` måste ha körts. Linux: GNOME-genväg. `stt-ensure`. |
| `permission denied` Docker | Användaren i gruppen `docker`, ny inloggning. |
| Windows | Docker Desktop igång. Git Bash för `tts`. |

---

## Utförande från tom dator

### Linux

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2 python3 python3-venv python3-pip \
  ffmpeg curl xclip xdotool python3-gi gir1.2-gtk-3.0
sudo usermod -aG docker "$USER"
# ny inloggning
git clone https://github.com/<användare>/lokal-roststack.git && cd lokal-roststack
./install.sh
# valfritt svensk TTS:
nano apps/azure-speech-gateway/.env   # AZURE_SPEECH_KEY och AZURE_SPEECH_REGION
# ny terminal
tts
curl -sS http://127.0.0.1:8880/health
curl -sS http://127.0.0.1:5050/health   # bara om nyckel finns
ttsoff
```

Brave: Load unpacked `lokal-roststack/apps/kokoro-fastapi/brave-extension`.

### Windows

```text
1. Docker Desktop, Python 3.12 (Add to PATH), Git for Windows, FFmpeg på PATH
2. PowerShell:
   git clone https://github.com/<användare>/lokal-roststack.git
   cd lokal-roststack
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   .\install.ps1
3. Valfritt: notepad apps\azure-speech-gateway\.env  (egen KEY + REGION)
4. Git Bash:  tts
   PowerShell: tts.ps1
5. Brave Load unpacked: apps\kokoro-fastapi\brave-extension
```

### Images

```bash
docker compose -f apps/azure-speech-gateway/compose.yml up -d --build
docker compose -f apps/whisper-stt-sv/compose.yml up -d --build
# Kokoro: färdig image. GPU: compose.yml (cu128). CPU: compose.cpu.yml (v0.9.0).
```

---

Licens: [MIT](LICENSE). Kokoro-imagen och KBLab Whisper har egna licenser. Azure Speech är en molntjänst med egen nyckel.
