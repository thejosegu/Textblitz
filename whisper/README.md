# Whisper-Modell für Blitztext4Win

Blitztext4Win verwendet das **faster-whisper-small** Modell von Systran für die Spracherkennung.

## Modell herunterladen

Das Modell wird beim ersten Start automatisch von Hugging Face heruntergeladen und hier im `whisper/`-Ordner gespeichert:

- **Modell:** `Systran/faster-whisper-small`
- **Hugging Face:** https://huggingface.co/Systran/faster-whisper-small
- **Framework:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2-basiert)

## Manueller Download (optional)

Falls der automatische Download nicht funktioniert (z. B. in Offline-Umgebungen), kann das Modell manuell heruntergeladen und hier abgelegt werden:

```bash
# Mit huggingface_hub
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', cache_dir='./whisper')"
```

Die erwartete Verzeichnisstruktur:

```
whisper/
├── models--Systran--faster-whisper-small/
│   ├── refs/
│   │   └── main
│   └── snapshots/
│       └── <commit-hash>/
│           ├── model.bin          (~461 MB)
│           ├── tokenizer.json
│           └── vocabulary.txt
└── README.md
```

> **Hinweis:** Die `model.bin`-Datei ist ca. 461 MB groß und wird **nicht** im Git-Repository versioniert. Sie wird bei Bedarf automatisch heruntergeladen.
