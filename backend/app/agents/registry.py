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


AGENTS: dict[str, Agent] = {}


def register(agent: Agent) -> None:
    AGENTS[agent.id] = agent


register(Agent(
    id="general", name="Generalist",
    description="Everyday conversation, questions, and tasks that fit no specialty.",
    prompt="", tool_tags=[]))

register(Agent(
    id="research", name="Research Agent",
    description="Web research: news, facts, comparisons, weather, prices, documentation lookups.",
    prompt="You are in research mode. Search the web and read pages before answering; "
           "cite the URLs you used. Prefer multiple sources for important claims.",
    tool_tags=["research"]))

register(Agent(
    id="coding", name="Coding Agent",
    description="Writing, explaining, debugging or running code; developer tooling.",
    prompt="You are in coding mode. Give working, complete code with brief explanations. "
           "Use fenced code blocks with language tags.",
    tool_tags=["coding", "files"]))

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
    tool_tags=["music", "browser", "automation"]))

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
    id="vision", name="Vision Agent",
    description="Looking at the screen or through the camera; describing or reading visual content.",
    prompt="You are in vision mode. Use the screen/camera tools to see, then answer "
           "precisely what the user asked about the image.",
    tool_tags=["vision"]))


async def route(user_message: str) -> Agent:
    """Pick the best agent for a message. Cheap, failure-proof."""
    if len(AGENTS) <= 1:
        return AGENTS["general"]
    catalog = "\n".join(f"- {a.id}: {a.description}" for a in AGENTS.values())
    try:
        answer = await ollama_client.chat_once([
            {"role": "system",
             "content": "You route user requests to agents. Reply with ONLY the agent id, "
                        "nothing else.\nAgents:\n" + catalog},
            {"role": "user", "content": user_message[:1000]},
        ])
        agent_id = answer.strip().split()[0].strip(".,:").lower() if answer.strip() else "general"
        return AGENTS.get(agent_id, AGENTS["general"])
    except Exception:
        return AGENTS["general"]
