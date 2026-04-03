from dataclasses import dataclass, field, replace
from typing import Any

from DOWN_AND_UP.branch_selection_result import BranchSelectionResult
from DOWN_AND_UP.terminal_outcome_result import TerminalOutcomeResult


@dataclass(frozen=True)
class RuntimeTask:
    """
    Primary runtime representation of a bounded execution attempt to resolve
    a user-originated intent into a terminal outcome.

    This is the explicit Task object that carries task identity, state,
    branch commitment, execution evidence, and terminal meaning across
    the machine. Per doc 12 (Task Object Model).
    """

    # Identity fields
    user_id: int
    source_message_id: int | None
    url: str
    tags_text: str

    # Intent fields
    tags: list[str] | None = None
    playlist_name: str | None = None
    video_count: int = 1
    video_start_with: int = 1
    force_no_title: bool = False

    # Machine state fields
    current_state: str = "initialized"
    state_history: list[dict[str, Any]] = field(default_factory=list)

    # Context state fields
    cached_video_info: dict[str, Any] | None = None
    concat_policy: str | None = None
    concat_ordering: str | None = None
    chapter_policy: str | None = None
    output_name_override: str | None = None
    video_concat_manifest: dict[str, Any] | None = None
    video_concat_compatibility: dict[str, Any] | None = None
    video_concat_execution: dict[str, Any] | None = None

    # Branch selection (constitutive - doc 12)
    branch_selection_result: BranchSelectionResult | None = None

    # Terminal outcome (constitutive - doc 12)
    terminal_outcome_result: TerminalOutcomeResult | None = None

    # Execution evidence (attached - doc 12)
    acquisition_attempts: list[dict[str, Any]] = field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    delivery_attempts: list[dict[str, Any]] = field(default_factory=list)
    cache_refs: list[dict[str, Any]] = field(default_factory=list)
    error_evidence: list[dict[str, Any]] = field(default_factory=list)

    # Legacy/UI fields (attached)
    proc_msg_id: int | None = None
    playlist_error_summary: dict[str, Any] | None = None
    gallery_command_result: Any | None = None

    def with_state(self, new_state: str, provenance: dict[str, Any] | None = None) -> "RuntimeTask":
        """Return new task with updated machine state and history."""
        new_history = list(self.state_history)
        entry = {"state": new_state}
        if provenance:
            entry.update(provenance)
        new_history.append(entry)
        return replace(
            self,
            current_state=new_state,
            state_history=new_history,
        )

    def with_branch_selection(
        self,
        branch_selection_result: BranchSelectionResult,
    ) -> "RuntimeTask":
        """Return new task with branch selection result attached."""
        return replace(
            self,
            branch_selection_result=branch_selection_result,
        )

    def with_terminal_outcome(
        self,
        terminal_outcome_result: TerminalOutcomeResult,
    ) -> "RuntimeTask":
        """Return new task with terminal outcome result attached."""
        return replace(
            self,
            terminal_outcome_result=terminal_outcome_result,
            playlist_error_summary=terminal_outcome_result.playlist_error_summary,
        )

    def with_proc_msg_id(self, proc_msg_id: int | None) -> "RuntimeTask":
        return replace(self, proc_msg_id=proc_msg_id)

    def with_url(self, url: str) -> "RuntimeTask":
        return replace(self, url=url)

    def with_cached_video_info(self, cached_video_info: dict[str, Any] | None) -> "RuntimeTask":
        return replace(self, cached_video_info=cached_video_info)

    def with_force_no_title(self, force_no_title: bool) -> "RuntimeTask":
        return replace(self, force_no_title=force_no_title)

    def with_concat_request(
        self,
        *,
        concat_policy: str | None = None,
        concat_ordering: str | None = None,
        chapter_policy: str | None = None,
        output_name_override: str | None = None,
    ) -> "RuntimeTask":
        return replace(
            self,
            concat_policy=concat_policy,
            concat_ordering=concat_ordering,
            chapter_policy=chapter_policy,
            output_name_override=output_name_override,
        )

    def with_video_concat_manifest(self, manifest: dict[str, Any] | None) -> "RuntimeTask":
        return replace(self, video_concat_manifest=manifest)

    def with_video_concat_compatibility(self, compatibility: dict[str, Any] | None) -> "RuntimeTask":
        return replace(self, video_concat_compatibility=compatibility)

    def with_video_concat_execution(self, execution: dict[str, Any] | None) -> "RuntimeTask":
        return replace(self, video_concat_execution=execution)

    def with_gallery_command_result(self, gallery_command_result: Any) -> "RuntimeTask":
        return replace(self, gallery_command_result=gallery_command_result)

    def with_acquisition_attempt(self, attempt: dict[str, Any]) -> "RuntimeTask":
        """Return new task with acquisition attempt recorded."""
        new_attempts = list(self.acquisition_attempts)
        new_attempts.append(attempt)
        return replace(self, acquisition_attempts=new_attempts)

    def with_delivery_attempt(self, attempt: dict[str, Any]) -> "RuntimeTask":
        """Return new task with delivery attempt recorded."""
        new_attempts = list(self.delivery_attempts)
        new_attempts.append(attempt)
        return replace(self, delivery_attempts=new_attempts)

    def with_artifact_ref(self, ref: dict[str, Any]) -> "RuntimeTask":
        """Return new task with artifact reference recorded."""
        new_refs = list(self.artifact_refs)
        new_refs.append(ref)
        return replace(self, artifact_refs=new_refs)

    def with_error_evidence(self, error: dict[str, Any]) -> "RuntimeTask":
        """Return new task with error evidence recorded."""
        new_errors = list(self.error_evidence)
        new_errors.append(error)
        return replace(self, error_evidence=new_errors)


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
    concat_policy: str | None = None,
    concat_ordering: str | None = None,
    chapter_policy: str | None = None,
    output_name_override: str | None = None,
    video_concat_manifest: dict[str, Any] | None = None,
    video_concat_compatibility: dict[str, Any] | None = None,
    video_concat_execution: dict[str, Any] | None = None,
) -> RuntimeTask:
    """Create a new RuntimeTask with initial state."""
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
        concat_policy=concat_policy,
        concat_ordering=concat_ordering,
        chapter_policy=chapter_policy,
        output_name_override=output_name_override,
        video_concat_manifest=video_concat_manifest,
        video_concat_compatibility=video_concat_compatibility,
        video_concat_execution=video_concat_execution,
    )


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
    concat_policy: str | None = None,
    concat_ordering: str | None = None,
    chapter_policy: str | None = None,
    output_name_override: str | None = None,
) -> RuntimeTask:
    """Return existing task or create new one if None."""
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
        concat_policy=concat_policy,
        concat_ordering=concat_ordering,
        chapter_policy=chapter_policy,
        output_name_override=output_name_override,
    )


# Backward compatibility: module-level functions that delegate to instance methods
def with_branch_selection(
    task: RuntimeTask,
    branch_selection_result: BranchSelectionResult,
) -> RuntimeTask:
    """Attach branch selection result to task (returns new immutable task)."""
    return task.with_branch_selection(branch_selection_result)


def with_terminal_outcome(
    task: RuntimeTask,
    terminal_outcome_result: TerminalOutcomeResult,
) -> RuntimeTask:
    """Attach terminal outcome result to task (returns new immutable task)."""
    return task.with_terminal_outcome(terminal_outcome_result)
