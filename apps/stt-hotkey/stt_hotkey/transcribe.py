from __future__ import annotations

import json
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SPECIAL_TOKEN = re.compile(r"<\|[^>]+\|>")

from stt_hotkey import config

SKIP = {
    "",
    ".",
    "..",
    "...",
    "tack för att du tittar",
    "tack för att ni tittar",
    "undertexter av amara.org",
    "musik",
    "applåder",
    "[musik]",
    "[applåder]",
    "textning",
}


def is_usable_transcript(text: str) -> bool:
    cleaned = SPECIAL_TOKEN.sub(" ", text)
    cleaned = " ".join(cleaned.split()).strip(" .").lower()
    if cleaned in SKIP:
        return False
    letters = [ch for ch in cleaned if ch.isalpha()]
    return len(letters) >= 2


def transcribe(wav: bytes) -> str:
    errors: list[str] = []
    for url, language in (
        (f"{config.WHISPER_URL.rstrip('/')}/v1/audio/transcriptions", config.LANGUAGE),
        (f"{config.AZURE_URL.rstrip('/')}/v1/audio/transcriptions", "sv-SE"),
    ):
        try:
            text = _post_wav(url, wav, language)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            errors.append(f"{url}: {exc}")
            continue
        if is_usable_transcript(text):
            return SPECIAL_TOKEN.sub("", text).strip()
        return ""
    if errors:
        raise RuntimeError("; ".join(errors))
    return ""


def _post_wav(url: str, wav: bytes, language: str) -> str:
    boundary = "----stt" + uuid.uuid4().hex
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        wav,
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="language"\r\n\r\n',
        language.encode(),
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="response_format"\r\n\r\n',
        b"json\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(chunks)
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    with urlopen(req, timeout=config.TRANSCRIBE_TIMEOUT) as resp:
        raw = resp.read()
        ctype = resp.headers.get("Content-Type", "")
    if "text/plain" in ctype:
        return raw.decode("utf-8", "replace").strip()
    payload = json.loads(raw.decode("utf-8") or "{}")
    if isinstance(payload, dict):
        text = payload.get("text") or payload.get("DisplayText") or ""
        if not text and isinstance(payload.get("error"), dict):
            raise RuntimeError(str(payload["error"].get("message") or payload["error"]))
        return str(text)
    return ""
