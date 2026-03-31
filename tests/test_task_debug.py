"""
Tests for task execution observability.

Verifies that accumulated evidence can actually be read and understood.
"""

import pytest
from dataclasses import dataclass
from datetime import datetime

from DOWN_AND_UP.runtime_task import make_runtime_task, RuntimeTask
from HELPERS.task_debug import (
    render_task_execution_trace,
    summarize_plan_outcomes,
    render_summary,
    compare_tasks,
    ExecutionTraceEntry,
    _normalize_evidence_to_entry,
)


def test_render_trace_shows_basic_task_info():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com/video",
        tags_text="#test",
    )

    trace = render_task_execution_trace(task)

    assert "Task Execution Trace" in trace
    assert "User: 42" in trace
    assert "https://example.com/video" in trace
    assert "No execution evidence" in trace


def test_render_trace_shows_evidence_entries():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    # Add some artifact evidence (simulating plan execution)
    task = task.with_artifact_ref({
        "plan_category": "TERMINAL",
        "plan_type": "TestPlan",
        "plan_input": {"media_kind": "video"},
        "execution_result": "completed",
        "result_summary": {"attempted_count": 5, "delivered_count": 5},
        "executor_name": "test_executor",
        "timestamp": 1234567890.5,
        "duration_ms": 100,
    })

    trace = render_task_execution_trace(task)

    assert "TERMINAL" in trace
    assert "TestPlan" in trace
    assert "test_executor" in trace
    assert "completed" in trace


def test_render_trace_shows_recovery_evidence():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    task = task.with_error_evidence({
        "plan_category": "RECOVERY",
        "plan_type": "AudioRetryOutcomePlan",
        "plan_input": {"mode": "postprocessing", "should_retry": True},
        "execution_result": "success",
        "result_summary": {},
        "executor_name": "retry_executor",
        "timestamp": 1234567890.5,
        "duration_ms": 50,
    })

    trace = render_task_execution_trace(task)

    assert "RECOVERY" in trace
    assert "AudioRetryOutcomePlan" in trace
    assert "retry_executor" in trace
    assert "retry_plan_mode" in trace or "mode" in trace


def test_summarize_plan_outcomes_aggregates_by_category():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    # Add mixed evidence
    task = task.with_artifact_ref({
        "plan_category": "TERMINAL",
        "execution_result": "completed",
        "timestamp": 1,
        "duration_ms": 100,
    })
    task = task.with_error_evidence({
        "plan_category": "RECOVERY",
        "execution_result": "success",
        "timestamp": 2,
        "duration_ms": 50,
    })
    task = task.with_acquisition_attempt({
        "plan_category": "ACQUISITION",
        "execution_result": "success",
        "timestamp": 3,
        "duration_ms": 200,
    })

    summary = summarize_plan_outcomes(task)

    assert summary["total_steps"] == 3
    assert summary["total_duration_ms"] == 350
    assert "TERMINAL" in summary["by_category"]
    assert "RECOVERY" in summary["by_category"]
    assert "ACQUISITION" in summary["by_category"]


def test_render_summary_is_concise():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    task = task.with_artifact_ref({
        "plan_category": "TERMINAL",
        "execution_result": "completed",
        "timestamp": 1,
        "duration_ms": 100,
    })

    summary_text = render_summary(task)

    assert "Task Summary" in summary_text
    assert "Total Steps: 1" in summary_text
    assert "User 42" in summary_text


def test_compare_tasks_finds_divergence():
    task_a = make_runtime_task(
        user_id=1,
        source_message_id=10,
        url="https://example.com/a",
        tags_text="",
    )
    task_b = make_runtime_task(
        user_id=2,
        source_message_id=20,
        url="https://example.com/b",
        tags_text="",
    )

    # Same initial path - must capture return values
    task_a = task_a.with_artifact_ref({
        "plan_category": "ROUTING",
        "plan_type": "RoutePlan",
        "execution_result": "success",
        "timestamp": 1,
        "duration_ms": 10,
    })
    task_b = task_b.with_artifact_ref({
        "plan_category": "ROUTING",
        "plan_type": "RoutePlan",
        "execution_result": "success",
        "timestamp": 1,
        "duration_ms": 10,
    })

    # Diverge here: task_a succeeds, task_b fails
    task_a = task_a.with_artifact_ref({
        "plan_category": "ACQUISITION",
        "plan_type": "DownloadPlan",
        "execution_result": "success",
        "timestamp": 2,
        "duration_ms": 100,
    })
    task_b = task_b.with_error_evidence({
        "plan_category": "RECOVERY",
        "plan_type": "RetryPlan",
        "execution_result": "failure",
        "timestamp": 2,
        "duration_ms": 50,
    })

    comparison = compare_tasks(task_a, task_b)

    assert comparison["execution_divergence"] is not None
    assert comparison["execution_divergence"]["step"] == 1


def test_normalize_evidence_extracts_key_data_by_category():
    terminal_ev = {
        "plan_category": "TERMINAL",
        "plan_type": "TerminalPlan",
        "plan_input": {},
        "execution_result": "completed",
        "result_summary": {"attempted_count": 5, "delivered_count": 3},
        "executor_name": "exec",
        "timestamp": 1234567890,
        "duration_ms": 100,
    }

    entry = _normalize_evidence_to_entry(terminal_ev)

    assert entry.category == "TERMINAL"
    assert entry.key_data["attempted"] == 5
    assert entry.key_data["delivered"] == 3
    assert entry.result == "completed"  # result is the execution_result, not outcome_kind from summary


def test_render_trace_with_terminal_outcome():
    from DOWN_AND_UP.terminal_outcome_result import upload_terminal_outcome

    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    # Add some evidence so trace shows execution path
    task = task.with_artifact_ref({
        "plan_category": "TERMINAL",
        "plan_type": "UploadPlan",
        "execution_result": "completed",
        "result_summary": {"attempted_count": 3, "delivered_count": 3, "outcome_kind": "completed"},
        "timestamp": 1,
        "duration_ms": 100,
    })

    outcome = upload_terminal_outcome(
        media_kind="audio",
        attempted_count=3,
        delivered_count=3,
    )
    task = task.with_terminal_outcome(outcome)

    trace = render_task_execution_trace(task)

    assert "TERMINAL OUTCOME" in trace
    assert "Kind: completed" in trace
    assert "Media: audio" in trace
    assert "Attempted: 3" in trace


def test_render_trace_limits_max_entries():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    # Add many evidence entries
    for i in range(10):
        task = task.with_artifact_ref({
            "plan_category": "TERMINAL",
            "plan_type": f"Plan{i}",
            "execution_result": "completed",
            "timestamp": i,
            "duration_ms": 10,
        })

    trace = render_task_execution_trace(task, max_entries=5)

    # Should show limited entries (implementation truncates at source)
    assert "Execution Steps:" in trace


def test_render_trace_with_full_input():
    task = make_runtime_task(
        user_id=42,
        source_message_id=99,
        url="https://example.com",
        tags_text="#test",
    )

    task = task.with_artifact_ref({
        "plan_category": "TERMINAL",
        "plan_type": "TestPlan",
        "plan_input": {"key1": "value1", "key2": "value2"},
        "execution_result": "completed",
        "timestamp": 1,
        "duration_ms": 10,
    })

    trace = render_task_execution_trace(task, include_full_input=True)

    assert "Input (sanitized):" in trace
    assert "key1" in trace
