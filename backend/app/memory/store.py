"""Long-term memory with retrieval.

If an embedding model is configured in settings, memories are embedded and
recalled by cosine similarity (RAG). Without one, recall falls back to
keyword overlap scoring so memory still works out of the box.
"""
from __future__ import annotations

import math
import re

from .. import db
from ..config import settings
from ..llm import ollama_client


async def save(content: str, category: str = "general") -> dict:
    embedding = await ollama_client.embed(content)
    return db.add_memory(content, category, embedding)


async def update(mem_id: str, content: str) -> None:
    embedding = await ollama_client.embed(content)
    db.update_memory(mem_id, content, embedding)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _keyword_score(query: str, content: str) -> float:
    q_words = set(re.findall(r"\w+", query.lower())) - _STOPWORDS
    c_words = set(re.findall(r"\w+", content.lower()))
    if not q_words:
        return 0.0
    return len(q_words & c_words) / len(q_words)


_STOPWORDS = {"the", "a", "an", "is", "are", "was", "to", "of", "in", "on", "for",
              "and", "or", "what", "my", "me", "i", "you", "it", "do", "does", "can"}


_PERSONAL_HINTS = re.compile(
    r"\b(i|my|me|i'm|im|i've|mine|we|our)\b", re.I)

CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": ["facts"],
}


def schedule_auto_capture(user_message: str) -> None:
    """Learn durable facts from what the user says, automatically and in the
    background. Toggleable via settings.memory.auto_capture."""
    import asyncio
    if not settings.get("memory.auto_capture", True):
        return
    if not settings.get("memory.enabled", True):
        return
    if len(user_message) < 15 or not _PERSONAL_HINTS.search(user_message):
        return
    asyncio.get_event_loop().create_task(_auto_capture(user_message))


async def _auto_capture(user_message: str) -> None:
    import json

    from ..security import audit
    try:
        raw = await ollama_client.chat_once([
            {"role": "system", "content":
                "Extract durable personal facts about the user from their message: "
                "preferences, projects, goals, relationships, habits, biography. "
                "Only facts worth remembering for months — NOT one-off requests, "
                "questions, or commands. Each fact must be one self-contained "
                "sentence starting with 'The user'. Return an empty list when "
                "there is nothing durable (most messages)."},
            {"role": "user", "content": user_message[:800]},
        ], model=ollama_client.model_for("utility"), format=CAPTURE_SCHEMA)
        facts = [f.strip() for f in json.loads(raw).get("facts", [])
                 if isinstance(f, str) and 10 < len(f.strip()) < 220][:3]
        for fact in facts:
            # skip near-duplicates of what we already know
            similar = await recall(fact, limit=1)
            if similar and _keyword_score(fact, similar[0]["content"]) > 0.75:
                continue
            await save(fact, "auto")
            audit.log("memory_auto_captured", fact=fact)
    except Exception:
        pass  # background nicety — never let it surface


async def recall(query: str, limit: int | None = None) -> list[dict]:
    if not settings.get("memory.enabled", True):
        return []
    limit = limit or settings.get("memory.max_recalled", 5)
    memories = db.list_memories()
    if not memories:
        return []

    query_emb = await ollama_client.embed(query)
    scored: list[tuple[float, dict]] = []
    for mem in memories:
        if query_emb and mem.get("embedding"):
            score = _cosine(query_emb, mem["embedding"])
            threshold = 0.35
        else:
            score = _keyword_score(query, mem["content"])
            threshold = 0.34
        if score >= threshold:
            scored.append((score, mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]
