#!/usr/bin/env python3
"""Convenience entry point for starting the demo from the web directory."""

from pathlib import Path
import runpy
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
runpy.run_path(str(PROJECT_ROOT / "run_demo.py"), run_name="__main__")
