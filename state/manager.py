"""State persistence manager — saves/loads agent state to state.json."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


STATE_FILE = Path(__file__).parent / "state.json"


@dataclass
class Step:
    index: int
    description: str
    status: str = "pending"   # pending | running | done | failed
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AgentState:
    task: str = ""
    workspace: str = ""
    plan: list[dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    status: str = "idle"       # idle | planning | coding | done | failed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    files_created: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Serialization helpers
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentState":
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    # ------------------------------------------------------------------ #
    # Step helpers
    # ------------------------------------------------------------------ #

    def get_steps(self) -> list[Step]:
        return [Step(**s) for s in self.plan]

    def get_current_step(self) -> Optional[Step]:
        steps = self.get_steps()
        if self.current_step < len(steps):
            return steps[self.current_step]
        return None

    def mark_step_done(self, output: str) -> None:
        if self.current_step < len(self.plan):
            self.plan[self.current_step]["status"] = "done"
            self.plan[self.current_step]["output"] = output
            self.current_step += 1
            self.updated_at = time.time()

    def mark_step_failed(self, error: str) -> None:
        if self.current_step < len(self.plan):
            self.plan[self.current_step]["status"] = "failed"
            self.plan[self.current_step]["error"] = error
            self.updated_at = time.time()

    def add_file(self, path: str) -> None:
        if path not in self.files_created:
            self.files_created.append(path)
            self.updated_at = time.time()

    def is_complete(self) -> bool:
        return self.current_step >= len(self.plan) and len(self.plan) > 0

    def pending_steps(self) -> list[Step]:
        return [s for s in self.get_steps() if s.status == "pending"]

    def done_steps(self) -> list[Step]:
        return [s for s in self.get_steps() if s.status == "done"]


class StateManager:
    """Persist and load AgentState to/from disk."""

    def __init__(self, path: Path = STATE_FILE):
        self.path = path

    def save(self, state: AgentState) -> None:
        state.updated_at = time.time()
        self.path.write_text(json.dumps(state.to_dict(), indent=2))

    def load(self) -> Optional[AgentState]:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text())
            return AgentState.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def exists(self) -> bool:
        return self.path.exists()
