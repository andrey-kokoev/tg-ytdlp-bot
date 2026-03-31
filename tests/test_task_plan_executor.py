"""
Tests for TaskPlanExecutor.

Verifies PDA principles:
- Plans execute and produce evidence
- Evidence attaches immutably to Task
- Categories route evidence correctly
- Error handling records evidence
"""

import pytest
from dataclasses import dataclass
from types import SimpleNamespace

from DOWN_AND_UP.task_plan_executor import (
    PlanCategory,
    PlanExecutionEvidence,
    execute_plan,
    execute_terminal_plan,
    execute_routing_plan,
    execute_recovery_plan,
    execute_with_error_evidence,
    _sanitize_plan_input,
    _summarize_result,
)
from DOWN_AND_UP.runtime_task import make_runtime_task, RuntimeTask


@dataclass(frozen=True)
class FakeTerminalPlan:
    media_kind: str
    attempted_count: int


@dataclass(frozen=True)
class FakeRoutingPlan:
    route: str
    priority: int


@dataclass(frozen=True)
class FakeOutcomeResult:
    outcome_kind: str
    attempted_count: int
    delivered_count: int


def test_execute_plan_records_evidence_and_returns_result():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeTerminalPlan(media_kind="video", attempted_count=3)

    def executor(p: FakeTerminalPlan) -> str:
        return f"executed_{p.media_kind}"

    new_task, result = execute_plan(
        task, plan, executor,
        category=PlanCategory.TERMINAL,
        executor_name="test_executor",
    )

    # Immutability
    assert new_task is not task
    # Result returned
    assert result == "executed_video"
    # Evidence attached (goes to artifact_refs for TERMINAL)
    assert len(new_task.artifact_refs) == 1
    evidence = new_task.artifact_refs[0]
    assert evidence["plan_category"] == "TERMINAL"
    assert evidence["plan_type"] == "FakeTerminalPlan"
    assert evidence["plan_input"]["media_kind"] == "video"
    assert evidence["executor_name"] == "test_executor"
    assert evidence["execution_result"] == "success"


def test_execute_plan_routes_acquisition_to_acquisition_attempts():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeRoutingPlan(route="direct", priority=1)

    def executor(p: FakeRoutingPlan) -> bool:
        return True

    new_task, result = execute_plan(
        task, plan, executor,
        category=PlanCategory.ACQUISITION,
    )

    # ACQUISITION routes to acquisition_attempts
    assert len(new_task.acquisition_attempts) == 1
    assert new_task.acquisition_attempts[0]["plan_category"] == "ACQUISITION"


def test_execute_plan_routes_delivery_to_delivery_attempts():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeRoutingPlan(route="upload", priority=1)

    def executor(p: FakeRoutingPlan) -> str:
        return "sent"

    new_task, result = execute_plan(
        task, plan, executor,
        category=PlanCategory.DELIVERY,
    )

    # DELIVERY routes to delivery_attempts
    assert len(new_task.delivery_attempts) == 1
    assert new_task.delivery_attempts[0]["plan_category"] == "DELIVERY"


def test_execute_plan_routes_recovery_to_error_evidence():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeRoutingPlan(route="retry", priority=1)

    def executor(p: FakeRoutingPlan) -> str:
        return "recovered"

    new_task, result = execute_plan(
        task, plan, executor,
        category=PlanCategory.RECOVERY,
    )

    # RECOVERY routes to error_evidence
    assert len(new_task.error_evidence) == 1
    assert new_task.error_evidence[0]["plan_category"] == "RECOVERY"


def test_execute_plan_captures_outcome_result_summary():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeTerminalPlan(media_kind="audio", attempted_count=2)

    def executor(p: FakeTerminalPlan) -> FakeOutcomeResult:
        return FakeOutcomeResult(
            outcome_kind="partial",
            attempted_count=2,
            delivered_count=1,
        )

    new_task, result = execute_plan(
        task, plan, executor,
        category=PlanCategory.TERMINAL,
    )

    evidence = new_task.artifact_refs[0]
    assert evidence["execution_result"] == "partial"
    assert evidence["result_summary"]["attempted_count"] == 2
    assert evidence["result_summary"]["delivered_count"] == 1


def test_execute_plan_records_failure_on_exception():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeTerminalPlan(media_kind="video", attempted_count=1)

    def executor(p: FakeTerminalPlan) -> str:
        raise ValueError("network timeout")

    new_task, result = execute_plan(
        task, plan, executor,
        category=PlanCategory.TERMINAL,
    )

    evidence = new_task.artifact_refs[0]
    assert evidence["execution_result"] == "failure"
    assert "ValueError" in evidence["result_summary"]["exception_type"]
    assert "network timeout" in evidence["result_summary"]["exception_msg"]


def test_execute_with_error_evidence_success_case():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    def operation() -> str:
        return "success_result"

    new_task, result, success = execute_with_error_evidence(
        task, operation, error_context={"phase": "test"}
    )

    assert success is True
    assert result == "success_result"
    # No error evidence on success
    assert len(new_task.error_evidence) == 0


def test_execute_with_error_evidence_failure_case():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    def operation() -> str:
        raise RuntimeError("system failure")

    new_task, result, success = execute_with_error_evidence(
        task, operation, error_context={"phase": "test"}
    )

    assert success is False
    assert result is None
    # Error evidence recorded
    assert len(new_task.error_evidence) == 1
    assert new_task.error_evidence[0]["error_type"] == "RuntimeError"


def test_sanitize_plan_input_handles_primitives():
    plan = FakeTerminalPlan(media_kind="video", attempted_count=3)
    result = _sanitize_plan_input(plan)
    assert result["media_kind"] == "video"
    assert result["attempted_count"] == 3


def test_sanitize_plan_input_handles_nested_objects():
    @dataclass(frozen=True)
    class ComplexPlan:
        name: str
        nested: dict[str, Any]
        items: list[int]

    plan = ComplexPlan(
        name="test",
        nested={"key": "value", "obj": SimpleNamespace()},
        items=[1, 2, 3],
    )
    result = _sanitize_plan_input(plan)
    assert result["name"] == "test"
    assert "key" in result["nested"]
    # Complex object converted to string representation
    assert "namespace" in result["nested"]["obj"]


def test_summarize_result_handles_outcome_kind():
    result = FakeOutcomeResult(
        outcome_kind="completed",
        attempted_count=5,
        delivered_count=5,
    )
    status, summary = _summarize_result(result)
    assert status == "completed"
    assert summary["attempted_count"] == 5
    assert summary["delivered_count"] == 5


def test_summarize_result_handles_bool():
    status, summary = _summarize_result(True)
    assert status == "success"
    assert summary["bool_result"] is True

    status, summary = _summarize_result(False)
    assert status == "failure"
    assert summary["bool_result"] is False


def test_summarize_result_handles_none():
    status, summary = _summarize_result(None)
    assert status == "success"
    assert "none_result" in summary.get("_note", "")


def test_convenience_executors_use_correct_categories():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeTerminalPlan(media_kind="video", attempted_count=1)

    # Test execute_terminal_plan
    new_task, _ = execute_terminal_plan(task, plan, lambda p: None)
    assert new_task.artifact_refs[0]["plan_category"] == "TERMINAL"

    # Test execute_routing_plan
    new_task, _ = execute_routing_plan(task, plan, lambda p: None)
    # ROUTING goes to artifact_refs
    assert any(e["plan_category"] == "ROUTING" for e in new_task.artifact_refs)


def test_chained_executions_accumulate_evidence():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    # First execution
    task, _ = execute_routing_plan(
        task, FakeRoutingPlan(route="A", priority=1), lambda p: None
    )
    # Second execution
    task, _ = execute_terminal_plan(
        task, FakeTerminalPlan(media_kind="video", attempted_count=2), lambda p: None
    )

    # Evidence accumulated
    assert len(task.artifact_refs) == 2
    categories = {e["plan_category"] for e in task.artifact_refs}
    assert categories == {"ROUTING", "TERMINAL"}


def test_plan_execution_includes_timing():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )
    plan = FakeTerminalPlan(media_kind="video", attempted_count=1)

    def executor(p: FakeTerminalPlan) -> str:
        return "done"

    new_task, _ = execute_plan(task, plan, executor, category=PlanCategory.TERMINAL)

    evidence = new_task.artifact_refs[0]
    assert "timestamp" in evidence
    assert "duration_ms" in evidence
    assert isinstance(evidence["duration_ms"], int)
    assert evidence["duration_ms"] >= 0


# Import for type annotations
from typing import Any
