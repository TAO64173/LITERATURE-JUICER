"""State Machine Engine — explicit state transitions for the orchestrator.

States: INIT → PLAN → EXECUTE → VERIFY → REVIEW → REPAIR → DONE
Rules:
  - No implicit transitions
  - No silent fallback
  - Every state transition is explicit and logged
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable


class State(Enum):
    INIT = "INIT"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    REPAIR = "REPAIR"
    STALL = "STALL"
    DONE = "DONE"


# Valid transitions: from_state → set of allowed to_states
VALID_TRANSITIONS: dict[State, set[State]] = {
    State.INIT: {State.PLAN},
    State.PLAN: {State.EXECUTE, State.DONE},  # DONE if no more tasks
    State.EXECUTE: {State.VERIFY},
    State.VERIFY: {State.REVIEW, State.REPAIR},  # REPAIR if tests fail
    State.REVIEW: {State.PLAN, State.REPAIR, State.DONE},
    State.REPAIR: {State.EXECUTE, State.STALL},  # STALL on repeated failure
    State.STALL: {State.DONE},  # terminal path via stall
    State.DONE: set(),  # terminal
}


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


class StateMachine:
    """Explicit state machine with logged transitions."""

    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file
        self._state = State.INIT
        self._history: list[dict] = []
        self._iteration = 0
        self._max_iterations = 15
        self._data: dict = {}
        self._state_entered_at: str = datetime.now(timezone.utc).isoformat()

    @property
    def state(self) -> State:
        return self._state

    @property
    def iteration(self) -> int:
        return self._iteration

    @property
    def is_terminal(self) -> bool:
        return self._state == State.DONE

    def can_transition(self, target: State) -> bool:
        return target in VALID_TRANSITIONS.get(self._state, set())

    def transition(self, target: State, reason: str = "") -> None:
        """Transition to a new state. Raises TransitionError if invalid."""
        if not self.can_transition(target):
            allowed = VALID_TRANSITIONS.get(self._state, set())
            raise TransitionError(
                f"Invalid transition: {self._state.value} → {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        old_state = self._state
        now = datetime.now(timezone.utc).isoformat()

        entry = {
            "from": old_state.value,
            "to": target.value,
            "reason": reason,
            "iteration": self._iteration,
            "timestamp": now,
            "entered_at": self._state_entered_at,
        }
        self._history.append(entry)

        self._state = target
        self._state_entered_at = now

        print(f"  [STATE] {old_state.value} → {target.value}" + (f" ({reason})" if reason else ""))

    def next_iteration(self) -> None:
        """Increment iteration counter and reset to PLAN state."""
        self._iteration += 1
        if self._iteration >= self._max_iterations:
            self.transition(State.DONE, "max iterations reached")

    def set_max_iterations(self, n: int) -> None:
        self._max_iterations = n

    def set_data(self, key: str, value) -> None:
        self._data[key] = value

    def get_data(self, key: str, default=None):
        return self._data.get(key, default)

    def get_phase_duration(self, phase: State) -> float:
        """Return seconds spent in a given phase across all occurrences.

        Sums durations for all entries where the state was `phase`.
        """
        total = 0.0
        for i, entry in enumerate(self._history):
            if entry.get("to") == phase.value:
                entered = entry.get("timestamp", "")
                # Find the next transition out
                if i + 1 < len(self._history):
                    exited = self._history[i + 1].get("timestamp", "")
                else:
                    exited = datetime.now(timezone.utc).isoformat()
                try:
                    t0 = datetime.fromisoformat(entered)
                    t1 = datetime.fromisoformat(exited)
                    total += (t1 - t0).total_seconds()
                except (ValueError, TypeError):
                    pass
        return total

    def to_dict(self) -> dict:
        return {
            "state": self._state.value,
            "iteration": self._iteration,
            "max_iterations": self._max_iterations,
            "history": self._history,  # keep full transition log
            "data": self._data,
            "state_entered_at": self._state_entered_at,
        }

    def save(self) -> None:
        """Persist state to file."""
        payload = self.to_dict()
        self._state_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> bool:
        """Load state from file. Returns True if loaded successfully."""
        if not self._state_file.exists():
            return False
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            self._state = State(raw.get("state", "INIT"))
            self._iteration = raw.get("iteration", 0)
            self._max_iterations = raw.get("max_iterations", 15)
            self._history = raw.get("history", [])
            self._data = raw.get("data", {})
            self._state_entered_at = raw.get(
                "state_entered_at", datetime.now(timezone.utc).isoformat()
            )
            return True
        except (json.JSONDecodeError, ValueError, KeyError):
            return False

    def reset(self) -> None:
        """Reset to initial state."""
        self._state = State.INIT
        self._iteration = 0
        self._history = []
        self._data = {}
        self.save()
