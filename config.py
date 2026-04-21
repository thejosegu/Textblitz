import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _app_dir() -> Path:
    """Directory next to the EXE (frozen) or next to this source file (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


load_dotenv(_app_dir() / ".env")

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
    "whisper_model_openai": "whisper-1",
    "whisper_model_groq":   "whisper-large-v3-turbo",
    "chat_model_openai":    "gpt-4o-mini",
    "chat_model_groq":      "llama-3.1-8b-instant",
    "temperature":          0.7,
    "max_tokens":           1024,
    "use_local_whisper":    False,
    "whisper_model_path":   "",
    "snippets": [
        {"keyword": "freundliche gr\u00fc\u00dfe", "text": "Mit freundlichen Gr\u00fc\u00dfen"},
        {"keyword": "vielen dank",      "text": "Vielen Dank und mit freundlichen Gr\u00fc\u00dfen"},
        {"keyword": "auf wiedersehen",  "text": "Auf Wiedersehen und einen sch\u00f6nen Tag noch!"},
    ],
}

CONFIG_PATH = _app_dir() / "config.json"


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
        data = {k: v for k, v in self._data.items() if k != "api_key"}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

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
        # Key wird NICHT in config.json gespeichert — nur in .env und Umgebungsvariable
        os.environ["GROQ_API_KEY"] = v
        env_path = _app_dir() / ".env"
        env_path.write_text(f"GROQ_API_KEY={v}\n", encoding="utf-8")

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

    @property
    def whisper_model_openai(self) -> str:
        return self._data.get("whisper_model_openai", "whisper-1")

    @whisper_model_openai.setter
    def whisper_model_openai(self, v: str):
        self._data["whisper_model_openai"] = v

    @property
    def whisper_model_groq(self) -> str:
        return self._data.get("whisper_model_groq", "whisper-large-v3-turbo")

    @whisper_model_groq.setter
    def whisper_model_groq(self, v: str):
        self._data["whisper_model_groq"] = v

    @property
    def chat_model_openai(self) -> str:
        return self._data.get("chat_model_openai", "gpt-4o-mini")

    @chat_model_openai.setter
    def chat_model_openai(self, v: str):
        self._data["chat_model_openai"] = v

    @property
    def chat_model_groq(self) -> str:
        return self._data.get("chat_model_groq", "llama-3.1-8b-instant")

    @chat_model_groq.setter
    def chat_model_groq(self, v: str):
        self._data["chat_model_groq"] = v

    @property
    def temperature(self) -> float:
        return float(self._data.get("temperature", 0.7))

    @temperature.setter
    def temperature(self, v: float):
        self._data["temperature"] = float(v)

    @property
    def max_tokens(self) -> int:
        return int(self._data.get("max_tokens", 1024))

    @max_tokens.setter
    def max_tokens(self, v: int):
        self._data["max_tokens"] = int(v)

    @property
    def use_local_whisper(self) -> bool:
        return bool(self._data.get("use_local_whisper", False))

    @use_local_whisper.setter
    def use_local_whisper(self, v: bool):
        self._data["use_local_whisper"] = bool(v)

    @property
    def whisper_model_path(self) -> str:
        return self._data.get("whisper_model_path", "")

    @whisper_model_path.setter
    def whisper_model_path(self, v: str):
        self._data["whisper_model_path"] = v


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
