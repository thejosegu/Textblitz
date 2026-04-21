"""System tray icon using pystray with dynamically generated PIL icons."""
from __future__ import annotations

from typing import Callable

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem as Item

# Status → (background color, label char)
_STATUS_STYLES: dict[str, tuple[tuple[int, int, int], str]] = {
    "ready":      ((46, 204, 113),  "B"),   # green
    "recording":  ((231, 76, 60),   "●"),   # red
    "processing": ((243, 156, 18),  "…"),   # orange
    "error":      ((149, 165, 166), "!"),   # grey
}

_MODE_LABELS = {
    "normal": "Normal",
    "plus":   "Plus",
    "rage":   "Rage",
    "emoji":  "Emoji",
}


def _make_icon_image(status: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    color, char = _STATUS_STYLES.get(status, _STATUS_STYLES["error"])
    pad = 3
    draw.ellipse([pad, pad, size - pad, size - pad], fill=color)

    # Try system font, fall back to default
    font = None
    for candidate in ["arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"]:
        try:
            font = ImageFont.truetype(candidate, 28)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    draw.text((size // 2, size // 2), char, fill="white", font=font, anchor="mm")
    return img


def _apply_icon(icon: pystray.Icon, image, title: str) -> None:
    icon.icon = image
    icon.title = title


class TrayIcon:
    def __init__(self,
                 on_open_settings: Callable[[], None],
                 on_quit: Callable[[], None]):
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit
        self._status = "ready"
        self._mode: str | None = None

        self._icon = pystray.Icon(
            name="Blitztext",
            icon=_make_icon_image("ready"),
            title=self._tooltip(),
            menu=self._build_menu(),
        )

    # ── public API ────────────────────────────────────────────────────
    def run(self):
        """Block the calling thread running the tray message loop (must be main thread)."""
        self._icon.run()

    def set_status(self, status: str, mode: str | None = None):
        self._status = status
        self._mode = mode
        image = _make_icon_image(status)
        title = self._tooltip()
        # Shell_NotifyIcon must run on the pystray main thread; schedule() posts
        # via the Win32 message queue to avoid WinError 1402 from other threads.
        backend = getattr(self._icon, "_icon", None)
        if backend is not None and hasattr(backend, "schedule"):
            backend.schedule(lambda: _apply_icon(self._icon, image, title))
        else:
            _apply_icon(self._icon, image, title)

    def stop(self):
        self._icon.stop()

    # ── private ───────────────────────────────────────────────────────
    def _tooltip(self) -> str:
        base = "Blitztext"
        if self._status == "ready":
            return f"{base} — bereit"
        if self._status == "recording":
            label = _MODE_LABELS.get(self._mode or "", self._mode or "")
            return f"{base} — aufnehmen ({label})"
        if self._status == "processing":
            return f"{base} — verarbeiten…"
        if self._status == "error":
            return f"{base} — Fehler"
        return base

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            Item("Einstellungen", self._settings_clicked),
            pystray.Menu.SEPARATOR,
            Item("Beenden", self._quit_clicked),
        )

    def _settings_clicked(self, icon, item):
        self._on_open_settings()

    def _quit_clicked(self, icon, item):
        self._on_quit()
