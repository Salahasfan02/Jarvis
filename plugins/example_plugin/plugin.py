"""Example plugin: adds a dice-rolling tool.

Copy this folder to ~/.jarvis/plugins/ (or add folders next to it here) to
extend Jarvis without touching the core code.
"""
import random

from app.tools.base import tool


@tool(
    name="roll_dice",
    description="Roll dice, e.g. sides=20 count=2 rolls two twenty-sided dice.",
    parameters={
        "type": "object",
        "properties": {
            "sides": {"type": "integer", "description": "number of sides (default 6)"},
            "count": {"type": "integer", "description": "number of dice (default 1)"},
        },
    },
)
def roll_dice(sides: int = 6, count: int = 1) -> str:
    rolls = [random.randint(1, max(2, sides)) for _ in range(max(1, min(count, 20)))]
    return f"Rolled {rolls} (total {sum(rolls)})"
