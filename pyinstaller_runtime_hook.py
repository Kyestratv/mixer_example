"""Runtime path setup for PyInstaller builds that bundle Tcl/Tk data."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bundle_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(sys.executable).resolve().parent


runtime_tcl = _bundle_root() / "runtime_tcl"
tcl_dir = runtime_tcl / "tcl8.6"
tk_dir = runtime_tcl / "tk8.6"

if tcl_dir.exists():
    os.environ["TCL_LIBRARY"] = str(tcl_dir)
if tk_dir.exists():
    os.environ["TK_LIBRARY"] = str(tk_dir)
