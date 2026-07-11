"""Plugin loader.

A plugin is a folder containing plugin.py. Inside it, use the same @tool
decorator as built-in tools (and optionally register Agents). Plugins are
loaded from the repo's plugins/ folder and from ~/.jarvis/plugins, so users
can add capabilities without rebuilding the app.

    # ~/.jarvis/plugins/hello/plugin.py
    from app.tools.base import tool

    @tool(name="hello", description="Say hello",
          parameters={"type": "object", "properties": {}})
    def hello() -> str:
        return "Hello from a plugin!"
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from ..config import PLUGINS_DIR

REPO_PLUGINS = Path(__file__).resolve().parents[3] / "plugins"

loaded: list[dict] = []


def load_all() -> list[dict]:
    loaded.clear()
    for base in (REPO_PLUGINS, PLUGINS_DIR):
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            entry = folder / "plugin.py"
            if not entry.is_file():
                continue
            name = f"jarvis_plugin_{folder.name}"
            try:
                spec = importlib.util.spec_from_file_location(name, entry)
                module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
                sys.modules[name] = module
                spec.loader.exec_module(module)  # type: ignore[union-attr]
                loaded.append({"name": folder.name, "path": str(entry), "ok": True})
            except Exception as e:
                loaded.append({"name": folder.name, "path": str(entry),
                               "ok": False, "error": str(e)})
    return loaded
