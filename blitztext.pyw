"""Konsolenloser Einstiegspunkt für Blitztext.

Starte mit: pythonw blitztext.pyw  (oder Doppelklick)
stdout/stderr werden in blitztext.log umgeleitet.
"""
import sys
import os

# Im frozen Build zeigt __file__ ins Temp-Verzeichnis — sys.executable zeigt auf die EXE.
if getattr(sys, "frozen", False):
    _base = os.path.dirname(sys.executable)
else:
    _base = os.path.dirname(os.path.abspath(__file__))

# Optionaler libs\-Ordner neben der EXE für externe Pakete (z.B. faster-whisper).
_libs = os.path.join(_base, "libs")
if os.path.isdir(_libs) and _libs not in sys.path:
    sys.path.insert(0, _libs)
    # Native DLLs der libs-Pakete registrieren
    # av legt FFmpeg-DLLs in av.libs/ ab (auditwheel-Konvention), nicht in av/
    for _pkg in ("ctranslate2", "av.libs"):
        _pkg_dir = os.path.join(_libs, _pkg)
        if os.path.isdir(_pkg_dir):
            os.add_dll_directory(_pkg_dir)

# Logdatei neben der EXE / dem Skript
_log = open(os.path.join(_base, "blitztext.log"), "a", encoding="utf-8", buffering=1)
sys.stdout = _log
sys.stderr = _log

from main import main
main()
