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
