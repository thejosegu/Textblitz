# C# Runtime Findings

Stand: 2026-05-05

## Wichtigste Erkenntnisse

- Die C#-App benutzt nicht die Repo-Konfiguration, sondern `%APPDATA%\Blitztext\config.json`.
- Mehrere vermeintliche Toggle-Probleme waren in Wahrheit Modus-Diskrepanzen zwischen Repo-`config.json` und der echten Laufzeit-Config.
- Tray-Status und Overlay konnten auseinanderlaufen, wenn UI-Updates asynchron eingeplant wurden.
- Ein Teil der Startprobleme lag nicht im Recorder, sondern im Hotkey-Zustand (`_activeMode`, Debounce, Auto-Repeat, Start-Fehler-Rollback).
- Das lokale Whisper-Setup ist inzwischen robust genug fuer echten Live-Betrieb, auch mit mehreren Aufnahmen hintereinander.

## Konkrete Ursachen

### 1. Falsche aktive Config

Die C#-App liest aus:

`C:\Users\Sebastian\AppData\Roaming\Blitztext\config.json`

Nicht aus:

`f:\90 Projekte\Blitztext\config.json`

Folge:

- Tests wurden teilweise als `toggle` interpretiert, waehrend die laufende App real im Modus `hold` war.
- Debugging-Ergebnisse wirkten dadurch widerspruechlich, obwohl der Code korrekt reagierte.

### 2. Start/Stop-Race in der Aufnahme-Orchestrierung

Frueher konnte `Stop` eintreffen, waehrend `Start()` intern noch den Recorder initialisierte.

Folgen:

- `Aufnahme sofort gestoppt (stop war vor start angekommen)`
- `Already recording`
- Semaphore-Fehler durch inkonsistente Start/Stop-Sequenzen

Das wurde in `BlitztextApp` abgesichert, indem der Startzustand explizit verfolgt und Stop waehrend des Startfensters nur vorgemerkt wird.

### 3. Recorder blieb teilweise intern haengen

`WaveInEvent` konnte nach `StopRecording()` in einem haengenden Zustand bleiben, wenn `RecordingStopped` nicht sauber oder zu spaet kam.

Folgen:

- `AudioRecorder.Start: Warten auf RecordingStopped Timeout`
- `Mikrofon-Fehler beim Starten: Already recording`

Der Recorder initialisiert das Device jetzt neu, wenn Stop/Idle-Timeouts auftreten.

### 4. Toggle und Auto-Repeat

Ein gehaltener Hotkey konnte durch wiederholte `KeyDown`-Events erneut verarbeitet werden.

Folge:

- Aufnahme startete und wurde sofort wieder beendet.

Der Listener ignoriert jetzt wiederholte `KeyDown`-Events fuer bereits gedrueckte Tasten.

### 5. Toggle-Zustand bei fehlgeschlagenem Start

Wenn ein Startversuch abgewiesen wurde, konnte der Listener intern trotzdem denken, eine Aufnahme sei aktiv.

Folge:

- Der naechste Tastendruck wurde erst als Stop verbraucht.
- Das fuehlte sich an wie: "Start geht oft erst beim zweiten Klick".

Der Listener setzt den aktiven Modus jetzt nur noch kontrolliert und rollt ihn bei fehlgeschlagenem Start sauber zurueck.

### 6. Kurze Toggle-Taps gingen verloren

Durch den 50-ms-Debounce konnte ein sehr kurzer Tap wieder invalidiert werden, bevor `TryTrigger()` lief.

Folge:

- Beim ersten kurzen Druck passierte manchmal scheinbar gar nichts.

Fuer Toggle startet die Aufnahme jetzt auch beim `KeyUp`, wenn der kurze Tap den Debounce sonst verpasst haette.

## Wirksame Fixes

- Start/Stop-Race in der Orchestrierung abgesichert
- Recorder-Reset bei haengendem `WaveInEvent`
- Overlay-Updates wieder synchron zum Tray-Status
- Wiederholte `KeyDown`-Events gefiltert
- Toggle-Zustand nur nach echtem Start stabilisiert
- Kurze Toggle-Taps beim Loslassen abgefangen
- Startup-Logeintrag fuer den effektiven Aufnahmemodus eingefuehrt

## Woran man den echten Zustand erkennt

Im Log steht jetzt direkt nach dem Start explizit:

- `Aufnahmemodus: hold`
- oder `Aufnahmemodus: toggle`

Damit laesst sich sofort erkennen, welcher Modus wirklich aktiv ist.

Logdatei:

`C:\Users\Sebastian\AppData\Roaming\Blitztext\blitztext.log`

## Aktueller Stand

- Aufnahme und Stop verhalten sich im Live-Betrieb deutlich stabiler als zu Beginn.
- Das lokale Modell wirkt praxistauglich und robust.
- Die verbleibenden Themen liegen eher im Feintuning als in einem fundamentalen Architekturfehler.

## Sinnvolle naechste Feinschliffe

- gezieltere Statusmeldungen fuer Start, Recording, Processing, Inject
- eventuell noch weniger aggressive Debounce- bzw. Toggle-Logik fuer Single-Key-Hotkeys
- Logging fuer Key-Hook-Zustaende nur bei Diagnose-Builds zuschaltbar machen
- Verhalten mit unterschiedlichen Hotkeys testen, vor allem Single-Key vs. Multi-Key

## Publish-Varianten

Es gibt jetzt zwei C#-Publish-Profile fuer die lokale Whisper-Variante:

- `LocalPortable`: self-contained, single-file, portable, groesser
- `LocalSlim`: framework-dependent, single-file, kleiner, braucht installierte .NET Desktop Runtime

Beide behalten die lokale Whisper-Funktionalitaet.

Beispiele:

```powershell
dotnet publish -c Release /p:PublishProfile=LocalPortable
dotnet publish -c Release /p:PublishProfile=LocalSlim
```