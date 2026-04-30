# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Blitztext — builds a portable Windows tray app."""

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
import sys
import os

# ---------------------------------------------------------------------------
# Paths  (spec is executed with globals; __file__ is not available)
# ---------------------------------------------------------------------------
BASE = os.path.abspath(os.path.dirname(os.path.normcase(os.sys.argv[-1])))

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(BASE, "blitztext.pyw")],
    pathex=[BASE],
    binaries=[],
    datas=[
        # Runtime assets (fonts, icons, default config)
        (os.path.join(BASE, "assets"), "assets"),
    ],
    hiddenimports=[
        # Core runtime imports
        "openai",
        "groq",
        "pystray",
        "pynput",
        "sounddevice",
        "numpy",
        "pyperclip",
        "sv_ttk",
        "PIL",
        "dotenv",
        # faster-whisper pulls in ctranslate2/av/torch at runtime
        "faster_whisper",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy ML frameworks that faster-whisper may pull in but we don't need
        "torch",
        "torchvision",
        "torchaudio",
        "tensorflow",
        "tensorboard",
        "transformers",
        "matplotlib",
        "scipy",
        "pandas",
        "sklearn",
        "pytest",
        "unittest",
        "pydoc",
        "tkinter.test",
        "IPython",
        "jupyter",
        "notebook",
        "cv2",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Single-folder build (recommended for tray apps — faster startup than onefile)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Blitztext",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # --windowed  (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(os.path.join(BASE, "assets", "icon.ico")
          if os.path.isfile(os.path.join(BASE, "assets", "icon.ico"))
          else None),
)
