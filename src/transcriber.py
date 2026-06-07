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
    return Path(__file__).parent.parent


_DEFAULT_MODEL_DIR = str(_app_dir() / "whisper")

_local_model = None
_local_model_dir: str | None = None  # tracks which directory is currently loaded


def _resolve_dir(model_path: str | None) -> str:
    """Return the top-level model cache directory.

    Accepts:
      - None               → default ./whisper
      - path/to/model.bin  → its parent directory
      - path/to/dir/       → that directory
      - any path *inside* a HuggingFace cache structure
        (…/models--ORG--NAME/… or …/snapshots/…)
        → normalised back to the cache root (the folder containing models--*)
    """
    if not model_path:
        return _DEFAULT_MODEL_DIR
    p = Path(model_path)
    if not p.is_absolute():
        p = _app_dir() / p
    if p.suffix == ".bin" or p.is_file():
        p = p.parent
    # Walk up to the HuggingFace cache root if we're inside one.
    # Cache root is the directory that *contains* the "models--ORG--NAME" folder.
    parts = p.parts
    for i, part in enumerate(parts):
        if part.startswith("models--"):
            return str(Path(*parts[:i])) if i > 0 else str(Path(parts[0]))
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


def load_local_model(model_path: str | None = None, on_progress=None):
    """Pre-load the local Whisper model (blocking). Safe to call if already loaded.

    on_progress: optional callable(downloaded_bytes: int, total_bytes: int)
                 called periodically during download. Not called when loading from disk.
    """
    _ensure_local_model(model_path, on_progress=on_progress)


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


def _find_model_bin(model_dir: str) -> str | None:
    """Find the directory containing model.bin — flat layout or HuggingFace snapshot.

    Always returns the shallowest match so nested duplicates (created by old
    download_root mis-configurations) are ignored.
    """
    p = Path(model_dir)
    candidate = p / "model.bin"
    if candidate.exists() or candidate.is_symlink():
        return str(p)
    # HuggingFace cache layout: pick the shallowest model.bin found
    matches = [f for f in p.rglob("model.bin") if f.exists() or f.is_symlink()]
    if matches:
        return str(min(matches, key=lambda f: len(f.parts)).parent)
    return None


def _download_with_progress(model_dir: str, on_progress=None):
    """Download faster-whisper-small into model_dir, reporting byte progress via on_progress."""
    import os
    os.makedirs(model_dir, exist_ok=True)
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    from huggingface_hub import snapshot_download

    if on_progress is None:
        snapshot_download("Systran/faster-whisper-small", cache_dir=model_dir)
        return

    # Monkey-patch tqdm in huggingface_hub temporarily to capture byte progress.
    # Only track large files (> 1 MB) so small metadata files don't confuse the display.
    import huggingface_hub.file_download as _hf_fd
    _orig_tqdm = _hf_fd.tqdm

    class _ProgressTqdm(_orig_tqdm):
        def update(self, n=1):
            super().update(n)
            if self.total and self.total > 1_000_000:
                on_progress(self.n, self.total)

    _hf_fd.tqdm = _ProgressTqdm
    try:
        snapshot_download("Systran/faster-whisper-small", cache_dir=model_dir)
    finally:
        _hf_fd.tqdm = _orig_tqdm


def _ensure_local_model(model_path: str | None = None, on_progress=None):
    global _local_model, _local_model_dir
    model_dir = _resolve_dir(model_path)
    if _local_model is not None and _local_model_dir == model_dir:
        return

    from faster_whisper import WhisperModel

    # Step 1: Check for existing model on disk (flat OR HuggingFace cache layout)
    print(f"[transcriber] Suche model.bin in: {model_dir}", file=sys.stderr, flush=True)
    found_dir = _find_model_bin(model_dir)
    if found_dir:
        print(f"[transcriber] model.bin gefunden: {found_dir} — lade direkt", file=sys.stderr, flush=True)
        try:
            _local_model = WhisperModel(found_dir, device="cpu", compute_type="int8")
            _local_model_dir = model_dir
            print("[transcriber] Modell erfolgreich geladen (cpu/int8)", file=sys.stderr, flush=True)
            return
        except Exception as e:
            print(f"[transcriber] Laden fehlgeschlagen: {e} — versuche Download", file=sys.stderr, flush=True)

    # Step 2: Model not found locally — download with progress, then load
    print(f"[transcriber] model.bin nicht gefunden, starte Download nach: {model_dir}", file=sys.stderr, flush=True)
    try:
        _download_with_progress(model_dir, on_progress=on_progress)
    except Exception as e:
        print(f"[transcriber] FEHLER beim Download: {e}", file=sys.stderr, flush=True)
        raise RuntimeError(f"Lokales Whisper-Modell konnte nicht heruntergeladen werden: {e}") from e

    found_dir = _find_model_bin(model_dir)
    if not found_dir:
        raise RuntimeError("Download abgeschlossen, aber model.bin nicht gefunden.")
    try:
        _local_model = WhisperModel(found_dir, device="cpu", compute_type="int8")
        _local_model_dir = model_dir
        print("[transcriber] Modell heruntergeladen und geladen", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[transcriber] FEHLER beim Laden nach Download: {e}", file=sys.stderr, flush=True)
        raise RuntimeError(f"Lokales Whisper-Modell konnte nicht geladen werden: {e}") from e


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
