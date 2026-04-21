"""Top-center status overlay — shown while recording or processing."""
from __future__ import annotations

import ctypes
import queue
import threading
import tkinter as tk

_MODE_LABELS = {
    "normal": "🎙  Normal",
    "plus":   "✏️  Plus",
    "rage":   "😤  Rage",
    "emoji":  "😊  Emoji",
}

_BG         = "#1a1a2e"
_FG         = "#ecf0f1"
_RED        = "#e74c3c"
_ORANGE     = "#f39c12"

_cmd_queue: queue.Queue             = queue.Queue()
_thread:    threading.Thread | None = None
_ready:     threading.Event         = threading.Event()


def show_recording(mode: str):
    """Show overlay with pulsing red dot — call when recording starts."""
    _ensure_thread()
    _cmd_queue.put(("show", mode, _RED, True))


def show_processing(mode: str):
    """Switch to static orange dot — call when recording stops and pipeline begins."""
    _ensure_thread()
    _cmd_queue.put(("show", mode, _ORANGE, False))


def hide():
    """Hide the overlay — call when pipeline is done or on error."""
    _ensure_thread()
    _cmd_queue.put(("hide",))


# ── internal ──────────────────────────────────────────────────────────

def _ensure_thread():
    global _thread
    if _thread is None or not _thread.is_alive():
        _ready.clear()
        _thread = threading.Thread(target=_worker, daemon=True, name="status-overlay")
        _thread.start()
        _ready.wait(timeout=2)


def _worker():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.90)
    root.configure(bg=_BG)

    frame = tk.Frame(root, bg=_BG, padx=20, pady=9)
    frame.pack()

    dot_lbl = tk.Label(frame, text="●", bg=_BG, fg=_RED,
                       font=("Segoe UI", 11, "bold"))
    dot_lbl.pack(side="left", padx=(0, 10))

    mode_lbl = tk.Label(frame, text="", bg=_BG, fg=_FG,
                        font=("Segoe UI", 10))
    mode_lbl.pack(side="left")

    root.withdraw()
    _ready.set()

    # state
    _state = {"visible": False, "pulse": True, "dot_color": _RED}

    def _pulse():
        if _state["visible"] and _state["pulse"]:
            _state["dot_color"] = _RED if _state["dot_color"] == _BG else _BG
            dot_lbl.configure(fg=_state["dot_color"])
        root.after(500, _pulse)

    root.after(500, _pulse)

    def _reposition():
        root.update_idletasks()
        w = max(root.winfo_reqwidth(), 200)
        h = root.winfo_reqheight()
        sw = root.winfo_screenwidth()
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+24")

    def _poll():
        try:
            while True:
                cmd = _cmd_queue.get_nowait()
                if cmd[0] == "show":
                    _, mode, color, pulse = cmd
                    mode_lbl.configure(text=_MODE_LABELS.get(mode, mode))
                    _state["pulse"] = pulse
                    _state["dot_color"] = color
                    dot_lbl.configure(fg=color)
                    _state["visible"] = True
                    _reposition()
                    root.deiconify()
                    root.lift()
                elif cmd[0] == "hide":
                    _state["visible"] = False
                    root.withdraw()
        except queue.Empty:
            pass
        # Poll frequently when visible (responsive), slow when hidden (no wasted wakeups)
        root.after(50 if _state["visible"] else 200, _poll)

    root.after(0, _poll)
    root.mainloop()
