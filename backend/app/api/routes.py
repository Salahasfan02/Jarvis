"""REST + WebSocket API consumed by the desktop frontend."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import db
from ..agents.registry import AGENTS
from ..chat import service as chat_service
from ..config import settings
from ..llm import ollama_client
from ..plugins import loader as plugin_loader
from ..security import audit
from ..security.permissions import confirmations
from ..tools import base as tools

router = APIRouter(prefix="/api")


# --- health / status ---------------------------------------------------------

@router.get("/status")
async def status():
    return {
        "ok": True,
        "ollama_up": await ollama_client.is_up(),
        "model": settings.get("ollama.model"),
        "assistant_name": settings.get("assistant.name"),
    }


# --- settings ----------------------------------------------------------------

class SettingsPatch(BaseModel):
    patch: dict


@router.get("/settings")
def get_settings():
    return settings.all()


@router.put("/settings")
def put_settings(body: SettingsPatch):
    audit.log("settings_changed", patch=body.patch)
    return settings.update(body.patch)


# --- models ------------------------------------------------------------------

@router.get("/models")
async def models():
    try:
        return {"models": await ollama_client.list_models(),
                "active": settings.get("ollama.model")}
    except Exception as e:
        return {"models": [], "active": settings.get("ollama.model"), "error": str(e)}


@router.delete("/models/{name:path}")
async def remove_model(name: str):
    await ollama_client.delete_model(name)
    audit.log("model_deleted", model=name)
    return {"ok": True}


@router.post("/models/pull")
async def pull_model(body: dict):
    name = body.get("name", "").strip()

    async def stream():
        try:
            async for event in ollama_client.pull_model(name):
                yield json.dumps(event) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
    audit.log("model_pull", model=name)
    return StreamingResponse(stream(), media_type="application/x-ndjson")


# --- conversations -----------------------------------------------------------

@router.get("/conversations")
def conversations(q: str = ""):
    return db.search_conversations(q) if q else db.list_conversations()


@router.post("/conversations")
def new_conversation():
    return db.create_conversation()


@router.get("/conversations/{conv_id}/messages")
def conversation_messages(conv_id: str):
    return db.get_messages(conv_id)


@router.patch("/conversations/{conv_id}")
def patch_conversation(conv_id: str, body: dict):
    db.rename_conversation(conv_id, title=body.get("title"), folder=body.get("folder"))
    return {"ok": True}


@router.delete("/conversations/{conv_id}")
def remove_conversation(conv_id: str):
    db.delete_conversation(conv_id)
    return {"ok": True}


class EditMessage(BaseModel):
    message_id: str


@router.post("/conversations/{conv_id}/truncate")
def truncate(conv_id: str, body: EditMessage):
    """Delete a message and everything after it (edit / regenerate support)."""
    db.delete_messages_after(conv_id, body.message_id)
    return {"ok": True}


# --- memory ------------------------------------------------------------------

@router.get("/memories")
def memories():
    return [{k: v for k, v in m.items() if k != "embedding"}
            for m in db.list_memories()]


@router.post("/memories")
async def create_memory(body: dict):
    from ..memory import store
    return await store.save(body.get("content", ""), body.get("category", "general"))


@router.put("/memories/{mem_id}")
async def edit_memory(mem_id: str, body: dict):
    from ..memory import store
    await store.update(mem_id, body.get("content", ""))
    return {"ok": True}


@router.delete("/memories/{mem_id}")
def remove_memory(mem_id: str):
    db.delete_memory(mem_id)
    return {"ok": True}


# --- tools / agents / plugins / audit (developer surface) ---------------------

@router.get("/tools")
def list_tools():
    return [{"name": t.name, "description": t.description, "risk": t.risk,
             "tags": t.agent_tags,
             "permission": settings.get(f"permissions.{t.name}", "default")}
            for t in tools.registry.all()]


@router.get("/agents")
def list_agents():
    return [{"id": a.id, "name": a.name, "description": a.description}
            for a in AGENTS.values()]


@router.get("/plugins")
def list_plugins():
    return plugin_loader.loaded


@router.post("/plugins/reload")
def reload_plugins():
    return plugin_loader.load_all()


@router.get("/audit")
def audit_log(limit: int = 200):
    return audit.tail(limit)


# --- capability gaps (self-improvement registry) -------------------------------

@router.get("/gaps")
def get_gaps():
    from ..gaps import registry as gaps
    from .. import db as _db
    return [gaps.with_priority(g) for g in _db.list_gaps()]


@router.post("/gaps")
async def create_gap(body: dict):
    from ..gaps import registry as gaps
    return await gaps.record(body)


@router.patch("/gaps/{gap_id}")
def patch_gap(gap_id: str, body: dict):
    from .. import db as _db
    _db.update_gap(gap_id, body)
    return {"ok": True}


@router.delete("/gaps/{gap_id}")
def remove_gap(gap_id: str):
    from .. import db as _db
    _db.delete_gap(gap_id)
    return {"ok": True}


@router.get("/gaps/reports")
def gap_reports():
    from ..gaps import registry as gaps
    return gaps.list_reports()


@router.get("/gaps/reports/{report_id}")
def gap_report(report_id: str):
    from ..gaps import registry as gaps
    md = gaps.read_report(report_id)
    return {"id": report_id, "markdown": md or ""}


@router.post("/gaps/report")
async def generate_gap_report():
    from ..gaps import registry as gaps
    return await gaps.generate_report()


# --- system stats & context (dashboard) ----------------------------------------

@router.get("/stats")
async def system_stats():
    import psutil
    from ..tools.base import running_now
    vm = psutil.virtual_memory()
    loaded = await ollama_client.loaded_models()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0),
        "memory_percent": vm.percent,
        "memory_used_gb": round(vm.used / 1e9, 1),
        "memory_total_gb": round(vm.total / 1e9, 1),
        "ollama_up": await ollama_client.is_up(),
        "active_model": settings.get("ollama.model"),
        "loaded_models": [
            {"name": m.get("name"), "size_gb": round(m.get("size", 0) / 1e9, 1),
             "gpu_percent": round(100 * m.get("size_vram", 0) / m["size"]) if m.get("size") else 0}
            for m in loaded],
        "running_tools": list(running_now.keys()),
        "recent_activity": audit.tail(8),
    }


@router.get("/context")
async def app_context_endpoint():
    from ..automation import context as app_context
    return await app_context.snapshot()


# --- text to speech -------------------------------------------------------------

@router.get("/tts/engines")
def tts_engines():
    from ..speech import engines
    return engines.list_engines()


@router.post("/tts/speak")
async def tts_speak(body: dict):
    from fastapi.responses import JSONResponse, Response
    from ..speech import engines
    wav = await engines.synthesize(body.get("text", "")[:3000])
    if wav is None:
        return JSONResponse({"engine": "browser"})
    return Response(content=wav, media_type="audio/wav")


# --- chat websocket ----------------------------------------------------------

@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    current_task: asyncio.Task | None = None

    async def run(conv_id: str, content: str):
        try:
            async for event in chat_service.run_chat(conv_id, content):
                await ws.send_json(event)
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            try:
                await ws.send_json({"type": "stopped"})
            except Exception:
                pass
            raise

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")

            if mtype == "chat":
                if current_task and not current_task.done():
                    current_task.cancel()
                conv_id = msg.get("conversation_id") or db.create_conversation()["id"]
                await ws.send_json({"type": "conversation", "conversation_id": conv_id})
                current_task = asyncio.create_task(run(conv_id, msg.get("content", "")))

            elif mtype == "confirm":
                confirmations.resolve(msg.get("id", ""), bool(msg.get("approved")))
                if msg.get("remember") and msg.get("approved") and msg.get("tool"):
                    t = tools.registry.get(msg["tool"])
                    if t and t.risk == "confirm":  # dangerous can't be remembered
                        settings.update({"permissions": {msg["tool"]: "always"}})

            elif mtype == "stop":
                if current_task and not current_task.done():
                    current_task.cancel()
    except WebSocketDisconnect:
        if current_task and not current_task.done():
            current_task.cancel()
