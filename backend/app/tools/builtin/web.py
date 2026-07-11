"""Internet tools: search and page reading. No API keys required —
search uses DuckDuckGo's HTML endpoint."""
from __future__ import annotations

import html as html_lib
import re

import httpx

from ..base import tool

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Jarvis/1.0"}


def _strip_html(html: str, limit: int = 8000) -> str:
    html = re.sub(r"(?is)<(script|style|nav|footer|header|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    text = html_lib.unescape(html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()[:limit]


@tool(
    name="web_search",
    description="Search the web. Returns a list of result titles, URLs and snippets. "
                "Use for current events, facts you're unsure about, weather, prices, news.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "search query"}},
        "required": ["query"],
    },
    agent_tags=["research"],
)
async def web_search(query: str) -> str:
    async with httpx.AsyncClient(timeout=15, headers=UA, follow_redirects=True) as client:
        r = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
        r.raise_for_status()
    results = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</a>', re.S)
    for m in pattern.finditer(r.text):
        url, title, snippet = m.groups()
        url = re.sub(r"^//duckduckgo\.com/l/\?uddg=([^&]+).*$",
                     lambda mm: httpx.URL(f"http://x?u={mm.group(1)}").params["u"], url)
        results.append(f"- {_strip_html(title, 200)}\n  {url}\n  {_strip_html(snippet, 300)}")
        if len(results) >= 8:
            break
    return "\n".join(results) if results else "No results found."


@tool(
    name="web_fetch",
    description="Fetch a URL and return the readable text content of the page. "
                "Use to read articles, documentation, or any webpage.",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "full URL including https://"}},
        "required": ["url"],
    },
    agent_tags=["research"],
)
async def web_fetch(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    async with httpx.AsyncClient(timeout=20, headers=UA, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            return f"URL returned non-text content ({ctype}); cannot read it as a page."
    return _strip_html(r.text) or "Page had no readable text."
