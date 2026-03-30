from __future__ import annotations

from HELPERS.ingress_models import (
    AddBotToGroupSelectionRequested,
    AddBotToGroupRequested,
    ArgsCommandRequested,
    ArgsTextInputRequested,
    ArgsMenuSelectionRequested,
    AudioDownloadRequested,
    AutoCacheCommandRequested,
    AskFilterSelectionRequested,
    AskQualitySelectionRequested,
    BanTimeCommandRequested,
    BrowserCookieSelectionRequested,
    BrowserCookiesRequested,
    BlockUserCommandRequested,
    BroadcastCommandRequested,
    CallbackIngressEnvelope,
    GalleryFallbackSelectionRequested,
    CheckPornCommandRequested,
    CheckCookieRequested,
    CleanCommandRequested,
    CleanOptionSelectionRequested,
    ConcatRequested,
    CloseMessageRequested,
    CookieMenuRequested,
    CookieMenuSelectionRequested,
    CookieUploadRequested,
    DocumentIngressEnvelope,
    FormatCommandRequested,
    FormatMenuSelectionRequested,
    HelpCommandRequested,
    ImageCommandRequested,
    ImageRangeSelectionRequested,
    IngressEnvelope,
    LanguageCommandRequested,
    LanguageSelectionRequested,
    ListFormatsRequested,
    LinkCommandRequested,
    KeyboardCommandRequested,
    KeyboardOptionSelectionRequested,
    MediaInfoCommandRequested,
    MediaInfoOptionSelectionRequested,
    NsfwCommandRequested,
    NsfwOptionSelectionRequested,
    PlaylistHelpRequested,
    ProxyCommandRequested,
    ProxyOptionSelectionRequested,
    ReloadCacheCommandRequested,
    ReloadPornCommandRequested,
    RenameRequested,
    RuntimeCommandRequested,
    SaveCookieTextRequested,
    SearchCommandRequested,
    StartCommandRequested,
    SettingsMenuOpenRequested,
    SettingsCommandSelectionRequested,
    SettingsMenuSelectionRequested,
    SplitCommandRequested,
    TagsCommandRequested,
    SplitSizeSelectionRequested,
    SubtitleOnlyRequested,
    SubtitleSettingsCommandRequested,
    SubtitleSettingsSelectionRequested,
    UncacheCommandRequested,
    UnblockUserCommandRequested,
    UpdatePornCommandRequested,
    UserDetailsCommandRequested,
    UserLogsCommandRequested,
    UsageCommandRequested,
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
    command_name = f"/{command_tokens[0]}" if command_tokens else "/concat"
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
            "command_name": command_name,
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
    command_name = f"/{command_tokens[0]}" if command_tokens else "/audio"
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
            "command_name": command_name,
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


def build_args_command_request(
    envelope: IngressEnvelope,
) -> ArgsCommandRequested:
    return ArgsCommandRequested(
        request_kind="ArgsCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_args_menu_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_key: str,
) -> ArgsMenuSelectionRequested:
    return ArgsMenuSelectionRequested(
        request_kind="ArgsMenuSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        action_key=action_key,
    )


def build_args_text_input_request(
    envelope: IngressEnvelope,
) -> ArgsTextInputRequested:
    return ArgsTextInputRequested(
        request_kind="ArgsTextInputRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={"event_kind": envelope.event_kind},
    )


def build_clean_option_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_key: str,
) -> CleanOptionSelectionRequested:
    return CleanOptionSelectionRequested(
        request_kind="CleanOptionSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        action_key=action_key,
    )


def build_browser_cookie_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_key: str,
) -> BrowserCookieSelectionRequested:
    return BrowserCookieSelectionRequested(
        request_kind="BrowserCookieSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        action_key=action_key,
    )


def build_gallery_fallback_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_key: str,
) -> GalleryFallbackSelectionRequested:
    return GalleryFallbackSelectionRequested(
        request_kind="GalleryFallbackSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        action_key=action_key,
    )


def build_subtitle_settings_command_request(
    envelope: IngressEnvelope,
) -> SubtitleSettingsCommandRequested:
    return SubtitleSettingsCommandRequested(
        request_kind="SubtitleSettingsCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_language_command_request(
    envelope: IngressEnvelope,
) -> LanguageCommandRequested:
    return LanguageCommandRequested(
        request_kind="LanguageCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_playlist_help_request(
    envelope: IngressEnvelope,
) -> PlaylistHelpRequested:
    return PlaylistHelpRequested(
        request_kind="PlaylistHelpRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_help_command_request(
    envelope: IngressEnvelope,
) -> HelpCommandRequested:
    return HelpCommandRequested(
        request_kind="HelpCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_start_command_request(
    envelope: IngressEnvelope,
) -> StartCommandRequested:
    return StartCommandRequested(
        request_kind="StartCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_image_command_request(
    envelope: IngressEnvelope,
) -> ImageCommandRequested:
    return ImageCommandRequested(
        request_kind="ImageCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_add_bot_to_group_request(
    envelope: IngressEnvelope,
) -> AddBotToGroupRequested:
    return AddBotToGroupRequested(
        request_kind="AddBotToGroupRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_add_bot_to_group_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_kind: str,
    action_value: str | None,
) -> AddBotToGroupSelectionRequested:
    return AddBotToGroupSelectionRequested(
        request_kind="AddBotToGroupSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        action_kind=action_kind,
        action_value=action_value,
    )


def build_usage_command_request(
    envelope: IngressEnvelope,
) -> UsageCommandRequested:
    return UsageCommandRequested(
        request_kind="UsageCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_uncache_command_request(
    envelope: IngressEnvelope,
) -> UncacheCommandRequested:
    return UncacheCommandRequested(
        request_kind="UncacheCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_reload_cache_command_request(
    envelope: IngressEnvelope,
) -> ReloadCacheCommandRequested:
    return ReloadCacheCommandRequested(
        request_kind="ReloadCacheCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_update_porn_command_request(
    envelope: IngressEnvelope,
) -> UpdatePornCommandRequested:
    return UpdatePornCommandRequested(
        request_kind="UpdatePornCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_reload_porn_command_request(
    envelope: IngressEnvelope,
) -> ReloadPornCommandRequested:
    return ReloadPornCommandRequested(
        request_kind="ReloadPornCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_check_porn_command_request(
    envelope: IngressEnvelope,
) -> CheckPornCommandRequested:
    return CheckPornCommandRequested(
        request_kind="CheckPornCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_auto_cache_command_request(
    envelope: IngressEnvelope,
) -> AutoCacheCommandRequested:
    return AutoCacheCommandRequested(
        request_kind="AutoCacheCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_runtime_command_request(
    envelope: IngressEnvelope,
) -> RuntimeCommandRequested:
    return RuntimeCommandRequested(
        request_kind="RuntimeCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_user_logs_command_request(
    envelope: IngressEnvelope,
) -> UserLogsCommandRequested:
    return UserLogsCommandRequested(
        request_kind="UserLogsCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_user_details_command_request(
    envelope: IngressEnvelope,
) -> UserDetailsCommandRequested:
    return UserDetailsCommandRequested(
        request_kind="UserDetailsCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_ban_time_command_request(
    envelope: IngressEnvelope,
) -> BanTimeCommandRequested:
    return BanTimeCommandRequested(
        request_kind="BanTimeCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_broadcast_command_request(
    envelope: IngressEnvelope,
) -> BroadcastCommandRequested:
    return BroadcastCommandRequested(
        request_kind="BroadcastCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_block_user_command_request(
    envelope: IngressEnvelope,
) -> BlockUserCommandRequested:
    return BlockUserCommandRequested(
        request_kind="BlockUserCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_unblock_user_command_request(
    envelope: IngressEnvelope,
) -> UnblockUserCommandRequested:
    return UnblockUserCommandRequested(
        request_kind="UnblockUserCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_clean_command_request(
    envelope: IngressEnvelope,
) -> CleanCommandRequested:
    return CleanCommandRequested(
        request_kind="CleanCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_language_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    action_kind: str,
    action_value: str | None,
) -> LanguageSelectionRequested:
    return LanguageSelectionRequested(
        request_kind="LanguageSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        action_kind=action_kind,
        action_value=action_value,
    )


def build_settings_menu_open_request(
    envelope: IngressEnvelope,
) -> SettingsMenuOpenRequested:
    return SettingsMenuOpenRequested(
        request_kind="SettingsMenuOpenRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_list_formats_request(
    envelope: IngressEnvelope,
    *,
    url: str | None,
) -> ListFormatsRequested:
    return ListFormatsRequested(
        request_kind="ListFormatsRequested",
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
    )


def build_tags_command_request(
    envelope: IngressEnvelope,
) -> TagsCommandRequested:
    return TagsCommandRequested(
        request_kind="TagsCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_browser_cookies_request(
    envelope: IngressEnvelope,
) -> BrowserCookiesRequested:
    return BrowserCookiesRequested(
        request_kind="BrowserCookiesRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_cookie_menu_request(
    envelope: IngressEnvelope,
) -> CookieMenuRequested:
    return CookieMenuRequested(
        request_kind="CookieMenuRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_check_cookie_request(
    envelope: IngressEnvelope,
) -> CheckCookieRequested:
    return CheckCookieRequested(
        request_kind="CheckCookieRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_save_cookie_text_request(
    envelope: IngressEnvelope,
) -> SaveCookieTextRequested:
    return SaveCookieTextRequested(
        request_kind="SaveCookieTextRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_mediainfo_command_request(
    envelope: IngressEnvelope,
) -> MediaInfoCommandRequested:
    return MediaInfoCommandRequested(
        request_kind="MediaInfoCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_mediainfo_option_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> MediaInfoOptionSelectionRequested:
    return MediaInfoOptionSelectionRequested(
        request_kind="MediaInfoOptionSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )


def build_link_command_request(
    envelope: IngressEnvelope,
) -> LinkCommandRequested:
    return LinkCommandRequested(
        request_kind="LinkCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_search_command_request(
    envelope: IngressEnvelope,
) -> SearchCommandRequested:
    return SearchCommandRequested(
        request_kind="SearchCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_keyboard_command_request(
    envelope: IngressEnvelope,
) -> KeyboardCommandRequested:
    return KeyboardCommandRequested(
        request_kind="KeyboardCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_keyboard_option_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> KeyboardOptionSelectionRequested:
    return KeyboardOptionSelectionRequested(
        request_kind="KeyboardOptionSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )


def build_format_command_request(
    envelope: IngressEnvelope,
) -> FormatCommandRequested:
    return FormatCommandRequested(
        request_kind="FormatCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_proxy_command_request(
    envelope: IngressEnvelope,
) -> ProxyCommandRequested:
    return ProxyCommandRequested(
        request_kind="ProxyCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_nsfw_command_request(
    envelope: IngressEnvelope,
) -> NsfwCommandRequested:
    return NsfwCommandRequested(
        request_kind="NsfwCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
    )


def build_split_command_request(
    envelope: IngressEnvelope,
) -> SplitCommandRequested:
    return SplitCommandRequested(
        request_kind="SplitCommandRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_text,
        provenance={
            "event_kind": envelope.event_kind,
            "command_tokens": list((envelope.raw_payload or {}).get("command_tokens") or []),
        },
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


def build_close_message_request(
    envelope: CallbackIngressEnvelope,
    *,
    close_scope: str,
) -> CloseMessageRequested:
    return CloseMessageRequested(
        request_kind="CloseMessageRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={
            "event_kind": envelope.event_kind,
        },
        close_scope=close_scope,
    )


def build_settings_menu_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> SettingsMenuSelectionRequested:
    return SettingsMenuSelectionRequested(
        request_kind="SettingsMenuSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )


def build_settings_command_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> SettingsCommandSelectionRequested:
    return SettingsCommandSelectionRequested(
        request_kind="SettingsCommandSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )


def build_proxy_option_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> ProxyOptionSelectionRequested:
    return ProxyOptionSelectionRequested(
        request_kind="ProxyOptionSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )


def build_nsfw_option_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> NsfwOptionSelectionRequested:
    return NsfwOptionSelectionRequested(
        request_kind="NsfwOptionSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )


def build_split_size_selection_request(
    envelope: CallbackIngressEnvelope,
    *,
    selection_key: str,
) -> SplitSizeSelectionRequested:
    return SplitSizeSelectionRequested(
        request_kind="SplitSizeSelectionRequested",
        user_id=envelope.user_id,
        chat_id=envelope.chat_id,
        source_message_id=envelope.source_message_id,
        source_transport=envelope.transport,
        raw_input=envelope.raw_data,
        provenance={"event_kind": envelope.event_kind},
        selection_key=selection_key,
    )
