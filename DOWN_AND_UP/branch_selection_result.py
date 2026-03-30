from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class BranchSelectionResult:
    branch_family: str
    selected_by: str
    task_scope: str
    delivery_intent: str
    media_intent: str
    quality_intent: str
    execution_source: str
    format_override: str | None = None
    quality_key: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


def task_scope_for_count(video_count: int) -> str:
    return "playlist_range" if video_count > 1 else "single_item"


def direct_link_branch(
    *,
    quality_intent: str,
    quality_key: str | None,
    task_scope: str = "single_item",
    selected_by: str = "explicit_callback",
    origin: str,
    provenance: dict[str, Any] | None = None,
) -> BranchSelectionResult:
    details = {"origin": origin}
    if provenance:
        details.update(provenance)
    return BranchSelectionResult(
        branch_family="direct_link",
        selected_by=selected_by,
        task_scope=task_scope,
        delivery_intent="response_only",
        media_intent="mixed",
        quality_intent=quality_intent,
        execution_source="response_only",
        quality_key=quality_key,
        provenance=details,
    )


def audio_download_branch(
    *,
    quality_intent: str,
    quality_key: str | None,
    video_count: int = 1,
    format_override: str | None = "ba",
    selected_by: str,
    origin: str,
    provenance: dict[str, Any] | None = None,
) -> BranchSelectionResult:
    details = {"origin": origin}
    if provenance:
        details.update(provenance)
    return BranchSelectionResult(
        branch_family="audio_download",
        selected_by=selected_by,
        task_scope=task_scope_for_count(video_count),
        delivery_intent="telegram_media",
        media_intent="audio",
        quality_intent=quality_intent,
        execution_source="fresh_acquisition",
        format_override=format_override,
        quality_key=quality_key,
        provenance=details,
    )


def audio_concat_branch(
    *,
    video_count: int,
    selected_by: str,
    origin: str,
    provenance: dict[str, Any] | None = None,
) -> BranchSelectionResult:
    details = {"origin": origin}
    if provenance:
        details.update(provenance)
    return BranchSelectionResult(
        branch_family="audio_concat_download",
        selected_by=selected_by,
        task_scope=task_scope_for_count(video_count),
        delivery_intent="telegram_media",
        media_intent="audio",
        quality_intent="audio_concat",
        execution_source="fresh_acquisition",
        format_override="bestaudio_concat",
        quality_key="audio_concat",
        provenance=details,
    )


def video_download_branch(
    *,
    quality_intent: str,
    quality_key: str | None,
    format_override: str | None,
    video_count: int = 1,
    selected_by: str,
    origin: str,
    provenance: dict[str, Any] | None = None,
    branch_family: str = "video_download",
) -> BranchSelectionResult:
    details = {"origin": origin}
    if provenance:
        details.update(provenance)
    return BranchSelectionResult(
        branch_family=branch_family,
        selected_by=selected_by,
        task_scope=task_scope_for_count(video_count),
        delivery_intent="telegram_media",
        media_intent="video",
        quality_intent=quality_intent,
        execution_source="fresh_acquisition",
        format_override=format_override,
        quality_key=quality_key,
        provenance=details,
    )


def saved_format_branch(
    *,
    saved_format: str | None,
    quality_key: str | None,
    video_count: int,
    origin: str,
) -> BranchSelectionResult:
    return video_download_branch(
        branch_family="saved_format_download",
        selected_by="saved_user_default",
        video_count=video_count,
        format_override=saved_format,
        quality_key=quality_key,
        quality_intent=quality_key or "saved_default",
        origin=origin,
        provenance={"saved_format": bool(saved_format)},
    )


def log_branch_selection(logger, branch_result: BranchSelectionResult, *, user_id: int | None = None) -> None:
    logger.info(
        "BranchSelectionResult: "
        f"user_id={user_id} "
        f"branch_family={branch_result.branch_family} "
        f"selected_by={branch_result.selected_by} "
        f"task_scope={branch_result.task_scope} "
        f"delivery_intent={branch_result.delivery_intent} "
        f"media_intent={branch_result.media_intent} "
        f"quality_intent={branch_result.quality_intent} "
        f"execution_source={branch_result.execution_source} "
        f"quality_key={branch_result.quality_key!r} "
        f"format_override={branch_result.format_override!r}"
    )


def redirected_audio_branch(
    branch_result: BranchSelectionResult | None,
    *,
    quality_key: str | None,
    format_override: str | None,
    reason: str,
) -> BranchSelectionResult | None:
    if branch_result is None:
        return None

    provenance = dict(branch_result.provenance)
    provenance["redirected_to"] = "audio_download"
    provenance["redirect_reason"] = reason

    return replace(
        branch_result,
        branch_family="audio_download",
        media_intent="audio",
        quality_intent=quality_key or branch_result.quality_intent,
        format_override=format_override,
        quality_key=quality_key,
        provenance=provenance,
    )


def gallery_fallback_branch(
    branch_result: BranchSelectionResult | None,
    *,
    origin: str,
    reason: str,
) -> BranchSelectionResult:
    if branch_result is None:
        return BranchSelectionResult(
            branch_family="gallery_fallback_download",
            selected_by="fallback_policy",
            task_scope="single_item",
            delivery_intent="telegram_media",
            media_intent="mixed",
            quality_intent="fallback_gallery_dl",
            execution_source="gallery_dl_fallback",
            provenance={"origin": origin, "fallback_reason": reason},
        )

    provenance = dict(branch_result.provenance)
    provenance["fallback_from_branch_family"] = branch_result.branch_family
    provenance["fallback_reason"] = reason
    provenance["fallback_origin"] = origin

    return replace(
        branch_result,
        branch_family="gallery_fallback_download",
        delivery_intent="telegram_media",
        execution_source="gallery_dl_fallback",
        provenance=provenance,
    )


def resolve_direct_link_preference(
    branch_result: BranchSelectionResult | None,
    *,
    user_id: int,
    ambient_link_mode_reader,
) -> tuple[bool, str]:
    if branch_result is not None:
        return branch_result.branch_family == "direct_link", "branch_result"

    return bool(ambient_link_mode_reader(user_id)), "ambient_link_mode"
