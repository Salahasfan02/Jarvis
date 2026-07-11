"""Pending-confirmation manager.

When the model wants to run a tool whose risk requires confirmation, the chat
loop parks the call here and notifies the UI. The UI shows a dialog; the
user's decision resolves the future and the chat loop resumes.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import audit


@dataclass
class PendingConfirmation:
    id: str
    tool: str
    arguments: dict[str, Any]
    risk: str
    future: asyncio.Future = field(repr=False, default=None)  # type: ignore


class ConfirmationManager:
    def __init__(self) -> None:
        self._pending: dict[str, PendingConfirmation] = {}

    def create(self, tool: str, arguments: dict[str, Any], risk: str) -> PendingConfirmation:
        pc = PendingConfirmation(
            id=uuid.uuid4().hex, tool=tool, arguments=arguments, risk=risk,
            future=asyncio.get_event_loop().create_future())
        self._pending[pc.id] = pc
        audit.log("confirmation_requested", id=pc.id, tool=tool, arguments=arguments)
        return pc

    async def wait(self, confirmation_id: str, timeout: float = 300) -> bool:
        pc = self._pending.get(confirmation_id)
        if pc is None:
            return False
        try:
            return await asyncio.wait_for(pc.future, timeout=timeout)
        except asyncio.TimeoutError:
            audit.log("confirmation_timeout", id=confirmation_id, tool=pc.tool)
            return False
        finally:
            self._pending.pop(confirmation_id, None)

    def resolve(self, confirmation_id: str, approved: bool) -> bool:
        pc = self._pending.get(confirmation_id)
        if pc is None or pc.future.done():
            return False
        pc.future.set_result(approved)
        audit.log("confirmation_resolved", id=confirmation_id, tool=pc.tool,
                  approved=approved)
        return True


confirmations = ConfirmationManager()
