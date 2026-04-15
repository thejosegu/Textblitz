import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_CONFIG = {
    "api_key": "",
    "whisper_language": "auto",
    "record_mode": "hold",
    "hotkeys": {
        "normal":  "ctrl_r",
        "plus":    "alt_r",
        "rage":    "ctrl_r+alt_r",
        "emoji":   "ctrl_r+shift_r",
    },
    "prompts": {
        "plus": (
            "Formuliere diesen gesprochenen Text natürlicher und schriftlicher um. "
            "Behalte den Sinn und die ungefähre Länge bei. "
            "Antworte NUR mit dem umformulierten Text, ohne Erklärungen oder Kommentare."
        ),
        "rage": (
            "Diese Person klingt aufgebracht oder frustriert. "
            "Schreibe eine höfliche, professionelle Version dieser Nachricht, "
            "die den Kerninhalt beibehält. "
            "Antworte NUR mit der höflichen Version, ohne Erklärungen."
        ),
        "emoji": (
            "Füge passende Emojis in diesen Text ein. "
            "Emoji-Dichte: {density}/10 (1=sehr wenige, 10=sehr viele). "
            "Behalte den Text ansonsten unverändert. "
            "Antworte NUR mit dem Text mit Emojis, ohne Erklärungen."
        ),
    },
    "emoji_density": 5,
    "proper_nouns": [],
    "autostart": False,
    "snippets": [
        {"keyword": "freundliche gr\u00fc\u00dfe", "text": "Mit freundlichen Gr\u00fc\u00dfen"},
        {"keyword": "vielen dank",      "text": "Vielen Dank und mit freundlichen Gr\u00fc\u00dfen"},
        {"keyword": "auf wiedersehen",  "text": "Auf Wiedersehen und einen sch\u00f6nen Tag noch!"},
    ],
}

CONFIG_PATH = Path(__file__).parent / "config.json"


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = _deep_merge(DEFAULT_CONFIG, loaded)
            except Exception:
                self._data = _deep_merge(DEFAULT_CONFIG, {})
        else:
            self._data = _deep_merge(DEFAULT_CONFIG, {})

    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ── generic access ──────────────────────────────────────────────
    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    # ── typed properties ────────────────────────────────────────────
    @property
    def api_key(self) -> str:
        # .env hat Vorrang vor config.json
        return os.environ.get("GROQ_API_KEY") or self._data.get("api_key", "")

    @api_key.setter
    def api_key(self, v: str):
        self._data["api_key"] = v
        # Auch Umgebungsvariable aktualisieren (für laufende Session)
        os.environ["GROQ_API_KEY"] = v

    @property
    def whisper_language(self) -> str:
        return self._data.get("whisper_language", "auto")

    @whisper_language.setter
    def whisper_language(self, v: str):
        self._data["whisper_language"] = v

    @property
    def record_mode(self) -> str:
        return self._data.get("record_mode", "hold")

    @record_mode.setter
    def record_mode(self, v: str):
        self._data["record_mode"] = v

    @property
    def hotkeys(self) -> dict:
        return self._data.setdefault("hotkeys", dict(DEFAULT_CONFIG["hotkeys"]))

    def get_hotkey(self, mode: str) -> str:
        return self.hotkeys.get(mode, "")

    def set_hotkey(self, mode: str, value: str):
        self.hotkeys[mode] = value

    @property
    def prompts(self) -> dict:
        return self._data.setdefault("prompts", dict(DEFAULT_CONFIG["prompts"]))

    def get_prompt(self, mode: str) -> str:
        return self.prompts.get(mode, "")

    def set_prompt(self, mode: str, value: str):
        self.prompts[mode] = value

    @property
    def emoji_density(self) -> int:
        return self._data.get("emoji_density", 5)

    @emoji_density.setter
    def emoji_density(self, v: int):
        self._data["emoji_density"] = int(v)

    @property
    def proper_nouns(self) -> list:
        return self._data.get("proper_nouns", [])

    @proper_nouns.setter
    def proper_nouns(self, v: list):
        self._data["proper_nouns"] = v

    @property
    def autostart(self) -> bool:
        return self._data.get("autostart", False)

    @autostart.setter
    def autostart(self, v: bool):
        self._data["autostart"] = v

    @property
    def snippets(self) -> list:
        """Liste von {keyword, text} Dicts."""
        return self._data.get("snippets", [])

    @snippets.setter
    def snippets(self, v: list):
        self._data["snippets"] = v


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
