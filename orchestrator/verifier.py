"""Verification Layer — pytest runner + diff validation + result gating.

Extends basic pytest with:
  - File diff validation (did Claude actually change files?)
  - Structured result validation (is the ExecutionResult well-formed?)
  - Test pass/fail gating (blocks progression on failure)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path


DEFAULT_TIMEOUT = 120


def run_pytest(project_root: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Run pytest and return structured result.

    Returns:
        {"passed": bool, "output": str, "duration": float}
    """
    print("  [verify] running pytest...")
    t0 = time.monotonic()

    try:
        proc = subprocess.run(
            ["pytest", "-x", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.monotonic() - t0
        output = (proc.stdout or "") + (proc.stderr or "")
        passed = proc.returncode == 0

        print(f"  [verify] pytest: {'PASS' if passed else 'FAIL'} ({duration:.0f}s)")
        if not passed:
            print(f"  [verify] errors: {output[:300]}")

        return {"passed": passed, "output": output, "duration": duration}

    except FileNotFoundError:
        return {"passed": False, "output": "pytest not found", "duration": 0}
    except subprocess.TimeoutExpired:
        return {"passed": False, "output": f"pytest timed out after {timeout}s", "duration": timeout}


def validate_diff(project_root: str) -> dict:
    """Check if any files were actually modified.

    Returns:
        {"has_changes": bool, "changed_files": list[str]}
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=project_root,
            encoding="utf-8",
            errors="replace",
        )
        changed = [f.strip() for f in (proc.stdout or "").split("\n") if f.strip()]

        # Also check staged changes
        proc2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=project_root,
            encoding="utf-8",
            errors="replace",
        )
        staged = [f.strip() for f in (proc2.stdout or "").split("\n") if f.strip()]

        all_changes = list(set(changed + staged))

        # Filter out orchestrator output files
        all_changes = [f for f in all_changes if not f.startswith("orchestrator/outputs/")]

        return {"has_changes": len(all_changes) > 0, "changed_files": all_changes}

    except Exception as e:
        return {"has_changes": True, "changed_files": [f"diff check error: {e}"]}


def validate_execution_output(raw_output: str) -> dict:
    """Validate that Claude's execution output indicates real work was done.

    Returns:
        {"valid": bool, "indicators": list[str]}
    """
    indicators = []
    lower = raw_output.lower()

    # Positive indicators — Claude actually did something
    positive = (
        "changed", "modified", "updated", "added", "created",
        "implemented", "fixed", "wrote", "edited", "replaced",
        "file:", "diff", "@@", "+++",
    )
    for marker in positive:
        if marker in lower:
            indicators.append(f"found '{marker}'")

    # Negative indicators — Claude didn't understand the task
    negative = (
        "i cannot", "i can't", "i'm unable", "no changes",
        "missing from your message", "unclear", "please provide",
    )
    for marker in negative:
        if marker in lower:
            indicators.append(f"NEGATIVE: found '{marker}'")

    has_positive = any(not i.startswith("NEGATIVE:") for i in indicators)
    has_negative = any(i.startswith("NEGATIVE:") for i in indicators)

    return {
        "valid": has_positive and not has_negative,
        "indicators": indicators,
    }


def full_verify(project_root: str, execution_output: str) -> dict:
    """Run full verification pipeline.

    Returns:
        {
            "passed": bool,
            "pytest": {...},
            "diff": {...},
            "output_valid": {...},
        }
    """
    pytest_result = run_pytest(project_root)
    diff_result = validate_diff(project_root)
    output_result = validate_execution_output(execution_output)

    passed = (
        pytest_result["passed"]
        and output_result["valid"]
    )

    return {
        "passed": passed,
        "pytest": pytest_result,
        "diff": diff_result,
        "output_valid": output_result,
    }
