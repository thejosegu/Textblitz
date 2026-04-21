# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Spec für Textblitz
# Build: python -m PyInstaller textblitz.spec

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# sv_ttk Theme-Dateien (TCL + PNG)
sv_ttk_datas = collect_data_files("sv_ttk")

a = Analysis(
    ["textblitz.pyw"],
    pathex=["."],
    binaries=[],
    datas=sv_ttk_datas,
    hiddenimports=[
        # pynput braucht die Backend-Implementierungen explizit
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # pystray Windows-Backend
        "pystray._win32",
        # tkinter
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        # sounddevice
        "sounddevice",
        "cffi",
        "_cffi_backend",
        # weitere
        "winreg",
        "PIL._tkinter_finder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Nicht benötigt — spart mehrere MB
        "unittest", "email", "html", "http", "urllib",
        "xml", "xmlrpc", "pydoc", "doctest",
        "difflib", "calendar", "csv", "ftplib",
        "imaplib", "poplib", "smtplib", "telnetlib",
        "turtle", "curses", "readline",
        "rich", "pygments",            # von openai/groq mitgezogen, aber nicht angezeigt
        "faster_whisper", "ctranslate2", "huggingface_hub", "tokenizers",  # separat installieren
        "matplotlib", "pandas",       # falls versehentlich gezogen
        "scipy", "sklearn",
        "IPython", "jupyter",
        "tkinter.test",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Textblitz",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,            # UPX-Komprimierung (~halbe Dateigröße); upx.exe muss im PATH oder Projektordner liegen
    console=False,       # kein Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",   # optional: .ico-Datei für die EXE
)
