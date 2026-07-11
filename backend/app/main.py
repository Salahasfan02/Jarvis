"""Jarvis backend entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .api.routes import router
from .plugins import loader as plugin_loader

# Importing the builtin tool modules registers their tools.
from .tools.builtin import browser, filesystem, macos, music, system, web  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    plugin_loader.load_all()
    yield


app = FastAPI(title="Jarvis", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Local UI origins only (Vite dev server / packaged desktop shell).
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "app://jarvis", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"name": "Jarvis", "docs": "/docs"}
