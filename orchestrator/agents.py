"""Agent Wrappers — OpenClaw and Claude Code CLI wrappers with self-healing.

Rules:
  - OpenClaw: ALWAYS use `openclaw agent --agent main --message <text>`
  - Claude: use `claude --print` with stdin pipe
  - On Windows: use shell=True for .cmd file resolution (npm globals)
  - On Unix: use shell=False for safety
  - Auto-retry on session errors, timeout, CLI errors
  - Escalate to replan on repeated failures
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# On Windows, npm global installs create .cmd wrappers that need shell=True
IS_WINDOWS = sys.platform == "win32"

# ─── Config ──────────────────────────────────────────────────

MAX_RETRY = 3
DEFAULT_TIMEOUT = 120  # seconds per CLI call
HARD_TIMEOUT = 300  # seconds — total budget per agent call
PROMPT_MAX_CHARS = 15000

# ─── Error Classification ────────────────────────────────────

SESSION_ERROR_MARKERS = (
    "no target session selected",
    "no agent",
    "session not found",
    "agent not found",
    "no session",
)

INFRA_ERROR_MARKERS = (
    "not found",
    "not recognized",
    "enoent",
    "no such file",
)


def _is_session_error(output: str) -> bool:
    lower = output.lower()
    return any(marker in lower for marker in SESSION_ERROR_MARKERS)


def _is_infra_error(output: str) -> bool:
    lower = output.lower()
    return any(marker in lower for marker in INFRA_ERROR_MARKERS)


# ─── OpenClaw Wrapper ────────────────────────────────────────


def call_openclaw(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Call OpenClaw agent CLI. Returns response text or 'ERROR: ...'.

    Always uses --agent main. Retries up to MAX_RETRY on session errors.
    On Windows, uses shell=True for .cmd file resolution.
    """
    if len(prompt) > PROMPT_MAX_CHARS:
        prompt = prompt[:PROMPT_MAX_CHARS] + "\n...(truncated)"

    cmd = ["openclaw", "agent", "--agent", "main", "--message", prompt]

    # Guard: ensure --agent main is always present
    assert "--agent" in cmd and "main" in cmd, (
        "OpenClaw calls MUST include '--agent main'"
    )

    t0 = time.monotonic()
    last_output = ""

    for attempt in range(1, MAX_RETRY + 1):
        elapsed = time.monotonic() - t0
        if elapsed > HARD_TIMEOUT:
            return f"ERROR: openclaw total timeout ({elapsed:.0f}s > {HARD_TIMEOUT}s)"

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=IS_WINDOWS,
                encoding="utf-8",
                errors="replace",
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            last_output = stdout

            if proc.returncode == 0:
                print(f"  [openclaw] attempt {attempt} OK ({time.monotonic() - t0:.0f}s)")
                return stdout

            combined = f"{stderr}\n{stdout}".strip()
            print(f"  [openclaw] attempt {attempt} rc={proc.returncode}: {combined[:200]}")

            # Hard infra error — no point retrying
            if _is_infra_error(combined) and "session" not in combined.lower():
                return f"ERROR: {combined}"

            # Session error — retry
            if _is_session_error(combined) and attempt < MAX_RETRY:
                print(f"  [openclaw] session error, retrying ({attempt + 1}/{MAX_RETRY})...")
                time.sleep(1)
                continue

            # Other error — break
            break

        except FileNotFoundError:
            return "ERROR: openclaw CLI not found. Install with: npm install -g openclaw"
        except subprocess.TimeoutExpired:
            print(f"  [openclaw] attempt {attempt} timed out ({timeout}s)")
            if attempt < MAX_RETRY:
                time.sleep(2)
                continue
            return f"ERROR: openclaw timed out after {timeout}s (tried {MAX_RETRY}x)"
        except Exception as e:
            return f"ERROR: openclaw exception: {e}"

    return last_output if last_output.strip() else "ERROR: openclaw produced no output"


# ─── Claude Code Wrapper ─────────────────────────────────────


def call_claude(prompt: str, timeout: int = DEFAULT_TIMEOUT, workdir: str = "") -> str:
    """Call Claude Code CLI via --print with stdin pipe.

    Returns response text or 'ERROR: ...'.
    On Windows, uses shell=True for .cmd file resolution.
    """
    if len(prompt) > PROMPT_MAX_CHARS:
        prompt = prompt[:PROMPT_MAX_CHARS] + "\n...(truncated)"

    cmd = ["claude", "--print"]

    t0 = time.monotonic()

    for attempt in range(1, MAX_RETRY + 1):
        try:
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
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            if proc.returncode == 0:
                print(f"  [claude] attempt {attempt} OK ({time.monotonic() - t0:.0f}s)")
                return stdout

            combined = f"{stderr}\n{stdout}".strip()
            print(f"  [claude] attempt {attempt} rc={proc.returncode}: {combined[:200]}")

            # Retry on transient errors
            if attempt < MAX_RETRY:
                time.sleep(2)
                continue

            return f"ERROR: claude exited with code {proc.returncode}\n{combined}"

        except FileNotFoundError:
            return "ERROR: claude CLI not found. Install Claude Code CLI."
        except subprocess.TimeoutExpired:
            print(f"  [claude] attempt {attempt} timed out ({timeout}s)")
            if attempt < MAX_RETRY:
                time.sleep(2)
                continue
            return f"ERROR: claude timed out after {timeout}s (tried {MAX_RETRY}x)"
        except Exception as e:
            return f"ERROR: claude exception: {e}"

    return "ERROR: claude produced no output"


# ─── Gemini API (standalone, used by router.py) ──────────────


def call_gemini_api(prompt: str) -> str:
    """Call Gemini API. Returns response text or 'ERROR: ...'.

    Standalone function — router.py uses this as fallback when OpenClaw is unavailable.
    """
    import os
    import requests

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "ERROR: GEMINI_API_KEY not set in .env"

    base_url = os.environ.get(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    )
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    url = f"{base_url}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4000},
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"ERROR: Gemini API: {e}"
