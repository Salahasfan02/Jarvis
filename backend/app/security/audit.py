"""Append-only audit log. Every tool execution, confirmation and denial is
recorded so nothing happens on the machine silently."""
from __future__ import annotations

import json
import threading
import time

from ..config import AUDIT_FILE

_lock = threading.Lock()


def log(event: str, **fields) -> None:
    entry = {"ts": time.time(), "event": event, **fields}
    with _lock:
        with AUDIT_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")


def tail(limit: int = 200) -> list[dict]:
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text().strip().splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))
