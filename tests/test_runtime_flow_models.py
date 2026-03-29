from types import SimpleNamespace

import DOWN_AND_UP.task_terminal_flow as task_terminal_flow
from DOWN_AND_UP.branch_selection_result import (
    audio_download_branch,
    direct_link_branch,
    redirected_audio_branch,
    resolve_direct_link_preference,
    saved_format_branch,
    task_scope_for_count,
    video_download_branch,
)
from DOWN_AND_UP.runtime_task import (
    ensure_runtime_task,
    make_runtime_task,
    with_branch_selection,
    with_terminal_outcome,
)
from DOWN_AND_UP.task_terminal_flow import attach_and_render_terminal_outcome
from DOWN_AND_UP.terminal_outcome_result import (
    failed_terminal_outcome,
    format_audio_failure_status,
    format_audio_terminal_status,
    format_video_failure_status,
    format_video_terminal_status,
    upload_terminal_outcome,
)


def test_branch_selection_helpers_capture_expected_shape():
    direct_branch = direct_link_branch(
        quality_intent="720p",
        quality_key="720p",
        origin="test",
    )
    assert direct_branch.branch_family == "direct_link"
    assert direct_branch.delivery_intent == "response_only"
    assert direct_branch.task_scope == "single_item"

    audio_branch = audio_download_branch(
        quality_intent="mp3",
        quality_key="mp3",
        video_count=3,
        selected_by="explicit_command",
        origin="test",
    )
    assert audio_branch.branch_family == "audio_download"
    assert audio_branch.media_intent == "audio"
    assert audio_branch.task_scope == "playlist_range"

    video_branch = video_download_branch(
        quality_intent="720p",
        quality_key="720p",
        format_override="bestvideo+bestaudio",
        selected_by="explicit_callback",
        origin="test",
    )
    assert video_branch.branch_family == "video_download"
    assert video_branch.media_intent == "video"
    assert video_branch.execution_source == "fresh_acquisition"

    saved_branch = saved_format_branch(
        saved_format="best",
        quality_key="best",
        video_count=1,
        origin="test",
    )
    assert saved_branch.branch_family == "saved_format_download"
    assert saved_branch.selected_by == "saved_user_default"
    assert saved_branch.provenance["saved_format"] is True

    assert task_scope_for_count(1) == "single_item"
    assert task_scope_for_count(2) == "playlist_range"


def test_redirected_audio_branch_preserves_and_augments_provenance():
    original = video_download_branch(
        quality_intent="bestvideo",
        quality_key="bestvideo",
        format_override="bestvideo+bestaudio",
        selected_by="explicit_callback",
        origin="test",
        provenance={"source": "callback"},
    )

    redirected = redirected_audio_branch(
        original,
        quality_key="mp3",
        format_override="ba",
        reason="video_resolved_to_audio_only",
    )

    assert redirected is not None
    assert redirected.branch_family == "audio_download"
    assert redirected.media_intent == "audio"
    assert redirected.quality_key == "mp3"
    assert redirected.format_override == "ba"
    assert redirected.provenance["source"] == "callback"
    assert redirected.provenance["redirected_to"] == "audio_download"
    assert redirected.provenance["redirect_reason"] == "video_resolved_to_audio_only"


def test_resolve_direct_link_preference_prefers_branch_result_over_ambient():
    branch = direct_link_branch(
        quality_intent="best",
        quality_key="best",
        origin="test",
    )

    use_direct_link, source = resolve_direct_link_preference(
        branch,
        user_id=123,
        ambient_link_mode_reader=lambda _user_id: False,
    )
    assert use_direct_link is True
    assert source == "branch_result"

    use_direct_link, source = resolve_direct_link_preference(
        None,
        user_id=123,
        ambient_link_mode_reader=lambda _user_id: True,
    )
    assert use_direct_link is True
    assert source == "ambient_link_mode"


def test_runtime_task_helpers_materialize_and_mutate_task_state():
    task = ensure_runtime_task(
        task=None,
        user_id=42,
        source_message_id=99,
        url="https://example.com/video",
        tags_text="#tag",
        tags=["#tag"],
        playlist_name="Playlist",
        video_count=3,
        video_start_with=2,
        force_no_title=True,
        cached_video_info={"id": "abc"},
        proc_msg_id=77,
    )

    assert task.user_id == 42
    assert task.source_message_id == 99
    assert task.url == "https://example.com/video"
    assert task.tags == ["#tag"]
    assert task.playlist_name == "Playlist"
    assert task.video_count == 3
    assert task.video_start_with == 2
    assert task.force_no_title is True
    assert task.cached_video_info == {"id": "abc"}
    assert task.proc_msg_id == 77

    branch = audio_download_branch(
        quality_intent="mp3",
        quality_key="mp3",
        selected_by="explicit_command",
        origin="test",
    )
    outcome = upload_terminal_outcome(
        media_kind="audio",
        attempted_count=2,
        delivered_count=1,
        cached_count=1,
    )

    assert with_branch_selection(task, branch) is task
    assert task.branch_selection_result == branch
    assert with_terminal_outcome(task, outcome) is task
    assert task.terminal_outcome_result == outcome

    existing = make_runtime_task(
        user_id=1,
        source_message_id=None,
        url="https://example.com",
        tags_text="",
    )
    ensured = ensure_runtime_task(
        task=existing,
        user_id=999,
        source_message_id=999,
        url="https://should-not-win.example.com",
        tags_text="ignored",
    )
    assert ensured is existing
    assert ensured.user_id == 1
    assert ensured.url == "https://example.com"


def test_terminal_outcome_helpers_and_formatters_cover_completed_partial_and_failed():
    messages = SimpleNamespace(
        AUDIO_SUCCESSFULLY_COMPLETED_MSG="audio done {total_files}",
        AUDIO_PARTIALLY_COMPLETED_MSG="audio partial {successful_uploads}/{total_files}",
        CREDITS_MSG="credits",
        DOWN_UP_UPLOAD_COMPLETE_MSG="upload complete",
        DOWN_UP_FILES_UPLOADED_MSG="files uploaded",
        DOWNLOAD_TIMEOUT_MSG="audio timeout",
        AUDIO_DOWNLOAD_FAILED_MSG="audio failed {error}",
        DOWNLOAD_CANCELLED_TIMEOUT_MSG="video timeout",
        FAILED_DOWNLOAD_VIDEO_MSG="video failed {error}",
    )

    completed_audio = upload_terminal_outcome(
        media_kind="audio",
        attempted_count=2,
        delivered_count=2,
    )
    partial_audio = upload_terminal_outcome(
        media_kind="audio",
        attempted_count=3,
        delivered_count=1,
        cached_count=1,
    )
    failed_audio = failed_terminal_outcome(
        media_kind="audio",
        failure_kind="download_failed",
        error_text="boom",
    )
    failed_video_timeout = failed_terminal_outcome(
        media_kind="video",
        failure_kind="timeout",
    )

    assert completed_audio.outcome_kind == "completed"
    assert partial_audio.outcome_kind == "partial"
    assert partial_audio.total_sent_count == 2
    assert format_audio_terminal_status(
        messages,
        completed_audio,
        include_credits=True,
        credits_msg=messages.CREDITS_MSG,
    ) == "audio done 2\ncredits"
    assert format_audio_terminal_status(
        messages,
        partial_audio,
        include_credits=False,
        credits_msg=messages.CREDITS_MSG,
    ) == "audio partial 1/3"
    assert format_video_terminal_status(
        messages,
        upload_terminal_outcome(media_kind="video", attempted_count=2, delivered_count=2),
        include_credits=False,
        credits_msg=None,
    ) == "<b>upload complete</b> - 2 files uploaded."
    assert format_audio_failure_status(messages, failed_audio) == "audio failed boom"
    assert format_video_failure_status(messages, failed_video_timeout) == "video timeout"


def test_attach_and_render_terminal_outcome_updates_task_and_respects_rendered_text(monkeypatch):
    task = make_runtime_task(
        user_id=7,
        source_message_id=11,
        url="https://example.com/audio",
        tags_text="",
    )
    outcome = upload_terminal_outcome(
        media_kind="audio",
        attempted_count=1,
        delivered_count=1,
    )
    fake_messages = SimpleNamespace(AUDIO_SUCCESSFULLY_COMPLETED_MSG="done {total_files}")

    monkeypatch.setattr(task_terminal_flow, "safe_get_messages", lambda _user_id: fake_messages)

    updated_task, rendered = attach_and_render_terminal_outcome(
        user_id=7,
        outcome=outcome,
        task_context=task,
        formatter=lambda messages, rendered_outcome: format_audio_terminal_status(
            messages,
            rendered_outcome,
            include_credits=False,
            credits_msg=None,
        ),
    )
    assert updated_task is task
    assert updated_task.terminal_outcome_result == outcome
    assert rendered == "done 1"

    _, explicit_render = attach_and_render_terminal_outcome(
        user_id=7,
        outcome=outcome,
        task_context=None,
        formatter=lambda _messages, _rendered_outcome: "unused",
        rendered_text="explicit text",
    )
    assert explicit_render == "explicit text"
