#!/usr/bin/env python3
"""OpenAI-compatible STT on CPU via faster-whisper. No GPU."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download

CT2_PATTERNS = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "vocabulary.json",
    "vocabulary.txt",
    "tokenizer_config.json",
    "preprocessor_config.json",
    "added_tokens.json",
    "normalizer.json",
)

MODEL_ID = os.environ.get("WHISPER_MODEL", "KBLab/kb-whisper-base").strip()
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu").strip() or "cpu"
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
DEFAULT_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "sv").strip() or "sv"
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9000"))
MAX_BODY = int(os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))

_INFER_LOCK = threading.Lock()
_MODEL: WhisperModel | None = None
_STATUS = "starting"
_STATUS_ERROR = ""


def load_model() -> WhisperModel:
    global _MODEL
    if _MODEL is None:
        print(
            f"loading {MODEL_ID} device={DEVICE} compute_type={COMPUTE_TYPE}",
            flush=True,
        )
        model_path = snapshot_download(MODEL_ID, allow_patterns=list(CT2_PATTERNS))
        _MODEL = WhisperModel(model_path, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("model ready", flush=True)
    return _MODEL


def _load_model_bg() -> None:
    global _STATUS, _STATUS_ERROR
    _STATUS = "loading"
    try:
        load_model()
        _STATUS = "ready"
    except Exception as exc:
        _STATUS = "error"
        _STATUS_ERROR = str(exc)
        print(f"model load failed: {exc}", flush=True)


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


def suffix_for(filename: str, content_type: str) -> str:
    name = filename.lower()
    ctype = content_type.lower()
    for ext in (".wav", ".ogg", ".mp3", ".webm", ".flac", ".m4a", ".mp4"):
        if name.endswith(ext):
            return ext
    if "wav" in ctype:
        return ".wav"
    if "ogg" in ctype:
        return ".ogg"
    if "mpeg" in ctype or "mp3" in ctype:
        return ".mp3"
    if "webm" in ctype:
        return ".webm"
    return ".wav"


def transcribe(
    audio: bytes, filename: str, content_type: str, language: str
) -> dict:
    model = load_model()
    ext = suffix_for(filename, content_type)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(audio)
        tmp.flush()
        with _INFER_LOCK:
            raw_segments, info = model.transcribe(
                tmp.name,
                language=language or None,
                condition_on_previous_text=False,
            )
            segs = list(raw_segments)
    segments = []
    for i, seg in enumerate(segs):
        segments.append(
            {
                "id": i,
                "seek": int(getattr(seg, "seek", 0) or 0),
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text,
                "tokens": list(getattr(seg, "tokens", []) or []),
                "temperature": float(getattr(seg, "temperature", 0.0) or 0.0),
                "avg_logprob": float(seg.avg_logprob),
                "compression_ratio": float(
                    getattr(seg, "compression_ratio", 1.0) or 1.0
                ),
                "no_speech_prob": float(getattr(seg, "no_speech_prob", 0.0) or 0.0),
            }
        )
    text = "".join(s["text"] for s in segments).strip()
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    if duration <= 0 and segments:
        duration = float(segments[-1]["end"])
    detected = getattr(info, "language", None) or language or DEFAULT_LANGUAGE
    return {
        "task": "transcribe",
        "language": detected,
        "duration": duration,
        "text": text,
        "segments": segments,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _cors_headers(self) -> None:
        origin = (self.headers.get("Origin") or "").strip()
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
                    "ok": _STATUS == "ready",
                    "status": _STATUS,
                    "error": _STATUS_ERROR or None,
                    "model": MODEL_ID,
                    "device": DEVICE,
                    "compute_type": COMPUTE_TYPE,
                    "language": DEFAULT_LANGUAGE,
                },
            )
            return
        if path in ("/v1/models", "/models"):
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "owned_by": "whisper-stt-sv",
                        }
                    ],
                },
            )
            return
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/v1/audio/transcriptions", "/audio/transcriptions"):
            self._json(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length > MAX_BODY:
            self._json(413, {"error": {"message": "body too large"}})
            return
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type") or ""
        qs = parse_qs(parsed.query)
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
        if _STATUS != "ready":
            self._json(
                503,
                {"error": {"message": "model not ready", "status": _STATUS}},
            )
            return
        if not audio:
            self._json(400, {"error": {"message": "file required"}})
            return
        language = (
            fields.get("language")
            or (qs.get("language") or [""])[0]
            or DEFAULT_LANGUAGE
        ).strip()
        fmt = (
            fields.get("response_format")
            or fields.get("responseFormat")
            or (qs.get("response_format") or [""])[0]
            or "json"
        ).strip().lower()
        try:
            result = transcribe(audio, filename, file_ctype, language)
        except Exception as exc:
            self._json(500, {"error": {"message": str(exc)}})
            return
        if fmt == "text":
            self._send(200, result["text"].encode(), "text/plain; charset=utf-8")
            return
        if fmt in {"json"}:
            # Hearing asks verbose_json; keep segments on json too so a
            # missed field name still lets confidence filtering run.
            self._json(200, {"text": result["text"], "segments": result["segments"]})
            return
        self._json(200, result)


def main() -> None:
    if DEVICE != "cpu":
        raise SystemExit(f"refusing non-cpu device={DEVICE!r}")
    threading.Thread(target=_load_model_bg, daemon=True).start()
    httpd = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"listen {LISTEN_HOST}:{LISTEN_PORT} model={MODEL_ID} status={_STATUS}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
