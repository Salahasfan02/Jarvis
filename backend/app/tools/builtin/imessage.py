"""Read Apple Messages (iMessage/SMS) from the local chat database.

Reads ~/Library/Messages/chat.db directly (read-only). This requires the app
running the backend to have Full Disk Access in System Settings > Privacy &
Security — the tools return clear guidance when access is missing. Reading is
confirm-gated; sending still goes through draft_imessage (user presses send).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..base import tool

CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"
# Apple stores dates as nanoseconds since 2001-01-01.
APPLE_EPOCH = "978307200"


def _connect() -> sqlite3.Connection | None:
    if not CHAT_DB.exists():
        return None
    try:
        # read-only URI so we never touch the live database
        return sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True, timeout=5)
    except sqlite3.OperationalError:
        return None


_ACCESS_HELP = (
    "Can't read Messages — the backend needs Full Disk Access. Open System "
    "Settings > Privacy & Security > Full Disk Access and enable it for the app "
    "running Jarvis (Terminal, or the Jarvis app), then try again.")


def _decode_text_dict(r: dict) -> str:
    """Message text is usually in `text`; newer messages may only have an
    attributedBody blob, from which we salvage the readable string run."""
    if r.get("text"):
        return r["text"]
    blob = r.get("attributedBody")
    if not blob:
        return ""
    try:
        raw = blob.decode("utf-8", errors="ignore")
        idx = raw.find("NSString")
        if idx != -1:
            segment = raw[idx + 8: idx + 8 + 2000]
            return "".join(c for c in segment if c.isprintable()).lstrip(
                "+ \x01\x02\x84\x85").strip()
    except Exception:
        pass
    return ""


@tool(
    name="read_messages",
    description="Read the most recent Messages (iMessage/SMS) conversations — who "
                "texted, when, and the latest message in each. Use for 'any new "
                "messages?', 'what did I miss', etc.",
    parameters={
        "type": "object",
        "properties": {"limit": {"type": "integer", "description": "how many recent messages (default 15)"}},
    },
    risk="confirm",
    agent_tags=["messaging"],
)
def read_messages(limit: int = 15) -> str:
    conn = _connect()
    if conn is None:
        return _ACCESS_HELP
    limit = max(1, min(limit, 40))
    try:
        rows = conn.execute(f"""
            SELECT m.text, m.attributedBody, m.is_from_me,
                   datetime(m.date/1000000000 + {APPLE_EPOCH}, 'unixepoch', 'localtime') AS when_local,
                   COALESCE(h.id, 'unknown') AS handle
            FROM message m
            LEFT JOIN handle h ON m.handle_id = h.ROWID
            ORDER BY m.date DESC LIMIT ?""", (limit,)).fetchall()
    except sqlite3.OperationalError as e:
        return f"Could not query Messages: {e}. {_ACCESS_HELP}"
    finally:
        conn.close()
    if not rows:
        return "No messages found."
    lines = []
    for r in rows:
        r = dict(zip(("text", "attributedBody", "is_from_me", "when_local", "handle"), r))
        # sqlite3.Row-like access via a manual dict
        who = "Me" if r["is_from_me"] else r["handle"]
        text = _decode_text_dict(r)[:200] or "(no text / attachment)"
        lines.append(f"[{r['when_local']}] {who}: {text}")
    return "\n".join(lines)


def _decode_text_dict(r: dict) -> str:
    if r.get("text"):
        return r["text"]
    blob = r.get("attributedBody")
    if not blob:
        return ""
    try:
        raw = blob.decode("utf-8", errors="ignore")
        idx = raw.find("NSString")
        if idx != -1:
            segment = raw[idx + 8: idx + 8 + 2000]
            return "".join(c for c in segment if c.isprintable()).lstrip("+ \x01\x02\x84\x85").strip()
    except Exception:
        pass
    return ""


@tool(
    name="read_conversation_with",
    description="Read the recent message history with a specific contact (by name, "
                "phone number or email/handle as it appears in Messages).",
    parameters={
        "type": "object",
        "properties": {
            "contact": {"type": "string", "description": "phone, email, or handle"},
            "limit": {"type": "integer", "description": "messages to fetch (default 20)"},
        },
        "required": ["contact"],
    },
    risk="confirm",
    agent_tags=["messaging"],
)
def read_conversation_with(contact: str, limit: int = 20) -> str:
    conn = _connect()
    if conn is None:
        return _ACCESS_HELP
    limit = max(1, min(limit, 60))
    try:
        rows = conn.execute(f"""
            SELECT m.text, m.attributedBody, m.is_from_me,
                   datetime(m.date/1000000000 + {APPLE_EPOCH}, 'unixepoch', 'localtime') AS when_local,
                   h.id AS handle
            FROM message m
            JOIN handle h ON m.handle_id = h.ROWID
            WHERE h.id LIKE ?
            ORDER BY m.date DESC LIMIT ?""", (f"%{contact}%", limit)).fetchall()
    except sqlite3.OperationalError as e:
        return f"Could not query Messages: {e}. {_ACCESS_HELP}"
    finally:
        conn.close()
    if not rows:
        return (f"No messages found with '{contact}'. Try their exact phone number "
                f"or email as saved in Messages.")
    out = []
    for r in reversed(rows):  # chronological
        r = dict(zip(("text", "attributedBody", "is_from_me", "when_local", "handle"), r))
        who = "Me" if r["is_from_me"] else r["handle"]
        out.append(f"[{r['when_local']}] {who}: {_decode_text_dict(r)[:300]}")
    return "\n".join(out)
