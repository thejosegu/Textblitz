"""Inject text at the current cursor position via clipboard + Ctrl+V."""
import time

import pyperclip
from pynput.keyboard import Controller, Key

_keyboard = Controller()


def inject(text: str):
    """Copy *text* to clipboard, paste at cursor, then restore previous clipboard."""
    old = _safe_paste()
    pyperclip.copy(text)
    time.sleep(0.05)  # give clipboard time to update

    _keyboard.press(Key.ctrl_l)
    _keyboard.press("v")
    _keyboard.release("v")
    _keyboard.release(Key.ctrl_l)

    time.sleep(0.1)  # give the target app time to process the paste

    if old is not None:
        pyperclip.copy(old)


def _safe_paste() -> str | None:
    try:
        return pyperclip.paste()
    except Exception:
        return None
