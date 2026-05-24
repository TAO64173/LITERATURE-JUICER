"""Multi-Agent Router — dispatches tasks to the correct CLI agent.

ROLE SEPARATION (CRITICAL):
  OpenClaw is ADVISORY ONLY — planning and review. NEVER executes code.
  Claude Code is the SOLE CODE EXECUTOR. All file modifications go through Claude.
  Pytest is the SOLE VERIFIER.

Agents:
  PLANNER  → openclaw agent --agent main (planning only — returns task spec)
  JUDGE    → openclaw agent --agent main (review only — returns verdict)
  EXECUTOR → claude --print (code execution — the ONLY agent that modifies files)
  REPAIR   → claude --print (auto-fix — the ONLY agent that modifies files)
  TESTER   → pytest (verification — runs tests, never modifies code)

Rules:
  - ALL OpenClaw calls MUST include --agent main
  - NEVER use dashboard or HTTP calls
  - OpenClaw output is sanitized by orchestrator to strip code patches
  - MUST retry once automatically on failure
  - Windows compatibility: shell=True for .cmd resolution
"""

from __future__ import annotations

import subprocess
import sys
import time
from enum import Enum
from typing import Callable

from error_classifier import classify_error, get_recovery_strategy, ErrorType

# ─── Config ──────────────────────────────────────────────────

IS_WINDOWS = sys.platform == "win32"
DEFAULT_TIMEOUT = 120
EXTENDED_TIMEOUT = 180


class AgentRole(Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    JUDGE = "judge"
    TESTER = "tester"
    REPAIR = "repair"


AGENT_CONFIG: dict[AgentRole, dict] = {
    AgentRole.PLANNER: {
        "cli": "openclaw",
        "args": ["agent", "--agent", "main"],
        "timeout": DEFAULT_TIMEOUT,
        "description": "OpenClaw Planner — generates task specs",
    },
    AgentRole.EXECUTOR: {
        "cli": "claude",
        "args": ["--print"],
        "timeout": EXTENDED_TIMEOUT,
        "description": "Claude Code Executor — implements code changes",
    },
    AgentRole.JUDGE: {
        "cli": "openclaw",
        "args": ["agent", "--agent", "main"],
        "timeout": DEFAULT_TIMEOUT,
        "description": "OpenClaw Judge — reviews execution results",
    },
    AgentRole.TESTER: {
        "cli": "pytest",
        "args": ["-x", "--tb=short", "-q"],
        "timeout": DEFAULT_TIMEOUT,
        "description": "Pytest Tester — runs verification tests",
    },
    AgentRole.REPAIR: {
        "cli": "claude",
        "args": ["--print"],
        "timeout": EXTENDED_TIMEOUT,
        "description": "Repair Agent — auto-fixes failing code",
    },
}


# ─── CLI Dispatch ────────────────────────────────────────────


def _run_cli(
    cli: str,
    args: list[str],
    prompt: str,
    timeout: int,
    workdir: str = "",
) -> tuple[str, int]:
    """Run a CLI command with prompt. Returns (output, returncode)."""
    from agents import PROMPT_MAX_CHARS

    if len(prompt) > PROMPT_MAX_CHARS:
        prompt = prompt[:PROMPT_MAX_CHARS] + "\n...(truncated)"

    if cli == "claude":
        # Claude reads from stdin
        cmd = [cli] + args
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=IS_WINDOWS,
            cwd=workdir or None,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return output, proc.returncode

    elif cli == "openclaw":
        # OpenClaw takes --message flag
        cmd = [cli] + args + ["--message", prompt]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=IS_WINDOWS,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return output, proc.returncode

    elif cli == "pytest":
        # Pytest doesn't take a prompt — runs in workdir
        cmd = [cli] + args
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir or None,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return output, proc.returncode

    else:
        return f"ERROR: unknown CLI '{cli}'", 1


def _validate_openclaw_cmd(args: list[str]) -> None:
    """Guard: ensure --agent main is always present for OpenClaw calls."""
    if "--agent" not in args or "main" not in args:
        raise ValueError(
            "OpenClaw calls MUST include '--agent main'. "
            f"Got args: {args}"
        )


# ─── Router ──────────────────────────────────────────────────


def route_to_agent(
    role: AgentRole,
    prompt: str,
    workdir: str = "",
) -> str:
    """Dispatch prompt to the correct agent CLI with error classification.

    Returns response text or 'ERROR: ...'.
    On failure, classifies error and retries per recovery strategy.
    """
    config = AGENT_CONFIG[role]
    cli = config["cli"]
    args = list(config["args"])
    timeout = config["timeout"]

    # Guard: OpenClaw must have --agent main
    if cli == "openclaw":
        _validate_openclaw_cmd(args)

    print(f"  [router] → {role.value} ({cli})")

    max_retries = 1  # default: one retry
    last_output = ""
    last_rc = 1

    for attempt in range(1, max_retries + 2):  # +2 because range is exclusive
        try:
            output, rc = _run_cli(cli, args, prompt, timeout, workdir)
            last_output = output
            last_rc = rc

            if rc == 0:
                print(f"  [router] {role.value} attempt {attempt} OK")
                return output

            # Classify the error
            error_type = classify_error(output, rc)
            strategy = get_recovery_strategy(error_type)

            print(
                f"  [router] {role.value} attempt {attempt} failed: "
                f"{error_type.value} → {strategy['action']}"
            )

            # Check if we should retry
            if strategy["action"] == "retry" and attempt <= strategy["max_retries"]:
                # If session error, ensure --agent main on retry
                if strategy.get("retry_with_agent_main"):
                    if "--agent" not in args:
                        args.extend(["--agent", "main"])
                    elif "main" not in args:
                        args[args.index("--agent") + 1] = "main"
                time.sleep(1)
                continue

            # Fallback or repair or abort — return the error
            if strategy["action"] == "fallback":
                # For CLI_ERROR, try one more time with shell=True already handled
                return f"ERROR:{error_type.value}: {output}"

            # repair or abort — return error for orchestrator to handle
            return f"ERROR:{error_type.value}: {output}"

        except FileNotFoundError:
            return f"ERROR:CLI_ERROR: {cli} CLI not found"
        except subprocess.TimeoutExpired:
            print(f"  [router] {role.value} attempt {attempt} timed out ({timeout}s)")
            if attempt <= 1:
                time.sleep(2)
                continue
            return f"ERROR:TIMEOUT_ERROR: {cli} timed out after {timeout}s"
        except Exception as e:
            return f"ERROR:UNKNOWN_ERROR: {e}"

    return last_output if last_output.strip() else f"ERROR:UNKNOWN_ERROR: {cli} produced no output"


def get_agent_for_phase(phase: str) -> AgentRole:
    """Map a state machine phase to the appropriate agent role.

    Phase names match State enum values.
    """
    mapping = {
        "PLAN": AgentRole.PLANNER,
        "EXECUTE": AgentRole.EXECUTOR,
        "REVIEW": AgentRole.JUDGE,
        "VERIFY": AgentRole.TESTER,
        "REPAIR": AgentRole.REPAIR,
    }
    role = mapping.get(phase.upper())
    if role is None:
        raise ValueError(f"No agent mapping for phase '{phase}'")
    return role
