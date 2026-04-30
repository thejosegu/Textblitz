#!/usr/bin/env python3
"""Build script for a portable Blitztext Windows executable.

Usage:
    python build.py

Requirements:
    pip install pyinstaller

Output:
    dist/Blitztext/Blitztext.exe   — portable folder, copy anywhere
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _ensure_assets():
    """Create assets/ folder with a minimal embedded font if missing."""
    assets = _repo_root() / "assets"
    assets.mkdir(exist_ok=True)

    # Minimal placeholder: if no font.ttf exists, try to copy a system font
    font_target = assets / "font.ttf"
    if not font_target.exists():
        for src in [
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path(r"C:\Windows\Fonts\arial.ttf"),
        ]:
            if src.exists():
                shutil.copy2(src, font_target)
                print(f"[build] copied font → {font_target}")
                break
        else:
            print("[build] WARNING: no system font found — tray icons may use default font")

    # Placeholder icon (PyInstaller will warn but still build if missing)
    icon_target = assets / "icon.ico"
    if not icon_target.exists():
        print("[build] NOTE: no assets/icon.ico found — EXE will use default icon")


def _clean():
    """Remove previous build artefacts."""
    root = _repo_root()
    for name in ("build", "dist"):
        path = root / name
        if path.exists():
            shutil.rmtree(path)
            print(f"[build] removed {name}/")


def _run_pyinstaller():
    """Invoke PyInstaller with the spec file."""
    spec = _repo_root() / "Blitztext.spec"
    cmd = [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"]
    print(f"[build] running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _post_build():
    """Copy runtime files into dist/ so the folder is truly portable."""
    root = _repo_root()
    dist = root / "dist"

    # When using a single-file EXE spec, dist/ contains Blitztext.exe directly.
    # When using a single-directory spec, dist/ contains Blitztext/ folder.
    exe_file = dist / "Blitztext.exe"
    if exe_file.exists():
        print(f"[build] done — portable build is in: {dist}")
        print(f"[build] EXE: {exe_file}")
        print("[build] zip that folder and distribute it.")
        return

    # Single-directory fallback
    dist_dir = dist / "Blitztext"
    if dist_dir.exists():
        config_src = root / "config.json"
        if config_src.exists():
            shutil.copy2(config_src, dist_dir / "config.json")
            print("[build] copied config.json → dist/Blitztext/")
        print(f"[build] done — portable build is in: {dist_dir}")
        print("[build] zip that folder and distribute it.")
        return

    print("[build] WARNING: dist output not found — check build log above")


def main():
    try:
        import PyInstaller
    except ImportError:
        print("[build] ERROR: PyInstaller is not installed.")
        print("[build] Run:  pip install pyinstaller")
        sys.exit(1)

    _ensure_assets()
    _clean()
    _run_pyinstaller()
    _post_build()


if __name__ == "__main__":
    main()
