"""Settings window — Windows 11 Fluent Design via tkinter/ttk + sv-ttk.

Runs in its own persistent daemon thread. Do NOT call from the main thread
while pystray is blocked there.
"""
from __future__ import annotations

import platform
import queue
import sys
import threading
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import ttk
import sv_ttk
from pynput import keyboard as pynput_kb

import log as applog
from config import Config
from hotkeys import hotkey_to_str, parse_hotkey
from transcriber import detect_provider, is_local_model_loaded, is_model_on_disk, load_local_model, _DEFAULT_MODEL_DIR

_MODES       = ["normal", "plus", "rage", "emoji"]
_MODE_LABELS = {"normal": "Normal", "plus": "Plus", "rage": "Rage", "emoji": "Emoji"}
_LANGUAGES   = ["auto", "de", "en", "fr", "es", "it", "pt", "nl", "pl", "ru", "zh", "ja"]

# ── Windows 11 Design Tokens ───────────────────────────────────────────
# Segoe UI Variable is the native Windows 11 typeface
_FONT        = ("Segoe UI Variable Text",    9)
_FONT_BOLD   = ("Segoe UI Variable Text",    9,  "bold")
_FONT_HEADER = ("Segoe UI Variable Display", 11, "bold")
_FONT_SMALL  = ("Segoe UI Variable Text",    8)
_FONT_MONO   = ("Cascadia Code",             9)

# Accent / status colors — switch per theme
_DARK_ACCENT  = "#60CDFF"   # Windows 11 blue (dark)
_LIGHT_ACCENT = "#0078D4"   # Windows 11 blue (light)
_GREEN        = "#6CCB5F"
_RED          = "#F55252"
_MUTED        = "#767676"

# Card backgrounds (drawn on top of sv-ttk surface)
_CARD_DARK  = "#2B2B2B"
_CARD_LIGHT = "#F5F5F5"


def _is_dark_mode() -> bool:
    """Read Windows registry to follow system dark/light setting."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return val == 0
    except Exception:
        return True  # default to dark


class SettingsWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self._dark = _is_dark_mode()
        sv_ttk.set_theme("dark" if self._dark else "light")

        self._accent   = _DARK_ACCENT  if self._dark else _LIGHT_ACCENT
        self._card_bg  = _CARD_DARK    if self._dark else _CARD_LIGHT
        self._input_bg = "#1A1A1A"     if self._dark else "#FFFFFF"
        self._muted_fg = _MUTED
        self._text_fg  = "#FFFFFF"      if self._dark else "#000000"

        self._apply_styles()

        self._config: Config | None = None
        self._on_save:  Callable | None = None
        self._on_close: Callable | None = None

        self.title("Blitztext — Einstellungen")
        self.geometry("720x820")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build_ui()
        self.withdraw()

    # ── Style overrides ────────────────────────────────────────────────
    def _apply_styles(self):
        s = ttk.Style(self)

        # Section header label
        s.configure("Header.TLabel",
                     font=_FONT_HEADER,
                     foreground=self._accent)

        # Muted / hint label
        s.configure("Muted.TLabel",
                     font=_FONT_SMALL,
                     foreground=self._muted_fg)

        # Status labels
        s.configure("Green.TLabel",  foreground=_GREEN, font=_FONT_BOLD)
        s.configure("Red.TLabel",    foreground=_RED,   font=_FONT_BOLD)
        s.configure("Accent.TLabel", foreground=self._accent, font=_FONT_BOLD)

        # Card-embedded widgets — match card background
        fg = self._text_fg
        bg = self._card_bg
        s.configure("Card.TRadiobutton", background=bg, foreground=fg, font=_FONT)
        s.configure("Card.TCheckbutton", background=bg, foreground=fg, font=_FONT)
        s.configure("Card.TFrame",       background=bg)
        s.map("Card.TRadiobutton",
              background=[("active", bg), ("focus", bg), ("disabled", bg)])
        s.map("Card.TCheckbutton",
              background=[("active", bg), ("focus", bg), ("disabled", bg)])

        # Notebook tabs: kompaktes Padding damit alle 6 Tabs passen
        s.configure("TNotebook.Tab",
                     font=("Segoe UI Variable Text", 9),
                     padding=[8, 2])

        # Entry fields: always use input_bg (white in light mode)
        s.configure("TEntry",
                     fieldbackground=self._input_bg,
                     foreground=self._text_fg,
                     insertcolor=self._text_fg)

    # ── show / hide ────────────────────────────────────────────────────
    def show(self, config: Config, on_save: Callable, on_close: Callable):
        self._config  = config
        self._on_save = on_save
        self._on_close = on_close
        self._is_visible = True
        self._reload_values()
        self.deiconify()
        self.lift()
        self.focus_force()

    # ── UI construction ────────────────────────────────────────────────
    def _build_ui(self):
        # Top title bar area
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(14, 0))
        ttk.Label(header, text="⚡ Blitztext",
                  font=("Segoe UI Variable Display", 16, "bold"),
                  foreground=self._accent).pack(side="left")
        ttk.Label(header, text="Einstellungen",
                  font=("Segoe UI Variable Display", 16),
                  ).pack(side="left", padx=(6, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(10, 0))

        # ── Buttons ZUERST packen (side=bottom) → bleiben immer sichtbar
        bottom_sep = ttk.Separator(self, orient="horizontal")
        bottom_sep.pack(side="bottom", fill="x", padx=16)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", padx=16, pady=10)
        ttk.Button(btn_frame, text="Speichern",
                   command=self._save).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self._cancel).pack(side="right")

        # ── Notebook füllt den Rest
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._tabs: dict[str, ttk.Frame] = {}
        for name in ["Allgemein", "Hotkeys", "Modi", "Snippets", "Eigennamen", "Feedback"]:
            frame = ttk.Frame(self._notebook)
            self._notebook.add(frame, text=name)
            self._tabs[name] = frame

        self._build_general(self._tabs["Allgemein"])
        self._build_hotkeys(self._tabs["Hotkeys"])
        self._build_modes(self._tabs["Modi"])
        self._build_snippets(self._tabs["Snippets"])
        self._build_nouns(self._tabs["Eigennamen"])
        self._build_feedback(self._tabs["Feedback"])

    # ── Allgemein ──────────────────────────────────────────────────────
    def _build_general(self, parent):
        frm = _plain(parent)

        # API Key card
        with _card(frm, self._card_bg) as card:
            _header(card, "API Key", self._card_bg, self._accent)
            tk.Label(card, text="OpenAI (sk-…) oder Groq (gsk_…)",
                     bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL).pack(anchor="w", pady=(0, 6))
            key_row = tk.Frame(card, bg=self._card_bg)
            key_row.pack(fill="x")
            self._api_key_var = tk.StringVar()
            self._api_key_entry = ttk.Entry(
                key_row, textvariable=self._api_key_var, show="●", font=_FONT)
            self._api_key_entry.pack(side="left", fill="x", expand=True)
            ttk.Button(key_row, text="Anzeigen", width=9,
                       command=self._toggle_key_visibility).pack(side="left", padx=(8, 0))

        # Sprache card
        with _card(frm, self._card_bg) as card:
            _header(card, "Whisper-Sprache", self._card_bg, self._accent)
            tk.Label(card, text="Sprachcode für Transkription — 'auto' erkennt automatisch.",
                     bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL).pack(anchor="w", pady=(0, 6))
            self._lang_var = tk.StringVar()
            ttk.Combobox(card, textvariable=self._lang_var,
                         values=_LANGUAGES, width=14, state="readonly",
                         font=_FONT).pack(anchor="w")

        # Aufnahme card
        with _card(frm, self._card_bg) as card:
            _header(card, "Aufnahme-Modus", self._card_bg, self._accent)
            self._record_mode_var = tk.StringVar(value="hold")
            tk.Radiobutton(card, text="Halten  —  Taste gedrückt halten",
                           variable=self._record_mode_var, value="hold",
                           bg=self._card_bg, fg=self._text_fg, font=_FONT,
                           activebackground=self._card_bg, activeforeground=self._text_fg,
                           selectcolor=self._card_bg).pack(anchor="w")
            tk.Radiobutton(card, text="Umschalten  —  1× drücken = start, 1× = stop",
                           variable=self._record_mode_var, value="toggle",
                           bg=self._card_bg, fg=self._text_fg, font=_FONT,
                           activebackground=self._card_bg, activeforeground=self._text_fg,
                           selectcolor=self._card_bg).pack(anchor="w", pady=(4, 0))

        # Transkription card
        with _card(frm, self._card_bg) as card:
            _header(card, "Transkriptions-Modus", self._card_bg, self._accent)
            self._transcription_mode_var = tk.StringVar(value="online")
            self._transcription_mode_var.trace_add("write", self._on_transcription_mode_change)
            tk.Radiobutton(card,
                           text="🌐  Online  —  OpenAI / Groq API",
                           variable=self._transcription_mode_var,
                           value="online",
                           bg=self._card_bg, fg=self._text_fg, font=_FONT,
                           activebackground=self._card_bg, activeforeground=self._text_fg,
                           selectcolor=self._card_bg).pack(anchor="w")
            tk.Radiobutton(card,
                           text="💻  Lokal   —  Whisper Small (~463 MB), kein API-Key nötig",
                           variable=self._transcription_mode_var,
                           value="local",
                           bg=self._card_bg, fg=self._text_fg, font=_FONT,
                           activebackground=self._card_bg, activeforeground=self._text_fg,
                           selectcolor=self._card_bg).pack(anchor="w", pady=(4, 8))

            path_row = tk.Frame(card, bg=self._card_bg)
            path_row.pack(fill="x")
            tk.Label(path_row, text="Modelldatei",
                     bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL,
                     width=11, anchor="w").pack(side="left")
            ttk.Button(path_row, text="…", width=3,
                       command=self._browse_model_file).pack(side="right")
            self._model_path_var = tk.StringVar()
            self._model_path_var.trace_add("write", lambda *_: self._update_model_status())
            ttk.Entry(path_row, textvariable=self._model_path_var,
                      font=_FONT_MONO).pack(side="left", fill="x", expand=True, padx=(8, 6))

            self._model_status_lbl = tk.Label(card, text="—",
                                              bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL)
            self._model_status_lbl.pack(anchor="w", pady=(6, 0))
            self._model_load_gen = 0  # invalidiert veraltete Timer/Threads bei neuem Load

        # Autostart card
        with _card(frm, self._card_bg) as card:
            _header(card, "Autostart", self._card_bg, self._accent)
            self._autostart_var = tk.BooleanVar()
            tk.Checkbutton(card, text="Blitztext beim Windows-Start automatisch öffnen",
                           variable=self._autostart_var,
                           bg=self._card_bg, fg=self._text_fg, font=_FONT,
                           activebackground=self._card_bg, activeforeground=self._text_fg,
                           selectcolor=self._card_bg).pack(anchor="w")

    def _toggle_key_visibility(self):
        self._api_key_entry.configure(
            show="" if self._api_key_entry.cget("show") else "●"
        )

    def _on_transcription_mode_change(self, *_):
        if self._transcription_mode_var.get() == "local":
            # Nur laden wenn explizit ein Pfad gesetzt — sonst nur Status prüfen
            if self._model_path_var.get().strip():
                self._load_local_model_async()
            else:
                self._update_model_status()
        else:
            self._model_status_lbl.configure(text="—", fg=self._muted_fg, font=_FONT_SMALL)

    def _browse_model_file(self):
        from tkinter import filedialog
        current = self._model_path_var.get().strip()
        initial = str(Path(current).parent) if current else _DEFAULT_MODEL_DIR
        path = filedialog.askopenfilename(
            title="Whisper model.bin auswählen",
            initialdir=initial,
            filetypes=[("Whisper-Modell", "model.bin"), ("Alle Dateien", "*.*")],
            parent=self,
        )
        if path:
            self._model_path_var.set(path)
            self._load_local_model_async()

    def _load_local_model_async(self):
        model_path = self._model_path_var.get().strip() or None
        if is_local_model_loaded():
            self._model_status_lbl.configure(text="✓ Modell bereit", fg=_GREEN, font=_FONT_BOLD)
            return

        self._model_load_gen += 1
        gen = self._model_load_gen

        self._model_status_lbl.configure(text="⏳ wird geladen…", fg=self._accent, font=_FONT_BOLD)

        def _on_progress(downloaded: int, total: int):
            if self._model_load_gen != gen:
                return
            dl_mb = downloaded / 1_048_576
            tot_mb = total / 1_048_576
            pct = int(downloaded / total * 100) if total else 0
            text = f"⏳ {dl_mb:.0f} MB / {tot_mb:.0f} MB  ({pct}%)"
            self.after(0, lambda t=text: self._model_status_lbl.configure(text=t))

        def _do():
            try:
                load_local_model(model_path, on_progress=_on_progress)
                if self._model_load_gen == gen:
                    self.after(0, lambda: self._model_status_lbl.configure(
                        text="✓ Modell bereit", fg=_GREEN, font=_FONT_BOLD))
            except Exception as e:
                msg = str(e)
                if self._model_load_gen == gen:
                    self.after(0, lambda m=msg: self._model_status_lbl.configure(
                        text=f"✕ Fehler: {m}", fg=_RED, font=_FONT_BOLD))

        threading.Thread(target=_do, daemon=True, name="model-load").start()

    def _update_model_status(self):
        current = self._model_status_lbl.cget("text")
        # Endzustände nicht überschreiben
        if current.startswith("⏳") or current == "✓ Modell bereit" or current.startswith("✕ Fehler:"):
            return
        if is_local_model_loaded():
            self._model_status_lbl.configure(text="✓ Modell bereit", fg=_GREEN, font=_FONT_BOLD)
            return
        if self._transcription_mode_var.get() != "local":
            return

        model_path = self._model_path_var.get().strip() or None

        def _check():
            on_disk = is_model_on_disk(model_path)
            if on_disk:
                self.after(0, lambda: self._model_status_lbl.configure(
                    text="○ Vorhanden, nicht geladen", fg=self._muted_fg, font=_FONT_SMALL))
            else:
                self.after(0, lambda: self._model_status_lbl.configure(
                    text="✕ Fehlt  (~463 MB, wird beim ersten Start heruntergeladen)",
                    fg=_RED, font=_FONT_BOLD))

        threading.Thread(target=_check, daemon=True, name="model-status-check").start()

    # ── Hotkeys ────────────────────────────────────────────────────────
    def _build_hotkeys(self, parent):
        frm = _plain(parent)
        self._hotkey_vars: dict[str, tk.StringVar] = {}
        icons = {"normal": "🎙", "plus": "📝", "rage": "😤", "emoji": "😊"}

        with _card(frm, self._card_bg) as card:
            _header(card, "Hotkeys", self._card_bg, self._accent)
            tk.Label(
                card,
                text="Drücke 'Aufnehmen' und halte dann die Tastenkombination.\n"
                     "Tipp: Rechte Sondertasten (Right Ctrl, Right Alt, Right Shift) "
                     "kollidieren selten mit anderen Apps.",
                bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL,
                wraplength=540, justify="left",
            ).pack(anchor="w", pady=(0, 10))

            for mode in _MODES:
                var = tk.StringVar()
                self._hotkey_vars[mode] = var

                row = tk.Frame(card, bg=self._card_bg)
                row.pack(fill="x", pady=3)

                tk.Label(row,
                         text=f"{icons[mode]}  {_MODE_LABELS[mode]}",
                         font=_FONT_BOLD, bg=self._card_bg, fg=self._text_fg,
                         width=16, anchor="w").pack(side="left")
                ttk.Entry(row, textvariable=var, width=22,
                          state="readonly", font=_FONT_MONO
                          ).pack(side="left", padx=(0, 6))
                ttk.Button(row, text="Aufnehmen", width=10,
                           command=lambda m=mode: self._capture_hotkey(m)
                           ).pack(side="left")
                ttk.Button(row, text="Löschen", width=7,
                           command=lambda m=mode: self._hotkey_vars[m].set("")
                           ).pack(side="left", padx=(6, 0))

    def _capture_hotkey(self, mode: str):
        dialog = tk.Toplevel(self)
        dialog.title("Hotkey aufnehmen")
        dialog.geometry("340x130")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self)

        ttk.Label(dialog,
                  text=f"Hotkey für Modus »{_MODE_LABELS[mode]}«",
                  font=_FONT_BOLD).pack(padx=20, pady=(18, 4))
        ttk.Label(dialog,
                  text="Halte jetzt die gewünschte Tastenkombination…",
                  style="Muted.TLabel").pack(padx=20)
        status_lbl = ttk.Label(dialog, text="",
                               font=_FONT_MONO, foreground=self._accent)
        status_lbl.pack(pady=8)

        captured: dict[str, frozenset] = {"keys": frozenset()}

        def on_press(key):
            captured["keys"] = captured["keys"] | {key}
            dialog.after(0, lambda: status_lbl.configure(
                text=hotkey_to_str(captured["keys"])))

        def on_release(key):
            if captured["keys"]:
                self._hotkey_vars[mode].set(hotkey_to_str(captured["keys"]))
                listener.stop()
                dialog.after(0, dialog.destroy)

        listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        dialog.wait_window()

    # ── Modi ───────────────────────────────────────────────────────────
    def _build_modes(self, parent):
        frm = _plain(parent)
        descs = {
            "plus":  "Formuliert gesprochenen Text schriftlicher um.",
            "rage":  "Wandelt wütenden Text in eine höfliche Nachricht.",
            "emoji": "Fügt passende Emojis in den Text ein.",
        }
        boxes = {}
        for key in ("plus", "rage", "emoji"):
            with _card(frm, self._card_bg) as card:
                _header(card, f"{_MODE_LABELS[key]}-Modus", self._card_bg, self._accent)
                tk.Label(card, text=descs[key],
                         bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL).pack(anchor="w", pady=(0, 6))
                boxes[key] = _textbox(card, height=3, font=_FONT,
                                      bg=self._card_bg, fg=self._text_fg)

        self._plus_prompt  = boxes["plus"]
        self._rage_prompt  = boxes["rage"]
        self._emoji_prompt = boxes["emoji"]

        with _card(frm, self._card_bg) as card:
            _header(card, "Emoji-Dichte", self._card_bg, self._accent)
            tk.Label(card,
                     text="Wie viele Emojis sollen eingefügt werden?",
                     bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL).pack(anchor="w", pady=(0, 8))
            slider_row = tk.Frame(card, bg=self._card_bg)
            slider_row.pack(fill="x")
            tk.Label(slider_row, text="Wenige", bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL).pack(side="left")
            self._emoji_density_var = tk.IntVar(value=5)
            self._density_lbl = tk.Label(slider_row, text="5",
                                         bg=self._card_bg, fg=self._accent, font=_FONT_BOLD, width=3)
            self._density_lbl.pack(side="right")
            tk.Label(slider_row, text="Viele",
                     bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL).pack(side="right", padx=(0, 8))
            tk.Scale(slider_row, from_=1, to=10, orient="horizontal",
                     variable=self._emoji_density_var,
                     bg=self._card_bg, fg=self._text_fg,
                     highlightthickness=0, troughcolor=self._muted_fg,
                     activebackground=self._accent, sliderrelief="flat",
                     width=12, sliderlength=28, showvalue=0,
                     command=lambda v: self._density_lbl.configure(
                         text=str(int(float(v))))).pack(
                side="left", fill="x", expand=True, padx=8)

    # ── Snippets ───────────────────────────────────────────────────────
    def _build_snippets(self, parent):
        outer = _scrollable(parent)

        with _card(outer, self._card_bg) as card:
            _header(card, "Snippets", self._card_bg, self._accent)
            tk.Label(
                card,
                text="Sprich ein Keyword — es wird automatisch durch den definierten Text ersetzt.\n"
                     "Groß-/Kleinschreibung wird ignoriert.",
                bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL,
                wraplength=540, justify="left",
            ).pack(anchor="w", pady=(0, 10))

            # Header-Zeile
            hdr = tk.Frame(card, bg=self._card_bg)
            hdr.pack(fill="x", pady=(0, 4))
            tk.Label(hdr, text="Keyword",    font=_FONT_BOLD, bg=self._card_bg, fg=self._text_fg, width=20, anchor="w").pack(side="left")
            tk.Label(hdr, text="Ersatztext", font=_FONT_BOLD, bg=self._card_bg, fg=self._text_fg, anchor="w").pack(side="left", padx=(8, 0))

            # Container für die Snippet-Zeilen
            self._snippets_frame = tk.Frame(card, bg=self._card_bg)
            self._snippets_frame.pack(fill="x")
            self._snippet_rows: list[tuple[tk.StringVar, tk.StringVar]] = []

            ttk.Button(
                card, text="+ Snippet hinzufügen",
                command=self._add_snippet_row,
            ).pack(anchor="w", pady=(10, 0))

    def _add_snippet_row(self, keyword: str = "", text: str = ""):
        kw_var  = tk.StringVar(master=self, value=keyword)
        txt_var = tk.StringVar(master=self, value=text)
        self._snippet_rows.append((kw_var, txt_var))

        frm = tk.Frame(self._snippets_frame, bg=self._card_bg)
        frm.pack(fill="x", pady=3)

        ttk.Entry(frm, textvariable=kw_var,  width=20, font=_FONT).pack(side="left")
        ttk.Entry(frm, textvariable=txt_var, font=_FONT).pack(
            side="left", fill="x", expand=True, padx=(8, 8))

        def _delete(f=frm, pair=(kw_var, txt_var)):
            if pair in self._snippet_rows:
                self._snippet_rows.remove(pair)
            f.destroy()

        ttk.Button(frm, text="✕", width=3, command=_delete).pack(side="left")

    # ── Eigennamen ─────────────────────────────────────────────────────
    def _build_nouns(self, parent):
        outer = _scrollable(parent)
        _sep = "#333333" if self._dark else "#DDDDDD"
        with _card(outer, self._card_bg) as card:
            _header(card, "Eigennamen", self._card_bg, self._accent)
            tk.Label(card,
                     text="Helfen Whisper, Markennamen, Personen und Fachbegriffe "
                          "korrekt zu erkennen.",
                     bg=self._card_bg, fg=self._muted_fg, font=_FONT_SMALL,
                     wraplength=540, justify="left",
                     ).pack(anchor="w", pady=(0, 6))

            # ── List area ──────────────────────────────────────────
            list_border = tk.Frame(card, bg=_sep)
            list_border.pack(fill="x", pady=(0, 8))
            list_inner = tk.Frame(list_border, bg=self._input_bg)
            list_inner.pack(fill="both", expand=True, padx=1, pady=1)
            self._nouns_list_frame = list_inner

            # ── Buttons ────────────────────────────────────────────
            btn_row = tk.Frame(card, bg=self._card_bg)
            btn_row.pack(fill="x")
            ttk.Button(btn_row, text="+ Hinzufügen",
                       command=self._add_noun_entry).pack(side="left")
            self._noun_del_btn = ttk.Button(
                btn_row, text="✕ Löschen",
                command=self._delete_selected_nouns, state="disabled")
            self._noun_del_btn.pack(side="left", padx=(6, 0))

            # ── Internal state ─────────────────────────────────────
            self._noun_items:    list[str]      = []
            self._noun_selected: set[int]       = set()
            self._noun_frames:   list[tk.Frame] = []
            self._noun_adding    = False

    def _rebuild_noun_list(self):
        for f in self._noun_frames:
            try:
                f.destroy()
            except Exception:
                pass
        self._noun_frames.clear()
        self._noun_selected.clear()
        self._noun_adding = False
        self._noun_del_btn.configure(state="disabled", text="✕ Löschen")
        for i, noun in enumerate(self._noun_items):
            self._append_noun_label(i, noun)

    def _append_noun_label(self, index: int, noun: str):
        sel_bg  = self._accent
        sel_fg  = "#000000" if self._dark else "#FFFFFF"
        norm_bg = self._input_bg
        norm_fg = self._text_fg

        row = tk.Frame(self._nouns_list_frame, bg=norm_bg, cursor="hand2")
        row.pack(fill="x", pady=(0, 1))
        lbl = tk.Label(row, text=noun, font=_FONT_MONO,
                       bg=norm_bg, fg=norm_fg, anchor="w", padx=10, pady=5)
        lbl.pack(fill="x")
        self._noun_frames.append(row)

        def _toggle(event, i=index, r=row, l=lbl):
            if i in self._noun_selected:
                self._noun_selected.discard(i)
                r.configure(bg=norm_bg)
                l.configure(bg=norm_bg, fg=norm_fg)
            else:
                self._noun_selected.add(i)
                r.configure(bg=sel_bg)
                l.configure(bg=sel_bg, fg=sel_fg)
            count = len(self._noun_selected)
            self._noun_del_btn.configure(
                state="normal" if count else "disabled",
                text=f"✕ Löschen ({count})" if count else "✕ Löschen",
            )

        row.bind("<Button-1>", _toggle)
        lbl.bind("<Button-1>", _toggle)

    def _delete_selected_nouns(self):
        self._noun_items = [
            n for i, n in enumerate(self._noun_items)
            if i not in self._noun_selected
        ]
        self._rebuild_noun_list()

    def _add_noun_entry(self):
        if self._noun_adding:
            return
        self._noun_adding = True
        row = tk.Frame(self._nouns_list_frame, bg=self._input_bg)
        row.pack(fill="x", pady=(0, 1))
        self._noun_frames.append(row)

        var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=var, font=_FONT_MONO)
        entry.pack(fill="x", padx=4, pady=3)
        entry.focus_set()

        committed = [False]

        def _commit(event=None):
            if committed[0]:
                return
            committed[0] = True
            text = var.get().strip()

            def _do():
                try:
                    row.destroy()
                except Exception:
                    pass
                if text:
                    self._noun_items.append(text)
                self._rebuild_noun_list()

            self.after(1, _do)

        entry.bind("<Return>", _commit)
        entry.bind("<FocusOut>", _commit)

    # ── Feedback ───────────────────────────────────────────────────────
    def _build_feedback(self, parent):
        frm = _scrollable(parent)
        bg = self._input_bg

        # API Status card
        with _card(frm, bg) as card:
            _header(card, "API-Status", bg, self._accent)
            grid = tk.Frame(card, bg=bg)
            grid.pack(fill="x")
            _row_label(grid, "Anbieter", 0, bg=bg, fg=self._muted_fg)
            self._fb_provider = tk.Label(grid, text="—", font=_FONT_BOLD, bg=bg, fg=self._text_fg)
            self._fb_provider.grid(row=0, column=1, sticky="w", padx=10, pady=3)

            _row_label(grid, "API-Key", 1, bg=bg, fg=self._muted_fg)
            self._fb_key_status = tk.Label(grid, text="—", bg=bg, fg=self._text_fg, font=_FONT)
            self._fb_key_status.grid(row=1, column=1, sticky="w", padx=10, pady=3)

            _row_label(grid, "Hotkeys", 2, bg=bg, fg=self._muted_fg)
            self._fb_hotkeys_lbl = tk.Label(grid, text="—",
                                             font=_FONT_MONO, bg=bg, fg=self._text_fg, wraplength=380)
            self._fb_hotkeys_lbl.grid(row=2, column=1, sticky="w", padx=10, pady=3)

        # Letztes Ergebnis card
        with _card(frm, bg) as card:
            _header(card, "Letztes Ergebnis", bg, self._accent)
            res = tk.Frame(card, bg=bg)
            res.pack(fill="x")
            for i, (label, attr) in enumerate([
                ("Transkript", "_fb_transcript"),
                ("Ausgabe",    "_fb_output"),
                ("Fehler",     "_fb_error"),
            ]):
                _row_label(res, label, i, bg=bg, fg=self._muted_fg)
                lbl = tk.Label(res, text="—", wraplength=380, justify="left",
                               bg=bg, fg=self._text_fg, font=_FONT)
                lbl.grid(row=i, column=1, sticky="w", padx=10, pady=3)
                setattr(self, attr, lbl)

        # Umgebung card
        with _card(frm, bg) as card:
            _header(card, "Umgebung", bg, self._accent)
            env = tk.Frame(card, bg=bg)
            env.pack(fill="x")
            for i, (k, v) in enumerate(self._collect_env()):
                tk.Label(env, text=k, bg=bg, fg=self._muted_fg, font=_FONT_SMALL,
                         width=14, anchor="w").grid(row=i, column=0, sticky="w", padx=0, pady=2)
                tk.Label(env, text=v, font=_FONT_MONO, bg=bg, fg=self._text_fg).grid(
                    row=i, column=1, sticky="w", padx=10, pady=2)

        # Log card
        with _card(frm, bg) as card:
            _header(card, "Ereignis-Log", bg, self._accent)
            self._fb_log = _textbox(card, height=6, font=_FONT_MONO, state="disabled",
                                   bg=bg, fg=self._text_fg)
            btn_row = tk.Frame(card, bg=bg)
            btn_row.pack(fill="x", pady=(4, 0))
            ttk.Button(btn_row, text="Aktualisieren",
                       command=self._refresh_feedback).pack(side="left")
            ttk.Button(btn_row, text="Log leeren",
                       command=self._clear_log).pack(side="left", padx=(6, 0))

        self._schedule_feedback_refresh()

    def _collect_env(self) -> list[tuple[str, str]]:
        rows = [
            ("Python",   sys.version.split()[0]),
            ("Platform", platform.platform(terse=True)),
        ]
        for pkg in ("openai", "groq", "sounddevice", "pynput"):
            try:
                import importlib.metadata
                rows.append((pkg, importlib.metadata.version(pkg)))
            except Exception:
                rows.append((pkg, "—"))
        try:
            import sounddevice as sd
            dev = sd.query_devices(sd.default.device[0], "input")
            rows.append(("Mikrofon", dev["name"][:40]))
        except Exception:
            rows.append(("Mikrofon", "nicht erkannt"))
        return rows

    def _refresh_feedback(self):
        cfg = self._config
        if cfg is None:
            return

        self._fb_provider.configure(text=detect_provider(cfg.api_key, cfg.use_local_whisper))
        self._update_model_status()

        if cfg.api_key:
            masked = (cfg.api_key[:6] + "…" + cfg.api_key[-4:]
                      if len(cfg.api_key) > 10 else "gesetzt")
            self._fb_key_status.configure(text=f"✓  {masked}", style="Green.TLabel")
        else:
            self._fb_key_status.configure(
                text="✕  Nicht gesetzt", style="Red.TLabel")

        hk = "   ".join(f"{_MODE_LABELS[m]}: {cfg.get_hotkey(m) or '—'}" for m in _MODES)
        self._fb_hotkeys_lbl.configure(text=hk)

        t   = applog.last_transcript or "—"
        o   = applog.last_processed  or "—"
        err = applog.last_error      or "—"
        self._fb_transcript.configure(text=(t[:120] + "…") if len(t) > 120 else t)
        self._fb_output.configure(    text=(o[:120] + "…") if len(o) > 120 else o)
        self._fb_error.configure(
            text=(err[:120] + "…") if len(err) > 120 else err,
            foreground=_RED if applog.last_error else "")

        entries = applog.get_all()
        self._fb_log.configure(state="normal")
        self._fb_log.delete("1.0", "end")
        self._fb_log.insert("1.0", "\n".join(reversed(entries)))
        self._fb_log.configure(state="disabled")

    def _clear_log(self):
        applog._entries.clear()
        self._refresh_feedback()

    def _schedule_feedback_refresh(self):
        try:
            if getattr(self, "_is_visible", False):
                self._refresh_feedback()
            self.after(2000, self._schedule_feedback_refresh)
        except Exception:
            pass

    # ── Load / Reload ──────────────────────────────────────────────────
    def _reload_values(self):
        cfg = self._config
        self._api_key_var.set(cfg.api_key)
        self._lang_var.set(cfg.whisper_language)
        self._record_mode_var.set(cfg.record_mode)
        self._autostart_var.set(cfg.autostart)
        self._transcription_mode_var.set("local" if cfg.use_local_whisper else "online")
        self._model_path_var.set(cfg.whisper_model_path)

        for mode in _MODES:
            self._hotkey_vars[mode].set(cfg.get_hotkey(mode))

        for box, key in [
            (self._plus_prompt,  "plus"),
            (self._rage_prompt,  "rage"),
            (self._emoji_prompt, "emoji"),
        ]:
            box.delete("1.0", "end")
            box.insert("1.0", cfg.get_prompt(key))

        self._emoji_density_var.set(cfg.emoji_density)
        self._density_lbl.configure(text=str(cfg.emoji_density))

        self._noun_items = list(cfg.proper_nouns)
        self._rebuild_noun_list()

        # Snippets neu aufbauen
        for w in self._snippets_frame.winfo_children():
            w.destroy()
        self._snippet_rows.clear()
        for s in cfg.snippets:
            self._add_snippet_row(s.get("keyword", ""), s.get("text", ""))

    # ── Save / Cancel ──────────────────────────────────────────────────
    def _save(self):
        cfg = self._config
        cfg.api_key          = self._api_key_var.get().strip()
        cfg.whisper_language = self._lang_var.get()
        cfg.record_mode      = self._record_mode_var.get()
        cfg.autostart           = self._autostart_var.get()
        cfg.use_local_whisper   = self._transcription_mode_var.get() == "local"
        cfg.whisper_model_path  = self._model_path_var.get().strip()

        for mode in _MODES:
            cfg.set_hotkey(mode, self._hotkey_vars[mode].get())

        cfg.set_prompt("plus",  self._plus_prompt.get("1.0", "end").strip())
        cfg.set_prompt("rage",  self._rage_prompt.get("1.0", "end").strip())
        cfg.set_prompt("emoji", self._emoji_prompt.get("1.0", "end").strip())
        cfg.emoji_density = self._emoji_density_var.get()

        cfg.proper_nouns = [n for n in self._noun_items if n.strip()]

        cfg.snippets = [
            {"keyword": kw.get().strip(), "text": tx.get().strip()}
            for kw, tx in self._snippet_rows
            if kw.get().strip()
        ]

        try:
            cfg.save()
        except Exception as e:
            print(f"[Fehler] config.save(): {e}")

        try:
            self._on_save(cfg)
        except Exception as e:
            print(f"[Fehler] on_save callback: {e}")

        try:
            self._apply_autostart(cfg.autostart)
        except Exception as e:
            print(f"[Fehler] autostart: {e}")

        self._close()

    def _cancel(self):
        self._close()

    def _close(self):
        self._is_visible = False
        self.withdraw()
        if self._on_close:
            self._on_close()

    @staticmethod
    def _apply_autostart(enable: bool):
        import winreg
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        # Portable: use the actual executable path (frozen EXE or pythonw script)
        if getattr(sys, "frozen", False):
            # Frozen build: just the EXE path
            app_cmd = f'"{sys.executable}"'
        else:
            # Dev mode: pythonw + script
            _candidate = Path(sys.executable).parent / "pythonw.exe"
            pythonw = str(_candidate if _candidate.exists() else Path(sys.executable))
            app = str(Path(__file__).resolve().parent.parent / "blitztext.pyw")
            app_cmd = f'"{pythonw}" "{app}"'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0,
                            winreg.KEY_WRITE) as key:
            if enable:
                winreg.SetValueEx(key, "Blitztext", 0, winreg.REG_SZ, app_cmd)
                print(f"[Autostart] aktiviert: {app_cmd}")
            else:
                try:
                    winreg.DeleteValue(key, "Blitztext")
                    print("[Autostart] deaktiviert")
                except FileNotFoundError:
                    pass


# ── Layout helpers ─────────────────────────────────────────────────────

class _card:
    """Context manager that creates a card-style frame with padding."""
    def __init__(self, parent, bg: str, expand: bool = False):
        self._frame = tk.Frame(parent, bg=bg, padx=10, pady=7)
        self._frame.pack(fill="both" if expand else "x",
                         expand=expand, padx=4, pady=(0, 5))

    def __enter__(self) -> tk.Frame:
        return self._frame

    def __exit__(self, *_):
        pass


def _scrollable(parent: ttk.Frame) -> ttk.Frame:
    """Canvas + Scrollbar; returns inner frame. Scrollbar only visible when needed."""
    outer = ttk.Frame(parent)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(0, weight=1)

    vsb    = ttk.Scrollbar(outer, orient="vertical")
    canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0,
                       yscrollcommand=vsb.set)
    vsb.configure(command=canvas.yview)
    inner  = ttk.Frame(canvas)

    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    # Stretch inner frame to full canvas width
    def _on_canvas_resize(e):
        canvas.itemconfig(win_id, width=e.width)

    # Update scroll region when content changes
    def _on_inner_resize(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
        # Show/hide scrollbar based on whether content overflows
        if inner.winfo_reqheight() > canvas.winfo_height():
            vsb.grid(row=0, column=1, sticky="ns")
        else:
            vsb.grid_remove()

    canvas.bind("<Configure>", _on_canvas_resize)
    inner.bind("<Configure>", _on_inner_resize)

    def _wheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
    return inner


def _plain(parent: ttk.Frame) -> ttk.Frame:
    """Simple frame without scrollbar — for tabs whose content always fits."""
    frm = ttk.Frame(parent)
    frm.pack(fill="both", expand=True, padx=8, pady=4)
    return frm


def _header(parent, text: str, bg: str = _CARD_DARK, fg: str = _DARK_ACCENT):
    tk.Label(parent, text=text, font=_FONT_HEADER, bg=bg, fg=fg).pack(
        anchor="w", pady=(0, 4))


def _row_label(parent, text: str, row: int, bg: str = _CARD_DARK, fg: str = _MUTED):
    tk.Label(parent, text=text, bg=bg, fg=fg, font=_FONT_SMALL,
             width=13, anchor="w").grid(row=row, column=0, sticky="nw", pady=3)


def _textbox(parent, height: int = 5, font=_FONT, state: str = "normal",
             expand: bool = False, bg: str = _CARD_DARK, fg: str = "#FFFFFF") -> tk.Text:
    frame = tk.Frame(parent, bg=bg)
    frame.pack(fill="both" if expand else "x", expand=expand, pady=(0, 4))
    text = tk.Text(frame, height=height, font=font, wrap="word",
                   relief="flat", borderwidth=0, state=state,
                   bg=bg, fg=fg, insertbackground=fg,
                   padx=6, pady=4)
    vsb  = ttk.Scrollbar(frame, orient="vertical", command=text.yview)

    def _set(first, last):
        # Only show scrollbar when content actually overflows
        if float(first) <= 0.0 and float(last) >= 1.0:
            vsb.pack_forget()
        else:
            vsb.pack(side="right", fill="y")
        vsb.set(first, last)

    text.configure(yscrollcommand=_set)
    text.pack(side="left", fill="both", expand=True)
    return text


# ── Dauerhafter UI-Thread ──────────────────────────────────────────────

_ui_queue:  queue.Queue             = queue.Queue()
_ui_ready:  threading.Event         = threading.Event()
_ui_thread: threading.Thread | None = None


def _ui_worker():
    try:
        win = SettingsWindow()
    except Exception as e:
        print(f"[Fehler] SettingsWindow konnte nicht erstellt werden: {e}")
        _ui_ready.set()   # Blocker freigeben damit open_settings_window nicht hängt
        return

    _ui_ready.set()

    def _poll():
        try:
            config, on_save, done = _ui_queue.get_nowait()
            win.show(config, on_save, on_close=done.set)
        except queue.Empty:
            pass
        try:
            win.after(100, _poll)
        except Exception:
            pass

    win.after(0, _poll)
    win.mainloop()


def open_settings_window(config: Config, on_save: Callable[[Config], None]):
    """Zeigt das Einstellungsfenster und blockiert bis es geschlossen wird."""
    global _ui_thread
    if _ui_thread is None or not _ui_thread.is_alive():
        _ui_ready.clear()
        _ui_thread = threading.Thread(target=_ui_worker, daemon=True, name="settings-ui")
        _ui_thread.start()
        _ui_ready.wait()

    if not _ui_thread.is_alive():
        print("[Fehler] Settings-UI-Thread konnte nicht gestartet werden")
        return

    done = threading.Event()
    _ui_queue.put((config, on_save, done))
    done.wait()
