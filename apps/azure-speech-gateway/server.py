#!/usr/bin/env python3
"""Loopback OpenAI-compatible proxy for Azure Speech REST (TTS + STT).

Apps call 127.0.0.1. This process forwards to Azure. Keys stay in env.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import xml.sax.saxutils
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

KEY = os.environ.get("AZURE_SPEECH_KEY", "").strip()
REGION = os.environ.get("AZURE_SPEECH_REGION", "swedencentral").strip()
TTS_ENDPOINT = (os.environ.get("AZURE_SPEECH_ENDPOINT") or "").strip() or (
    f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
)
STT_ENDPOINT = (os.environ.get("AZURE_SPEECH_STT_ENDPOINT") or "").strip()
STT_API_VERSION = os.environ.get("AZURE_SPEECH_STT_API_VERSION", "2024-11-15").strip()
DEFAULT_VOICE = os.environ.get("AZURE_SPEECH_VOICE", "sv-SE-HilleviNeural").strip()
DEFAULT_LANGUAGE = os.environ.get("AZURE_SPEECH_LANGUAGE", "sv-SE").strip()
AUDIO_FORMAT = os.environ.get(
    "AZURE_SPEECH_FORMAT",
    "audio-24khz-48kbitrate-mono-mp3",
).strip()
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "5050"))
TTS_MODEL = "azure-tts"
STT_MODEL = "azure-stt"
AZURE_WAV_TYPE = "audio/wav; codecs=audio/pcm; samplerate=16000"
AZURE_VOICES = (
    {"id": "sv-SE-HilleviNeural", "name": "Hillevi (sv female)"},
    {"id": "sv-SE-SofieNeural", "name": "Sofie (sv female)"},
    {"id": "sv-SE-MattiasNeural", "name": "Mattias (sv male)"},
)
VOICE_ALIASES = {
    "hillevi": "sv-SE-HilleviNeural",
    "sofie": "sv-SE-SofieNeural",
    "mattias": "sv-SE-MattiasNeural",
}


def resource_origin(endpoint: str) -> str | None:
    parsed = urlparse(endpoint)
    host = parsed.netloc.lower()
    if host.endswith(".cognitiveservices.azure.com") or host.endswith(
        ".api.cognitive.microsoft.com"
    ):
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def default_stt_url(language: str) -> str:
    if STT_ENDPOINT:
        base = STT_ENDPOINT
        sep = "&" if "?" in base else "?"
        if "language=" not in base:
            return f"{base}{sep}language={language}"
        return base
    origin = resource_origin(TTS_ENDPOINT)
    if origin:
        return (
            f"{origin}/speechtotext/transcriptions:transcribe"
            f"?api-version={STT_API_VERSION}"
        )
    tts_host = urlparse(TTS_ENDPOINT).netloc.lower()
    if ".tts.speech.microsoft.com" in tts_host:
        stt_host = tts_host.replace(".tts.", ".stt.", 1)
        return (
            f"https://{stt_host}/speech/recognition/conversation/"
            f"cognitiveservices/v1?language={language}"
        )
    return (
        f"https://{REGION}.stt.speech.microsoft.com/speech/recognition/"
        f"conversation/cognitiveservices/v1?language={language}"
    )


def stt_is_fast(url: str) -> bool:
    return "speechtotext/transcriptions:transcribe" in url


def voice_lang(voice: str) -> str:
    parts = voice.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return DEFAULT_LANGUAGE


def pick_voice(requested: str | None) -> str:
    voice = (requested or "").strip()
    first = voice.split("+")[0]
    first = re.sub(r"\([^)]*\)", "", first).strip()
    alias = VOICE_ALIASES.get(first.lower())
    if alias:
        return alias
    if first.endswith("Neural") or first.endswith("NeuralMultilingual"):
        return first
    if "MultilingualNeural" in first:
        return first
    return DEFAULT_VOICE


def ssml_for(text: str, voice: str) -> bytes:
    lang = voice_lang(voice)
    esc = xml.sax.saxutils.escape
    payload = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="{lang}">'
        f'<voice name="{esc(voice)}">{esc(text)}</voice>'
        f"</speak>"
    )
    return payload.encode("utf-8")


def azure_synth(text: str, voice: str) -> bytes:
    if not KEY:
        raise RuntimeError("AZURE_SPEECH_KEY missing")
    req = Request(
        TTS_ENDPOINT,
        data=ssml_for(text, voice),
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": AUDIO_FORMAT,
            "User-Agent": "kick-azure-speech-gateway",
        },
    )
    with urlopen(req, timeout=30) as resp:
        return resp.read()


def _multipart_body(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> tuple[bytes, str]:
    boundary = "----KickSpeechBoundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{file_field}"; '
        f'filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    chunks.append(header + data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def to_pcm16_wav(audio: bytes) -> bytes:
    """Classic Azure short-audio wants 16 kHz mono PCM WAV."""
    suffix = ".wav" if audio[:4] == b"RIFF" else ".bin"
    src_path = ""
    dst_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as src:
            src.write(audio)
            src_path = src.name
        dst_path = src_path + ".16k.wav"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                src_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                dst_path,
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip()[:200]
            raise RuntimeError(err or "ffmpeg failed")
        with open(dst_path, "rb") as handle:
            out = handle.read()
        if not out:
            raise RuntimeError("ffmpeg empty output")
        return out
    finally:
        for path in (src_path, dst_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def azure_transcribe(
    audio: bytes,
    language: str,
    filename: str,
    content_type: str,
) -> str:
    if not KEY:
        raise RuntimeError("AZURE_SPEECH_KEY missing")
    url = default_stt_url(language)
    if stt_is_fast(url):
        body, ctype = _multipart_body(
            {"definition": json.dumps({"locales": [language]})},
            "audio",
            filename or "audio.wav",
            content_type or "application/octet-stream",
            audio,
        )
        req = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Ocp-Apim-Subscription-Key": KEY,
                "Content-Type": ctype,
                "Accept": "application/json",
                "User-Agent": "kick-azure-speech-gateway",
            },
        )
        with urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
        phrases = payload.get("combinedPhrases") or []
        if phrases and isinstance(phrases[0], dict):
            return str(phrases[0].get("text") or "").strip()
        return str(payload.get("text") or "").strip()

    req = Request(
        url,
        data=audio,
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": KEY,
            "Content-Type": content_type or AZURE_WAV_TYPE,
            "Accept": "application/json",
            "User-Agent": "kick-azure-speech-gateway",
        },
    )
    with urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8") or "{}")
    return str(payload.get("DisplayText") or payload.get("text") or "").strip()


def parse_multipart(
    content_type: str, body: bytes
) -> tuple[dict[str, str], bytes, str, str]:
    match = re.search(r"boundary=([^;]+)", content_type, re.I)
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = match.group(1).strip().strip('"').encode("ascii", "replace")
    fields: dict[str, str] = {}
    file_bytes = b""
    file_ctype = "application/octet-stream"
    file_name = "audio.wav"
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        data = data.rstrip(b"\r\n")
        if data.endswith(b"--"):
            data = data[:-2]
        headers = header_blob.decode("utf-8", "replace")
        name_m = re.search(r'name="([^"]+)"', headers, re.I)
        if not name_m:
            continue
        name = name_m.group(1)
        fn_m = re.search(r'filename="([^"]*)"', headers, re.I)
        ctype_m = re.search(r"Content-Type:\s*([^\r\n]+)", headers, re.I)
        if fn_m is not None or name in {"file", "audio"}:
            file_bytes = data
            file_name = (fn_m.group(1) if fn_m else "") or file_name
            if ctype_m:
                file_ctype = ctype_m.group(1).strip()
        else:
            fields[name] = data.decode("utf-8", "replace")
    return fields, file_bytes, file_ctype, file_name


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: object) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def _cors_headers(self) -> None:
        origin = (self.headers.get("Origin") or "").strip()
        # Chromium rejects ACAO file://; Electron often sends that Origin.
        if (not origin) or origin == "null" or origin.startswith("file:"):
            allow_origin = "*"
        else:
            allow_origin = origin
        self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        requested = (self.headers.get("Access-Control-Request-Headers") or "").strip()
        self.send_header(
            "Access-Control-Allow-Headers",
            requested or "content-type,authorization",
        )
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/health", "/"):
            self._json(
                200,
                {
                    "ok": True,
                    "status": "healthy",
                    "models": [TTS_MODEL, STT_MODEL],
                    "voice": DEFAULT_VOICE,
                    "language": DEFAULT_LANGUAGE,
                    "region": REGION,
                },
            )
            return
        if path in ("/v1/audio/voices", "/audio/voices"):
            self._json(
                200,
                {"voices": list(AZURE_VOICES), "default_voice": DEFAULT_VOICE},
            )
            return
        if path in ("/v1/models", "/models"):
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": TTS_MODEL,
                            "object": "model",
                            "owned_by": "azure-speech",
                        },
                        {
                            "id": STT_MODEL,
                            "object": "model",
                            "owned_by": "azure-speech",
                        },
                    ],
                },
            )
            return
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b""
        if path in ("/v1/audio/speech", "/audio/speech"):
            self._handle_speech(raw)
            return
        if path in ("/v1/audio/transcriptions", "/audio/transcriptions"):
            self._handle_transcription(raw, parsed.query)
            return
        self._json(404, {"error": {"message": "not found"}})

    def _handle_speech(self, raw: bytes) -> None:
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": {"message": "invalid json"}})
            return
        text = str(payload.get("input") or payload.get("text") or "").strip()
        if not text:
            self._json(400, {"error": {"message": "input required"}})
            return
        voice = pick_voice(payload.get("voice"))
        try:
            audio = azure_synth(text, voice)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            self._json(
                exc.code, {"error": {"message": f"azure {exc.code}", "detail": detail}}
            )
            return
        except (URLError, RuntimeError, TimeoutError) as exc:
            self._json(502, {"error": {"message": str(exc)}})
            return
        self._send(200, audio, "audio/mpeg")

    def _handle_transcription(self, raw: bytes, query: str) -> None:
        ctype = self.headers.get("Content-Type") or ""
        qs = parse_qs(query)
        fields: dict[str, str] = {}
        audio = b""
        file_ctype = "application/octet-stream"
        filename = "audio.wav"
        if "multipart/form-data" in ctype.lower():
            try:
                fields, audio, file_ctype, filename = parse_multipart(ctype, raw)
            except ValueError as exc:
                self._json(400, {"error": {"message": str(exc)}})
                return
        else:
            audio = raw
            file_ctype = ctype.split(";")[0].strip() or file_ctype
        if not audio:
            self._json(400, {"error": {"message": "file required"}})
            return
        print(
            f"stt in bytes={len(audio)} magic={audio[:4]!r} "
            f"ctype={file_ctype!r} name={filename!r}"
        )
        try:
            audio = to_pcm16_wav(audio)
        except RuntimeError as exc:
            print(f"stt convert fail {exc}")
            self._json(400, {"error": {"message": f"audio convert: {exc}"}})
            return
        language = (
            fields.get("language")
            or (qs.get("language") or [None])[0]
            or DEFAULT_LANGUAGE
        )
        print(f"stt wav16k bytes={len(audio)} lang={language!r}")
        response_format = (fields.get("response_format") or "json").strip()
        try:
            text = azure_transcribe(audio, language, filename, AZURE_WAV_TYPE)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            print(f"stt azure {exc.code} {detail}")
            self._json(
                exc.code, {"error": {"message": f"azure {exc.code}", "detail": detail}}
            )
            return
        except (URLError, RuntimeError, TimeoutError, json.JSONDecodeError) as exc:
            self._json(502, {"error": {"message": str(exc)}})
            return
        if response_format == "text":
            self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
            return
        self._json(200, {"text": text})


def main() -> None:
    if not KEY:
        raise SystemExit("AZURE_SPEECH_KEY is empty")
    httpd = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"azure-speech-gateway listening on {LISTEN_HOST}:{LISTEN_PORT} -> {REGION}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
