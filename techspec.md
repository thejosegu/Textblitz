# Textblitz — Technical Specification

**Version:** 1.1  
**Stand:** April 2026  
**Plattform:** Windows 10/11  
**Sprache:** Python 3.14+

---

## 1. Übersicht

Textblitz ist eine Windows System Tray App, die per Tastenkombination Sprache in Text umwandelt und diesen direkt an der aktuellen Cursorposition einfügt — ohne Fensterwechsel, ohne manuelles Einfügen. Die App läuft dauerhaft im Hintergrund und ist in jeder Anwendung nutzbar.

### Kernfunktion

```
Taste halten → sprechen → Taste loslassen → Text erscheint am Cursor
```

Vier Modi bestimmen, wie der transkribierte Text weiterverarbeitet wird:

| Modus  | Hotkey (Standard)       | Verhalten                                         |
|--------|-------------------------|---------------------------------------------------|
| Normal | Right Ctrl              | Whisper-Transkript 1:1, keine Nachbearbeitung     |
| Plus   | Right Alt               | GPT reformuliert gesprochen → geschrieben         |
| Rage   | Right Ctrl + Right Alt  | Wütender Text wird in höfliche Nachricht umgeschrieben |
| Emoji  | Right Ctrl + Right Shift| Text bleibt erhalten, Emojis werden eingefügt     |

---

## 2. Architektur

### Threading-Modell

```
┌─────────────────────────────────────────────────────┐
│ Main Thread                                         │
│  pystray.Icon.run()  ← muss auf Main Thread (Win32) │
└───────────────┬─────────────────────────────────────┘
                │ callbacks (on_open_settings, on_quit)
                ▼
┌─────────────────────────────────────────────────────┐
│ Thread: pynput Keyboard Listener (auto-managed)     │
│  on_press / on_release → HotkeyListener._on_press   │
│  fires: _on_recording_start / _on_recording_stop    │
└───────────────┬─────────────────────────────────────┘
                │ submits jobs
                ▼
┌─────────────────────────────────────────────────────┐
│ ThreadPoolExecutor (max_workers=1)                  │
│  _pipeline(): transcribe → process → inject → toast │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Thread: Settings Window (on demand, daemon)         │
│  customtkinter.CTk.mainloop()                       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Thread: Toast Notification (on demand, daemon)      │
│  tkinter.Tk.mainloop() — kurzlebig (2–3 s)          │
└─────────────────────────────────────────────────────┘
```

**Wichtig:** pystray benötigt auf Windows den Main Thread (Win32 Message Loop). Alle anderen Komponenten laufen in Daemon-Threads.

### Verarbeitungs-Pipeline

```
[Hotkey keydown]
      │
      ▼
Recorder.start()          ← sounddevice.InputStream startet
TrayIcon → "recording"

[Hotkey keyup]
      │
      ▼
Recorder.stop()           ← numpy frames → WAV BytesIO
TrayIcon → "processing"
      │
      ▼
transcriber.transcribe()  ← Whisper API (OpenAI oder Groq)
      │
      ├─ mode == "normal" ──────────────────────────────→ apply_snippets() → inject()
      │
      └─ mode in {plus, rage, emoji}
              │
              ▼
        processor.process()   ← GPT-4o-mini oder llama-3.1-8b
              │
              ▼
        apply_snippets()      ← Keyword→Text-Ersetzung (case-insensitive)
              │
              ▼
           inject()           ← clipboard + Ctrl+V
              │
              ▼
           toast.show()       ← kurze Overlay-Benachrichtigung
              │
              ▼
        TrayIcon → "ready"
```

---

## 3. Module

### `main.py` — Einstiegspunkt & Orchestrierung

Klasse `Textblitz` koordiniert alle Komponenten.

| Methode | Beschreibung |
|---------|-------------|
| `run()` | Startet HotkeyListener, blockiert auf pystray |
| `_on_recording_start(mode)` | Prüft API-Key, startet Recorder, setzt Tray-Status |
| `_on_recording_stop(mode)` | Stoppt Recorder, submittet Pipeline-Job |
| `_pipeline(audio_buf, mode)` | Vollständige Verarbeitungskette in ThreadPool |
| `_open_settings()` | Öffnet Settings-Window in neuem Thread (Lock verhindert Doppel-Öffnung) |

---

### `config.py` — Einstellungen

Persistenz via `config.json` im Projektverzeichnis. Deep-merge mit `DEFAULT_CONFIG` bei jedem Laden — neue Felder werden automatisch befüllt.

**API-Key-Speicherung:** Der Key wird **ausschließlich** in `.env` gespeichert (niemals in `config.json`). `load_dotenv()` lädt ihn beim Start in `os.environ["GROQ_API_KEY"]`. Der `api_key`-Setter schreibt direkt in `.env` und die Umgebungsvariable; `save()` filtert `api_key` aus den JSON-Daten heraus.

**Schema `config.json`** (api_key wird nie geschrieben):

```json
{
  "whisper_language": "auto",
  "record_mode": "hold",
  "hotkeys": {
    "normal":  "ctrl_r",
    "plus":    "alt_r",
    "rage":    "ctrl_r+alt_r",
    "emoji":   "ctrl_r+shift_r"
  },
  "prompts": {
    "plus":  "...",
    "rage":  "...",
    "emoji": "... {density} ..."
  },
  "emoji_density": 5,
  "proper_nouns": ["Name1", "Name2"],
  "autostart": false,
  "snippets": [
    {"keyword": "freundliche grüße", "text": "Mit freundlichen Grüßen"},
    ...
  ]
}
```

**`.env`** (gitignored):
```
GROQ_API_KEY=gsk_...
```

**Hotkey-Format:** pynput Key-Attributnamen, durch `+` getrennt.  
Unterstützte Token: `ctrl_r`, `ctrl_l`, `alt_r`, `alt_l`, `shift_r`, `shift_l`, `cmd_r`, `cmd_l`, `space`, `f13`–`f15`, `scroll_lock`, `pause`.

---

### `hotkeys.py` — Globale Tastenkombinationen

`HotkeyListener` lauscht systemweit auf alle Tastenereignisse via `pynput.keyboard.Listener` (`suppress=False` — Tasten werden nicht blockiert).

**Hold-to-Record-Logik:**

```
on_press(key):
  pressed_set.add(key)
  falls active_mode == None:
    prüfe alle konfigurierten Combos:
      if combo ⊆ pressed_set → active_mode = mode, fire on_start(mode)

on_release(key):
  falls key ∈ active_combo:
    active_mode = None, fire on_stop(mode)
  pressed_set.discard(key)
```

`capturing = True` während der Hotkey-Aufnahme in den Einstellungen — verhindert versehentliche Aufnahmen.

---

### `recorder.py` — Audioaufnahme

| Parameter | Wert |
|-----------|------|
| Sample Rate | 16.000 Hz |
| Channels | 1 (Mono) |
| Dtype | int16 |
| Backend | sounddevice (PortAudio) |

Frames werden als `numpy.ndarray` in einer Liste gesammelt. `stop()` konkateniert alle Frames und verpackt sie in einen WAV-`BytesIO`-Buffer mit `.name = "audio.wav"` (Whisper API benötigt ein Filename-Attribut).

---

### `transcriber.py` — Transkription

**Provider-Erkennung** anhand des API-Key-Präfixes:

| Präfix | Provider | Modell |
|--------|----------|--------|
| `sk-...` | OpenAI | `whisper-1` |
| `gsk_...` | Groq | `whisper-large-v3-turbo` |

Beide APIs verwenden dieselbe Aufruf-Signatur (`client.audio.transcriptions.create`).  
`detect_provider(api_key)` → `"OpenAI"` / `"Groq"` / `"Nicht gesetzt"` (genutzt im Feedback-Tab).

Proper Nouns werden als Whisper `prompt`-Parameter übergeben (verbessert Erkennungsgenauigkeit für Eigennamen).

---

### `processor.py` — Textverarbeitung

**Normal-Modus:** No-Op, gibt Transkript unverändert zurück.

**Plus / Rage / Emoji:** Sendet `(system_prompt, user_text)` an ein Chat-Modell:

| Provider | Modell |
|----------|--------|
| OpenAI | `gpt-4o-mini` |
| Groq | `llama-3.1-8b-instant` |

Im Emoji-Prompt wird `{density}` durch den konfigurierten Wert (1–10) ersetzt.

**`apply_snippets(text, snippets)`:** Wird nach jeder Verarbeitung (alle Modi) aufgerufen. Ersetzt Keywords case-insensitiv durch den definierten Ersatztext via `re.sub`. Snippets werden in `config.json` gespeichert und im Snippets-Tab verwaltet.

---

### `injector.py` — Text-Einbindung

```
1. Alten Clipboard-Inhalt sichern  (pyperclip.paste)
2. Text in Clipboard schreiben     (pyperclip.copy)
3. Warte 50 ms
4. Ctrl+V simulieren               (pynput.keyboard.Controller)
5. Warte 100 ms
6. Alten Clipboard-Inhalt wiederherstellen
```

Funktioniert in jeder Anwendung die Ctrl+V unterstützt.

---

### `tray.py` — System Tray Icon

Icons werden zur Laufzeit mit Pillow generiert (64×64 RGBA, gefüllter Kreis + Buchstabe „B"):

| Status | Farbe | Bedeutung |
|--------|-------|-----------|
| `ready` | Grün `#2ECC71` | Bereit, wartet auf Hotkey |
| `recording` | Rot `#E74C3C` | Aufnahme läuft |
| `processing` | Orange `#F39C12` | API-Aufruf läuft |
| `error` | Grau `#95A5A6` | Fehler (auto-reset nach 3 s) |

Tray-Menü: **Einstellungen** / **Beenden**.

Modulweiter Zustand (kein Objekt nötig):

- `_entries`: `deque(maxlen=100)` — Ring-Buffer mit Zeitstempel
- `last_transcript`, `last_processed`, `last_mode`, `last_error` — letztes Ergebnis für Feedback-Tab
- `add(msg)` / `get_all()` / `set_last(...)` / `set_error(...)` — threadsicher via `threading.Lock`

---

### `toast.py` — Overlay-Benachrichtigung

Borderless `tkinter.Tk`-Fenster, läuft in eigenem Daemon-Thread:

- Position: unten rechts, 20 px Abstand zum Bildschirmrand, 60 px über Taskleiste
- Zeigt: Titel „✓ Textblitz — Text eingefügt" + erste 60 Zeichen der Ausgabe
- Transparenz: 93% (`-alpha 0.93`)
- Lebensdauer: 2.800 ms, danach `root.destroy()`

---

### `settings_ui.py` — Einstellungsfenster

`tkinter.Tk` + `sv-ttk` (Windows 11 Fluent Design), 640×820 px, folgt System Dark/Light Mode, 6 Tabs:

| Tab | Inhalt |
|-----|--------|
| **Allgemein** | API Key (masked, wird in `.env` gespeichert), Whisper-Sprache, Aufnahme-Modus, Autostart |
| **Hotkeys** | Hotkey-Aufnahme per pynput-Listener-Dialog für alle 4 Modi |
| **Modi** | System-Prompts für Plus/Rage/Emoji, Emoji-Dichte-Slider |
| **Snippets** | Keyword→Text-Paare, beliebig viele, per „+ Snippet hinzufügen" erweiterbar |
| **Eigennamen** | Freitext-Liste, ein Name pro Zeile |
| **Feedback** | API-Status, letztes Ergebnis, Umgebung, Live-Log (auto-refresh 2 s) |

Globale **Speichern** / **Abbrechen**-Buttons am unteren Fensterrand — immer sichtbar (via `side="bottom"` vor dem Notebook gepackt).

**Hotkey-Aufnahme-Dialog:** Öffnet `tk.Toplevel`, startet temporären `pynput.Listener`. Alle gedrückten Tasten werden gesammelt, beim ersten `on_release` wird der Combo-String gespeichert und der Dialog geschlossen.

**Autostart:** Schreibt/löscht Registry-Eintrag `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Textblitz`.

**Einstellungen sperren Hotkeys:** Während das Fenster offen ist, wird `HotkeyListener.capturing = True` gesetzt — verhindert versehentliche Aufnahmen beim Konfigurieren.

---

## 4. Externe Abhängigkeiten

| Paket | Version | Zweck |
|-------|---------|-------|
| openai | 2.31.0 | Whisper-1 + GPT-4o-mini API |
| groq | 1.1.2 | Whisper-large-v3-turbo + llama-3.1-8b API |
| pystray | 0.19.5 | Windows System Tray Icon |
| pynput | 1.8.1 | Globale Tastatureingabe (keydown/keyup) |
| sounddevice | 0.5.5 | Audioaufnahme via PortAudio |
| numpy | 2.3.5 | Audio-Frame-Buffer |
| pyperclip | 1.11.0 | Clipboard-Zugriff |
| sv-ttk | — | Windows 11 Fluent Design für tkinter |
| Pillow | 12.1.0 | Tray-Icon-Generierung |
| python-dotenv | — | `.env`-Datei laden |

**Laufzeitumgebung:** Python 3.14.2, Windows 11

---

## 5. API-Kosten (Orientierungswerte)

### OpenAI
| Dienst | Modell | Kosten |
|--------|--------|--------|
| Transkription | whisper-1 | $0.006 / Minute Audio |
| Textverarbeitung (Plus/Rage/Emoji) | gpt-4o-mini | ~$0.0002 / Anfrage |

### Groq (deutlich günstiger / schneller)
| Dienst | Modell | Kosten |
|--------|--------|--------|
| Transkription | whisper-large-v3-turbo | $0.0004 / Minute Audio |
| Textverarbeitung | llama-3.1-8b-instant | ~$0.00003 / Anfrage |

> Groq empfohlen für tägliche Nutzung — ca. 15× günstiger als OpenAI bei vergleichbarer Qualität.

---

## 6. Bekannte Einschränkungen

- **Clipboard-Überschreibung:** Text wird kurz in die Zwischenablage geschrieben. Läuft parallel eine Kopier-Operation des Nutzers, kann der Inhalt kurz verloren gehen (wird nach 100 ms wiederhergestellt).
- **Hotkey-Konflikte:** `ctrl_r` allein kann mit anderen Ctrl-Shortcuts kollidieren. Empfehlung: seltene Kombinationen wie `f14` oder `scroll_lock` verwenden.
- **Suppress=False:** Die Hotkey-Tasten werden nicht blockiert — das Betriebssystem verarbeitet sie weiterhin. Bei Single-Key-Hotkeys kann das unerwünschte Nebeneffekte in bestimmten Apps haben.
- **Kein lokales Modell:** Alle Transkriptionen erfordern eine Internetverbindung und kosten API-Credits.
- **Nur Windows:** pystray verhält sich auf macOS/Linux anders; die App ist nicht portiert.

---

## 7. Erweiterungsmöglichkeiten

- **Lokales Whisper-Modell** via `faster-whisper` — eliminiert API-Kosten und Latenz
- **Fünfter Modus** (z.B. „Zusammenfassen", „Übersetzen", „Code-Kommentar")
- **Mehrere Profile** mit unterschiedlichen API-Keys / Prompts (z.B. Team vs. privat)
- **Hotkey-Konflikt-Erkennung** beim Speichern der Einstellungen
- **`.exe`-Build** via PyInstaller für verteilbare Einzeldatei ohne Python-Installation

---

## 8. Nachträgliche Änderungen & Erkenntnisse

### 8.1 Umbenennung: Blitztext → Textblitz

App wurde von „Blitztext" in „Textblitz" umbenannt. Betroffen: `main.py`, `tray.py`, `toast.py`, `settings_ui.py`, Einstiegspunkt `textblitz.pyw` (ehemals `blitztext.pyw`), Registry-Autostart-Key, Tray-Icons (Buchstabe „T").

---

### 8.2 API-Key-Sicherheit (.env statt config.json)

**Problem:** Groq API-Key war in `config.json` gespeichert und wurde versehentlich nach GitHub gepusht → GitHub Push Protection blockierte den Push.

**Lösung:**
- API-Key wird **ausschließlich** in `.env` gespeichert (`.gitignore`d)
- `config.py` lädt per `load_dotenv()` beim Start; `api_key`-Setter schreibt direkt in `.env`
- `save()` filtert `api_key` aus `config.json` heraus — Key kann nie mehr versehentlich committet werden

---

### 8.3 Konsolenloser Start (`textblitz.pyw`)

**Problem:** `python main.py` öffnete ein Konsolenfenster.  
**Lösung:** Launcher `textblitz.pyw` — Windows führt `.pyw`-Dateien automatisch mit `pythonw.exe` aus (kein Fenster). `stdout`/`stderr` werden in `textblitz.log` umgeleitet.

```
Starten: Doppelklick auf textblitz.pyw
Logs:    textblitz.log (im Projektverzeichnis)
```

---

### 8.4 Einstellungsfenster: Migration von customtkinter → tkinter + sv-ttk

**Problem:** customtkinter 5.2.2 ist nicht kompatibel mit Python 3.14: GUI-Calls aus Nicht-Main-Threads scheitern mit `RuntimeError: main thread is not in main loop`. Nach `destroy()` ist der Tcl-Interpreter beendet — eine neue Instanz kann nicht erstellt werden.

**Lösung:**
- Wechsel zu `tkinter.Tk` + `sv-ttk` (Windows 11 Fluent Design, folgt System Dark/Light Mode)
- `SettingsWindow` wird **einmalig** erstellt und nie zerstört
- Öffnen = `deiconify()` + `_reload_values()`; Schließen = `withdraw()`
- Ein dauerhafter Daemon-Thread (`settings-ui`) besitzt das Fenster und empfängt Öffnen-Anfragen via `queue.Queue`

```
settings_ui.py:
  _ui_worker()            ← dauerhafter Thread, erstellt SettingsWindow einmalig
  SettingsWindow.show()   ← reload + deiconify
  SettingsWindow._close() ← withdraw (kein destroy)
```

---

### 8.5 Multi-Key-Hotkeys ohne Funktion (Bug)

**Ursache:** `ctrl_r` (Normal-Modus) wurde sofort ausgelöst, bevor `alt_r` gedrückt werden konnte — `ctrl_r+alt_r` (Rage-Modus) wurde nie erreicht.

**Lösung:** 50 ms Debounce-Timer in `hotkeys.py`. Beim Drücken einer Taste wird gewartet; wenn weitere Tasten folgen, wird der Timer zurückgesetzt. Beim Ablauf gewinnt die **längste passende Combo**.

```
hotkeys.py:
  _on_press()      ← startet/resettet threading.Timer(0.05, _try_trigger)
  _try_trigger()   ← wählt längste Combo aus self._pressed
  _on_release()    ← bricht pending Timer ab falls Taste vor Auslösung losgelassen
``` 

---

### 8.6 Snippets-Feature

Keyword→Text-Ersetzung nach der Transkription. Konfigurierbar im Einstellungsfenster (Tab „Snippets").

- `processor.apply_snippets(text, snippets)` — iteriert die Snippet-Liste, ersetzt per `re.sub` case-insensitiv
- Wird in `_pipeline()` nach allen Modi (Normal + KI-Modi) angewendet
- Gespeichert in `config.json` als Array von `{keyword, text}`-Objekten

