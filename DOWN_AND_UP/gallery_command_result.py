from dataclasses import dataclass


@dataclass(frozen=True)
class GalleryCommandResult:
    outcome_kind: str
    attempted_count: int
    delivered_count: int
    error_text: str | None = None


def is_gallery_command_result(result) -> bool:
    return isinstance(result, GalleryCommandResult)


def is_handled_gallery_command_result(result) -> bool:
    return is_gallery_command_result(result) and result.outcome_kind in {
        "completed",
        "partial",
        "failed",
    }


def did_gallery_command_succeed(result) -> bool:
    return is_gallery_command_result(result) and result.outcome_kind in {"completed", "partial"}


def did_gallery_command_fail(result) -> bool:
    return is_gallery_command_result(result) and result.outcome_kind == "failed"
