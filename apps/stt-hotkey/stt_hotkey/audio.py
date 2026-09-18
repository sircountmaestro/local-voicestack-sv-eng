from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

from stt_hotkey import config


def wav_bytes(pcm: bytes, sample_rate: int = config.SAMPLE_RATE, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class Recorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._impl: _SoundDeviceRecorder | _FfmpegRecorder | None = None

    def start(self) -> None:
        self.stop()
        impl = _FfmpegRecorder()
        impl.start()
        with self._lock:
            self._impl = impl

    def stop(self) -> bytes:
        with self._lock:
            impl = self._impl
            self._impl = None
        if impl is None:
            return b""
        return impl.stop()


class _SoundDeviceRecorder:
    def __init__(self) -> None:
        self._frames: list[bytes] = []
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._frames = []

        def callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
            self._frames.append(bytes(indata))

        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> bytes:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        pcm = b"".join(self._frames)
        self._frames = []
        if not pcm:
            return b""
        return wav_bytes(pcm)


class _FfmpegRecorder:
    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._path: Path | None = None

    def start(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("varken sounddevice eller ffmpeg kan spela in")
        tmp = tempfile.NamedTemporaryFile(prefix="stt-hotkey-", suffix=".wav", delete=False)
        tmp.close()
        self._path = Path(tmp.name)
        args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if sys.platform == "win32":
            args += ["-f", "dshow", "-i", "audio=default"]
        else:
            args += ["-f", "pulse", "-i", "default"]
        args += [
            "-ac",
            str(config.CHANNELS),
            "-ar",
            str(config.SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(self._path),
        ]
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self) -> bytes:
        if self._proc is not None:
            self._proc.send_signal(2) if sys.platform != "win32" else self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        path = self._path
        self._path = None
        if path is None or not path.is_file():
            return b""
        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return data
