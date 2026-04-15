# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Ohne Konsolenfenster (empfohlen):
pythonw blitztext.pyw

# Mit Konsolenfenster (für Debugging):
python main.py
```

Logs landen in `blitztext.log`. Die App erscheint als Tray-Icon — kein eigenes Fenster.

## Dependencies installieren

```bash
pip install -r requirements.txt
```

## Architecture

**Blitztext** ist eine Windows System Tray App (Python 3.14): Hotkey halten → Sprache aufnehmen → Whisper transkribieren → optional per GPT nachbearbeiten → Text an Cursorposition einfügen.

### Threading-Modell

| Thread | Besitzer | Aufgabe |
|--------|----------|---------|
| Main | `pystray` | Win32 Message Loop — **muss** Main Thread sein |
| pynput Listener | pynput | Globale Tastaturereignisse |
| ThreadPoolExecutor (max 1) | `main.py` | Audio-Pipeline (transcribe → process → inject) |
| `settings-ui` (Daemon) | `settings_ui.py` | Einziger Thread der tkinter/customtkinter anfassen darf |
| Toast (Daemon, kurzlebig) | `toast.py` | Overlay-Benachrichtigung via eigenem `tk.Tk()` |

### Kritische Architekturentscheidungen

**Settings-Fenster:** `SettingsWindow(ctk.CTk)` wird **einmalig** in einem dauerhaften Daemon-Thread erstellt und nie zerstört. Öffnen = `deiconify()`, Schließen = `withdraw()`. Grund: customtkinter 5.2.2 ist inkompatibel mit Python 3.14 in Nicht-Main-Threads — `destroy()` korrumpiert den Tcl-State unwiederbringlich. Anfragen laufen über `queue.Queue`, der aufrufende Thread wartet via `threading.Event`.

**Hotkey-Debounce:** Multi-Key-Combos (z.B. `ctrl_r+alt_r`) brauchen einen 50ms Timer in `_on_press`. Beim Ablauf gewinnt die längste passende Combo. Ohne Debounce löst `ctrl_r` sofort Normal-Modus aus, bevor `alt_r` gedrückt werden kann.

**pystray auf Windows:** Muss zwingend auf dem Main Thread laufen. Alle anderen Komponenten sind Daemon-Threads.

### Datenfluss

```
Hotkey keydown → Recorder.start()
Hotkey keyup   → Recorder.stop() → WAV BytesIO
               → transcribe() [Whisper API]
               → process()    [GPT, nur bei plus/rage/emoji]
               → inject()     [clipboard + Ctrl+V]
               → toast.show() [tkinter Overlay]
```

### Modul-Übersicht

- **`main.py`** — `Blitztext`-Klasse orchestriert alle Komponenten; `_pipeline()` im ThreadPool
- **`config.py`** — JSON-Persistenz via `config.json`; Deep-Merge mit `DEFAULT_CONFIG`
- **`hotkeys.py`** — `HotkeyListener` mit 50ms Debounce; `parse_hotkey()` wandelt Config-Strings in pynput-Keys
- **`settings_ui.py`** — `SettingsWindow` (ctk.CTk) + dauerhafter `_ui_worker`-Thread + Queue-Mechanismus
- **`transcriber.py`** — Provider-Erkennung via API-Key-Präfix (`sk-` = OpenAI, `gsk_` = Groq)
- **`processor.py`** — Kein-Op für Normal-Modus; Chat-API für plus/rage/emoji
- **`injector.py`** — Clipboard-Swap + Ctrl+V; stellt alten Clipboard-Inhalt nach 100ms wieder her
- **`tray.py`** — Icons werden zur Laufzeit mit Pillow generiert (64×64 RGBA)
- **`toast.py`** — Eigenes `tk.Tk()` pro Anzeige in Daemon-Thread (2.800ms Lebensdauer)
- **`log.py`** — Modulweiter Ring-Buffer (`deque(maxlen=100)`), threadsicher

### Hotkey-Format (config.json)

Pynput Key-Attributnamen, durch `+` getrennt: `ctrl_r`, `alt_r`, `shift_r`, `ctrl_r+alt_r` etc.
Token-Liste in `hotkeys.py::_KEY_MAP`.

### Bekannte Inkompatibilität

customtkinter 5.2.2 + Python 3.14: `CTkSegmentedButton._variable` wird bei fehlgeschlagenem `__init__` nicht gesetzt → `AttributeError` bei `destroy()`. Workaround bereits implementiert (never destroy).
