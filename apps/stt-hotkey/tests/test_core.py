#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stt_hotkey.audio import wav_bytes
from stt_hotkey.transcribe import is_usable_transcript, transcribe


class WavTests(unittest.TestCase):
    def test_header(self) -> None:
        pcm = b"\x00\x00" * 160
        data = wav_bytes(pcm, sample_rate=16000)
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(data[8:12], b"WAVE")
        self.assertGreater(len(data), 44)


class TranscriptFilterTests(unittest.TestCase):
    def test_keeps_swedish(self) -> None:
        self.assertTrue(is_usable_transcript("Hej, hur mår du?"))

    def test_drops_noise(self) -> None:
        self.assertFalse(is_usable_transcript("musik"))
        self.assertFalse(is_usable_transcript("..."))
        self.assertFalse(is_usable_transcript("  "))
        self.assertFalse(is_usable_transcript("<|nospeech|>"))


class TranscribeClientTests(unittest.TestCase):
    def test_posts_whisper_first(self) -> None:
        wav = wav_bytes(b"\x01\x00" * 320)

        class Resp:
            headers = {"Content-Type": "application/json"}

            def read(self) -> bytes:
                return '{"text":"hej världen"}'.encode()

            def __enter__(self):
                return self

            def __exit__(self, *args) -> None:
                return None

        with mock.patch("stt_hotkey.transcribe.urlopen", return_value=Resp()) as opener:
            text = transcribe(wav)
        self.assertEqual(text, "hej världen")
        url = opener.call_args[0][0].full_url
        self.assertIn("127.0.0.1:9000", url)


class LifecyclePidTests(unittest.TestCase):
    def test_stale_pid_cleared(self) -> None:
        from stt_hotkey import lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            with mock.patch.object(lifecycle, "runtime_dir", return_value=fake):
                lifecycle.pid_path().write_text("99999999")
                self.assertIsNone(lifecycle.running_pid())
                self.assertFalse(lifecycle.pid_path().exists())


if __name__ == "__main__":
    unittest.main()
