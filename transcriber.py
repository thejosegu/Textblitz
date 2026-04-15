"""Audio transcription — supports OpenAI Whisper and Groq Whisper.

Provider is detected automatically from the API key prefix:
  sk-...   → OpenAI  (model: whisper-1)
  gsk_...  → Groq    (model: whisper-large-v3-turbo)
"""
from __future__ import annotations

import io


def transcribe(audio_buf: io.BytesIO, api_key: str,
               language: str = "auto",
               proper_nouns: list[str] | None = None) -> str:
    if _is_groq(api_key):
        return _groq(audio_buf, api_key, language, proper_nouns)
    return _openai(audio_buf, api_key, language, proper_nouns)


def detect_provider(api_key: str) -> str:
    """Return 'Groq', 'OpenAI', or 'Unbekannt'."""
    if not api_key:
        return "Nicht gesetzt"
    if _is_groq(api_key):
        return "Groq"
    if api_key.startswith("sk-"):
        return "OpenAI"
    return "Unbekannt"


# ── providers ─────────────────────────────────────────────────────────

def _is_groq(key: str) -> bool:
    return key.startswith("gsk_")


def _openai(audio_buf, api_key, language, proper_nouns):
    import openai
    client = openai.OpenAI(api_key=api_key)
    kwargs: dict = {"model": "whisper-1", "file": audio_buf}
    if language and language != "auto":
        kwargs["language"] = language
    if proper_nouns:
        kwargs["prompt"] = ", ".join(proper_nouns)
    return client.audio.transcriptions.create(**kwargs).text.strip()


def _groq(audio_buf, api_key, language, proper_nouns):
    from groq import Groq
    client = Groq(api_key=api_key)
    kwargs: dict = {"model": "whisper-large-v3-turbo", "file": audio_buf}
    if language and language != "auto":
        kwargs["language"] = language
    if proper_nouns:
        kwargs["prompt"] = ", ".join(proper_nouns)
    return client.audio.transcriptions.create(**kwargs).text.strip()
