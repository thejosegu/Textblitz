# Abhängigkeiten

Installation aller Pakete:

```bash
python -m pip install -r requirements.txt
```

## Pakete

| Paket | Version | Zweck |
|-------|---------|-------|
| `openai` | >=1.0.0 | Whisper-Transkription & GPT-Verarbeitung (OpenAI API) |
| `groq` | >=0.28.0 | Whisper-Transkription (Groq API, Alternative zu OpenAI) |
| `pystray` | >=0.19.0 | System-Tray-Icon unter Windows |
| `pynput` | >=1.7.0 | Globale Hotkey-Erkennung |
| `sounddevice` | >=0.4.6 | Audioaufnahme vom Mikrofon |
| `numpy` | >=1.24.0 | Audiodatenverarbeitung (benötigt von sounddevice) |
| `pyperclip` | >=1.8.0 | Zwischenablage-Zugriff zum Einfügen des Textes |
| `sv-ttk` | >=2.6.0 | Modernes Theme für tkinter (Settings-Fenster) |
| `Pillow` | >=10.0.0 | Generierung der Tray-Icons zur Laufzeit |
| `python-dotenv` | >=1.0.0 | Laden von API-Keys aus einer `.env`-Datei |

## Hinweise

- Python 3.14 wird vorausgesetzt.
- `customtkinter` ist **nicht** in `requirements.txt` enthalten, wird aber von `settings_ui.py` verwendet — ggf. separat installieren:
  ```bash
  python -m pip install customtkinter
  ```
- API-Key kann entweder in `config.json` oder in einer `.env`-Datei hinterlegt werden (z.B. `OPENAI_API_KEY=sk-...`).
