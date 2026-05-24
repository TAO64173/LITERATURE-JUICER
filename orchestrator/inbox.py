"""Task Inbox — file-based task queue for OpenClaw → Orchestrator handoff.

OpenClaw writes a task JSON to inbox/current_task.json.
Orchestrator reads it on startup, executes, then archives completed tasks.

Schema:
{
  "goal": "...",
  "success_criteria": [],
  "constraints": [],
  "allowed_files": []
}
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INBOX_DIR = Path(__file__).parent / "inbox"
CURRENT_TASK = INBOX_DIR / "current_task.json"
ARCHIVE_DIR = INBOX_DIR / "archive"


def _ensure_dirs() -> None:
    INBOX_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)


def has_task() -> bool:
    """Check if a task file exists with a non-empty goal."""
    _ensure_dirs()
    if not CURRENT_TASK.exists():
        return False
    try:
        data = json.loads(CURRENT_TASK.read_text(encoding="utf-8"))
        return bool(data.get("goal", "").strip())
    except (json.JSONDecodeError, OSError):
        return False


def read_task() -> dict[str, Any] | None:
    """Read the current task. Returns None if no task or empty goal."""
    _ensure_dirs()
    if not CURRENT_TASK.exists():
        return None
    try:
        data = json.loads(CURRENT_TASK.read_text(encoding="utf-8"))
        if not data.get("goal", "").strip():
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def write_task(
    goal: str,
    success_criteria: list[str] | None = None,
    constraints: list[str] | None = None,
    allowed_files: list[str] | None = None,
) -> None:
    """Write a new task to the inbox (overwrites current)."""
    _ensure_dirs()
    task = {
        "goal": goal,
        "success_criteria": success_criteria or [],
        "constraints": constraints or [],
        "allowed_files": allowed_files or [],
    }
    CURRENT_TASK.write_text(
        json.dumps(task, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clear_task() -> None:
    """Remove the current task file."""
    _ensure_dirs()
    if CURRENT_TASK.exists():
        CURRENT_TASK.unlink()


def archive_task(outcome: str = "completed") -> Path | None:
    """Move current task to archive with timestamp and outcome.

    Returns the archive file path, or None if no task to archive.
    """
    _ensure_dirs()
    if not CURRENT_TASK.exists():
        return None

    try:
        data = json.loads(CURRENT_TASK.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"{ts}_{outcome}.json"
    archive_path = ARCHIVE_DIR / archive_name

    data["archived_at"] = datetime.now(timezone.utc).isoformat()
    data["outcome"] = outcome

    archive_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    CURRENT_TASK.unlink()
    return archive_path
