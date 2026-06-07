# Zippy for Windows — Technische Architekturdokumentation

Dieses Dokument beschreibt vollständig, wie Zippy gebaut ist und funktioniert. Es ist so geschrieben, dass ein erfahrener Entwickler (oder eine KI) die App anhand dieser Dokumentation von Grund auf neu implementieren kann.

---

## Überblick

Zippy ist ein WinForms-Desktop-Assistent für Windows. Er läuft im System Tray, zeigt ein animiertes Overlay-Mascot ("Companion") neben dem Cursor und ermöglicht per Sprache oder Text:

- Screenshots aller Monitore zu machen und mit einer Vision-LLM-API (Groq) zu analysieren
- Spracheingaben zu transkribieren (Groq Whisper / ElevenLabs / lokales Whisper)
- Antworten via Text-to-Speech vorzulesen (Edge TTS via Python-Subprocess oder SAPI-Fallback)
- Code-Aufgaben an externe CLI-Tools weiterzureichen (Codex, Claude Code, OpenClaw)

---

## Build-System

Die App hat **kein MSBuild-Projektfile, kein Visual Studio Solution**. Sie wird direkt mit dem .NET Framework 4.x C#-Compiler (csc.exe) gebaut.

**`Build-Clicky.cmd`:**
```
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
  /nologo
  /target:winexe
  /out:Clicky.Windows.exe
  /reference:System.Windows.Forms.dll
  /reference:System.Drawing.dll
  /reference:System.Net.Http.dll
  /reference:System.Web.Extensions.dll
  /reference:Microsoft.CSharp.dll
  Clicky.Windows.cs
```

**`Start-Clicky.cmd`** prüft, ob `Clicky.Windows.exe` existiert, baut sonst nach, dann startet er die Exe.

Es gibt nur **eine einzige C#-Quelldatei**: `Clicky.Windows.cs`.  
Namespace: `ClickyWindows`  
Target Framework: .NET Framework 4.x (nicht .NET 5+)  
`[STAThread]` ist erforderlich (WinForms).

---

## Konfiguration

### `windows/.env`

Alle Secrets und Konfigurationsoptionen leben in einer `.env`-Datei neben der Exe. Das Format ist `KEY=VALUE`, Leerzeilen und `#`-Kommentare werden übersprungen. Values können optional in Anführungszeichen stehen.

| Variable | Zweck | Default |
|---|---|---|
| `GROQ_API_KEY` | Pflicht. Für Chat und STT. | – |
| `ELEVENLABS_API_KEY` | Optional. Für ElevenLabs TTS/STT. | – |
| `ELEVENLABS_VOICE_ID` | ElevenLabs Stimmen-ID | – |
| `STT_PROVIDER` | `groq` / `elevenlabs` / `whisper` | `groq` |
| `WHISPER_PYTHON` | Python-Befehl für lokales Whisper | `python` |
| `WHISPER_MODEL` | Whisper-Modell (z.B. `base`, `small`) | `base` |
| `WHISPER_LANGUAGE` | Sprachcode für STT | `de` |
| `EDGE_TTS_VOICE` | Edge TTS Stimme (z.B. `de-DE-AmalaNeural`) | `de-DE-KatjaNeural` |
| `PUSH_TO_TALK_KEY` | Globale Hotkey (Keys-Enum-Name) | `F8` |
| `CODEX_COMMAND` | Pfad zu codex.cmd | `codex.cmd` |
| `CLAUDE_CODE_COMMAND` | Pfad zu claude | `claude` |
| `CODEX_WORKDIR` | Arbeitsverzeichnis für Codex/Claude Code | `../playground` |
| `CODEX_TIMEOUT_SECONDS` | Timeout für Codex/Claude Code | `900` |
| `OPENCLAW_COMMAND` | Pfad zu openclaw | `openclaw` |
| `OPENCLAW_SESSION_KEY` | Session/Agent-ID für OpenClaw | `main` |
| `OPENCLAW_TIMEOUT_SECONDS` | Timeout für OpenClaw | `120` |
| `OPENCLAW_GATEWAY_URL` | WebSocket-URL | `ws://127.0.0.1:18789` |
| `GATEWAY_TOKEN` | Auth-Token für OpenClaw | – |

### `windows/data/settings.json`

Persistierte UI-Einstellungen. Werden beim Klick auf "save settings" geschrieben.

```json
{
  "ClaudeModel": "meta-llama/llama-4-scout-17b-16e-instruct",
  "SpeakResponses": true,
  "MaxConversationTurns": 10,
  "EdgeTtsVoice": "de-DE-AmalaNeural"
}
```

Serialisierung: `System.Web.Script.Serialization.JavaScriptSerializer` (kein Newtonsoft, kein System.Text.Json).

---

## Klassen-Übersicht

```
Program                     — Entry Point, STAThread
AppSettings                 — UI-Einstellungen (settings.json)
EnvironmentConfiguration    — .env-Parsing, Validation
ConversationTurn            — {UserTranscript, AssistantResponse}
PointTagResult              — Parsed POINT-Tag aus LLM-Antwort
ScreenCaptureInfo           — Screenshot-Metadaten + Base64-Daten
CompanionVisualState        — Enum: Idle/Listening/Transcribing/Thinking/Speaking
ScreenCaptureService        — Macht Screenshots aller Monitore
DirectApiClient             — Alle HTTP-API-Calls (Groq, ElevenLabs)
MicrophoneRecorder          — WinMM-Aufnahme via mciSendString
WhisperClient               — Lokales Whisper via Python-Subprocess
SpeechToTextClient          — Router: Groq / ElevenLabs / Whisper
CodexClient                 — Codex CLI one-shot
ClaudeCodeClient            — Claude Code CLI one-shot
OpenClawClient              — OpenClaw CLI one-shot
PushToTalkHotKeyListener    — Globaler Keyboard-Hook (SetWindowsHookEx)
CompanionOverlayForm        — Animiertes Overlay-Mascot (WinForms Form)
MainForm                    — Hauptfenster + Tray-Icon + alle Flows
```

---

## Datenfluss: Hauptinteraktion

```
Nutzer hält Taste/Button
    → MicrophoneRecorder.Start()          — mciSendString "open / record"
    → CompanionVisualState: Listening

Nutzer lässt los
    → MicrophoneRecorder.Stop()           — "stop / save" → WAV-Datei
    → SpeechToTextClient.TranscribeAsync()
        groq:       DirectApiClient.TranscribeSpeechWithGroqAsync()
        elevenlabs: DirectApiClient.TranscribeSpeechWithElevenLabsAsync()
        whisper:    WhisperClient.TranscribeAsync()
    → Transcript → _promptTextBox.Text
    → RunAskFlowAsync(transcript)

RunAskFlowAsync(prompt):
    → Trigger-Check: OpenClaw? ClaudeCode? Codex?
    → ScreenCaptureService.CaptureAllScreens()
    → DirectApiClient.AskAsync()          — Groq Vision API
    → PointTagResult.Parse(response)      — optional POINT-Tag extrahieren
    → Companion navigiert zu Koordinate
    → SpeakResponseAsync()               — Edge TTS → MP3 → WMP
```

---

## Speech-to-Text

### Groq (empfohlen)

**Endpoint:** `POST https://api.groq.com/openai/v1/audio/transcriptions`  
**Authentifizierung:** `Authorization: Bearer {GROQ_API_KEY}`  
**Modell:** `whisper-large-v3-turbo`  
**Request:** Multipart Form
- `file`: WAV-Datei (Content-Type: `audio/wav`)
- `model`: `whisper-large-v3-turbo`
- `language`: z.B. `de` (optional)
- `response_format`: `text`

**Response:** Plaintext-Transkript (kein JSON wenn `response_format=text`).

### ElevenLabs

**Endpoint:** `POST https://api.elevenlabs.io/v1/speech-to-text`  
**Authentifizierung:** `xi-api-key: {ELEVENLABS_API_KEY}`  
**Request:** Multipart Form
- `file`: WAV-Datei
- `model_id`: `scribe_v2`
- `language_code`: z.B. `de` (optional)

**Response:** JSON mit `text`-Feld (oder `words[].text` als Fallback).

### Lokales Whisper (Fallback)

Subprocess-Aufruf:
```
{WHISPER_PYTHON} -m whisper "{audiofile}" --model {model} --task transcribe
  --fp16 False --verbose False --output_format txt --output_dir {outputDir}
  [--language {lang}]
```
Liest das erzeugte `.txt`-File zurück. Aufräumen nach dem Lesen.

---

## Vision / Chat

**Endpoint:** `POST https://api.groq.com/openai/v1/chat/completions`  
**Authentifizierung:** `Authorization: Bearer {GROQ_API_KEY}`  
**Format:** OpenAI-kompatibel

### Prompt-Struktur

```json
{
  "model": "{settings.ClaudeModel}",
  "max_tokens": 1024,
  "stream": false,
  "messages": [
    { "role": "system", "content": "{SOUL.md-Inhalt}\n\n{CompanionBehaviorRules}" },
    ... (Konversationshistorie als user/assistant-Paare) ...
    {
      "role": "user",
      "content": [
        { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,{base64}" } },
        { "type": "text", "text": "{screenlabel}" },
        ... (für jeden Monitor) ...
        { "type": "text", "text": "{userPrompt}" }
      ]
    }
  ]
}
```

**System-Prompt** besteht aus zwei Teilen:
1. `SOUL.md` aus dem Repo-Root (wird live eingelesen; Fallback: hardcodierter Default-Text)
2. `CompanionBehaviorRules` — hardcodierter String mit Verhaltensregeln (Sprache, Tonalität, Element-Pointing-Protokoll, Monitoring-Regeln)

**POINT-Tag-Protokoll:**
Das Modell kann am Ende seiner Antwort einen Tag anhängen:
```
[POINT:x,y:label]          — Zeigt auf Pixel (x,y) des Cursor-Screens
[POINT:x,y:label:screenN]  — Zeigt auf Screen N
[POINT:none]               — Kein Punkt
```
`PointTagResult.Parse()` parst diesen Tag mit Regex aus der Antwort.

**Response-Parsing:** Klassisches OpenAI-Format: `choices[0].message.content` (via `JavaScriptSerializer.DeserializeObject`, kein typisiertes Deserialisieren).

### Verfügbare Modelle (in der UI konfigurierbar)

- `meta-llama/llama-4-scout-17b-16e-instruct` (Default)
- `meta-llama/llama-4-maverick-17b-128e-instruct`
- `llama-3.3-70b-versatile`
- `llama-3.2-90b-vision-preview`
- `llama-3.2-11b-vision-preview`

---

## Screenshot-System

`ScreenCaptureService.CaptureAllScreens()`:

1. `Screen.AllScreens` abfragen
2. Cursor-Position prüfen → Cursor-Screen wird auf Index 0 gesetzt (OrderBy)
3. Für jeden Screen:
   - `Graphics.CopyFromScreen()` → Bitmap
   - Skalieren auf max. 1280px in der längsten Dimension (HighQualityBicubic)
   - Als JPEG mit Quality 82 encodieren
   - `ScreenCaptureInfo` anlegen (inkl. `DisplayBounds` für spätere Koordinaten-Rückrechnung)
4. `Label`-String für jeden Screen mitschicken:
   - Cursor-Screen: `"screen 1 of 2 - cursor is on this screen (primary focus) (image dimensions: WxH pixels)"`
   - Andere: `"screen 2 of 2 - secondary screen (image dimensions: WxH pixels)"`

**Koordinaten-Rückrechnung** (`ConvertPointTagToScreenPoint`):
```
displayX = pointX * (displayBounds.Width / screenshotWidth)
displayY = pointY * (displayBounds.Height / screenshotHeight)
screenPoint = (displayBounds.Left + displayX, displayBounds.Top + displayY)
```

---

## Text-to-Speech

### Primär: Edge TTS via Python-Subprocess

```
python -m edge_tts --voice "{voice}" --text "{text}" --write-media "{mp3path}"
```

Das erzeugte MP3 wird via **Windows Media Player COM-Interface** (`WMPlayer.OCX`) abgespielt:
```csharp
dynamic wmp = Activator.CreateInstance(Type.GetTypeFromProgID("WMPlayer.OCX"));
wmp.settings.autoStart = false;
wmp.URL = filePath;
wmp.controls.play();
```

### Fallback: Windows SAPI

```csharp
dynamic voice = Activator.CreateInstance(Type.GetTypeFromProgID("SAPI.SpVoice"));
voice.Speak(text, 1);
```

**Hinweis:** Edge TTS benötigt `pip install edge-tts` und eine funktionierende Python-Installation.

---

## Mikrofonaufnahme

`MicrophoneRecorder` verwendet die **WinMM MCI API** via P/Invoke:

```csharp
[DllImport("winmm.dll")] mciSendString(string command, ...)
```

Ablauf:
```
mciSendString("open new type waveaudio alias zippyrec")
mciSendString("set zippyrec time format ms")
mciSendString("record zippyrec")
// ... Aufnahme läuft ...
mciSendString("stop zippyrec")
mciSendString("save zippyrec \"path\\to\\file.wav\"")
```

Output: WAV-Datei in `windows/data/clicky-recording-{timestamp}.wav`.  
Nach der Transkription wird die WAV-Datei gelöscht.

---

## Globaler Push-to-Talk Hotkey

`PushToTalkHotKeyListener` setzt einen **Low-Level Keyboard Hook** (`WH_KEYBOARD_LL = 13`) via `SetWindowsHookEx`. Dieser fängt alle Tastatureingaben systemweit ab, unabhängig vom Fokus.

```csharp
SetWindowsHookEx(13, hookCallback, moduleHandle, 0)
```

Im Callback: Prüfung auf `WM_KEYDOWN` / `WM_KEYUP` gegen den konfigurierten Key (`Keys.F8` default).  
Events: `HotKeyPressed`, `HotKeyReleased`.

Die `MainForm` leitet diese Events via `BeginInvoke` auf den UI-Thread weiter.

---

## CLI-Routing (Codex / Claude Code / OpenClaw)

Bevor ein Prompt an den LLM geht, prüft `RunAskFlowAsync` drei Trigger-Klassen:

### Trigger-Erkennung (Regex + Normalisierung)

Jede Klasse hat einen `TriggerRegex` und eine `NormalizePrompt()`-Methode, die typische Speech-to-Text-Fehler korrigiert (z.B. "kodex" → "codex", "cloud code" → "claude code").

| Trigger-Pattern | Klasse |
|---|---|
| `nimm (den) (codex|kodex|...)` | `CodexClient` |
| `nimm ... codex mit screen` | `CodexClient` + Screenshot |
| `nimm (den) claude code` | `ClaudeCodeClient` |
| `nimm (den) (open claw|openclaw|klaus|...)` | `OpenClawClient` |

### Codex (`CodexClient`)

```
cmd.exe /c {CODEX_COMMAND} exec --full-auto --skip-git-repo-check
  -C {workingDir} -o {outputFile} [-i {screenshotFile}] -
```

Prompt wird via `StandardInput` übergeben (UTF-8). Stdout wird in eine Textdatei in `codex output/` geschrieben.

### Claude Code (`ClaudeCodeClient`)

```
cmd.exe /c {CLAUDE_CODE_COMMAND} -p --permission-mode bypassPermissions
```

Prompt via Stdin.

### OpenClaw (`OpenClawClient`)

```
cmd.exe /c {OPENCLAW_COMMAND} agent --agent {agentId} --message {prompt} --timeout {seconds}
```

Stdout der OpenClaw-Antwort wird als Response-Text verwendet.

---

## Companion Overlay

`CompanionOverlayForm` ist ein WinForms-`Form` ohne Rahmen, das:
- `TopMost = true`
- `TransparencyKey = Color.Magenta` (chromakey-ähnliche Transparenz)
- `ShowWithoutActivation = true`
- Extended Window Styles: `WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE`
- `DoubleBuffered = true`

### Animation

Ein `Timer` mit 33ms Interval (~30 fps) ruft `AdvanceAnimationFrame()` auf:
- Bubble-Expiry prüfen (nach Zeit automatisch ausblenden)
- `_phase += 0.16f` für den Sinus-Bob-Effekt
- `_displayLocation` spring-interpoliert (`lerp`) auf Zielposition
- Zielposition: 18px neben Cursor, vertikal zentriert, am Screen-Rand geclampt
- Bubble wird links oder rechts platziert je nach Cursor-Position (> 62% Screen-Breite → links)

### Darstellung (`OnPaint`)

Alle Zeichenoperationen via `System.Drawing`:
1. **Trail**: 3 kleine Ellipsen hinter dem Orb (Richtung abhängig von Bubble-Seite)
2. **Bubble**: Abgerundetes Rechteck mit Dreieck-Zeiger zum Orb, Schattenversatz +4px
3. **State-Chip**: Kleines Label unter dem Orb (`ready` / `listening` / etc.)
4. **Companion-Body**: Orb (Glow + LinearGradient + Ring + Auge + Pupille + Antenne)
5. **State-Indikator** je nach State:
   - `Listening`: zwei Arcs um den Orb
   - `Transcribing`: gestrichelter Arc
   - `Thinking`: 3 Punkte über dem Orb
   - `Speaking`: 3 Wellen-Arcs neben dem Orb

### Akzentfarben

| State | Farbe |
|---|---|
| Idle | `RGB(88, 196, 255)` — Blau |
| Listening | `RGB(255, 124, 92)` — Orange-Rot |
| Transcribing | `RGB(255, 183, 77)` — Amber |
| Thinking | `RGB(88, 196, 255)` — Blau |
| Speaking | `RGB(93, 212, 136)` — Grün |

### Navigation

`NavigateTo(Point anchorPoint, ...)` bewegt den Companion zu einem bestimmten Bildschirmpunkt (z.B. vom LLM angezeigte Element-Position). Die Spring-Konstante erhöht sich beim Navigieren von 0.24 auf 0.30.

---

## MainForm

### Fenster

Festes Layout per absolute Pixel-Positionierung (kein Layout-Manager):
- Breite: 980px, Höhe: 760px, Mindest: 920×700
- `BackColor = RGB(11, 17, 27)` (tiefes Blau-Schwarz)
- Alle Kontrollelemente via `CreateLabel()`, `CreateTextBox()`, `CreateButton()` helper-Methoden erstellt

### Tray-Icon

`NotifyIcon` mit `ContextMenuStrip`:
- "Open Zippy" → `ShowClickyWindow()`
- "Ask About Screen" → `RunAskFlowAsync()`
- "Test APIs" → `RunWorkerTestAsync()`
- "Quit" → setzt `_quitRequested = true`, dann `Close()`

Fenster schließen ohne Quit → `Hide()` statt wirklich schließen (Tray-Verhalten).

### Konversationshistorie

`List<ConversationTurn>` mit max. `MaxConversationTurns` (Default: 10) Einträgen. Älteste werden bei Überlauf entfernt. Wird bei jedem AskAsync-Aufruf als alternating user/assistant-Paare mitgeschickt.

### Smoke Test

`DirectApiClient.SmokeTestAsync()` sendet ein Mini-Request (`max_tokens: 24`, Prompt: "say ready") und zeigt das Ergebnis an.

---

## Fehlerbehandlung

- Alle async Flows in `try/catch (Exception)` — Fehler werden via `MessageBox.Show()` angezeigt
- STT-Fehler: Status-Label + Companion-Bubble + MessageBox
- TTS-Fehler: Fallback auf SAPI
- Microphone-Fehler: Companion-Bubble
- WAV-Datei wird in `finally` gelöscht (auch bei Fehler)
- Startup-Exceptions werden in `startup-error.log` neben der Exe geschrieben

---

## Datei-Layout

```
windows/
├── Clicky.Windows.cs          — Gesamter App-Code (eine Datei)
├── Build-Clicky.cmd           — Build-Skript
├── Start-Clicky.cmd           — Build + Start
├── .env                       — Secrets (nicht in Git)
├── .env.example               — Template
├── Clicky.Windows.exe         — Build-Output (nicht in Git)
└── data/
    ├── settings.json          — UI-Einstellungen
    └── clicky-recording-*.wav — Temp-Aufnahmen (werden gelöscht)

(Repo-Root)/
├── SOUL.md                    — Editierbare Persönlichkeit des Assistenten
├── playground/                — Codex/Claude-Code Arbeitsverzeichnis (nicht in Git)
└── codex output/              — Logs von CLI-Runs (nicht in Git)
```

---

## Abhängigkeiten

| Abhängigkeit | Wozu | Installation |
|---|---|---|
| .NET Framework 4.x | Runtime | Windows-Standardkomponente |
| `edge-tts` Python-Paket | TTS | `pip install edge-tts` |
| Windows Media Player | MP3-Wiedergabe | Windows-Standardkomponente |
| SAPI | TTS-Fallback | Windows-Standardkomponente |
| WinMM | Mikrofon-Aufnahme | Windows-Standardkomponente (winmm.dll) |
| Groq API | LLM + STT | API-Key in `.env` |
| ElevenLabs API | TTS + STT (optional) | API-Key in `.env` |
| Codex CLI | Code-Ausführung (optional) | `npm install -g @openai/codex` |
| Claude Code CLI | Code-Ausführung (optional) | Anthropic Claude Code |
| OpenClaw | Agent-Ausführung (optional) | Lokale Installation |

**Keine NuGet-Pakete.** Alle Referenzen sind .NET Framework Standard-Assemblies.

---

## Sicherheitshinweise

- API-Keys leben ausschließlich in `windows/.env` (nicht committet)
- Die `.env`-Datei wird bei jedem API-Call neu eingelesen (`ReloadEnvironmentConfiguration`)
- Keine Secrets im Quellcode (nur Default-Werte für nicht-sensitive Einstellungen)
- HTTP-Timeout: 4 Minuten (`HttpClient.Timeout`)
- TLS 1.2 wird explizit in `Program.Main()` aktiviert: `ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12`
