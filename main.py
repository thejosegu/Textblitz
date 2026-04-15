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

import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import log as applog
import toast
from config import Config
from hotkeys import HotkeyListener
from injector import inject
from processor import process
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

        self._tray = TrayIcon(
            on_open_settings=self._open_settings,
            on_quit=self._quit,
        )
        self._hotkeys = HotkeyListener(
            get_hotkeys=lambda: self._config.hotkeys,
            on_start=self._on_recording_start,
            on_stop=self._on_recording_stop,
        )

    # ── lifecycle ─────────────────────────────────────────────────────
    def run(self):
        self._hotkeys.start()
        print("[Textblitz] gestartet — bereit")
        self._tray.run()  # blocks until quit

    def _quit(self):
        print("[Textblitz] wird beendet…")
        self._hotkeys.stop()
        self._executor.shutdown(wait=False)
        self._tray.stop()

    # ── hotkey callbacks (called from pynput thread) ──────────────────
    def _on_recording_start(self, mode: str):
        if not self._config.api_key:
            applog.add("Kein API-Key gesetzt — Einstellungen öffnen")
            self._tray.set_status("error")
            self._open_settings()
            return

        applog.add(f"Aufnahme gestartet ({mode})")
        self._tray.set_status("recording", mode=mode)
        self._recorder.start()

    def _on_recording_stop(self, mode: str):
        applog.add(f"Aufnahme gestoppt ({mode})")
        audio_buf = self._recorder.stop()
        if audio_buf is None:
            applog.add("Keine Audiodaten — zu kurze Aufnahme?")
            self._tray.set_status("ready")
            return

        self._tray.set_status("processing", mode=mode)
        self._executor.submit(self._pipeline, audio_buf, mode)

    # ── processing pipeline (runs in thread-pool) ─────────────────────
    def _pipeline(self, audio_buf, mode: str):
        try:
            transcript = transcribe(
                audio_buf,
                api_key=self._config.api_key,
                language=self._config.whisper_language,
                proper_nouns=self._config.proper_nouns or None,
            )
            applog.add(f"Transkript ({mode}): {transcript!r}")

            if mode != "normal":
                result = process(
                    transcript,
                    mode=mode,
                    api_key=self._config.api_key,
                    prompt_template=self._config.get_prompt(mode),
                    emoji_density=self._config.emoji_density,
                )
                applog.add(f"Verarbeitet ({mode}): {result!r}")
            else:
                result = transcript

            applog.set_last(transcript, result, mode)
            inject(result)
            toast.show(result)
            self._tray.set_status("ready")

        except Exception as exc:
            msg = str(exc)
            applog.set_error(msg)
            print(f"[Fehler] {msg}", file=sys.stderr)
            self._tray.set_status("error")
            threading.Timer(3.0, lambda: self._tray.set_status("ready")).start()

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
