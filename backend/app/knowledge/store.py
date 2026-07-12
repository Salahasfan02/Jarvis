"""Document knowledge base (RAG).

PDFs / text / markdown are chunked, embedded with the configured embedding
model (nomic-embed-text) and stored in SQLite. `search()` does cosine
retrieval; the `search_documents` tool exposes it to every agent so Jarvis
can answer questions from the user's own files.
"""
from __future__ import annotations

import io
import math
import re

from .. import db
from ..llm import ollama_client

CHUNK_CHARS = 1100
OVERLAP = 150


def extract_text(name: str, data: bytes) -> str:
    lower = name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    # txt / md / code / anything text-like
    return data.decode("utf-8", errors="replace")


def chunk_text(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            # prefer to break on a paragraph or sentence boundary
            window = text[start:end]
            brk = max(window.rfind("\n\n"), window.rfind(". "))
            if brk > CHUNK_CHARS // 2:
                end = start + brk + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
    return [c for c in chunks if len(c) > 40]


async def ingest(name: str, data: bytes) -> dict:
    text = extract_text(name, data)
    chunks = chunk_text(text)
    if not chunks:
        return {"error": f"No readable text found in {name}"}
    embedded: list[tuple[str, list[float] | None]] = []
    for chunk in chunks:
        emb = await ollama_client.embed(chunk)
        embedded.append((chunk, emb))
    doc = db.add_document(name, embedded)
    doc["embedded"] = all(e is not None for _, e in embedded)
    return doc


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _keyword_score(query: str, content: str) -> float:
    q = set(re.findall(r"\w+", query.lower()))
    c = set(re.findall(r"\w+", content.lower()))
    return len(q & c) / len(q) if q else 0.0


async def search(query: str, limit: int = 5) -> list[dict]:
    chunks = db.all_chunks()
    if not chunks:
        return []
    query_emb = await ollama_client.embed(query)
    scored = []
    for ch in chunks:
        if query_emb and ch.get("embedding"):
            score = _cosine(query_emb, ch["embedding"])
        else:
            score = _keyword_score(query, ch["content"])
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"document": ch["doc_name"], "content": ch["content"],
             "score": round(score, 3)}
            for score, ch in scored[:limit] if score > 0.2]
