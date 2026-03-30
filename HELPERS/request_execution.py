from __future__ import annotations

from HELPERS.ingress_models import (
    AudioDownloadRequested,
    AskFilterSelectionRequested,
    ImageRangeSelectionRequested,
    AskQualitySelectionRequested,
    ConcatRequested,
    CookieMenuSelectionRequested,
    FormatMenuSelectionRequested,
    RenameRequested,
    SubtitleOnlyRequested,
    SubtitleSettingsSelectionRequested,
    UrlDownloadRequested,
)

import hashlib
import os
from types import SimpleNamespace


def handle_subtitle_only_request(app, message, request: SubtitleOnlyRequested) -> None:
    from COMMANDS.subtitles_cmd import download_subtitles_only, get_or_compute_subs_langs
    from URL_PARSERS.tags import save_user_tags

    save_user_tags(request.user_id, request.tags)
    normal_langs, auto_langs = get_or_compute_subs_langs(request.user_id, request.url)
    available_langs = sorted(set((normal_langs or []) + (auto_langs or [])))
    download_subtitles_only(
        app,
        message,
        request.url,
        request.tags,
        available_langs,
        playlist_name=request.playlist_name,
        video_count=request.video_count,
        video_start_with=request.video_start_with,
        text_only=request.text_only,
    )


def handle_ask_quality_selection_request(
    app,
    callback_query,
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
        callback_query,
        request.selection_token,
        original_message,
        url,
        tags_text,
        available_langs,
        proc_msg,
    )


def handle_ask_filter_selection_request(
    app,
    callback_query,
    request: AskFilterSelectionRequested,
) -> None:
    from DOWN_AND_UP.always_ask_menu import ask_filter_callback_logic

    ask_filter_callback_logic(
        app,
        callback_query,
        request,
    )


def handle_image_range_selection_request(
    app,
    callback_query,
    request: ImageRangeSelectionRequested,
) -> None:
    from COMMANDS.image_cmd import image_command
    from HELPERS.safe_messeger import fake_message

    range_command = f"/img {request.start_index}-{request.end_index} {request.url}"
    mock_message = fake_message(
        range_command,
        request.user_id,
        original_chat_id=callback_query.message.chat.id,
        message_thread_id=getattr(callback_query.message, "message_thread_id", None),
        original_message=callback_query.message,
    )
    image_command(app, mock_message)


def handle_cookie_menu_selection_request(
    app,
    callback_query,
    request: CookieMenuSelectionRequested,
) -> None:
    from COMMANDS.cookies_cmd import _handle_cookie_menu_selection

    _handle_cookie_menu_selection(
        app,
        user_id=request.user_id,
        selection_key=request.selection_key,
        message=callback_query.message,
        callback_query=callback_query,
    )


def handle_subtitle_settings_selection_request(
    app,
    callback_query,
    request: SubtitleSettingsSelectionRequested,
) -> None:
    from COMMANDS.subtitles_cmd import subtitle_settings_callback_logic

    subtitle_settings_callback_logic(app, callback_query, request)


def handle_format_menu_selection_request(
    app,
    callback_query,
    request: FormatMenuSelectionRequested,
) -> None:
    from COMMANDS.format_cmd import format_menu_callback_logic

    format_menu_callback_logic(app, callback_query, request)


def handle_concat_request(app, message, request: ConcatRequested) -> None:
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
            message,
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
        message,
        url=request.url,
        video_start_with=request.video_start_with,
        video_end_with=request.video_end_with,
        reverse_output=request.reverse_output,
        output_name_override=request.output_name_override,
        task_context=task,
    )


def handle_rename_request(app, message, request: RenameRequested) -> None:
    from DOWN_AND_UP.audio_concat import resend_last_audio_concat_with_new_name

    resend_last_audio_concat_with_new_name(app, message, new_name=request.new_name)


def handle_audio_download_request(app, message, request: AudioDownloadRequested) -> None:
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
        message,
        quality_key=request.quality_key,
        format_override=request.format_override,
        task_context=task,
    )


def handle_url_download_request(app, message, request: UrlDownloadRequested) -> None:
    from URL_PARSERS.video_extractor import video_url_extractor

    video_url_extractor(app, message, url_request=request)


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


def derive_playlist_start_index(video_start_with: int, video_end_with: int) -> int:
    has_range = (video_start_with != 1 or video_end_with != 1) or (
        video_start_with < 0 or video_end_with < 0
    )
    return video_start_with if has_range else 1


def handle_url_quality_menu_runtime(
    app,
    message,
    request: UrlDownloadRequested,
) -> None:
    from DOWN_AND_UP.always_ask_menu import ask_quality_menu

    playlist_start_index = derive_playlist_start_index(
        request.video_start_with,
        request.video_end_with,
    )
    ask_quality_menu(
        app,
        message,
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


def send_url_tag_error(app, message, *, user_id: int, tag_error) -> None:
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
    app.send_message(
        user_id,
        error_msg,
        reply_parameters=ReplyParameters(message_id=message.id),
    )
    log_error_to_channel(message, error_msg)


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
    message,
    request: UrlDownloadRequested,
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
        message,
        format_override=saved_format,
        quality_key=quality_key,
        task_context=task,
    )
