"""Pluggable TTS backends for generate_audio.py."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path


class TTSBackend(ABC):
    name: str

    @abstractmethod
    def synthesize(self, text: str, language: str, out_path: Path) -> None:
        pass


class EdgeTTSBackend(TTSBackend):
    """Microsoft Edge neural voices — free, no API key, much better than gTTS."""

    name = "edge"

    DEFAULT_VOICES = {
        "fr": "fr-FR-HenriNeural",
        "en": "en-US-JennyNeural",
        "de": "de-DE-ConradNeural",
        "es": "es-ES-AlvaroNeural",
        "it": "it-IT-DiegoNeural",
        "pt": "pt-BR-AntonioNeural",
    }

    def __init__(self, voice: str | None = None, rate: str = "-5%") -> None:
        self.voice = voice
        self.rate = rate  # slightly slower for literary reading

    def _resolve_voice(self, language: str) -> str:
        if self.voice:
            return self.voice
        return self.DEFAULT_VOICES.get(language, f"{language}-{language.upper()}")

    def synthesize(self, text: str, language: str, out_path: Path) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise SystemExit("Install edge-tts: pip install edge-tts") from exc

        voice = self._resolve_voice(language)

        async def _run() -> None:
            communicate = edge_tts.Communicate(text, voice, rate=self.rate)
            await communicate.save(str(out_path))

        asyncio.run(_run())


class OpenAITTSBackend(TTSBackend):
    """OpenAI tts-1-hd — natural, uses your existing OPENAI_API_KEY."""

    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        voice: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or os.environ.get("TTS_MODEL", "tts-1-hd")
        self.voice = voice or os.environ.get("TTS_VOICE", "nova")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def synthesize(self, text: str, language: str, out_path: Path) -> None:
        if not self.api_key:
            raise SystemExit("Set OPENAI_API_KEY for the openai TTS backend")

        url = self.base_url.rstrip("/") + "/audio/speech"
        payload = {
            "model": self.model,
            "voice": self.voice,
            "input": text,
            "response_format": "mp3",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out_path.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"OpenAI TTS error {exc.code}: {detail}") from exc


class ElevenLabsTTSBackend(TTSBackend):
    """ElevenLabs — most expressive; best for audiobook-style narration."""

    name = "elevenlabs"

    def __init__(
        self,
        voice_id: str | None = None,
        model_id: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
        self.model_id = model_id or os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")

    def synthesize(self, text: str, language: str, out_path: Path) -> None:
        if not self.api_key:
            raise SystemExit("Set ELEVENLABS_API_KEY for the elevenlabs TTS backend")
        if not self.voice_id:
            raise SystemExit(
                "Set ELEVENLABS_VOICE_ID (pick a French voice at elevenlabs.io/voice-library)"
            )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "xi-api-key": self.api_key,
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out_path.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"ElevenLabs TTS error {exc.code}: {detail}") from exc


class GTTSBackend(TTSBackend):
    """Google Translate TTS — legacy fallback, robotic but simple."""

    name = "gtts"

    def synthesize(self, text: str, language: str, out_path: Path) -> None:
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise SystemExit("Install gTTS: pip install gtts") from exc

        tts = gTTS(text=text, lang=language)
        tts.save(str(out_path))


BACKENDS: dict[str, type[TTSBackend]] = {
    "edge": EdgeTTSBackend,
    "openai": OpenAITTSBackend,
    "elevenlabs": ElevenLabsTTSBackend,
    "gtts": GTTSBackend,
}


def get_backend(name: str, **kwargs) -> TTSBackend:
    cls = BACKENDS.get(name)
    if not cls:
        options = ", ".join(BACKENDS)
        raise SystemExit(f"Unknown backend {name!r}. Choose: {options}")
    return cls(**kwargs)
