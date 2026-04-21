"""Textblitz — Windows speech-to-text tray app.

Architecture
------------
  main thread  → pystray (required on Windows)
  thread-2     → pynput keyboard listener (self-managed by pynput)
  thread-pool  → audio recording + API pipeline (one job at a time)
  thread-3     → customtkinter settings window (opened on demand)

Usage
-----
  python main.py
"""
from __future__ import annotations

import ctypes
import sys
import threading

# DPI-Awareness vor allen GUI-Importen setzen, damit Windows kein unscharfes
# Bitmap-Upscaling anwendet (z. B. bei 125 % Anzeigeskalierung).
try:
    ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
from concurrent.futures import ThreadPoolExecutor

import log as applog
import overlay
import toast
import transcriber as _transcriber
from config import Config
from hotkeys import HotkeyListener
from injector import inject
from processor import process, apply_snippets
from recorder import Recorder
from settings_ui import open_settings_window
from transcriber import transcribe
from tray import TrayIcon


class Textblitz:
    def __init__(self):
        self._config = Config()
        self._recorder = Recorder()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._settings_lock = threading.Lock()  # prevent multiple settings windows
        self._busy_lock = threading.Lock()       # prevent overlapping recordings/pipelines
        self._recording_active = False           # True only when recording actually started

        self._tray = TrayIcon(
            on_open_settings=self._open_settings,
            on_quit=self._quit,
        )
        self._hotkeys = HotkeyListener(
            get_hotkeys=lambda: self._config.hotkeys,
            on_start=self._on_recording_start,
            on_stop=self._on_recording_stop,
            get_record_mode=lambda: self._config.record_mode,
        )

    # ── lifecycle ─────────────────────────────────────────────────────
    def run(self):
        self._hotkeys.start()
        if self._config.use_local_whisper:
            threading.Thread(
                target=self._preload_model, daemon=True, name="model-preload"
            ).start()
        print("[Textblitz] gestartet — bereit")
        self._tray.run()  # blocks until quit

    def _preload_model(self):
        try:
            _transcriber.load_local_model(self._config.whisper_model_path or None)
            applog.add("Lokales Modell geladen")
        except Exception as exc:
            applog.add(f"Modell-Vorladen fehlgeschlagen: {exc}")

    def _quit(self):
        print("[Textblitz] wird beendet…")
        self._hotkeys.stop()
        self._executor.shutdown(wait=False)
        self._tray.stop()

    # ── hotkey callbacks (called from pynput thread) ──────────────────
    def _on_recording_start(self, mode: str):
        print(f"[DBG] start mode={mode} api={'ok' if self._config.api_key else 'LEER'} local={self._config.use_local_whisper}", file=sys.stderr, flush=True)
        if not self._config.api_key and not self._config.use_local_whisper:
            applog.add("Kein API-Key gesetzt — Einstellungen öffnen")
            self._tray.set_status("error")
            self._open_settings()
            return

        if not self._busy_lock.acquire(blocking=False):
            applog.add("Aufnahme ignoriert — vorherige Verarbeitung läuft noch")
            return

        self._recording_active = True
        applog.add(f"Aufnahme gestartet ({mode})")
        self._tray.set_status("recording", mode=mode)
        overlay.show_recording(mode)
        self._recorder.start()
        print(f"[DBG] recorder gestartet", file=sys.stderr, flush=True)

    def _on_recording_stop(self, mode: str):
        if not self._recording_active:
            return  # start was ignored (busy lock held) — don't touch the lock
        self._recording_active = False

        applog.add(f"Aufnahme gestoppt ({mode})")
        audio_buf = self._recorder.stop()
        print(f"[DBG] stop audio_buf={'None' if audio_buf is None else f'{audio_buf.getbuffer().nbytes} bytes'}", file=sys.stderr, flush=True)
        if audio_buf is None:
            applog.add("Keine Audiodaten — zu kurze Aufnahme?")
            overlay.hide()
            self._busy_lock.release()
            self._tray.set_status("ready")
            return

        self._tray.set_status("processing", mode=mode)
        overlay.show_processing(mode)
        try:
            self._executor.submit(self._pipeline, audio_buf, mode)
        except Exception:
            overlay.hide()
            self._busy_lock.release()
            self._tray.set_status("error")

    # ── processing pipeline (runs in thread-pool) ─────────────────────
    def _pipeline(self, audio_buf, mode: str):
        try:
            print(f"[DBG] pipeline start, use_local={self._config.use_local_whisper}", file=sys.stderr, flush=True)
            transcript = transcribe(
                audio_buf,
                api_key=self._config.api_key,
                language=self._config.whisper_language,
                proper_nouns=self._config.proper_nouns or None,
                model=(self._config.whisper_model_groq
                       if self._config.api_key.startswith("gsk_")
                       else self._config.whisper_model_openai),
                use_local=self._config.use_local_whisper,
                model_path=self._config.whisper_model_path or None,
            )
            print(f"[DBG] transcript={transcript!r}", file=sys.stderr, flush=True)
            applog.add(f"Transkript ({mode}): {transcript!r}")

            if mode != "normal":
                result = process(
                    transcript,
                    mode=mode,
                    api_key=self._config.api_key,
                    prompt_template=self._config.get_prompt(mode),
                    emoji_density=self._config.emoji_density,
                    model=(self._config.chat_model_groq
                           if self._config.api_key.startswith("gsk_")
                           else self._config.chat_model_openai),
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens,
                )
                applog.add(f"Verarbeitet ({mode}): {result!r}")
            else:
                result = transcript

            applog.set_last(transcript, result, mode)
            result = apply_snippets(result, self._config.snippets)
            print(f"[DBG] inject: {result!r}", file=sys.stderr, flush=True)
            inject(result)
            print(f"[DBG] inject done", file=sys.stderr, flush=True)
            overlay.hide()
            toast.show(result)
            self._tray.set_status("ready")

        except Exception as exc:
            msg = str(exc)
            applog.set_error(msg)
            print(f"[Fehler] {msg}", file=sys.stderr)
            overlay.hide()
            self._tray.set_status("error")
            threading.Timer(3.0, lambda: self._tray.set_status("ready")).start()

        finally:
            self._busy_lock.release()

    # ── settings ──────────────────────────────────────────────────────
    def _open_settings(self):
        if not self._settings_lock.acquire(blocking=False):
            return  # already open
        try:
            # Tell hotkey listener to stop acting while settings are capturing keys
            self._hotkeys.capturing = True
            t = threading.Thread(
                target=self._run_settings_thread,
                daemon=True,
                name="settings-window",
            )
            t.start()
        except Exception:
            self._settings_lock.release()
            self._hotkeys.capturing = False

    def _run_settings_thread(self):
        try:
            open_settings_window(
                config=self._config,
                on_save=self._on_settings_saved,
            )
        finally:
            self._hotkeys.capturing = False
            self._settings_lock.release()

    def _on_settings_saved(self, config: Config):
        applog.add("Einstellungen gespeichert")


def main():
    app = Textblitz()
    app.run()


if __name__ == "__main__":
    main()
