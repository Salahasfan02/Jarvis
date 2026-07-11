"""Pluggable text-to-speech engines.

The frontend asks /api/tts/speak; if the configured engine can synthesize
server-side it returns a WAV, otherwise {"engine": "browser"} tells the UI
to use the built-in browser voices. New engines (XTTS-v2, Kokoro, OpenVoice,
F5-TTS, voice clones...) implement synthesize() and register themselves —
no other code changes needed, and the Settings dropdown picks them up from
/api/tts/engines.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from ..config import settings


class TTSEngine:
    id = "base"
    name = "Base"

    def available(self) -> bool:
        raise NotImplementedError

    def unavailable_reason(self) -> str:
        return ""

    async def synthesize(self, text: str) -> bytes | None:
        """Return WAV bytes, or None to fall back to the browser."""
        raise NotImplementedError


class BrowserEngine(TTSEngine):
    """The default: synthesis happens in the frontend (Web Speech API)."""
    id = "browser"
    name = "Browser voices (built-in)"

    def available(self) -> bool:
        return True

    async def synthesize(self, text: str) -> bytes | None:
        return None


class PiperEngine(TTSEngine):
    """Local neural TTS via the `piper` CLI. Install:  brew install piper-tts
    (or pipx install piper-tts), then download a voice .onnx model and set
    its path in Settings -> Voice."""
    id = "piper"
    name = "Piper (local neural TTS)"

    def _binary(self) -> str | None:
        return shutil.which("piper")

    def _voice(self) -> str:
        return settings.get("voice.piper_voice_path", "")

    def available(self) -> bool:
        return bool(self._binary() and self._voice() and Path(self._voice()).exists())

    def unavailable_reason(self) -> str:
        if not self._binary():
            return "piper binary not found (brew install piper-tts)"
        if not self._voice():
            return "no voice model set (Settings > Voice > Piper voice path)"
        if not Path(self._voice()).exists():
            return f"voice model not found at {self._voice()}"
        return ""

    async def synthesize(self, text: str) -> bytes | None:
        if not self.available():
            return None
        out = Path(tempfile.mkstemp(suffix=".wav")[1])
        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary(), "--model", self._voice(), "--output_file", str(out),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await asyncio.wait_for(proc.communicate(text.encode()), timeout=60)
            return out.read_bytes() if out.exists() and out.stat().st_size > 0 else None
        except (asyncio.TimeoutError, OSError):
            return None
        finally:
            out.unlink(missing_ok=True)


ENGINES: dict[str, TTSEngine] = {}


def register(engine: TTSEngine) -> None:
    ENGINES[engine.id] = engine


register(BrowserEngine())
register(PiperEngine())


def list_engines() -> list[dict]:
    return [{"id": e.id, "name": e.name, "available": e.available(),
             "reason": e.unavailable_reason()} for e in ENGINES.values()]


async def synthesize(text: str) -> bytes | None:
    engine = ENGINES.get(settings.get("voice.tts_engine", "browser"))
    if engine is None:
        return None
    try:
        return await engine.synthesize(text)
    except Exception:
        return None
