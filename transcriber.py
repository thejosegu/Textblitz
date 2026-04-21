"""Audio transcription — supports OpenAI Whisper, Groq Whisper, and local faster-whisper.

Provider is detected automatically from the API key prefix:
  sk-...   → OpenAI  (model: whisper-1)
  gsk_...  → Groq    (model: whisper-large-v3-turbo)
  local    → faster-whisper small (no API key required)
"""
from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


_DEFAULT_MODEL_DIR = str(_app_dir() / "whisper")

_local_model = None
_local_model_dir: str | None = None  # tracks which directory is currently loaded


def _resolve_dir(model_path: str | None) -> str:
    """Return model directory from a file path, directory path, or None (→ default)."""
    if not model_path:
        return _DEFAULT_MODEL_DIR
    p = Path(model_path)
    if not p.is_absolute():
        p = _app_dir() / p
    if p.suffix == ".bin" or p.is_file():
        return str(p.parent)
    return str(p)


def is_local_model_loaded() -> bool:
    return _local_model is not None


def is_model_on_disk(model_path: str | None = None) -> bool:
    """Check if model files exist on disk without loading them.

    Accepts a path to model.bin, a model directory, or None (uses default ./whisper).
    Supports both flat layout and huggingface_hub cache layout.
    """
    model_dir = _resolve_dir(model_path)
    if Path(model_dir, "model.bin").exists():
        return True
    try:
        from huggingface_hub import try_to_load_from_cache
        result = try_to_load_from_cache(
            repo_id="Systran/faster-whisper-small",
            filename="model.bin",
            cache_dir=model_dir,
        )
        return result is not None
    except Exception:
        return False


def load_local_model(model_path: str | None = None):
    """Pre-load the local Whisper model (blocking). Safe to call if already loaded."""
    _ensure_local_model(model_path)


def transcribe(audio_buf: io.BytesIO, api_key: str,
               language: str = "auto",
               proper_nouns: list[str] | None = None,
               model: str | None = None,
               use_local: bool = False,
               model_path: str | None = None) -> str:
    if use_local:
        return _local(audio_buf, language, proper_nouns, model_path)
    if _is_groq(api_key):
        return _groq(audio_buf, api_key, language, proper_nouns,
                     model or "whisper-large-v3-turbo")
    return _openai(audio_buf, api_key, language, proper_nouns,
                   model or "whisper-1")


def detect_provider(api_key: str, use_local: bool = False) -> str:
    if use_local:
        return "Lokal (Whisper Small)"
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


def _openai(audio_buf, api_key, language, proper_nouns, model="whisper-1"):
    import openai
    client = openai.OpenAI(api_key=api_key)
    kwargs: dict = {"model": model, "file": audio_buf}
    if language and language != "auto":
        kwargs["language"] = language
    if proper_nouns:
        kwargs["prompt"] = ", ".join(proper_nouns)
    return client.audio.transcriptions.create(**kwargs).text.strip()


def _groq(audio_buf, api_key, language, proper_nouns, model="whisper-large-v3-turbo"):
    from groq import Groq
    client = Groq(api_key=api_key)
    kwargs: dict = {"model": model, "file": audio_buf}
    if language and language != "auto":
        kwargs["language"] = language
    if proper_nouns:
        kwargs["prompt"] = ", ".join(proper_nouns)
    return client.audio.transcriptions.create(**kwargs).text.strip()


def _ensure_local_model(model_path: str | None = None):
    global _local_model, _local_model_dir
    model_dir = _resolve_dir(model_path)
    if _local_model is not None and _local_model_dir == model_dir:
        return
    from faster_whisper import WhisperModel
    import os
    if Path(model_dir, "model.bin").exists():
        _local_model = WhisperModel(model_dir, device="auto", compute_type="auto")
    else:
        os.makedirs(model_dir, exist_ok=True)
        _local_model = WhisperModel("small", device="auto", compute_type="auto",
                                    download_root=model_dir)
    _local_model_dir = model_dir


def _local(audio_buf: io.BytesIO, language: str,
           proper_nouns: list[str] | None,
           model_path: str | None = None) -> str:
    _ensure_local_model(model_path)

    audio_buf.seek(0)
    with wave.open(audio_buf) as wf:
        frames = wf.readframes(wf.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    kwargs: dict = {"beam_size": 5}
    if language and language != "auto":
        kwargs["language"] = language
    if proper_nouns:
        kwargs["initial_prompt"] = ", ".join(proper_nouns)

    segments, _ = _local_model.transcribe(audio, **kwargs)
    return "".join(seg.text for seg in segments).strip()
