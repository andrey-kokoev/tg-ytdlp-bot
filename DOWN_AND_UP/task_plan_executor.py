"""
TaskPlanExecutor: systematic plan execution with evidence recording.

This module provides the glue between Plan dataclasses and Task execution evidence.
Per PDA doc 12 (Task Object Model), Plans are "attached execution evidence" that
should be recorded on the Task, not just transient control-flow artifacts.

Forced structure:
- Plans are dataclasses with a specific purpose (terminal, routing, recovery, completion)
- Execution produces results
- Evidence is recorded immutably on the Task

Contingent policy (explicit here):
- What evidence is captured (input, output, timing, executor)
- How plans are categorized
- Whether to preserve full plan state or summary
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Callable, TypeVar, Protocol, cast
from time import time

from DOWN_AND_UP.runtime_task import RuntimeTask


class PlanCategory(Enum):
    """
    The forced structure of plan purposes in this system.

    Not arbitrary: these map to the actual lifecycle stages:
    - ROUTING: deciding which execution path to take
    - TERMINAL: final outcomes (success, failure, partial)
    - RECOVERY: handling failures and retries
    - COMPLETION: cleanup and finalization
    - ACQUISITION: obtaining media/metadata
    - DELIVERY: sending to Telegram
    """
    ROUTING = auto()
    TERMINAL = auto()
    RECOVERY = auto()
    COMPLETION = auto()
    ACQUISITION = auto()
    DELIVERY = auto()


@dataclass(frozen=True)
class PlanExecutionEvidence:
    """
    Record of a single plan execution attached to Task.

    This is the explicit evidence structure that doc 12 calls for.
    Frozen because evidence is immutable once recorded.
    """
    plan_category: PlanCategory
    plan_type: str  # The concrete plan class name
    plan_input: dict[str, Any]  # The plan as dict (sanitized)
    execution_result: str  # "success", "failure", "partial", "skipped"
    result_summary: dict[str, Any]  # Key result fields (not full objects)
    executor_name: str  # Function that executed this
    timestamp: float
    duration_ms: int


# Type variable for plan types
P = TypeVar("P")
R = TypeVar("R")


class PlanExecutor(Protocol[P, R]):
    """Protocol for functions that execute plans and return results."""
    def __call__(self, plan: P, task: RuntimeTask) -> R: ...


def _sanitize_plan_input(plan: Any) -> dict[str, Any]:
    """
    Convert plan to dict, removing non-serializable objects.

    Policy decision: what to preserve from the plan input.
    We keep primitives, lists, dicts; replace complex objects with type names.
    """
    result: dict[str, Any] = {}
    try:
        plan_dict = asdict(plan) if hasattr(plan, "__dataclass_fields__") else {"value": str(plan)}
    except (TypeError, ValueError):
        return {"_error": "could not serialize plan", "_repr": repr(plan)[:200]}

    for key, value in plan_dict.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, (list, tuple)):
            # Truncate long lists, preserve first 10
            result[key] = list(value[:10])
            if len(value) > 10:
                result[f"{key}_truncated"] = len(value) - 10
        elif isinstance(value, dict):
            result[key] = {k: str(v)[:100] for k, v in list(value.items())[:20]}
        else:
            # Replace complex objects with type indicator
            result[key] = f"<{type(value).__name__}>"
    return result


def _summarize_result(result: Any) -> tuple[str, dict[str, Any]]:
    """
    Summarize execution result for evidence recording.

    Policy: extract key status fields without preserving full objects.
    Returns (execution_result, result_summary).
    """
    if result is None:
        return "success", {"_note": "none_result"}

    result_type = type(result).__name__

    # Handle boolean results
    if isinstance(result, bool):
        return ("success" if result else "failure"), {"bool_result": result}

    # Handle dataclasses with outcome_kind
    if hasattr(result, "outcome_kind"):
        outcome = result.outcome_kind
        summary: dict[str, Any] = {
            "outcome_kind": outcome,
            "result_type": result_type,
        }
        # Capture key counts if present
        for attr in ["attempted_count", "delivered_count", "cached_count"]:
            if hasattr(result, attr):
                summary[attr] = getattr(result, attr)
        return outcome, summary

    # Handle dataclasses with result_kind
    if hasattr(result, "result_kind"):
        summary = {
            "result_kind": result.result_kind,
            "result_type": result_type,
        }
        return result.result_kind, summary

    # Handle dataclasses - capture primitive fields
    if hasattr(result, "__dataclass_fields__"):
        try:
            result_dict = asdict(result)
            summary = {}
            for k, v in list(result_dict.items())[:10]:
                if isinstance(v, (str, int, float, bool)) or v is None:
                    summary[k] = v
                elif isinstance(v, (list, tuple)) and len(v) <= 3:
                    summary[k] = list(v)
                else:
                    summary[k] = f"<{type(v).__name__}>"
            return "success", summary
        except (TypeError, ValueError):
            return "success", {"_repr": repr(result)[:200]}

    # Default: string representation
    return "success", {"_repr": str(result)[:200], "_type": result_type}


def execute_plan(
    task: RuntimeTask,
    plan: P,
    executor: Callable[[P], R],
    *,
    category: PlanCategory,
    executor_name: str | None = None,
) -> tuple[RuntimeTask, R]:
    """
    Execute a plan and record execution evidence on the Task.

    This is the core PDA move: making plan execution evidence explicit
    and attached to the Task, not lost in transient control flow.

    Args:
        task: Current RuntimeTask (immutable)
        plan: The plan dataclass to execute
        executor: Function that executes the plan and returns result
        category: PlanCategory for classification
        executor_name: Name of executor function (for provenance)

    Returns:
        Tuple of (new_task_with_evidence, execution_result)
    """
    start_time = time()
    plan_type = type(plan).__name__
    executor_name = executor_name or executor.__name__

    # Execute the plan
    try:
        result = executor(plan)
        execution_result, result_summary = _summarize_result(result)
    except Exception as e:
        result = None  # type: ignore
        execution_result = "failure"
        result_summary = {
            "exception_type": type(e).__name__,
            "exception_msg": str(e)[:200],
        }

    duration_ms = int((time() - start_time) * 1000)

    # Build evidence record
    evidence = PlanExecutionEvidence(
        plan_category=category,
        plan_type=plan_type,
        plan_input=_sanitize_plan_input(plan),
        execution_result=execution_result,
        result_summary=result_summary,
        executor_name=executor_name,
        timestamp=start_time,
        duration_ms=duration_ms,
    )

    # Attach evidence to task (immutably)
    new_task = _attach_evidence(task, evidence)

    return new_task, cast(R, result)


def execute_with_error_evidence(
    task: RuntimeTask,
    operation: Callable[[], R],
    *,
    error_context: dict[str, Any] | None = None,
) -> tuple[RuntimeTask, R | None, bool]:
    """
    Execute an operation, recording error evidence if it fails.

    Returns: (new_task, result_or_none, success_bool)
    """
    try:
        result = operation()
        return task, result, True
    except Exception as e:
        error_evidence = {
            "error_type": type(e).__name__,
            "error_message": str(e)[:500],
            "context": error_context or {},
            "timestamp": time(),
        }
        new_task = task.with_error_evidence(error_evidence)
        return new_task, None, False


def _attach_evidence(task: RuntimeTask, evidence: PlanExecutionEvidence) -> RuntimeTask:
    """
    Attach plan execution evidence to task based on category.

    Policy: route evidence to appropriate task field based on category.
    This keeps the evidence organized and queryable.
    """
    evidence_dict = {
        "plan_category": evidence.plan_category.name,
        "plan_type": evidence.plan_type,
        "plan_input": evidence.plan_input,
        "execution_result": evidence.execution_result,
        "result_summary": evidence.result_summary,
        "executor_name": evidence.executor_name,
        "timestamp": evidence.timestamp,
        "duration_ms": evidence.duration_ms,
    }

    # Route to category-specific list for structured access
    if evidence.plan_category == PlanCategory.ACQUISITION:
        return task.with_acquisition_attempt(evidence_dict)
    elif evidence.plan_category == PlanCategory.DELIVERY:
        return task.with_delivery_attempt(evidence_dict)
    elif evidence.plan_category == PlanCategory.RECOVERY:
        # Recovery attempts go to error evidence (they handle failures)
        return task.with_error_evidence(evidence_dict)
    else:
        # ROUTING, TERMINAL, COMPLETION go to artifact refs
        return task.with_artifact_ref(evidence_dict)


# Convenience executors for common patterns

def execute_terminal_plan(
    task: RuntimeTask,
    plan: P,
    executor: Callable[[P], R],
    executor_name: str | None = None,
) -> tuple[RuntimeTask, R]:
    """Execute a terminal outcome plan and record evidence."""
    return execute_plan(
        task, plan, executor,
        category=PlanCategory.TERMINAL,
        executor_name=executor_name,
    )


def execute_routing_plan(
    task: RuntimeTask,
    plan: P,
    executor: Callable[[P], R],
    executor_name: str | None = None,
) -> tuple[RuntimeTask, R]:
    """Execute a routing plan and record evidence."""
    return execute_plan(
        task, plan, executor,
        category=PlanCategory.ROUTING,
        executor_name=executor_name,
    )


def execute_recovery_plan(
    task: RuntimeTask,
    plan: P,
    executor: Callable[[P], R],
    executor_name: str | None = None,
) -> tuple[RuntimeTask, R]:
    """Execute a recovery plan and record evidence."""
    return execute_plan(
        task, plan, executor,
        category=PlanCategory.RECOVERY,
        executor_name=executor_name,
    )


def execute_completion_plan(
    task: RuntimeTask,
    plan: P,
    executor: Callable[[P], R],
    executor_name: str | None = None,
) -> tuple[RuntimeTask, R]:
    """Execute a completion plan and record evidence."""
    return execute_plan(
        task, plan, executor,
        category=PlanCategory.COMPLETION,
        executor_name=executor_name,
    )
