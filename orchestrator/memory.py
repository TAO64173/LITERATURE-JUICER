"""Persistent Memory Layer — stores task outcomes, failures, and patterns.

Three JSON-backed stores:
  - success_memory.json — successful task completions
  - failure_memory.json — classified failures with fix strategies
  - pattern_memory.json — extracted reusable patterns

All stores are append-only lists of dicts. Search is keyword-overlap based.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


# ─── Schema ──────────────────────────────────────────────────


def _make_entry(
    task_id: str,
    goal: str,
    outcome: Literal["success", "failure", "pattern"],
    error_type: str = "",
    fix_strategy: str = "",
    diff: str = "",
    tags: list[str] | None = None,
    pattern: str = "",
) -> dict:
    return {
        "task_id": task_id,
        "goal": goal,
        "outcome": outcome,
        "error_type": error_type,
        "fix_strategy": fix_strategy,
        "diff": diff,
        "pattern": pattern,
        "tags": tags or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Keyword Extraction ─────────────────────────────────────


_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below between "
    "and or but not no nor so yet both either neither each every all "
    "any few more most other some such than too very just about also "
    "that this these those it its i me my we our you your he him his "
    "she her they them their what which who whom how when where why".split()
)


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text for matching."""
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _keyword_overlap(query: str, target: str) -> float:
    """Calculate keyword overlap score between 0.0 and 1.0."""
    q_kw = _extract_keywords(query)
    t_kw = _extract_keywords(target)
    if not q_kw or not t_kw:
        return 0.0
    overlap = q_kw & t_kw
    return len(overlap) / max(len(q_kw), len(t_kw))


# ─── Memory Store ────────────────────────────────────────────


class MemoryStore:
    """Persistent memory backed by three JSON files."""

    def __init__(self, memory_dir: Path) -> None:
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)

        self._success_file = memory_dir / "success_memory.json"
        self._failure_file = memory_dir / "failure_memory.json"
        self._pattern_file = memory_dir / "pattern_memory.json"

        self._successes: list[dict] = self._load(self._success_file)
        self._failures: list[dict] = self._load(self._failure_file)
        self._patterns: list[dict] = self._load(self._pattern_file)

    @staticmethod
    def _load(path: Path) -> list[dict]:
        if not path.exists():
            path.write_text("[]", encoding="utf-8")
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    @staticmethod
    def _save(path: Path, data: list[dict]) -> None:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _flush(self, kind: Literal["success", "failure", "pattern"]) -> None:
        if kind == "success":
            self._save(self._success_file, self._successes)
        elif kind == "failure":
            self._save(self._failure_file, self._failures)
        else:
            self._save(self._pattern_file, self._patterns)

    # ── Store Operations ─────────────────────────────────────

    def store_success(
        self,
        task_id: str,
        goal: str,
        diff: str = "",
        tags: list[str] | None = None,
    ) -> None:
        entry = _make_entry(
            task_id=task_id,
            goal=goal,
            outcome="success",
            diff=diff,
            tags=tags,
        )
        self._successes.append(entry)
        self._flush("success")

    def store_failure(
        self,
        task_id: str,
        goal: str,
        error_type: str = "",
        fix_strategy: str = "",
        tags: list[str] | None = None,
    ) -> None:
        entry = _make_entry(
            task_id=task_id,
            goal=goal,
            outcome="failure",
            error_type=error_type,
            fix_strategy=fix_strategy,
            tags=tags,
        )
        self._failures.append(entry)
        self._flush("failure")

    def store_pattern(
        self,
        goal: str,
        pattern: str,
        tags: list[str] | None = None,
    ) -> None:
        entry = _make_entry(
            task_id="",
            goal=goal,
            outcome="pattern",
            pattern=pattern,
            tags=tags,
        )
        self._patterns.append(entry)
        self._flush("pattern")

    # ── Search Operations ────────────────────────────────────

    def search_similar(self, goal: str, limit: int = 5) -> list[dict]:
        """Search all memories by keyword overlap with goal.

        Returns entries sorted by relevance (highest overlap first).
        """
        all_entries = self._successes + self._failures + self._patterns
        if not all_entries:
            return []

        scored = []
        for entry in all_entries:
            target = entry.get("goal", "") + " " + entry.get("pattern", "")
            score = _keyword_overlap(goal, target)
            if score > 0.0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def get_fix_for_error(self, error_type: str) -> str | None:
        """Look up a known fix strategy for a given error type.

        Returns the most recent fix_strategy that matches, or None.
        """
        for entry in reversed(self._failures):
            if entry.get("error_type") == error_type and entry.get("fix_strategy"):
                return entry["fix_strategy"]
        return None

    def get_stats(self) -> dict:
        """Return memory statistics."""
        total = len(self._successes) + len(self._failures)
        success_rate = len(self._successes) / total if total > 0 else 0.0

        error_counts: dict[str, int] = {}
        for entry in self._failures:
            et = entry.get("error_type", "unknown")
            error_counts[et] = error_counts.get(et, 0) + 1

        return {
            "total_tasks": total,
            "successes": len(self._successes),
            "failures": len(self._failures),
            "patterns": len(self._patterns),
            "success_rate": round(success_rate, 3),
            "common_errors": dict(
                sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
            ),
        }
