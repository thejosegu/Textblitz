# Blitztext4Win

Spracherkennung per Hotkey für Windows. Drücken, sprechen, loslassen – der transkribierte Text erscheint an der aktuellen Cursorposition.

## Installation

```bash
pip install -r requirements.txt
pythonw blitztext.pyw
```

Oder die fertige EXE aus `dist/Blitztext.exe` starten.

## Hinweise

- **Einstellungsfenster muss geschlossen sein**: Die Texterkennung funktioniert nur, wenn das Einstellungsfenster (Rechtsklick auf Tray-Icon → *Einstellungen*) geschlossen ist. Während das Fenster geöffnet ist, werden Hotkeys nicht verarbeitet.

- **Erste Transkription mit lokalem Modell**: Wenn das lokale Whisper-Modell (*faster-whisper*) als Transkriptions-Engine ausgewählt ist, kommt es bei der **allerersten** Transkription zu einer Verzögerung von **bis zu 5 Minuten**. In dieser Zeit wird das Sprachmodell (~500 MB) aus dem Internet heruntergeladen. Dies ist kein Bug, sondern einmalig pro Installation. Alle weiteren Transkriptionen starten sofort.

## Bedienungsanleitung

Siehe [docs/Benutzerhandbuch.md](docs/Benutzerhandbuch.md) für die vollständige Anleitung.
