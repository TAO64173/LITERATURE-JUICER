#!/usr/bin/env python3
"""Autonomous AI workflow orchestrator for Literature Juicer.

Coordinates a full autonomous loop between:
  - OpenClaw (planner + reviewer)
  - Claude Code (executor)
  - pytest (verifier)

State machine: INIT → PLAN → EXECUTE → VERIFY → REVIEW → REPAIR → DONE

Usage:
    python orchestrator/orchestrator.py                         # read from inbox
    python orchestrator/orchestrator.py --goal "Fix path bug"   # explicit goal
    python orchestrator/orchestrator.py --watch                 # poll inbox for tasks
    python orchestrator/orchestrator.py --reset --goal "New goal"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import inbox

from contracts import (
    TaskSpec,
    ExecutionResult,
    ReviewDecision,
)
from state_machine import State, StateMachine, TransitionError
from verifier import full_verify
from memory import MemoryStore
from error_classifier import classify_error, get_recovery_strategy
from router import AgentRole, route_to_agent

# ─── Paths ───────────────────────────────────────────────────

ORCHESTRATOR_DIR = Path(__file__).parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent
STATE_FILE = ORCHESTRATOR_DIR / "state.json"
PROMPTS_DIR = ORCHESTRATOR_DIR / "prompts"
OUTPUTS_DIR = ORCHESTRATOR_DIR / "outputs"
MEMORY_DIR = ORCHESTRATOR_DIR / "memory"

OUTPUTS_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────

MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_MAX_ITERATIONS = 15


# ─── Helpers ─────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_output(filename: str, content: str) -> Path:
    path = OUTPUTS_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


# ─── Prompt Builders ─────────────────────────────────────────


def _sanitize_openclaw_output(raw: str, role: str = "planner") -> str:
    """Strip code patches and implementation details from OpenClaw output.

    OpenClaw is advisory only — it must NEVER contain executable code.
    This function extracts ONLY the structured instruction lines and discards
    everything else: code blocks, diffs, commentary, and leaked implementation.

    For planner: keeps only TASK:, FILES:, VERIFICATION: lines.
    For reviewer: keeps only VERDICT:, FEEDBACK:, ISSUES: lines.
    """
    lines = raw.strip().split("\n")
    kept = []
    in_code_block = False
    stripped_count = 0

    # What structured prefixes to keep per role
    if role == "planner":
        prefixes = ("TASK:", "FILES:", "VERIFICATION:", "VERIFY:")
    else:
        prefixes = ("VERDICT:", "FEEDBACK:", "ISSUES:")

    for line in lines:
        stripped = line.strip()

        # Toggle code block tracking
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            stripped_count += 1
            continue

        # Skip anything inside code blocks
        if in_code_block:
            stripped_count += 1
            continue

        # Skip diff markers
        if stripped.startswith(("--- a/", "+++ b/", "@@ ", "diff --git")):
            stripped_count += 1
            continue

        # Skip indented code (likely patches)
        if line.startswith("    ") and any(
            stripped.startswith(kw)
            for kw in ("def ", "class ", "import ", "from ", "if ", "for ", "while ", "return ")
        ):
            stripped_count += 1
            continue

        upper = stripped.upper()

        # Keep ONLY structured instruction lines
        if upper.startswith(prefixes):
            kept.append(stripped)
        elif not stripped:
            continue  # skip blank lines
        else:
            # Everything else is discarded — OpenClaw is advisory only
            stripped_count += 1

    if stripped_count > 0:
        print(f"  [guard] Stripped {stripped_count} code/patch lines from OpenClaw {role} output")

    return "\n".join(kept) if kept else raw


def _build_memory_context(memories: list[dict]) -> str:
    """Format memory entries into a context block for prompts."""
    if not memories:
        return ""
    lines = ["Similar tasks found in memory:"]
    for m in memories:
        outcome = m.get("outcome", "unknown")
        goal = m.get("goal", "")
        if outcome == "success":
            diff = m.get("diff", "")[:200]
            lines.append(f"  - [success] \"{goal}\" → {diff}")
        elif outcome == "failure":
            fix = m.get("fix_strategy", "")[:200]
            err = m.get("error_type", "")
            lines.append(f"  - [failure] \"{goal}\" → error: {err}, fix: {fix}")
        elif outcome == "pattern":
            pattern = m.get("pattern", "")[:200]
            lines.append(f"  - [pattern] \"{goal}\" → {pattern}")
    return "\n".join(lines)


def build_plan_prompt(
    goal: str,
    completed: list[str],
    failed: list[str],
    memory_context: str = "",
) -> str:
    """Build prompt for OpenClaw to generate the next task."""
    completed_str = "\n".join(f"  - {t}" for t in completed) or "  (none)"
    failed_str = "\n".join(f"  - {t}" for t in failed) or "  (none)"
    system = read_prompt("system.txt")
    plan_template = read_prompt("step1_design.txt")

    mem_block = f"\n{memory_context}\n" if memory_context else ""

    return f"""{system}

{plan_template}
{mem_block}
Goal: {goal}
Completed tasks:
{completed_str}
Failed tasks:
{failed_str}

Generate ONE task that moves toward the goal. Output EXACTLY 3 lines:
TASK: <one sentence>
FILES: <file paths>
VERIFICATION: <how to verify>"""


def build_execute_prompt(task_spec: TaskSpec, memory_context: str = "") -> str:
    """Build prompt for Claude Code to execute a task."""
    system = read_prompt("system.txt")
    impl_template = read_prompt("step2_implement.txt")

    files_str = ", ".join(task_spec.files) if task_spec.files else "auto-detect"
    constraints_str = "\n".join(f"- {c}" for c in task_spec.constraints)
    criteria_str = "\n".join(f"- {c}" for c in task_spec.success_criteria)

    mem_block = f"\n{memory_context}\n" if memory_context else ""

    return f"""{system}

{impl_template}
{mem_block}
Task: {task_spec.goal}
Files to modify: {files_str}
Constraints:
{constraints_str}
Success criteria:
{criteria_str}

Make the actual code changes now. After changing files, summarize what you changed."""


def build_review_prompt(task_spec: TaskSpec, result: ExecutionResult, verification: dict) -> str:
    """Build prompt for OpenClaw to review the result."""
    review_template = read_prompt("review.txt")
    test_status = "PASSED" if verification.get("passed") else "FAILED"
    test_output = verification.get("pytest", {}).get("output", "")[:1000]

    return f"""{review_template}

Task: {task_spec.goal}
Files targeted: {", ".join(task_spec.files) if task_spec.files else "auto"}
Test result: {test_status}
Test output:
{test_output}

Implementation summary:
{result.diff_summary[:2000]}

Output EXACTLY 3 lines:
VERDICT: PASS or FAIL
FEEDBACK: <2-3 sentences>
ISSUES: <bullet list or None>"""


# ─── Core Loop ───────────────────────────────────────────────


class Orchestrator:
    """Main autonomous orchestrator using state machine + contracts + memory."""

    def __init__(self, goal: str, supervisor: str = "openclaw", max_iter: int = 15) -> None:
        self.goal = goal
        self.supervisor = supervisor
        self.sm = StateMachine(STATE_FILE)
        self.sm.set_max_iterations(max_iter)
        self.memory = MemoryStore(MEMORY_DIR)

        # Persistent state across iterations
        self.completed_tasks: list[str] = []
        self.failed_tasks: list[str] = []
        self.consecutive_failures = 0

    def run(self) -> None:
        """Run the full autonomous loop."""
        print("=" * 60)
        print(f"Goal: {self.goal}")
        print(f"Supervisor: {self.supervisor}")
        print(f"Max iterations: {self.sm._max_iterations}")
        print(f"Memory: {self.memory.get_stats()}")
        print("=" * 60)

        # Ensure we start in PLAN state
        if self.sm.state == State.INIT:
            self.sm.transition(State.PLAN, "begin planning")

        while not self.sm.is_terminal:
            # Check iteration limit
            if self.sm.iteration >= self.sm._max_iterations:
                print("\n[STOP] Max iterations reached.")
                self.sm.transition(State.DONE, "max iterations reached")
                break

            self._run_one_iteration()

            # Check if we hit STALL state
            if self.sm.state == State.STALL:
                print(f"\n[STALL] {self.consecutive_failures} consecutive failures.")
                self.sm.transition(State.DONE, "stalled")
                break

            # Advance iteration counter
            self.sm.next_iteration()
            if self.sm.is_terminal:
                break

            # After a successful review, state is already PLAN (transitioned in _review)
            # After a failure cycle (REPAIR → EXECUTE → VERIFY → REVIEW), state may vary
            # Ensure we're in PLAN for the next iteration
            if self.sm.state not in (State.PLAN,):
                try:
                    self.sm.transition(State.PLAN, f"iteration {self.sm.iteration + 1}")
                except TransitionError:
                    # Can't get to PLAN — stop
                    print(f"\n[STOP] Cannot transition to PLAN from {self.sm.state.value}")
                    self.sm.transition(State.DONE, "unrecoverable state")
                    break

        self._print_summary()
        self.sm.save()

    def _run_one_iteration(self) -> None:
        """Execute one PLAN → EXECUTE → VERIFY → REVIEW cycle.

        Handles REPAIR internally. Always ends in PLAN or DONE state.
        """
        iteration = self.sm.iteration
        print(f"\n{'='*60}")
        print(f"Iteration {iteration + 1}/{self.sm._max_iterations}")
        print(f"State: {self.sm.state.value}")
        print(f"{'='*60}")

        try:
            # ── PLAN ──
            task_spec = self._plan()
            if task_spec is None:
                self.consecutive_failures += 1
                # Return to PLAN for next attempt
                if self.sm.state != State.PLAN:
                    try:
                        self.sm.transition(State.PLAN, "plan failed, retry next iter")
                    except TransitionError:
                        pass
                return

            # ── EXECUTE ──
            result = self._execute(task_spec)

            # ── VERIFY ──
            verification = self._verify(result)

            # ── REVIEW ──
            self._review(task_spec, result, verification)

            # If verification or review failed, do one REPAIR cycle
            if self.sm.state == State.REPAIR:
                self._do_repair_cycle(task_spec)

        except TransitionError as e:
            print(f"\n[ERROR] State transition failed: {e}")
            self.consecutive_failures += 1
            # Try to recover to PLAN
            try:
                if self.sm.state != State.PLAN and not self.sm.is_terminal:
                    self.sm.transition(State.PLAN, "error recovery")
            except TransitionError:
                pass
        except Exception as e:
            print(f"\n[ERROR] Unexpected: {e}")
            self.consecutive_failures += 1
            try:
                if self.sm.state != State.PLAN and not self.sm.is_terminal:
                    self.sm.transition(State.PLAN, "error recovery")
            except TransitionError:
                pass

    def _plan(self) -> TaskSpec | None:
        """PLAN phase: search memory, then ask OpenClaw for the next task."""
        print("\n--- PLANNING ---")

        # Self-learning: search memory for similar tasks
        memories = self.memory.search_similar(self.goal, limit=5)
        memory_context = _build_memory_context(memories)
        if memory_context:
            print(f"  [memory] Found {len(memories)} similar task(s)")

        prompt = build_plan_prompt(
            self.goal, self.completed_tasks, self.failed_tasks, memory_context
        )

        # Route to planner agent via router
        response = route_to_agent(AgentRole.PLANNER, prompt)

        # Guard: strip any code patches OpenClaw may have leaked
        if not response.startswith("ERROR:"):
            response = _sanitize_openclaw_output(response, role="planner")

        save_output(f"plan_iter{self.sm.iteration}.txt", response)

        if response.startswith("ERROR:"):
            error_type = classify_error(response)
            print(f"  [FAIL] Planning error ({error_type.value}): {response[:200]}")
            # Store failure in memory
            self.memory.store_failure(
                task_id=f"task_{self.sm.iteration}",
                goal=self.goal,
                error_type=error_type.value,
                fix_strategy=get_recovery_strategy(error_type).get("description", ""),
            )
            return None

        # Parse into TaskSpec
        task_spec = TaskSpec.from_planner_output(
            response,
            task_id=f"task_{self.sm.iteration}",
            goal=self.goal,
        )

        if not task_spec.goal or task_spec.goal == self.goal:
            # Planner returned the goal itself, not a specific task
            # Try to extract a task from the context
            for line in response.strip().split("\n"):
                stripped = line.strip()
                if stripped.upper().startswith("TASK:"):
                    task_spec = TaskSpec(
                        task_id=task_spec.task_id,
                        goal=stripped.split(":", 1)[1].strip(),
                        context=response[:2000],
                        files=task_spec.files,
                        constraints=task_spec.constraints,
                        success_criteria=task_spec.success_criteria,
                    )
                    break

        print(f"  Task: {task_spec.goal[:120]}")
        print(f"  Files: {task_spec.files}")

        # Transition to EXECUTE
        self.sm.transition(State.EXECUTE, f"task: {task_spec.goal[:80]}")
        return task_spec

    def _execute(self, task_spec: TaskSpec) -> ExecutionResult:
        """EXECUTE phase: search memory for context, route to Claude Code."""
        print("\n--- EXECUTING ---")

        # Self-learning: search memory for similar task patterns
        memories = self.memory.search_similar(task_spec.goal, limit=3)
        memory_context = _build_memory_context(memories)

        prompt = build_execute_prompt(task_spec, memory_context)
        project_root = str(PROJECT_ROOT)

        # Route to executor agent via router
        raw_output = route_to_agent(AgentRole.EXECUTOR, prompt, workdir=project_root)

        save_output(f"execute_iter{self.sm.iteration}.txt", raw_output)

        # Classify result
        if raw_output.startswith("ERROR:"):
            error_type = classify_error(raw_output)
            result = ExecutionResult(
                task_id=task_spec.task_id,
                status="error",
                error_message=raw_output,
            )
            print(f"  [FAIL] Execution error ({error_type.value}): {raw_output[:200]}")
            # Store failure in memory
            self.memory.store_failure(
                task_id=task_spec.task_id,
                goal=task_spec.goal,
                error_type=error_type.value,
                fix_strategy=get_recovery_strategy(error_type).get("description", ""),
            )
        else:
            result = ExecutionResult(
                task_id=task_spec.task_id,
                status="success",
                diff_summary=raw_output[:3000],
            )
            print(f"  [OK] Execution complete ({len(raw_output)} chars)")

        # Transition to VERIFY
        self.sm.transition(State.VERIFY, "execution complete")
        return result

    def _verify(self, result: ExecutionResult) -> dict:
        """VERIFY phase: run pytest and validate output."""
        print("\n--- VERIFYING ---")

        project_root = str(PROJECT_ROOT)
        verification = full_verify(project_root, result.diff_summary)

        if result.status == "success":
            result.test_result = "pass" if verification["passed"] else "fail"

        passed = verification["passed"]
        print(f"  pytest: {'PASS' if verification['pytest']['passed'] else 'FAIL'}")
        print(f"  output valid: {verification['output_valid']['valid']}")
        print(f"  overall: {'PASS' if passed else 'FAIL'}")

        # Transition based on verification result
        if passed:
            self.sm.transition(State.REVIEW, "verification passed")
        else:
            self.sm.transition(State.REPAIR, "verification failed")

        return verification

    def _review(self, task_spec: TaskSpec, result: ExecutionResult, verification: dict) -> None:
        """REVIEW phase: route to judge agent, then handle decision."""
        if self.sm.state == State.REPAIR:
            # Verification failed — go straight to repair
            self._handle_failure(task_spec, result, verification.get("pytest", {}).get("output", ""))
            return

        print("\n--- REVIEWING ---")

        prompt = build_review_prompt(task_spec, result, verification)

        # Route to judge agent via router
        response = route_to_agent(AgentRole.JUDGE, prompt)

        # Guard: strip any code patches OpenClaw may have leaked
        if not response.startswith("ERROR:"):
            response = _sanitize_openclaw_output(response, role="reviewer")

        save_output(f"review_iter{self.sm.iteration}.txt", response)

        if response.startswith("ERROR:"):
            print(f"  [WARN] Review error: {response[:200]}")
            # If review fails but tests passed, accept it
            if verification["passed"]:
                self._handle_success(task_spec)
            else:
                self._handle_failure(task_spec, result, "review failed, tests also failed")
            return

        decision = ReviewDecision.from_reviewer_output(response)
        print(f"  Decision: {decision.decision}")
        print(f"  Reason: {decision.reason[:200]}")

        if decision.decision == "PASS":
            self.sm.transition(State.PLAN, "review passed")
            self._handle_success(task_spec)
        else:
            self.sm.transition(State.REPAIR, f"review failed: {decision.reason[:80]}")
            self._handle_failure(task_spec, result, decision.reason)

    def _handle_success(self, task_spec: TaskSpec) -> None:
        """Record a successful task completion and store in memory."""
        self.completed_tasks.append(task_spec.goal)
        self.consecutive_failures = 0
        print(f"  [OK] Task completed ({len(self.completed_tasks)} total)")

        # Self-learning: store success in memory
        self.memory.store_success(
            task_id=task_spec.task_id,
            goal=task_spec.goal,
            diff=task_spec.context[:500],
            tags=["success"],
        )

        # Check goal completion
        if self._is_goal_complete():
            print("\n[DONE] Goal completed!")
            self.sm.transition(State.DONE, "goal completed")

    def _handle_failure(self, task_spec: TaskSpec, result: ExecutionResult, feedback: str) -> None:
        """Handle a failed task — classify error, store in memory, transition to REPAIR."""
        self.failed_tasks.append(task_spec.goal)
        self.consecutive_failures += 1

        # Error intelligence: classify the failure
        error_type = classify_error(feedback)
        strategy = get_recovery_strategy(error_type)

        # Self-learning: store classified failure in memory
        self.memory.store_failure(
            task_id=task_spec.task_id,
            goal=task_spec.goal,
            error_type=error_type.value,
            fix_strategy=strategy.get("description", ""),
            tags=["failure", error_type.value.lower()],
        )

        print(f"  [REPAIR] {error_type.value} ({self.consecutive_failures} consecutive)")

        # Transition to REPAIR or STALL
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            try:
                self.sm.transition(State.STALL, f"stalled after {self.consecutive_failures} failures")
            except TransitionError:
                pass
        elif self.sm.state != State.REPAIR:
            try:
                self.sm.transition(State.REPAIR, f"failure: {feedback[:80]}")
            except TransitionError:
                pass

    def _do_repair_cycle(self, task_spec: TaskSpec) -> None:
        """Execute one REPAIR → EXECUTE → VERIFY → REVIEW cycle.

        Called when verification or review fails. Gives the task one retry.
        Ends in PLAN (success) or stays in REPAIR (failure).
        """
        print("\n--- REPAIR CYCLE ---")

        # REPAIR → EXECUTE
        self.sm.transition(State.EXECUTE, "repair retry")
        result = self._execute(task_spec)

        # EXECUTE → VERIFY
        verification = self._verify(result)

        if not verification["passed"]:
            # Still failing — record and move to PLAN for next iteration
            self._handle_failure(task_spec, result, verification.get("pytest", {}).get("output", ""))
            # Transition to PLAN so the main loop can continue
            if self.sm.state != State.STALL:
                try:
                    self.sm.transition(State.PLAN, "repair failed, next iteration")
                except TransitionError:
                    pass
            return

        # VERIFY passed → REVIEW
        if self.sm.state == State.REVIEW:
            print("\n--- REPAIR REVIEW ---")
            prompt = build_review_prompt(task_spec, result, verification)
            # Route to judge agent via router
            response = route_to_agent(AgentRole.JUDGE, prompt)

            # Guard: strip any code patches OpenClaw may have leaked
            if not response.startswith("ERROR:"):
                response = _sanitize_openclaw_output(response, role="reviewer")

            save_output(f"review_iter{self.sm.iteration}_repair.txt", response)

            if response.startswith("ERROR:"):
                # Review failed but tests passed — accept it
                self.sm.transition(State.PLAN, "repair review error, tests pass")
                self._handle_success(task_spec)
                return

            decision = ReviewDecision.from_reviewer_output(response)
            print(f"  Repair decision: {decision.decision}")

            if decision.decision == "PASS":
                self.sm.transition(State.PLAN, "repair review passed")
                self._handle_success(task_spec)
            else:
                # Still failing after repair — move on
                self._handle_failure(task_spec, result, decision.reason)
                if self.sm.state != State.STALL:
                    try:
                        self.sm.transition(State.PLAN, "repair review failed, next iteration")
                    except TransitionError:
                        pass

    def _is_goal_complete(self) -> bool:
        """Check if enough tasks completed to consider goal done."""
        if len(self.completed_tasks) >= 3 and self.consecutive_failures == 0:
            return True
        if len(self.completed_tasks) >= 1 and len(self.failed_tasks) == 0:
            # At least 1 task done with no failures — ask supervisor
            return False  # conservative: keep going
        return False

    def _print_summary(self) -> None:
        """Print final summary with memory stats."""
        print("\n" + "=" * 60)
        print(f"Final state: {self.sm.state.value}")
        print(f"Completed: {len(self.completed_tasks)} tasks")
        print(f"Failed: {len(self.failed_tasks)} tasks")
        print(f"Iterations: {self.sm.iteration}/{self.sm._max_iterations}")

        if self.completed_tasks:
            print("\nCompleted tasks:")
            for t in self.completed_tasks:
                print(f"  + {t}")
        if self.failed_tasks:
            print("\nFailed tasks:")
            for t in self.failed_tasks:
                print(f"  - {t}")

        stats = self.memory.get_stats()
        print(f"\nMemory: {stats['total_tasks']} tasks stored, "
              f"{stats['success_rate']:.0%} success rate")
        if stats["common_errors"]:
            print(f"Common errors: {stats['common_errors']}")

        print("=" * 60)


# ─── CLI ─────────────────────────────────────────────────────


def _resolve_goal(args) -> tuple[str, dict] | None:
    """Resolve goal from inbox, CLI arg, or state file.

    Returns (goal, task_metadata) or None if no goal found.
    Task metadata includes success_criteria, constraints, allowed_files.
    """
    # Priority 1: inbox
    task = inbox.read_task()
    if task:
        goal = task["goal"]
        print(f"[inbox] Task loaded: {goal[:80]}")
        meta = {
            "success_criteria": task.get("success_criteria", []),
            "constraints": task.get("constraints", []),
            "allowed_files": task.get("allowed_files", []),
        }
        return goal, meta

    # Priority 2: CLI --goal
    if args.goal:
        return args.goal, {}

    # Priority 3: state file
    sm = StateMachine(STATE_FILE)
    if sm.load():
        goal = sm.get_data("goal", "")
        if goal:
            return goal, {}

    return None


def _run_once(args) -> str:
    """Run one orchestrator cycle. Returns outcome: 'completed' | 'failed' | 'stalled'."""
    resolved = _resolve_goal(args)
    if resolved is None:
        print("ERROR: No goal found. Use --goal, set inbox/current_task.json, or set state.json")
        sys.exit(1)

    goal, meta = resolved

    # Save goal to state data
    sm = StateMachine(STATE_FILE)
    sm.set_data("goal", goal)
    sm.set_data("supervisor", args.supervisor)
    sm.set_data("task_meta", meta)
    sm.save()

    orchestrator = Orchestrator(
        goal=goal,
        supervisor=args.supervisor,
        max_iter=args.max_iterations,
    )
    orchestrator.run()

    # Determine outcome
    final_state = orchestrator.sm.state
    if final_state == State.DONE and len(orchestrator.completed_tasks) > 0:
        return "completed"
    elif final_state == State.STALL:
        return "stalled"
    return "failed"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autonomous AI workflow orchestrator for Literature Juicer"
    )
    parser.add_argument(
        "--goal", type=str, default="",
        help="The high-level goal to accomplish",
    )
    parser.add_argument(
        "--supervisor", type=str,
        choices=["openclaw", "gemini"],
        default="openclaw",
        help="Supervisor backend (default: openclaw)",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum iterations (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Reset state and exit",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Poll inbox for new tasks and execute automatically",
    )

    args = parser.parse_args()

    if args.reset:
        sm = StateMachine(STATE_FILE)
        sm.reset()
        print("State reset.")
        if args.goal:
            print(f"Goal: {args.goal}")
        return

    if args.watch:
        _watch_loop(args)
    else:
        outcome = _run_once(args)
        # Archive task if it came from inbox
        if inbox.has_task():
            archived = inbox.archive_task(outcome)
            if archived:
                print(f"[inbox] Task archived: {archived.name}")


def _watch_loop(args) -> None:
    """Poll inbox for new tasks. Execute each one as it arrives."""
    print("[watch] Polling inbox for tasks... (Ctrl+C to stop)")
    poll_interval = 5  # seconds

    try:
        while True:
            if inbox.has_task():
                task = inbox.read_task()
                print(f"\n[watch] New task: {task['goal'][:80]}")

                outcome = _run_once(args)
                archived = inbox.archive_task(outcome)
                if archived:
                    print(f"[watch] Archived: {archived.name}")

                print(f"[watch] Outcome: {outcome}")
                print("[watch] Waiting for next task...")
            else:
                time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[watch] Stopped.")


if __name__ == "__main__":
    main()
