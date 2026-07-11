"""Filesystem tools. Reads are safe; writes/moves ask for confirmation;
deletion is always confirmed and only moves items to the Trash (never a
permanent delete)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..base import tool


def _expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


@tool(
    name="list_directory",
    description="List files and folders in a directory. Path supports ~ for home.",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "directory path, e.g. ~/Desktop"}},
        "required": ["path"],
    },
    agent_tags=["files"],
)
def list_directory(path: str) -> str:
    p = _expand(path)
    if not p.is_dir():
        return f"Not a directory: {p}"
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    lines = [f"{'[dir] ' if e.is_dir() else ''}{e.name}" for e in entries[:200]]
    return f"{p} ({len(entries)} items):\n" + "\n".join(lines)


@tool(
    name="read_file",
    description="Read a text file's contents (first 10000 characters).",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    agent_tags=["files", "coding"],
)
def read_file(path: str) -> str:
    p = _expand(path)
    if not p.is_file():
        return f"Not a file: {p}"
    try:
        return p.read_text(errors="replace")[:10000]
    except OSError as e:
        return f"Could not read file: {e}"


@tool(
    name="write_file",
    description="Write text content to a file, creating it if needed.",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
    risk="confirm",
    agent_tags=["files", "coding"],
)
def write_file(path: str, content: str) -> str:
    p = _expand(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} characters to {p}"


@tool(
    name="create_folder",
    description="Create a folder (and any missing parent folders).",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    agent_tags=["files"],
)
def create_folder(path: str) -> str:
    p = _expand(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"Created folder {p}"


@tool(
    name="move_file",
    description="Move or rename a file or folder.",
    parameters={
        "type": "object",
        "properties": {"source": {"type": "string"}, "destination": {"type": "string"}},
        "required": ["source", "destination"],
    },
    risk="confirm",
    agent_tags=["files"],
)
def move_file(source: str, destination: str) -> str:
    src, dst = _expand(source), _expand(destination)
    if not src.exists():
        return f"Source does not exist: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Moved {src} -> {dst}"


@tool(
    name="trash_file",
    description="Move a file or folder to the macOS Trash (recoverable delete).",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    risk="dangerous",
    agent_tags=["files"],
)
def trash_file(path: str) -> str:
    p = _expand(path)
    if not p.exists():
        return f"Path does not exist: {p}"
    script = f'tell application "Finder" to delete POSIX file "{p}"'
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return f"Failed to trash: {result.stderr.strip()}"
    return f"Moved {p} to Trash"


@tool(
    name="search_files",
    description="Search for files by name using Spotlight (mdfind).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "file name or part of it"},
            "directory": {"type": "string", "description": "optional folder to limit the search to"},
        },
        "required": ["query"],
    },
    agent_tags=["files"],
)
def search_files(query: str, directory: str = "") -> str:
    cmd = ["mdfind", "-name", query]
    if directory:
        cmd += ["-onlyin", str(_expand(directory))]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    lines = result.stdout.strip().splitlines()[:30]
    return "\n".join(lines) if lines else "No files found."
