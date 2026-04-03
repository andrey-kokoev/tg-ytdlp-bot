# --- Callback Processor ---
import os
import hashlib
import re
from datetime import datetime
import json
from dataclasses import dataclass
from typing import Any, cast
from pyrogram import filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters, WebAppInfo
import requests
from HELPERS.porn import is_porn
from DOWN_AND_UP.branch_selection_result import BranchSelectionResult
from DOWN_AND_UP.runtime_task import RuntimeTask, ensure_runtime_task, make_runtime_task, with_branch_selection
from DOWN_AND_UP.task_plan_executor import execute_routing_plan
from HELPERS.ingress_models import build_telegram_callback_envelope
from HELPERS.ingress_requests import (
    build_ask_filter_selection_request,
    build_ask_quality_selection_request,
    build_gallery_fallback_selection_request,
)
from HELPERS.request_execution import (
    build_callback_execution_context,
    handle_ask_filter_selection_request,
    handle_ask_quality_selection_request,
    handle_gallery_fallback_selection_request,
)

def safe_callback_answer(callback_query, text, show_alert=False):
    """Safely answer callback query, handling QueryIdInvalid errors"""
    try:
        callback_query.answer(text, show_alert=show_alert)
    except Exception:
        pass  # Query ID might be invalid after long operation


def _select_video_branch(
    user_id: int,
    *,
    quality_intent: str,
    quality_key: str | None,
    format_override: str | None,
    video_count: int = 1,
    selected_by: str = "explicit_callback",
    origin: str,
    provenance: dict | None = None,
) -> BranchSelectionResult:
    branch_result = video_download_branch(
        quality_intent=quality_intent,
        quality_key=quality_key,
        format_override=format_override,
        video_count=video_count,
        selected_by=selected_by,
        origin=origin,
        provenance=provenance,
    )
    log_branch_selection(logger, branch_result, user_id=user_id)
    return branch_result


def _select_audio_branch(
    user_id: int,
    *,
    quality_intent: str,
    quality_key: str | None,
    video_count: int = 1,
    format_override: str | None = "ba",
    selected_by: str = "explicit_callback",
    origin: str,
    provenance: dict | None = None,
) -> BranchSelectionResult:
    branch_result = audio_download_branch(
        quality_intent=quality_intent,
        quality_key=quality_key,
        video_count=video_count,
        format_override=format_override,
        selected_by=selected_by,
        origin=origin,
        provenance=provenance,
    )
    log_branch_selection(logger, branch_result, user_id=user_id)
    return branch_result


def _select_direct_link_branch(
    user_id: int,
    *,
    quality_intent: str,
    quality_key: str | None,
    task_scope: str = "single_item",
    selected_by: str = "explicit_callback",
    origin: str,
    provenance: dict | None = None,
) -> BranchSelectionResult:
    branch_result = direct_link_branch(
        quality_intent=quality_intent,
        quality_key=quality_key,
        task_scope=task_scope,
        selected_by=selected_by,
        origin=origin,
        provenance=provenance,
    )
    log_branch_selection(logger, branch_result, user_id=user_id)
    return branch_result


def _select_callback_download_branch(
    user_id: int,
    *,
    callback_data: str,
    quality_intent: str,
    quality_key: str | None,
    format_override: str | None,
    video_count: int = 1,
    origin: str,
    provenance: dict | None = None,
    force_branch_family: str | None = None,
) -> BranchSelectionResult:
    branch_family = force_branch_family or ("audio" if callback_data == "mp3" else "video")
    if branch_family == "audio":
        return _select_audio_branch(
            user_id,
            quality_intent=quality_intent,
            quality_key=quality_key,
            video_count=video_count,
            format_override=format_override,
            origin=origin,
            provenance=provenance,
        )

    return _select_video_branch(
        user_id,
        quality_intent=quality_intent,
        quality_key=quality_key,
        format_override=format_override,
        video_count=video_count,
        origin=origin,
        provenance=provenance,
    )


def _dispatch_callback_download_branch(
    app,
    original_message,
    task: RuntimeTask,
    *,
    proc_msg=None,
    clear_subs_cache_on_start: bool = False,
) -> None:
    user_id = task.user_id
    branch_result = task.branch_selection_result
    if branch_result is None:
        raise ValueError("RuntimeTask must carry branch_selection_result before dispatch")
    if proc_msg is not None and task.proc_msg_id is None:
        task = task.with_proc_msg_id(getattr(proc_msg, "id", None))
    delete_processing_message(app, user_id, proc_msg)

    if branch_result.branch_family == "audio_download":
        down_and_audio(
            app,
            original_message,
            quality_key=branch_result.quality_key,
            format_override=branch_result.format_override,
            cookies_already_checked=True,
            task_context=task,
        )
        return

    if task.playlist_name or task.video_count > 1 or task.video_start_with != 1:
        down_and_up(
            app,
            original_message,
            format_override=branch_result.format_override,
            quality_key=branch_result.quality_key,
            cookies_already_checked=True,
            clear_subs_cache_on_start=clear_subs_cache_on_start,
            task_context=task,
        )
        return

    down_and_up_with_format(
        app,
        original_message,
        fmt=branch_result.format_override,
        quality_key=branch_result.quality_key,
        proc_msg=proc_msg,
        task_context=task,
    )


def _make_callback_runtime_task(
    original_message,
    *,
    url: str,
    tags,
    tags_text: str,
    branch_result: BranchSelectionResult,
    playlist_name: str | None = None,
    video_count: int = 1,
    video_start_with: int = 1,
    proc_msg=None,
) -> RuntimeTask:
    base_task = make_runtime_task(
        user_id=original_message.chat.id,
        source_message_id=getattr(original_message, "id", None),
        url=url,
        tags_text=tags_text,
        tags=list(tags) if tags is not None else None,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        force_no_title=is_tiktok_url(url),
        proc_msg_id=getattr(proc_msg, "id", None),
    )
    return with_branch_selection(base_task, branch_result)

from HELPERS.app_instance import get_app
from HELPERS.decorators import get_main_reply_keyboard
from HELPERS.logger import send_to_logger, logger, send_error_to_user, log_error_to_channel
from HELPERS.safe_messeger import safe_send_message, safe_delete_messages, safe_edit_message_text
from CONFIG.logger_msg import LoggerMsg
from HELPERS.filesystem_hlp import create_directory
from HELPERS.qualifier import get_quality_by_min_side, get_real_height_for_quality
from HELPERS.limitter import check_subs_limits, check_playlist_range_limits, TimeFormatter

from CONFIG.config import Config
from CONFIG.messages import Messages, safe_get_messages
from CONFIG.logger_msg import LoggerMsg
from URL_PARSERS.tags import extract_url_range_tags

from COMMANDS.subtitles_cmd import (
    clear_subs_check_cache, is_subs_enabled, check_subs_availability, 
    get_user_subs_auto_mode, download_subtitles_only, get_user_subs_language, _subs_check_cache,
    LANGUAGES, get_language_keyboard, is_subs_always_ask, save_subs_always_ask,
    get_language_keyboard_always_ask, get_available_subs_languages, get_flag,
    save_user_subs_language, save_user_subs_auto_mode,
)
from COMMANDS.split_sizer import get_user_split_size
from COMMANDS.nsfw_cmd import should_apply_spoiler

from DATABASE.cache_db import (
    get_cached_qualities, get_cached_playlist_count, get_cached_playlist_videos, 
    get_cached_playlist_qualities, save_to_video_cache, get_cached_message_ids
)

from DOWN_AND_UP.yt_dlp_hook import get_video_formats
from HELPERS.pot_helper import build_cli_extractor_args
from COMMANDS.format_cmd import set_session_mkv_override
from DOWN_AND_UP.down_and_audio import down_and_audio
from DOWN_AND_UP.down_and_up import down_and_up
from DOWN_AND_UP.branch_selection_result import (
    BranchSelectionResult,
    audio_download_branch,
    direct_link_branch,
    gallery_fallback_branch,
    log_branch_selection,
    resolve_direct_link_preference,
    redirected_audio_branch,
    video_download_branch,
)
from DOWN_AND_UP.direct_link_flow import (
    execute_direct_link_flow,
    send_always_ask_direct_link_response,
    send_always_ask_direct_link_response_legacy_error,
)
from DOWN_AND_UP.runtime_task import RuntimeTask, ensure_runtime_task, make_runtime_task, with_branch_selection

from URL_PARSERS.playlist_utils import is_playlist_with_range
from URL_PARSERS.tags import generate_final_tags, extract_url_range_tags
from URL_PARSERS.youtube import is_youtube_url, download_thumbnail, youtube_to_piped_url
from URL_PARSERS.tiktok import is_tiktok_url
from URL_PARSERS.normalizer import get_clean_playlist_url
from URL_PARSERS.embedder import transform_to_embed_url, is_instagram_url, is_twitter_url, is_reddit_url
from URL_PARSERS.thumbnail_downloader import download_thumbnail as download_universal_thumbnail

# Import function to get user args
def get_user_args(user_id: int):
    """Get user's saved args settings"""
    import os
    import json
    user_dir = os.path.join("users", str(user_id))
    args_file = os.path.join(user_dir, "args.txt")
    
    if not os.path.exists(args_file):
        return {}
    
    try:
        with open(args_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(LoggerMsg.ALWAYS_ASK_ERROR_READING_USER_ARGS_LOG_MSG.format(user_id=user_id, error=e))
        return {}
from COMMANDS.image_cmd import image_command
from DOWN_AND_UP.gallery_command_result import (
    did_gallery_command_succeed,
    is_gallery_command_result,
)
from HELPERS.safe_messeger import fake_message

# Get app instance for decorators
app = get_app()
assert app is not None


def _dispatch_gallery_fallback(
    app,
    *,
    user_id: int,
    fallback_text: str,
    original_chat_id: int,
    message_thread_id,
    original_message,
    runtime_task: RuntimeTask | None = None,
) -> None:
    fake_msg = fake_message(
        fallback_text,
        user_id,
        original_chat_id=original_chat_id,
        message_thread_id=message_thread_id,
        original_message=original_message,
        runtime_task=runtime_task,
    )
    return image_command(app, fake_msg)


@dataclass(frozen=True)
class GalleryFallbackTransitionPlan:
    user_id: int
    url: str
    video_start_with: int
    video_end_with: int
    original_chat_id: int
    message_thread_id: int | None
    fallback_text: str
    runtime_task: RuntimeTask


@dataclass(frozen=True)
class AlwaysAskSourceContext:
    original_message: Any
    url: str
    url_text: str


@dataclass(frozen=True)
class AlwaysAskFilterTransition:
    mode: str
    answer_text: str | None = None
    show_alert: bool = False
    page: int | None = None


@dataclass(frozen=True)
class AlwaysAskSubsMenuPlan:
    reply_markup: InlineKeyboardMarkup
    answer_text: str


@dataclass(frozen=True)
class AlwaysAskDubsMenuPlan:
    reply_markup: InlineKeyboardMarkup
    answer_text: str


@dataclass(frozen=True)
class AlwaysAskFilterUpdatePlan:
    mode: str
    answer_text: str | None = None
    show_alert: bool = False


@dataclass(frozen=True)
class AlwaysAskQualitySelectionPlan:
    mode: str
    answer_text: str | None = None
    quality_key: str | None = None
    format_override: str | None = None
    branch_family: str = "video"
    download_subtitles_only: bool = False


@dataclass(frozen=True)
class AlwaysAskSpecialActionPlan:
    mode: str
    answer_text: str | None = None
    show_alert: bool = False


@dataclass(frozen=True)
class AlwaysAskClosePlan:
    user_id: int
    format_cache_pattern: str
    answer_text: str


@dataclass(frozen=True)
class AlwaysAskNavigationPlan:
    mode: str
    page: int | None = None
    url: str | None = None
    answer_text: str | None = None
    show_alert: bool = False
    keep_current_cache: bool = False


@dataclass(frozen=True)
class OtherQualitiesMenuPlan:
    text: str
    reply_markup: InlineKeyboardMarkup
    answer_text: str


@dataclass(frozen=True)
class AlwaysAskOtherFormatSelectionPlan:
    mode: str
    answer_text: str | None = None
    show_alert: bool = False
    format_id: str | None = None


@dataclass(frozen=True)
class AlwaysAskManualQualitySelectionPlan:
    mode: str
    answer_text: str | None = None
    show_alert: bool = False
    quality: str | None = None
    format_override: str | None = None
    quality_key: str | None = None
    branch_family: str = "video"


@dataclass(frozen=True)
class AlwaysAskGalleryFallbackPrompt:
    message_text: str
    callback_data: str


@dataclass(frozen=True)
class AlwaysAskMenuSourceDecision:
    mode: str
    info: dict | None = None
    error_text: str | None = None
    gallery_fallback_prompt: AlwaysAskGalleryFallbackPrompt | None = None


@dataclass(frozen=True)
class AlwaysAskMenuFailureDecision:
    mode: str
    fallback_text: str | None = None
    runtime_task: RuntimeTask | None = None


@dataclass(frozen=True)
class CachedQualitiesMenuPlan:
    text: str
    reply_markup: InlineKeyboardMarkup


@dataclass(frozen=True)
class QualityMenuRenderPlan:
    text: str
    reply_markup: InlineKeyboardMarkup
    can_send_thumb_menu: bool
    thumb_path: str | None
    is_nsfw: bool


@dataclass(frozen=True)
class QualityMenuComposition:
    text: str
    keyboard_rows: list


@dataclass(frozen=True)
class QualityMenuDataModel:
    cap: str
    quality_map: dict
    found_quality_keys: set
    filters_state: dict
    selected_codec: str
    selected_ext: str
    user_fixed_format: str | None
    found_subtitle_type: str | None


def _emit_gallery_fallback_transition_start(callback_query, plan: GalleryFallbackTransitionPlan) -> None:
    safe_callback_answer(callback_query, "🔄 Switching to gallery-dl...")
    try:
        callback_query.message.delete()
        logger.info(f"Deleted fallback gallery-dl message for user {plan.user_id}")
    except Exception as e:
        logger.warning(f"Failed to delete fallback gallery-dl message: {e}")


def _emit_gallery_fallback_transition_error(callback_query, error: Exception) -> None:
    logger.error(f"Error in fallback_gallery_dl_callback: {error}")
    safe_callback_answer(callback_query, "❌ Error switching to gallery-dl", show_alert=True)


def _build_gallery_fallback_transition_plan(
    execution_context,
    request,
) -> GalleryFallbackTransitionPlan:
    callback_query = execution_context.callback_query
    if callback_query is None:
        raise ValueError("Gallery fallback selection requires callback execution context")

    user_id = request.user_id
    url_data = get_original_data_from_callback("fallback_gallery_dl", request.action_key)
    url_parts = url_data.split("|")
    url = url_parts[0]

    if len(url_parts) >= 3:
        video_start_with = int(url_parts[1])
        video_end_with = int(url_parts[2])
        logger.info(
            "[FALLBACK DEBUG] Extracted range from callback data: %s-%s",
            video_start_with,
            video_end_with,
        )
    else:
        video_start_with = 1
        video_end_with = 1
        logger.info("[FALLBACK DEBUG] No range in callback data, using default: 1-1")

    if len(url_parts) >= 4:
        original_chat_id = int(url_parts[3])
    else:
        original_chat_id = execution_context.chat_id or callback_query.message.chat.id

    if video_start_with != 1 or video_end_with != 1:
        fallback_text = f"/img {video_start_with}-{video_end_with} {url}"
        logger.info(
            "[FALLBACK DEBUG] Creating fallback command with range: %s-%s",
            video_start_with,
            video_end_with,
        )
    else:
        fallback_text = f"/img {url}"
        logger.info("[FALLBACK DEBUG] Creating fallback command without range")

    fallback_branch = gallery_fallback_branch(
        None,
        origin="always_ask_menu",
        reason="explicit_callback_gallery_fallback",
    )
    runtime_task = make_runtime_task(
        user_id=user_id,
        source_message_id=execution_context.source_message_id,
        url=url,
        tags_text="",
        video_count=max(1, video_end_with - video_start_with + 1),
        video_start_with=video_start_with,
        proc_msg_id=None,
        branch_selection_result=fallback_branch,
    )

    return GalleryFallbackTransitionPlan(
        user_id=user_id,
        url=url,
        video_start_with=video_start_with,
        video_end_with=video_end_with,
        original_chat_id=original_chat_id,
        message_thread_id=execution_context.message_thread_id,
        fallback_text=fallback_text,
        runtime_task=runtime_task,
    )


def _execute_gallery_fallback_transition_plan_core(
    *,
    plan: GalleryFallbackTransitionPlan,
    app,
    callback_query,
) -> dict:
    """
    Core execution logic for gallery fallback transition plan.

    Returns dict with execution result.
    """
    from COMMANDS.image_cmd import image_command

    logger.info(
        "[FALLBACK] Executing gallery fallback for user %s: %s (range: %s-%s)",
        plan.user_id,
        plan.url,
        plan.video_start_with,
        plan.video_end_with,
    )

    _emit_gallery_fallback_transition_start(callback_query, plan)

    logger.info(
        "[FALLBACK] fallback_task.user_id=%s, message_thread_id=%s, callback_query.message.chat.id=%s, callback_query.message.message_thread_id=%s",
        plan.runtime_task.user_id,
        plan.message_thread_id,
        callback_query.message.chat.id,
        getattr(callback_query.message, "message_thread_id", None),
    )
    logger.info(
        "About to execute image_command for user %s with fake_msg: %s",
        plan.user_id,
        plan.fallback_text,
    )

    # Build fake message for gallery-dl command
    class FakeMessage:
        def __init__(self, user_id, chat_id, text, message_thread_id=None):
            self.from_user = type('User', (), {'id': user_id})()
            self.chat = type('Chat', (), {'id': chat_id, 'type': enums.ChatType.PRIVATE})()
            self.text = text
            self.id = None
            self.message_thread_id = message_thread_id

        def reply_text(self, *args, **kwargs):
            return None

    fake_msg = FakeMessage(
        user_id=plan.user_id,
        chat_id=plan.original_chat_id,
        text=plan.fallback_text,
        message_thread_id=plan.message_thread_id,
    )

    # Execute gallery-dl command
    fallback_result = image_command(app, fake_msg)

    fallback_outcome_kind = (
        fallback_result.outcome_kind
        if fallback_result is not None and is_gallery_command_result(fallback_result)
        else None
    )
    logger.info(
        "Gallery-dl fallback result for user %s: outcome=%s success=%s",
        plan.user_id,
        fallback_outcome_kind,
        None,  # Success check moved to caller
    )

    logger.info(
        "Gallery-dl fallback executed for user %s: %s",
        plan.user_id,
        plan.fallback_text,
    )

    return {
        "fallback_result": fallback_result,
        "user_id": plan.user_id,
        "url": plan.url,
    }


def _execute_gallery_fallback_transition_plan_with_evidence(
    *,
    plan: GalleryFallbackTransitionPlan,
    app,
    callback_query,
) -> tuple[dict, RuntimeTask]:
    """
    PDA-refactored gallery fallback transition executor using TaskPlanExecutor.

    Returns (result_dict, updated_task) with execution evidence recorded.
    """
    def _executor(p: GalleryFallbackTransitionPlan) -> dict:
        return _execute_gallery_fallback_transition_plan_core(
            plan=p,
            app=app,
            callback_query=callback_query,
        )

    # Get the runtime task from the plan
    task_context = plan.runtime_task

    # Execute with evidence recording (ROUTING category for transition decisions)
    new_task, result = execute_routing_plan(
        task_context,
        plan,
        _executor,
        executor_name="_execute_gallery_fallback_transition_plan",
    )

    return result, new_task


def _build_always_ask_source_context(execution_context) -> AlwaysAskSourceContext | None:
    source_message = execution_context.source_message
    if source_message is None:
        return None

    original_message = getattr(source_message, "reply_to_message", None)
    if original_message is None:
        return None

    url_text = original_message.text or (original_message.caption or "")
    match = re.search(r'https?://[^\s\*#]+', url_text)
    url = match.group(0) if match else url_text
    return AlwaysAskSourceContext(
        original_message=original_message,
        url=url,
        url_text=url_text,
    )


def _determine_ask_filter_transition(
    user_id: int,
    *,
    kind: str,
    value: str,
    source_context: AlwaysAskSourceContext | None,
) -> AlwaysAskFilterTransition:
    messages = safe_get_messages(user_id)

    if kind == "subs" and value == "open":
        if source_context is None:
            return AlwaysAskFilterTransition("error", messages.ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        return AlwaysAskFilterTransition("subs_open")

    if kind == "subs_page":
        if source_context is None:
            return AlwaysAskFilterTransition("error", messages.ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        return AlwaysAskFilterTransition(
            "subs_page",
            messages.PAGE_NUMBER_MSG.format(page=int(value) + 1),
            page=int(value),
        )

    if kind == "subs" and value == "back":
        return AlwaysAskFilterTransition("reopen_quality_menu")

    if kind == "subs" and value == "close":
        return AlwaysAskFilterTransition("close_subs_menu", messages.SUBTITLE_MENU_CLOSED_MSG)

    if kind == "subs_lang":
        return AlwaysAskFilterTransition("set_subs_lang", messages.SUBTITLE_LANGUAGE_SET_MSG.format(value=value))

    if kind == "dubs" and value == "open":
        if source_context is None:
            return AlwaysAskFilterTransition("error", messages.ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        return AlwaysAskFilterTransition("dubs_open")

    if kind == "audio_lang":
        return AlwaysAskFilterTransition("set_audio_lang", messages.AUDIO_SET_MSG.format(value=value))

    if kind == "dubs" and value in ("back", "close"):
        return AlwaysAskFilterTransition("reopen_quality_menu", messages.FILTERS_UPDATED_MSG)

    if kind in ("codec", "ext", "toggle"):
        return AlwaysAskFilterTransition("update_filters", messages.FILTERS_UPDATED_MSG)

    return AlwaysAskFilterTransition("noop", messages.FILTERS_UPDATED_MSG)


def _build_askf_subs_menu_plan(
    user_id: int,
    *,
    normal_langs,
    auto_langs,
    page: int,
) -> AlwaysAskSubsMenuPlan:
    langs = sorted(set(normal_langs) | set(auto_langs))
    kb = get_language_keyboard_always_ask(
        page=page,
        user_id=user_id,
        langs_override=langs,
        per_page_rows=8,
        normal_langs=normal_langs,
        auto_langs=auto_langs,
    )
    answer_text = (
        safe_get_messages(user_id).CHOOSE_SUBTITLE_LANGUAGE_MSG
        if page == 0
        else safe_get_messages(user_id).PAGE_NUMBER_MSG.format(page=page + 1)
    )
    return AlwaysAskSubsMenuPlan(reply_markup=kb, answer_text=answer_text)


def _emit_askf_subs_menu(callback_query, plan: AlwaysAskSubsMenuPlan) -> None:
    try:
        callback_query.edit_message_reply_markup(reply_markup=plan.reply_markup)
    except Exception:
        pass
    safe_callback_answer(callback_query, plan.answer_text)


def _build_askf_dubs_menu_plan(user_id: int, langs) -> AlwaysAskDubsMenuPlan:
    rows, row = [], []
    for i, lang in enumerate(sorted(langs)):
        flag = _dub_flag(lang)
        label = f"{flag} {lang}" if flag else lang
        row.append(InlineKeyboardButton(label, callback_data=f"askf|audio_lang|{lang}"))
        if (i + 1) % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(safe_get_messages(user_id).BACK_BUTTON_TEXT, callback_data="askf|dubs|back"),
        InlineKeyboardButton(safe_get_messages(user_id).CLOSE_BUTTON_TEXT, callback_data="askf|dubs|close"),
    ])
    return AlwaysAskDubsMenuPlan(
        reply_markup=InlineKeyboardMarkup(rows),
        answer_text=safe_get_messages(user_id).CHOOSE_AUDIO_LANGUAGE_MSG,
    )


def _emit_askf_dubs_menu(callback_query, plan: AlwaysAskDubsMenuPlan) -> None:
    try:
        callback_query.edit_message_reply_markup(reply_markup=plan.reply_markup)
    except Exception:
        pass
    safe_callback_answer(callback_query, plan.answer_text)


def _reopen_askf_quality_menu(app, callback_query, source_context: AlwaysAskSourceContext | None) -> None:
    if source_context is not None:
        ask_quality_menu(
            app,
            source_context.original_message,
            source_context.url,
            [],
            playlist_start_index=1,
            cb=callback_query,
        )


def _close_askf_subs_menu(app, callback_query, answer_text: str | None) -> None:
    try:
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
    except Exception:
        app.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.id,
            reply_markup=None,
        )
    if answer_text:
        safe_callback_answer(callback_query, answer_text)


def _determine_askf_filter_update_plan(
    user_id: int,
    *,
    kind: str,
    value: str,
    source_context: AlwaysAskSourceContext | None,
) -> AlwaysAskFilterUpdatePlan | None:
    if kind not in ("codec", "ext", "toggle"):
        return None

    messages = safe_get_messages(user_id)
    if kind == "ext" and value == "empty":
        return AlwaysAskFilterUpdatePlan(
            mode="error",
            answer_text=messages.ALWAYS_ASK_FORMAT_FIXED_VIA_ARGS_MSG,
            show_alert=True,
        )

    if source_context is None:
        return AlwaysAskFilterUpdatePlan(
            mode="error",
            answer_text=messages.ERROR_ORIGINAL_NOT_FOUND_MSG,
            show_alert=True,
        )

    available_formats = get_available_formats_from_cache(user_id, source_context.url)
    if kind == "codec" and value not in available_formats["codecs"] and available_formats["codecs"]:
        return AlwaysAskFilterUpdatePlan(
            mode="error",
            answer_text=messages.AA_ERROR_CODEC_NOT_AVAILABLE_MSG.format(codec=value.upper()),
            show_alert=True,
        )
    if kind == "ext" and value not in available_formats["formats"] and available_formats["formats"]:
        return AlwaysAskFilterUpdatePlan(
            mode="error",
            answer_text=messages.AA_ERROR_FORMAT_NOT_AVAILABLE_MSG.format(format=value.upper()),
            show_alert=True,
        )

    return AlwaysAskFilterUpdatePlan(
        mode="apply",
        answer_text=messages.FILTERS_UPDATED_MSG,
    )


def _execute_askf_filter_update_plan(
    app,
    callback_query,
    user_id: int,
    source_context: AlwaysAskSourceContext | None,
    *,
    kind: str,
    value: str,
    plan: AlwaysAskFilterUpdatePlan,
) -> None:
    if plan.answer_text and plan.mode == "error":
        safe_callback_answer(callback_query, plan.answer_text, show_alert=plan.show_alert)
        return

    set_filter(user_id, kind, value)
    if kind == "ext":
        try:
            set_session_mkv_override(user_id, value == "mkv")
        except Exception:
            pass
    elif kind == "toggle" and value == "off":
        set_filter(user_id, "codec", "avc1")
        set_filter(user_id, "ext", "mp4")

    _reopen_askf_quality_menu(app, callback_query, source_context)
    if plan.answer_text:
        safe_callback_answer(callback_query, plan.answer_text)


def _build_quality_range_context(original_message):
    full_string = original_message.text or original_message.caption or ""
    _, video_start_with, video_end_with, playlist_name, _, _, _ = extract_url_range_tags(full_string)
    if video_start_with < 0 and video_end_with < 0:
        video_count = abs(video_end_with) - abs(video_start_with) + 1
    elif video_start_with > video_end_with:
        video_count = abs(video_start_with - video_end_with) + 1
    else:
        video_count = video_end_with - video_start_with + 1
    return full_string, video_start_with, video_end_with, playlist_name, video_count


def _determine_ask_quality_selection_plan(user_id: int, *, data: str) -> AlwaysAskQualitySelectionPlan:
    messages = safe_get_messages(user_id)
    if data == "mp3":
        return AlwaysAskQualitySelectionPlan(
            mode="download",
            answer_text="🎧 Downloading audio...",
            quality_key="mp3",
            format_override="ba",
            branch_family="audio",
        )
    if data == "subs_only":
        return AlwaysAskQualitySelectionPlan(
            mode="subs_only",
            answer_text="💬 Downloading subtitles only...",
            download_subtitles_only=True,
        )
    if data == "best":
        return AlwaysAskQualitySelectionPlan(
            mode="best_video",
            answer_text=messages.ALWAYS_ASK_DOWNLOADING_BEST_QUALITY_MSG,
            quality_key="best",
            branch_family="video",
        )
    return AlwaysAskQualitySelectionPlan(
        mode="quality_video",
        answer_text=f"{messages.ALWAYS_ASK_DOWNLOADING_QUALITY_MSG} {data}...",
        quality_key=data,
        branch_family="video",
    )


def _determine_askq_special_action_plan(
    user_id: int,
    *,
    data: str,
    source_context: AlwaysAskSourceContext | None,
) -> AlwaysAskSpecialActionPlan | None:
    messages = safe_get_messages(user_id)
    if data == "link":
        if source_context is None:
            return AlwaysAskSpecialActionPlan("error", messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        return AlwaysAskSpecialActionPlan("link", messages.ALWAYS_ASK_GETTING_DIRECT_LINK_MSG)
    if data == "list":
        if source_context is None:
            return AlwaysAskSpecialActionPlan("error", messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        return AlwaysAskSpecialActionPlan("list", messages.ALWAYS_ASK_GETTING_FORMATS_MSG)
    if data == "image":
        if source_context is None:
            return AlwaysAskSpecialActionPlan("error", messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        return AlwaysAskSpecialActionPlan("image", messages.ALWAYS_ASK_STARTING_GALLERY_DL_MSG)
    if data == "quick_embed":
        if source_context is None:
            return AlwaysAskSpecialActionPlan("error", messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG, True)
        if not source_context.url:
            return AlwaysAskSpecialActionPlan("error", messages.AA_ERROR_URL_NOT_FOUND_MSG, True)
        return AlwaysAskSpecialActionPlan("quick_embed")
    return None


def _build_askq_close_plan(user_id: int) -> AlwaysAskClosePlan:
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)
    user_download_dir = get_user_download_dir(user_id)
    if user_download_dir and os.path.exists(user_download_dir):
        format_cache_pattern = os.path.join(user_download_dir, "formats_cache_*.json")
    else:
        format_cache_pattern = os.path.join(user_dir, "formats_cache_*.json")
    return AlwaysAskClosePlan(
        user_id=user_id,
        format_cache_pattern=format_cache_pattern,
        answer_text=safe_get_messages(user_id).ALWAYS_ASK_MENU_CLOSED_MSG,
    )


def _execute_askq_close_plan(app, callback_query, close_plan: AlwaysAskClosePlan) -> None:
    try:
        import glob
        old_cache_files = glob.glob(close_plan.format_cache_pattern)
        for cache_file in old_cache_files:
            try:
                os.remove(cache_file)
                logger.info(f"{LoggerMsg.ALWAYS_ASK_CLEANED_UP_OLD_FORMAT_CACHE_LOG_MSG}: {cache_file}")
            except Exception as e:
                logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_REMOVE_OLD_CACHE_FILE_LOG_MSG} {cache_file}: {e}")
        if old_cache_files:
            logger.info(
                f"{LoggerMsg.ALWAYS_ASK_CLEANED_UP_OLD_FORMAT_CACHE_FILES_BEFORE_CLOSING_LOG_MSG}: {len(old_cache_files)}"
            )
    except Exception as e:
        logger.warning(f"{LoggerMsg.ALWAYS_ASK_ERROR_CLEANING_UP_OLD_FORMAT_CACHE_FILES_BEFORE_CLOSING_LOG_MSG}: {e}")

    callback_message = getattr(callback_query, "message", None)
    try:
        if callback_message and getattr(callback_message, "chat", None) and getattr(callback_message, "id", None):
            safe_delete_messages(chat_id=callback_message.chat.id, message_ids=[callback_message.id])
    except Exception:
        if callback_message and getattr(callback_message, "chat", None) and getattr(callback_message, "id", None):
            app.edit_message_reply_markup(
                chat_id=callback_message.chat.id,
                message_id=callback_message.id,
                reply_markup=None,
            )
    safe_callback_answer(callback_query, close_plan.answer_text)


def _determine_other_format_selection_plan(
    user_id: int,
    *,
    data: str,
    source_context: AlwaysAskSourceContext | None,
) -> AlwaysAskOtherFormatSelectionPlan | None:
    if not data.startswith("other_id_"):
        return None

    messages = safe_get_messages(user_id)
    if source_context is None:
        return AlwaysAskOtherFormatSelectionPlan(
            mode="error",
            answer_text=messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG,
            show_alert=True,
        )
    if not source_context.url:
        return AlwaysAskOtherFormatSelectionPlan(
            mode="error",
            answer_text=messages.AA_ERROR_URL_NOT_FOUND_MSG,
            show_alert=True,
        )

    format_id_hash = data.replace("other_id_", "")
    format_id = get_original_data_from_callback("askq|other_id", f"askq|{data}")
    if format_id == format_id_hash:
        format_id = format_id_hash

    return AlwaysAskOtherFormatSelectionPlan(
        mode="download",
        answer_text=f"{messages.ALWAYS_ASK_DOWNLOADING_FORMAT_MSG} {format_id}...",
        format_id=format_id,
    )


def _build_manual_quality_format_override(quality: str) -> str:
    if quality == "best":
        return "bv*[vcodec*=avc1]+ba[acodec*=mp4a]/bv*[vcodec*=avc1]+ba/bv+ba/best"

    quality_str = quality.replace("p", "")
    quality_val = int(quality_str)
    if quality_val >= 4320:
        prev = 2160
    elif quality_val >= 2160:
        prev = 1440
    elif quality_val >= 1440:
        prev = 1080
    elif quality_val >= 1080:
        prev = 720
    elif quality_val >= 720:
        prev = 480
    elif quality_val >= 480:
        prev = 360
    elif quality_val >= 360:
        prev = 240
    elif quality_val >= 240:
        prev = 144
    else:
        prev = 0
    return (
        f"bv*[vcodec*=avc1][height<={quality_val}][height>{prev}]+ba[acodec*=mp4a]/"
        f"bv*[vcodec*=avc1][height<={quality_val}]+ba[acodec*=mp4a]/"
        "bv*[vcodec*=avc1]+ba/best/bv+ba/best"
    )


def _determine_askq_navigation_plan(
    user_id: int,
    *,
    data: str,
    callback_query,
    source_context: AlwaysAskSourceContext | None,
) -> AlwaysAskNavigationPlan | None:
    messages = safe_get_messages(user_id)

    if data.startswith("other_page_"):
        if source_context is None or not source_context.url:
            return AlwaysAskNavigationPlan(
                mode="error",
                answer_text=messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG,
                show_alert=True,
            )
        return AlwaysAskNavigationPlan(
            mode="other_page",
            page=int(data.replace("other_page_", "")),
            url=source_context.url,
            keep_current_cache=True,
        )

    if data == "other_back":
        if source_context is None or not source_context.url:
            return AlwaysAskNavigationPlan(
                mode="error",
                answer_text=messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG,
                show_alert=True,
            )
        return AlwaysAskNavigationPlan(
            mode="reopen_quality_menu",
            url=source_context.url,
            keep_current_cache=True,
        )

    if data == "manual_back":
        if source_context is None:
            return AlwaysAskNavigationPlan(
                mode="error",
                answer_text=messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG,
                show_alert=True,
            )
        if not source_context.url:
            return AlwaysAskNavigationPlan(
                mode="error",
                answer_text=messages.AA_ERROR_URL_NOT_FOUND_MSG,
                show_alert=True,
            )
        return AlwaysAskNavigationPlan(
            mode="manual_back",
            url=source_context.url,
        )

    return None


def _determine_manual_quality_selection_plan(
    user_id: int,
    *,
    data: str,
    source_context: AlwaysAskSourceContext | None,
) -> AlwaysAskManualQualitySelectionPlan | None:
    if not data.startswith("manual_"):
        return None

    messages = safe_get_messages(user_id)
    if source_context is None:
        return AlwaysAskManualQualitySelectionPlan(
            mode="error",
            answer_text=messages.AA_ERROR_ORIGINAL_NOT_FOUND_MSG,
            show_alert=True,
        )
    if not source_context.url:
        return AlwaysAskManualQualitySelectionPlan(
            mode="error",
            answer_text=messages.AA_ERROR_URL_NOT_FOUND_MSG,
            show_alert=True,
        )

    quality = data.replace("manual_", "")
    if quality == "mp3":
        return AlwaysAskManualQualitySelectionPlan(
            mode="download",
            answer_text=f"{messages.ALWAYS_ASK_DOWNLOADING_QUALITY_MSG} {quality}...",
            quality=quality,
            quality_key="mp3",
            format_override="ba",
            branch_family="audio",
        )

    try:
        format_override = _build_manual_quality_format_override(quality)
    except ValueError:
        format_override = "bv*[vcodec*=avc1]+ba[acodec*=mp4a]/bv*[vcodec*=avc1]+ba/bv+ba/best"

    return AlwaysAskManualQualitySelectionPlan(
        mode="download",
        answer_text=f"{messages.ALWAYS_ASK_DOWNLOADING_QUALITY_MSG} {quality}...",
        quality=quality,
        quality_key=quality,
        format_override=format_override,
        branch_family="video",
    )


def _build_other_qualities_menu_plan(
    callback_query,
    *,
    format_lines,
    page: int,
    url: str,
    video_title: str,
    is_nsfw: bool,
    is_private_chat: bool,
    from_cache: bool = False,
) -> OtherQualitiesMenuPlan:
    user_id = callback_query.from_user.id
    cap = f"<b>{video_title}</b>\n"
    cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_ALL_AVAILABLE_FORMATS_MSG}</b>\n"
    if isinstance(url, str) and is_nsfw and is_private_chat:
        cap += "\n<b>⭐️ — 🔞NSFW is paid (⭐️$0.02)</b>\n"
    cap += f"\n<i>{safe_get_messages(user_id).PAGE_NUMBER_MSG.format(page=page + 1)}</i>\n"

    formats_per_page = 10
    total_formats = len(format_lines)
    total_pages = (total_formats + formats_per_page - 1) // formats_per_page
    start_idx = page * formats_per_page
    end_idx = min(start_idx + formats_per_page, total_formats)
    page_formats = format_lines[start_idx:end_idx]

    user_args = get_user_args(user_id)
    send_as_file = user_args.get("send_as_file", False)
    cached_qualities = set()
    if not send_as_file:
        try:
            cached_qualities = get_cached_qualities(url)
        except Exception:
            pass

    keyboard_rows = []
    for format_line in page_formats:
        format_id = format_line.split()[0].strip()
        if format_id and not format_id.startswith("[") and not format_id.startswith("(") and format_id != "unknown":
            button_parts = extract_button_data(format_line)
            if button_parts:
                button_text = " | ".join(button_parts)
                if format_id in cached_qualities and not is_nsfw:
                    button_text = f"🚀 {button_text}"
                elif is_nsfw and is_private_chat:
                    button_text = f"1⭐️ {button_text}"
                if len(button_text) > (64 if from_cache else 40):
                    limit = 61 if from_cache else 37
                    button_text = button_text[:limit] + "..."
                callback_data = create_safe_callback_data("askq|other_id", format_id)
                logger.info(f"Created callback_data '{callback_data}' for format_id '{format_id}'")
                keyboard_rows.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_PREV_BUTTON_MSG, callback_data=f"askq|other_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_NEXT_BUTTON_MSG, callback_data=f"askq|other_page_{page+1}"))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(safe_get_messages(user_id).BACK_BUTTON_TEXT if not from_cache else "🔙Back", callback_data="askq|other_back"),
        InlineKeyboardButton(
            safe_get_messages(user_id).CLOSE_BUTTON_TEXT if not from_cache else safe_get_messages(user_id).URL_EXTRACTOR_HELP_CLOSE_BUTTON_MSG,
            callback_data="askq|close",
        ),
    ])

    answer_text = (
        f"{safe_get_messages(user_id).ALWAYS_ASK_FORMATS_PAGE_FROM_CACHE_MSG} {page + 1}/{total_pages} {safe_get_messages(user_id).ALWAYS_ASK_FROM_CACHE_MSG}"
        if from_cache
        else f"Formats page {page + 1}/{total_pages}"
    )
    return OtherQualitiesMenuPlan(
        text=cap,
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        answer_text=answer_text,
    )


def _emit_other_qualities_menu_plan(app, callback_query, *, menu_plan: OtherQualitiesMenuPlan, original_message) -> None:
    user_id = callback_query.from_user.id
    try:
        if callback_query.message.photo:
            callback_query.edit_message_caption(
                caption=menu_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=menu_plan.reply_markup,
            )
        else:
            callback_query.edit_message_text(
                text=menu_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=menu_plan.reply_markup,
            )
        safe_callback_answer(callback_query, menu_plan.answer_text)
    except Exception:
        try:
            chat_id = callback_query.message.chat.id
            ref_id = original_message.id if original_message else None
            app.send_message(
                chat_id,
                menu_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=menu_plan.reply_markup,
                reply_parameters=ReplyParameters(message_id=ref_id) if ref_id else None,
            )
            safe_callback_answer(callback_query, menu_plan.answer_text)
        except Exception as e2:
            logger.error(f"Error showing other qualities menu: {e2}")
            safe_callback_answer(callback_query, safe_get_messages(user_id).ALWAYS_ASK_ERROR_SHOWING_FORMATS_MENU_MSG, show_alert=True)

# Proxy functionality is now handled by COMMANDS.proxy_cmd
logger.info(LoggerMsg.ALWAYS_ASK_IMPORTED_LOG_MSG.format(app_available=app is not None))

def format_filesize(size_str):
    """Convert filesize to shortest readable format (kb, mb, gb)"""
    if not size_str or size_str in ['unknown', 'none', '|', '≈']:
        return None
    
    # Only process KiB, MiB, GiB formats
    import re
    if not re.match(r'^\d+\.?\d*(KiB|MiB|GiB)$', size_str, re.IGNORECASE):
        return None
    
    # Remove any non-numeric characters except decimal point
    clean_size = re.sub(r'[^\d.]', '', size_str)
    
    try:
        size = float(clean_size)
    except ValueError:
        return None
    
    # Determine the original unit from the original string
    original_str = size_str.lower()
    if 'kib' in original_str:
        unit_multiplier = 1024
    elif 'mib' in original_str:
        unit_multiplier = 1024 * 1024
    elif 'gib' in original_str:
        unit_multiplier = 1024 * 1024 * 1024
    else:
        return None  # Only process KiB/MiB/GiB
    
    # Convert to bytes
    bytes_size = size * unit_multiplier
    
    # Convert to shortest readable format
    if bytes_size and bytes_size >= 1024 * 1024 * 1024:  # GB
        return f"{bytes_size / (1024 * 1024 * 1024):.0f}gb"
    elif bytes_size and bytes_size >= 1024 * 1024:  # MB
        return f"{bytes_size / (1024 * 1024):.0f}mb"
    elif bytes_size and bytes_size >= 1024:  # KB
        return f"{bytes_size / 1024:.0f}kb"
    else:
        return f"{bytes_size:.0f}b"

def create_safe_callback_data(prefix, data, max_length=50):
    """Create safe callback_data that doesn't exceed Telegram's 64-byte limit"""
    import hashlib
    
    # Calculate total length including prefix and separators
    full_data = f"{prefix}|{data}"
    
    if len(full_data) <= 64:
        return full_data
    
    # If too long, use hash
    data_hash = hashlib.md5(data.encode()).hexdigest()[:16]
    safe_callback = f"{prefix}|{data_hash}"
    
    # Store mapping for later retrieval
    mapping_attr = f"_{prefix.replace('|', '_')}_mapping"
    if not hasattr(create_safe_callback_data, mapping_attr):
        setattr(create_safe_callback_data, mapping_attr, {})
    
    mapping = getattr(create_safe_callback_data, mapping_attr)
    mapping[data_hash] = data
    setattr(create_safe_callback_data, mapping_attr, mapping)
    
    return safe_callback

def get_original_data_from_callback(prefix, callback_data):
    """Get original data from safe callback_data using mapping"""
    try:
        data_hash = callback_data.replace(f"{prefix}|", "")
        mapping_attr = f"_{prefix.replace('|', '_')}_mapping"
        
        logger.info(f"Looking for data_hash '{data_hash}' in mapping_attr '{mapping_attr}'")
        
        if hasattr(create_safe_callback_data, mapping_attr):
            mapping = getattr(create_safe_callback_data, mapping_attr)
            logger.info(f"Mapping found: {mapping}")
            result = mapping.get(data_hash, data_hash)  # Return original data or hash if not found
            logger.info(f"Retrieved result: '{result}'")
            return result
        else:
            logger.warning(f"Mapping attribute '{mapping_attr}' not found")
    except Exception as e:
        logger.warning(LoggerMsg.ALWAYS_ASK_ERROR_RETRIEVING_CALLBACK_LOG_MSG.format(error=e))
    
    fallback = callback_data.replace(f"{prefix}|", "")
    logger.info(f"Using fallback: '{fallback}'")
    return fallback

def extract_button_data(format_line):
    """Extract only needed data for button display from complete format line"""
    parts = format_line.split()
    button_parts = []
    
    # Media extensions to look for (popular formats only)
    media_extensions = ['mp4', 'webm', 'm4a', 'mkv', 'avi', 'mov', 'flv', 'wmv', '3gp', 'ogv', 'ts', 'mts', 'm2ts', 'mp3', 'ogg', 'm3u8', 'f4v', 'm4v', 'm4p', 'm4b', 'm4r', '3g2', '3gpp', '3gpp2', 'asf', 'divx', 'xvid', 'rm', 'rmvb', 'vob', 'vcd', 'svcd', 'dvd', 'iso', 'sub', 'idx', 'srt', 'ssa', 'ass', 'vtt', 'smi', 'sami', 'rt', 'txt', 'lrc', 'vobsub', 'dvdsub', 'pgs', 'dvb', 'hdmv', 'pcm', 'wav', 'aiff', 'wma', 'ape', 'flac', 'alac', 'aac', 'ac3', 'dts', 'dtshd', 'truehd', 'eac3', 'mp2', 'opus', 'vorbis', 'speex', 'amr', 'awb', 'gsm', 'amrnb', 'amrwb']
    
    # Codec patterns to look for (popular codecs only)
    codec_patterns = ['avc', 'vp9', 'av1', 'h264', 'h265', 'hevc', 'avc1', 'vp09', 'av01', 'opus', 'aac', 'ac3', 'dts', 'mp3', 'wav', 'flac', 'alac', 'vorbis', 'speex', 'amr', 'gsm', 'amrnb', 'amrwb', 'mp2', 'eac3', 'truehd', 'dtshd', 'pcm', 'aiff', 'wma', 'ape', 'ogg', 'm4a', 'm4b', 'm4p', 'm4r', 'f4a', 'f4b', 'f4p', 'f4v', '3g2', '3gpp', '3gpp2', 'asf', 'divx', 'xvid', 'rm', 'rmvb', 'vob', 'vcd', 'svcd', 'dvd', 'sub', 'idx', 'srt', 'ssa', 'ass', 'vtt', 'smi', 'sami', 'rt', 'txt', 'lrc', 'vobsub', 'dvdsub', 'pgs', 'dvb', 'hdmv']
    
    # Extract all possible data from format line
    all_extracted = []
    
    for part in parts:
        part = part.strip()
        
        # Skip empty or invalid parts
        if not part or part in ['unknown', 'none', '|', '≈'] or len(part) == 1 and part.isdigit():
            continue
        
        # Check for media extension
        if part.lower() in media_extensions:
            all_extracted.append(part)
            continue
        
        # Check for resolution pattern (WxH)
        if 'x' in part and part.replace('x', '').replace('p', '').isdigit():
            all_extracted.append(part)
            continue
        
        # Check for filesize pattern (only KiB/MiB/GiB)
        import re
        if re.match(r'^\d+\.?\d*(KiB|MiB|GiB)$', part, re.IGNORECASE):
            formatted_size = format_filesize(part)
            if formatted_size:
                all_extracted.append(formatted_size)
            continue
        
        # Check for quality pattern (e.g., 144p, 720p60, 1080p60)
        if re.match(r'^\d+p\d*$', part):
            all_extracted.append(part)
            continue
        
        # Extract quality from format names (e.g., h264_540p_389369-0 -> 540p)
        quality_match = re.search(r'(\d+p\d*)', part)
        if quality_match:
            all_extracted.append(quality_match.group(1))
            continue
        
        # Check for video codec patterns
        if any(codec in part.lower() for codec in codec_patterns):
            # Shorten video codec names
            if part.startswith('avc1'):
                part = 'avc1'
            elif part.startswith('vp9'):
                part = 'vp9'
            elif part.startswith('vp09'):
                part = 'vp9'
            elif part.startswith('av1'):
                part = 'av1'
            elif part.startswith('av01'):
                part = 'av1'
            all_extracted.append(part)
            continue
        
        # Check for audio indicator
        if part.lower() == 'audio':
            all_extracted.append('audio')
            continue
    
    # Extract data from format names (first part of the line)
    format_name = parts[0] if parts else ""
    
    # Replace url360, url240, etc. with 360p, 240p, etc.
    url_quality_match = re.search(r'url(\d+)', format_name, re.IGNORECASE)
    if url_quality_match:
        quality = url_quality_match.group(1) + 'p'
        all_extracted.append(quality)
    
    # Extract specific patterns from format names
    # Extract hls from hls_fmp4-12_4-Audio
    if 'hls' in format_name.lower():
        all_extracted.append('hls')
    
    # Extract mp4 from hls_fmp4-12_4-Audio
    if 'mp4' in format_name.lower():
        all_extracted.append('mp4')
    
    # Extract dash from dash_sep-7
    if 'dash' in format_name.lower():
        all_extracted.append('dash')
    
    # Extract other extensions and codecs from format names
    for ext in media_extensions:
        if ext.lower() in format_name.lower() and ext not in ['mp4', 'hls', 'dash']:  # Avoid duplicates
            all_extracted.append(ext)
    
    for codec in codec_patterns:
        if codec.lower() in format_name.lower():
            # Shorten codec names
            if codec.startswith('avc1.'):
                codec = 'avc1'
            elif codec.startswith('vp9'):
                codec = 'vp9'
            elif codec.startswith('vp09'):
                codec = 'vp9'
            elif codec.startswith('av1.'):
                codec = 'av1'
            elif codec.startswith('av01.'):
                codec = 'av1'
            all_extracted.append(codec)
    
    # Extract quality from format names like hls_fmp4-12_4-Audio
    quality_from_name = re.search(r'(\d+p\d*)', format_name, re.IGNORECASE)
    if quality_from_name:
        all_extracted.append(quality_from_name.group(1))
    
    # Remove duplicates while preserving order (including comma variations)
    seen = set()
    for item in all_extracted:
        # Clean up item (remove commas, extra spaces)
        clean_item = item.strip().rstrip(',')
        
        # Handle combined items like m4a_dash, mp4_dash
        if '_' in clean_item:
            # Split combined items and add each part if not already present
            parts_combined = clean_item.split('_')
            for part_combined in parts_combined:
                part_combined = part_combined.strip()
                if part_combined and part_combined.lower() not in seen:
                    seen.add(part_combined.lower())
                    button_parts.append(part_combined)
            continue
        
        # Convert to lowercase for comparison but keep original case
        clean_item_lower = clean_item.lower()
        if clean_item_lower not in seen:
            seen.add(clean_item_lower)
            button_parts.append(clean_item)
    
    return button_parts

# In-memory filters for Always Ask (per user session)
_ASK_FILTERS = {}
_ASK_INFO_CACHE_FILE = "ask_formats.json"
_ASK_SUBS_LANGS_PREFIX = "ask_subs_"
# Store download directories for each user session
_USER_DOWNLOAD_DIRS = {}
# Store processing messages for each user session
_PROC_MSG_CACHE = {}

def get_filters(user_id):
    f = _ASK_FILTERS.get(str(user_id))
    if not f:
        # defaults: filters hidden to keep UI simple
        f = {"codec": "avc1", "ext": "mp4", "visible": False, "audio_lang": None, "has_dubs": False, "available_dubs": []}
        _ASK_FILTERS[str(user_id)] = f
    return f

def set_user_download_dir(user_id, download_dir):
    """Set download directory for user session"""
    _USER_DOWNLOAD_DIRS[str(user_id)] = download_dir

def get_user_download_dir(user_id):
    """Get download directory for user session"""
    return _USER_DOWNLOAD_DIRS.get(str(user_id))

def set_user_proc_msg(user_id, proc_msg):
    """Set processing message for user session"""
    _PROC_MSG_CACHE[str(user_id)] = proc_msg

def get_user_proc_msg(user_id):
    """Get processing message for user session"""
    return _PROC_MSG_CACHE.get(str(user_id))

def clear_user_proc_msg(user_id):
    """Clear processing message for user session"""
    _PROC_MSG_CACHE.pop(str(user_id), None)

def copy_cookies_to_download_dir(user_id, download_dir):
    """Copy cookies from user root directory to download directory"""
    try:
        if not download_dir or not os.path.exists(download_dir):
            return False
            
        user_dir = os.path.join("users", str(user_id))
        cookie_file = os.path.join(user_dir, "cookie.txt")
        
        if os.path.exists(cookie_file):
            import shutil
            download_cookie_file = os.path.join(download_dir, "cookie.txt")
            shutil.copy2(cookie_file, download_cookie_file)
            logger.info(f"Copied cookies to download directory: {download_cookie_file}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to copy cookies to download directory: {e}")
        return False

def generate_download_dir_name(url):
    """Generate download directory name based on URL with minimal sanitization - only replace unsupported characters"""
    try:
        from urllib.parse import urlparse
        import re
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Start with domain
        dir_name = domain
        
        # Add path if exists and not just '/'
        if parsed.path and parsed.path != '/':
            path = parsed.path.strip('/')
            # Remove file extension if present
            path = re.sub(r'\.[a-zA-Z0-9]+$', '', path)
            if path:
                dir_name += f"_{path}"
        
        # Add query parameters if exist
        if parsed.query:
            # Add first few query parameters for all sites
            query_parts = parsed.query.split('&')[:3]
            for part in query_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    # Only replace truly problematic characters, keep most symbols
                    key = re.sub(r'[^\w\-_.]', '_', key)
                    value = re.sub(r'[^\w\-_.]', '_', value)
                    dir_name += f"_{key}_{value}"
        
        # Only replace characters that are truly problematic for filesystem
        # Keep letters, numbers, hyphens, underscores, dots
        dir_name = re.sub(r'[^\w\-_.]', '_', dir_name)
        
        # Clean up multiple underscores
        dir_name = re.sub(r'_+', '_', dir_name)
        dir_name = dir_name.strip('_')
        
        # Limit length to reasonable size
        if len(dir_name) > 150:
            # Keep domain and first part, truncate rest
            parts = dir_name.split('_')
            if len(parts) > 1:
                domain_part = parts[0]
                remaining = '_'.join(parts[1:])
                if len(remaining) > 100:
                    remaining = remaining[:100]
                dir_name = f"{domain_part}_{remaining}"
            else:
                dir_name = dir_name[:150]
        
        # Ensure we have something
        if not dir_name or dir_name == '_':
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            dir_name = f"{domain}_{url_hash}"
        
        return dir_name
    except Exception as e:
        logger.warning(f"Failed to generate download directory name: {e}")
        try:
            from urllib.parse import urlparse
            import hashlib
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            return f"{domain}_{url_hash}"
        except:
            return "unknown"

def set_filter(user_id, kind, value):
    f = get_filters(user_id)
    if kind == "codec":
        f["codec"] = value
    elif kind == "ext":
        f["ext"] = value
    elif kind == "audio_lang":
        f["audio_lang"] = value
    elif kind == "quality":
        f["quality"] = value
    elif kind == "toggle":
        f["visible"] = (value == "on")
    _ASK_FILTERS[str(user_id)] = f

def save_filters(user_id, state):
    """Persist current in-memory filters back to the session map."""
    _ASK_FILTERS[str(user_id)] = dict(state)

def _ask_cache_path(user_id):
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)
    return os.path.join(user_dir, _ASK_INFO_CACHE_FILE)

def _subs_langs_cache_path(user_id, url: str) -> str:
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)
    h = hashlib.sha1((url or "").encode("utf-8", errors="ignore")).hexdigest()[:16]
    return os.path.join(user_dir, f"{_ASK_SUBS_LANGS_PREFIX}{h}.json")

def save_subs_langs_cache(user_id: int, url: str, normal_langs, auto_langs) -> None:
    try:
        path = _subs_langs_cache_path(user_id, url)
        data = {
            "url": url,
            "normal": list(normal_langs or []),
            "auto": list(auto_langs or []),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

def load_subs_langs_cache(user_id: int, url: str):
    try:
        path = _subs_langs_cache_path(user_id, url)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("normal", []), data.get("auto", [])
    except Exception:
        return [], []
    return [], []

def delete_subs_langs_cache(user_id: int, url: str) -> None:
    try:
        path = _subs_langs_cache_path(user_id, url)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def save_ask_info(user_id, url, info, download_dir=None):
    try:
        # Use stored download directory if not provided
        if download_dir is None:
            download_dir = get_user_download_dir(user_id)
        
        # Create ask_formats.json directly in download directory if available
        if download_dir and os.path.exists(download_dir):
            download_ask_file = os.path.join(download_dir, _ASK_INFO_CACHE_FILE)
            data = {}
            if os.path.exists(download_ask_file):
                with open(download_ask_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[url] = {
                "title": info.get("title"),
                "id": info.get("id"),
                "formats": info.get("formats", [])
            }
            with open(download_ask_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Created ask_formats.json in download directory: {download_ask_file}")
        else:
            # Fallback to user root directory if download directory not available
            path = _ask_cache_path(user_id)
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[url] = {
                "title": info.get("title"),
                "id": info.get("id"),
                "formats": info.get("formats", [])
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Created ask_formats.json in user directory: {path}")
    except Exception as e:
        logger.warning(f"Failed to save ask_formats.json: {e}")

def load_ask_info(user_id, url):
    try:
        # First try to find ask_formats.json in download directory
        download_dir = get_user_download_dir(user_id)
        if download_dir and os.path.exists(download_dir):
            download_cache_file = os.path.join(download_dir, _ASK_INFO_CACHE_FILE)
            if os.path.exists(download_cache_file):
                with open(download_cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Using ask_formats.json from download directory: {download_cache_file}")
                return data.get(url)
        
        # Fallback to user root directory
        path = _ask_cache_path(user_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Using ask_formats.json from user directory: {path}")
            return data.get(url)
    except Exception as e:
        logger.warning(f"Failed to load ask_formats.json: {e}")
        return None
    return None

# --- DUBS flag resolver (robust) ---
_DUBS_FLAG_OVERRIDES = {
    'de': '🇩🇪',
    'fr': '🇫🇷',
    'es': '🇪🇸',
    'it': '🇮🇹',
    'en': '🇬🇧',
    'pt': '🇵🇹',
}

def _dub_flag(lang_code: str) -> str:
    try:
        base = (lang_code or '').split('-', 1)[0].lower()
        if base in _DUBS_FLAG_OVERRIDES:
            return _DUBS_FLAG_OVERRIDES[base]
        # fallback to generic resolver by first part
        return get_flag(lang_code, use_second_part=False)
    except Exception:
        return '🌐'

@app.on_callback_query(filters.regex(r"^askf\|"))
def ask_filter_callback(app, callback_query):
    messages = safe_get_messages(callback_query.from_user.id)
    logger.info(LoggerMsg.ALWAYS_ASK_CALLBACK_RECEIVED_LOG_MSG.format(callback_data=callback_query.data))
    parts = callback_query.data.split("|")
    if len(parts) >= 3:
        _, kind, value = parts[:3]
        callback_envelope = build_telegram_callback_envelope(callback_query)
        filter_request = build_ask_filter_selection_request(
            callback_envelope,
            filter_kind=kind,
            filter_value=value,
        )
        handle_ask_filter_selection_request(
            app,
            build_callback_execution_context(callback_query),
            filter_request,
        )


def ask_filter_callback_logic(app, execution_context, filter_request):
    callback_query = execution_context.callback_query
    if callback_query is None:
        raise ValueError("Ask filter callback logic requires callback execution context")
    messages = safe_get_messages(callback_query.from_user.id)
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = callback_query.from_user.id
    kind = filter_request.filter_kind
    value = filter_request.filter_value
    logger.info(LoggerMsg.ALWAYS_ASK_PARSED_LOG_MSG.format(kind=kind, value=value))
    source_context = _build_always_ask_source_context(execution_context)
    transition = _determine_ask_filter_transition(
        user_id,
        kind=kind,
        value=value,
        source_context=source_context,
    )

    # --- SUBS handlers must run BEFORE generic filter rebuild ---
    if kind == "subs" and value == "open":
        if transition.mode == "error":
            safe_callback_answer(callback_query, transition.answer_text, show_alert=transition.show_alert)
            return
        assert source_context is not None
        try:
            from COMMANDS.subtitles_cmd import get_or_compute_subs_langs
            normal, auto = get_or_compute_subs_langs(user_id, source_context.url)
            check_subs_availability(source_context.url, user_id, return_type=True)
        except Exception:
            normal, auto = load_subs_langs_cache(user_id, source_context.url)
        langs = sorted(set(normal) | set(auto))
        if not langs:
            safe_callback_answer(callback_query, safe_get_messages(user_id).NO_SUBTITLES_DETECTED_MSG, show_alert=True)
            return
        plan = _build_askf_subs_menu_plan(user_id, normal_langs=normal, auto_langs=auto, page=0)
        _emit_askf_subs_menu(callback_query, plan)
        return
    if kind == "subs_page":
        if transition.mode == "error":
            safe_callback_answer(callback_query, transition.answer_text, show_alert=transition.show_alert)
            return
        assert source_context is not None
        n_cached, a_cached = load_subs_langs_cache(user_id, source_context.url)
        if n_cached or a_cached:
            normal, auto = n_cached, a_cached
        else:
            normal = _subs_check_cache.get(f"{source_context.url}_{user_id}_normal_langs") or []
            auto = _subs_check_cache.get(f"{source_context.url}_{user_id}_auto_langs") or []
        plan = _build_askf_subs_menu_plan(
            user_id,
            normal_langs=normal,
            auto_langs=auto,
            page=transition.page or 0,
        )
        _emit_askf_subs_menu(callback_query, plan)
        return
    if kind == "subs" and value in ("back", "close"):
        if value == "back":
            _reopen_askf_quality_menu(app, callback_query, source_context)
            return
        _close_askf_subs_menu(app, callback_query, transition.answer_text)
        return
    if kind == "subs_lang":
        try:
            save_user_subs_language(user_id, value)
            save_user_subs_auto_mode(user_id, False)
        except Exception:
            pass
        _reopen_askf_quality_menu(app, callback_query, source_context)
        safe_callback_answer(callback_query, transition.answer_text)
        return
    if kind == "dubs" and value == "open":
        if transition.mode == "error":
            safe_callback_answer(callback_query, transition.answer_text, show_alert=transition.show_alert)
            return
        fstate = get_filters(user_id)
        langs = fstate.get("available_dubs", [])
        if not langs or len(langs) <= 1:
            safe_callback_answer(callback_query, safe_get_messages(user_id).NO_ALTERNATIVE_AUDIO_LANGUAGES_MSG, show_alert=True)
            return
        plan = _build_askf_dubs_menu_plan(user_id, langs)
        _emit_askf_dubs_menu(callback_query, plan)
        return
    if kind == "audio_lang":
        set_filter(user_id, kind, value)
        _reopen_askf_quality_menu(app, callback_query, source_context)
        safe_callback_answer(callback_query, transition.answer_text)
        return
    if kind == "dubs" and value in ("back", "close"):
        _reopen_askf_quality_menu(app, callback_query, source_context)
        safe_callback_answer(callback_query, transition.answer_text)
        return
    filter_update_plan = _determine_askf_filter_update_plan(
        user_id,
        kind=kind,
        value=value,
        source_context=source_context,
    )
    if filter_update_plan is not None:
        _execute_askf_filter_update_plan(
            app,
            callback_query,
            user_id,
            source_context,
            kind=kind,
            value=value,
            plan=filter_update_plan,
        )
        return
    if source_context is not None:
        _reopen_askf_quality_menu(app, callback_query, source_context)
        safe_callback_answer(callback_query, transition.answer_text)
        return
    safe_callback_answer(callback_query, transition.answer_text)

def get_available_formats_from_cache(user_id, url, download_dir=None):
    """Get available codecs and formats from ask_formats.json cache"""
    try:
        # First try to find ask_formats.json in download directory
        cache_file = None
        if download_dir and os.path.exists(download_dir):
            download_cache_file = os.path.join(download_dir, _ASK_INFO_CACHE_FILE)
            if os.path.exists(download_cache_file):
                cache_file = download_cache_file
                logger.info(f"Using ask_formats.json from download directory: {download_cache_file}")
        
        # Fallback to user root directory
        if not cache_file:
            user_dir = os.path.join("users", str(user_id))
            cache_file = os.path.join(user_dir, _ASK_INFO_CACHE_FILE)
            if os.path.exists(cache_file):
                logger.info(f"Using ask_formats.json from user directory: {cache_file}")
        
        if not cache_file or not os.path.exists(cache_file):
            return {"codecs": set(), "formats": set()}
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        available_codecs = set()
        available_formats = set()
        
        # Check if this URL matches the cached data
        if data.get('url') == url:
            formats = data.get('formats', [])
            
            for format_line in formats:
                # Extract codecs and formats using our existing function
                extracted = extract_button_data(format_line)
                
                for item in extracted:
                    # Check for codecs
                    if item.lower() in ['avc1', 'avc', 'h264']:
                        available_codecs.add('avc1')
                    elif item.lower() in ['av1', 'av01']:
                        available_codecs.add('av01')
                    elif item.lower() in ['vp9', 'vp09']:
                        available_codecs.add('vp9')
                    
                    # Check for formats
                    if item.lower() in ['mp4']:
                        available_formats.add('mp4')
                    elif item.lower() in ['mkv', 'webm', 'avi', 'mov', 'flv', 'wmv', '3gp', 'ogv', 'ts', 'mts', 'm2ts']:
                        # These formats can be converted to MKV by ffmpeg
                        available_formats.add('mkv')
        
        return {"codecs": available_codecs, "formats": available_formats}
    except Exception as e:
        logger.warning(f"{LoggerMsg.ALWAYS_ASK_ERROR_READING_AVAILABLE_FORMATS_FROM_CACHE_LOG_MSG}: {e}")
        return {"codecs": set(), "formats": set()}

def filter_qualities_by_codec_format(user_id, url, qualities, download_dir=None):
    """Filter qualities based on selected codec and format"""
    try:
        # Get current filters
        f = get_filters(user_id)
        selected_codec = f.get("codec", "avc1")
        selected_format = f.get("ext", "mp4")
        
        # Get available formats from cache
        user_download_dir = get_user_download_dir(user_id) if download_dir is None else download_dir
        available_formats = get_available_formats_from_cache(user_id, url, user_download_dir)
        
        # If no cache or no specific formats available, return all qualities
        if not available_formats["codecs"] and not available_formats["formats"]:
            return qualities
        
        # Get all format lines from cache
        user_dir = os.path.join("users", str(user_id))
        cache_file = os.path.join(user_dir, _ASK_INFO_CACHE_FILE)
        
        if not os.path.exists(cache_file):
            return qualities
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if data.get('url') != url:
            return qualities
        
        formats = data.get('formats', [])
        filtered_qualities = set()
        
        for format_line in formats:
            extracted = extract_button_data(format_line)
            
            # Check if this format matches selected codec and format
            has_codec = False
            has_format = False
            
            for item in extracted:
                # Check codec
                if selected_codec == 'avc1' and item.lower() in ['avc1', 'avc', 'h264']:
                    has_codec = True
                elif selected_codec == 'av01' and item.lower() in ['av1', 'av01']:
                    has_codec = True
                elif selected_codec == 'vp9' and item.lower() in ['vp9', 'vp09']:
                    has_codec = True
                
                # Check format
                if selected_format == 'mp4' and item.lower() == 'mp4':
                    has_format = True
                elif selected_format == 'mkv' and item.lower() in ['mkv', 'webm', 'avi', 'mov', 'flv', 'wmv', '3gp', 'ogv', 'ts', 'mts', 'm2ts']:
                    has_format = True
            
            # If both codec and format match, extract quality
            if has_codec and has_format:
                for item in extracted:
                    # Look for quality patterns (e.g., 720p, 1080p)
                    if 'p' in item and any(char.isdigit() for char in item):
                        quality_match = re.search(r'(\d+p\d*)', item)
                        if quality_match:
                            filtered_qualities.add(quality_match.group(1))
        
        # Return intersection of available qualities and filtered qualities
        if filtered_qualities:
            return [q for q in qualities if q in filtered_qualities]
        else:
            return qualities
            
    except Exception as e:
        logger.warning(f"{LoggerMsg.ALWAYS_ASK_ERROR_FILTERING_QUALITIES_LOG_MSG}: {e}")
        return qualities

def get_link_mode(user_id):
    """
    Get the user's LINK mode state.
    """
    try:
        user_dir = os.path.join("users", str(user_id))
        link_mode_file = os.path.join(user_dir, "link_mode.txt")
        if os.path.exists(link_mode_file):
            with open(link_mode_file, 'r') as f:
                return f.read().strip() == "enabled"
        return False
    except Exception:
        return False

def set_link_mode(user_id, enabled):
    """
    Set the user's LINK mode state.
    """
    try:
        user_dir = os.path.join("users", str(user_id))
        create_directory(user_dir)
        link_mode_file = os.path.join(user_dir, "link_mode.txt")
        with open(link_mode_file, 'w') as f:
            f.write("enabled" if enabled else "disabled")
        return True
    except Exception as e:
        logger.error(f"{LoggerMsg.ALWAYS_ASK_ERROR_SETTING_LINK_MODE_LOG_MSG} {user_id}: {e}")
        return False

def build_filter_rows(user_id, url=None, is_private_chat=False, download_dir=None):
    messages = safe_get_messages(user_id)
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    f = get_filters(user_id)
    codec = f.get("codec", "avc1")
    ext = f.get("ext", "mp4")
    visible = bool(f.get("visible", False))
    audio_lang = f.get("audio_lang")
    has_dubs = bool(f.get("has_dubs"))
    
    # Check if user has fixed container format via /args
    user_fixed_format = None
    try:
        user_args = get_user_args(user_id)
        user_video_format = user_args.get('video_format', 'mp4')
        user_merge_format = user_args.get('merge_output_format', 'mp4')
        
        # If user has set video_format to something other than mp4, it's fixed
        if user_video_format != 'mp4':
            user_fixed_format = user_video_format
        # If user has set merge_output_format to something other than mp4, it's fixed
        elif user_merge_format != 'mp4':
            user_fixed_format = user_merge_format
    except Exception:
        pass
    
    # Get available formats from cache if URL is provided
    available_formats = {"codecs": set(), "formats": set()}
    if url:
        user_download_dir = get_user_download_dir(user_id) if download_dir is None else download_dir
        available_formats = get_available_formats_from_cache(user_id, url, user_download_dir)
    
    # When filters are hidden – show compact row with CODEC + audio (+ optional DUBS, SUBS)
    if not visible:
        # Determine NSFW for star icon on MP3
        is_nsfw = False
        if url:
            try:
                info = load_ask_info(user_id, url) or {}
                tags_text = ' '.join(generate_final_tags(url, [], info)) if isinstance(generate_final_tags(url, [], info), list) else generate_final_tags(url, [], info)
                is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
            except Exception:
                is_nsfw = False
        # Get user's audio format setting and check send_as_file
        try:
            user_args = get_user_args(user_id)
            audio_format = user_args.get('audio_format', 'mp3').upper()
            send_as_file = user_args.get('send_as_file', False)
        except Exception:
            audio_format = 'MP3'
            send_as_file = False
        
        # Determine MP3 cache status for rocket icon (skip if send_as_file is enabled)
        is_cached_mp3 = False
        if url and not send_as_file:
            try:
                cq = get_cached_qualities(url)
                is_cached_mp3 = ('mp3' in cq)
            except Exception:
                is_cached_mp3 = False
        
        mp3_label = (
            f"1⭐️{audio_format}" if (is_nsfw and is_private_chat)
            else (f"🚀{audio_format}" if is_cached_mp3 else f"🎧{audio_format}")
        )
        
        # Create dynamic layout based on available buttons
        buttons = [InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_CODEC_BUTTON_MSG, callback_data="askf|toggle|on"), InlineKeyboardButton(mp3_label, callback_data="askq|mp3")]
        
        # Show DUBS button only if audio dubs are detected for this video (set elsewhere)
        if has_dubs:
            buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_DUBS_BUTTON_MSG, callback_data="askf|dubs|open"))
        
        # Show SUBS button if Always Ask is enabled for this user
        try:
            if is_subs_always_ask(user_id):
                buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_SUBS_BUTTON_MSG, callback_data="askf|subs|open"))
        except Exception:
            pass
        
        # Dynamic layout: 2 or 4 buttons = 2 per row, 3 buttons = all in one row
        if len(buttons) == 2 or len(buttons) == 4:
            # Split into 2 rows of 2 buttons each
            first_row = buttons[:2]
            second_row = buttons[2:] if len(buttons) > 2 else []
            return [first_row, second_row] if second_row else [first_row], []
        elif len(buttons) == 3:
            # All 3 buttons in one row
            return [buttons], []
        else:
            # Fallback: single row
            return [buttons], []
    
    # Build codec buttons with availability check
    avc1_available = 'avc1' in available_formats["codecs"] or not available_formats["codecs"]  # Show if available or if no cache
    av01_available = 'av01' in available_formats["codecs"] or not available_formats["codecs"]
    vp9_available = 'vp9' in available_formats["codecs"] or not available_formats["codecs"]
    
    avc1_btn = (safe_get_messages(user_id).AA_AVC_BUTTON_MSG if codec == "avc1" else safe_get_messages(user_id).AA_AVC_BUTTON_INACTIVE_MSG) if avc1_available else safe_get_messages(user_id).AA_AVC_BUTTON_UNAVAILABLE_MSG
    av01_btn = (safe_get_messages(user_id).AA_AV1_BUTTON_MSG if codec == "av01" else safe_get_messages(user_id).AA_AV1_BUTTON_INACTIVE_MSG) if av01_available else safe_get_messages(user_id).AA_AV1_BUTTON_UNAVAILABLE_MSG
    vp9_btn = (safe_get_messages(user_id).AA_VP9_BUTTON_MSG if codec == "vp9" else safe_get_messages(user_id).AA_VP9_BUTTON_INACTIVE_MSG) if vp9_available else safe_get_messages(user_id).AA_VP9_BUTTON_UNAVAILABLE_MSG
    
    # Build format buttons with availability check
    # If user has fixed format via /args, don't show container buttons
    if user_fixed_format:
        # Show fixed format as read-only
        fixed_format_btn = f"🔒 {user_fixed_format.upper()}"
        mp4_btn = fixed_format_btn
        mkv_btn = None  # Don't show MKV button
    else:
        mp4_available = 'mp4' in available_formats["formats"] or not available_formats["formats"]
        mkv_available = 'mkv' in available_formats["formats"] or not available_formats["formats"]
        
        mp4_btn = (safe_get_messages(user_id).AA_MP4_BUTTON_MSG if ext == "mp4" else safe_get_messages(user_id).AA_MP4_BUTTON_INACTIVE_MSG) if mp4_available else safe_get_messages(user_id).AA_MP4_BUTTON_UNAVAILABLE_MSG
        mkv_btn = (safe_get_messages(user_id).AA_MKV_BUTTON_MSG if ext == "mkv" else safe_get_messages(user_id).AA_MKV_BUTTON_INACTIVE_MSG) if mkv_available else safe_get_messages(user_id).AA_MKV_BUTTON_UNAVAILABLE_MSG
    
    # NSFW detection for expanded filters
    is_nsfw = False
    if url:
        try:
            info = load_ask_info(user_id, url) or {}
            tags_text = ' '.join(generate_final_tags(url, [], info)) if isinstance(generate_final_tags(url, [], info), list) else generate_final_tags(url, [], info)
            is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
        except Exception:
            is_nsfw = False
    # Get user's audio format setting and check send_as_file
    try:
        user_args = get_user_args(user_id)
        audio_format = user_args.get('audio_format', 'mp3').upper()
        send_as_file = user_args.get('send_as_file', False)
    except Exception:
        audio_format = 'MP3'
        send_as_file = False
    
    # Determine MP3 cache status for rocket icon (skip if send_as_file is enabled)
    is_cached_mp3 = False
    if url and not send_as_file:
        try:
            cq = get_cached_qualities(url)
            is_cached_mp3 = ('mp3' in cq)
        except Exception:
            is_cached_mp3 = False
    
    mp3_label = (
        f"1⭐️{audio_format}" if (is_nsfw and is_private_chat)
        else (f"🚀{audio_format}" if is_cached_mp3 else f"🎧{audio_format}")
    )
    # Build rows based on whether format is fixed
    rows = [
        [InlineKeyboardButton(avc1_btn, callback_data="askf|codec|avc1"), InlineKeyboardButton(av01_btn, callback_data="askf|codec|av01"), InlineKeyboardButton(vp9_btn, callback_data="askf|codec|vp9")]
    ]
    
    # Add format row - only show container buttons if not fixed via /args
    if user_fixed_format:
        # Show fixed format as non-clickable
        format_row = [InlineKeyboardButton(mp4_btn, callback_data="askf|empty"), InlineKeyboardButton(mp3_label, callback_data="askq|mp3")]
    else:
        # Show normal container selection
        format_row = [
            InlineKeyboardButton(str(mp4_btn), callback_data="askf|ext|mp4"),
            InlineKeyboardButton(str(mkv_btn), callback_data="askf|ext|mkv"),
            InlineKeyboardButton(str(mp3_label), callback_data="askq|mp3"),
        ]
    
    rows.append(format_row)
    action_buttons = []
    if has_dubs:
        action_buttons.append(InlineKeyboardButton("🗣 DUBS", callback_data="askf|dubs|open"))
    try:
        if is_subs_always_ask(user_id):
            action_buttons.append(InlineKeyboardButton("💬 SUBS", callback_data="askf|subs|open"))
    except Exception:
        pass
    
    return rows, action_buttons

@app.on_callback_query(filters.regex(r"^askq\|"))
# @reply_with_keyboard
def askq_callback(app, callback_query):
    messages = safe_get_messages(callback_query.from_user.id)
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    logger.info(f"{LoggerMsg.ALWAYS_ASK_CALLBACK_LOG_MSG}: {callback_query.data}")
    user_id = callback_query.from_user.id
    callback_message = getattr(callback_query, "message", None)
    execution_context = build_callback_execution_context(callback_query)
    source_context = _build_always_ask_source_context(execution_context)

    def _delete_callback_message():
        if callback_message and getattr(callback_message, "chat", None) and getattr(callback_message, "id", None):
            safe_delete_messages(chat_id=callback_message.chat.id, message_ids=[callback_message.id])

    # Parse callback data correctly - handle both old and new formats
    parts = callback_query.data.split("|")
    if len(parts) >= 4 and parts[1] == "f":
        filter_request = build_ask_filter_selection_request(
            build_telegram_callback_envelope(callback_query),
            filter_kind=parts[2],
            filter_value=parts[3],
        )
        handle_ask_filter_selection_request(
            app,
            execution_context,
            filter_request,
        )
        return
    if len(parts) >= 3 and parts[1] == "other_id":
        selection_token = f"other_id_{parts[2]}"  # Reconstruct other_id_XXX format
    else:
        selection_token = parts[1] if len(parts) > 1 else ""
    callback_envelope = build_telegram_callback_envelope(callback_query)
    selection_request = build_ask_quality_selection_request(
        callback_envelope,
        selection_token=selection_token,
    )
    data = selection_request.selection_token
    found_type = None
    
    logger.info(f"Processing callback data: '{data}' for user {user_id}")
    
    # Get processing message from cache (created in ask_quality_menu)
    proc_msg = get_user_proc_msg(user_id)
    if data == "close":
        close_plan = _build_askq_close_plan(user_id)
        _execute_askq_close_plan(app, callback_query, close_plan)
        return
    special_action_plan = _determine_askq_special_action_plan(
        user_id,
        data=data,
        source_context=source_context,
    )
    if special_action_plan is not None:
        if special_action_plan.answer_text:
            safe_callback_answer(
                callback_query,
                special_action_plan.answer_text,
                show_alert=special_action_plan.show_alert,
            )
        if special_action_plan.mode == "error":
            return
        if special_action_plan.mode == "link":
            assert source_context is not None
            _execute_askq_link_action(app, callback_query, user_id, source_context)
            return
        if special_action_plan.mode == "list":
            assert source_context is not None
            _execute_askq_list_action(app, callback_query, user_id, source_context)
            return
        if special_action_plan.mode == "image":
            assert source_context is not None
            _execute_askq_image_action(app, callback_query, user_id, source_context)
            return
        if special_action_plan.mode == "quick_embed":
            assert source_context is not None
            _execute_askq_quick_embed_action(app, callback_query, user_id, source_context)
            return
    
    # Handle manual quality selection menu
    if data == "try_manual":
        show_manual_quality_menu(app, callback_query)
        return
    
    # Handle other qualities menu
    if data == "other_qualities":
        show_other_qualities_menu(app, callback_query)
        return

    navigation_plan = _determine_askq_navigation_plan(
        user_id,
        data=data,
        callback_query=callback_query,
        source_context=source_context,
    )
    if navigation_plan is not None:
        _execute_askq_navigation_plan(
            app,
            callback_query,
            user_id,
            source_context,
            navigation_plan,
        )
        return
    
    other_format_plan = _determine_other_format_selection_plan(
        user_id,
        data=data,
        source_context=source_context,
    )
    if other_format_plan is not None:
        if other_format_plan.answer_text:
            safe_callback_answer(
                callback_query,
                other_format_plan.answer_text,
                show_alert=other_format_plan.show_alert,
            )
        if other_format_plan.mode == "error":
            return
        _execute_askq_other_format_selection(
            app,
            callback_query,
            user_id,
            source_context,
            other_format_plan,
        )
        return

    manual_quality_plan = _determine_manual_quality_selection_plan(
        user_id,
        data=data,
        source_context=source_context,
    )
    if manual_quality_plan is not None:
        if manual_quality_plan.answer_text:
            safe_callback_answer(
                callback_query,
                manual_quality_plan.answer_text,
                show_alert=manual_quality_plan.show_alert,
            )
        if manual_quality_plan.mode == "error":
            _delete_callback_message()
            return
        _execute_askq_manual_quality_selection(
            app,
            callback_query,
            user_id,
            source_context,
            manual_quality_plan,
            proc_msg=proc_msg,
        )
        return

    if source_context is None:
        safe_callback_answer(callback_query, safe_get_messages(user_id).ALWAYS_ASK_ERROR_ORIGINAL_MESSAGE_NOT_FOUND_DETAILED_MSG, show_alert=True)
        _delete_callback_message()
        return

    original_message = source_context.original_message
    url = source_context.url
    if not url:
        safe_callback_answer(callback_query, safe_get_messages(user_id).ALWAYS_ASK_ERROR_ORIGINAL_URL_NOT_FOUND_MSG, show_alert=True)
        _delete_callback_message()
        return

    # We extract tags from the initial message of the user
    original_text = source_context.url_text
    _, _, _, _, tags, tags_text, _ = extract_url_range_tags(original_text)

    _delete_callback_message()

    original_text = getattr(original_message, "text", None) or getattr(original_message, "caption", None) or ""
    if is_playlist_with_range(original_text):
        logger.info(f"{LoggerMsg.ALWAYS_ASK_PLAYLIST_WITH_RANGE_DETECTED_LOG_MSG}: {url}")
        _, video_start_with, video_end_with, playlist_name, _, _, tag_error = extract_url_range_tags(original_text)
        # Correct video_count calculation for negative indices
        if video_start_with < 0 and video_end_with < 0:
            video_count = abs(video_end_with) - abs(video_start_with) + 1
        elif video_start_with > video_end_with:
            video_count = abs(video_start_with - video_end_with) + 1
        else:
            video_count = video_end_with - video_start_with + 1
        
        # Build the list of indices, taking negative indices into account
        # For negative indices, convert them to positive after we know total video count
        has_negative_indices = video_start_with < 0 or video_end_with < 0
        if has_negative_indices:
            # For negative indices, build a list with negative values first
            if abs(video_start_with) < abs(video_end_with):
                # -1..-7: build [-1, -2, -3, -4, -5, -6, -7]
                requested_indices = list(range(video_start_with, video_end_with - 1, -1))
            else:
                # -7..-1: build [-7, -6, -5, -4, -3, -2, -1]
                requested_indices = list(range(video_start_with, video_end_with + 1, 1))
        elif video_start_with > video_end_with:
            # Reverse order: from start to end inclusive, reversed
            requested_indices = list(range(video_start_with, video_end_with - 1, -1))
        else:
            # Forward order: from start to end inclusive
            requested_indices = list(range(video_start_with, video_start_with + video_count))
        
        # If there are negative indices, we must get total video count and convert them
        if has_negative_indices:
            try:
                from DOWN_AND_UP.yt_dlp_hook import get_video_formats
                logger.info(f"Getting total playlist count for negative indices conversion (always_ask)...")
                temp_info = get_video_formats(url, user_id, 1, True, False, 1)
                if temp_info and isinstance(temp_info, dict):
                    if "entries" in temp_info:
                        total_playlist_count = len(temp_info["entries"])
                    elif "_playlist_entries" in temp_info:
                        total_playlist_count = len(temp_info["_playlist_entries"])
                    else:
                        total_playlist_count = None
                    
                    if total_playlist_count:
                        logger.info(f"Total playlist count (always_ask): {total_playlist_count}")
                        # Convert negative indices to positive
                        converted_indices = []
                        for neg_idx in requested_indices:
                            if neg_idx < 0:
                                pos_idx = total_playlist_count + neg_idx + 1
                                converted_indices.append(pos_idx)
                            else:
                                converted_indices.append(neg_idx)
                        # Sort in reverse order to download from last to first
                        converted_indices.sort(reverse=True)
                        requested_indices = converted_indices
                        logger.info(f"Converted negative indices to positive (always_ask): {converted_indices}")
            except Exception as e:
                logger.warning(f"Failed to get total playlist count for negative indices (always_ask): {e}, using original indices")
        
        # Check if Always Ask mode is enabled - if yes, skip cache completely
        # Also check if send_as_file is enabled - if so, skip cache completely
        user_args = get_user_args(user_id)
        send_as_file = user_args.get("send_as_file", False)
        
        if not is_subs_always_ask(user_id) and not send_as_file:
            # Check cache for selected quality
            cached_videos = get_cached_playlist_videos(get_clean_playlist_url(url), data, requested_indices)
            uncached_indices = [i for i in requested_indices if i not in cached_videos]
            used_quality_key = data
            
            # If there is no cache for the selected quality, try fallback to best
            if not cached_videos and data != "best":
                logger.info(f"{LoggerMsg.ALWAYS_ASK_NO_CACHE_FOR_QUALITY_KEY_LOG_MSG}={data}, trying fallback to best")
                best_cached = get_cached_playlist_videos(get_clean_playlist_url(url), "best", requested_indices)
                if best_cached:
                    cached_videos = best_cached
                    used_quality_key = "best"
                    uncached_indices = [i for i in requested_indices if i not in cached_videos]
                    logger.info(f"{LoggerMsg.ALWAYS_ASK_FOUND_CACHE_WITH_BEST_QUALITY_LOG_MSG}: {list(cached_videos.keys())}, uncached: {uncached_indices}")
        else:
            logger.info(f"{LoggerMsg.ALWAYS_ASK_SKIPPING_CACHE_CHECK_FOR_PLAYLIST_LOG_MSG}: url={url}, quality={data}")
            cached_videos = {}
            uncached_indices = requested_indices
            used_quality_key = data
        
        if cached_videos:
            # Reposting cached videos
            callback_query.answer("🚀 Found in cache! Reposting...", show_alert=False)
            try:
                target_chat_id = getattr(original_message.chat, 'id', user_id)
            except Exception:
                target_chat_id = user_id
            for index in requested_indices:
                if index in cached_videos:
                    try:
                        thread_id = getattr(original_message, 'message_thread_id', None)
                        # Use forward everywhere; in groups try to keep topic via message_thread_id
                        if thread_id:
                            from HELPERS.logger import get_log_channel
                            from HELPERS.porn import is_porn
                            # Determine the correct log channel based on content type
                            is_nsfw = is_porn(url, "", "", None)
                            is_private_chat = getattr(original_message.chat, "type", None) == enums.ChatType.PRIVATE
                            is_paid = is_nsfw and is_private_chat
                            logger.info(f"{LoggerMsg.ALWAYS_ASK_URL_ANALYSIS_LOG_MSG}: url={url}, is_nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}")
                            
                            # Get the correct log channel for reposting
                            if is_paid:
                                from_chat_id = get_log_channel("video", paid=True)
                                channel_type = "PAID"
                            elif is_nsfw:
                                from_chat_id = get_log_channel("video", nsfw=True)
                                channel_type = "NSFW"
                            else:
                                from_chat_id = get_log_channel("video")
                                channel_type = "regular"
                            
                            logger.info(f"[VIDEO CACHE] Channel selection: nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}, channel_type={channel_type}, from_chat_id={from_chat_id}")
                            
                            # Verify we're reposting from a valid log channel
                            valid_channels = [
                                get_log_channel("video"),
                                get_log_channel("video", nsfw=True),
                                get_log_channel("video", paid=True)
                            ]
                            if from_chat_id not in valid_channels:
                                logger.error(f"CRITICAL: Attempting to repost from wrong channel {from_chat_id}")
                                continue
                                
                            logger.info(f"[VIDEO CACHE] Reposting video {index} from channel {from_chat_id} to user {target_chat_id}, message_id={cached_videos[index]}")
                            app.forward_messages(
                                chat_id=target_chat_id,
                                from_chat_id=from_chat_id,
                                message_ids=[cached_videos[index]],
                                message_thread_id=thread_id
                            )
                        else:
                            from HELPERS.logger import get_log_channel
                            from HELPERS.porn import is_porn
                            # Determine the correct log channel based on content type
                            is_nsfw = is_porn(url, "", "", None)
                            is_private_chat = getattr(original_message.chat, "type", None) == enums.ChatType.PRIVATE
                            is_paid = is_nsfw and is_private_chat
                            logger.info(f"{LoggerMsg.ALWAYS_ASK_URL_ANALYSIS_LOG_MSG}: url={url}, is_nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}")
                            
                            # Get the correct log channel for reposting
                            if is_paid:
                                from_chat_id = get_log_channel("video", paid=True)
                                channel_type = "PAID"
                            elif is_nsfw:
                                from_chat_id = get_log_channel("video", nsfw=True)
                                channel_type = "NSFW"
                            else:
                                from_chat_id = get_log_channel("video")
                                channel_type = "regular"
                            
                            logger.info(f"[VIDEO CACHE] Channel selection: nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}, channel_type={channel_type}, from_chat_id={from_chat_id}")
                            
                            # Verify we're reposting from a valid log channel
                            valid_channels = [
                                get_log_channel("video"),
                                get_log_channel("video", nsfw=True),
                                get_log_channel("video", paid=True)
                            ]
                            if from_chat_id not in valid_channels:
                                logger.error(f"CRITICAL: Attempting to repost from wrong channel {from_chat_id}")
                                continue
                                
                            logger.info(f"[VIDEO CACHE] Reposting video {index} from channel {from_chat_id} to user {target_chat_id}, message_id={cached_videos[index]}")
                            forward_kwargs = {
                                'chat_id': target_chat_id,
                                'from_chat_id': from_chat_id,
                                'message_ids': [cached_videos[index]]
                            }
                            # Only apply thread_id in groups/channels, not in private chats
                            if getattr(original_message.chat, "type", None) != enums.ChatType.PRIVATE and thread_id:
                                forward_kwargs['message_thread_id'] = thread_id
                            app.forward_messages(**forward_kwargs)
                    except Exception as e:
                        logger.warning(f"askq_callback: cached video for index {index} not found: {e}")
            
            # If there are missing videos - download them
            if uncached_indices:
                logger.info(f"askq_callback: we start downloading the missing indexes: {uncached_indices}")
                new_start = uncached_indices[0]
                new_end = uncached_indices[-1]
                new_count = new_end - new_start + 1
                
                if data == "mp3":
                    branch_result = _select_callback_download_branch(
                        user_id,
                        callback_data=data,
                        quality_intent=used_quality_key,
                        quality_key=used_quality_key,
                        format_override="ba",
                        video_count=new_count,
                        origin="playlist_cache_miss_callback",
                        provenance={"callback_data": data, "cache_miss_only": True},
                    )
                    task = _make_callback_runtime_task(
                        original_message,
                        url=url,
                        tags=tags,
                        tags_text=tags_text,
                        branch_result=branch_result,
                        playlist_name=playlist_name,
                        video_count=new_count,
                        video_start_with=new_start,
                        proc_msg=proc_msg,
                    )
                    _dispatch_callback_download_branch(
                        app,
                        original_message,
                        task,
                        proc_msg=proc_msg,
                    )
                else:
                    try:
                        # Form the correct format for the missing videos
                        if used_quality_key == "best":
                            format_override = "bv*[vcodec*=avc1]+ba[acodec*=mp4a]/bv*[vcodec*=avc1]+ba/best/bv+ba/best"
                        else:
                            quality_str = used_quality_key.replace('p', '')
                            quality_val = int(quality_str)
                            if quality_val and quality_val >= 4320:
                                prev = 2160
                            elif quality_val and quality_val >= 2160:
                                prev = 1440
                            elif quality_val and quality_val >= 1440:
                                prev = 1080
                            elif quality_val and quality_val >= 1080:
                                prev = 720
                            elif quality_val and quality_val >= 720:
                                prev = 480
                            elif quality_val and quality_val >= 480:
                                prev = 360
                            elif quality_val and quality_val >= 360:
                                prev = 240
                            elif quality_val and quality_val >= 240:
                                prev = 144
                            else:
                                prev = 0
                            format_override = f"bv*[vcodec*=avc1][height<={quality_val}][height>{prev}]+ba[acodec*=mp4a]/bv*[vcodec*=avc1][height<={quality_val}]+ba[acodec*=mp4a]/bv*[vcodec*=avc1]+ba/best/bv+ba/best"
                    except Exception as e:
                        logger.error(f"askq_callback: error forming format: {e}")
                        format_override = "bestvideo+bestaudio/best/bv+ba/best"
                    
                    branch_result = _select_callback_download_branch(
                        user_id,
                        callback_data=data,
                        quality_intent=used_quality_key,
                        quality_key=used_quality_key,
                        format_override=format_override,
                        video_count=new_count,
                        origin="playlist_cache_miss_callback",
                        provenance={"callback_data": data, "cache_miss_only": True},
                        force_branch_family="video",
                    )
                    task = _make_callback_runtime_task(
                        original_message,
                        url=url,
                        tags=tags,
                        tags_text=tags_text,
                        branch_result=branch_result,
                        playlist_name=playlist_name,
                        video_count=new_count,
                        video_start_with=new_start,
                        proc_msg=proc_msg,
                    )
                    _dispatch_callback_download_branch(
                        app,
                        original_message,
                        task,
                        proc_msg=proc_msg,
                        clear_subs_cache_on_start=False,
                    )
            else:
                # All videos were in the cache
                app.send_message(target_chat_id, safe_get_messages(user_id).PLAYLIST_CACHE_SENT_MSG.format(cached=len(cached_videos), total=len(requested_indices)), reply_parameters=ReplyParameters(message_id=original_message.id))
                media_type = safe_get_messages(user_id).ALWAYS_ASK_AUDIO_TYPE_MSG if data == "mp3" else safe_get_messages(user_id).ALWAYS_ASK_VIDEO_TYPE_MSG
                log_msg = f"{media_type} playlist sent from cache to user.\nURL: {url}\nUser: {callback_query.from_user.first_name} ({user_id})"
                send_to_logger(original_message, log_msg)
            return
        else:
            # If there is no cache at all - download everything again
            logger.info(f"askq_callback: no cache found for any quality, starting new download")
            if data == "mp3":
                branch_result = _select_callback_download_branch(
                    user_id,
                    callback_data=data,
                    quality_intent=data,
                    quality_key=data,
                    format_override="ba",
                    video_count=video_count,
                    origin="playlist_uncached_callback",
                    provenance={"callback_data": data},
                )
                task = _make_callback_runtime_task(
                    original_message,
                    url=url,
                    tags=tags,
                    tags_text=tags_text,
                    branch_result=branch_result,
                    playlist_name=playlist_name,
                    video_count=video_count,
                    video_start_with=video_start_with,
                    proc_msg=proc_msg,
                )
                _dispatch_callback_download_branch(
                    app,
                    original_message,
                    task,
                    proc_msg=proc_msg,
                )
            else:
                try:
                    # Form the correct format for the new download
                    if data == "best":
                        format_override = "bv*[vcodec*=avc1]+ba[acodec*=mp4a]/bv*[vcodec*=avc1]+ba/best/bv+ba/best"
                    else:
                        quality_str = data.replace('p', '')
                        quality_val = int(quality_str)
                        if quality_val and quality_val >= 4320:
                            prev = 2160
                        elif quality_val and quality_val >= 2160:
                            prev = 1440
                        elif quality_val and quality_val >= 1440:
                            prev = 1080
                        elif quality_val and quality_val >= 1080:
                            prev = 720
                        elif quality_val and quality_val >= 720:
                            prev = 480
                        elif quality_val and quality_val >= 480:
                            prev = 360
                        elif quality_val and quality_val >= 360:
                            prev = 240
                        elif quality_val and quality_val >= 240:
                            prev = 144
                        else:
                            prev = 0
                        format_override = f"bv*[vcodec*=avc1][height<={quality_val}][height>{prev}]+ba[acodec*=mp4a]/bv*[vcodec*=avc1][height<={quality_val}]+ba[acodec*=mp4a]/bv*[vcodec*=avc1]+ba/best/bv+ba/best"
                except ValueError:
                    format_override = "bestvideo+bestaudio/best/bv+ba/best"
                
                # Save selected quality to filters
                set_filter(user_id, "quality", data)
                
                branch_result = _select_callback_download_branch(
                    user_id,
                    callback_data=data,
                    quality_intent=data,
                    quality_key=data,
                    format_override=format_override,
                    video_count=video_count,
                    origin="playlist_uncached_callback",
                    provenance={"callback_data": data},
                    force_branch_family="video",
                )
                task = _make_callback_runtime_task(
                    original_message,
                    url=url,
                    tags=tags,
                    tags_text=tags_text,
                    branch_result=branch_result,
                    playlist_name=playlist_name,
                    video_count=video_count,
                    video_start_with=video_start_with,
                    proc_msg=proc_msg,
                )
                _dispatch_callback_download_branch(
                    app,
                    original_message,
                    task,
                    proc_msg=proc_msg,
                    clear_subs_cache_on_start=False,
                )
            return
    # --- other logic for single files ---
    found_type = check_subs_availability(url, user_id, data, return_type=True)
    available_langs = _subs_check_cache.get(
        f"{url}_{user_id}_{'auto' if found_type == 'auto' else 'normal'}_langs",
        []
    )

    subs_enabled = is_subs_enabled(user_id)
    auto_mode = get_user_subs_auto_mode(user_id)
    need_subs = (subs_enabled and ((auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal")))
    
    # Check if send_as_file is enabled - if so, skip cache repost
    user_args = get_user_args(user_id)
    send_as_file = user_args.get("send_as_file", False)
    
    if not need_subs and not is_subs_always_ask(user_id) and not send_as_file:

        message_ids = get_cached_message_ids(url, data)
        # If cache by the primary URL is not found, try cache by the video's unique URL (single video from a playlist)
        if not message_ids:
            try:
                # Try to load cached info to obtain the video's unique URL
                cached_info = load_ask_info(user_id, url)
                if cached_info:
                    video_page_url = (
                        cached_info.get("webpage_url")
                        or cached_info.get("original_url")
                        or cached_info.get("url")
                        or cached_info.get("canonical_url")
                    )
                    # If this is not the playlist URL, check cache by the unique URL
                    if video_page_url and video_page_url != url:
                        message_ids = get_cached_message_ids(video_page_url, data)
                        if message_ids:
                            logger.info(f"🔍 [CACHE] Found single video in cache by unique URL: {video_page_url}, quality: {data}")
                            # Update url for further processing
                            url = video_page_url
            except Exception as e:
                logger.warning(f"⚠️ [CACHE] Error while checking cache for a single video: {e}")
        
        if message_ids:
            callback_query.answer("🚀 Found in cache! Forwarding instantly...", show_alert=False)
            # found_type = None
            try:
                try:
                    target_chat_id = getattr(original_message.chat, 'id', user_id)
                except Exception:
                    target_chat_id = user_id
                thread_id = getattr(original_message, 'message_thread_id', None)
                # Only apply thread_id in groups/channels, not in private chats
                if thread_id and getattr(original_message.chat, "type", None) != enums.ChatType.PRIVATE:
                    # Forward each to ensure thread id is applied
                    for mid in message_ids:
                        from HELPERS.logger import get_log_channel
                        from HELPERS.porn import is_porn
                        # Determine if this is paid media (NSFW in private chat)
                        is_nsfw = is_porn(url, "", "", None)
                        is_private_chat = getattr(original_message.chat, "type", None) == enums.ChatType.PRIVATE
                        is_paid = is_nsfw and is_private_chat
                        logger.info(f"[VIDEO CACHE] URL analysis: url={url}, is_nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}")
                        # Get the correct log channel for reposting
                        if is_paid:
                            from_chat_id = get_log_channel("video", paid=True)
                            channel_type = "PAID"
                        elif is_nsfw:
                            from_chat_id = get_log_channel("video", nsfw=True)
                            channel_type = "NSFW"
                        else:
                            from_chat_id = get_log_channel("video")
                            channel_type = "regular"
                        
                        logger.info(f"[VIDEO CACHE] Channel selection: nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}, channel_type={channel_type}, from_chat_id={from_chat_id}")
                        
                        # Check channel access restrictions
                        if is_private_chat and channel_type == "NSFW":
                            logger.info(f"[VIDEO CACHE] Access denied: NSFW cache not allowed in private chat, skipping message {mid}")
                            continue  # Skip this message
                        elif not is_private_chat and channel_type == "PAID":
                            logger.info(f"[VIDEO CACHE] Access denied: Paid cache not allowed in group chat, skipping message {mid}")
                            continue  # Skip this message
                        
                        app.forward_messages(
                            chat_id=target_chat_id,
                            from_chat_id=from_chat_id,
                            message_ids=[mid],
                            message_thread_id=thread_id
                        )
                else:
                    from HELPERS.logger import get_log_channel
                    from HELPERS.porn import is_porn
                    # Determine if this is paid media (NSFW in private chat)
                    is_nsfw = is_porn(url, "", "", None)
                    is_private_chat = getattr(original_message.chat, "type", None) == enums.ChatType.PRIVATE
                    is_paid = is_nsfw and is_private_chat
                    logger.info(f"[VIDEO CACHE] URL analysis: url={url}, is_nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}")
                    # Get the correct log channel for reposting
                    if is_paid:
                        from_chat_id = get_log_channel("video", paid=True)
                        channel_type = "PAID"
                    elif is_nsfw:
                        from_chat_id = get_log_channel("video", nsfw=True)
                        channel_type = "NSFW"
                    else:
                        from_chat_id = get_log_channel("video")
                        channel_type = "regular"
                    
                    logger.info(f"[VIDEO CACHE] Channel selection: nsfw={is_nsfw}, is_private_chat={is_private_chat}, is_paid={is_paid}, channel_type={channel_type}, from_chat_id={from_chat_id}")
                    
                    # Check channel access restrictions
                    if is_private_chat and channel_type == "NSFW":
                        logger.info(f"[VIDEO CACHE] Access denied: NSFW cache not allowed in private chat, forcing re-download")
                        # Don't forward, let the function continue to download
                        return
                    elif not is_private_chat and channel_type == "PAID":
                        logger.info(f"[VIDEO CACHE] Access denied: Paid cache not allowed in group chat, forcing re-download")
                        # Don't forward, let the function continue to download
                        return
                    
                    app.forward_messages(
                        chat_id=target_chat_id,
                        from_chat_id=from_chat_id,
                        message_ids=message_ids
                    )
                app.send_message(target_chat_id, safe_get_messages(user_id).VIDEO_SENT_FROM_CACHE_MSG, reply_parameters=ReplyParameters(message_id=original_message.id))
                media_type = safe_get_messages(user_id).ALWAYS_ASK_AUDIO_TYPE_MSG if data == "mp3" else safe_get_messages(user_id).ALWAYS_ASK_VIDEO_TYPE_MSG
                log_msg = f"{media_type} sent from cache to user.\nURL: {url}\nUser: {callback_query.from_user.first_name} ({user_id})"
                send_to_logger(original_message, log_msg)
                return
            except Exception as e:
                logger.error(f"Error forwarding cached video: {e}")
                # found_type = check_subs_availability(url, user_id, data, return_type=True)
                subs_enabled = is_subs_enabled(user_id)
                auto_mode = get_user_subs_auto_mode(user_id)
                need_subs = (subs_enabled and ((auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal")))
                if not need_subs:
                    save_to_video_cache(url, data, [], clear=True)
                else:
                    logger.info("Video with subtitles (real subs found and needed) is not cached!")
                # Don't show error message if we successfully got video from cache
                # The video was already sent successfully in the try block
                handle_ask_quality_selection_request(
                    app,
                    build_callback_execution_context(callback_query),
                    selection_request,
                    original_message=original_message,
                    url=url,
                    tags_text=tags_text,
                    available_langs=available_langs,
                    proc_msg=proc_msg,
                )
            
            # Delete the Always Ask menu after handling
            try:
                _delete_callback_message()
            except Exception as e:
                logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_DELETE_ALWAYS_ASK_MENU_LOG_MSG}: {e}")
            return
    else:
        if is_subs_always_ask(user_id):
            logger.info(f"[VIDEO CACHE] Skipping cache check because Always Ask mode is enabled: url={url}, quality={data}")
        else:
            logger.info(f"[VIDEO CACHE] Skipping cache check because need_subs=True: url={url}, quality={data}")
    handle_ask_quality_selection_request(
        app,
        build_callback_execution_context(callback_query),
        selection_request,
        original_message=original_message,
        url=url,
        tags_text=tags_text,
        available_langs=available_langs,
        proc_msg=proc_msg,
    )
    
    # Delete the Always Ask menu after handling
    try:
        _delete_callback_message()
    except Exception as e:
        logger.warning(f"Failed to delete Always Ask menu: {e}")

###########################

@app.on_callback_query(filters.regex(r"^fallback_gallery_dl\|"))
def fallback_gallery_dl_callback(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_gallery_fallback_selection_request(
        callback_envelope,
        action_key=callback_query.data,
    )
    handle_gallery_fallback_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def fallback_gallery_dl_callback_logic(app, execution_context, request):
    """Handle fallback to gallery-dl when yt-dlp fails"""
    try:
        callback_query = execution_context.callback_query
        if callback_query is None:
            raise ValueError("Gallery fallback callback logic requires callback execution context")

        plan = _build_gallery_fallback_transition_plan(execution_context, request)
        logger.info(
            "Fallback to gallery-dl requested for user %s: %s (range: %s-%s)",
            plan.user_id,
            plan.url,
            plan.video_start_with,
            plan.video_end_with,
        )

        # Execute with evidence recording
        result, new_task = _execute_gallery_fallback_transition_plan_with_evidence(
            plan=plan,
            app=app,
            callback_query=callback_query,
        )

        fallback_result = result.get("fallback_result")
        logger.info(
            "Gallery-dl callback fallback result for user %s: outcome=%s success=%s",
            plan.user_id,
            fallback_result.outcome_kind
            if fallback_result is not None and is_gallery_command_result(fallback_result)
            else None,
            did_gallery_command_succeed(fallback_result)
            if fallback_result is not None and is_gallery_command_result(fallback_result)
            else None,
        )

        logger.info(
            "Gallery-dl fallback executed for user %s: %s",
            plan.user_id,
            plan.fallback_text,
        )

    except Exception as e:
        _emit_gallery_fallback_transition_error(callback_query, e)

###########################

# @reply_with_keyboard
def show_manual_quality_menu(app, callback_query):
    messages = safe_get_messages(callback_query.from_user.id)
    """Show manual quality selection menu when automatic detection fails"""
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = callback_query.from_user.id
    subs_available = ""
    found_type = None
    # Extract URL and tags from the callback
    original_message = callback_query.message.reply_to_message
    if not original_message:
        callback_query.answer(safe_get_messages(user_id).ALWAYS_ASK_ERROR_ORIGINAL_MESSAGE_NOT_FOUND_MSG, show_alert=True)
        callback_query.message.delete()
        return
    
    url = None
    if callback_query.message.caption_entities:
        for entity in callback_query.message.caption_entities:
            if entity.type == enums.MessageEntityType.TEXT_LINK and entity.url:
                url = entity.url
                break
    if not url and callback_query.message.reply_to_message:
        url_match = re.search(r'https?://[^\s\*#]+', callback_query.message.reply_to_message.text)
        if url_match:
            url = url_match.group(0)
    
    if not url:
        callback_query.answer("❌ Error: URL not found.", show_alert=True)
        callback_query.message.delete()
        return
    
    tags = []
    caption_text = callback_query.message.caption
    if caption_text:
        tag_matches = re.findall(r'#\S+', caption_text)
        if tag_matches:
            tags = tag_matches
    tags_text = ' '.join(tags)
    # NSFW detection for paid media warning
    try:
        is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
    except Exception:
        is_nsfw = False
    
    # Check if we're in a private chat (paid media only works in private chats)
    is_private_chat = getattr(callback_query.message.chat, "type", None) == enums.ChatType.PRIVATE
    
    # Check if user has send_as_file enabled
    user_args = get_user_args(user_id)
    send_as_file = user_args.get("send_as_file", False)
    
    # Check if it's a playlist
    original_text = original_message.text or original_message.caption or ""
    is_playlist = is_playlist_with_range(original_text)
    playlist_range = None
    if is_playlist:
        _, video_start_with, video_end_with, _, _, _, _ = extract_url_range_tags(original_text)
        playlist_range = (video_start_with, video_end_with)
        cached_qualities = get_cached_playlist_qualities(get_clean_playlist_url(url)) if not send_as_file else set()
    else:
        cached_qualities = get_cached_qualities(url) if not send_as_file else set()
    
    # Create manual quality buttons
    manual_qualities = ["144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p", "4320p"]
    buttons = []
    
    for quality in manual_qualities:
        if is_playlist and playlist_range:
            # Correct indices construction for negative indices
            start, end = playlist_range
            if start < 0 and end < 0:
                # Negative indices in reverse order
                if abs(start) < abs(end):
                    indices = list(range(start, end - 1, -1))
                else:
                    indices = list(range(start, end + 1, 1))
            elif start > end:
                # Reverse order
                indices = list(range(start, end - 1, -1))
            else:
                # Forward order
                indices = list(range(start, end + 1))
            n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality, indices)
            total = len(indices)
            icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
            postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
            button_text = f"{icon}{quality}{postfix}"
        else:
            icon = "🚀" if (quality in cached_qualities and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
            button_text = f"{icon}{quality}"
        buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|manual_{quality}"))

    # {safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG} Quality
    if is_playlist and playlist_range:
        # Correct indices construction for negative indices
        start, end = playlist_range
        if start < 0 and end < 0:
            if abs(start) < abs(end):
                indices = list(range(start, end - 1, -1))
            else:
                indices = list(range(start, end + 1, 1))
        elif start > end:
            indices = list(range(start, end - 1, -1))
        else:
            indices = list(range(start, end + 1))
        n_cached = get_cached_playlist_count(get_clean_playlist_url(url), "best", indices)
        total = len(indices)
        icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
        postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
        button_text = f"{icon}{safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG} Quality{postfix}"
    else:
        icon = "🚀" if ("best" in cached_qualities and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
        button_text = f"{icon}{safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG} Quality"
    buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|manual_best"))
    
    # Form rows of 3 buttons
    keyboard_rows = []
    for i in range(0, len(buttons), 3):
        keyboard_rows.append(buttons[i:i+3])
    
    # Add mp3 button
    quality_key = "mp3"
    if is_playlist and playlist_range:
        # Correct indices construction for negative indices
        start, end = playlist_range
        if start < 0 and end < 0:
            if abs(start) < abs(end):
                indices = list(range(start, end - 1, -1))
            else:
                indices = list(range(start, end + 1, 1))
        elif start > end:
            indices = list(range(start, end - 1, -1))
        else:
            indices = list(range(start, end + 1))
        n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality_key, indices)
        total = len(indices)
        icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "🎧")
        postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
        button_text = f"{icon} audio (mp3){postfix}"
    else:
        icon = "🚀" if (quality_key in cached_qualities and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "🎧")
        button_text = f"{icon} audio (mp3)"
    keyboard_rows.append([InlineKeyboardButton(button_text, callback_data=f"askq|manual_{quality_key}")])
    
    # Add subtitles only button if enabled
    subs_enabled = is_subs_enabled(user_id)
    if subs_enabled and is_youtube_url(url):
        found_type = check_subs_availability(url, user_id, return_type=True)
        auto_mode = get_user_subs_auto_mode(user_id)
        need_subs = (auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal")
        
        if need_subs:
            keyboard_rows.append([InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_SUB_ONLY_BUTTON_MSG, callback_data="askq|subs_only")])
    
    # Add Back and close buttons
    keyboard_rows.append([
        InlineKeyboardButton(safe_get_messages(user_id).BACK_BUTTON_TEXT, callback_data="askq|manual_back"),
        InlineKeyboardButton(safe_get_messages(user_id).CLOSE_BUTTON_TEXT, callback_data="askq|close")
    ])
    
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    
    # Get video title for caption - try cached info first
    try:
        cached_info = load_ask_info(user_id, url)
        if cached_info:
            title = cached_info.get('title', 'Video')
            video_title = title
            logger.info(f"✅ [OPTIMIZATION] Using cached title for caption")
        else:
            info = get_video_formats(url, user_id, cookies_already_checked=True)
            title = info.get('title', 'Video')
            video_title = title
            logger.info(f"⚠️ [OPTIMIZATION] Had to fetch video info for title")
    except:
        video_title = safe_get_messages(user_id).ALWAYS_ASK_VIDEO_TITLE_MSG
    
    # Form caption
    cap = f"<b>{video_title}</b>\n"
    if tags_text:
        cap += f"{tags_text}"
    try:
        is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
    except Exception:
        is_nsfw = False
    if is_nsfw and is_private_chat:
        cap += "\n<b>⭐️ — 🔞NSFW is paid (⭐️$0.02)</b>\n"
    if is_nsfw and is_private_chat:
        cap += "\n<b>⭐️ — 🔞NSFW is paid (⭐️$0.02)</b>\n"
    cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_MANUAL_QUALITY_SELECTION_MSG}</b>\n"
    cap += f"\n<i>{safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_QUALITY_MANUALLY_MSG}</i>\n"
    
    # Update current menu; if MESSAGE_ID_INVALID, send new message
    if callback_query and getattr(callback_query, 'message', None):
        try:
            if callback_query.message.photo:
                callback_query.edit_message_caption(caption=cap, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)
            else:
                callback_query.edit_message_text(text=cap, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)
            callback_query.answer("Quality selection menu opened.")
            return
        except Exception as ee:
            # If editing fails (e.g., MESSAGE_ID_INVALID), send a new message instead
            if 'MESSAGE_ID_INVALID' not in str(ee):
                logger.warning(f"Manual menu edit failed, fallback to new message: {ee}")
    # Fallback: send a new message, replying to the original
    try:
        chat_id = callback_query.message.chat.id if callback_query and getattr(callback_query, 'message', None) else user_id
        ref_id = original_message.id if original_message else None
        send_kwargs = {
            "chat_id": chat_id,
            "text": cap,
            "parse_mode": enums.ParseMode.HTML,
            "reply_markup": keyboard,
        }
        if ref_id is not None:
            send_kwargs["reply_parameters"] = ReplyParameters(message_id=ref_id)
        app.send_message(**send_kwargs)
        if callback_query:
            callback_query.answer("Quality selection menu opened.")
    except Exception as e2:
        logger.error(f"Error showing manual quality menu (fallback): {e2}")
        if callback_query:
            callback_query.answer("❌ Failed to open the quality selection menu.", show_alert=True)

def show_other_qualities_menu(app, callback_query, page=0):
    messages = safe_get_messages(callback_query.from_user.id)
    """Show all available qualities from yt-dlp -F output with pagination"""
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = callback_query.from_user.id
    
    # Local safe wrapper to avoid noisy QueryIdInvalid when answering twice/late
    def _safe_answer(text, show_alert=False):
        messages = safe_get_messages(user_id)
        try:
            callback_query.answer(text, show_alert=show_alert)
        except Exception as e:
            if 'QUERY_ID_INVALID' in str(e).upper():
                return
            try:
                # Some environments provide .MESSAGE_ID_INVALID
                if 'MESSAGE_ID_INVALID' in str(e).upper():
                    return
            except Exception:
                pass
            raise
    
    # Check if we have cached formats for this URL
    url = None
    original_message = callback_query.message.reply_to_message
    if original_message:
        url_text = original_message.text or (original_message.caption or "")
        import re as _re
        m = _re.search(r'https?://[^\s\*#]+', url_text)
        url = m.group(0) if m else url_text
    
    if url:
        # Clean up old format cache files before checking current cache
        try:
            user_dir = os.path.join("users", str(user_id))
            create_directory(user_dir)
            
            # Get download directory if available
            user_download_dir = get_user_download_dir(user_id)
            
            # Remove all old format cache files except current one
            import glob
            # Use download directory if available, otherwise fallback to user directory
            if user_download_dir and os.path.exists(user_download_dir):
                format_cache_pattern = os.path.join(user_download_dir, "formats_cache_*.json")
                current_cache_file = os.path.join(user_download_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
            else:
                format_cache_pattern = os.path.join(user_dir, "formats_cache_*.json")
                current_cache_file = os.path.join(user_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
            old_cache_files = glob.glob(format_cache_pattern)
            
            for cache_file in old_cache_files:
                if cache_file != current_cache_file:  # Don't delete current cache
                    try:
                        os.remove(cache_file)
                        logger.info(f"{LoggerMsg.ALWAYS_ASK_CLEANED_UP_OLD_FORMAT_CACHE_LOG_MSG}: {cache_file}")
                    except Exception as e:
                        logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_REMOVE_OLD_CACHE_FILE_LOG_MSG} {cache_file}: {e}")
                        
            if len(old_cache_files) > 1:  # More than just current cache
                logger.info(f"Cleaned up {len(old_cache_files) - 1} old format cache files for user {user_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up old format cache files: {e}")
        
        cache_file = current_cache_file
        if os.path.exists(cache_file):
            # Use cached formats for any page
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    format_lines = cached_data.get('formats', [])
                    if format_lines:
                        # Show cached formats immediately
                        logger.info(f"Using cached formats for page {page + 1}, {len(format_lines)} formats found")
                        show_formats_from_cache(app, callback_query, format_lines, page, url)
                        return
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_file}: {e}")
                pass  # Fall back to fresh fetch
    
    # Extract URL from the callback
    original_message = callback_query.message.reply_to_message
    if not original_message:
        callback_query.answer(safe_get_messages(user_id).ALWAYS_ASK_ERROR_ORIGINAL_MESSAGE_NOT_FOUND_MSG, show_alert=True)
        callback_query.message.delete()
        return
    
    url = None
    if callback_query.message.caption_entities:
        for entity in callback_query.message.caption_entities:
            if entity.type == enums.MessageEntityType.TEXT_LINK and entity.url:
                url = entity.url
                break
    if not url and callback_query.message.reply_to_message:
        url_match = re.search(r'https?://[^\s\*#]+', callback_query.message.reply_to_message.text)
        if url_match:
            url = url_match.group(0)
    
    if not url:
        callback_query.answer("❌ Error: URL not found.", show_alert=True)
        callback_query.message.delete()
        return
    
    # Extract tags
    tags = []
    caption_text = callback_query.message.caption
    if caption_text:
        tag_matches = re.findall(r'#\S+', caption_text)
        if tag_matches:
            tags = tag_matches
    tags_text = ' '.join(tags)
    try:
        is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
    except Exception:
        is_nsfw = False
    
    # Check if we're in a private chat (paid media only works in private chats)
    is_private_chat = getattr(callback_query.message.chat, "type", None) == enums.ChatType.PRIVATE
    
    # Check if it's a playlist
    original_text = original_message.text or original_message.caption or ""
    is_playlist = is_playlist_with_range(original_text)
    
    # Get video title for caption - try cached info first
    try:
        cached_info = load_ask_info(user_id, url)
        if cached_info:
            title = cached_info.get('title', 'Video')
            video_title = title
            logger.info(f"✅ [OPTIMIZATION] Using cached title for caption")
        else:
            info = get_video_formats(url, user_id, cookies_already_checked=True)
            title = info.get('title', 'Video')
            video_title = title
            logger.info(f"⚠️ [OPTIMIZATION] Had to fetch video info for title")
    except:
        video_title = safe_get_messages(user_id).ALWAYS_ASK_VIDEO_TITLE_MSG
    
    # Form caption
    cap = f"<b>{video_title}</b>\n"
    if tags_text:
        cap += f"{tags_text}"
    if is_nsfw and is_private_chat:
        cap += "\n<b>⭐️ — 🔞NSFW is paid (⭐️$0.02)</b>\n"
    cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_ALL_AVAILABLE_FORMATS_MSG}</b>\n"
    cap += f"\n<i>{safe_get_messages(user_id).PAGE_NUMBER_MSG.format(page=page + 1)}</i>\n"
    
    # Get all formats using yt-dlp -F
    try:
        import subprocess
        import sys
        
        # Create cache file path
        user_dir = os.path.join("users", str(user_id))
        create_directory(user_dir)
        
        # Get download directory if available
        user_download_dir = get_user_download_dir(user_id)
        
        # Use download directory if available, otherwise fallback to user directory
        if user_download_dir and os.path.exists(user_download_dir):
            cache_file = os.path.join(user_download_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
        else:
            cache_file = os.path.join(user_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
        
        # Check if we have cached formats
        format_lines = []
        if os.path.exists(cache_file):
            # Use cached data if available
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    format_lines = cached_data.get('formats', [])
                    if format_lines:
                        logger.info(f"Using cached formats from {cache_file}")
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_file}: {e}")
        
        if not format_lines:
            # Run yt-dlp -F to get all formats
            logger.info(f"Running yt-dlp -F for URL: {url}")
            
            # Build command with cookies if available (use same yt-dlp as Python API)
            cmd = [sys.executable, "-m", "yt_dlp"]
            # Add PO token extractor-args for CLI if applicable (YouTube only)
            cmd.extend(build_cli_extractor_args(url))
            # -F list formats
            cmd.append("-F")
            
            # Add cookies file if it exists
            user_cookie_file = os.path.join("users", str(user_id), "cookie.txt")
            if os.path.exists(user_cookie_file):
                cmd.extend(["--cookies", user_cookie_file])
                logger.info(f"Using cookies from: {user_cookie_file}")
            else:
                logger.info("No user cookie file found, using default")
            
            # Add proxy if needed for this domain
            from HELPERS.proxy_helper import is_proxy_domain, get_proxy_config
            if is_proxy_domain(url):
                proxy_config = get_proxy_config()
                if proxy_config and 'proxy' in proxy_config:
                    proxy_url = proxy_config['proxy']
                    cmd.extend(["--proxy", proxy_url])
                    logger.info(f"Added proxy to yt-dlp command: {proxy_url}")
            
            cmd.append(url)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            logger.info(f"yt-dlp -F completed with return code: {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"yt-dlp -F failed with stderr: {result.stderr}")
                # Fallback: try to get formats from cached info
                info = get_video_formats(url, user_id, cookies_already_checked=True)
                formats = info.get('formats', [])
                format_lines = []
                for f in formats:
                    if not isinstance(f, dict):
                        continue
                    format_id = f.get('format_id', 'unknown')
                    ext = f.get('ext', 'unknown')
                    resolution = f.get('resolution', 'unknown')
                    proto = f.get('protocol', 'https')
                    vcodec = f.get('vcodec', 'none')
                    
                    # Validate format_id - should not contain brackets or special characters
                    if format_id and not format_id.startswith('[') and not format_id.startswith('(') and format_id != 'unknown':
                        # Skip non-media formats
                        if ext.lower() in ['mhtml', 'html', 'txt', 'json', 'xml']:
                            continue
                        
                        # Store format info for button creation
                        format_lines.append(f"{format_id:<12} {ext:<8} {resolution:<12} {proto:<12} {vcodec}")
                        logger.debug(f"Fallback format: {format_id} | {ext} | {resolution} | {proto} | {vcodec}")
                    else:
                        logger.warning(f"Skipping invalid fallback format_id: {format_id}")
                
                # If no formats found, create basic format list
                if not format_lines:
                    # Create basic format list based on common patterns
                    basic_formats = [
                        "best",
                        "worst", 
                        "bestvideo+bestaudio",
                        "bv+ba"
                    ]
                    for fmt in basic_formats:
                        format_lines.append(f"{fmt:<12} mp4 unknown https none")
                
                # Cache the fallback formats for future use
                if format_lines:
                    try:
                        cache_data = {
                            'url': url,
                            'timestamp': datetime.now().isoformat(),
                            'formats': format_lines
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        logger.info(f"Cached {len(format_lines)} fallback formats to {cache_file}")
                    except Exception as e:
                        logger.warning(f"Failed to cache fallback formats: {e}")
            else:
                # Parse yt-dlp output
                output_lines = result.stdout.strip().split('\n')
                format_lines = []
                logger.info(f"Parsing yt-dlp output: {len(output_lines)} lines")
                
                for line in output_lines:
                    if line.strip() and not line.startswith('ID') and not line.startswith('─') and not line.startswith('format_id'):
                        # Parse format line (ID, EXT, RESOLUTION, FPS, FILESIZE, TBR, PROTO, VCODEC, VBR, ACODEC, ABR, ASR, MORE INFO)
                        parts = line.split()
                        if len(parts) >= 7:  # Need at least ID, EXT, RESOLUTION, FPS, FILESIZE, TBR, PROTO
                            format_id = parts[0]
                            ext = parts[1] if len(parts) > 1 else 'unknown'
                            resolution = parts[2] if len(parts) > 2 else '—'
                            filesize = parts[4] if len(parts) > 4 else 'unknown'
                            proto = parts[6] if len(parts) > 6 else 'unknown'
                            vcodec = 'none'
                            
                            # Remove ≈ symbol from filesize
                            if filesize.startswith('≈'):
                                filesize = filesize[1:].strip()
                            
                            # Find VCODEC (usually around position 8-9)
                            for j, part in enumerate(parts):
                                if j and j > 7 and part and part != 'none' and not part.startswith('mp4a') and not part.startswith('—') and not part.startswith('audio') and not part.startswith('≈'):
                                    # Check if this looks like a video codec
                                    if any(codec in part.lower() for codec in ['avc', 'vp9', 'av1', 'h264', 'h265', 'hevc']):
                                        vcodec = part
                                        break
                            
                            # Skip non-media formats
                            if ext.lower() in ['mhtml', 'html', 'txt', 'json', 'xml']:
                                continue
                            
                            # Validate format_id - should not contain brackets or special characters
                            if format_id and not format_id.startswith('[') and not format_id.startswith('('):
                                # Store complete original line for full data preservation
                                format_lines.append(line.strip())
                                logger.debug(f"Stored complete format line: {line.strip()}")
                            else:
                                logger.warning(f"Skipping invalid format_id: {format_id}")
                
                logger.info(f"Parsed {len(format_lines)} formats from yt-dlp output")
                
                # Cache the formats for future use
                if format_lines:
                    try:
                        cache_data = {
                            'url': url,
                            'timestamp': datetime.now().isoformat(),
                            'formats': format_lines
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        logger.info(f"Cached {len(format_lines)} formats to {cache_file}")
                    except Exception as e:
                        logger.warning(f"Failed to cache formats: {e}")
        
        menu_plan = _build_other_qualities_menu_plan(
            callback_query,
            format_lines=format_lines,
            page=page,
            url=url,
            video_title=video_title,
            is_nsfw=is_nsfw,
            is_private_chat=is_private_chat,
            from_cache=False,
        )
        _emit_other_qualities_menu_plan(app, callback_query, menu_plan=menu_plan, original_message=original_message)
        
            # Clean up temp file
        # No temp file used here; keep block for future extensions
            
    except Exception as e:
        logger.error(f"Error getting formats: {e}")
        _safe_answer(safe_get_messages(user_id).ALWAYS_ASK_ERROR_GETTING_FORMATS_MSG, show_alert=True)
        # Show error message
        error_cap = f"<b>{video_title}</b>\n\n{safe_get_messages(user_id).ALWAYS_ASK_ERROR_GETTING_AVAILABLE_FORMATS_MSG}\n{safe_get_messages(user_id).ALWAYS_ASK_PLEASE_TRY_AGAIN_LATER_MSG}"
        try:
            if callback_query.message.photo:
                callback_query.edit_message_caption(caption=error_cap, parse_mode=enums.ParseMode.HTML)
            else:
                callback_query.edit_message_text(text=error_cap, parse_mode=enums.ParseMode.HTML)
        except:
            pass

def show_formats_from_cache(app, callback_query, format_lines, page, url):
    messages = safe_get_messages(callback_query.from_user.id)
    """Show formats from cached data for fast navigation"""
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = callback_query.from_user.id
    logger.info(f"Showing formats from cache for user {user_id}, page {page}, {len(format_lines)} formats")
    
    # Get video title for caption - try cached info first
    try:
        cached_info = load_ask_info(user_id, url)
        if cached_info:
            title = cached_info.get('title', 'Video')
            video_title = title
            logger.info(f"✅ [OPTIMIZATION] Using cached title for caption")
        else:
            info = get_video_formats(url, user_id, cookies_already_checked=True)
            title = info.get('title', 'Video')
            video_title = title
            logger.info(f"⚠️ [OPTIMIZATION] Had to fetch video info for title")
    except:
        video_title = safe_get_messages(user_id).ALWAYS_ASK_VIDEO_TITLE_MSG
    
    # Form caption
    cap = f"<b>{video_title}</b>\n"
    cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_ALL_AVAILABLE_FORMATS_MSG}</b>\n"
    try:
        orig_text = callback_query.message.reply_to_message.text or callback_query.message.reply_to_message.caption or ""
    except Exception:
        orig_text = ""
    is_nsfw = isinstance(orig_text, str) and ('#nsfw' in orig_text.lower())
    # Check if we're in a private chat (paid media only works in private chats)
    is_private_chat = getattr(callback_query.message.chat, "type", None) == enums.ChatType.PRIVATE
    if isinstance(url, str) and is_nsfw and is_private_chat:
        cap += "\n<b>⭐️ — 🔞NSFW is paid (⭐️$0.02)</b>\n"
    cap += f"\n<i>{safe_get_messages(user_id).PAGE_NUMBER_MSG.format(page=page + 1)}</i>\n"
    
    menu_plan = _build_other_qualities_menu_plan(
        callback_query,
        format_lines=format_lines,
        page=page,
        url=url,
        video_title=video_title,
        is_nsfw=is_nsfw,
        is_private_chat=is_private_chat,
        from_cache=True,
    )
    _emit_other_qualities_menu_plan(
        app,
        callback_query,
        menu_plan=menu_plan,
        original_message=callback_query.message.reply_to_message,
    )

# --- Always ask processing ---
def sort_quality_key(quality_key):
    """Sort qualities by increasing resolution from lower to higher"""
    if quality_key == "best":
        return 999999  # best is always at the end
    elif quality_key == "mp3":
        return -1  # mp3 at the very beginning
    else:
        # Extract a number from a string (e.g. "720p" -> 720)
        try:
            return int(quality_key.replace('p', ''))
        except ValueError:
            return 0  # for unknown formats

def create_cached_qualities_menu(app, message, url, tags, proc_msg, user_id, original_text, is_playlist, playlist_range):
    """Build a quality menu from cached data when fresh data cannot be fetched."""
    try:
        menu_plan = _build_cached_qualities_menu_plan(
            message,
            url=url,
            tags=tags,
            user_id=user_id,
            original_text=original_text,
            is_playlist=is_playlist,
            playlist_range=playlist_range,
        )
        if menu_plan is None:
            return False
        return _emit_cached_qualities_menu(
            app,
            message,
            proc_msg=proc_msg,
            user_id=user_id,
            menu_plan=menu_plan,
        )
    except Exception as e:
        logger.error(f"Error creating cached qualities menu: {e}")
        return False


def _build_cached_qualities_menu_plan(
    message,
    *,
    url: str,
    tags,
    user_id: int,
    original_text: str,
    is_playlist: bool,
    playlist_range,
) -> CachedQualitiesMenuPlan | None:
    messages = safe_get_messages(user_id)
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        logger.info(f"Attempting to create menu from cached qualities for user {user_id}")
        
        # Check if user has fixed format via /args
        user_fixed_format = None
        try:
            user_args = get_user_args(user_id)
            user_video_format = user_args.get('video_format', 'mp4')
            user_merge_format = user_args.get('merge_output_format', 'mp4')
            
            # If user has set video_format to something other than mp4, it's fixed
            if user_video_format != 'mp4':
                user_fixed_format = user_video_format
            # If user has set merge_output_format to something other than mp4, it's fixed
            elif user_merge_format != 'mp4':
                user_fixed_format = user_merge_format
        except Exception:
            pass
        
        # Check if user has send_as_file enabled
        user_args = get_user_args(user_id)
        send_as_file = user_args.get("send_as_file", False)
        
        # Fetch cached qualities (skip if send_as_file is enabled)
        if send_as_file:
            cached_qualities = set()
        elif is_playlist and playlist_range:
            cached_qualities = get_cached_playlist_qualities(get_clean_playlist_url(url))
        else:
            cached_qualities = get_cached_qualities(url)
        
        if not cached_qualities:
            logger.info(f"No cached qualities found for user {user_id}")
            return None
        
        logger.info(f"Found cached qualities for user {user_id}: {list(cached_qualities)}")
        
        # Load basic video info from cache
        try:
            info = load_ask_info(user_id, url)
            if not info:
                # Fall back to minimal info
                info = {'title': 'Video (cached)', 'id': 'cached'}
        except Exception:
            info = {'title': 'Video (cached)', 'id': 'cached'}
        
        title = info.get('title', 'Video (cached)')
        tags_text = generate_final_tags(url, tags, info)
        
        # Determine NSFW
        try:
            is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
        except Exception:
            is_nsfw = False
        
        # Check if we're in a private chat (paid media only works in private chats)
        is_private_chat = getattr(message.chat, "type", None) == enums.ChatType.PRIVATE
        
        # Build caption header
        cap = f"<b>{title}</b>\n"
        if tags_text:
            cap += f"{tags_text}"
        if is_nsfw and is_private_chat:
            cap += "\n<b>⭐️ — 🔞NSFW is paid (⭐️$0.02)</b>\n"
        if user_fixed_format:
                cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_FIXED_VIA_ARGS_MSG}: {user_fixed_format.upper()}</b>\n"
        cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_AVAILABLE_QUALITIES_FROM_CACHE_MSG}</b>\n"
        cap += f"\n<i>{safe_get_messages(user_id).ALWAYS_ASK_USING_CACHED_QUALITIES_MSG}</i>\n"
        
        # Build quality buttons from cache
        buttons = []
        
        # Add a button per cached quality
        quality_order = ["144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p", "4320p", "mp3"]
        
        for quality_key in quality_order:
            if quality_key in cached_qualities:
                if is_playlist and playlist_range:
                    # Correct indices construction for negative indices
                    start, end = playlist_range
                    if start < 0 and end < 0:
                        if abs(start) < abs(end):
                            indices = list(range(start, end - 1, -1))
                        else:
                            indices = list(range(start, end + 1, 1))
                    elif start > end:
                        indices = list(range(start, end - 1, -1))
                    else:
                        indices = list(range(start, end + 1))
                    n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality_key, indices)
                    total = len(indices)
                    icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
                    postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
                    button_text = f"{icon}{quality_key}{postfix}"
                else:
                    # Check cache for a single video
                    is_cached = quality_key in cached_qualities
                    # Additionally check cache by the video's unique URL (single video from a playlist)
                    if not is_cached:
                        try:
                            cached_info = load_ask_info(user_id, url)
                            if cached_info:
                                video_page_url = (
                                    cached_info.get("webpage_url")
                                    or cached_info.get("original_url")
                                    or cached_info.get("url")
                                    or cached_info.get("canonical_url")
                                )
                                # If this is not the playlist URL, check cache by the unique URL
                                if video_page_url and video_page_url != url:
                                    single_video_cached = get_cached_message_ids(video_page_url, quality_key)
                                    if single_video_cached:
                                        is_cached = True
                                        logger.info(f"🔍 [CACHE] Found single video in cache by unique URL: {video_page_url}, quality: {quality_key}")
                        except Exception as e:
                            logger.warning(f"⚠️ [CACHE] Error while checking cache for a single video: {e}")
                    
                    icon = "🚀" if (is_cached and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
                    button_text = f"{icon}{quality_key}"
                buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|{quality_key}"))
        
        # Always include {safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG} quality
        quality_key = "best"
        if is_playlist and playlist_range:
            # Correct indices construction for negative indices
            start, end = playlist_range
            if start < 0 and end < 0:
                if abs(start) < abs(end):
                    indices = list(range(start, end - 1, -1))
                else:
                    indices = list(range(start, end + 1, 1))
            elif start > end:
                indices = list(range(start, end - 1, -1))
            else:
                indices = list(range(start, end + 1))
            n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality_key, indices)
            total = len(indices)
            icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
            postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
            button_text = f"{icon}{safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG}{postfix}"
        else:
            icon = "🚀" if (quality_key in cached_qualities and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
            button_text = f"{icon}{safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG}"
        buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|{quality_key}"))
        
        # Always include "Other qualities"
        buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_OTHER_LABEL_MSG, callback_data=f"askq|other_qualities"))

        # Build keyboard
        keyboard_rows = []
        
        # Add filters
        filter_rows, filter_action_buttons = build_filter_rows(user_id, url, is_private_chat)
        keyboard_rows.extend(filter_rows)
        
        # Group quality buttons in rows of 3
        if buttons:
            total_quality_buttons = len(buttons)
            if total_quality_buttons % 3 == 0:
                for i in range(0, total_quality_buttons, 3):
                    keyboard_rows.append(buttons[i:i+3])
            elif total_quality_buttons % 3 == 1 and total_quality_buttons > 1:
                for i in range(0, total_quality_buttons - 4, 3):
                    keyboard_rows.append(buttons[i:i+3])
                keyboard_rows.append(buttons[-4:-2])
                keyboard_rows.append(buttons[-2:])
            else:
                for i in range(0, total_quality_buttons, 3):
                    keyboard_rows.append(buttons[i:i+3])
        
        # Collect action buttons
        action_buttons = []
        action_buttons.extend(filter_action_buttons)
        # IMAGE fallback from the cached menu
        action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).IMAGE_BUTTON_TEXT, callback_data="askq|image"))        
        # Add a WATCH button for YouTube
        # - private chat: WebApp (convenient viewing)
        # - groups: regular URL button (WebApp can cause BUTTON_TYPE_INVALID in some contexts)
        try:
            if is_youtube_url(url):
                piped_url = youtube_to_piped_url(url)
                try:
                    is_group = isinstance(user_id, int) and user_id < 0
                except Exception:
                    is_group = False
                if is_group:
                    action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_WATCH_BUTTON_MSG, url=piped_url))
                else:
                    wa = WebAppInfo(url=piped_url)
                    action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_WATCH_BUTTON_MSG, web_app=wa))
        except Exception as e:
            logger.error(f"Error adding WATCH button: {e}")
        
        # Group action buttons
        if action_buttons:
            for i in range(0, len(action_buttons), 3):
                keyboard_rows.append(action_buttons[i:i+3])
        
        # Add a close button
        keyboard_rows.append([InlineKeyboardButton(safe_get_messages(user_id).CLOSE_BUTTON_TEXT, callback_data="askq|close")])
        
        keyboard = InlineKeyboardMarkup(keyboard_rows)
        return CachedQualitiesMenuPlan(text=cap, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error building cached qualities menu: {e}")
        return None


def _emit_cached_qualities_menu(app, message, *, proc_msg, user_id: int, menu_plan: CachedQualitiesMenuPlan) -> bool:
    try:
        if proc_msg:
            try:
                result = app.edit_message_text(
                    chat_id=user_id,
                    message_id=proc_msg.id,
                    text=menu_plan.text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=menu_plan.reply_markup,
                )
                if result is None:
                    app.send_message(
                        user_id,
                        menu_plan.text,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=menu_plan.reply_markup,
                    )
            except Exception as edit_error:
                if "MESSAGE_ID_INVALID" in str(edit_error):
                    logger.warning(f"Message ID invalid, sending new message: {edit_error}")
                    app.send_message(
                        user_id,
                        menu_plan.text,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=menu_plan.reply_markup,
                    )
                elif "BUTTON_TYPE_INVALID" in str(edit_error):
                    logger.warning(f"Button type invalid, sending without keyboard: {edit_error}")
                    app.send_message(
                        user_id,
                        menu_plan.text,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        parse_mode=enums.ParseMode.HTML,
                    )
                else:
                    raise
        else:
            try:
                app.send_message(
                    user_id,
                    menu_plan.text,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=menu_plan.reply_markup,
                )
            except Exception as send_error:
                if "BUTTON_TYPE_INVALID" in str(send_error):
                    logger.warning(f"Button type invalid, sending without keyboard: {send_error}")
                    app.send_message(
                        user_id,
                        menu_plan.text,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        parse_mode=enums.ParseMode.HTML,
                    )
                else:
                    raise
        logger.info(f"Successfully created cached qualities menu for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending cached qualities menu: {e}")
        return False


def _build_quality_menu_render_plan(
    *,
    text: str,
    keyboard_rows,
    thumb_path: str | None,
    is_playlist: bool,
    is_nsfw: bool,
) -> QualityMenuRenderPlan:
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    can_send_thumb_menu = bool(thumb_path and os.path.exists(thumb_path) and not is_playlist)
    return QualityMenuRenderPlan(
        text=text,
        reply_markup=reply_markup,
        can_send_thumb_menu=can_send_thumb_menu,
        thumb_path=thumb_path,
        is_nsfw=is_nsfw,
    )


def _group_buttons_smart(buttons: list, *, log_prefix: str | None = None) -> list:
    rows = []
    if not buttons:
        return rows
    total_buttons = len(buttons)
    if total_buttons % 3 == 0:
        for i in range(0, total_buttons, 3):
            row = buttons[i:i + 3]
            rows.append(row)
            if log_prefix:
                logger.info(f"{log_prefix}: {[btn.text for btn in row]}")
    elif total_buttons % 3 == 1 and total_buttons > 1:
        for i in range(0, total_buttons - 4, 3):
            row = buttons[i:i + 3]
            rows.append(row)
            if log_prefix:
                logger.info(f"{log_prefix}: {[btn.text for btn in row]}")
        rows.append(buttons[-4:-2])
        rows.append(buttons[-2:])
        if log_prefix:
            logger.info(f"{log_prefix}: {[btn.text for btn in buttons[-4:-2]]}")
            logger.info(f"{log_prefix}: {[btn.text for btn in buttons[-2:]]}")
    else:
        for i in range(0, total_buttons, 3):
            row = buttons[i:i + 3]
            rows.append(row)
            if log_prefix:
                logger.info(f"{log_prefix}: {[btn.text for btn in row]}")
    return rows


def _compose_quality_menu(
    *,
    user_id: int,
    url: str,
    cap: str,
    buttons: list,
    action_buttons: list,
    filter_rows: list,
    found_quality_keys,
    is_nsfw: bool,
    is_private_chat: bool,
    show_repost_hint: bool,
    cached_qualities,
    subs_hint: str,
    subs_warn: str,
    filters_state,
) -> QualityMenuComposition:
    if not found_quality_keys:
        cap += f"\n{safe_get_messages(user_id).QUALITIES_NOT_AUTO_DETECTED_NOTE}\n"

    keyboard_rows = []
    keyboard_rows.extend(filter_rows)
    keyboard_rows.extend(_group_buttons_smart(buttons))

    logger.info(f"{safe_get_messages(user_id).ALWAYS_ASK_SMART_GROUPING_MSG} {len(action_buttons)} action buttons for user {user_id}")
    keyboard_rows.extend(
        _group_buttons_smart(
            action_buttons,
            log_prefix=safe_get_messages(user_id).ALWAYS_ASK_ADDED_ACTION_BUTTON_ROW_3_MSG,
        )
    )

    bottom_buttons = (
        [
            InlineKeyboardButton(
                safe_get_messages(user_id).BACK_BUTTON_TEXT,
                callback_data="askf|toggle|off",
            ),
            InlineKeyboardButton(
                safe_get_messages(user_id).CLOSE_BUTTON_TEXT,
                callback_data="askq|close",
            ),
        ]
        if bool(filters_state.get("visible", False))
        else [
            InlineKeyboardButton(
                safe_get_messages(user_id).CLOSE_BUTTON_TEXT,
                callback_data="askq|close",
            )
        ]
    )
    if keyboard_rows and len(keyboard_rows[-1]) < 3 and len(bottom_buttons) <= (3 - len(keyboard_rows[-1])):
        keyboard_rows[-1].extend(bottom_buttons)
        logger.info(
            f"{safe_get_messages(user_id).ALWAYS_ASK_ADDED_BOTTOM_BUTTONS_TO_EXISTING_ROW_MSG}: "
            f"{[btn.text for btn in bottom_buttons]}"
        )
    else:
        keyboard_rows.append(bottom_buttons)
        logger.info(
            f"{safe_get_messages(user_id).ALWAYS_ASK_CREATED_NEW_BOTTOM_ROW_MSG}: "
            f"{[btn.text for btn in bottom_buttons]}"
        )

    logger.info(f"Final keyboard structure for user {user_id}: {len(keyboard_rows)} rows")
    for i, row in enumerate(keyboard_rows):
        logger.info(f"Row {i}: {[btn.text for btn in row]}")

    used_emojis = set()
    for button_group in (action_buttons, buttons):
        for button in button_group:
            if hasattr(button, "text") and button.text:
                first_char = button.text[0]
                if ord(first_char) > 127:
                    used_emojis.add(first_char)
    for row in filter_rows:
        for button in row:
            if hasattr(button, "text") and button.text:
                first_char = button.text[0]
                if ord(first_char) > 127:
                    used_emojis.add(first_char)
    logger.info(f"Detected emojis in menu for user {user_id}: {sorted(used_emojis)}")

    dynamic_hints = [safe_get_messages(user_id).ALWAYS_ASK_CHANGE_VIDEO_EXT_MSG]
    if is_nsfw and is_private_chat:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_NSFW_PAID_MSG)
    else:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_DOWNLOAD_QUALITY_MSG)
    if show_repost_hint and cached_qualities and "🚀" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_INSTANT_REPOST_MSG)
    if is_youtube_url(url) and "👁" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_WATCH_VIDEO_MSG)
    if "🔗" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_GET_DIRECT_LINK_MSG)
    if "📃" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_SHOW_AVAILABLE_FORMATS_MSG)
    if not found_quality_keys and "🖼" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_DOWNLOAD_IMAGE_MSG)
    if "🎧" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_EXTRACT_AUDIO_MSG)
    if subs_hint:
        dynamic_hints.append(subs_hint.strip())
    if subs_warn:
        dynamic_hints.append(subs_warn.strip())
    if get_filters(user_id).get("has_dubs") and "🗣" in used_emojis:
        dynamic_hints.append(safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_AUDIO_LANGUAGE_MSG)

    dynamic_hint_text = "<pre language=\"info\">" + "\n".join(dynamic_hints) + "</pre>"
    logger.info(f"Final dynamic hints for user {user_id}: {dynamic_hints}")
    cap = re.sub(r'<pre language="info">.*?</pre>', '', cap, flags=re.DOTALL)
    cap += f"{dynamic_hint_text}\n"
    return QualityMenuComposition(text=cap, keyboard_rows=keyboard_rows)


def _build_quality_menu_data_model(
    *,
    message,
    user_id: int,
    url: str,
    info: dict,
    cached_qualities,
    is_playlist: bool,
    playlist_range,
    tags_text: str,
    is_nsfw: bool,
    is_private_chat: bool,
    send_as_file: bool,
) -> QualityMenuDataModel:
    filters_state = get_filters(user_id)
    sel_codec = filters_state.get("codec", "avc1")
    sel_ext = filters_state.get("ext", "mp4")

    available_dubs = []
    lang_seen = set()
    for fmt in info.get("formats", []):
        if fmt.get("vcodec") == "none" and fmt.get("acodec") and fmt.get("language"):
            lang = fmt.get("language")
            if lang and lang not in lang_seen:
                lang_seen.add(lang)
                available_dubs.append(lang)
    has_dubs = len(available_dubs) > 1
    filters_state["has_dubs"] = has_dubs
    filters_state["available_dubs"] = sorted(available_dubs)
    if not has_dubs:
        filters_state["audio_lang"] = None
    _ASK_FILTERS[str(user_id)] = filters_state
    try:
        set_session_mkv_override(user_id, sel_ext == "mkv")
    except Exception:
        pass

    user_fixed_format = None
    try:
        user_args = get_user_args(user_id)
        user_video_format = user_args.get("video_format", "mp4")
        user_merge_format = user_args.get("merge_output_format", "mp4")
        if user_video_format != "mp4":
            user_fixed_format = user_video_format
        elif user_merge_format != "mp4":
            user_fixed_format = user_merge_format
    except Exception:
        pass

    quality_map = {}
    table_block = ""
    found_quality_keys = set()
    found_type = None

    if ("youtube.com" in url or "youtu.be" in url):
        for fmt in info.get("formats", []):
            if fmt.get("vcodec", "none") == "none" or not fmt.get("height") or not fmt.get("width"):
                continue
            vcodec = fmt.get("vcodec") or ""
            ext = fmt.get("ext") or ""
            if sel_codec == "avc1" and "avc1" not in vcodec:
                continue
            if sel_codec == "av01" and not vcodec.startswith("av01"):
                continue
            if sel_codec == "vp9" and "vp9" not in vcodec:
                continue
            target_ext = user_fixed_format if user_fixed_format else sel_ext
            if target_ext == "mp4" and ext != "mp4":
                continue
            if target_ext == "mkv" and ext == "mp4":
                continue
            if target_ext == "webm" and ext != "webm":
                continue
            if target_ext == "avi" and ext != "avi":
                continue
            if target_ext == "mov" and ext != "mov":
                continue
            if target_ext == "flv" and ext != "flv":
                continue
            if target_ext == "3gp" and ext not in ("3gp", "3g2"):
                continue
            if target_ext == "ogv" and ext not in ("ogv", "ogg"):
                continue
            if target_ext == "wmv" and ext != "wmv":
                continue
            if target_ext == "asf" and ext != "asf":
                continue
            w = fmt["width"]
            h = fmt["height"]
            quality_key = get_quality_by_min_side(w, h)
            if quality_key == "best":
                continue
            filesize = fmt.get("filesize") or fmt.get("filesize_approx")
            if quality_key not in quality_map or (filesize and filesize > (quality_map[quality_key].get("filesize") or 0)):
                quality_map[quality_key] = fmt

        table_lines = []
        for q in sorted(quality_map.keys(), key=sort_quality_key):
            fmt = quality_map[q]
            w = fmt.get("width")
            h = fmt.get("height")
            filesize = fmt.get("filesize") or fmt.get("filesize_approx")
            if filesize:
                if filesize >= 1024 * 1024 * 1024:
                    size_str = f"{round(filesize/1024/1024/1024, 2)}GB"
                else:
                    size_str = f"{round(filesize/1024/1024, 1)}MB"
            else:
                size_str = "—"
            dim_str = f" ({w}×{h})" if w and h else ""
            scissors = ""
            if get_user_split_size(user_id) and filesize:
                video_bytes = filesize
                if video_bytes > get_user_split_size(user_id):
                    n_parts = (video_bytes + get_user_split_size(user_id) - 1) // get_user_split_size(user_id)
                    scissors = f" ✂️{n_parts}"
            subs_enabled = is_subs_enabled(user_id)
            auto_mode = get_user_subs_auto_mode(user_id)
            subs_available = ""
            if subs_enabled:
                if sel_ext == "mkv":
                    subs_available = "💬"
                elif is_youtube_url(url) and w is not None and h is not None and min(int(w), int(h)) <= Config.MAX_SUB_QUALITY:
                    found_type = check_subs_availability(url, user_id, q, return_type=True)
                    if (auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal"):
                        temp_info = {"duration": info.get("duration"), "filesize": filesize, "filesize_approx": filesize}
                        if check_subs_limits(temp_info, q):
                            subs_available = "💬"
            if send_as_file:
                is_cached = False
                postfix = ""
            elif is_playlist and playlist_range:
                start, end = playlist_range
                has_negative = start < 0 or end < 0
                if has_negative:
                    if abs(start) < abs(end):
                        indices = list(range(start, end - 1, -1))
                    else:
                        indices = list(range(start, end + 1, 1))
                    try:
                        from DOWN_AND_UP.yt_dlp_hook import get_video_formats
                        temp_info = get_video_formats(url, user_id, 1, True, False, 1)
                        if temp_info and isinstance(temp_info, dict):
                            if "entries" in temp_info:
                                total_playlist_count = len(temp_info["entries"])
                            elif "_playlist_entries" in temp_info:
                                total_playlist_count = len(temp_info["_playlist_entries"])
                            else:
                                total_playlist_count = None
                            if total_playlist_count:
                                converted_indices = []
                                for neg_idx in indices:
                                    if neg_idx < 0:
                                        converted_indices.append(total_playlist_count + neg_idx + 1)
                                    else:
                                        converted_indices.append(neg_idx)
                                indices = converted_indices
                    except Exception as err:
                        logger.warning(f"Failed to convert negative indices for cache check: {err}")
                elif start > end:
                    indices = list(range(start, end - 1, -1))
                else:
                    indices = list(range(start, end + 1))
                n_cached = get_cached_playlist_count(get_clean_playlist_url(url), q, indices)
                total = len(indices)
                postfix = f" ({n_cached}/{total})"
                is_cached = n_cached > 0
            else:
                is_cached = q in cached_qualities
                if not is_cached:
                    video_page_url = (
                        info.get("webpage_url")
                        or info.get("original_url")
                        or info.get("url")
                        or info.get("canonical_url")
                        or url
                    )
                    if video_page_url != url and video_page_url:
                        try:
                            single_video_cached = get_cached_message_ids(video_page_url, q)
                            if single_video_cached:
                                is_cached = True
                                logger.info(f"🔍 [CACHE] Found single video in cache by unique URL: {video_page_url}, quality: {q}")
                        except Exception as err:
                            logger.warning(f"⚠️ [CACHE] Error while checking cache for a single video: {err}")
                postfix = ""
            need_subs = subs_enabled and ((auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal"))
            emoji = "🚀" if (is_cached and not need_subs and not is_nsfw) else "📹"
            sel_audio_lang = get_filters(user_id).get("audio_lang")
            audio_mark = f" 🗣{sel_audio_lang}" if sel_audio_lang else ""
            table_lines.append(f"{emoji}{q}{subs_available}{audio_mark}:  {size_str}{dim_str}{scissors}{postfix}")
            found_quality_keys.add(q)
        table_block = "\n".join(table_lines)
    else:
        import re as _re
        def infer_quality_key(fmt):
            w = fmt.get("width")
            h = fmt.get("height")
            if w and h:
                return get_quality_by_min_side(w, h)
            fid = fmt.get("format_id") or ""
            for pattern in (r"^(\d{3,4})p$", r"^url(\d{3,4})$", r"(\d{3,4})p"):
                match = _re.search(pattern, fid)
                if match:
                    try:
                        return f"{int(match.group(1))}p"
                    except Exception:
                        pass
            format_note = fmt.get("format_note") or ""
            match = _re.search(r"(\d{3,4})p", format_note)
            if match:
                try:
                    return f"{int(match.group(1))}p"
                except Exception:
                    pass
            url_field = fmt.get("url") or ""
            match = _re.search(r"(\d{3,4})p", url_field)
            if match:
                try:
                    return f"{int(match.group(1))}p"
                except Exception:
                    pass
            if w and h:
                return get_quality_by_min_side(w, h)
            return None

        def is_manifest(fmt):
            proto = (fmt.get("protocol") or "").lower()
            return "m3u8" in proto or "dash" in (fmt.get("format_note") or "").lower() or fmt.get("manifest_url") is not None

        def best_audio_kbps() -> int:
            kbps = 0
            for af in info.get("formats", []):
                if af.get("vcodec") == "none":
                    val = float(af["tbr"]) if af.get("tbr") else float(af["abr"]) if af.get("abr") else None
                    if val:
                        kbps = max(kbps, int(val))
            return kbps or 128

        _audio_kbps = best_audio_kbps()

        def default_video_kbps_for_height(height: int, fps: int | None, vcodec: str | None) -> int:
            baseline = {144: 250, 240: 400, 360: 800, 480: 1200, 540: 2000, 576: 2200, 720: 2500, 1080: 4500, 1440: 8000, 2160: 14000, 4320: 40000}
            chosen = baseline[sorted(baseline.keys())[0]]
            for hk in sorted(baseline.keys()):
                if height >= hk:
                    chosen = baseline[hk]
            if fps and fps > 30:
                chosen = int(chosen * 1.25)
            if vcodec and (vcodec.startswith("av01") or "vp9" in vcodec):
                chosen = int(chosen * 0.9)
            return max(chosen, 200)

        def sibling_video_kbps_for_quality(qk: str) -> int:
            best = 0
            for sf in info.get("formats", []):
                if infer_quality_key(sf) != qk:
                    continue
                val = float(sf["tbr"]) if sf.get("tbr") else float(sf["vbr"]) if sf.get("vbr") else 0.0
                if val:
                    best = max(best, int(val))
            return best

        def estimate_size_mb(fmt, qk: str, filesize_str: str = "") -> int:
            if fmt.get("filesize"):
                return int(fmt["filesize"]) // (1024 * 1024)
            if fmt.get("filesize_approx"):
                return int(fmt["filesize_approx"]) // (1024 * 1024)
            if filesize_str:
                try:
                    match = _re.match(r"^([\d.]+)\s*(KB|MB|GB)$", filesize_str.strip())
                    if match:
                        size_val = float(match.group(1))
                        unit = match.group(2)
                        if unit == "KB":
                            return max(1, int(size_val / 1024))
                        if unit == "MB":
                            return int(size_val)
                        if unit == "GB":
                            return int(size_val * 1024)
                except Exception:
                    pass
            duration = info.get("duration")
            if not duration:
                return 0
            kbps = float(fmt["tbr"]) if fmt.get("tbr") else float(fmt["vbr"]) if fmt.get("vbr") else float(fmt["abr"]) if fmt.get("abr") else 0.0
            if not kbps:
                kbps = float(sibling_video_kbps_for_quality(qk))
            if not kbps:
                try:
                    height = int((qk or "0p").rstrip("p"))
                except Exception:
                    height = fmt.get("height") or 0
                kbps = float(default_video_kbps_for_height(int(height or 0), int(fmt.get("fps") or 30), fmt.get("vcodec") or ""))
            if (fmt.get("acodec") in (None, "", "none")) or (not fmt.get("abr")):
                kbps += float(_audio_kbps)
            try:
                mb = (kbps * float(duration) * 125) / (1024 * 1024)
                return 1 if mb and 0 < mb < 1 else int(round(mb))
            except Exception:
                return 0

        for fmt in info.get("formats", []):
            if fmt.get("vcodec") == "none" and (fmt.get("audio_ext") or "") != "none":
                continue
            if user_fixed_format:
                ext = fmt.get("ext") or ""
                if user_fixed_format == "mp4" and ext != "mp4":
                    continue
                if user_fixed_format == "webm" and ext != "webm":
                    continue
                if user_fixed_format == "mkv" and ext == "mp4":
                    continue
                if user_fixed_format == "avi" and ext != "avi":
                    continue
                if user_fixed_format == "mov" and ext != "mov":
                    continue
                if user_fixed_format == "flv" and ext != "flv":
                    continue
                if user_fixed_format == "3gp" and ext not in ("3gp", "3g2"):
                    continue
                if user_fixed_format == "ogv" and ext not in ("ogv", "ogg"):
                    continue
                if user_fixed_format == "wmv" and ext != "wmv":
                    continue
                if user_fixed_format == "asf" and ext != "asf":
                    continue
            vcodec = fmt.get("vcodec") or ""
            if sel_codec == "avc1" and "avc1" not in vcodec:
                continue
            if sel_codec == "av01" and not vcodec.startswith("av01"):
                continue
            if sel_codec == "vp9" and "vp9" not in vcodec:
                continue
            ext = fmt.get("ext") or ""
            target_ext = user_fixed_format if user_fixed_format else sel_ext
            if target_ext == "mp4" and ext != "mp4":
                continue
            if target_ext == "mkv" and ext == "mp4":
                continue
            if target_ext == "webm" and ext != "webm":
                continue
            qk = infer_quality_key(fmt)
            if not qk or qk == "best":
                continue
            w_val = fmt.get("width") or 0
            h_val = fmt.get("height") or 0
            if not h_val:
                try:
                    h_val = int(qk.rstrip("p"))
                except Exception:
                    h_val = 0
            if not w_val and h_val:
                w_val = int(h_val * 16 / 9)
            candidate = {
                "w": w_val,
                "h": h_val,
                "size_mb": estimate_size_mb(fmt, qk, fmt.get("filesize_str") or ""),
                "format_id": fmt.get("format_id") or "",
                "protocol": fmt.get("protocol") or "",
                "filesize_str": fmt.get("filesize_str") or "",
            }
            prev = quality_map.get(qk)
            if not prev:
                quality_map[qk] = candidate
            else:
                prev_has_dims = bool(prev.get("w")) and bool(prev.get("h"))
                curr_has_dims = bool(candidate.get("w")) and bool(candidate.get("h"))
                prev_has_size = prev.get("size_mb", 0) > 0
                curr_has_size = candidate.get("size_mb", 0) > 0
                prev_manifest = is_manifest(prev)
                curr_manifest = is_manifest(candidate)
                def better(a_has_dims, a_has_size, a_manifest, a_size, b_has_dims, b_has_size, b_manifest, b_size):
                    if a_has_dims != b_has_dims:
                        return a_has_dims
                    if a_has_size != b_has_size:
                        return a_has_size
                    if a_manifest != b_manifest:
                        return not a_manifest
                    return a_size > b_size
                if better(curr_has_dims, curr_has_size, curr_manifest, candidate["size_mb"], prev_has_dims, prev_has_size, prev_manifest, prev.get("size_mb", 0)):
                    quality_map[qk] = candidate

        if not quality_map:
            video_formats = [fmt for fmt in info.get("formats", []) if fmt.get("vcodec") != "none"]
            if video_formats:
                resolution_groups = {}
                for fmt in video_formats:
                    w = fmt.get("width", 0)
                    h = fmt.get("height", 0)
                    if w and h:
                        res_key = f"{w}x{h}"
                        if res_key not in resolution_groups or (fmt.get("filesize") or 0) > (resolution_groups[res_key].get("filesize") or 0):
                            resolution_groups[res_key] = fmt
                for _, fmt in resolution_groups.items():
                    w, h = fmt.get("width", 0), fmt.get("height", 0)
                    if w and h:
                        qk = get_quality_by_min_side(w, h)
                        if qk not in quality_map:
                            quality_map[qk] = {
                                "w": w,
                                "h": h,
                                "size_mb": estimate_size_mb(fmt, qk, fmt.get("filesize_str") or ""),
                                "format_id": fmt.get("format_id") or "",
                                "protocol": fmt.get("protocol") or "",
                                "filesize_str": fmt.get("filesize_str") or "",
                            }
        table_lines = []
        for quality_key in sorted(quality_map.keys(), key=sort_quality_key):
            entry = quality_map[quality_key]
            w, h, size_val = entry["w"], entry["h"], entry["size_mb"]
            found_quality_keys.add(quality_key)
            size_str = f"{round(size_val/1024, 1)}GB" if size_val and size_val >= 1024 else (f"{size_val}MB" if size_val else "—")
            dim_str = f" ({w}×{h})" if w and h else ""
            scissors = ""
            if get_user_split_size(user_id) and size_val:
                video_bytes = size_val * 1024 * 1024
                if video_bytes > get_user_split_size(user_id):
                    n_parts = (video_bytes + get_user_split_size(user_id) - 1) // get_user_split_size(user_id)
                    scissors = f" ✂️{n_parts}"
            table_lines.append(f"📹{quality_key}:  {size_str}{dim_str}{scissors}")
        table_block = "\n".join(table_lines)

    title = info.get("title", "Video")
    cap = f"<b>{title}</b>\n"
    if user_fixed_format:
        cap += f"\n<b>{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_FIXED_VIA_ARGS_MSG}: {user_fixed_format.upper()}</b>\n"

    sel_audio_lang = filters_state.get("audio_lang")
    subs_enabled = is_subs_enabled(user_id)
    subs_lang = get_user_subs_language(user_id) if subs_enabled else None
    summary_parts = []
    if sel_audio_lang:
        summary_parts.append(f"🗣 {sel_audio_lang}")
    if subs_enabled and subs_lang:
        summary_parts.append(f"💬 {subs_lang}")
    if summary_parts:
        cap += "<blockquote>" + " | ".join(summary_parts) + "</blockquote>\n"

    is_youtube = ("youtube.com" in url or "youtu.be" in url)
    if is_youtube:
        uploader = info.get("uploader") or ""
        view_count = info.get("view_count")
        like_count = info.get("like_count")
        channel_follower_count = info.get("channel_follower_count")
        duration = info.get("duration")
        upload_date = info.get("upload_date")
        title_val = info.get("title") or ""
        duration_str = TimeFormatter(duration * 1000) if duration else ""
        upload_date_str = ""
        if upload_date and len(str(upload_date)) == 8:
            try:
                upload_date_str = datetime.strptime(str(upload_date), "%Y%m%d").strftime("%d.%m.%Y")
            except Exception:
                upload_date_str = str(upload_date)
        views_str = f"👁 {view_count:,}" if view_count is not None else ""
        likes_str = f"❤️ {like_count:,}" if like_count is not None else ""
        subs_str = f"👥 {channel_follower_count:,}" if channel_follower_count is not None else ""
        meta_lines = []
        if uploader:
            ch_line = f"📺 <b>{uploader}</b>\n"
            if subs_str:
                ch_line += f"<blockquote>{subs_str}</blockquote>\n"
            meta_lines.append(ch_line)
        if title_val:
            meta_lines.append(f"<b>{title_val}</b>")
        date_dur_line = ""
        if upload_date_str:
            date_dur_line += f"📅 {upload_date_str}"
        if duration_str:
            date_dur_line += f"  ⏱️ {duration_str}" if date_dur_line else f"⏱️ {duration_str}"
        if date_dur_line:
            meta_lines.append(f"<blockquote>{date_dur_line}</blockquote>")
        stat_line = views_str
        if likes_str:
            stat_line = f"{stat_line}  {likes_str}" if stat_line else likes_str
        if stat_line:
            meta_lines.append(f"<blockquote>{stat_line}</blockquote>")
        cap = "\n".join(meta_lines) + "\n\n"
    else:
        title_ny = info.get("title") or ""
        uploader_ny = info.get("uploader") or ""
        duration_ny = info.get("duration")
        duration_str_ny = TimeFormatter(duration_ny * 1000) if duration_ny else ""
        meta_lines_ny = []
        if uploader_ny:
            meta_lines_ny.append(f"📺 <b>{uploader_ny}</b>")
        if duration_str_ny:
            meta_lines_ny.append(f"<blockquote>⏱️ {duration_str_ny}</blockquote>")
        if title_ny:
            meta_lines_ny.append(f"\n<b>{title_ny}</b>")
        cap = ("\n".join(meta_lines_ny) + "\n\n") if meta_lines_ny else ""

    if table_block:
        cap += f"<blockquote>{table_block}</blockquote>\n"

    subs_count_info = ""
    dubs_count_info = ""
    if is_subs_enabled(user_id) and is_subs_always_ask(user_id):
        try:
            from COMMANDS.subtitles_cmd import get_or_compute_subs_langs
            normal_subs, auto_subs = get_or_compute_subs_langs(user_id, url)
            total_subs = len(set(normal_subs) | set(auto_subs))
            if total_subs > 0:
                subs_count_info = f"{safe_get_messages(user_id).ALWAYS_ASK_SUBTITLES_MSG}: {total_subs} available\n"
        except Exception as err:
            logger.error(f"Error getting subtitles count: {err}")
    available_dubs = filters_state.get("available_dubs", [])
    if len(available_dubs) > 1:
        dubs_count_info = f"{safe_get_messages(user_id).ALWAYS_ASK_DUBBED_AUDIO_MSG}: {len(available_dubs)} languages"
    info_parts = []
    if subs_count_info:
        info_parts.append(subs_count_info)
    if dubs_count_info:
        info_parts.append(dubs_count_info)
    if info_parts:
        cap += f"<blockquote>{''.join(info_parts)}</blockquote>\n"
    if tags_text:
        cap += f"{tags_text}"

    if len(cap) > 1024:
        if is_youtube:
            cap = cap[:1021] + "..."
        else:
            cap = cap[:1021] + "..."

    return QualityMenuDataModel(
        cap=cap,
        quality_map=quality_map,
        found_quality_keys=found_quality_keys,
        filters_state=filters_state,
        selected_codec=sel_codec,
        selected_ext=sel_ext,
        user_fixed_format=user_fixed_format,
        found_subtitle_type=found_type,
    )


def _emit_quality_menu_render_plan(app, message, *, cb, proc_msg, user_id: int, render_plan: QualityMenuRenderPlan) -> None:
    if cb is not None and getattr(cb, "message", None):
        try:
            if cb.message.photo:
                cb.edit_message_caption(
                    caption=render_plan.text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=render_plan.reply_markup,
                )
            else:
                cb.edit_message_text(
                    text=render_plan.text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=render_plan.reply_markup,
                )
        except Exception as edit_error:
            logger.warning(f"Failed to edit message for callback: {edit_error}")
            try:
                if render_plan.can_send_thumb_menu:
                    app.send_photo(
                        user_id,
                        render_plan.thumb_path,
                        caption=render_plan.text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=render_plan.reply_markup,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        has_spoiler=should_apply_spoiler(
                            user_id,
                            render_plan.is_nsfw,
                            getattr(message.chat, "type", None) == enums.ChatType.PRIVATE,
                        ),
                    )
                else:
                    app.send_message(
                        user_id,
                        render_plan.text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=render_plan.reply_markup,
                        reply_parameters=ReplyParameters(message_id=message.id),
                    )
            except Exception as fallback_error:
                logger.error(f"Failed to send fallback message: {fallback_error}")
        if proc_msg:
            try:
                safe_delete_messages(chat_id=cb.message.chat.id, message_ids=[proc_msg.id])
            except Exception:
                pass
        return

    if proc_msg:
        try:
            safe_delete_messages(chat_id=user_id, message_ids=[proc_msg.id])
        except Exception:
            pass
    try:
        if render_plan.can_send_thumb_menu:
            app.send_photo(
                user_id,
                render_plan.thumb_path,
                caption=render_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=render_plan.reply_markup,
                reply_parameters=ReplyParameters(message_id=message.id),
                has_spoiler=should_apply_spoiler(
                    user_id,
                    render_plan.is_nsfw,
                    getattr(message.chat, "type", None) == enums.ChatType.PRIVATE,
                ),
            )
        else:
            app.send_message(
                user_id,
                render_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=render_plan.reply_markup,
                reply_parameters=ReplyParameters(message_id=message.id),
            )
    except Exception as keyboard_error:
        logger.warning(f"Failed to send with keyboard, retrying without: {keyboard_error}")
        if render_plan.can_send_thumb_menu:
            app.send_photo(
                user_id,
                render_plan.thumb_path,
                caption=render_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_parameters=ReplyParameters(message_id=message.id),
                has_spoiler=should_apply_spoiler(
                    user_id,
                    render_plan.is_nsfw,
                    getattr(message.chat, "type", None) == enums.ChatType.PRIVATE,
                ),
            )
        else:
            app.send_message(
                user_id,
                render_plan.text,
                parse_mode=enums.ParseMode.HTML,
                reply_parameters=ReplyParameters(message_id=message.id),
            )


def _build_always_ask_gallery_fallback_prompt(
    message,
    *,
    url: str,
    user_id: int,
    original_error: str,
    original_text: str,
) -> AlwaysAskGalleryFallbackPrompt:
    _, video_start_with, video_end_with, _, _, _, _ = extract_url_range_tags(original_text or "")

    from DOWN_AND_UP.gallery_dl_hook import get_total_media_count

    detected_total = get_total_media_count(url, user_id, use_proxy=False)
    if detected_total and detected_total > 0:
        logger.info(
            "Fallback detected %s media items for Always Ask gallery recommendation",
            detected_total,
        )

    if video_start_with and video_end_with and (video_start_with != 1 or video_end_with != 1):
        range_info = f" (range {video_start_with}-{video_end_with})"
        range_examples = (
            f"• For your range: <code>/img {video_start_with}-{video_end_with}</code>\n"
        )
    else:
        range_info = ""
        range_examples = ""

    fallback_message = (
        f"{safe_get_messages(user_id).ALWAYS_ASK_YTDLP_CANNOT_PROCESS_MSG}{range_info}</b>\n\n"
        f"<b>Error:</b> <code>{original_error[:200]}{'...' if len(original_error) > 200 else ''}</code>\n\n"
        f"{safe_get_messages(user_id).ALWAYS_ASK_SYSTEM_RECOMMENDS_GALLERY_DL_MSG}\n\n"
        f"{safe_get_messages(user_id).ALWAYS_ASK_OPTIONS_MSG}\n"
        f"{range_examples}"
        f"{safe_get_messages(user_id).ALWAYS_ASK_FOR_IMAGE_GALLERIES_MSG}\n"
        f"{safe_get_messages(user_id).ALWAYS_ASK_FOR_SINGLE_IMAGES_MSG}\n\n"
        f"{safe_get_messages(user_id).ALWAYS_ASK_GALLERY_DL_WORKS_BETTER_MSG}"
    )

    chat_id = message.chat.id
    original_start = video_start_with
    original_end = video_end_with
    if (video_start_with == 1 and video_end_with == 1) and hasattr(message, "text"):
        range_match = re.search(r"(https?://[^\s\*#]+)\*(\d+)\*(\d+)", message.text)
        if range_match:
            original_start = int(range_match.group(2))
            original_end = int(range_match.group(3))
            logger.info(
                "[FALLBACK DEBUG] Extracted range from original message: %s-%s",
                original_start,
                original_end,
            )

    if original_start and original_end and (original_start != 1 or original_end != 1):
        url_data = f"{url}|{original_start}|{original_end}|{chat_id}"
        logger.info(
            "[FALLBACK DEBUG] Using extracted range for gallery prompt: %s-%s",
            original_start,
            original_end,
        )
    elif detected_total and detected_total > 0:
        url_data = f"{url}|1|{detected_total}|{chat_id}"
        logger.info("[FALLBACK DEBUG] Using detected_total for gallery prompt: 1-%s", detected_total)
    else:
        url_data = f"{url}|1|1|{chat_id}"
        logger.info("[FALLBACK DEBUG] Using default range for gallery prompt: 1-1")

    return AlwaysAskGalleryFallbackPrompt(
        message_text=fallback_message,
        callback_data=create_safe_callback_data("fallback_gallery_dl", url_data),
    )


def _determine_ask_quality_menu_source_decision(
    message,
    *,
    url: str,
    user_id: int,
    original_text: str,
    playlist_start_index: int,
    is_playlist: bool,
    playlist_range,
) -> AlwaysAskMenuSourceDecision:
    info = load_ask_info(user_id, url)
    if info:
        logger.info("✅ [DEBUG] Using cached ask info for quality menu")
        return AlwaysAskMenuSourceDecision(mode="video_info", info=info)

    logger.info("🔍 [DEBUG] Loading video info via get_video_formats")
    logger.info(f"   url: {url}")
    logger.info(f"   user_id: {user_id}")
    logger.info(f"   playlist_start_index: {playlist_start_index}")
    logger.info("   cookies_already_checked: True")

    playlist_end_index = playlist_range[1] if is_playlist and playlist_range else None
    from DOWN_AND_UP.yt_dlp_hook import get_video_formats

    try:
        info = get_video_formats(
            url,
            user_id,
            playlist_start_index,
            cookies_already_checked=True,
            playlist_end_index=playlist_end_index,
        )
    except Exception as error:
        logger.error(f"❌ [DEBUG] Error in get_video_formats: {error}")
        logger.error(f"   Error type: {type(error)}")
        logger.error(f"   Error string: {str(error)}")
        raise
    logger.info("✅ [DEBUG] get_video_formats completed successfully")
    logger.info(f"   info type: {type(info)}")
    if isinstance(info, dict):
        logger.info(f"   info keys: {list(info.keys())}")
        if "duration" in info:
            logger.info(f"   duration: {info['duration']} (type: {type(info['duration'])})")
        if "formats" in info:
            logger.info(f"   formats count: {len(info.get('formats', []))}")

    if isinstance(info, dict) and info.get("error") == "LIVE_STREAM_DETECTED":
        from CONFIG.limits import LimitsConfig

        if LimitsConfig.ENABLE_LIVE_STREAM_BLOCKING:
            logger.warning("Live stream detected in ask_quality_menu for user %s: %s", user_id, url)
            live_stream_message = (
                "🚫 <b>Live Stream Detected</b>\n\n"
                "Downloading of ongoing or infinite live streams is not allowed.\n\n"
                "<blockquote>Please wait for the stream to end and try downloading again when:\n"
                "• The stream duration is known\n"
                "• The stream has finished\n"
                "• You can see the final video length</blockquote>\n\n"
                "Once the stream is completed, you'll be able to download it as a regular video."
            )
            return AlwaysAskMenuSourceDecision(mode="terminal_error", error_text=live_stream_message)

    if isinstance(info, dict) and info.get("error") == "TIKTOK_PRIVATE_ACCOUNT":
        logger.info("TikTok private account detected in ask_quality_menu for user %s: %s", user_id, url)
        username_match = re.search(r"tiktok\.com/@([^/?]+)", url)
        username = username_match.group(1) if username_match else "unknown"
        return AlwaysAskMenuSourceDecision(
            mode="terminal_error",
            error_text=safe_get_messages(user_id).TIKTOK_PRIVATE_ACCOUNT_MSG.format(username=username),
        )

    if isinstance(info, dict) and info.get("error") == "FALLBACK_TO_GALLERY_DL":
        logger.info("Fallback to gallery-dl recommended in ask_quality_menu for user %s: %s", user_id, url)
        prompt = _build_always_ask_gallery_fallback_prompt(
            message,
            url=url,
            user_id=user_id,
            original_error=info.get("original_error", "Unknown error"),
            original_text=original_text,
        )
        return AlwaysAskMenuSourceDecision(mode="gallery_fallback_prompt", gallery_fallback_prompt=prompt)

    try:
        save_ask_info(user_id, url, info)
    except Exception:
        pass

    return AlwaysAskMenuSourceDecision(mode="video_info", info=info)


def _determine_ask_quality_menu_failure_decision(
    message,
    *,
    url: str,
    tags,
    proc_msg,
    user_id: int,
    error: Exception,
) -> AlwaysAskMenuFailureDecision:
    messages = safe_get_messages(user_id)
    error_text = str(error)
    gallery_like_errors = (
        messages.ALWAYS_ASK_NO_VIDEOS_FOUND_IN_PLAYLIST_MSG,
        messages.ALWAYS_ASK_UNSUPPORTED_URL_MSG,
        messages.ALWAYS_ASK_NO_VIDEO_COULD_BE_FOUND_MSG,
        messages.ALWAYS_ASK_NO_VIDEO_FOUND_MSG,
        messages.ALWAYS_ASK_NO_MEDIA_FOUND_MSG,
        messages.ALWAYS_ASK_THIS_TWEET_DOES_NOT_CONTAIN_MSG,
    )
    if not any(token in error_text for token in gallery_like_errors):
        return AlwaysAskMenuFailureDecision(mode="cached_menu")

    nsfw_enabled = bool(getattr(Config, "NSFW_CHECK_ENABLED", True))
    is_nsfw = is_porn(url, "", "", None) if nsfw_enabled else False
    user_forced_nsfw = any(t.lower() in ("#nsfw", "#porn") for t in (tags or [])) if nsfw_enabled else False
    if user_forced_nsfw:
        is_nsfw = True

    original_text = message.text or message.caption or ""
    logger.info("[ASKQ FALLBACK DEBUG] original_text: %s", original_text)
    range_url_match = re.search(r"(https?://[^\s\*#]+)\*(\d+)\*(\d+)", original_text)
    if range_url_match:
        parsed_url = range_url_match.group(1)
        start_range = int(range_url_match.group(2))
        end_range = int(range_url_match.group(3))
        logger.info(
            "[ASKQ FALLBACK DEBUG] FOUND RANGE: %s with range %s-%s",
            parsed_url,
            start_range,
            end_range,
        )
    else:
        url_match = re.search(r"https?://[^\s\*#]+", original_text)
        parsed_url = url_match.group(0) if url_match else original_text
        start_range = 1
        end_range = 1
        logger.info("[ASKQ FALLBACK DEBUG] NO RANGE FOUND, using url: %s", parsed_url)

    if start_range != 1 or end_range != 1:
        fallback_text = f"/img {start_range}-{end_range} {parsed_url}"
        logger.info(
            "%s: *%s*%s -> %s-%s, fallback_text: %s",
            LoggerMsg.ALWAYS_ASK_FALLBACK_CONVERTING_RANGE_LOG_MSG,
            start_range,
            end_range,
            start_range,
            end_range,
            fallback_text,
        )
    else:
        fallback_text = f"/img {parsed_url}"
        logger.info("%s: %s", LoggerMsg.ALWAYS_ASK_FALLBACK_NO_RANGE_DETECTED_LOG_MSG, fallback_text)

    if tags:
        fallback_text += f" {' '.join(tags)}"
    fallback_tags = list(tags) if tags else []
    fallback_tags_text = " ".join(fallback_tags)
    if is_nsfw and "#nsfw" not in fallback_text.lower():
        fallback_text += " #nsfw"
        if "#nsfw" not in fallback_tags:
            fallback_tags.append("#nsfw")
        fallback_tags_text = " ".join(fallback_tags)
        logger.info("%s: %s", LoggerMsg.ALWAYS_ASK_FALLBACK_ADDED_NSFW_TAG_LOG_MSG, url)

    fallback_branch = gallery_fallback_branch(
        None,
        origin="always_ask_menu",
        reason="menu_quality_detection_fallback",
    )
    fallback_task = make_runtime_task(
        user_id=user_id,
        source_message_id=getattr(message, "id", None),
        url=parsed_url,
        tags_text=fallback_tags_text,
        tags=fallback_tags or None,
        video_count=max(1, end_range - start_range + 1),
        video_start_with=start_range,
        proc_msg_id=getattr(proc_msg, "id", None) if proc_msg else None,
        branch_selection_result=fallback_branch,
    )
    return AlwaysAskMenuFailureDecision(
        mode="gallery_fallback_dispatch",
        fallback_text=fallback_text,
        runtime_task=fallback_task,
    )


def _emit_ask_quality_menu_terminal_error(app, message, user_id: int, proc_msg, url: str) -> None:
    error_text = (
        f"{safe_get_messages(user_id).ALWAYS_ASK_ERROR_RETRIEVING_VIDEO_INFO_MSG}\n"
        f"<blockquote>{safe_get_messages(user_id).ALWAYS_ASK_ERROR_RETRIEVING_VIDEO_INFO_SHORT_MSG}</blockquote>\n\n"
        f"{safe_get_messages(user_id).ALWAYS_ASK_TRY_CLEAN_COMMAND_MSG}"
    )
    try:
        if proc_msg:
            result = app.edit_message_text(
                chat_id=user_id,
                message_id=proc_msg.id,
                text=error_text,
                parse_mode=enums.ParseMode.HTML,
            )
            if result is not None:
                log_error_to_channel(
                    message,
                    safe_get_messages(user_id).ALWAYS_ASK_MENU_ERROR_LOG_MSG.format(
                        url=url,
                        error=safe_get_messages(user_id).ALWAYS_ASK_ERROR_RETRIEVING_VIDEO_INFO_SHORT_MSG,
                    ),
                    url,
                )
                return
    except Exception as edit_error:
        logger.error(f"Error editing processing message: {edit_error}")

    logger.error(
        "Always Ask menu error for user %s: %s",
        user_id,
        safe_get_messages(user_id).ALWAYS_ASK_ERROR_RETRIEVING_VIDEO_INFO_SHORT_MSG,
    )
    safe_send_message(user_id, error_text, parse_mode=enums.ParseMode.HTML, message=message)
    log_error_to_channel(
        message,
        safe_get_messages(user_id).ALWAYS_ASK_MENU_ERROR_LOG_MSG.format(
            url=url,
            error=safe_get_messages(user_id).ALWAYS_ASK_ERROR_RETRIEVING_VIDEO_INFO_SHORT_MSG,
        ),
        url,
    )

# @reply_with_keyboard
def delete_processing_message(app, user_id, proc_msg):
    """Delete processing message if it exists"""
    if proc_msg:
        try:

            logger.info(f"Deleting processing message {proc_msg.id} for user {user_id}")
            from HELPERS.safe_messeger import safe_delete_messages
            safe_delete_messages(chat_id=user_id, message_ids=[proc_msg.id], revoke=True)
            logger.info(f"Successfully deleted processing message {proc_msg.id}")
            # Clear from cache after successful deletion
            clear_user_proc_msg(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete processing message: {e}")
    else:
        logger.warning(f"proc_msg is None for user {user_id}, cannot delete processing message")

def ask_quality_menu(app, message, url, tags, playlist_start_index=1, cb=None, download_dir=None):  # pyright: ignore[reportGeneralTypeIssues]
    """Show quality selection menu for video"""
    # Detailed debug logging
    logger.info("🔍 [DEBUG] ask_quality_menu called with parameters:")
    logger.info(f"   url: {url}")
    logger.info(f"   tags: {tags}")
    logger.info(f"   playlist_start_index: {playlist_start_index}")
    logger.info(f"   download_dir: {download_dir}")
    
    # Global guard: messages must never be undefined
    try:
        messages = safe_get_messages(message.chat.id)
        logger.info("✅ [DEBUG] messages initialized successfully")
    except Exception as e:
        logger.error(f"❌ [DEBUG] Failed to initialize messages: {e}")
        # As a last resort, initialize via the standard translation system
        messages = safe_get_messages(message.chat.id)
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = message.chat.id
    proc_msg = None
    # Defensive init to avoid UnboundLocalError in rare branches
    action_buttons = []
    
    # Create download directory if not provided
    if download_dir is None:
        try:
            user_dir = os.path.join("users", str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Generate download directory name based on URL
            dir_name = generate_download_dir_name(url)
            download_dir = os.path.join(user_dir, "downloads", dir_name)
            os.makedirs(download_dir, exist_ok=True)
            logger.info(f"Created download directory for ask_quality_menu: {download_dir}")
            # Store download directory for this user session
            set_user_download_dir(user_id, download_dir)
            # Copy cookies to download directory
            copy_cookies_to_download_dir(user_id, download_dir)
        except Exception as e:
            logger.warning(f"Failed to create download directory in ask_quality_menu: {e}")
            download_dir = None
    
    # Clean up old format cache files before starting
    try:
        user_dir = os.path.join("users", str(user_id))
        create_directory(user_dir)
        
        # Remove old format cache files except current one
        import glob
        # Use download directory if available, otherwise fallback to user directory
        if download_dir and os.path.exists(download_dir):
            format_cache_pattern = os.path.join(download_dir, "formats_cache_*.json")
            current_cache_file = os.path.join(download_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
        else:
            format_cache_pattern = os.path.join(user_dir, "formats_cache_*.json")
            current_cache_file = os.path.join(user_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
        old_cache_files = glob.glob(format_cache_pattern)
        
        for cache_file in old_cache_files:
            if cache_file != current_cache_file:  # Don't delete current cache
                try:
                    os.remove(cache_file)
                    logger.info(f"Cleaned up old format cache: {cache_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove old cache file {cache_file}: {e}")
                
        if len(old_cache_files) > 1:  # More than just current cache
            logger.info(f"Cleaned up {len(old_cache_files) - 1} old format cache files for user {user_id}")
    except Exception as e:
        logger.warning(f"Error cleaning up old format cache files: {e}")
    
    # Early FloodWait check: if there is a saved waiting time, inform user and try to clear on success
    try:
        user_dir = os.path.join("users", str(user_id))
        flood_time_file = os.path.join(user_dir, "flood_wait.txt")
        if os.path.exists(flood_time_file):
            with open(flood_time_file, 'r') as f:
                try:
                    wait_time = int(f.read().strip())
                except Exception:
                    wait_time = None
            if wait_time is not None:
                hours = wait_time // 3600
                minutes = (wait_time % 3600) // 60
                seconds = wait_time % 60
                time_str = f"{hours}h {minutes}m {seconds}s"
                proc_msg = app.send_message(user_id, safe_get_messages(user_id).RATE_LIMIT_WITH_TIME_MSG.format(time=time_str))
            else:
                proc_msg = app.send_message(user_id, safe_get_messages(user_id).RATE_LIMIT_NO_TIME_MSG)
            try:
                app.edit_message_text(chat_id=user_id, message_id=proc_msg.id, text=safe_get_messages(user_id).DOWNLOAD_STARTED_MSG, parse_mode=enums.ParseMode.HTML)
                try:
                    from HELPERS.safe_messeger import schedule_delete_message
                    schedule_delete_message(user_id, proc_msg.id, delete_after_seconds=5)
                except Exception:
                    pass
                if os.path.exists(flood_time_file):
                    os.remove(flood_time_file)
            except FloodWait as e:
                # Keep/refresh timer and exit early
                try:
                    os.makedirs(user_dir, exist_ok=True)
                    with open(flood_time_file, 'w') as f:
                        f.write(str(e.value))
                except Exception:
                    pass
                return
            except Exception:
                return
            # If edit succeeded, proceed as usual (no flood)
            proc_msg = None
    except Exception:
        pass
    found_type = None
    # Clean the cache of subtitles only on initial open (when no callback provided).
    # On filter toggles (when cb is not None), we KEEP the cache to avoid re-fetching subtitles.
    if cb is None:
        clear_subs_check_cache()
    # --- checking the range of the range for Always ASK Menu ---
    original_text = message.text or message.caption or ""
    is_playlist = is_playlist_with_range(original_text)
    if is_playlist:
        _, video_start_with, video_end_with, _, _, _, _ = extract_url_range_tags(original_text)
        if not check_playlist_range_limits(url, video_start_with, video_end_with, app, message):
            return
        # Update playlist_start_index from original_text if a range is present.
        # This guarantees negative indices are handled correctly.
        # Check that a range exists (not 1-1) or that indices are negative.
        has_range = (video_start_with != 1 or video_end_with != 1) or (video_start_with < 0 or video_end_with < 0)
        if video_start_with is not None and has_range:
            playlist_start_index = video_start_with
            logger.info(f"🔍 [DEBUG] Updated playlist_start_index from original_text: {playlist_start_index}, video_end_with: {video_end_with}")
    try:
        # Check if subtitles are included
        subs_enabled = is_subs_enabled(user_id)
        processing_text = safe_get_messages(user_id).AA_PROCESSING_WAIT_MSG if subs_enabled else safe_get_messages(user_id).AA_PROCESSING_MSG
        
        # Only send new processing message if this is the initial menu open (no callback)
        # If callback is provided, we should NOT edit the message here - let the final logic handle it
        if cb is None:
            proc_msg = app.send_message(user_id, processing_text, reply_parameters=ReplyParameters(message_id=message.id), reply_markup=get_main_reply_keyboard())
            # Save processing message to cache for deletion when download starts
            set_user_proc_msg(user_id, proc_msg)
        else:
            # For callback queries, we don't edit the message here - let the final logic handle it
            # This prevents the menu from being replaced with "🔎 Analyzing..." temporarily
            proc_msg = None
        original_text = message.text or message.caption or ""
        logger.info(f"🔍 [DEBUG] ask_quality_menu: original_text='{original_text}'")
        is_playlist = is_playlist_with_range(original_text)
        logger.info(f"🔍 [DEBUG] ask_quality_menu: is_playlist={is_playlist}")
        playlist_range = None
        # Check if user has send_as_file enabled
        user_args = get_user_args(user_id)
        send_as_file = user_args.get("send_as_file", False)
        
        if is_playlist:
            _, video_start_with, video_end_with, _, _, _, _ = extract_url_range_tags(original_text)
            logger.info(f"🔍 [DEBUG] ask_quality_menu: after extract_url_range_tags: video_start_with={video_start_with}, video_end_with={video_end_with}")
            playlist_range = (video_start_with, video_end_with)
            cached_qualities = get_cached_playlist_qualities(get_clean_playlist_url(url)) if not send_as_file else set()
        else:
            cached_qualities = get_cached_qualities(url) if not send_as_file else set()
        source_decision = _determine_ask_quality_menu_source_decision(
            message,
            url=url,
            user_id=user_id,
            original_text=original_text,
            playlist_start_index=playlist_start_index,
            is_playlist=is_playlist,
            playlist_range=playlist_range,
        )
        if source_decision.mode == "terminal_error":
            send_error_to_user(message, source_decision.error_text)
            return
        if source_decision.mode == "gallery_fallback_prompt":
            prompt = source_decision.gallery_fallback_prompt
            keyboard = [
                [
                    InlineKeyboardButton(
                        safe_get_messages(user_id).ALWAYS_ASK_TRY_GALLERY_DL_BUTTON_MSG,
                        callback_data=prompt.callback_data,
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            app.send_message(
                message.chat.id,
                prompt.message_text,
                reply_markup=reply_markup,
                reply_parameters=ReplyParameters(message_id=message.id),
            )
            return
        info = source_decision.info
        title = info.get('title', 'Video')
        video_id = info.get('id')
        tags_text = generate_final_tags(url, tags, info)
        # Determine NSFW to hide preview under spoiler in Always Ask Menu too
        try:
            is_nsfw = isinstance(tags_text, str) and ('#nsfw' in tags_text.lower())
        except Exception:
            is_nsfw = False
        
        # Check if we're in a private chat (paid media only works in private chats)
        is_private_chat = getattr(message.chat, "type", None) == enums.ChatType.PRIVATE
        thumb_path = None
        # Use download directory if available, otherwise fallback to user directory
        download_dir = get_user_download_dir(user_id)
        if download_dir and os.path.exists(download_dir):
            thumb_dir = download_dir
        else:
            thumb_dir = os.path.join("users", str(user_id))
            create_directory(thumb_dir)
        
        # For playlists, download thumbnails for all videos
        playlist_entries = info.get('_playlist_entries')
        if is_playlist and playlist_entries and isinstance(playlist_entries, list):
            logger.info(f"🔍 [DEBUG] Playlist detected, downloading thumbnails for {len(playlist_entries)} videos")
            for entry in playlist_entries:
                if not entry:
                    continue
                entry_id = entry.get('id')
                entry_url = entry.get('url') or entry.get('webpage_url')
                if not entry_id:
                    continue
                
                # For YouTube, use the dedicated downloader
                if ("youtube.com" in url or "youtu.be" in url) and entry_id:
                    entry_thumb_path = os.path.join(thumb_dir, f"yt_thumb_{entry_id}.jpg")
                    try:
                        # Use the specific video's URL if available
                        entry_video_url = entry_url or f"https://www.youtube.com/watch?v={entry_id}"
                        download_thumbnail(entry_id, entry_thumb_path, entry_video_url)
                        logger.info(f"✅ Downloaded thumbnail for video {entry_id}: {entry_thumb_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to download thumbnail for video {entry_id}: {e}")
                elif entry_url:
                    # For other services, use the universal downloader
                    try:
                        service_name = "unknown"
                        if 'vk.com' in entry_url:
                            service_name = "vk"
                        elif 'tiktok.com' in entry_url:
                            service_name = "tiktok"
                        elif any(x in entry_url for x in ['twitter.com', 'x.com']):
                            service_name = "twitter"
                        # Add other services as needed
                        
                        if service_name != "unknown":
                            entry_thumb_path = os.path.join(thumb_dir, f"{service_name}_thumb_{entry_id}.jpg")
                            if download_universal_thumbnail(entry_url, entry_thumb_path):
                                logger.info(f"✅ Downloaded thumbnail for video {entry_id}: {entry_thumb_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to download thumbnail for video {entry_id}: {e}")
        
        # Download the thumbnail for the first video (to display in the menu)
        if ("youtube.com" in url or "youtu.be" in url) and video_id:
            thumb_path = os.path.join(thumb_dir, f"yt_thumb_{video_id}.jpg")
            try:
                download_thumbnail(video_id, thumb_path, url)
                logger.info(f"Downloaded thumbnail to download directory: {thumb_path}")
            except Exception as e:
                logger.warning(f"Failed to download thumbnail: {e}")
                thumb_path = None
        else:
            # Try to download thumbnail for non-YouTube services
            service_name = "unknown"
            if 'vk.com' in url:
                service_name = "vk"
            elif 'tiktok.com' in url:
                service_name = "tiktok"
            elif any(x in url for x in ['twitter.com', 'x.com']):
                service_name = "twitter"
            elif 'facebook.com' in url:
                service_name = "facebook"
            elif 'pornhub.com' in url or 'pornhub.org' in url:
                service_name = "pornhub"
            elif any(x in url for x in ['instagram.com', 'instagr.am']):
                service_name = "instagram"
            elif 'vimeo.com' in url:
                service_name = "vimeo"
            elif any(x in url for x in ['dailymotion.com', 'dai.ly']):
                service_name = "dailymotion"
            elif 'rutube.ru' in url:
                service_name = "rutube"
            elif 'twitch.tv' in url:
                service_name = "twitch"
            elif 'boosty.to' in url:
                service_name = "boosty"
            elif 'ok.ru' in url:
                service_name = "okru"
            elif any(x in url for x in ['reddit.com', 'redd.it']):
                service_name = "reddit"
            elif 'pikabu.ru' in url:
                service_name = "pikabu"
            elif 'zen.yandex.ru' in url:
                service_name = "yandex_zen"
            elif any(x in url for x in ['drive.google.com', 'docs.google.com']):
                service_name = "google_drive"
            elif 'redtube.com' in url:
                service_name = "redtube"
            elif 'bilibili.com' in url:
                service_name = "bilibili"
            elif 'nicovideo.jp' in url:
                service_name = "niconico"
            elif 'xvideos.com' in url:
                service_name = "xvideos"
            elif 'xnxx.com' in url:
                service_name = "xnxx"
            elif 'youporn.com' in url:
                service_name = "youporn"
            elif 'xhamster.com' in url:
                service_name = "xhamster"
            elif 'porntube.com' in url:
                service_name = "porntube"
            elif 'spankbang.com' in url:
                service_name = "spankbang"
            elif 'onlyfans.com' in url:
                service_name = "onlyfans"
            elif 'patreon.com' in url:
                service_name = "patreon"
            elif 'soundcloud.com' in url:
                service_name = "soundcloud"
            elif 'bandcamp.com' in url:
                service_name = "bandcamp"
            elif 'mixcloud.com' in url:
                service_name = "mixcloud"
            elif 'deezer.com' in url:
                service_name = "deezer"
            elif 'spotify.com' in url:
                service_name = "spotify"
            elif 'music.apple.com' in url:
                service_name = "apple_music"
            elif 'tidal.com' in url:
                service_name = "tidal"
            
            if service_name != "unknown":
                thumb_path = os.path.join(user_dir, f"{service_name}_thumb_{video_id or 'unknown'}.jpg")
                try:
                    if download_universal_thumbnail(url, thumb_path):
                        thumb_path = thumb_path
                    else:
                        thumbnail_url = info.get('thumbnail')
                        if thumbnail_url:
                            try:
                                response = requests.get(thumbnail_url, timeout=10)
                                if response.status_code == 200 and len(response.content) <= 1024 * 1024:
                                    with open(thumb_path, "wb") as f:
                                        f.write(response.content)
                                    thumb_path = thumb_path
                            except Exception:
                                pass
                except Exception:
                    pass
        # At this point, lack of thumbnail must NOT block further UI
        menu_data = _build_quality_menu_data_model(
            message=message,
            user_id=user_id,
            url=url,
            info=info,
            cached_qualities=cached_qualities,
            is_playlist=is_playlist,
            playlist_range=playlist_range,
            tags_text=tags_text,
            is_nsfw=is_nsfw,
            is_private_chat=is_private_chat,
            send_as_file=send_as_file,
        )
        filters_state = menu_data.filters_state
        sel_codec = menu_data.selected_codec
        sel_ext = menu_data.selected_ext
        user_fixed_format = menu_data.user_fixed_format
        quality_map = menu_data.quality_map
        found_quality_keys = menu_data.found_quality_keys
        found_type = menu_data.found_subtitle_type
        cap = menu_data.cap
        # --- Hint ---
        subs_enabled = is_subs_enabled(user_id)
        auto_mode = get_user_subs_auto_mode(user_id)
        subs_lang = get_user_subs_language(user_id)

        # We check for subtitles of the desired type for the selected language
        subs_hint = ""
        subs_warn = ""
        show_repost_hint = True

        if subs_enabled and is_youtube_url(url):
            found_type = check_subs_availability(url, user_id, return_type=True)
            # Check if we're in Always Ask mode (user will choose language manually)
            is_always_ask_mode = is_subs_always_ask(user_id)
            
            if is_always_ask_mode:
                # In Always Ask menu, always show subtitles as available if found, regardless of auto_mode
                # User will choose language and type manually
                need_subs = found_type is not None  # True if any subtitles found (auto or normal)
            else:
                # In manual mode, respect user's auto_mode setting
                need_subs = (auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal")
            
            logger.info(f"Always Ask menu: subs_enabled={subs_enabled}, auto_mode={auto_mode}, found_type={found_type}, is_always_ask={is_always_ask_mode}, need_subs={need_subs}")
            if need_subs:
                subs_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_SUBTITLES_ARE_AVAILABLE_MSG}"
                show_repost_hint = False  # 🚀 we don't show if subs really exist and are needed
            elif is_always_ask_mode and not need_subs:
                # In Always Ask mode, show subs hint even if not found (user can still try)
                subs_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_SUBTITLE_LANGUAGE_MSG}"
            else:
                subs_warn = f"\n{safe_get_messages(user_id).ALWAYS_ASK_SUBS_NOT_FOUND_MSG}"

        repost_line = f"\n{safe_get_messages(user_id).ALWAYS_ASK_INSTANT_REPOST_MSG}" if show_repost_hint else ""
        # Add DUBS hint if available
        dubs_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_AUDIO_LANGUAGE_MSG}" if get_filters(user_id).get("has_dubs") else ""
        # Replace quality hint with paid note for NSFW
        paid_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_NSFW_IS_PAID_MSG}" if (is_nsfw and is_private_chat) else f"\n{safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_DOWNLOAD_QUALITY_MSG}"
        # Hints tied to optional buttons
        image_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_DOWNLOAD_IMAGE_MSG}" if not found_quality_keys else ""
        watch_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_WATCH_VIDEO_MSG}" if is_youtube_url(url) else ""
        link_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_GET_DIRECT_LINK_MSG}"  # Link button is always present
        list_hint = f"\n{safe_get_messages(user_id).ALWAYS_ASK_SHOW_AVAILABLE_FORMATS_MSG}"  # LIST button is always present
        
        # Create dynamic hints based on actual buttons that will be shown
        def create_dynamic_hints(action_buttons, found_quality_keys, is_youtube_url, url, is_nsfw, is_private_chat, get_filters, user_id, subs_hint, subs_warn):
            messages = safe_get_messages(message.chat.id)
            """Create hints only for emojis that are actually used in the menu"""
            hints = []
            
            # Always show format change hint (📼) - this is always available
            hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_CHANGE_VIDEO_EXT_MSG}")
            
            # Quality hint (📹) - always shown unless NSFW
            if is_nsfw and is_private_chat:
                hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_NSFW_IS_PAID_MSG}")
            else:
                hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_DOWNLOAD_QUALITY_MSG}")
            
            # Repost hint (🚀) - only if show_repost_hint is True
            if show_repost_hint:
                hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_INSTANT_REPOST_MSG}")
            
            # Watch hint (👁) - only for YouTube
            if is_youtube_url(url):
                hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_WATCH_VIDEO_MSG}")
            
            # Link hint (🔗) - always present
            hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_GET_DIRECT_LINK_MSG}")
            
            # List hint (📃) - always present
            hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_SHOW_AVAILABLE_FORMATS_MSG}")
            
            # Image hint (🖼) - only if no quality keys found
            if not found_quality_keys:
                hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_DOWNLOAD_IMAGE_MSG}")
            
            # Subs hints
            if subs_hint:
                hints.append(subs_hint.strip())
            if subs_warn:
                hints.append(subs_warn.strip())
            
            # Dubs hint (🗣) - only if available
            if get_filters(user_id).get("has_dubs"):
                hints.append(f"{safe_get_messages(user_id).ALWAYS_ASK_CHOOSE_AUDIO_LANGUAGE_MSG}")
            
            return "\n".join(hints)
        
        # We need to create action_buttons first to determine which hints to show
        # This will be done later in the code, so for now we'll use the old logic
        # but we'll replace it after action_buttons are created
        # Temporary hint for now - will be replaced later
        temp_hint = (
            f"<pre language=\"info\">{safe_get_messages(user_id).ALWAYS_ASK_CHANGE_VIDEO_EXT_MSG}"
            + paid_hint
            + repost_line
            + watch_hint
            + link_hint
            + list_hint
            + image_hint
            + subs_hint
            + subs_warn
            + dubs_hint
            + "</pre>"
        )
        cap += f"\n{temp_hint}\n"
        buttons = []
        # Sort buttons by quality from lowest to highest
        if ("youtube.com" in url or "youtu.be" in url):
            for quality_key in sorted(quality_map.keys(), key=sort_quality_key):
                f = quality_map[quality_key]
                w = f.get('width')
                h = f.get('height')
                filesize = f.get('filesize') or f.get('filesize_approx')
                if filesize:
                    if filesize and filesize >= 1024*1024*1024:
                        size_str = f"{round(filesize/1024/1024/1024, 2)}GB"
                    else:
                        size_str = f"{round(filesize/1024/1024, 1)}MB"
                else:
                    size_str = '—'
                dim_str = f" ({w}×{h})" if w and h else ''
                scissors = ""
                if get_user_split_size(user_id) and filesize:
                    video_bytes = filesize
                    if video_bytes and video_bytes > get_user_split_size(user_id):
                        n_parts = (video_bytes + get_user_split_size(user_id) - 1) // get_user_split_size(user_id)
                        scissors = f" ✂️{n_parts}"
                # Check the availability of subtitles for this quality
                subs_available = ""
                subs_enabled = is_subs_enabled(user_id)
                auto_mode = get_user_subs_auto_mode(user_id)
                if subs_enabled:
                    if sel_ext == 'mkv':
                        subs_available = "💬"
                    elif is_youtube_url(url) and w is not None and h is not None and min(int(w), int(h)) <= Config.MAX_SUB_QUALITY:
                        # Check if we're in Always Ask mode
                        is_always_ask_mode = is_subs_always_ask(user_id)
                        
                        if is_always_ask_mode:
                            # In Always Ask menu, show 💬 if any subtitles found, regardless of auto_mode
                            if found_type is not None:  # Any subtitles found (auto or normal)
                                temp_info = {
                                    'duration': info.get('duration'),
                                    'filesize': filesize,
                                    'filesize_approx': filesize
                                }
                                if check_subs_limits(temp_info, quality_key):
                                    subs_available = "💬"
                        else:
                            # In manual mode, respect user's auto_mode setting
                            if (auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal"):
                                temp_info = {
                                    'duration': info.get('duration'),
                                    'filesize': filesize,
                                    'filesize_approx': filesize
                                }
                                if check_subs_limits(temp_info, quality_key):
                                    subs_available = "💬"
                
                # Cache/icon (skip if send_as_file is enabled)
                if send_as_file:
                    icon = "1⭐️" if (is_nsfw and is_private_chat) else "📹"
                    postfix = ""
                    button_text = f"{icon}{quality_key}{subs_available}"
                elif is_playlist and playlist_range:
                    # Correct indices construction for negative indices
                    start, end = playlist_range
                    if start < 0 and end < 0:
                        if abs(start) < abs(end):
                            indices = list(range(start, end - 1, -1))
                        else:
                            indices = list(range(start, end + 1, 1))
                    elif start > end:
                        indices = list(range(start, end - 1, -1))
                    else:
                        indices = list(range(start, end + 1))
                    n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality_key, indices)
                    total = len(indices)
                    icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
                    postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
                    button_text = f"{icon}{quality_key}{subs_available}{postfix}"
                else:
                    # Check if we're in Always Ask mode
                    is_always_ask_mode = is_subs_always_ask(user_id)
                    
                    if is_always_ask_mode:
                        # In Always Ask menu, show 💬 if any subtitles found, regardless of auto_mode
                        need_subs = (subs_enabled and found_type is not None)  # True if any subtitles found
                    else:
                        # In manual mode, respect user's auto_mode setting
                        need_subs = (subs_enabled and ((auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal")))
                    
                    # Check cache for a single video
                    is_cached = quality_key in cached_qualities
                    # Additionally check cache by the video's unique URL (single video from a playlist)
                    if not is_cached:
                        # Extract the current video's unique URL
                        video_page_url = (
                            info.get("webpage_url")
                            or info.get("original_url")
                            or info.get("url")
                            or info.get("canonical_url")
                            or url
                        )
                        # If this is not the playlist URL, check cache by the unique URL
                        if video_page_url != url and video_page_url:
                            try:
                                single_video_cached = get_cached_message_ids(video_page_url, quality_key)
                                if single_video_cached:
                                    is_cached = True
                                    logger.info(f"🔍 [CACHE] Found single video in cache by unique URL: {video_page_url}, quality: {quality_key}")
                            except Exception as e:
                                logger.warning(f"⚠️ [CACHE] Error while checking cache for a single video: {e}")
                    
                    icon = "🚀" if (is_cached and not need_subs and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
                    button_text = f"{icon}{quality_key}{subs_available}"
                buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|{quality_key}"))
        else:
            # Show only detected qualities derived from formats (one per quality)
            detected_ordered = sorted(quality_map.keys(), key=sort_quality_key)
            for quality_key in detected_ordered:
                entry = quality_map[quality_key]
                w, h, size_val = entry['w'], entry['h'], entry['size_mb']
                size_str = f"{round(size_val/1024, 1)}GB" if size_val and size_val >= 1024 else (f"{size_val}MB" if size_val else '—')
                dim_str = f" ({w}×{h})" if w and h else ''
                scissors = ""
                if get_user_split_size(user_id) and size_val:
                    video_bytes = size_val * 1024 * 1024
                    if video_bytes and video_bytes > get_user_split_size(user_id):
                        n_parts = (video_bytes + get_user_split_size(user_id) - 1) // get_user_split_size(user_id)
                        scissors = f" ✂️{n_parts}"

                if is_playlist and playlist_range:
                    # Correct indices construction for negative indices
                    start, end = playlist_range
                    if start < 0 and end < 0:
                        if abs(start) < abs(end):
                            indices = list(range(start, end - 1, -1))
                        else:
                            indices = list(range(start, end + 1, 1))
                    elif start > end:
                        indices = list(range(start, end - 1, -1))
                    else:
                        indices = list(range(start, end + 1))
                    n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality_key, indices)
                    total = len(indices)
                    icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
                    postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
                    button_text = f"{icon}{quality_key}{postfix}"
                else:
                    # Check cache for a single video
                    is_cached = quality_key in cached_qualities
                    # Additionally check cache by the video's unique URL (single video from a playlist)
                    if not is_cached:
                        try:
                            cached_info = load_ask_info(user_id, url)
                            if cached_info:
                                video_page_url = (
                                    cached_info.get("webpage_url")
                                    or cached_info.get("original_url")
                                    or cached_info.get("url")
                                    or cached_info.get("canonical_url")
                                )
                                # If this is not the playlist URL, check cache by the unique URL
                                if video_page_url and video_page_url != url:
                                    single_video_cached = get_cached_message_ids(video_page_url, quality_key)
                                    if single_video_cached:
                                        is_cached = True
                                        logger.info(f"🔍 [CACHE] Found single video in cache by unique URL: {video_page_url}, quality: {quality_key}")
                        except Exception as e:
                            logger.warning(f"⚠️ [CACHE] Error while checking cache for a single video: {e}")
                    
                    icon = "🚀" if (is_cached and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
                    button_text = f"{icon}{quality_key}"
                buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|{quality_key}"))

        # Always add {safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG} Quality button
        quality_key = "best"
        if is_playlist and playlist_range:
            # Correct indices construction for negative indices
            start, end = playlist_range
            if start < 0 and end < 0:
                if abs(start) < abs(end):
                    indices = list(range(start, end - 1, -1))
                else:
                    indices = list(range(start, end + 1, 1))
            elif start > end:
                indices = list(range(start, end - 1, -1))
            else:
                indices = list(range(start, end + 1))
            n_cached = get_cached_playlist_count(get_clean_playlist_url(url), quality_key, indices)
            total = len(indices)
            icon = "🚀" if (n_cached > 0 and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
            postfix = f" ({n_cached}/{total})" if total and total > 1 else ""
            button_text = f"{icon}{safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG}{postfix}"
        else:
            icon = "🚀" if (quality_key in cached_qualities and not is_nsfw) else ("1⭐️" if (is_nsfw and is_private_chat) else "📹")
            button_text = f"{icon}{safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG}"
        buttons.append(InlineKeyboardButton(button_text, callback_data=f"askq|{quality_key}"))
        
        # Always add Other Qualities button
        other_label = f"{safe_get_messages(user_id).ALWAYS_ASK_OTHER_LABEL_MSG}" if not is_nsfw else f"{safe_get_messages(user_id).ALWAYS_ASK_OTHER_LABEL_MSG}"
        buttons.append(InlineKeyboardButton(other_label, callback_data=f"askq|other_qualities"))
        
        filter_rows, filter_action_buttons = build_filter_rows(user_id, url, is_private_chat)
        action_buttons = []
        action_buttons.extend(filter_action_buttons)
        logger.info(f"Adding LINK button for user {user_id}")
        action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_LINK_BUTTON_MSG, callback_data="askq|link"))
        action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).LIST_BUTTON_TEXT, callback_data="askq|list"))
        if not found_quality_keys:
            action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).IMAGE_BUTTON_TEXT, callback_data="askq|image"))
        if (is_instagram_url(url) or is_twitter_url(url) or is_reddit_url(url)) and not is_playlist_with_range(original_text):
            action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_EMBED_BUTTON_MSG, callback_data="askq|quick_embed"))

        # Add WATCH button for YouTube links - always add to action_buttons for consistent placement
        try:
            if is_youtube_url(url):
                logger.info(f"Processing YouTube URL for WATCH button: {url}")
                piped_url = youtube_to_piped_url(url)
                logger.info(f"Converted to Piped URL: {piped_url}")
                # Check if this is a group (negative user_id)
                try:
                    is_group = isinstance(user_id, int) and user_id < 0
                except Exception:
                    is_group = False
                if is_group:
                    action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_WATCH_BUTTON_MSG, url=piped_url))
                else:
                    wa = WebAppInfo(url=piped_url)
                    action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_WATCH_BUTTON_MSG, web_app=wa))
                logger.info(f"Added WATCH button to action_buttons for user {user_id}")
        except Exception as e:
            logger.error(f"Error adding WATCH button for user {user_id}: {e}")
            pass
        
        # --- button subtitles only ---
        # Show the button only if subtitles are turned on and it is youtube
        subs_enabled = is_subs_enabled(user_id)
        if subs_enabled and is_youtube_url(url):
            # Check if we're in Always Ask mode
            is_always_ask_mode = is_subs_always_ask(user_id)
            
            if is_always_ask_mode:
                # In Always Ask menu, show button if any subtitles found, regardless of auto_mode
                need_subs = found_type is not None  # True if any subtitles found (auto or normal)
            else:
                # manual mode, respect user's auto_mode setting
                need_subs = (auto_mode and found_type == "auto") or (not auto_mode and found_type == "normal")
            
            if need_subs:
                action_buttons.append(InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_SUB_ONLY_BUTTON_MSG, callback_data="askq|subs_only"))
        composition = _compose_quality_menu(
            user_id=user_id,
            url=url,
            cap=cap,
            buttons=buttons,
            action_buttons=action_buttons,
            filter_rows=filter_rows,
            found_quality_keys=found_quality_keys,
            is_nsfw=is_nsfw,
            is_private_chat=is_private_chat,
            show_repost_hint=show_repost_hint,
            cached_qualities=cached_qualities,
            subs_hint=subs_hint,
            subs_warn=subs_warn,
            filters_state=filters_state,
        )
        render_plan = _build_quality_menu_render_plan(
            text=composition.text,
            keyboard_rows=composition.keyboard_rows,
            thumb_path=thumb_path,
            is_playlist=is_playlist,
            is_nsfw=is_nsfw,
        )
        _emit_quality_menu_render_plan(
            app,
            message,
            cb=cb,
            proc_msg=proc_msg,
            user_id=user_id,
            render_plan=render_plan,
        )
        send_to_logger(message, safe_get_messages(user_id).ALWAYS_ASK_MENU_SENT_LOG_MSG.format(url=url))
    except FloodWait as e:
        wait_time = e.value
        user_dir = os.path.join("users", str(user_id))
        create_directory(user_dir)
        flood_time_file = os.path.join(user_dir, "flood_wait.txt")
        with open(flood_time_file, 'w') as f:
            f.write(str(wait_time))
        hours = wait_time // 3600
        minutes = (wait_time % 3600) // 60
        seconds = wait_time % 60
        time_str = f"{hours}h {minutes}m {seconds}s"
        flood_msg = safe_get_messages(user_id).AA_FLOOD_WAIT_MSG.format(time_str=time_str)
        if proc_msg:
            try:
                app.edit_message_text(chat_id=user_id, message_id=proc_msg.id, text=flood_msg)
            except Exception as e:
                if 'MESSAGE_ID_INVALID' not in str(e):
                    logger.warning(f"Failed to edit message: {e}")
            proc_msg = None
        else:
            try:
                app.send_message(user_id, flood_msg, reply_parameters=ReplyParameters(message_id=message.id))
            except FloodWait:
                # Can't send even a FloodWait notice — exit, the time is already saved
                pass
            except Exception as e:
                logger.warning(f"Failed to send flood notice: {e}")
        return
    except Exception as e:
        import traceback
        logger.error(f"Error retrieving video information for user {user_id}: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        failure_decision = _determine_ask_quality_menu_failure_decision(
            message,
            url=url,
            tags=tags,
            proc_msg=proc_msg,
            user_id=user_id,
            error=e,
        )
        if failure_decision.mode == "gallery_fallback_dispatch":
            try:
                safe_edit_message_text(
                    user_id,
                    proc_msg.id if proc_msg else None,
                    safe_get_messages(user_id).AA_NO_VIDEO_FORMATS_FOUND_MSG,
                )
            except Exception:
                pass
            try:
                fallback_result = _dispatch_gallery_fallback(
                    app,
                    user_id=user_id,
                    fallback_text=failure_decision.fallback_text,
                    original_chat_id=user_id,
                    message_thread_id=None,
                    original_message=None,
                    runtime_task=failure_decision.runtime_task,
                )
                logger.info(
                    "Always Ask menu fallback result for user %s: outcome=%s success=%s",
                    user_id,
                    fallback_result.outcome_kind if is_gallery_command_result(fallback_result) else None,
                    did_gallery_command_succeed(fallback_result)
                    if is_gallery_command_result(fallback_result)
                    else None,
                )
                logger.info("Triggered gallery-dl fallback via /img from Always Ask menu")
                return
            except Exception as dispatch_error:
                logger.error(
                    "Failed to trigger gallery-dl fallback from Always Ask menu: %s",
                    dispatch_error,
                )

        try:
            logger.info(f"Attempting to create menu from cached qualities for user {user_id}")
            if create_cached_qualities_menu(
                app,
                message,
                url,
                tags,
                proc_msg,
                user_id,
                original_text,
                is_playlist,
                playlist_range,
            ):
                logger.info(f"Successfully created cached qualities menu for user {user_id}")
                send_to_logger(
                    message,
                    safe_get_messages(user_id).CACHED_QUALITIES_MENU_CREATED_LOG_MSG.format(
                        user_id=user_id,
                        error=str(e),
                    ),
                )
                return
            logger.info(f"No cached qualities available for user {user_id}, showing error message")
        except Exception as cache_error:
            logger.error(f"Error creating cached qualities menu: {cache_error}")

        _emit_ask_quality_menu_terminal_error(app, message, user_id, proc_msg, url)
        return

def askq_callback_logic(
    app,
    execution_context,
    data,
    original_message,
    url,
    tags_text,
    available_langs,
    proc_msg=None,
):
    callback_query = execution_context.callback_query
    if callback_query is None:
        raise ValueError("Ask quality callback logic requires callback execution context")
    user_id = callback_query.from_user.id
    messages = safe_get_messages(user_id)
    tags = tags_text.split() if tags_text else []
    selection_plan = _determine_ask_quality_selection_plan(user_id, data=data)
    
    # Check if LINK mode is enabled
    if get_link_mode(user_id):
        branch_result = _select_direct_link_branch(
            user_id,
            quality_intent=data,
            quality_key=data,
            origin="askq_callback_logic",
            provenance={"mode": "link"},
        )
        # Get direct link instead of downloading
        try:
            callback_query.answer(safe_get_messages(user_id).ALWAYS_ASK_GETTING_DIRECT_LINK_MSG)
        except Exception:
            pass
        
        from COMMANDS.link_cmd import get_direct_link
        result = execute_direct_link_flow(
            fetch_direct_link=get_direct_link,
            response_sender=send_always_ask_direct_link_response_legacy_error,
            app=app,
            message=original_message,
            user_id=user_id,
            url=url,
            quality_key=data,
            cookies_already_checked=True,
            use_proxy=False,
        )
        
        if result.get('success'):
            send_to_logger(original_message, safe_get_messages(user_id).DIRECT_LINK_EXTRACTED_ALWAYS_ASK_LOG_MSG.format(user_id=user_id, url=url))
            
        else:
            error_msg = result.get('error', 'Unknown error')
            log_error_to_channel(original_message, safe_get_messages(user_id).DIRECT_LINK_FAILED_ALWAYS_ASK_LOG_MSG.format(user_id=user_id, url=url, error=error_msg), url)
        
        return
    # Read current filters to build correct format strings and container override
    try:
        filters_state = get_filters(user_id)
    except Exception:
        filters_state = {"codec": "avc1", "ext": "mp4"}
    sel_codec = filters_state.get("codec", "avc1")
    sel_ext = filters_state.get("ext", "mp4")
    sel_audio_lang = filters_state.get("audio_lang")
    
    # Get selected subtitle language from filters (for Always Ask mode)
    selected_subs_lang = filters_state.get("selected_subs_lang")
    if selected_subs_lang:
        # Temporarily save the selected subtitle language for this download
        from COMMANDS.subtitles_cmd import save_user_subs_language, save_user_subs_auto_mode
        save_user_subs_language(user_id, selected_subs_lang)
        # If user picks explicit language from SUBS menu – assume manual, not auto
        save_user_subs_auto_mode(user_id, False)
        logger.info(f"Using selected subtitle language from Always Ask: {selected_subs_lang}")
    try:
        set_session_mkv_override(user_id, sel_ext == "mkv")
    except Exception:
        pass
    if selection_plan.answer_text:
        try:
            callback_query.answer(selection_plan.answer_text)
        except Exception:
            pass
    if selection_plan.mode == "download" and selection_plan.branch_family == "audio":
        # Extract playlist parameters from the original message
        _, video_start_with, video_end_with, playlist_name, video_count = _build_quality_range_context(original_message)
        branch_result = _select_callback_download_branch(
            user_id,
            callback_data=data,
            quality_intent="mp3",
            quality_key="mp3",
            format_override="ba",
            video_count=video_count,
            origin="askq_callback_logic",
            provenance={"callback_data": data},
        )
        task = _make_callback_runtime_task(
            original_message,
            url=url,
            tags=tags,
            tags_text=tags_text,
            branch_result=branch_result,
            playlist_name=playlist_name,
            video_count=video_count,
            video_start_with=video_start_with,
            proc_msg=proc_msg,
        )
        _dispatch_callback_download_branch(
            app,
            original_message,
            task,
            proc_msg=proc_msg,
        )
        return
    
    if selection_plan.download_subtitles_only:
        # Extract playlist parameters from the original message
        _, video_start_with, video_end_with, playlist_name, video_count = _build_quality_range_context(original_message)
        download_subtitles_only(app, original_message, url, tags, available_langs, playlist_name=playlist_name, video_count=video_count, video_start_with=video_start_with)
        return
    
    # Logic for forming the format with the real height
    if selection_plan.mode == "best_video":
        # Use format with AVC codec and MP4 container priority for {safe_get_messages(user_id).ALWAYS_ASK_BEST_BUTTON_MSG} quality
        # with fallback to bv+ba/best if no AVC+MP4 available
        audio_filter = f"[language^={sel_audio_lang}]" if sel_audio_lang else ""
        fmt = f"bv*[vcodec*={sel_codec}][ext={sel_ext}]+ba{audio_filter}/bv*[vcodec*={sel_codec}]+ba{audio_filter}/bv*[ext={sel_ext}]+ba{audio_filter}/bv+ba/best"
        quality_key = selection_plan.quality_key or "best"
    else:
        try:
            # Get information about the video to determine the sizes - try cached info first
            cached_info = load_ask_info(user_id, url)
            if cached_info:
                info = cached_info
                logger.info(f"✅ [OPTIMIZATION] Using cached video info for size determination")
            else:
                info = get_video_formats(url, user_id, cookies_already_checked=True)
                logger.info(f"⚠️ [OPTIMIZATION] Had to fetch video info for size determination")
            formats = info.get('formats', [])
            
            # Find the format with the highest quality to determine the sizes
            max_width = 0
            max_height = 0
            for f in formats:
                if not isinstance(f, dict):
                    continue
                if f.get('width') and f.get('height'):
                    width = int(f.get('width') or 0)
                    height = int(f.get('height') or 0)
                    if width > max_width:
                        max_width = width
                    if height > max_height:
                        max_height = height
            
            # If the sizes are not found, use the standard logic
            if max_width == 0 or max_height == 0:
                quality_str = data.replace('p', '')
                quality_val = int(quality_str)
                # choose previous rung for lower bound
                if quality_val and quality_val >= 4320:
                    prev = 2160
                elif quality_val and quality_val >= 2160:
                    prev = 1440
                elif quality_val and quality_val >= 1440:
                    prev = 1080
                elif quality_val and quality_val >= 1080:
                    prev = 720
                elif quality_val and quality_val >= 720:
                    prev = 480
                elif quality_val and quality_val >= 480:
                    prev = 360
                elif quality_val and quality_val >= 360:
                    prev = 240
                elif quality_val and quality_val >= 240:
                    prev = 144
                else:
                    prev = 0
                audio_filter = f"[language^={sel_audio_lang}]" if sel_audio_lang else ""
                fmt = f"bv*[vcodec*={sel_codec}][height<={quality_val}][height>{prev}]+ba{audio_filter}/bv*[vcodec*={sel_codec}][height<={quality_val}]+ba{audio_filter}/bv*[vcodec*={sel_codec}]+ba/bv+ba/best"
            else:
                # Determine the quality by the smaller side
                min_side_quality = get_quality_by_min_side(max_width, max_height)
                
                # If the selected quality does not match the smaller side, use the standard logic
                if data != min_side_quality:
                    quality_str = data.replace('p', '')
                    quality_val = int(quality_str)
                    if quality_val and quality_val >= 4320:
                        prev = 2160
                    elif quality_val and quality_val >= 2160:
                        prev = 1440
                    elif quality_val and quality_val >= 1440:
                        prev = 1080
                    elif quality_val and quality_val >= 1080:
                        prev = 720
                    elif quality_val and quality_val >= 720:
                        prev = 480
                    elif quality_val and quality_val >= 480:
                        prev = 360
                    elif quality_val and quality_val >= 360:
                        prev = 240
                    elif quality_val and quality_val >= 240:
                        prev = 144
                    else:
                        prev = 0
                    audio_filter = f"[language^={sel_audio_lang}]" if sel_audio_lang else ""
                    fmt = f"bv*[vcodec*={sel_codec}][height<={quality_val}][height>{prev}]+ba{audio_filter}/bv*[vcodec*={sel_codec}][height<={quality_val}]+ba{audio_filter}/bv*[vcodec*={sel_codec}]+ba/bv+ba/best"
                else:
                    # Use the real height to form the format
                    real_height = get_real_height_for_quality(data, max_width, max_height)
                    quality_str = data.replace('p', '')
                    quality_val = int(quality_str)
                    if quality_val and quality_val >= 4320:
                        prev = 2160
                    elif quality_val and quality_val >= 2160:
                        prev = 1440
                    elif quality_val and quality_val >= 1440:
                        prev = 1080
                    elif quality_val and quality_val >= 1080:
                        prev = 720
                    elif quality_val and quality_val >= 720:
                        prev = 480
                    elif quality_val and quality_val >= 480:
                        prev = 360
                    elif quality_val and quality_val >= 360:
                        prev = 240
                    elif quality_val and quality_val >= 240:
                        prev = 144
                    else:
                        prev = 0
                    audio_filter = f"[language^={sel_audio_lang}]" if sel_audio_lang else ""
                    fmt = f"bv*[vcodec*={sel_codec}][height<={real_height}][height>{prev}]+ba{audio_filter}/bv*[vcodec*={sel_codec}][height<={real_height}]+ba{audio_filter}/bv*[vcodec*={sel_codec}]+ba/bv+ba/best"
            
            quality_key = selection_plan.quality_key or data
        except ValueError:
            callback_query.answer("Unknown quality.")
            return
    branch_result = _select_callback_download_branch(
        user_id,
        callback_data=data,
        quality_intent=quality_key or data,
        quality_key=quality_key,
        format_override=fmt,
        origin="askq_callback_logic",
        provenance={"callback_data": data},
        force_branch_family="video",
    )
    task = _make_callback_runtime_task(
        original_message,
        url=url,
        tags=tags,
        tags_text=tags_text,
        branch_result=branch_result,
        proc_msg=proc_msg,
    )
    _dispatch_callback_download_branch(
        app,
        original_message,
        task,
        proc_msg=proc_msg,
    )


def _execute_askq_link_action(app, callback_query, user_id: int, source_context: AlwaysAskSourceContext) -> None:
    original_message = source_context.original_message
    url = source_context.url
    from HELPERS.proxy_link_helper import get_direct_link_with_proxy

    result = get_direct_link_with_proxy(url, "bv+ba/best", user_id)
    if result.get("success"):
        title = result.get("title", "Unknown")
        duration = result.get("duration", 0)
        player_urls = result.get("player_urls", {})
        main_response = safe_get_messages(user_id).STREAM_LINKS_TITLE_MSG
        main_response += safe_get_messages(user_id).STREAM_TITLE_MSG.format(title=title)
        if duration and duration > 0:
            main_response += f"{safe_get_messages(user_id).ALWAYS_ASK_DURATION_MSG} {duration} sec\n"
        main_response += f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_MSG} <code>bv+ba/best</code>\n\n"
        main_response += f"{safe_get_messages(user_id).ALWAYS_ASK_BROWSER_MSG}\n\n"
        browser_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_BROWSER_BUTTON_MSG, url=player_urls["direct"])],
            [InlineKeyboardButton("🔚 Close", callback_data="askq|close")],
        ])
        app.send_message(
            user_id,
            main_response,
            reply_parameters=ReplyParameters(message_id=original_message.id),
            reply_markup=browser_keyboard,
            parse_mode=enums.ParseMode.HTML,
        )
        if "vlc_ios" in player_urls:
            vlc_ios_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_VLC_IOS_BUTTON_MSG, url=player_urls["vlc_ios"])],
                [InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_CLOSE_BUTTON_MSG, callback_data="askq|close")],
            ])
            app.send_message(
                user_id,
                safe_get_messages(user_id).AA_VLC_IOS_MSG,
                reply_parameters=ReplyParameters(message_id=original_message.id),
                reply_markup=vlc_ios_keyboard,
                parse_mode=enums.ParseMode.HTML,
            )
        if "vlc_android" in player_urls:
            vlc_android_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_VLC_ANDROID_BUTTON_MSG, url=player_urls["vlc_android"])],
                [InlineKeyboardButton(safe_get_messages(user_id).ALWAYS_ASK_CLOSE_BUTTON_MSG, callback_data="askq|close")],
            ])
            app.send_message(
                user_id,
                safe_get_messages(user_id).AA_VLC_ANDROID_MSG,
                reply_parameters=ReplyParameters(message_id=original_message.id),
                reply_markup=vlc_android_keyboard,
                parse_mode=enums.ParseMode.HTML,
            )
        send_to_logger(original_message, safe_get_messages(user_id).DIRECT_LINK_MENU_CREATED_LOG_MSG.format(user_id=user_id, url=url))
    else:
        error_msg = result.get("error", "Unknown error")
        app.send_message(
            user_id,
            safe_get_messages(user_id).AA_ERROR_GETTING_LINK_MSG.format(error_msg=error_msg),
            reply_parameters=ReplyParameters(message_id=original_message.id),
            parse_mode=enums.ParseMode.HTML,
        )
        log_error_to_channel(
            original_message,
            safe_get_messages(user_id).DIRECT_LINK_EXTRACTION_FAILED_LOG_MSG.format(user_id=user_id, url=url, error=error_msg),
            url,
        )
    try:
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
    except Exception as e:
        logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_DELETE_ALWAYS_ASK_MENU_LOG_MSG}: {e}")


def _execute_askq_list_action(app, callback_query, user_id: int, source_context: AlwaysAskSourceContext) -> None:
    original_message = source_context.original_message
    url = source_context.url
    from COMMANDS.list_cmd import run_ytdlp_list

    success, output = run_ytdlp_list(url, user_id)
    if success:
        audio_only_formats = []
        video_only_formats = []
        for line in output.split("\n"):
            if "audio only" in line.lower() or "audio_only" in line.lower():
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    audio_only_formats.append(parts[0])
            elif "video only" in line.lower() or "video_only" in line.lower():
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    video_only_formats.append(parts[0])
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_AVAILABLE_FORMATS_FOR_MSG}: {url}\n")
            temp_file.write("=" * 50 + "\n\n")
            temp_file.write(output)
            temp_file.write("\n\n" + "=" * 50 + "\n")
            temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_HOW_TO_USE_FORMAT_IDS_MSG}\n")
            temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_AFTER_GETTING_LIST_MSG}\n")
            temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_ID_401_MSG}\n")
            temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_ID401_MSG}\n")
            temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_ID_140_AUDIO_MSG}\n")
            if audio_only_formats:
                temp_file.write(f"\n{safe_get_messages(user_id).ALWAYS_ASK_AUDIO_ONLY_FORMATS_DETECTED_MSG}: {', '.join(audio_only_formats)}\n")
                temp_file.write(f"{safe_get_messages(user_id).ALWAYS_ASK_THESE_FORMATS_MP3_MSG}\n")
            temp_file_path = temp_file.name
        try:
            caption = f"{safe_get_messages(user_id).ALWAYS_ASK_AVAILABLE_FORMATS_FOR_MSG}:\n<code>{url}</code>\n\n"
            caption += f"{safe_get_messages(user_id).ALWAYS_ASK_HOW_TO_SET_FORMAT_MSG}\n"
            caption += f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_ID_134_MSG}\n"
            caption += f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_720P_MSG}\n"
            caption += f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_BEST_MSG}\n"
            caption += f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_ASK_MSG}\n\n"
            if video_only_formats:
                video_formats_text = ", ".join([f"<code>{fmt}</code>" for fmt in video_only_formats])
                caption += f"\n{safe_get_messages(user_id).LIST_VIDEO_ONLY_FORMATS_MSG.format(formats=video_formats_text)}\n"
            if audio_only_formats:
                audio_formats_text = ", ".join([f"<code>{fmt}</code>" for fmt in audio_only_formats])
                caption += f"{safe_get_messages(user_id).ALWAYS_ASK_AUDIO_ONLY_FORMATS_MSG}: {audio_formats_text}\n"
                caption += f"{safe_get_messages(user_id).ALWAYS_ASK_FORMAT_ID_140_AUDIO_CAPTION_MSG}\n"
                caption += f"{safe_get_messages(user_id).ALWAYS_ASK_THESE_WILL_BE_MP3_MSG}\n\n"
            caption += f"{safe_get_messages(user_id).ALWAYS_ASK_USE_FORMAT_ID_MSG}"
            app.send_document(
                user_id,
                document=temp_file_path,
                file_name=f"formats_{user_id}.txt",
                caption=caption,
                reply_parameters=ReplyParameters(message_id=original_message.id),
            )
            send_to_logger(original_message, safe_get_messages(user_id).LIST_COMMAND_EXECUTED_LOG_MSG.format(user_id=user_id, url=url))
        except Exception as e:
            logger.error(f"{LoggerMsg.ALWAYS_ASK_ERROR_SENDING_FORMATS_FILE_LOG_MSG}: {e}")
            app.send_message(
                user_id,
                safe_get_messages(user_id).AA_ERROR_SENDING_FORMATS_MSG.format(error=str(e)),
                reply_parameters=ReplyParameters(message_id=original_message.id),
            )
        finally:
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
    else:
        app.send_message(
            user_id,
            safe_get_messages(user_id).AA_FAILED_GET_FORMATS_MSG.format(output=output),
            reply_parameters=ReplyParameters(message_id=original_message.id),
        )
    try:
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
    except Exception as e:
        logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_DELETE_ALWAYS_ASK_MENU_LOG_MSG}: {e}")


def _execute_askq_image_action(app, callback_query, user_id: int, source_context: AlwaysAskSourceContext) -> None:
    original_message = source_context.original_message
    url_text = source_context.url_text
    logger.info(
        f"{LoggerMsg.ALWAYS_ASK_FALLBACK_DEBUG_ORIGINAL_MESSAGE_TEXT_LOG_MSG}: "
        f"{getattr(original_message, 'text', None)}"
    )
    logger.info(
        f"{LoggerMsg.ALWAYS_ASK_FALLBACK_DEBUG_ORIGINAL_MESSAGE_CAPTION_LOG_MSG}: "
        f"{getattr(original_message, 'caption', None)}"
    )
    logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_DEBUG_URL_TEXT_LOG_MSG}: {url_text}")
    import re as _re
    range_url_match = _re.search(r'(https?://[^\s\*#]+)\*(\d+)\*(\d+)', url_text)
    if range_url_match:
        url = range_url_match.group(1)
        start_range = int(range_url_match.group(2))
        end_range = int(range_url_match.group(3))
        logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_DEBUG_FOUND_RANGE_URL_LOG_MSG}: {url} with range {start_range}-{end_range}")
    else:
        m = _re.search(r'https?://[^\s\*#]+', url_text)
        url = m.group(0) if m else url_text
        start_range = 1
        end_range = 1
        logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_DEBUG_NO_RANGE_FOUND_LOG_MSG}: {url}")
    try:
        from HELPERS.porn import is_porn
        nsfw_enabled = bool(getattr(Config, "NSFW_CHECK_ENABLED", True))
        is_nsfw = bool(is_porn(url, "", "", None)) if nsfw_enabled else False
        logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_IS_PORN_CHECK_LOG_MSG} {url}: {is_nsfw}")
        user_forced_nsfw = bool(re.search(r"(?i)(?:^|\s)#nsfw(?:\s|$)", url_text)) if nsfw_enabled else False
        if user_forced_nsfw:
            is_nsfw = True
            logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_USER_FORCED_NSFW_TAG_DETECTED_LOG_MSG} {url}")
        parsed_url = url
        if start_range and end_range and start_range != 1 and end_range != 1:
            fallback_text = f"/img {start_range}-{end_range} {parsed_url}"
            logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_CONVERTING_RANGE_LOG_MSG}: *{start_range}*{end_range} -> {start_range}-{end_range}, fallback_text: {fallback_text}")
        else:
            fallback_text = f"/img {url}"
            logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_NO_RANGE_DETECTED_LOG_MSG}: {fallback_text}")
        if is_nsfw and "#nsfw" not in fallback_text.lower():
            fallback_text += " #nsfw"
            logger.info(f"{LoggerMsg.ALWAYS_ASK_FALLBACK_ADDED_NSFW_TAG_LOG_MSG}: {url}")
        fallback_branch = gallery_fallback_branch(None, origin="always_ask_menu", reason="explicit_image_menu_fallback")
        fallback_task = _make_callback_runtime_task(
            original_message,
            url=parsed_url,
            tags=["#nsfw"] if is_nsfw else [],
            tags_text="#nsfw" if is_nsfw else "",
            branch_result=fallback_branch,
            video_count=max(1, end_range - start_range + 1),
            video_start_with=start_range,
        )
        fallback_result = _dispatch_gallery_fallback(
            app,
            user_id=original_message.chat.id,
            fallback_text=fallback_text,
            original_chat_id=original_message.chat.id,
            message_thread_id=getattr(original_message, "message_thread_id", None),
            original_message=original_message,
            runtime_task=fallback_task,
        )
        logger.info(
            "Always Ask image fallback result: outcome=%s success=%s",
            fallback_result.outcome_kind
            if fallback_result is not None and is_gallery_command_result(fallback_result)
            else None,
            did_gallery_command_succeed(fallback_result)
            if fallback_result is not None and is_gallery_command_result(fallback_result)
            else None,
        )
    except Exception as e:
        logger.error(f"{LoggerMsg.ALWAYS_ASK_IMAGE_FALLBACK_FAILED_LOG_MSG}: {e}")
    try:
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
    except Exception as e:
        logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_DELETE_ALWAYS_ASK_MENU_LOG_MSG}: {e}")


def _execute_askq_quick_embed_action(app, callback_query, user_id: int, source_context: AlwaysAskSourceContext) -> None:
    original_message = source_context.original_message
    url = source_context.url
    embed_url = transform_to_embed_url(url)
    if embed_url == url:
        safe_callback_answer(callback_query, safe_get_messages(user_id).AA_ERROR_URL_NOT_EMBEDDABLE_MSG, show_alert=True)
        return
    app.send_message(
        callback_query.message.chat.id,
        embed_url,
        reply_parameters=ReplyParameters(message_id=original_message.id),
    )
    send_to_logger(original_message, safe_get_messages(user_id).QUICK_EMBED_LOG_MSG.format(embed_url=embed_url))
    safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])


def _execute_askq_other_format_selection(
    app,
    callback_query,
    user_id: int,
    source_context: AlwaysAskSourceContext | None,
    selection_plan: AlwaysAskOtherFormatSelectionPlan,
) -> None:
    if source_context is None or selection_plan.format_id is None:
        return

    logger.info("Processing other_id_ callback: %s", callback_query.data)
    format_id = selection_plan.format_id
    original_message = source_context.original_message
    url = source_context.url
    original_text = source_context.url_text
    _, _, _, _, tags, tags_text, _ = extract_url_range_tags(original_text)

    try:
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
        logger.info("Deleted Other menu message successfully")
    except Exception as e:
        logger.warning("Failed to delete Other menu message: %s", e)

    logger.info("Starting download process for format_id: %s", format_id)
    if is_playlist_with_range(original_text):
        logger.info("Detected playlist, using down_and_up")
        _, video_start_with, _, playlist_name, video_count = _build_quality_range_context(original_message)
        branch_result = _select_callback_download_branch(
            user_id,
            callback_data=callback_query.data,
            quality_intent=format_id,
            quality_key=format_id,
            format_override=format_id,
            video_count=video_count,
            origin="format_id_callback",
            provenance={"callback_data": callback_query.data},
            force_branch_family="video",
        )
        task = _make_callback_runtime_task(
            original_message,
            url=url,
            tags=tags,
            tags_text=tags_text,
            branch_result=branch_result,
            playlist_name=playlist_name,
            video_count=video_count,
            video_start_with=video_start_with,
        )
        _dispatch_callback_download_branch(
            app,
            original_message,
            task,
            clear_subs_cache_on_start=False,
        )
    else:
        logger.info("Single video, using down_and_up_with_format")
        branch_result = _select_callback_download_branch(
            user_id,
            callback_data=callback_query.data,
            quality_intent=format_id,
            quality_key=format_id,
            format_override=format_id,
            origin="format_id_callback",
            provenance={"callback_data": callback_query.data},
            force_branch_family="video",
        )
        task = _make_callback_runtime_task(
            original_message,
            url=url,
            tags=tags,
            tags_text=tags_text,
            branch_result=branch_result,
        )
        _dispatch_callback_download_branch(
            app,
            original_message,
            task,
        )
    logger.info("Download process initiated successfully")


def _execute_askq_manual_quality_selection(
    app,
    callback_query,
    user_id: int,
    source_context: AlwaysAskSourceContext | None,
    selection_plan: AlwaysAskManualQualitySelectionPlan,
    *,
    proc_msg=None,
) -> None:
    if source_context is None or selection_plan.quality is None or selection_plan.format_override is None:
        return

    original_message = source_context.original_message
    url = source_context.url
    original_text = source_context.url_text
    _, _, _, _, tags, tags_text, _ = extract_url_range_tags(original_text)

    try:
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
    except Exception:
        pass

    if is_playlist_with_range(original_text):
        _, video_start_with, _, playlist_name, video_count = _build_quality_range_context(original_message)
        branch_result = _select_callback_download_branch(
            user_id,
            callback_data=selection_plan.quality,
            quality_intent=selection_plan.quality,
            quality_key=selection_plan.quality_key,
            format_override=selection_plan.format_override,
            video_count=video_count,
            origin="manual_quality_callback",
            provenance={"quality": selection_plan.quality},
            force_branch_family="video" if selection_plan.branch_family == "video" else None,
        )
        task = _make_callback_runtime_task(
            original_message,
            url=url,
            tags=tags,
            tags_text=tags_text,
            branch_result=branch_result,
            playlist_name=playlist_name,
            video_count=video_count,
            video_start_with=video_start_with,
            proc_msg=proc_msg,
        )
        _dispatch_callback_download_branch(
            app,
            original_message,
            task,
            proc_msg=proc_msg,
            clear_subs_cache_on_start=False,
        )
        return

    branch_result = _select_callback_download_branch(
        user_id,
        callback_data=selection_plan.quality,
        quality_intent=selection_plan.quality,
        quality_key=selection_plan.quality_key,
        format_override=selection_plan.format_override,
        origin="manual_quality_callback",
        provenance={"quality": selection_plan.quality},
        force_branch_family="video" if selection_plan.branch_family == "video" else None,
    )
    task = _make_callback_runtime_task(
        original_message,
        url=url,
        tags=tags,
        tags_text=tags_text,
        branch_result=branch_result,
        proc_msg=proc_msg,
    )
    _dispatch_callback_download_branch(
        app,
        original_message,
        task,
        proc_msg=proc_msg,
    )


def _cleanup_other_qualities_format_cache(
    user_id: int,
    *,
    url: str,
    keep_current_cache: bool,
    cleanup_log_msg,
    cleanup_error_log_msg,
) -> None:
    try:
        user_dir = os.path.join("users", str(user_id))
        create_directory(user_dir)
        user_download_dir = get_user_download_dir(user_id)
        if user_download_dir and os.path.exists(user_download_dir):
            format_cache_pattern = os.path.join(user_download_dir, "formats_cache_*.json")
            current_cache_file = os.path.join(
                user_download_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json"
            )
        else:
            format_cache_pattern = os.path.join(user_dir, "formats_cache_*.json")
            current_cache_file = os.path.join(
                user_dir, f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json"
            )

        import glob

        old_cache_files = glob.glob(format_cache_pattern)
        removed_count = 0
        for cache_file in old_cache_files:
            if keep_current_cache and cache_file == current_cache_file:
                continue
            try:
                os.remove(cache_file)
                removed_count += 1
                logger.info(f"{LoggerMsg.ALWAYS_ASK_CLEANED_UP_OLD_FORMAT_CACHE_LOG_MSG}: {cache_file}")
            except Exception as e:
                logger.warning(f"{LoggerMsg.ALWAYS_ASK_FAILED_TO_REMOVE_OLD_CACHE_FILE_LOG_MSG} {cache_file}: {e}")
        if removed_count:
            logger.info(f"{cleanup_log_msg}: {removed_count}")
    except Exception as e:
        logger.warning(f"{cleanup_error_log_msg}: {e}")


def _execute_askq_navigation_plan(
    app,
    callback_query,
    user_id: int,
    source_context: AlwaysAskSourceContext | None,
    navigation_plan: AlwaysAskNavigationPlan,
) -> None:
    if navigation_plan.answer_text:
        safe_callback_answer(
            callback_query,
            navigation_plan.answer_text,
            show_alert=navigation_plan.show_alert,
        )
    if navigation_plan.mode == "error" or source_context is None:
        return

    original_message = source_context.original_message
    url = navigation_plan.url or source_context.url

    if navigation_plan.mode == "other_page":
        _cleanup_other_qualities_format_cache(
            user_id,
            url=url,
            keep_current_cache=navigation_plan.keep_current_cache,
            cleanup_log_msg=LoggerMsg.ALWAYS_ASK_CLEANED_UP_OLD_FORMAT_CACHE_FILES_DURING_NAVIGATION_LOG_MSG,
            cleanup_error_log_msg=LoggerMsg.ALWAYS_ASK_ERROR_CLEANING_UP_OLD_FORMAT_CACHE_FILES_DURING_NAVIGATION_LOG_MSG,
        )
        user_download_dir = get_user_download_dir(user_id)
        if user_download_dir and os.path.exists(user_download_dir):
            cache_file = os.path.join(
                user_download_dir,
                f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json",
            )
        else:
            cache_file = os.path.join(
                "users",
                str(user_id),
                f"formats_cache_{hashlib.md5(url.encode()).hexdigest()[:8]}.json",
            )
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                format_lines = cached_data.get("formats", [])
                if format_lines:
                    show_formats_from_cache(app, callback_query, format_lines, navigation_plan.page or 0, url)
                    return
            except Exception:
                pass
        show_other_qualities_menu(app, callback_query, navigation_plan.page or 0)
        return

    if navigation_plan.mode == "reopen_quality_menu":
        _cleanup_other_qualities_format_cache(
            user_id,
            url=url,
            keep_current_cache=navigation_plan.keep_current_cache,
            cleanup_log_msg=LoggerMsg.ALWAYS_ASK_CLEANED_UP_OLD_FORMAT_CACHE_FILES_BEFORE_RETURNING_TO_MAIN_MENU_LOG_MSG,
            cleanup_error_log_msg=LoggerMsg.ALWAYS_ASK_ERROR_CLEANING_UP_OLD_FORMAT_CACHE_FILES_BEFORE_RETURNING_TO_MAIN_MENU_LOG_MSG,
        )
        ask_quality_menu(app, original_message, url, [], playlist_start_index=1, cb=callback_query)
        return

    if navigation_plan.mode == "manual_back":
        tags = []
        caption_text = getattr(callback_query.message, "caption", None)
        if caption_text:
            tag_matches = re.findall(r'#\S+', caption_text)
            if tag_matches:
                tags = tag_matches
        safe_delete_messages(chat_id=callback_query.message.chat.id, message_ids=[callback_query.message.id])
        ask_quality_menu(app, original_message, url, tags)


def analyze_format_type(format_info):
    """
    Analyze format info to determine if it's audio-only, video-only, or full format
    Returns: 'audio_only', 'video_only', or 'full'
    """
    vcodec = format_info.get('vcodec', 'none')
    acodec = format_info.get('acodec', 'none')
    
    # Check if it's audio only
    if vcodec == 'none' and acodec != 'none':
        return 'audio_only'
    
    # Check if it's video only
    if vcodec != 'none' and acodec == 'none':
        return 'video_only'
    
    # Full format (both video and audio)
    return 'full'

def get_complementary_audio_format(video_format_info, all_formats):
    """
    Find the best complementary audio format for a video-only format
    Returns the best audio format or None
    """
    video_height = video_format_info.get('height', 0)
    video_width = video_format_info.get('width', 0)
    
    best_audio = None
    best_quality = 0
    
    for f in all_formats:
        # Look for audio-only formats
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            # Prefer audio with similar quality to video
            audio_height = f.get('height', 0)
            audio_width = f.get('width', 0)
            
            # Calculate quality score (prefer higher bitrate/quality)
            quality_score = 0
            if f.get('abr'):
                quality_score += float(f['abr'])
            if f.get('tbr'):
                quality_score += float(f['tbr'])
            
            # Bonus for matching resolution
            if audio_height == video_height and audio_width == video_width:
                quality_score += 1000
            
            if quality_score and quality_score > best_quality:
                best_quality = quality_score
                best_audio = f
    
    return best_audio

# --- an auxiliary function for downloading with the format ---
# @reply_with_keyboard
def down_and_up_with_format(app, message, url=None, fmt=None, tags_text="", quality_key=None, proc_msg=None, task_context: RuntimeTask | None = None):
    messages = safe_get_messages(message.chat.id)
    user_id = message.chat.id
    task_context = ensure_runtime_task(
        task=task_context,
        user_id=user_id,
        source_message_id=getattr(message, "id", None),
        url=url or "",
        tags_text=tags_text,
        proc_msg_id=getattr(proc_msg, "id", None),
    )
    url = task_context.url
    tags_text = task_context.tags_text
    playlist_name = task_context.playlist_name
    video_count = task_context.video_count
    video_start_with = task_context.video_start_with
    if task_context.proc_msg_id is not None and proc_msg is None:
        proc_msg = type("ProcMsgRef", (), {"id": task_context.proc_msg_id})()
    branch_result = task_context.branch_selection_result
    if branch_result is not None:
        log_branch_selection(logger, branch_result, user_id=user_id)
    
    # Check if there is a link to Tiktok
    is_tiktok = is_tiktok_url(url)
    task_context = task_context.with_force_no_title(is_tiktok)
    
    user_id = message.chat.id
    try:
        use_direct_link, direct_link_source = resolve_direct_link_preference(
            branch_result,
            user_id=user_id,
            ambient_link_mode_reader=get_link_mode,
        )
        if use_direct_link:
            logger.info(
                f"Direct-link path active for user {user_id}, "
                f"source={direct_link_source}"
            )
            
            from COMMANDS.link_cmd import get_direct_link
            result = execute_direct_link_flow(
                fetch_direct_link=get_direct_link,
                response_sender=send_always_ask_direct_link_response,
                app=app,
                message=message,
                user_id=user_id,
                url=url,
                quality_key=quality_key,
                cookies_already_checked=True,
                use_proxy=True,
            )
            
            if result.get('success'):
                send_to_logger(message, safe_get_messages(user_id).DIRECT_LINK_EXTRACTED_DOWN_UP_LOG_MSG.format(user_id=user_id, url=url))
                
            else:
                error_msg = result.get('error', 'Unknown error')
                log_error_to_channel(message, safe_get_messages(user_id).DIRECT_LINK_FAILED_DOWN_UP_LOG_MSG.format(user_id=user_id, url=url, error=error_msg), url)
            
            return
    except Exception as e:
        logger.error(f"Error checking direct-link path for user {user_id}: {e}")
        # Continue with normal download if direct-link check fails

    # Check if format contains /bestaudio (audio-only format)
    logger.info(f"Checking format: {fmt} for /bestaudio")
    if fmt and '/bestaudio' in fmt:
        logger.info(f"Audio-only format detected: {fmt}, redirecting to down_and_audio")
        audio_branch_result = redirected_audio_branch(
            branch_result,
            quality_key=quality_key,
            format_override=fmt,
            reason="down_and_up_with_format_detected_bestaudio",
        )
        # Delete processing message before starting download
        delete_processing_message(app, user_id, proc_msg)
        audio_task = (
            with_branch_selection(task_context, audio_branch_result)
            if audio_branch_result is not None
            else task_context
        )
        down_and_audio(
            app,
            message,
            quality_key=quality_key,
            format_override=fmt,
            cookies_already_checked=True,
            task_context=audio_task,
        )
        return

    # Analyze the format to determine if it's audio-only, video-only, or full
    format_type = None
    complementary_format = None
    info = None  # Initialize info variable
    
    try:
        # Get video info to analyze the selected format
        user_id = message.chat.id
        # Try to load cached info first to avoid redundant API calls
        cached_info = load_ask_info(user_id, url)
        if cached_info:
            info = cached_info
            logger.info(f"✅ [OPTIMIZATION] Using cached video info for format analysis")
        else:
            info = get_video_formats(url, user_id, cookies_already_checked=True)
            logger.info(f"⚠️ [OPTIMIZATION] Had to fetch video info again - consider improving caching")
        task_context = task_context.with_cached_video_info(info)
        
        if quality_key and info and 'formats' in info:
            # Find the selected format
            selected_format = None
            for f in info['formats']:
                if not isinstance(f, dict):
                    continue
                if f.get('format_id') == quality_key:
                    selected_format = f
                    break
            
            if selected_format:
                format_type = analyze_format_type(selected_format)
                
                # If it's audio-only, convert to user's preferred audio format
                if format_type == 'audio_only':
                    audio_branch_result = redirected_audio_branch(
                        branch_result,
                        quality_key=quality_key,
                        format_override=fmt,
                        reason="selected_format_resolved_to_audio_only",
                    )
                    # Use audio download function with the selected format
                    # Pass cookies_already_checked=True since we already checked cookies in get_video_formats
                    # Delete processing message before starting download
                    delete_processing_message(app, user_id, proc_msg)
                    audio_task = (
                        with_branch_selection(task_context, audio_branch_result)
                        if audio_branch_result is not None
                        else task_context
                    )
                    down_and_audio(
                        app,
                        message,
                        quality_key=quality_key,
                        format_override=fmt,
                        cookies_already_checked=True,
                        task_context=audio_task,
                    )
                    return
                
                # If it's video-only, find complementary audio
                elif format_type == 'video_only':
                    complementary_format = get_complementary_audio_format(selected_format, info['formats'])
                    if complementary_format:
                        # Create a format string that merges video-only with best audio
                        video_format_id = selected_format.get('format_id', '')
                        audio_format_id = complementary_format.get('format_id', '')
                        fmt = f"{video_format_id}+{audio_format_id}/bv+ba/best"
                    else:
                        # If no complementary audio found, use best audio
                        fmt = f"{selected_format.get('format_id', '')}+bestaudio/bv+ba/best"
                
                # If it's full format, use as is
                else:
                    # Use the original format
                    pass
    except Exception as e:
        logger.warning(f"Error analyzing format type: {e}")
        # Continue with original format if analysis fails
        # info remains None if there was an error

    # We call the main function of loading with the correct parameters of the playlist
    # Pass cookies_already_checked=True since we already checked cookies in get_video_formats
    # Pass cached video info to avoid redundant API calls
    # Delete processing message before starting download
    delete_processing_message(app, user_id, proc_msg)
    down_and_up(
        app,
        message,
        format_override=fmt,
        quality_key=quality_key,
        cookies_already_checked=True,
        task_context=task_context,
    )
    # Cleanup temp subs languages cache after we kicked off download
    try:
        delete_subs_langs_cache(message.chat.id, url)
    except Exception:
        pass

    # Save detected qualities per filters to a per-user file for all services
    try:
        # Use download directory if available, otherwise fallback to user directory
        download_dir = get_user_download_dir(user_id)
        if download_dir and os.path.exists(download_dir):
            qfile = os.path.join(download_dir, "available_qualities.txt")
            logger.info(f"Saving available_qualities.txt to download directory: {qfile}")
        else:
            user_dir = os.path.join("users", str(user_id))
            create_directory(user_dir)
            qfile = os.path.join(user_dir, "available_qualities.txt")
            logger.info(f"Saving available_qualities.txt to user directory: {qfile}")
        
        # Get current filters
        filters_state = get_filters(user_id)
        sel_codec = filters_state.get("codec", "avc1")
        sel_ext = filters_state.get("ext", "mp4")
        
        # Build quality map from available formats (only if info is available)
        quality_map = {}
        if info and 'formats' in info:
            for f in info.get('formats', []):
                if not isinstance(f, dict):
                    continue
                if f.get('vcodec', 'none') != 'none' and f.get('height') and f.get('width'):
                    w = int(f.get('width') or 0)
                    h = int(f.get('height') or 0)
                    quality_key = get_quality_by_min_side(w, h)
                    if quality_key != "best":
                        quality_map[quality_key] = f
        
        payload = {
            "url": info.get('webpage_url') if info else url,
            "sel_codec": sel_codec,
            "sel_ext": sel_ext,
            "qualities": sorted(list(quality_map.keys()), key=sort_quality_key)
        }
        import json as _json
        with open(qfile, "w", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning(f"Failed to save available_qualities.txt: {e}")
    
