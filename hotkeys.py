"""Global hotkey listener using pynput.

Supports hold-to-record: pressing the configured key combination starts
recording; releasing any key in the combination stops it.

Hotkey strings (stored in config) use pynput Key attribute names joined
by '+', e.g.:
  "ctrl_r"           → Key.ctrl_r
  "ctrl_r+alt_r"     → Key.ctrl_r AND Key.alt_r both held
  "ctrl_r+shift_r"   → Key.ctrl_r AND Key.shift_r both held
"""
from __future__ import annotations

import threading
from typing import Callable

from pynput import keyboard
from pynput.keyboard import Key, KeyCode


# Map config string tokens → pynput Key objects
_KEY_MAP: dict[str, Key] = {
    "ctrl_r":    Key.ctrl_r,
    "ctrl_l":    Key.ctrl_l,
    "alt_r":     Key.alt_r,
    "alt_l":     Key.alt_l,
    "shift_r":   Key.shift_r,
    "shift_l":   Key.shift_l,
    "cmd_r":     Key.cmd_r,
    "cmd_l":     Key.cmd_l,
    "space":     Key.space,
    "f13":       Key.f13,
    "f14":       Key.f14,
    "f15":       Key.f15,
    "scroll_lock": Key.scroll_lock,
    "pause":     Key.pause,
}


def parse_hotkey(spec: str) -> frozenset:
    """Convert a hotkey spec string to a frozenset of pynput key objects."""
    if not spec:
        return frozenset()
    keys: set = set()
    for token in spec.split("+"):
        token = token.strip().lower()
        if token in _KEY_MAP:
            keys.add(_KEY_MAP[token])
        elif len(token) == 1:
            keys.add(KeyCode.from_char(token))
    return frozenset(keys)


def hotkey_to_str(keys: frozenset) -> str:
    """Convert a frozenset of pynput keys back to a display string."""
    reverse = {v: k for k, v in _KEY_MAP.items()}
    parts = []
    for k in keys:
        if k in reverse:
            parts.append(reverse[k])
        elif isinstance(k, KeyCode) and k.char:
            parts.append(k.char)
        else:
            parts.append(str(k))
    return "+".join(sorted(parts))


class HotkeyListener:
    """Listens for configured hotkey combos and fires start/stop callbacks."""

    def __init__(self,
                 get_hotkeys: Callable[[], dict[str, str]],
                 on_start: Callable[[str], None],
                 on_stop:  Callable[[str], None]):
        self._get_hotkeys = get_hotkeys
        self._on_start = on_start
        self._on_stop  = on_stop

        self._pressed: set = set()
        self._active_mode: str | None = None
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None
        self._pending_timer: threading.Timer | None = None
        self.capturing = False  # True while recording a new hotkey in settings

    # ── public API ────────────────────────────────────────────────────
    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    # ── pynput callbacks ──────────────────────────────────────────────
    def _on_press(self, key):
        if self.capturing:
            return  # settings window is capturing – don't act

        with self._lock:
            self._pressed.add(key)
            if self._active_mode is not None:
                return  # already recording

            # Cancel any pending trigger — a new key was pressed, re-evaluate
            if self._pending_timer is not None:
                self._pending_timer.cancel()
                self._pending_timer = None

            # Wait 50 ms before triggering so multi-key combos can fully form
            self._pending_timer = threading.Timer(0.05, self._try_trigger)
            self._pending_timer.start()

    def _try_trigger(self):
        """Called after the short debounce delay — fires the most specific matching combo."""
        with self._lock:
            self._pending_timer = None
            if self._active_mode is not None:
                return

            # Find the combo with the most keys that is fully pressed
            best_mode = None
            best_len = 0
            for mode, spec in self._get_hotkeys().items():
                combo = parse_hotkey(spec)
                if combo and combo.issubset(self._pressed) and len(combo) > best_len:
                    best_len = len(combo)
                    best_mode = mode

            if best_mode:
                self._active_mode = best_mode
            else:
                return

        self._on_start(best_mode)

    def _on_release(self, key):
        if self.capturing:
            return

        with self._lock:
            # Key released before debounce fired → cancel pending trigger
            if self._pending_timer is not None:
                self._pending_timer.cancel()
                self._pending_timer = None

            mode_to_stop = None
            if self._active_mode is not None:
                combo = parse_hotkey(self._get_hotkeys().get(self._active_mode, ""))
                if key in combo:
                    mode_to_stop = self._active_mode
                    self._active_mode = None
            self._pressed.discard(key)

        if mode_to_stop:
            self._on_stop(mode_to_stop)
