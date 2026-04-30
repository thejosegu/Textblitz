# Blitztext Build-Dokumentation

Diese Datei dokumentiert den Build-Prozess der portablen Windows-EXE, erklärt die resultierende Dateigröße und beschreibt bekannte Probleme mit dem lokalen Whisper-Modell.

---

## Build durchführen

### Voraussetzungen

```bash
pip install pyinstaller
```

### Build starten

```bash
python build.py
```

**Ausgabe:** `dist/Blitztext.exe` (portable Single-File-EXE)

Die `build.py` erledigt automatisch:
1. Kopiert einen System-Font nach `assets/font.ttf` (für Tray-Icons)
2. Räumt alte Build-Artefakte auf
3. Führt PyInstaller mit `Blitztext.spec` aus
4. Kopiert `config.json` in den Distribution-Ordner

---

## Warum ist die EXE 83 MB groß?

Die EXE enthält den kompletten Python-Interpreter (3.12), alle Python-Pakete und nativen DLLs, die zur Laufzeit benötigt werden. Ohne diese Abhängigkeiten läuft die App nicht auf PCs ohne Python-Installation.

### Größenaufschlüsselung

| Komponente | Größe | Zweck |
|---|---|---|
| **onnxruntime** | ~32 MB | ML-Inference-Engine. Wird intern von `ctranslate2` für optimierte CPU-Inference genutzt. |
| **av.libs** | ~19 MB | FFmpeg-Bibliotheken (libavcodec, libavformat etc.). Werden für Audio-Decoding benötigt. |
| **ctranslate2** | ~17 MB | Das eigentliche Whisper-Backend für lokale Transkription. |
| **PYZ.pyz** | ~14 MB | Komprimierter Python-Bytecode aller importierten Pakete. |
| **numpy.libs** | ~4 MB | OpenBLAS-DLL für Matrix-Operationen. |
| **PIL** | ~3.6 MB | Pillow-Bildverarbeitung (wird für dynamische Tray-Icons genutzt). |
| **cryptography** | ~2.5 MB | Rust-basierte TLS/HTTPS-Bibliothek (für API-Calls zu OpenAI/Groq). |
| **Sonstiges** | ~11 MB | Python-DLL, Tcl/Tk, VC-Redist, Font, Sounddevice, PyStray, etc. |

**Gesamt: ~83 MB**

### Was wurde absichtlich entfernt?

Die folgenden Pakete sind in der `Blitztext.spec` explizit ausgeschlossen (`excludes`), da sie nicht benötigt werden:

- `torch` (447 MB) — wird von faster-whisper nicht zwingend benötigt
- `torchvision`, `torchaudio` (15 MB)
- `tensorflow`, `tensorboard`
- `transformers`
- `matplotlib`
- `scipy`
- `pandas`, `sklearn`
- `cv2` (OpenCV)
- `IPython`, `jupyter`, `notebook`

**Ohne diese Excludes wäre die EXE > 500 MB.**

### Kann die Größe weiter reduziert werden?

Ja, mit Einschränkungen:

| Ansatz | Einsparung | Einschränkung |
|---|---|---|
| `onnxruntime` entfernen | ~32 MB | Lokales Whisper funktioniert dann nur noch ohne ONNX-Optimierung (langsamer) |
| `av.libs` (FFmpeg) entfernen | ~19 MB | Kein Audio-Decoding mehr — lokales Whisper funktioniert nicht |
| `--onefile` statt eingebettetem PKG | ~0 MB | PyInstaller erstellt dann einen Selbstentpacker, der bei jedem Start ins Temp-Verzeichnis extrahiert |
| Nur Online-Modus bauen | ~50 MB | ctranslate2 + av.libs + onnxruntime könnten entfallen |

**Empfehlung:** Die aktuelle Größe ist ein guter Kompromiss. Wer nur den Online-Modus nutzt, kann eine separate Spec ohne lokale ML-Bibliotheken erstellen.

---

## Lokales Whisper-Modell

### Funktionsweise

Beim ersten Wechsel zu „Lokal“ in den Einstellungen (oder beim ersten Start mit aktiviertem lokalem Modus) lädt `faster-whisper` automatisch das Modell `Systran/faster-whisper-small` von Hugging Face herunter.

- **Download-Größe:** ~461 MB (`model.bin`)
- **Zielpfad:** `whisper/` neben der EXE (oder neben dem Skript im Dev-Modus)
- **RAM-Bedarf beim Laden:** ~1 GB
- **RAM-Bedarf bei Transkription:** ~500 MB

### Bekannte Probleme

#### 1. App scheint beim Modell-Laden einzufrieren

**Symptom:** Nach Klick auf „Lokal“ in den Einstellungen friert die UI für 10–30 Sekunden ein. Der Toast „⏳ wird geladen…" bleibt stehen.

**Ursache:** Das Modell wird im Haupt-Thread geladen (blocking). `faster-whisper` lädt ~460 MB von der Festplatte in den RAM und initialisiert die ONNX/CTranslate2-Runtime.

**Lösung:** Warten. Der Ladevorgang kann auf langsamen PCs oder HDDs bis zu einer Minute dauern. Das Modell wird nur **einmalig** heruntergeladen; danach ist der Start sofort.

#### 2. App stürzt beim Modell-Laden ab

**Symptom:** Die EXE verschwindet ohne Fehlermeldung aus dem Tray.

**Mögliche Ursachen:**

| Ursache | Erkennung | Lösung |
|---|---|---|
| **Nicht genug RAM** | PC hat < 4 GB RAM | Schließe andere Anwendungen oder nutze Online-Modus |
| **Modell-Download unterbrochen** | `model.bin` ist kleiner als 461 MB | Lösche den `whisper/`-Ordner und versuche es erneut |
| **Fehlende VC-Redist** | `vcruntime140.dll` / `msvcp140.dll` fehlen | Installiere [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| **Antivirus blockiert DLL-Ladung** | Windows Defender oder AV meldet „Verhalten:Win32" | Füge den Blitztext-Ordner zur AV-Ausnahme hinzu |

**Debugging:**

Prüfe die Log-Datei `blitztext.log` neben der EXE. Dort steht die genaue Exception, falls der Crash im Python-Code passiert.

#### 3. Modell wird bei jedem Start neu heruntergeladen

**Symptom:** `whisper/` bleibt leer oder das Modell wird immer neu geladen.

**Ursache:** Im frozen Build zeigt `__file__` ins temporäre Entpack-Verzeichnis. `faster-whisper` versucht, das Modell dort zu speichern — beim nächsten Start ist es weg.

**Status:** Bereits behoben. `config.py`, `transcriber.py` und `blitztext.pyw` nutzen `sys.executable`-Pfad für den frozen Build, sodass das Modell neben der EXE landet.

---

## Technische Details zum Build

### PyInstaller Spec (`Blitztext.spec`)

- **Build-Typ:** Single-File-EXE (`console=False`)
- **UPX:** Aktiviert (komprimiert native DLLs, spart ~20–30%)
- **Assets:** `assets/font.ttf` wird eingebunden
- **Icon:** `assets/icon.ico` (optional — wenn vorhanden)

### Wichtige Code-Anpassungen für Portabilität

1. **`blitztext.pyw`** — Leitet stdout/stderr in `blitztext.log` um und fügt `libs/` zu `sys.path` hinzu
2. **`config.py`** — Speichert `config.json` und `.env` neben der EXE (`_app_dir()`)
3. **`tray.py`** — Prüft zuerst `assets/font.ttf` für Tray-Icons
4. **`settings_ui.py`** — Schreibt bei frozen Build nur den EXE-Pfad in die Registry (Autostart)

### Ordnerstruktur nach Build

```
dist/
├── Blitztext.exe          # 83 MB, portable EXE
├── config.json            # Benutzereinstellungen
├── .env                   # API-Key (optional)
├── blitztext.log          # Log-Datei
└── whisper/               # Lokales Modell (wird bei Bedarf erstellt)
    └── models--Systran--faster-whisper-small/
        └── model.bin      # ~461 MB (wird bei erstem Lokal-Start geladen)
```

---

## Tipps

- **Zip für Distribution:** Den gesamten `dist/`-Ordner zippen und verteilen. Der Nutzer entpackt und startet `Blitztext.exe`.
- **Autostart:** Funktioniert im frozen Build automatisch mit korrektem EXE-Pfad.
- **Updates:** Einfach die neue `Blitztext.exe` überschreiben. `config.json` bleibt erhalten.
