"""Specialized agents.

An agent is a persona + a subset of tools. The router asks the LLM to pick
the best agent for each user message with a cheap classification call; the
chosen agent's system prompt and tool set drive the actual response. Falls
back to the generalist if classification fails, so routing can never break
chat.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..llm import ollama_client


@dataclass
class Agent:
    id: str
    name: str
    description: str            # shown to the router LLM
    prompt: str                 # appended to the system prompt
    tool_tags: list[str] = field(default_factory=list)  # empty = all tools
    model_task: str | None = None  # per-task model override key (e.g. "coding")


AGENTS: dict[str, Agent] = {}


def register(agent: Agent) -> None:
    AGENTS[agent.id] = agent


# The generalist deliberately carries a LEAN tool set: serializing all ~30
# tool schemas into every prompt made casual messages take ~10s of prompt
# processing. Actionable requests route to specialists with the full kit.
register(Agent(
    id="general", name="Generalist",
    description="Everyday conversation, questions, and tasks that fit no specialty.",
    prompt="", tool_tags=["_conversation"]))  # only untagged basics (calculator, remember, ...)

register(Agent(
    id="research", name="Research Agent",
    description="Web research: news, facts, comparisons, weather, prices, documentation lookups.",
    prompt="You are in research mode. Search the web and read pages BEFORE answering; "
           "compare multiple sources for important claims. Use web_search's `site` "
           "parameter to target github.com, stackoverflow.com, reddit.com, youtube.com "
           "or arxiv.org when the question calls for it.\n"
           "CITATIONS ARE MANDATORY: every factual claim gathered from the internet "
           "must be traceable. End your answer with a 'Sources:' section listing, for "
           "each source: title — URL — publication date if known — one-line summary. "
           "Never invent URLs; only cite pages you actually fetched or that web_search "
           "returned.",
    tool_tags=["research"]))

register(Agent(
    id="coding", name="Coding Agent",
    description="Writing, explaining, debugging or running code; developer tooling.",
    prompt="You are a senior software engineer. Give working, complete code in fenced "
           "blocks with language tags. Beyond writing code you: design architecture and "
           "explain trade-offs, review code for bugs/security/performance, refactor, "
           "write tests and documentation, explain compiler errors plainly, and manage "
           "dependencies. Verify non-trivial code with run_python before presenting it "
           "when practical. When debugging, state the root cause before the fix.",
    tool_tags=["coding", "files"], model_task="coding"))

register(Agent(
    id="automation", name="Automation Agent",
    description="Controlling the Mac: apps, browser tabs, YouTube, Apple Music, notes, "
                "reminders, calendar, clipboard, windows.",
    prompt="You are in automation mode. Use the macOS tools to act on the user's behalf. "
           "Reuse existing tabs, windows and sessions — never duplicate them. "
           "Confirm what you did after each action.",
    tool_tags=["automation", "files", "browser", "music", "notes", "calendar"]))

register(Agent(
    id="media", name="Media Agent",
    description="Playing or controlling music and videos: YouTube, Apple Music, playlists, "
                "pause/skip/shuffle.",
    prompt="You are in media mode. Continue the user's current music or video session "
           "in place — reuse the open YouTube tab or the running Music app, never open "
           "duplicates. Confirm what is now playing.",
    tool_tags=["music", "browser"]))

register(Agent(
    id="files", name="File Agent",
    description="Finding, organizing, reading, moving or cleaning up files and folders.",
    prompt="You are in file-management mode. Always list what you find before changing "
           "anything, and summarize changes you make.",
    tool_tags=["files"]))

register(Agent(
    id="messaging", name="Messaging & Email Agent",
    description="Drafting or managing messages and emails.",
    prompt="You are in messaging mode. Draft clear, well-toned messages. You can only "
           "prepare drafts — the user always sends them personally.",
    tool_tags=["messaging", "email"]))

register(Agent(
    id="planner", name="Planning Agent",
    description="Complex multi-step goals that need several actions in sequence.",
    prompt="You are executing one step of a larger plan. Use tools to complete "
           "ONLY the current step, then summarize what you did in one sentence.",
    tool_tags=[]))  # planner steps may need any tool

register(Agent(
    id="vision", name="Vision Agent",
    description="Looking at the screen or through the camera; describing or reading visual content.",
    prompt="You are in vision mode. Use the screen/camera tools to see, then answer "
           "precisely what the user asked about the image.",
    tool_tags=["vision"]))


# Keyword routing: instant, no LLM round-trip. An extra generation per message
# just to pick an agent was the single biggest source of reply latency.
_ROUTE_KEYWORDS: dict[str, list[str]] = {
    "media": ["play", "pause", "resume", "skip", "song", "music", "playlist",
              "spotify", "shuffle", "volume", "track"],
    "vision": ["screen", "camera", "webcam", "looking at", "what do you see",
               "what am i", "read this", "on my display"],
    "research": ["search", "news", "weather", "price", "google", "look up",
                 "latest", "who is", "what is the", "compare", "stock"],
    "coding": ["code", "function", "script", "debug", "python", "javascript",
               "typescript", "program", "compile", "regex", "bug", "api"],
    "files": ["file", "folder", "desktop", "downloads", "organize", "rename",
              "directory", "trash", "documents"],
    "messaging": ["email", "mail", "imessage", "message", "text him", "text her",
                  "draft", "reply to", "inbox"],
    "automation": ["open", "close", "launch", "quit", "safari", "chrome", "app",
                   "note", "reminder", "calendar", "clipboard", "tab", "window",
                   "youtube"],
}


_PLANNER_HINTS = ["plan ", "plan:", "step by step", "multi-step", "organize my day",
                  "organize my week", "morning routine", "and then", "after that",
                  "set everything up", "prepare my"]


async def route(user_message: str) -> Agent:
    """Pick the best agent for a message instantly via keyword scoring."""
    lower = f" {user_message.lower()} "
    if any(h in lower for h in _PLANNER_HINTS) or lower.strip().startswith("plan"):
        return AGENTS["planner"]
    best_id, best_score = "general", 0
    for agent_id, words in _ROUTE_KEYWORDS.items():
        if agent_id not in AGENTS:
            continue
        score = sum(1 for w in words if w in lower)
        if score > best_score:
            best_id, best_score = agent_id, score
    return AGENTS.get(best_id, AGENTS["general"])
