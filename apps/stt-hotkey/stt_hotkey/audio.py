from __future__ import annotations

import io
import re
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


def pulse_default_source() -> str | None:
    pactl = shutil.which("pactl")
    if not pactl:
        return None
    try:
        proc = subprocess.run(
            [pactl, "get-default-source"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    name = (proc.stdout or "").strip()
    return name or None


def dshow_first_audio(ffmpeg_stderr: str) -> str | None:
    in_audio = False
    for line in ffmpeg_stderr.splitlines():
        lower = line.lower()
        if "directshow audio devices" in lower:
            in_audio = True
            continue
        if in_audio and "directshow video" in lower:
            break
        if in_audio:
            match = re.search(r'"([^"]+)"', line)
            if match:
                return match.group(1)
    return None


def _dshow_first_audio_live() -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return dshow_first_audio(proc.stderr or "")


class Recorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._impl: _SoundDeviceRecorder | _FfmpegRecorder | None = None

    def start(self) -> None:
        self.stop()
        errors: list[str] = []
        for factory in (_SoundDeviceRecorder, _FfmpegRecorder):
            impl = factory()
            try:
                _start_limited(impl, 4.0)
            except Exception as exc:
                errors.append(f"{factory.__name__}: {exc}")
                try:
                    impl.stop()
                except Exception:
                    pass
                continue
            with self._lock:
                self._impl = impl
            print(f"inspelning via {factory.__name__}", flush=True)
            return
        raise RuntimeError("; ".join(errors) or "ingen inspelningsbackend")

    def stop(self) -> bytes:
        with self._lock:
            impl = self._impl
            self._impl = None
        if impl is None:
            return b""
        return impl.stop()


def _start_limited(impl: object, seconds: float) -> None:
    box: list[BaseException] = []

    def run() -> None:
        try:
            impl.start()  # type: ignore[attr-defined]
        except BaseException as exc:
            box.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise TimeoutError(f"{type(impl).__name__}.start timeout {seconds}s")
    if box:
        raise box[0]


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
            raise RuntimeError("ffmpeg saknas")
        tmp = tempfile.NamedTemporaryFile(prefix="stt-hotkey-", suffix=".wav", delete=False)
        tmp.close()
        self._path = Path(tmp.name)
        args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        args += _ffmpeg_input_args()
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
            if sys.platform == "win32":
                self._proc.terminate()
            else:
                self._proc.send_signal(2)
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


def _ffmpeg_input_args() -> list[str]:
    if sys.platform == "win32":
        name = _dshow_first_audio_live()
        if name:
            return ["-f", "dshow", "-i", f"audio={name}"]
        return ["-f", "wasapi", "-i", "default"]
    source = pulse_default_source()
    if source:
        return ["-f", "pulse", "-i", source]
    return ["-f", "pulse", "-i", "default"]
