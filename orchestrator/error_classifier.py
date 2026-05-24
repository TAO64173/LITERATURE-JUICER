"""Error Intelligence System — classifies errors and maps to recovery strategies.

Error types:
  SESSION_ERROR  — OpenClaw session/agent issues → retry with --agent main
  CLI_ERROR      — CLI not found / infra issues  → fallback subprocess retry
  CODE_ERROR     — syntax/import/indent errors    → trigger repair loop
  TEST_ERROR     — pytest failures                → trigger repair loop
  TIMEOUT_ERROR  — subprocess timeouts            → retry once only
  UNKNOWN_ERROR  — anything else                  → retry once, then abort

Rules:
  - System MUST NEVER stall
  - Every error MUST be classified
  - Recovery strategy is deterministic per error type
"""

from __future__ import annotations

from enum import Enum


class ErrorType(Enum):
    SESSION_ERROR = "SESSION_ERROR"
    CLI_ERROR = "CLI_ERROR"
    CODE_ERROR = "CODE_ERROR"
    TEST_ERROR = "TEST_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# ─── Markers ─────────────────────────────────────────────────

SESSION_MARKERS = (
    "no target session selected",
    "no agent",
    "session not found",
    "agent not found",
    "no session",
    "--agent main",
)

CLI_MARKERS = (
    "not found",
    "not recognized",
    "enoent",
    "no such file",
    "file not found",
    "command not found",
)

CODE_MARKERS = (
    "syntaxerror",
    "syntax error",
    "indentationerror",
    "indentation error",
    "importerror",
    "import error",
    "modulenotfounderror",
    "nameerror",
    "typeerror",
    "attributeerror",
)

TEST_MARKERS = (
    "failed",
    "assert",
    "assertionerror",
    "assertion error",
    "test_",
    "error in test",
    "pytest",
)

TIMEOUT_MARKERS = (
    "timed out",
    "timeout",
    "time out",
    "timedout",
)


# ─── Classifier ──────────────────────────────────────────────


def classify_error(output: str, returncode: int = 1) -> ErrorType:
    """Classify an error from CLI output and return code.

    Checks markers in priority order: timeout > session > cli > code > test > unknown.
    """
    lower = output.lower()

    for marker in TIMEOUT_MARKERS:
        if marker in lower:
            return ErrorType.TIMEOUT_ERROR

    for marker in SESSION_MARKERS:
        if marker in lower:
            return ErrorType.SESSION_ERROR

    for marker in CLI_MARKERS:
        if marker in lower:
            return ErrorType.CLI_ERROR

    for marker in CODE_MARKERS:
        if marker in lower:
            return ErrorType.CODE_ERROR

    for marker in TEST_MARKERS:
        if marker in lower:
            return ErrorType.TEST_ERROR

    return ErrorType.UNKNOWN_ERROR


# ─── Recovery Strategies ─────────────────────────────────────


_RECOVERY_MAP: dict[ErrorType, dict] = {
    ErrorType.SESSION_ERROR: {
        "action": "retry",
        "retry_with_agent_main": True,
        "max_retries": 2,
        "description": "Retry with --agent main automatically",
    },
    ErrorType.CLI_ERROR: {
        "action": "fallback",
        "retry_with_agent_main": False,
        "max_retries": 1,
        "description": "Fallback to safe subprocess retry",
    },
    ErrorType.CODE_ERROR: {
        "action": "repair",
        "retry_with_agent_main": False,
        "max_retries": 1,
        "description": "Trigger repair loop — code has syntax/import errors",
    },
    ErrorType.TEST_ERROR: {
        "action": "repair",
        "retry_with_agent_main": False,
        "max_retries": 1,
        "description": "Trigger repair loop — tests are failing",
    },
    ErrorType.TIMEOUT_ERROR: {
        "action": "retry",
        "retry_with_agent_main": False,
        "max_retries": 1,
        "description": "Retry once only — previous attempt timed out",
    },
    ErrorType.UNKNOWN_ERROR: {
        "action": "retry",
        "retry_with_agent_main": False,
        "max_retries": 1,
        "description": "Retry once, then abort — unknown error type",
    },
}


def get_recovery_strategy(error_type: ErrorType) -> dict:
    """Return the recovery strategy for a given error type.

    Returns dict with keys: action, retry_with_agent_main, max_retries, description.
    """
    return dict(_RECOVERY_MAP.get(error_type, _RECOVERY_MAP[ErrorType.UNKNOWN_ERROR]))
