"""Async client for the Ollama HTTP API.

Model-agnostic by design: every call takes the model name from settings at
call time, so switching models in the settings page takes effect on the next
message without restarting anything.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from ..config import settings


class OllamaError(RuntimeError):
    pass


def _host() -> str:
    return settings.get("ollama.host", "http://localhost:11434").rstrip("/")


def _options() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "temperature": settings.get("ollama.temperature", 0.7),
        "num_ctx": settings.get("ollama.num_ctx", 8192),
    }
    num_gpu = settings.get("ollama.num_gpu", -1)
    if num_gpu is not None and num_gpu >= 0:
        opts["num_gpu"] = num_gpu
    return opts


async def is_up() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{_host()}/api/version")
            return r.status_code == 200
    except httpx.HTTPError:
        return False


async def list_models() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_host()}/api/tags")
        r.raise_for_status()
        return r.json().get("models", [])


async def delete_model(name: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request("DELETE", f"{_host()}/api/delete", json={"model": name})
        r.raise_for_status()


async def pull_model(name: str) -> AsyncIterator[dict]:
    """Stream pull progress events."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{_host()}/api/pull",
                                 json={"model": name}) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line.strip():
                    yield json.loads(line)


async def chat_stream(messages: list[dict], model: str | None = None,
                      tools: list[dict] | None = None) -> AsyncIterator[dict]:
    """Stream chat chunks. Yields the raw Ollama chunk dicts.

    Text chunks arrive as {"message": {"content": "..."}}; tool calls arrive
    as {"message": {"tool_calls": [...]}} (Ollama emits those non-streamed).
    """
    payload: dict[str, Any] = {
        "model": model or settings.get("ollama.model"),
        "messages": messages,
        "stream": True,
        "options": _options(),
        "keep_alive": settings.get("ollama.keep_alive", "5m"),
    }
    if tools:
        payload["tools"] = tools
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{_host()}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    body = (await r.aread()).decode(errors="replace")
                    raise OllamaError(f"Ollama returned {r.status_code}: {body[:500]}")
                async for line in r.aiter_lines():
                    if line.strip():
                        yield json.loads(line)
    except httpx.ConnectError as e:
        raise OllamaError(
            f"Cannot reach Ollama at {_host()}. Is `ollama serve` running?") from e


async def chat_once(messages: list[dict], model: str | None = None,
                    format: str | dict | None = None) -> str:
    """Non-streamed helper for internal calls (titles, self-analysis...).
    Pass format="json" (or a JSON schema dict) to force structured output."""
    payload: dict[str, Any] = {
        "model": model or settings.get("ollama.model"),
        "messages": messages,
        "stream": False,
        "options": _options(),
        "keep_alive": settings.get("ollama.keep_alive", "5m"),
    }
    if format:
        payload["format"] = format
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{_host()}/api/chat", json=payload)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")


async def loaded_models() -> list[dict]:
    """Models currently loaded in memory (name, size, VRAM usage)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{_host()}/api/ps")
            r.raise_for_status()
            return r.json().get("models", [])
    except httpx.HTTPError:
        return []


async def embed(text: str) -> list[float] | None:
    """Embed text with the configured embedding model, or None if unset."""
    model = settings.get("ollama.embedding_model", "")
    if not model:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{_host()}/api/embed",
                                  json={"model": model, "input": text})
            r.raise_for_status()
            embeddings = r.json().get("embeddings", [])
            return embeddings[0] if embeddings else None
    except httpx.HTTPError:
        return None
