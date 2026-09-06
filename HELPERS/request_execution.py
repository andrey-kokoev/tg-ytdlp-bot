from __future__ import annotations

from dataclasses import dataclass
import logging

from HELPERS.ingress_models import (
    AddBotToGroupSelectionRequested,
    AddBotToGroupRequested,
    ArgsCommandRequested,
    ArgsTextInputRequested,
    ArgsMenuSelectionRequested,
    AudioDownloadRequested,
    AutoCacheCommandRequested,
    AskFilterSelectionRequested,
    BanTimeCommandRequested,
    BrowserCookieSelectionRequested,
    CleanOptionSelectionRequested,
    ImageRangeSelectionRequested,
    BrowserCookiesRequested,
    BlockUserCommandRequested,
    BroadcastCommandRequested,
    CheckPornCommandRequested,
    CheckCookieRequested,
    CleanCommandRequested,
    CookieMenuRequested,
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
    AskQualitySelectionRequested,
    ConcatRequested,
    CloseMessageRequested,
    CookieMenuSelectionRequested,
    FormatCommandRequested,
    FormatMenuSelectionRequested,
    GalleryFallbackSelectionRequested,
    HelpCommandRequested,
    ImageCommandRequested,
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

import hashlib
import os
from types import SimpleNamespace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramExecutionContext:
    chat_id: int | None
    source_message_id: int | None
    source_message: object | None = None
    callback_query: object | None = None
    message_thread_id: int | None = None


def build_message_execution_context(message) -> TelegramExecutionContext:
    return TelegramExecutionContext(
        chat_id=getattr(getattr(message, "chat", None), "id", None),
        source_message_id=getattr(message, "id", None),
        source_message=message,
        message_thread_id=getattr(message, "message_thread_id", None),
    )


def build_callback_execution_context(callback_query) -> TelegramExecutionContext:
    message = getattr(callback_query, "message", None)
    return TelegramExecutionContext(
        chat_id=getattr(getattr(message, "chat", None), "id", None),
        source_message_id=getattr(message, "id", None),
        source_message=message,
        callback_query=callback_query,
        message_thread_id=getattr(message, "message_thread_id", None),
    )


def handle_subtitle_only_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SubtitleOnlyRequested,
) -> None:
    from COMMANDS.subtitles_cmd import download_subtitles_only, get_or_compute_subs_langs
    from URL_PARSERS.tags import save_user_tags

    save_user_tags(request.user_id, request.tags)
    normal_langs, auto_langs = get_or_compute_subs_langs(request.user_id, request.url)
    available_langs = sorted(set((normal_langs or []) + (auto_langs or [])))
    download_subtitles_only(
        app,
        execution_context.source_message,
        request.url,
        request.tags,
        available_langs,
        playlist_name=request.playlist_name,
        video_count=request.video_count,
        video_start_with=request.video_start_with,
        text_only=request.text_only,
    )


def handle_subtitle_playlist_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SubtitleOnlyRequested,
) -> None:
    from COMMANDS.subtitles_cmd import download_playlist_subtitles_only
    from URL_PARSERS.tags import save_user_tags

    save_user_tags(request.user_id, request.tags)
    download_playlist_subtitles_only(
        app,
        execution_context.source_message,
        request.url,
        request.tags,
        text_only=request.text_only,
    )


def handle_subtitle_settings_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SubtitleSettingsCommandRequested,
) -> None:
    from COMMANDS.subtitles_cmd import subs_command_logic

    subs_command_logic(app, execution_context.source_message, request)


def handle_language_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: LanguageCommandRequested,
) -> None:
    from COMMANDS.lang_cmd import lang_command_logic

    lang_command_logic(app, execution_context.source_message, request)


def handle_playlist_help_request(
    app,
    execution_context: TelegramExecutionContext,
    request: PlaylistHelpRequested,
) -> None:
    from COMMANDS.other_handlers import playlist_command_logic

    playlist_command_logic(app, execution_context.source_message, request)


def handle_help_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: HelpCommandRequested,
) -> None:
    from COMMANDS.other_handlers import help_command_logic

    help_command_logic(app, execution_context.source_message, request)


def handle_image_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ImageCommandRequested,
) -> None:
    from COMMANDS.image_cmd import image_command_logic

    image_command_logic(app, execution_context.source_message, request)


def handle_start_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: StartCommandRequested,
) -> None:
    from URL_PARSERS.url_extractor import start_command_logic

    start_command_logic(app, execution_context.source_message, request)


def handle_add_bot_to_group_request(
    app,
    execution_context: TelegramExecutionContext,
    request: AddBotToGroupRequested,
) -> None:
    from URL_PARSERS.url_extractor import add_bot_to_group_command_logic

    add_bot_to_group_command_logic(app, execution_context.source_message, request)


def handle_add_bot_to_group_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: AddBotToGroupSelectionRequested,
) -> None:
    from URL_PARSERS.url_extractor import add_group_msg_callback_logic

    add_group_msg_callback_logic(app, execution_context.callback_query, request)


def handle_usage_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UsageCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import get_user_usage_stats

    get_user_usage_stats(app, execution_context.source_message)


def handle_uncache_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UncacheCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import uncache_command

    uncache_command(app, execution_context.source_message)


def handle_reload_cache_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ReloadCacheCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import reload_firebase_cache_command_logic

    reload_firebase_cache_command_logic(app, execution_context.source_message, request)


def handle_update_porn_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UpdatePornCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import update_porn_command_logic

    update_porn_command_logic(app, execution_context.source_message, request)


def handle_reload_porn_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ReloadPornCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import reload_porn_command_logic

    reload_porn_command_logic(app, execution_context.source_message, request)


def handle_check_porn_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CheckPornCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import check_porn_command_logic

    check_porn_command_logic(app, execution_context.source_message, request)


def handle_auto_cache_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: AutoCacheCommandRequested,
) -> None:
    from DATABASE.cache_db import auto_cache_command

    auto_cache_command(app, execution_context.source_message)


def handle_runtime_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: RuntimeCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import check_runtime

    check_runtime(execution_context.source_message)


def handle_user_logs_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UserLogsCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import get_user_log

    get_user_log(app, execution_context.source_message)


def handle_user_details_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UserDetailsCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import get_user_details

    get_user_details(app, execution_context.source_message)


def handle_ban_time_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: BanTimeCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import ban_time_command

    ban_time_command(app, execution_context.source_message)


def handle_broadcast_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: BroadcastCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import send_promo_message

    send_promo_message(app, execution_context.source_message)


def handle_block_user_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: BlockUserCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import block_user

    block_user(app, execution_context.source_message)


def handle_unblock_user_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UnblockUserCommandRequested,
) -> None:
    from COMMANDS.admin_cmd import unblock_user

    unblock_user(app, execution_context.source_message)


def handle_clean_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CleanCommandRequested,
) -> None:
    from COMMANDS.clean_cmd import clean_command_logic

    clean_command_logic(app, execution_context.source_message, request)


def handle_clean_option_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CleanOptionSelectionRequested,
) -> None:
    from COMMANDS.clean_cmd import clean_option_callback_logic

    clean_option_callback_logic(app, execution_context.callback_query, request)


def handle_language_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: LanguageSelectionRequested,
) -> None:
    from URL_PARSERS.url_extractor import lang_callback_logic

    lang_callback_logic(app, execution_context.callback_query, request)


def handle_args_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ArgsCommandRequested,
) -> None:
    from COMMANDS.args_cmd import args_command_logic

    args_command_logic(app, execution_context.source_message, request)


def handle_args_menu_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ArgsMenuSelectionRequested,
) -> None:
    from COMMANDS.args_cmd import args_callback_logic

    args_callback_logic(app, execution_context, request)


def handle_args_text_input_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ArgsTextInputRequested,
) -> None:
    from COMMANDS.args_cmd import handle_args_text_input

    handle_args_text_input(app, execution_context, request)


def handle_ask_quality_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: AskQualitySelectionRequested,
    *,
    original_message,
    url: str,
    tags_text: str,
    available_langs,
    proc_msg=None,
) -> None:
    from DOWN_AND_UP.always_ask_menu import askq_callback_logic

    askq_callback_logic(
        app,
        execution_context,
        request.selection_token,
        original_message,
        url,
        tags_text,
        available_langs,
        proc_msg,
    )


def handle_ask_filter_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: AskFilterSelectionRequested,
) -> None:
    from DOWN_AND_UP.always_ask_menu import ask_filter_callback_logic

    ask_filter_callback_logic(
        app,
        execution_context,
        request,
    )


def handle_image_range_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ImageRangeSelectionRequested,
) -> None:
    from COMMANDS.image_cmd import image_command
    from HELPERS.safe_messeger import fake_message
    callback_query = execution_context.callback_query

    range_command = f"/img {request.start_index}-{request.end_index} {request.url}"
    mock_message = fake_message(
        range_command,
        request.user_id,
        original_chat_id=execution_context.chat_id,
        message_thread_id=execution_context.message_thread_id,
        original_message=execution_context.source_message,
    )
    image_command(app, mock_message)


def handle_cookie_menu_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CookieMenuSelectionRequested,
) -> None:
    from COMMANDS.cookies_cmd import _handle_cookie_menu_selection

    _handle_cookie_menu_selection(
        app,
        execution_context=execution_context,
        user_id=request.user_id,
        selection_key=request.selection_key,
    )


def handle_subtitle_settings_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SubtitleSettingsSelectionRequested,
) -> None:
    from COMMANDS.subtitles_cmd import subtitle_settings_callback_logic
    callback_query = execution_context.callback_query

    subtitle_settings_callback_logic(app, callback_query, request)


def handle_format_menu_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: FormatMenuSelectionRequested,
) -> None:
    from COMMANDS.format_cmd import format_menu_callback_logic

    format_menu_callback_logic(app, execution_context, request)


def handle_settings_menu_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SettingsMenuSelectionRequested,
) -> None:
    from COMMANDS.settings_cmd import settings_menu_callback_logic

    settings_menu_callback_logic(app, execution_context, request)


def handle_settings_menu_open_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SettingsMenuOpenRequested,
) -> None:
    from COMMANDS.settings_cmd import settings_command_logic

    settings_command_logic(app, execution_context.source_message, request)


def handle_list_formats_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ListFormatsRequested,
) -> None:
    from COMMANDS.list_cmd import list_command_logic

    list_command_logic(app, execution_context.source_message, request)


def handle_tags_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: TagsCommandRequested,
) -> None:
    from COMMANDS.tag_cmd import tags_command_logic

    tags_command_logic(app, execution_context.source_message, request)


def handle_browser_cookies_request(
    app,
    execution_context: TelegramExecutionContext,
    request: BrowserCookiesRequested,
) -> None:
    from COMMANDS.cookies_cmd import cookies_from_browser_logic

    cookies_from_browser_logic(app, execution_context.source_message, request)


def handle_browser_cookie_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: BrowserCookieSelectionRequested,
) -> None:
    from COMMANDS.cookies_cmd import browser_choice_callback_logic

    browser_choice_callback_logic(app, execution_context, request)


def handle_gallery_fallback_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: GalleryFallbackSelectionRequested,
) -> None:
    from DOWN_AND_UP.always_ask_menu import fallback_gallery_dl_callback_logic

    fallback_gallery_dl_callback_logic(app, execution_context, request)


def handle_cookie_menu_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CookieMenuRequested,
) -> None:
    from COMMANDS.cookies_cmd import download_cookie_logic

    download_cookie_logic(app, execution_context.source_message, request)


def handle_check_cookie_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CheckCookieRequested,
) -> None:
    from COMMANDS.cookies_cmd import checking_cookie_file_logic

    checking_cookie_file_logic(app, execution_context.source_message, request)


def handle_save_cookie_text_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SaveCookieTextRequested,
) -> None:
    from COMMANDS.cookies_cmd import save_as_cookie_file_logic

    save_as_cookie_file_logic(app, execution_context.source_message, request)


def handle_mediainfo_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: MediaInfoCommandRequested,
) -> None:
    from COMMANDS.mediainfo_cmd import mediainfo_command_logic

    mediainfo_command_logic(app, execution_context.source_message, request)


def handle_mediainfo_option_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: MediaInfoOptionSelectionRequested,
) -> None:
    from COMMANDS.mediainfo_cmd import mediainfo_option_callback_logic

    mediainfo_option_callback_logic(app, execution_context, request)


def handle_link_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: LinkCommandRequested,
) -> None:
    from COMMANDS.link_cmd import link_command_logic

    link_command_logic(app, execution_context.source_message, request)


def handle_search_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SearchCommandRequested,
) -> None:
    from COMMANDS.search import search_command_logic

    search_command_logic(app, execution_context.source_message, request)


def handle_keyboard_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: KeyboardCommandRequested,
) -> None:
    from COMMANDS.keyboard_cmd import keyboard_command_logic

    keyboard_command_logic(app, execution_context.source_message, request)


def handle_keyboard_option_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: KeyboardOptionSelectionRequested,
) -> None:
    from COMMANDS.keyboard_cmd import keyboard_callback_logic

    keyboard_callback_logic(app, execution_context, request)


def handle_format_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: FormatCommandRequested,
) -> None:
    from COMMANDS.format_cmd import set_format_logic

    set_format_logic(app, execution_context.source_message, request)


def handle_proxy_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ProxyCommandRequested,
) -> None:
    from COMMANDS.proxy_cmd import proxy_command_logic

    proxy_command_logic(app, execution_context.source_message, request)


def handle_nsfw_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: NsfwCommandRequested,
) -> None:
    from COMMANDS.nsfw_cmd import nsfw_command_logic

    nsfw_command_logic(app, execution_context.source_message, request)


def handle_split_command_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SplitCommandRequested,
) -> None:
    from COMMANDS.split_sizer import split_command_logic

    split_command_logic(app, execution_context.source_message, request)


def handle_settings_command_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SettingsCommandSelectionRequested,
) -> None:
    from COMMANDS.settings_cmd import settings_cmd_callback_logic

    settings_cmd_callback_logic(app, execution_context, request)


def handle_close_message_request(
    app,
    execution_context: TelegramExecutionContext,
    request: CloseMessageRequested,
    *,
    answer_text: str,
    log_text: str,
) -> None:
    from HELPERS.logger import send_to_logger

    callback_query = execution_context.callback_query
    if callback_query is None:
        return
    source_message = execution_context.source_message
    try:
        delete_message = getattr(source_message, "delete", None)
        if callable(delete_message):
            delete_message()
        else:
            raise AttributeError("source message has no delete")
    except Exception:
        try:
            from HELPERS.safe_messeger import safe_edit_reply_markup

            safe_edit_reply_markup(
                execution_context.chat_id,
                execution_context.source_message_id,
                reply_markup=None,
                _callback_query=callback_query,
            )
        except Exception:
            edit_reply_markup = getattr(callback_query, "edit_message_reply_markup", None)
            if callable(edit_reply_markup):
                edit_reply_markup(reply_markup=None)
    answer_callback = getattr(callback_query, "answer", None)
    if callable(answer_callback):
        answer_callback(answer_text)
    send_to_logger(source_message, log_text)


def handle_proxy_option_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ProxyOptionSelectionRequested,
) -> None:
    from COMMANDS.proxy_cmd import proxy_option_callback_logic

    proxy_option_callback_logic(app, execution_context, request)


def handle_nsfw_option_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: NsfwOptionSelectionRequested,
) -> None:
    from COMMANDS.nsfw_cmd import nsfw_option_callback_logic

    nsfw_option_callback_logic(app, execution_context, request)


def handle_split_size_selection_request(
    app,
    execution_context: TelegramExecutionContext,
    request: SplitSizeSelectionRequested,
) -> None:
    from COMMANDS.split_sizer import split_size_callback_logic

    split_size_callback_logic(app, execution_context, request)


def handle_concat_request(
    app,
    execution_context: TelegramExecutionContext,
    request: ConcatRequested,
) -> None:
    from DOWN_AND_UP.audio_concat import concat_audio_playlist_range
    from DOWN_AND_UP.branch_selection_result import (
        audio_concat_branch,
        log_branch_selection,
        video_concat_branch,
    )
    from DOWN_AND_UP.runtime_task import make_runtime_task, with_branch_selection
    from DOWN_AND_UP.video_concat import concat_video_playlist_range
    from HELPERS.logger import logger

    if request.media_mode == "audio":
        branch_result = audio_concat_branch(
            video_count=request.video_count,
            selected_by="explicit_command",
            origin="audio_concat_command_handler",
            provenance={
                "command": request.provenance.get("command_name", "/concat"),
                "reverse_output": request.reverse_output,
                "audio_only": True,
            },
        )
    else:
        branch_result = video_concat_branch(
            video_count=request.video_count,
            selected_by="explicit_command",
            origin="audio_concat_command_handler",
            provenance={
                "command": request.provenance.get("command_name", "/concat"),
                "reverse_output": request.reverse_output,
                "audio_only": False,
                "concat_policy": request.concat_policy,
                "chapter_policy": request.chapter_policy,
            },
        )
    log_branch_selection(logger, branch_result, user_id=request.user_id)
    task = with_branch_selection(
        make_runtime_task(
            user_id=request.user_id,
            source_message_id=request.source_message_id,
            url=request.url,
            tags_text=request.tags_text,
            tags=request.tags,
            playlist_name=request.playlist_name,
            video_count=request.video_count,
            video_start_with=request.video_start_with,
            concat_policy=request.concat_policy,
            concat_ordering=request.concat_ordering,
            chapter_policy=request.chapter_policy,
            output_name_override=request.output_name_override,
        ),
        branch_result,
    )
    if request.media_mode == "audio":
        concat_audio_playlist_range(
            app,
            execution_context.source_message,
            url=request.url,
            video_start_with=request.video_start_with,
            video_end_with=request.video_end_with,
            reverse_output=request.reverse_output,
            output_name_override=request.output_name_override,
            task_context=task,
        )
        return

    concat_video_playlist_range(
        app,
        execution_context.source_message,
        url=request.url,
        video_start_with=request.video_start_with,
        video_end_with=request.video_end_with,
        reverse_output=request.reverse_output,
        output_name_override=request.output_name_override,
        task_context=task,
    )


def handle_rename_request(
    app,
    execution_context: TelegramExecutionContext,
    request: RenameRequested,
) -> None:
    from DOWN_AND_UP.audio_concat import resend_last_audio_concat_with_new_name

    resend_last_audio_concat_with_new_name(
        app,
        execution_context.source_message,
        new_name=request.new_name,
    )


def handle_audio_download_request(
    app,
    execution_context: TelegramExecutionContext,
    request: AudioDownloadRequested,
) -> None:
    from DOWN_AND_UP.branch_selection_result import audio_download_branch, log_branch_selection
    from DOWN_AND_UP.down_and_audio import down_and_audio
    from DOWN_AND_UP.runtime_task import make_runtime_task, with_branch_selection
    from HELPERS.logger import logger
    from URL_PARSERS.tags import save_user_tags

    save_user_tags(request.user_id, request.tags)
    branch_result = audio_download_branch(
        quality_intent=request.quality_key,
        quality_key=request.quality_key,
        video_count=request.video_count,
        format_override=request.format_override,
        selected_by="explicit_command",
        origin="audio_command_handler",
        provenance={"command": request.provenance.get("command_name", "/audio")},
    )
    log_branch_selection(logger, branch_result, user_id=request.user_id)
    task = with_branch_selection(
        make_runtime_task(
            user_id=request.user_id,
            source_message_id=request.source_message_id,
            url=request.url,
            tags_text=request.tags_text,
            tags=request.tags,
            playlist_name=request.playlist_name,
            video_count=request.video_count,
            video_start_with=request.video_start_with,
        ),
        branch_result,
    )
    down_and_audio(
        app,
        execution_context.source_message,
        quality_key=request.quality_key,
        format_override=request.format_override,
        task_context=task,
    )


def handle_url_download_request(
    app,
    execution_context: TelegramExecutionContext,
    request: UrlDownloadRequested,
) -> None:
    from URL_PARSERS.video_extractor import video_url_extractor

    video_url_extractor(app, execution_context=execution_context, url_request=request)


def normalize_url_download_runtime_request(
    *,
    user_id: int,
    source_message_id: int | None,
    raw_input: str,
    request: UrlDownloadRequested | None = None,
):
    if request is not None:
        return request, None

    from URL_PARSERS.tags import extract_url_range_tags

    (
        url,
        video_start_with,
        video_end_with,
        playlist_name,
        tags,
        tags_text,
        tag_error,
    ) = extract_url_range_tags(raw_input)
    normalized = SimpleNamespace(
        user_id=user_id,
        source_message_id=source_message_id,
        raw_input=raw_input,
        url=url,
        playlist_name=playlist_name,
        tags=list(tags),
        tags_text=tags_text,
        video_start_with=video_start_with,
        video_end_with=video_end_with,
    )
    return normalized, tag_error


@dataclass(frozen=True)
class UrlRuntimeDecision:
    mode: str
    request: UrlDownloadRequested | SimpleNamespace
    saved_format: str | None = None
    tag_error: object | None = None
    error_text: str | None = None
    should_clear_playlist_errors: bool = False
    playlist_name_to_clear: str | None = None


@dataclass(frozen=True)
class UrlRuntimeExecutionPlan:
    mode: str
    request: UrlDownloadRequested | SimpleNamespace
    saved_format: str | None = None
    tag_error: object | None = None
    error_text: str | None = None
    should_clear_playlist_errors: bool = False
    playlist_name_to_clear: str | None = None
    tags: tuple[str, ...] = ()
    tags_text: str = ""
    video_count: int = 1
    force_no_title: bool = False


def resolve_saved_format_policy(*, user_id: int) -> tuple[bool, str | None]:
    user_dir = os.path.join("users", str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    format_file = os.path.join(user_dir, "format.txt")

    should_ask = True
    saved_format = None
    if os.path.exists(format_file):
        with open(format_file, "r", encoding="utf-8") as handle:
            fmt = handle.read().strip()
        if fmt != "ALWAYS_ASK":
            should_ask = False
            saved_format = fmt
    return should_ask, saved_format


def determine_url_runtime_decision(
    *,
    user_id: int,
    raw_input: str,
    source_message_id: int | None,
    request: UrlDownloadRequested | None = None,
    has_active_download: bool = False,
    invalid_input_text: str | None = None,
) -> UrlRuntimeDecision:
    runtime_request, tag_error = normalize_url_download_runtime_request(
        user_id=user_id,
        source_message_id=source_message_id,
        raw_input=raw_input,
        request=request,
    )
    should_ask, saved_format = resolve_saved_format_policy(user_id=user_id)

    if should_ask:
        return UrlRuntimeDecision(
            mode="quality_menu",
            request=runtime_request,
            tag_error=tag_error,
        )

    if has_active_download:
        return UrlRuntimeDecision(
            mode="wait_download",
            request=runtime_request,
            saved_format=saved_format,
            should_clear_playlist_errors=True,
        )

    if tag_error:
        return UrlRuntimeDecision(
            mode="tag_error",
            request=runtime_request,
            saved_format=saved_format,
            tag_error=tag_error,
            should_clear_playlist_errors=True,
        )

    if not runtime_request.url:
        return UrlRuntimeDecision(
            mode="invalid_input",
            request=runtime_request,
            saved_format=saved_format,
            error_text=invalid_input_text,
            should_clear_playlist_errors=True,
        )

    if is_url_blacklisted(raw_input):
        return UrlRuntimeDecision(
            mode="blacklisted",
            request=runtime_request,
            saved_format=saved_format,
            should_clear_playlist_errors=True,
        )

    return UrlRuntimeDecision(
        mode="saved_format",
        request=runtime_request,
        saved_format=saved_format,
        should_clear_playlist_errors=True,
        playlist_name_to_clear=runtime_request.playlist_name or None,
    )


def build_url_runtime_execution_plan(
    decision: UrlRuntimeDecision,
) -> UrlRuntimeExecutionPlan:
    if decision.mode != "saved_format":
        return UrlRuntimeExecutionPlan(
            mode=decision.mode,
            request=decision.request,
            saved_format=decision.saved_format,
            tag_error=decision.tag_error,
            error_text=decision.error_text,
            should_clear_playlist_errors=decision.should_clear_playlist_errors,
            playlist_name_to_clear=decision.playlist_name_to_clear,
        )

    media_policy = derive_url_runtime_media_policy(decision.request)
    return UrlRuntimeExecutionPlan(
        mode=decision.mode,
        request=decision.request,
        saved_format=decision.saved_format,
        tag_error=decision.tag_error,
        error_text=decision.error_text,
        should_clear_playlist_errors=decision.should_clear_playlist_errors,
        playlist_name_to_clear=decision.playlist_name_to_clear,
        tags=tuple(media_policy["all_tags"]),
        tags_text=media_policy["tags_text"],
        video_count=media_policy["video_count"],
        force_no_title=media_policy["force_no_title"],
    )


def derive_playlist_start_index(video_start_with: int, video_end_with: int) -> int:
    has_range = (video_start_with != 1 or video_end_with != 1) or (
        video_start_with < 0 or video_end_with < 0
    )
    return video_start_with if has_range else 1


def handle_url_quality_menu_runtime(
    app,
    execution_context: TelegramExecutionContext,
    request: UrlDownloadRequested | SimpleNamespace,
) -> None:
    from DOWN_AND_UP.always_ask_menu import ask_quality_menu

    playlist_start_index = derive_playlist_start_index(
        request.video_start_with,
        request.video_end_with,
    )
    ask_quality_menu(
        app,
        execution_context.source_message,
        request.url,
        list(request.tags),
        playlist_start_index,
    )


def derive_saved_format_quality_key(saved_format: str | None) -> str | None:
    if not saved_format:
        return None
    if "height=144" in saved_format:
        return "144p"
    if "height=240" in saved_format:
        return "240p"
    if "height=360" in saved_format:
        return "360p"
    if "height=480" in saved_format:
        return "480p"
    if "height=720" in saved_format:
        return "720p"
    if "height=1080" in saved_format:
        return "1080p"
    if "height=1440" in saved_format:
        return "1440p"
    if "height=2160" in saved_format:
        return "2160p"
    if "height=4320" in saved_format:
        return "4320p"
    if "height<=144" in saved_format:
        return "144p"
    if "height<=240" in saved_format:
        return "240p"
    if "height<=360" in saved_format:
        return "360p"
    if "height<=480" in saved_format:
        return "480p"
    if "height<=720" in saved_format:
        return "720p"
    if "height<=1080" in saved_format:
        return "1080p"
    if "height<=1440" in saved_format:
        return "1440p"
    if "height<=2160" in saved_format:
        return "2160p"
    if "height<=4320" in saved_format:
        return "4320p"
    if (
        "bestvideo+bestaudio" in saved_format
        or "bv*[vcodec*=avc1]+ba" in saved_format
        or "bv*[vcodec*=av01]+ba" in saved_format
    ):
        return "bestvideo"
    if saved_format == "best":
        return "best"
    return f"custom_{hashlib.md5(saved_format.encode()).hexdigest()[:8]}"


def derive_url_runtime_media_policy(request: UrlDownloadRequested | SimpleNamespace) -> dict:
    from URL_PARSERS.tags import get_auto_tags
    from URL_PARSERS.tiktok import is_tiktok_url

    is_tiktok = is_tiktok_url(request.url)
    auto_tags = get_auto_tags(request.url, request.tags)
    all_tags = list(request.tags) + list(auto_tags)
    tags_text_full = " ".join(all_tags)

    if request.video_start_with < 0 and request.video_end_with < 0:
        video_count = abs(request.video_end_with) - abs(request.video_start_with) + 1
    elif request.video_start_with > request.video_end_with:
        video_count = abs(request.video_start_with - request.video_end_with) + 1
    else:
        video_count = request.video_end_with - request.video_start_with + 1

    return {
        "force_no_title": is_tiktok,
        "all_tags": all_tags,
        "tags_text": tags_text_full,
        "video_count": video_count,
    }


def send_url_tag_error(
    app,
    execution_context: TelegramExecutionContext,
    *,
    user_id: int,
    tag_error,
) -> None:
    if not tag_error:
        return
    from CONFIG.messages import safe_get_messages
    from HELPERS.logger import log_error_to_channel
    from pyrogram.types import ReplyParameters

    wrong, example = tag_error
    error_msg = safe_get_messages(user_id).TAG_FORBIDDEN_CHARS_MSG.format(
        tag=wrong,
        example=example,
    )
    send_kwargs = {"chat_id": user_id, "text": error_msg}
    if execution_context.source_message_id is not None:
        send_kwargs["reply_parameters"] = ReplyParameters(message_id=execution_context.source_message_id)
    app.send_message(**send_kwargs)
    log_error_to_channel(execution_context.source_message, error_msg)


def send_url_wait_download_notice(
    app,
    execution_context: TelegramExecutionContext,
    *,
    user_id: int,
    text: str,
) -> None:
    from pyrogram.types import ReplyParameters

    send_kwargs = {"chat_id": user_id, "text": text}
    if execution_context.source_message_id is not None:
        send_kwargs["reply_parameters"] = ReplyParameters(message_id=execution_context.source_message_id)
    app.send_message(**send_kwargs)


def send_url_runtime_error(
    execution_context: TelegramExecutionContext,
    text: str | None,
) -> None:
    from HELPERS.logger import send_error_to_user

    if text is None:
        return
    send_error_to_user(execution_context.source_message, text)


def clear_user_playlist_error_state(*, user_id: int, playlist_name: str | None = None) -> None:
    from HELPERS.download_status import playlist_errors, playlist_errors_lock

    with playlist_errors_lock:
        if playlist_name:
            error_key = f"{user_id}_{playlist_name}"
            if error_key in playlist_errors:
                del playlist_errors[error_key]
            return

        keys_to_remove = [key for key in playlist_errors if key.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            del playlist_errors[key]


def is_url_blacklisted(raw_input: str) -> bool:
    from CONFIG.config import Config

    return any(blocked in raw_input for blocked in Config.BLACK_LIST)


def handle_saved_format_url_runtime(
    app,
    execution_context: TelegramExecutionContext,
    request: UrlDownloadRequested | SimpleNamespace,
    *,
    saved_format: str,
    tags: list[str],
    tags_text: str,
    video_count: int,
    force_no_title: bool,
) -> None:
    from DOWN_AND_UP.branch_selection_result import log_branch_selection, saved_format_branch
    from DOWN_AND_UP.down_and_up import down_and_up
    from DOWN_AND_UP.runtime_task import make_runtime_task, with_branch_selection
    from HELPERS.logger import logger
    from URL_PARSERS.tags import save_user_tags

    save_user_tags(request.user_id, tags)
    quality_key = derive_saved_format_quality_key(saved_format)
    branch_result = saved_format_branch(
        saved_format=saved_format,
        quality_key=quality_key,
        video_count=video_count,
        origin="video_url_extractor",
    )
    task = with_branch_selection(
        make_runtime_task(
            user_id=request.user_id,
            source_message_id=request.source_message_id,
            url=request.url,
            tags_text=tags_text,
            tags=list(tags),
            playlist_name=request.playlist_name,
            video_count=video_count,
            video_start_with=request.video_start_with,
            force_no_title=force_no_title,
        ),
        branch_result,
    )
    log_branch_selection(logger, branch_result, user_id=request.user_id)
    down_and_up(
        app,
        execution_context.source_message,
        format_override=saved_format,
        quality_key=quality_key,
        task_context=task,
    )


def execute_url_runtime_plan(
    app,
    execution_context: TelegramExecutionContext,
    *,
    user_id: int,
    raw_input: str,
    plan: UrlRuntimeExecutionPlan,
) -> object | None:
    from CONFIG.messages import safe_get_messages
    from HELPERS.limitter import check_playlist_range_limits
    from HELPERS.logger import send_to_logger

    message = execution_context.source_message
    if message is None:
        raise ValueError("URL runtime execution requires a source message")

    if plan.mode == "quality_menu":
        logger.info(f"🔍 [DEBUG] video_extractor: full_string='{raw_input}'")
        logger.info(
            "🔍 [DEBUG] video_extractor: after extract_url_range_tags: url='%s', video_start_with=%s, video_end_with=%s",
            plan.request.url,
            plan.request.video_start_with,
            plan.request.video_end_with,
        )
        if plan.tag_error:
            send_url_tag_error(app, execution_context, user_id=user_id, tag_error=plan.tag_error)
            return None
        logger.info(
            "🔍 [DEBUG] video_extractor: video_start_with=%s, video_end_with=%s",
            plan.request.video_start_with,
            plan.request.video_end_with,
        )
        handle_url_quality_menu_runtime(app, execution_context, plan.request)
        return None

    if plan.should_clear_playlist_errors:
        clear_user_playlist_error_state(
            user_id=user_id,
            playlist_name=plan.playlist_name_to_clear,
        )

    if plan.mode == "wait_download":
        send_url_wait_download_notice(
            app,
            execution_context,
            user_id=user_id,
            text=safe_get_messages(user_id).VIDEO_EXTRACTOR_WAIT_DOWNLOAD_MSG,
        )
        return None

    if plan.mode == "tag_error":
        send_url_tag_error(app, execution_context, user_id=user_id, tag_error=plan.tag_error)
        return None

    if not check_playlist_range_limits(
        plan.request.url,
        plan.request.video_start_with,
        plan.request.video_end_with,
        app,
        message,
    ):
        return None

    if plan.mode == "saved_format":
        users_first_name = getattr(getattr(message, "chat", None), "first_name", "")
        assert plan.saved_format is not None
        send_to_logger(
            message,
            safe_get_messages(user_id).URL_PARSER_USER_ENTERED_URL_LOG_MSG.format(
                user_name=users_first_name,
                url=raw_input,
            ),
        )
        return handle_saved_format_url_runtime(
            app,
            execution_context,
            plan.request,
            saved_format=plan.saved_format,
            tags=list(plan.tags),
            tags_text=plan.tags_text,
            video_count=plan.video_count,
            force_no_title=plan.force_no_title,
        )

    if plan.mode == "blacklisted":
        send_url_runtime_error(
            execution_context,
            safe_get_messages(user_id).PORN_CONTENT_CANNOT_DOWNLOAD_MSG,
        )
        return None

    if plan.mode == "invalid_input":
        assert plan.error_text is not None
        send_url_runtime_error(execution_context, plan.error_text)
        return None

    return None
