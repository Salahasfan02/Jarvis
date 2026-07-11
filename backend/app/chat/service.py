"""Chat orchestration: memory recall -> agent routing -> LLM streaming ->
tool-calling loop with user confirmations.

Emits event dicts consumed by the WebSocket layer:
  {"type": "agent", "agent": {...}}
  {"type": "memory", "recalled": [...]}
  {"type": "token", "content": "..."}
  {"type": "tool_start" | "tool_result", ...}
  {"type": "confirm_request", "id", "tool", "arguments", "risk"}
  {"type": "done", "content": "...", "message_id": "..."}
  {"type": "title", "title": "..."}
  {"type": "error", "message": "..."}
"""
from __future__ import annotations

import datetime
import json
from typing import AsyncIterator

from .. import db
from ..agents import registry as agents
from ..automation import context as app_context
from ..config import settings
from ..gaps import registry as gaps
from ..llm import ollama_client
from ..memory import store as memory_store
from ..security import audit
from ..security.permissions import confirmations
from ..tools import base as tools

SMART_WINDOW_RULES = """Smart context rules (IMPORTANT):
- Before opening any website, check the open tabs (they are listed above, or
  call browser_tabs). If a tab for that site already exists, REUSE it.
- NEVER open a new browser window unless the user explicitly says "new window".
- Never launch an app that is already running; continue its existing session.
- 'Play X' when a YouTube tab is open -> youtube_play (same tab).
  'Play X' referring to the user's library / Apple Music -> music_play.
- Continue the user's current activity in place; don't duplicate contexts."""


def _system_prompt(agent: agents.Agent, memories: list[dict], ctx: dict) -> str:
    name = settings.get("assistant.name", "Jarvis")
    persona = settings.get("assistant.persona", "").format(name=name)
    parts = [persona]
    parts.append("Current date/time: "
                 + datetime.datetime.now().strftime("%A, %B %d %Y, %H:%M"))
    if agent.prompt:
        parts.append(agent.prompt)
    ctx_summary = app_context.summary_for_prompt(ctx)
    if ctx_summary:
        parts.append("What the user is doing right now:\n" + ctx_summary)
        parts.append(SMART_WINDOW_RULES)
    if memories:
        facts = "\n".join(f"- {m['content']}" for m in memories)
        parts.append("Relevant things you remember about the user:\n" + facts)
    parts.append(
        "When a tool would help, call it instead of guessing. Some tool calls "
        "require the user's confirmation; if one is denied, respect that and "
        "explain what you would have done.")
    return "\n\n".join(parts)


def _history_to_llm(history: list[dict]) -> list[dict]:
    msgs = []
    for m in history:
        if m["role"] in ("user", "assistant"):
            msgs.append({"role": m["role"], "content": m["content"]})
    return msgs


async def run_chat(conversation_id: str, user_content: str) -> AsyncIterator[dict]:
    db.add_message(conversation_id, "user", user_content)
    history = db.get_messages(conversation_id)

    memories = []
    try:
        memories = await memory_store.recall(user_content)
    except Exception:
        pass
    if memories:
        yield {"type": "memory",
               "recalled": [{"id": m["id"], "content": m["content"]} for m in memories]}

    agent = await agents.route(user_content)
    yield {"type": "agent", "agent": {"id": agent.id, "name": agent.name}}

    try:
        ctx = await app_context.snapshot()
    except Exception:
        ctx = {}

    llm_messages: list[dict] = [
        {"role": "system", "content": _system_prompt(agent, memories, ctx)},
        *_history_to_llm(history),
    ]

    use_tools = settings.get("tools.enabled", True)
    tool_list = tools.registry.for_agent(agent.tool_tags) if use_tools else []
    tool_schemas = [t.to_ollama() for t in tool_list] or None

    full_response = ""
    tool_events: list[dict] = []
    max_rounds = settings.get("tools.max_iterations", 6)

    try:
        for round_no in range(max_rounds + 1):
            # Last round: no tools, force the model to answer with what it has.
            schemas = tool_schemas if round_no < max_rounds else None
            round_text = ""
            tool_calls: list[dict] = []

            async for chunk in ollama_client.chat_stream(llm_messages, tools=schemas):
                msg = chunk.get("message", {})
                if msg.get("content"):
                    round_text += msg["content"]
                    full_response += msg["content"]
                    yield {"type": "token", "content": msg["content"]}
                for tc in msg.get("tool_calls") or []:
                    tool_calls.append(tc)
                if chunk.get("done"):
                    break

            if not tool_calls:
                break

            llm_messages.append({"role": "assistant", "content": round_text,
                                 "tool_calls": tool_calls})

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                out: dict = {}
                async for event in _execute_with_permission(name, args, tool_events, out):
                    yield event
                llm_messages.append({"role": "tool", "content": out["output"],
                                     "tool_name": name})
    except ollama_client.OllamaError as e:
        yield {"type": "error", "message": str(e)}
        return
    except Exception as e:
        audit.log("chat_error", error=str(e))
        yield {"type": "error", "message": f"Unexpected error: {e}"}
        return

    saved = db.add_message(conversation_id, "assistant", full_response,
                           meta={"agent": agent.id, "tools": tool_events})
    yield {"type": "done", "content": full_response, "message_id": saved["id"]}

    # Self-improvement: analyze this turn for capability gaps (non-blocking).
    gaps.schedule_analysis(user_content, full_response, tool_events)

    # Auto-title new conversations from the first exchange.
    conv_msgs = db.get_messages(conversation_id)
    if len([m for m in conv_msgs if m["role"] == "user"]) == 1:
        try:
            title = await ollama_client.chat_once([
                {"role": "user",
                 "content": "Write a title of at most 5 words for this conversation. "
                            "Reply with only the title, no quotes.\n\nUser: "
                            + user_content[:500]}])
            title = title.strip().strip('"')[:60]
            if title:
                db.rename_conversation(conversation_id, title=title)
                yield {"type": "title", "title": title}
        except Exception:
            pass


async def _execute_with_permission(name: str, args: dict, tool_events: list[dict],
                                   out: dict) -> AsyncIterator[dict]:
    """Yields UI events as they happen (crucially, confirm_request is yielded
    BEFORE blocking on the user's answer). Final tool output lands in out."""
    t = tools.registry.get(name)
    denied = False

    if t is None:
        output = f"Error: unknown tool '{name}'"
    elif t.needs_confirmation():
        pc = confirmations.create(name, args, t.risk)
        yield {"type": "confirm_request", "id": pc.id, "tool": name,
               "arguments": args, "risk": t.risk}
        approved = await confirmations.wait(pc.id)
        if approved:
            yield {"type": "tool_start", "name": name, "arguments": args}
            output = await tools.execute(name, args)
        else:
            denied = True
            output = ("The user DENIED permission to run this tool. Do not retry it; "
                      "acknowledge and continue.")
    else:
        yield {"type": "tool_start", "name": name, "arguments": args}
        output = await tools.execute(name, args)

    yield {"type": "tool_result", "name": name,
           "result": "Denied by user" if denied else output[:1000], "denied": denied}
    tool_events.append({"name": name, "arguments": args, "result": output[:500]})
    out["output"] = output
