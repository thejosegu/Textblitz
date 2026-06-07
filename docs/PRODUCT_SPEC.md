# Zippy — Product Spec Sheet

Abgeleitet aus dem Build-Video (Transkript `i4u_sLwTlYw`). Enthält ausschließlich softwarerelevante Informationen.

---

## 1. Produktdefinition

Zippy ist ein nativer Windows-Desktop-Assistent in Form eines animierten Cursor-Overlays. Er folgt der Maus, sieht alle angeschlossenen Bildschirme, hört auf Spracheingabe per Push-to-Talk und kann andere KI-Tools orchestrieren. Er läuft dauerhaft im System Tray und hat kein persistentes Terminalfenster.

**Kernversprechen:** Immer verfügbar, sofort startbar, alle Screens sichtbar, beliebige CLI-Tools triggerbar.

---

## 2. Technologie-Stack

| Schicht | Technologie |
|---|---|
| Programmiersprache | C# (.NET Framework 4.x) |
| UI-Framework | WinForms (native Windows) |
| Build-Tool | csc.exe direkt (kein MSBuild/Visual Studio) |
| LLM / Vision | Groq API — OpenAI-kompatibel (Chat + Vision) |
| Spracherkennung (STT) | Groq Whisper API (primär), ElevenLabs Scribe v2, lokales Whisper (Fallback) |
| Text-to-Speech (TTS) | Edge TTS via Python-Subprocess, ElevenLabs Flash v2.5, SAPI (Fallback) |
| Mikrofonaufnahme | Windows MCI API (winmm.dll, `mciSendString`) |
| Screenshot | `Graphics.CopyFromScreen` (WinForms) |
| HTTP | `System.Net.Http.HttpClient` |
| Serialisierung | `System.Web.Script.Serialization.JavaScriptSerializer` |
| Quellcode-Umfang | Exakt eine `.cs`-Datei (`Clicky.Windows.cs`) |

---

## 3. Architektur

```
User (Sprache / Text)
        │
        ▼
   Zippy (Orchestrator)
        │
        ├── Vision/Chat → Groq API (LLM mit Screenshots)
        ├── STT        → Groq Whisper / ElevenLabs / lokales Whisper
        ├── TTS        → Edge TTS / ElevenLabs / SAPI
        │
        ├── "nimm codex"       → Codex CLI (one-shot, kein persistenter Kontext)
        ├── "nimm claude code" → Claude Code CLI (one-shot, kein persistenter Kontext)
        └── "nimm openclaw"    → OpenClaw CLI (persistenter Kontext via Gateway)
```

Zippy selbst führt keinen Code aus. Er ist reiner Orchestrator: nimmt Input auf, macht Screenshots, schickt alles an die APIs und leitet Coding-Aufgaben an lokale CLI-Tools weiter.

---

## 4. Funktionen im Detail

### 4.1 Screen Vision
- Alle angeschlossenen Monitore werden gleichzeitig erfasst
- Screenshots werden auf max. 1280px skaliert und als JPEG (Qualität 82) an die API geschickt
- Cursor-Position bestimmt den "primären" Screen (bekommt höhere Priorität im Prompt)
- Das Modell kann Pixel-Koordinaten zurückgeben → Companion navigiert autonom dorthin

### 4.2 Spracheingabe (Push-to-Talk)
- Standard-Hotkey: **F8** (konfigurierbar via `.env`)
- Globaler Keyboard-Hook (`SetWindowsHookEx`, `WH_KEYBOARD_LL`) → funktioniert auch wenn Zippy-Fenster nicht im Fokus ist
- Aufnahme als WAV via WinMM MCI
- WAV wird nach der Transkription automatisch gelöscht

### 4.3 Speech-to-Text
Drei Provider, umschaltbar via `STT_PROVIDER` in `.env`:

| Provider | Modell | API |
|---|---|---|
| `groq` (Standard) | `whisper-large-v3-turbo` | `POST /openai/v1/audio/transcriptions` |
| `elevenlabs` | `scribe_v2` | `POST /v1/speech-to-text` |
| `whisper` | konfigurierbar (z.B. `base`, `small`) | lokaler Python-Subprocess |

### 4.4 Regex-Normalisierung von STT-Fehlern
STT-Modelle transkribieren Triggerwörter nicht immer exakt. Zippy normalisiert bekannte Fehler vor dem Trigger-Matching:

| Erkannter Fehler | Normalisiert zu |
|---|---|
| `kodex`, `kodes`, `codecs`, `kodexx` | `codex` |
| `nehm` | `nimm` |
| `cloud code`, `clod code`, `klod code` | `claude code` |
| `open claw`, `open clau`, `openclo`, `orpen claw`, `oppen claw`, `claus`, `claws`, `klaus` | `openclaw` |

### 4.5 CLI-Routing / Handoffs
Trigger-Erkennung läuft vor jedem LLM-Call. Die erkannten Präfixe werden aus dem Prompt entfernt; nur der eigentliche Auftrag wird weitergeleitet.

| Trigger-Phrase | Ziel | Persistenter Kontext |
|---|---|---|
| `nimm codex` | Codex CLI | Nein (jede Session neu) |
| `nimm codex mit screen` | Codex CLI + Screenshot(s) | Nein |
| `nimm claude code` | Claude Code CLI | Nein (jede Session neu) |
| `nimm openclaw` / `nimm klaus` | OpenClaw CLI via Gateway | Ja (Gateway-Session) |

**Codex-Aufruf:**
```
codex.cmd exec --full-auto --skip-git-repo-check -C {workdir} -o {logfile} [-i {screenshot}] -
```
Prompt via stdin.

**Claude Code-Aufruf:**
```
claude -p --permission-mode bypassPermissions
```
Prompt via stdin.

**OpenClaw-Aufruf:**
```
openclaw agent --agent {agentId} --message {prompt} --timeout {seconds}
```

Logs aller CLI-Runs werden in `codex output/` gespeichert.  
CLI-Outputs (generierte Dateien) landen im `playground/`-Verzeichnis.

### 4.6 Text-to-Speech
Primär: Edge TTS via `python -m edge_tts --voice ... --write-media ... .mp3`, Wiedergabe über Windows Media Player COM (`WMPlayer.OCX`). Fallback: `SAPI.SpVoice`.

### 4.7 Persönlichkeit / System-Prompt
- `SOUL.md` im Repo-Root wird zur Laufzeit eingelesen und als System-Prompt-Prefix verwendet
- Fallback: hardcodierter Default-Prompt im Binary
- Verhaltensregeln: keine Füllwörter, präzise Antworten, eigene Meinungen, Deutsch als Standardsprache
- Easter Egg: "Hey Zippy" → "Hey Meister, stehts zu Diensten"

### 4.8 Companion Overlay
- Chromakey-Transparenz (`TransparencyKey = Magenta`)
- `TopMost`, kein Taskbar-Eintrag, click-through (`WS_EX_TRANSPARENT`)
- Spring-Interpolation: folgt dem Cursor mit einstellbarer Dämpfung
- Navigiert autonom zu vom Modell zurückgegebenen Bildschirmkoordinaten

**Visuelle Zustände:**

| State | Farbe | Indikator |
|---|---|---|
| Idle/Ready | Blau `#58C4FF` | — |
| Listening | Orange-Rot `#FF7C5C` | Arcs um den Orb |
| Transcribing | Amber `#FFB74D` | gestrichelter Arc |
| Thinking | Blau `#58C4FF` | 3 Punkte oben |
| Speaking | Grün `#5DD488` | Wellenarcs seitlich |

---

## 5. Konfiguration (`.env`)

Pflichtfelder für Basisbetrieb:

| Variable | Beschreibung |
|---|---|
| `GROQ_API_KEY` | Groq API Key (Chat + STT) |
| `ELEVENLABS_API_KEY` | ElevenLabs API Key (TTS/STT, optional wenn Edge TTS genutzt) |
| `ELEVENLABS_VOICE_ID` | ElevenLabs Stimmen-ID |

Optionale Felder:

| Variable | Default | Beschreibung |
|---|---|---|
| `STT_PROVIDER` | `groq` | `groq` / `elevenlabs` / `whisper` |
| `PUSH_TO_TALK_KEY` | `F8` | Beliebige `Keys`-Enum-Werte |
| `EDGE_TTS_VOICE` | `de-DE-KatjaNeural` | Edge TTS Stimme |
| `CODEX_COMMAND` | `codex.cmd` | Pfad zur Codex-Executable |
| `CLAUDE_CODE_COMMAND` | `claude` | Pfad zur Claude Code-Executable |
| `CODEX_WORKDIR` | `../playground` | Arbeitsverzeichnis für Codex/Claude Code |
| `CODEX_TIMEOUT_SECONDS` | `900` | Timeout für Codex- und Claude Code-Sessions |
| `OPENCLAW_COMMAND` | `openclaw` | Pfad zur OpenClaw-Executable |
| `OPENCLAW_SESSION_KEY` | `main` | Session/Agent-ID |
| `OPENCLAW_GATEWAY_URL` | `ws://127.0.0.1:18789` | OpenClaw Gateway WebSocket |
| `GATEWAY_TOKEN` | — | Auth-Token für OpenClaw |
| `OPENCLAW_TIMEOUT_SECONDS` | `120` | Timeout für OpenClaw |
| `WHISPER_PYTHON` | `python` | Python-Befehl für lokales Whisper |
| `WHISPER_MODEL` | `base` | Whisper-Modell |
| `WHISPER_LANGUAGE` | `de` | Sprachcode |

---

## 6. Modellauswahl

In der UI konfigurierbar (Dropdown), gespeichert in `settings.json`:

| Modell | Empfehlung |
|---|---|
| `meta-llama/llama-4-scout-17b-16e-instruct` | Standard |
| `meta-llama/llama-4-maverick-17b-128e-instruct` | — |
| `llama-3.3-70b-versatile` | — |
| `llama-3.2-90b-vision-preview` | — |
| `llama-3.2-11b-vision-preview` | — |

Für vollständig lokalen Betrieb: Ollama mit Gemma 4 (30B) oder Qwen 3.5 (30B, Vision erforderlich).

---

## 7. Build & Start

```
windows/Build-Clicky.cmd   → kompiliert Clicky.Windows.exe via csc.exe
windows/Start-Clicky.cmd   → baut falls nötig, startet dann die Exe
```

Keine NuGet-Abhängigkeiten. Alle Referenzen sind .NET Framework Standard-Assemblies.

---

## 8. Datei-Layout

```
(Repo-Root)/
├── SOUL.md                  — Persönlichkeits-Prompt (editierbar, live eingelesen)
├── AGENTS.md                — Anweisungen für Coding Agents (Codex, Claude Code)
├── CLAUDE.md                — zeigt auf AGENTS.md
├── playground/              — Outputs von Codex/Claude Code (nicht in Git)
└── codex output/            — Logs aller CLI-Runs (nicht in Git)

windows/
├── Clicky.Windows.cs        — Gesamter App-Code (eine Datei)
├── Build-Clicky.cmd
├── Start-Clicky.cmd
├── .env                     — Secrets (nicht in Git)
├── .env.example             — Template
└── data/
    └── settings.json        — UI-Einstellungen (Modell, Stimme, TTS an/aus)
```

---

## 9. Aktuelle Einschränkungen

| Einschränkung | Detail |
|---|---|
| Nur Windows | Native WinForms-App, kein Installer |
| Kein persistenter Codex/Claude Code Kontext | Jede Session startet neu; nur OpenClaw hat persistenten Kontext via Gateway |
| Screenshot-Anhang nur für Codex | Claude Code und OpenClaw erhalten aktuell keine Screenshots |
| TTS benötigt Python | Edge TTS via `python -m edge_tts`; SAPI als Fallback |
| Trigger nur auf Deutsch | Triggerwörter sind auf deutsche Aussprache ausgelegt (`nimm codex`, `nimm claude code`, `nimm openclaw`) |

---

## 10. Lokaler Vollbetrieb (experimentell)

Alle Cloud-Abhängigkeiten können ersetzt werden:

| Komponente | Cloud-Variante | Lokale Alternative |
|---|---|---|
| LLM/Vision | Groq API | Ollama + Gemma 4 / Qwen 3.5 (30B, mit Vision) |
| STT | Groq Whisper / ElevenLabs | lokales Whisper (`STT_PROVIDER=whisper`) |
| TTS | ElevenLabs / Edge TTS | beliebiges lokales TTS-Modell |
| Coding-Agents | Codex CLI / Claude Code | lokale Modelle in Codex/Claude Code konfigurierbar |

Hinweis aus dem Video: Lokaler Betrieb wurde getestet, war aber auf der verwendeten Hardware zu langsam.

---

## 11. Prompt Engineering

- **CompanionBehaviorRules** (hardcodiert): alles lowercase, Deutsch als Default, keine Listen/Markdown, kurze Antworten (1–2 Sätze), keine Füllphrasen
- **SOUL.md** (extern, editierbar): Persönlichkeit, Grenzen, Signatur-Antworten
- **Konversationshistorie**: max. 10 Turns (konfigurierbar), älteste werden bei Überlauf entfernt
- **POINT-Tag-Protokoll**: Modell kann `[POINT:x,y:label]` oder `[POINT:x,y:label:screenN]` an Antwortende anhängen → Companion navigiert zu dieser Bildschirmposition

---

## 12. Lizenz & Open Source

MIT-Lizenz. Repository auf GitHub. Vollständig Open Source.
