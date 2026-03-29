from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalOutcomeResult:
    outcome_kind: str
    media_kind: str
    attempted_count: int
    delivered_count: int
    cached_count: int = 0
    failure_kind: str | None = None
    error_text: str | None = None

    @property
    def total_sent_count(self) -> int:
        return self.cached_count + self.delivered_count


def upload_terminal_outcome(
    *,
    media_kind: str,
    attempted_count: int,
    delivered_count: int,
    cached_count: int = 0,
) -> TerminalOutcomeResult:
    outcome_kind = "completed" if delivered_count == attempted_count else "partial"
    return TerminalOutcomeResult(
        outcome_kind=outcome_kind,
        media_kind=media_kind,
        attempted_count=attempted_count,
        delivered_count=delivered_count,
        cached_count=cached_count,
    )


def failed_terminal_outcome(
    *,
    media_kind: str,
    failure_kind: str,
    error_text: str | None = None,
    attempted_count: int = 0,
    delivered_count: int = 0,
    cached_count: int = 0,
) -> TerminalOutcomeResult:
    return TerminalOutcomeResult(
        outcome_kind="failed",
        media_kind=media_kind,
        attempted_count=attempted_count,
        delivered_count=delivered_count,
        cached_count=cached_count,
        failure_kind=failure_kind,
        error_text=error_text,
    )


def format_audio_terminal_status(messages, outcome: TerminalOutcomeResult, *, include_credits: bool, credits_msg: str | None) -> str:
    if outcome.outcome_kind == "completed":
        status_text = messages.AUDIO_SUCCESSFULLY_COMPLETED_MSG.format(
            total_files=outcome.attempted_count,
        )
    else:
        status_text = messages.AUDIO_PARTIALLY_COMPLETED_MSG.format(
            successful_uploads=outcome.delivered_count,
            total_files=outcome.attempted_count,
        )

    if include_credits and credits_msg:
        status_text += f"\n{credits_msg}"
    return status_text


def format_video_terminal_status(messages, outcome: TerminalOutcomeResult, *, include_credits: bool, credits_msg: str | None) -> str:
    status_text = (
        f"<b>{messages.DOWN_UP_UPLOAD_COMPLETE_MSG}</b> - "
        f"{outcome.delivered_count} {messages.DOWN_UP_FILES_UPLOADED_MSG}."
    )
    if include_credits and credits_msg:
        status_text += f"\n{credits_msg}"
    return status_text


def format_audio_failure_status(messages, outcome: TerminalOutcomeResult) -> str:
    if outcome.failure_kind == "timeout":
        return messages.DOWNLOAD_TIMEOUT_MSG
    return messages.AUDIO_DOWNLOAD_FAILED_MSG.format(error=outcome.error_text or "Unknown error")


def format_video_failure_status(messages, outcome: TerminalOutcomeResult) -> str:
    if outcome.failure_kind == "timeout":
        return messages.DOWNLOAD_CANCELLED_TIMEOUT_MSG
    return messages.FAILED_DOWNLOAD_VIDEO_MSG.format(error=outcome.error_text or "Unknown error")
