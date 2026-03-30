from __future__ import annotations

from HELPERS.ingress_models import (
    AudioDownloadRequested,
    AskFilterSelectionRequested,
    AskQualitySelectionRequested,
    CallbackIngressEnvelope,
    ConcatRequested,
    CookieMenuSelectionRequested,
    CookieUploadRequested,
    DocumentIngressEnvelope,
    FormatMenuSelectionRequested,
    ImageRangeSelectionRequested,
    IngressEnvelope,
    RenameRequested,
    SubtitleOnlyRequested,
    SubtitleSettingsSelectionRequested,
    UrlDownloadRequested,
)


def build_subtitle_only_request(
    envelope: IngressEnvelope,
    *,
    url: str,
    tags: list[str],
    text_only: bool,
    playlist_name: str | None,
    video_count: int,
    video_start_with: int,
) -> SubtitleOnlyRequested:
    command_tokens = list((envelope.raw_payload or {}).get("command_tokens") or [])
    subtitle_mode = "text_only" if text_only else "subtitle_file"
    return SubtitleOnlyRequested(
        request_kind="SubtitleOnlyRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": command_tokens,
            "subtitle_mode": subtitle_mode,
        },
        url=url,
        subtitle_mode=subtitle_mode,
        text_only=text_only,
        tags=list(tags),
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
    )


def build_concat_request(
    envelope: IngressEnvelope,
    *,
    url: str,
    media_mode: str,
    reverse_output: bool,
    output_name_override: str | None,
    tags: list[str],
    tags_text: str,
    playlist_name: str | None,
    video_count: int,
    video_start_with: int,
    video_end_with: int,
) -> ConcatRequested:
    command_tokens = list((envelope.raw_payload or {}).get("command_tokens") or [])
    concat_ordering = "reverse" if reverse_output else "original"
    chapter_policy = "none"
    concat_policy = "direct_concat_only"
    return ConcatRequested(
        request_kind="ConcatRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": command_tokens,
            "media_mode": media_mode,
            "concat_ordering": concat_ordering,
            "concat_policy": concat_policy,
            "chapter_policy": chapter_policy,
        },
        url=url,
        media_mode=media_mode,
        reverse_output=reverse_output,
        output_name_override=output_name_override,
        tags=list(tags),
        tags_text=tags_text,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        video_end_with=video_end_with,
        concat_policy=concat_policy,
        chapter_policy=chapter_policy,
        concat_ordering=concat_ordering,
    )


def build_rename_request(
    envelope: IngressEnvelope,
    *,
    target_kind: str,
    new_name: str,
) -> RenameRequested:
    command_tokens = list((envelope.raw_payload or {}).get("command_tokens") or [])
    return RenameRequested(
        request_kind="RenameRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": command_tokens,
            "target_kind": target_kind,
        },
        target_kind=target_kind,
        new_name=new_name,
    )


def build_audio_download_request(
    envelope: IngressEnvelope,
    *,
    url: str,
    quality_key: str,
    format_override: str,
    tags: list[str],
    tags_text: str,
    playlist_name: str | None,
    video_count: int,
    video_start_with: int,
) -> AudioDownloadRequested:
    command_tokens = list((envelope.raw_payload or {}).get("command_tokens") or [])
    return AudioDownloadRequested(
        request_kind="AudioDownloadRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": command_tokens,
            "quality_key": quality_key,
            "format_override": format_override,
        },
        url=url,
        quality_key=quality_key,
        format_override=format_override,
        tags=list(tags),
        tags_text=tags_text,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
    )


def build_url_download_request(
    envelope: IngressEnvelope,
    *,
    url: str,
    tags: list[str],
    tags_text: str,
    playlist_name: str | None,
    video_start_with: int,
    video_end_with: int,
) -> UrlDownloadRequested:
    return UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
        url=url,
        tags=list(tags),
        tags_text=tags_text,
        playlist_name=playlist_name,
        video_start_with=video_start_with,
        video_end_with=video_end_with,
    )


def build_ask_quality_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_token: str,
) -> AskQualitySelectionRequested:
    return AskQualitySelectionRequested(
        request_kind="AskQualitySelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        selection_token=selection_token,
        original_message_id=(envelope.reply_context or {}).get("reply_to_message_id"),
    )


def build_ask_filter_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    filter_kind: str,
    filter_value: str,
) -> AskFilterSelectionRequested:
    return AskFilterSelectionRequested(
        request_kind="AskFilterSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        filter_kind=filter_kind,
        filter_value=filter_value,
        original_message_id=(envelope.reply_context or {}).get("reply_to_message_id"),
    )


def build_image_range_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    start_index: int,
    end_index: int,
    url: str,
) -> ImageRangeSelectionRequested:
    return ImageRangeSelectionRequested(
        request_kind="ImageRangeSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        start_index=start_index,
        end_index=end_index,
        url=url,
    )


def build_cookie_upload_request(
    envelope: DocumentIngressEnvelope,
) -> CookieUploadRequested:
    return CookieUploadRequested(
        request_kind="CookieUploadRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        provenance={
            "event_kind": envelope.event_kind,
        },
        file_name=envelope.document_name or "",
        file_size=int(envelope.document_size or 0),
        mime_type=envelope.mime_type,
    )


def build_cookie_menu_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> CookieMenuSelectionRequested:
    return CookieMenuSelectionRequested(
        request_kind="CookieMenuSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        selection_key=selection_key,
    )


def build_subtitle_settings_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_kind: str,
    action_value: str | None = None,
    page: int | None = None,
) -> SubtitleSettingsSelectionRequested:
    return SubtitleSettingsSelectionRequested(
        request_kind="SubtitleSettingsSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        action_kind=action_kind,
        action_value=action_value,
        page=page,
    )


def build_format_menu_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_kind: str,
    action_value: str | None = None,
) -> FormatMenuSelectionRequested:
    return FormatMenuSelectionRequested(
        request_kind="FormatMenuSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        action_kind=action_kind,
        action_value=action_value,
    )
