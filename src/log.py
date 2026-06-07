"""Shared in-memory event log accessible from all modules."""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

_lock = threading.Lock()
_entries: deque[str] = deque(maxlen=100)

# Latest transcription / processed results (for feedback tab)
last_transcript: str = ""
last_processed: str = ""
last_mode: str = ""
last_error: str = ""


def add(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    with _lock:
        _entries.append(f"[{ts}] {msg}")


def get_all() -> list[str]:
    with _lock:
        return list(_entries)


def set_last(transcript: str, processed: str, mode: str):
    global last_transcript, last_processed, last_mode, last_error
    last_transcript = transcript
    last_processed = processed
    last_mode = mode
    last_error = ""


def set_error(msg: str):
    global last_error
    last_error = msg
    add(f"FEHLER: {msg}")
