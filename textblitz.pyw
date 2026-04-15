"""Konsolenloser Einstiegspunkt für Textblitz.

Starte mit: pythonw textblitz.pyw  (oder Doppelklick)
stdout/stderr werden in textblitz.log umgeleitet.
"""
import sys
import os

# Logdatei im selben Verzeichnis wie dieses Skript
_base = os.path.dirname(os.path.abspath(__file__))
_log  = open(os.path.join(_base, "textblitz.log"), "a", encoding="utf-8", buffering=1)
sys.stdout = _log
sys.stderr = _log

# Ab hier normaler Start
from main import main
main()
