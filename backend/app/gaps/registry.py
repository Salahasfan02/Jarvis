"""Missing Capabilities Registry — the self-improvement system.

After every chat turn, a background self-analysis asks the LLM whether the
user's request was actually fulfilled. If not, a structured gap entry is
created (or an existing one bumped, which raises its priority). Tool errors
and permission denials feed the same registry. Weekly reports turn the
registry into a prioritized roadmap.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re

from .. import db
from ..config import JARVIS_HOME, settings
from ..llm import ollama_client
from ..security import audit

REPORTS_DIR = JARVIS_HOME / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# --- priority ---------------------------------------------------------------

def priority_for(count: int) -> str:
    if count >= 20:
        return "critical"
    if count > 10:
        return "high"
    if count >= 4:
        return "medium"
    return "low"


def with_priority(gap: dict) -> dict:
    return {**gap, "priority": priority_for(gap.get("count", 1))}


# --- recording ---------------------------------------------------------------

async def record(entry: dict) -> dict:
    """Insert a gap, or bump the count of an existing matching capability."""
    capability = (entry.get("capability") or "").strip()
    if not capability:
        return {}
    existing = _find_match(capability)
    if existing:
        db.bump_gap(existing["id"], entry.get("user_prompt", ""))
        audit.log("gap_bumped", capability=existing["capability"],
                  count=existing["count"] + 1)
        return with_priority({**existing, "count": existing["count"] + 1})
    gap = db.add_gap(entry)
    audit.log("gap_recorded", capability=capability)
    return with_priority(gap)


def _find_match(capability: str) -> dict | None:
    """Match by normalized word overlap so 'Apple Music playlist creation'
    and 'create Apple Music playlists' count as the same capability."""
    words = _norm(capability)
    best, best_score = None, 0.0
    for gap in db.list_gaps():
        other = _norm(gap["capability"])
        if not words or not other:
            continue
        score = len(words & other) / len(words | other)
        if score > best_score:
            best, best_score = gap, score
    return best if best_score >= 0.5 else None


_STOP = {"the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "my", "with"}


def _norm(text: str) -> set[str]:
    import re
    words = set(re.findall(r"[a-z0-9]+", text.lower())) - _STOP
    return {w.rstrip("s") for w in words}


# --- automatic self-analysis ---------------------------------------------------

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "fulfilled": {"type": "boolean"},
        "capability": {"type": "string"},
        "goal": {"type": "string"},
        "reason": {"type": "string"},
        "technical_limitation": {"type": "string"},
        "missing_tool": {"type": "string"},
        "missing_integration": {"type": "string"},
        "missing_permission": {"type": "string"},
        "missing_ai_capability": {"type": "string"},
        "suggested_fix": {"type": "string"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard", "very hard"]},
    },
    "required": ["fulfilled"],
}

ANALYST_PROMPT = """You are the self-improvement analyst for a local AI assistant.
Judge ONLY whether the assistant actually accomplished what the user asked for.

fulfilled=true when the request was answered/completed, even partially but usefully.
fulfilled=false when the assistant could not do it: missing tool, missing app
integration, missing permission, an error, or it only apologized/deflected.
A user DENYING permission is NOT a failure (fulfilled=true).

If fulfilled=false, fill in the analysis fields:
- capability: short name of the missing capability, e.g. "Apple Music playlist creation"
- goal: what the user was trying to achieve
- reason: why it failed, one sentence
- technical_limitation / missing_tool / missing_integration / missing_permission /
  missing_ai_capability: fill the ones that apply, empty string otherwise
- suggested_fix: what to implement, e.g. "Add MusicKit integration"
- difficulty: easy | medium | hard | very hard"""


_FAILURE_HINTS = re.compile(
    r"\b(can'?t|cannot|unable|not (?:able|possible|implemented|supported|installed)|"
    r"don'?t have|no way to|failed|error|sorry|restriction)\b", re.I)


def schedule_analysis(user_prompt: str, assistant_reply: str,
                      tool_events: list[dict]) -> None:
    """Fire-and-forget, and only when the turn actually smells like a failure.
    Running an LLM self-analysis after EVERY message kept the model busy and
    delayed the user's next reply; successful turns are skipped instantly."""
    if not settings.get("gaps.enabled", True):
        return
    tool_trouble = any("Error" in (t.get("result") or "") or
                       "DENIED" in (t.get("result") or "").upper()
                       for t in tool_events)
    if not tool_trouble and not _FAILURE_HINTS.search(assistant_reply or ""):
        return
    asyncio.get_event_loop().create_task(
        _analyze(user_prompt, assistant_reply, tool_events))


async def _analyze(user_prompt: str, assistant_reply: str,
                   tool_events: list[dict]) -> None:
    try:
        tools_text = "\n".join(
            f"- {t['name']}({json.dumps(t['arguments'])[:120]}) -> {t['result'][:150]}"
            for t in tool_events) or "(no tools used)"
        raw = await ollama_client.chat_once([
            {"role": "system", "content": ANALYST_PROMPT},
            {"role": "user", "content":
                f"USER REQUEST:\n{user_prompt[:800]}\n\n"
                f"TOOLS THE ASSISTANT RAN:\n{tools_text}\n\n"
                f"ASSISTANT'S FINAL REPLY:\n{assistant_reply[:1200]}"},
        ], model=ollama_client.model_for("utility"), format=ANALYSIS_SCHEMA)
        data = json.loads(raw)
        if data.get("fulfilled", True):
            return
        data["user_prompt"] = user_prompt[:500]
        await record(data)
    except Exception as e:
        audit.log("gap_analysis_error", error=str(e))


# --- weekly report -------------------------------------------------------------

def _week_id(dt: datetime.date | None = None) -> str:
    dt = dt or datetime.date.today()
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def list_reports() -> list[dict]:
    out = []
    for p in sorted(REPORTS_DIR.glob("*.md"), reverse=True):
        out.append({"id": p.stem, "path": str(p),
                    "created": p.stat().st_mtime})
    return out


def read_report(report_id: str) -> str | None:
    p = REPORTS_DIR / f"{report_id}.md"
    return p.read_text() if p.exists() else None


async def generate_report() -> dict:
    """Build the weekly capability report from real registry data."""
    gaps = [with_priority(g) for g in db.list_gaps()]
    week = _week_id()
    now = datetime.datetime.now()
    week_ago = now.timestamp() - 7 * 86400

    open_gaps = [g for g in gaps if g["status"] == "open"]
    new_this_week = [g for g in open_gaps if g["created_at"] >= week_ago]
    active_this_week = [g for g in open_gaps if g["updated_at"] >= week_ago]
    completed = [g for g in gaps if g["status"] == "completed"]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    top = sorted(open_gaps, key=lambda g: (order[g["priority"]], -g["count"]))[:10]

    def fmt(gs: list[dict]) -> str:
        if not gs:
            return "- none\n"
        return "".join(
            f"- **{g['capability']}** — requested {g['count']}x, "
            f"priority {g['priority']}, difficulty {g['difficulty'] or '?'}\n"
            f"  - reason: {g['reason'] or '—'}\n"
            f"  - suggested fix: {g['suggested_fix'] or '—'}\n"
            for g in gs)

    body = (
        f"# Weekly Capability Report — {week}\n\n"
        f"Generated {now.strftime('%Y-%m-%d %H:%M')} · "
        f"{len(open_gaps)} open gaps · {len(completed)} completed capabilities\n\n"
        f"## New capability requests this week\n{fmt(new_this_week)}\n"
        f"## Most requested (highest priority first)\n{fmt(top)}\n"
        f"## Frequently failing (active again this week)\n{fmt(active_this_week[:8])}\n"
        f"## Completed capabilities\n{fmt(completed[:8])}\n")

    # Ask the model for a roadmap section grounded in the data above.
    try:
        roadmap = await ollama_client.chat_once([
            {"role": "user", "content":
                "You are a product planner for a personal AI assistant. Based on this "
                "capability gap report, write a short '## Suggested roadmap' section "
                "(markdown, max 200 words): order the improvements sensibly, group "
                "related ones, and call out automation opportunities.\n\n" + body}])
        body += "\n" + roadmap.strip() + "\n"
    except Exception:
        body += "\n## Suggested roadmap\n(model unavailable when this report was generated)\n"

    path = REPORTS_DIR / f"{week}.md"
    path.write_text(body)
    audit.log("gap_report_generated", report=week)
    return {"id": week, "markdown": body}
