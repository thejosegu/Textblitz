"""Small overlay notification shown after text is injected."""
from __future__ import annotations

import threading
import tkinter as tk


def show(text: str, duration_ms: int = 2800):
    """Show a brief bottom-right overlay. Non-blocking."""
    threading.Thread(target=_show, args=(text, duration_ms), daemon=True).start()


def show_info(message: str, duration_ms: int = 30_000):
    """Show a status/info overlay (no 'text inserted' header). Non-blocking."""
    threading.Thread(target=_show_info, args=(message, duration_ms), daemon=True).start()


def _show(text: str, duration_ms: int):
    try:
        root = tk.Tk()
        root.overrideredirect(True)       # no title bar / border
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.93)
        root.configure(bg="#16213e")

        # ── layout ────────────────────────────────────────────────────
        pad_x, pad_y = 14, 10
        max_chars = 60
        preview = (text[:max_chars] + "…") if len(text) > max_chars else text

        header = tk.Label(
            root, text="✓ Textblitz — Text eingefügt",
            bg="#16213e", fg="#2ecc71",
            font=("Segoe UI", 9, "bold"),
            anchor="w", padx=pad_x, pady=pad_y,
        )
        header.pack(fill="x")

        body = tk.Label(
            root, text=preview,
            bg="#16213e", fg="#ecf0f1",
            font=("Segoe UI", 9),
            anchor="w", padx=pad_x, pady=(0, pad_y),
            wraplength=380, justify="left",
        )
        body.pack(fill="x")

        # ── position: bottom-right above taskbar ──────────────────────
        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{max(w, 280)}x{h}+{sw - max(w, 280) - 20}+{sh - h - 60}")

        root.after(duration_ms, root.destroy)
        root.mainloop()
    except Exception:
        pass  # toast is non-critical


def _show_info(message: str, duration_ms: int):
    try:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.93)
        root.configure(bg="#16213e")

        pad_x, pad_y = 14, 10
        tk.Label(
            root, text=message,
            bg="#16213e", fg="#ecf0f1",
            font=("Segoe UI", 9),
            anchor="w", padx=pad_x, pady=pad_y,
            wraplength=380, justify="left",
        ).pack(fill="x")

        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{max(w, 280)}x{h}+{sw - max(w, 280) - 20}+{sh - h - 60}")

        root.after(duration_ms, root.destroy)
        root.mainloop()
    except Exception:
        pass
