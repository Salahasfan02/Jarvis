"""Terminal, screen and camera tools."""
from __future__ import annotations

import asyncio
import base64
import datetime
import subprocess
import tempfile
from pathlib import Path

from ...config import settings
from ..base import tool


@tool(
    name="run_command",
    description="Run a shell command in the user's terminal environment and return its "
                "output. Use for developer tasks the user asked for.",
    parameters={
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
    risk="dangerous",
    agent_tags=["coding", "automation"],
)
def run_command(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True,
                            timeout=60, cwd=str(Path.home()))
    out = (result.stdout + result.stderr).strip()
    return f"exit code {result.returncode}\n{out[:8000]}" if out else f"exit code {result.returncode}"


@tool(
    name="current_datetime",
    description="Get the current local date and time.",
    parameters={"type": "object", "properties": {}},
)
def current_datetime() -> str:
    return datetime.datetime.now().strftime("%A, %B %d %Y, %H:%M:%S")


@tool(
    name="calculator",
    description="Evaluate a mathematical expression, e.g. '2**10 + 5' or 'round(17.5 * 0.0825, 2)'.",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
)
def calculator(expression: str) -> str:
    import math
    allowed = {name: getattr(math, name) for name in dir(math) if not name.startswith("_")}
    allowed.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
    try:
        result = eval(compile(expression, "<calc>", "eval"), {"__builtins__": {}}, allowed)
        return str(result)
    except Exception as e:
        return f"Could not evaluate: {e}"


async def _describe_image(path: Path, question: str) -> str:
    """Send an image to the configured multimodal model."""
    from ...llm import ollama_client
    vision_model = settings.get("ollama.vision_model", "")
    if not vision_model:
        return ("Image captured at " + str(path) + ", but no vision model is configured. "
                "Set one in Settings (e.g. pull 'llava' or 'llama3.2-vision').")
    img_b64 = base64.b64encode(path.read_bytes()).decode()
    text = await ollama_client.chat_once(
        [{"role": "user", "content": question, "images": [img_b64]}],
        model=vision_model)
    return text or "The vision model returned no description."


@tool(
    name="screen_look",
    description="Capture the user's screen and describe what's on it, or answer a "
                "question about it. Requires Screen Recording permission for the app.",
    parameters={
        "type": "object",
        "properties": {"question": {"type": "string",
                                    "description": "what to look for; default: describe the screen"}},
    },
    risk="confirm",
    agent_tags=["vision"],
)
async def screen_look(question: str = "Describe what is on this screen.") -> str:
    path = Path(tempfile.mkstemp(suffix=".png")[1])
    proc = await asyncio.create_subprocess_exec("screencapture", "-x", str(path))
    await proc.wait()
    if not path.exists() or path.stat().st_size == 0:
        return "Screen capture failed — check Screen Recording permission in System Settings."
    try:
        return await _describe_image(path, question)
    finally:
        path.unlink(missing_ok=True)


@tool(
    name="camera_look",
    description="Take a photo with the webcam and describe what the camera sees, or "
                "answer a question about it. Requires the 'imagesnap' utility "
                "(brew install imagesnap) and camera permission.",
    parameters={
        "type": "object",
        "properties": {"question": {"type": "string",
                                    "description": "what to look for; default: describe the view"}},
    },
    risk="confirm",
    agent_tags=["vision"],
)
async def camera_look(question: str = "Describe what you see.") -> str:
    path = Path(tempfile.mkstemp(suffix=".jpg")[1])
    try:
        proc = await asyncio.create_subprocess_exec(
            "imagesnap", "-w", "1.5", str(path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
    except FileNotFoundError:
        return "Camera capture needs the 'imagesnap' utility. Install it with: brew install imagesnap"
    if not path.exists() or path.stat().st_size == 0:
        return "Camera capture failed — check camera permission."
    try:
        return await _describe_image(path, question)
    finally:
        path.unlink(missing_ok=True)


@tool(
    name="remember",
    description="Save a fact to long-term memory so it persists across conversations. "
                "Use when the user shares preferences, projects, contacts, goals, or "
                "says 'remember that...'.",
    parameters={
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "a single self-contained fact"},
            "category": {"type": "string",
                         "description": "preference | project | contact | goal | general"},
        },
        "required": ["fact"],
    },
)
async def remember(fact: str, category: str = "general") -> str:
    from ...memory import store
    await store.save(fact, category)
    return f"Remembered: {fact}"
