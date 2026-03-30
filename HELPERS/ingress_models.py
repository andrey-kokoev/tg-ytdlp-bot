from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IngressEnvelope:
    transport: str
    event_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    raw_text: str | None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    reply_context: dict[str, Any] = field(default_factory=dict)
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class CallbackIngressEnvelope:
    transport: str
    event_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    raw_data: str | None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    reply_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentIngressEnvelope:
    transport: str
    event_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    document_name: str | None
    document_size: int | None
    mime_type: str | None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    reply_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubtitleOnlyRequested:
    request_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    url: str
    subtitle_mode: str
    text_only: bool
    tags: list[str]
    playlist_name: str | None = None
    video_count: int = 1
    video_start_with: int = 1


@dataclass(frozen=True)
class ConcatRequested:
    request_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    url: str
    media_mode: str
    reverse_output: bool
    output_name_override: str | None
    tags: list[str]
    tags_text: str
    playlist_name: str | None
    video_count: int
    video_start_with: int
    video_end_with: int
    concat_policy: str
    chapter_policy: str
    concat_ordering: str


@dataclass(frozen=True)
class RenameRequested:
    request_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    target_kind: str
    new_name: str


@dataclass(frozen=True)
class AudioDownloadRequested:
    request_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    url: str
    quality_key: str
    format_override: str
    tags: list[str]
    tags_text: str
    playlist_name: str | None
    video_count: int
    video_start_with: int


@dataclass(frozen=True)
class UrlDownloadRequested:
    request_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    url: str
    tags: list[str]
    tags_text: str
    playlist_name: str | None
    video_start_with: int
    video_end_with: int


@dataclass(frozen=True)
class AskQualitySelectionRequested:
    request_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    selection_token: str
    original_message_id: int | None


@dataclass(frozen=True)
class AskFilterSelectionRequested:
    request_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    filter_kind: str
    filter_value: str
    original_message_id: int | None


@dataclass(frozen=True)
class ImageRangeSelectionRequested:
    request_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    start_index: int
    end_index: int
    url: str


@dataclass(frozen=True)
class CookieUploadRequested:
    request_kind: str
    user_id: int
    chat_id: int
    source_message_id: int | None
    source_transport: str
    provenance: dict[str, Any]
    file_name: str
    file_size: int
    mime_type: str | None


@dataclass(frozen=True)
class CookieMenuSelectionRequested:
    request_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    selection_key: str


@dataclass(frozen=True)
class SubtitleSettingsSelectionRequested:
    request_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    action_kind: str
    action_value: str | None
    page: int | None


@dataclass(frozen=True)
class FormatMenuSelectionRequested:
    request_kind: str
    user_id: int
    chat_id: int | None
    source_message_id: int | None
    source_transport: str
    raw_input: str | None
    provenance: dict[str, Any]
    action_kind: str
    action_value: str | None


def build_telegram_message_envelope(
    message,
    *,
    raw_text: str | None = None,
    event_kind: str | None = None,
) -> IngressEnvelope:
    text = raw_text if raw_text is not None else (getattr(message, "text", None) or getattr(message, "caption", None))
    command_tokens = list(getattr(message, "command", []) or [])
    resolved_event_kind = event_kind or ("command_message" if command_tokens else "text_message")
    return IngressEnvelope(
        transport="telegram",
        event_kind=resolved_event_kind,
        user_id=message.chat.id,
        chat_id=message.chat.id,
        source_message_id=getattr(message, "id", None),
        raw_text=text,
        raw_payload={"command_tokens": command_tokens},
        reply_context={"reply_to_message_id": getattr(getattr(message, "reply_to_message", None), "id", None)},
        attachments=[],
    )


def build_telegram_command_envelope(message, *, raw_text: str | None = None) -> IngressEnvelope:
    return build_telegram_message_envelope(message, raw_text=raw_text, event_kind="command_message")


def build_telegram_callback_envelope(
    callback_query,
    *,
    raw_data: str | None = None,
    event_kind: str = "callback_query",
) -> CallbackIngressEnvelope:
    callback_message = getattr(callback_query, "message", None)
    original_message = getattr(callback_message, "reply_to_message", None)
    return CallbackIngressEnvelope(
        transport="telegram",
        event_kind=event_kind,
        user_id=getattr(getattr(callback_query, "from_user", None), "id", None),
        chat_id=getattr(getattr(callback_message, "chat", None), "id", None),
        source_message_id=getattr(callback_message, "id", None),
        raw_data=raw_data if raw_data is not None else getattr(callback_query, "data", None),
        raw_payload={},
        reply_context={
            "reply_to_message_id": getattr(original_message, "id", None),
        },
    )


def build_telegram_document_envelope(
    message,
    *,
    event_kind: str = "document_message",
) -> DocumentIngressEnvelope:
    document = getattr(message, "document", None)
    return DocumentIngressEnvelope(
        transport="telegram",
        event_kind=event_kind,
        user_id=message.chat.id,
        chat_id=message.chat.id,
        source_message_id=getattr(message, "id", None),
        document_name=getattr(document, "file_name", None),
        document_size=getattr(document, "file_size", None),
        mime_type=getattr(document, "mime_type", None),
        raw_payload={},
        reply_context={
            "reply_to_message_id": getattr(getattr(message, "reply_to_message", None), "id", None),
        },
    )
