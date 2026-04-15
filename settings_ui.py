"""Settings window — Windows 11 Fluent Design via tkinter/ttk + sv-ttk.

Runs in its own persistent daemon thread. Do NOT call from the main thread
while pystray is blocked there.
"""
from __future__ import annotations

import platform
import queue
import sys
import threading
from typing import Callable

import tkinter as tk
from tkinter import ttk
import sv_ttk
from pynput import keyboard as pynput_kb

import log as applog
from config import Config
from hotkeys import hotkey_to_str, parse_hotkey
from transcriber import detect_provider

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
        self._muted_fg = _MUTED

        self._apply_styles()

        self._config: Config | None = None
        self._on_save:  Callable | None = None
        self._on_close: Callable | None = None

        self.title("Textblitz — Einstellungen")
        self.geometry("640x740")
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

        # Notebook tabs: Windows 11-proportioned (roomier padding vs font)
        s.configure("TNotebook.Tab",
                     font=("Segoe UI Variable Text", 10),
                     padding=[14, 6])

    # ── show / hide ────────────────────────────────────────────────────
    def show(self, config: Config, on_save: Callable, on_close: Callable):
        self._config  = config
        self._on_save = on_save
        self._on_close = on_close
        self._reload_values()
        self.deiconify()
        self.lift()
        self.focus_force()

    # ── UI construction ────────────────────────────────────────────────
    def _build_ui(self):
        # Top title bar area
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(14, 0))
        ttk.Label(header, text="⚡ Textblitz",
                  font=("Segoe UI Variable Display", 16, "bold"),
                  foreground=self._accent).pack(side="left")
        ttk.Label(header, text="Einstellungen",
                  font=("Segoe UI Variable Display", 16),
                  ).pack(side="left", padx=(6, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(10, 0))

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._tabs: dict[str, ttk.Frame] = {}
        for name in ["Allgemein", "Hotkeys", "Modi", "Eigennamen", "Feedback"]:
            frame = ttk.Frame(self._notebook)
            self._notebook.add(frame, text=name)
            self._tabs[name] = frame

        self._build_general(self._tabs["Allgemein"])
        self._build_hotkeys(self._tabs["Hotkeys"])
        self._build_modes(self._tabs["Modi"])
        self._build_nouns(self._tabs["Eigennamen"])
        self._build_feedback(self._tabs["Feedback"])

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=16, pady=10)
        ttk.Button(btn_frame, text="Speichern",
                   command=self._save).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self._cancel).pack(side="right")

    # ── Allgemein ──────────────────────────────────────────────────────
    def _build_general(self, parent):
        frm = _plain(parent)

        # API Key card
        with _card(frm, self._card_bg) as card:
            _header(card, "API Key")
            ttk.Label(card, text="OpenAI (sk-…) oder Groq (gsk_…)",
                      style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
            key_row = ttk.Frame(card)
            key_row.pack(fill="x")
            self._api_key_var = tk.StringVar()
            self._api_key_entry = ttk.Entry(
                key_row, textvariable=self._api_key_var, show="●", font=_FONT)
            self._api_key_entry.pack(side="left", fill="x", expand=True)
            ttk.Button(key_row, text="Anzeigen", width=9,
                       command=self._toggle_key_visibility).pack(side="left", padx=(8, 0))

        # Sprache card
        with _card(frm, self._card_bg) as card:
            _header(card, "Whisper-Sprache")
            ttk.Label(card, text="Sprachcode für Transkription — 'auto' erkennt automatisch.",
                      style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
            self._lang_var = tk.StringVar()
            ttk.Combobox(card, textvariable=self._lang_var,
                         values=_LANGUAGES, width=14, state="readonly",
                         font=_FONT).pack(anchor="w")

        # Aufnahme card
        with _card(frm, self._card_bg) as card:
            _header(card, "Aufnahme-Modus")
            self._record_mode_var = tk.StringVar(value="hold")
            ttk.Radiobutton(card, text="Halten  —  Taste gedrückt halten",
                            variable=self._record_mode_var, value="hold").pack(anchor="w")
            ttk.Radiobutton(card, text="Umschalten  —  1× drücken = start, 1× = stop",
                            variable=self._record_mode_var, value="toggle").pack(anchor="w", pady=(4, 0))

        # Autostart card
        with _card(frm, self._card_bg) as card:
            _header(card, "Autostart")
            self._autostart_var = tk.BooleanVar()
            ttk.Checkbutton(card, text="Textblitz beim Windows-Start automatisch öffnen",
                            variable=self._autostart_var).pack(anchor="w")

    def _toggle_key_visibility(self):
        self._api_key_entry.configure(
            show="" if self._api_key_entry.cget("show") else "●"
        )

    # ── Hotkeys ────────────────────────────────────────────────────────
    def _build_hotkeys(self, parent):
        frm = _plain(parent)

        ttk.Label(frm,
                  text="Drücke 'Aufnehmen' und halte dann die Tastenkombination.\n"
                       "Tipp: Rechte Sondertasten (Right Ctrl, Right Alt, Right Shift) "
                       "kollidieren selten mit anderen Apps.",
                  style="Muted.TLabel", wraplength=550, justify="left",
                  ).pack(anchor="w", padx=4, pady=(4, 12))

        self._hotkey_vars: dict[str, tk.StringVar] = {}
        icons = {"normal": "🎙", "plus": "✏️", "rage": "😤", "emoji": "😊"}

        for mode in _MODES:
            with _card(frm, self._card_bg) as card:
                row = ttk.Frame(card)
                row.pack(fill="x")
                ttk.Label(row,
                          text=f"{icons[mode]}  {_MODE_LABELS[mode]}",
                          font=_FONT_BOLD).pack(side="left")

                var = tk.StringVar()
                self._hotkey_vars[mode] = var

                ttk.Button(row, text="Löschen", width=7,
                           command=lambda m=mode: self._hotkey_vars[m].set("")
                           ).pack(side="right")
                ttk.Button(row, text="Aufnehmen", width=10,
                           command=lambda m=mode: self._capture_hotkey(m)
                           ).pack(side="right", padx=(0, 6))
                ttk.Entry(row, textvariable=var, width=22,
                          state="readonly", font=_FONT_MONO
                          ).pack(side="right", padx=(0, 10))

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
                _header(card, f"{_MODE_LABELS[key]}-Modus")
                ttk.Label(card, text=descs[key],
                          style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
                boxes[key] = _textbox(card, height=4, font=_FONT)

        self._plus_prompt  = boxes["plus"]
        self._rage_prompt  = boxes["rage"]
        self._emoji_prompt = boxes["emoji"]

        with _card(frm, self._card_bg) as card:
            _header(card, "Emoji-Dichte")
            ttk.Label(card,
                      text="Wie viele Emojis sollen eingefügt werden?",
                      style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
            slider_row = ttk.Frame(card)
            slider_row.pack(fill="x")
            ttk.Label(slider_row, text="Wenige", style="Muted.TLabel").pack(side="left")
            self._emoji_density_var = tk.IntVar(value=5)
            self._density_lbl = ttk.Label(slider_row, text="5",
                                          style="Accent.TLabel", width=3)
            self._density_lbl.pack(side="right")
            ttk.Label(slider_row, text="Viele",
                      style="Muted.TLabel").pack(side="right", padx=(0, 8))
            ttk.Scale(slider_row, from_=1, to=10, orient="horizontal",
                      variable=self._emoji_density_var,
                      command=lambda v: self._density_lbl.configure(
                          text=str(int(float(v))))).pack(
                side="left", fill="x", expand=True, padx=8)

    # ── Eigennamen ─────────────────────────────────────────────────────
    def _build_nouns(self, parent):
        frm = _plain(parent)
        with _card(frm, self._card_bg, expand=True) as card:
            _header(card, "Eigennamen")
            ttk.Label(card,
                      text="Helfen Whisper, Markennamen, Personen und Fachbegriffe "
                           "korrekt zu erkennen. Ein Begriff pro Zeile.",
                      style="Muted.TLabel", wraplength=540, justify="left",
                      ).pack(anchor="w", pady=(0, 8))
            self._nouns_box = _textbox(card, height=6, expand=True)

    # ── Feedback ───────────────────────────────────────────────────────
    def _build_feedback(self, parent):
        frm = _plain(parent)

        # API Status card
        with _card(frm, self._card_bg) as card:
            _header(card, "API-Status")
            grid = ttk.Frame(card)
            grid.pack(fill="x")
            _row_label(grid, "Anbieter", 0)
            self._fb_provider = ttk.Label(grid, text="—", font=_FONT_BOLD)
            self._fb_provider.grid(row=0, column=1, sticky="w", padx=10, pady=3)

            _row_label(grid, "API-Key", 1)
            self._fb_key_status = ttk.Label(grid, text="—")
            self._fb_key_status.grid(row=1, column=1, sticky="w", padx=10, pady=3)

            _row_label(grid, "Hotkeys", 2)
            self._fb_hotkeys_lbl = ttk.Label(grid, text="—",
                                              font=_FONT_MONO, wraplength=380)
            self._fb_hotkeys_lbl.grid(row=2, column=1, sticky="w", padx=10, pady=3)

        # Letztes Ergebnis card
        with _card(frm, self._card_bg) as card:
            _header(card, "Letztes Ergebnis")
            res = ttk.Frame(card)
            res.pack(fill="x")
            for i, (label, attr) in enumerate([
                ("Transkript", "_fb_transcript"),
                ("Ausgabe",    "_fb_output"),
                ("Fehler",     "_fb_error"),
            ]):
                _row_label(res, label, i)
                lbl = ttk.Label(res, text="—", wraplength=380, justify="left")
                lbl.grid(row=i, column=1, sticky="w", padx=10, pady=3)
                setattr(self, attr, lbl)

        # Umgebung card
        with _card(frm, self._card_bg) as card:
            _header(card, "Umgebung")
            env = ttk.Frame(card)
            env.pack(fill="x")
            for i, (k, v) in enumerate(self._collect_env()):
                ttk.Label(env, text=k, style="Muted.TLabel",
                          width=14, anchor="w").grid(row=i, column=0, sticky="w", padx=0, pady=2)
                ttk.Label(env, text=v, font=_FONT_MONO).grid(
                    row=i, column=1, sticky="w", padx=10, pady=2)

        # Log card
        with _card(frm, self._card_bg) as card:
            _header(card, "Ereignis-Log")
            self._fb_log = _textbox(card, height=9, font=_FONT_MONO, state="disabled")
            btn_row = ttk.Frame(card)
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

        self._fb_provider.configure(text=detect_provider(cfg.api_key))

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

        self._nouns_box.delete("1.0", "end")
        self._nouns_box.insert("1.0", "\n".join(cfg.proper_nouns))

    # ── Save / Cancel ──────────────────────────────────────────────────
    def _save(self):
        cfg = self._config
        cfg.api_key          = self._api_key_var.get().strip()
        cfg.whisper_language = self._lang_var.get()
        cfg.record_mode      = self._record_mode_var.get()
        cfg.autostart        = self._autostart_var.get()

        for mode in _MODES:
            cfg.set_hotkey(mode, self._hotkey_vars[mode].get())

        cfg.set_prompt("plus",  self._plus_prompt.get("1.0", "end").strip())
        cfg.set_prompt("rage",  self._rage_prompt.get("1.0", "end").strip())
        cfg.set_prompt("emoji", self._emoji_prompt.get("1.0", "end").strip())
        cfg.emoji_density = self._emoji_density_var.get()

        raw = self._nouns_box.get("1.0", "end").strip()
        cfg.proper_nouns = [n.strip() for n in raw.splitlines() if n.strip()]

        cfg.save()
        self._on_save(cfg)
        self._apply_autostart(cfg.autostart)
        self._close()

    def _cancel(self):
        self._close()

    def _close(self):
        self.withdraw()
        if self._on_close:
            self._on_close()

    @staticmethod
    def _apply_autostart(enable: bool):
        try:
            import winreg
            path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                                winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, "Textblitz", 0, winreg.REG_SZ,
                                      f'"{sys.executable}" "{__file__}"')
                else:
                    try:
                        winreg.DeleteValue(key, "Textblitz")
                    except FileNotFoundError:
                        pass
        except Exception:
            pass


# ── Layout helpers ─────────────────────────────────────────────────────

class _card:
    """Context manager that creates a card-style frame with padding."""
    def __init__(self, parent, bg: str, expand: bool = False):
        self._frame = tk.Frame(parent, bg=bg, padx=14, pady=12)
        self._frame.pack(fill="both" if expand else "x",
                         expand=expand, padx=4, pady=(0, 8))

    def __enter__(self) -> tk.Frame:
        return self._frame

    def __exit__(self, *_):
        pass


def _scrollable(parent: ttk.Frame) -> ttk.Frame:
    """Canvas + Scrollbar; returns inner frame. Scrollbar only visible when needed."""
    outer = ttk.Frame(parent)
    outer.pack(fill="both", expand=True)

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
            vsb.pack(side="right", fill="y")
        else:
            vsb.pack_forget()

    canvas.bind("<Configure>", _on_canvas_resize)
    inner.bind("<Configure>", _on_inner_resize)

    def _wheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    canvas.pack(fill="both", expand=True, padx=(8, 0), pady=8)
    return inner


def _plain(parent: ttk.Frame) -> ttk.Frame:
    """Simple frame without scrollbar — for tabs whose content always fits."""
    frm = ttk.Frame(parent)
    frm.pack(fill="both", expand=True, padx=12, pady=8)
    return frm


def _header(parent, text: str):
    ttk.Label(parent, text=text, style="Header.TLabel").pack(
        anchor="w", pady=(0, 6))


def _row_label(parent, text: str, row: int):
    ttk.Label(parent, text=text, style="Muted.TLabel",
              width=13, anchor="w").grid(row=row, column=0, sticky="nw", pady=3)


def _textbox(parent, height: int = 5, font=_FONT, state: str = "normal",
             expand: bool = False) -> tk.Text:
    frame = ttk.Frame(parent)
    frame.pack(fill="both" if expand else "x", expand=expand, pady=(0, 4))
    text = tk.Text(frame, height=height, font=font, wrap="word",
                   relief="flat", borderwidth=0, state=state,
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
    win = SettingsWindow()
    _ui_ready.set()

    def _poll():
        try:
            config, on_save, done = _ui_queue.get_nowait()
            win.show(config, on_save, on_close=done.set)
        except queue.Empty:
            pass
        win.after(100, _poll)

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

    done = threading.Event()
    _ui_queue.put((config, on_save, done))
    done.wait()
