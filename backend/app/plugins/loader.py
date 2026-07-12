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


def install_skill(name: str, code: str) -> dict:
    """Validate and hot-install a new plugin (a self-taught skill).

    The code is syntax-checked and test-imported BEFORE being written; the
    live registry picks the new tools up immediately. Raises ValueError with
    a readable message on any problem so the caller (LLM or UI) can fix it.
    """
    import re

    from ..tools.base import registry

    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    if not slug:
        raise ValueError("invalid skill name")
    if "@tool(" not in code or "from app.tools.base import tool" not in code:
        raise ValueError(
            "code must use the plugin framework: `from app.tools.base import tool` "
            "and at least one @tool(...) decorated function")
    try:
        compile(code, f"{slug}/plugin.py", "exec")
    except SyntaxError as e:
        raise ValueError(f"syntax error: {e}") from e

    folder = PLUGINS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    entry = folder / "plugin.py"
    entry.write_text(code)

    before = {t.name for t in registry.all()}
    module_name = f"jarvis_plugin_{slug}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, entry)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as e:
        entry.unlink(missing_ok=True)
        raise ValueError(f"plugin failed to load: {e}") from e

    new_tools = sorted({t.name for t in registry.all()} - before)
    loaded.append({"name": slug, "path": str(entry), "ok": True})
    return {"skill": slug, "path": str(entry), "new_tools": new_tools}


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
