from dataclasses import dataclass
from typing import Any

from DOWN_AND_UP.branch_selection_result import BranchSelectionResult
from DOWN_AND_UP.terminal_outcome_result import TerminalOutcomeResult


@dataclass
class RuntimeTask:
    user_id: int
    source_message_id: int | None
    url: str
    tags_text: str
    tags: list[str] | None = None
    playlist_name: str | None = None
    video_count: int = 1
    video_start_with: int = 1
    force_no_title: bool = False
    branch_selection_result: BranchSelectionResult | None = None
    terminal_outcome_result: TerminalOutcomeResult | None = None
    playlist_error_summary: dict[str, Any] | None = None
    cached_video_info: dict[str, Any] | None = None
    proc_msg_id: int | None = None


def make_runtime_task(
    *,
    user_id: int,
    source_message_id: int | None,
    url: str,
    tags_text: str,
    tags: list[str] | None = None,
    playlist_name: str | None = None,
    video_count: int = 1,
    video_start_with: int = 1,
    force_no_title: bool = False,
    branch_selection_result: BranchSelectionResult | None = None,
    terminal_outcome_result: TerminalOutcomeResult | None = None,
    playlist_error_summary: dict[str, Any] | None = None,
    cached_video_info: dict[str, Any] | None = None,
    proc_msg_id: int | None = None,
) -> RuntimeTask:
    return RuntimeTask(
        user_id=user_id,
        source_message_id=source_message_id,
        url=url,
        tags_text=tags_text,
        tags=tags,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        force_no_title=force_no_title,
        branch_selection_result=branch_selection_result,
        terminal_outcome_result=terminal_outcome_result,
        playlist_error_summary=playlist_error_summary,
        cached_video_info=cached_video_info,
        proc_msg_id=proc_msg_id,
    )


def with_branch_selection(
    task: RuntimeTask,
    branch_selection_result: BranchSelectionResult,
) -> RuntimeTask:
    task.branch_selection_result = branch_selection_result
    return task


def with_terminal_outcome(
    task: RuntimeTask,
    terminal_outcome_result: TerminalOutcomeResult,
) -> RuntimeTask:
    task.terminal_outcome_result = terminal_outcome_result
    task.playlist_error_summary = terminal_outcome_result.playlist_error_summary
    return task


def ensure_runtime_task(
    *,
    task: RuntimeTask | None,
    user_id: int,
    source_message_id: int | None,
    url: str,
    tags_text: str,
    tags: list[str] | None = None,
    playlist_name: str | None = None,
    video_count: int = 1,
    video_start_with: int = 1,
    force_no_title: bool = False,
    cached_video_info: dict[str, Any] | None = None,
    proc_msg_id: int | None = None,
) -> RuntimeTask:
    if task is not None:
        return task
    return make_runtime_task(
        user_id=user_id,
        source_message_id=source_message_id,
        url=url,
        tags_text=tags_text,
        tags=tags,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        force_no_title=force_no_title,
        cached_video_info=cached_video_info,
        proc_msg_id=proc_msg_id,
    )
