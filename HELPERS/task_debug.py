"""
Task execution observability and debugging utilities.

This module validates whether Task execution evidence actually answers
debugging questions. Per PDA: evidence exists to be examined.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from datetime import datetime

from DOWN_AND_UP.runtime_task import RuntimeTask


@dataclass(frozen=True)
class ExecutionTraceEntry:
    """Normalized view of a single execution step."""
    timestamp: datetime
    category: str
    plan_type: str
    executor: str
    result: str
    duration_ms: int
    key_data: dict[str, Any]


@dataclass(frozen=True)
class ExecutionTrace:
    """Complete execution trace for a task."""
    task_id_components: dict[str, Any]
    entries: list[ExecutionTraceEntry]
    outcome_summary: dict[str, Any]


def _extract_timestamp(evidence: dict[str, Any]) -> datetime:
    """Extract timestamp from evidence, defaulting to epoch."""
    ts = evidence.get("timestamp", 0)
    try:
        return datetime.fromtimestamp(ts)
    except (TypeError, ValueError, OSError):
        return datetime.fromtimestamp(0)


def _normalize_evidence_to_entry(evidence: dict[str, Any]) -> ExecutionTraceEntry:
    """Convert raw evidence dict to normalized entry."""
    result_summary = evidence.get("result_summary", {})
    plan_input = evidence.get("plan_input", {})

    # Extract key data based on category
    key_data: dict[str, Any] = {}
    category = evidence.get("plan_category", "UNKNOWN")

    if category == "TERMINAL":
        key_data["attempted"] = result_summary.get("attempted_count")
        key_data["delivered"] = result_summary.get("delivered_count")
        key_data["outcome_kind"] = result_summary.get("outcome_kind")
    elif category == "RECOVERY":
        key_data["retry_plan_mode"] = plan_input.get("mode")
        key_data["should_retry"] = plan_input.get("should_retry")
    elif category == "ROUTING":
        key_data["route"] = plan_input.get("route")
    elif category == "ACQUISITION":
        key_data["url"] = plan_input.get("url", "")[:100]
    elif category == "DELIVERY":
        key_data["media_kind"] = plan_input.get("media_kind")

    return ExecutionTraceEntry(
        timestamp=_extract_timestamp(evidence),
        category=category,
        plan_type=evidence.get("plan_type", "Unknown"),
        executor=evidence.get("executor_name", "unknown"),
        result=evidence.get("execution_result", "unknown"),
        duration_ms=evidence.get("duration_ms", 0),
        key_data=key_data,
    )


def render_task_execution_trace(
    task: RuntimeTask,
    *,
    include_full_input: bool = False,
    max_entries: int = 100,
) -> str:
    """
    Render a human-readable execution trace from task evidence.

    This validates whether accumulated evidence tells a coherent story.
    """
    lines: list[str] = []

    # Header
    lines.append("=" * 60)
    lines.append(f"Task Execution Trace")
    lines.append(f"  User: {task.user_id}")
    lines.append(f"  URL: {task.url[:80]}..." if len(task.url) > 80 else f"  URL: {task.url}")
    lines.append(f"  Current State: {task.current_state}")
    lines.append(f"  State History: {len(task.state_history)} transitions")
    lines.append("=" * 60)

    # Collect all evidence from all categories
    all_evidence: list[tuple[str, dict[str, Any]]] = []

    for idx, ref in enumerate(task.artifact_refs[:max_entries]):
        all_evidence.append((f"artifact_{idx}", ref))

    for idx, attempt in enumerate(task.acquisition_attempts[:max_entries]):
        all_evidence.append((f"acquisition_{idx}", attempt))

    for idx, attempt in enumerate(task.delivery_attempts[:max_entries]):
        all_evidence.append((f"delivery_{idx}", attempt))

    for idx, error in enumerate(task.error_evidence[:max_entries]):
        all_evidence.append((f"error_{idx}", error))

    # Sort by timestamp
    all_evidence.sort(key=lambda x: x[1].get("timestamp", 0))

    if not all_evidence:
        lines.append("\n[No execution evidence recorded]")
        return "\n".join(lines)

    # Render each entry
    lines.append(f"\nExecution Steps: {len(all_evidence)}\n")
    lines.append("-" * 60)

    for source, evidence in all_evidence:
        entry = _normalize_evidence_to_entry(evidence)

        time_str = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
        lines.append(f"\n[{time_str}] {entry.category:12} | {entry.plan_type}")
        lines.append(f"  Executor: {entry.executor}")
        lines.append(f"  Result: {entry.result}")
        lines.append(f"  Duration: {entry.duration_ms}ms")

        if entry.key_data:
            lines.append(f"  Key Data:")
            for k, v in entry.key_data.items():
                if v is not None:
                    lines.append(f"    {k}: {v}")

        if include_full_input and evidence.get("plan_input"):
            lines.append(f"  Input (sanitized):")
            for k, v in list(evidence["plan_input"].items())[:5]:
                lines.append(f"    {k}: {v}")

        lines.append("-" * 60)

    # Outcome summary
    if task.terminal_outcome_result:
        lines.append("\n" + "=" * 60)
        lines.append("TERMINAL OUTCOME")
        lines.append(f"  Kind: {task.terminal_outcome_result.outcome_kind}")
        lines.append(f"  Media: {task.terminal_outcome_result.media_kind}")
        lines.append(f"  Attempted: {task.terminal_outcome_result.attempted_count}")
        lines.append(f"  Delivered: {task.terminal_outcome_result.delivered_count}")
        lines.append(f"  Cached: {task.terminal_outcome_result.cached_count}")
        if task.terminal_outcome_result.failure_kind:
            lines.append(f"  Failure: {task.terminal_outcome_result.failure_kind}")
        lines.append("=" * 60)

    return "\n".join(lines)


def summarize_plan_outcomes(task: RuntimeTask) -> dict[str, Any]:
    """
    Aggregate execution evidence by category and outcome.

    Useful for quick diagnosis of task execution patterns.
    """
    all_evidence = []
    all_evidence.extend(task.artifact_refs)
    all_evidence.extend(task.acquisition_attempts)
    all_evidence.extend(task.delivery_attempts)
    all_evidence.extend(task.error_evidence)

    by_category: dict[str, dict[str, Any]] = {}
    by_result: dict[str, int] = {}
    total_duration_ms = 0

    for evidence in all_evidence:
        cat = evidence.get("plan_category", "UNKNOWN")
        result = evidence.get("execution_result", "unknown")
        duration = evidence.get("duration_ms", 0)

        by_result[result] = by_result.get(result, 0) + 1
        total_duration_ms += duration

        if cat not in by_category:
            by_category[cat] = {"count": 0, "success": 0, "failure": 0, "partial": 0}

        by_category[cat]["count"] += 1
        if result in ("success", "completed"):
            by_category[cat]["success"] += 1
        elif result == "failure":
            by_category[cat]["failure"] += 1
        elif result == "partial":
            by_category[cat]["partial"] += 1

    return {
        "total_steps": len(all_evidence),
        "by_category": by_category,
        "by_result": by_result,
        "total_duration_ms": total_duration_ms,
        "has_terminal_outcome": task.terminal_outcome_result is not None,
        "terminal_outcome_kind": task.terminal_outcome_result.outcome_kind if task.terminal_outcome_result else None,
    }


def render_summary(task: RuntimeTask) -> str:
    """Render a concise summary of task execution."""
    summary = summarize_plan_outcomes(task)

    lines: list[str] = []
    lines.append(f"Task Summary (User {task.user_id})")
    lines.append(f"  Total Steps: {summary['total_steps']}")
    lines.append(f"  Total Duration: {summary['total_duration_ms']}ms")
    lines.append(f"  Terminal: {summary['terminal_outcome_kind'] or 'N/A'}")

    if summary["by_category"]:
        lines.append("\n  By Category:")
        for cat, stats in summary["by_category"].items():
            lines.append(f"    {cat:15} | {stats['count']:3} | "
                        f"✓{stats['success']} ✗{stats['failure']} ~{stats['partial']}")

    if summary["by_result"]:
        lines.append("\n  By Result:")
        for result, count in summary["by_result"].items():
            lines.append(f"    {result}: {count}")

    return "\n".join(lines)


def compare_tasks(task_a: RuntimeTask, task_b: RuntimeTask) -> dict[str, Any]:
    """
    Compare two task executions.

    Useful for analyzing why similar tasks had different outcomes.
    """
    def extract_key_events(task: RuntimeTask) -> list[tuple[str, str, str]]:
        """Extract (category, plan_type, result) tuples."""
        events = []
        all_evidence = (
            task.artifact_refs +
            task.acquisition_attempts +
            task.delivery_attempts +
            task.error_evidence
        )
        for ev in sorted(all_evidence, key=lambda x: x.get("timestamp", 0)):
            events.append((
                ev.get("plan_category", "?"),
                ev.get("plan_type", "?"),
                ev.get("execution_result", "?"),
            ))
        return events

    events_a = extract_key_events(task_a)
    events_b = extract_key_events(task_b)

    return {
        "task_a_steps": len(events_a),
        "task_b_steps": len(events_b),
        "task_a_terminal": task_a.terminal_outcome_result.outcome_kind if task_a.terminal_outcome_result else None,
        "task_b_terminal": task_b.terminal_outcome_result.outcome_kind if task_b.terminal_outcome_result else None,
        "execution_divergence": _find_divergence(events_a, events_b),
    }


def _find_divergence(events_a: list, events_b: list) -> dict[str, Any] | None:
    """Find first point where two event sequences differ."""
    min_len = min(len(events_a), len(events_b))

    for i in range(min_len):
        if events_a[i] != events_b[i]:
            return {
                "step": i,
                "task_a": events_a[i],
                "task_b": events_b[i],
            }

    if len(events_a) != len(events_b):
        return {
            "step": min_len,
            "reason": "length_mismatch",
            "task_a_length": len(events_a),
            "task_b_length": len(events_b),
        }

    return None


# CLI helper for debugging
def dump_task_to_console(task: RuntimeTask, *, verbose: bool = False) -> None:
    """Print task execution trace to console."""
    print(render_task_execution_trace(task, include_full_input=verbose))
    print("\n")
    print(render_summary(task))
