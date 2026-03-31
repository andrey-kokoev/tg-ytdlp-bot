
# ########################################
# Down_and_audio function
# ########################################

import os
from HELPERS.logger import get_log_channel
from CONFIG.logger_msg import LoggerMsg
import threading
import time
import yt_dlp
from pyrogram.errors import FloodWait
from HELPERS.app_instance import get_app
from HELPERS.logger import logger, send_to_logger, send_to_user, send_error_to_user, log_error_to_channel
from HELPERS.limitter import TimeFormatter
from HELPERS.download_status import (
    set_active_download,
    clear_download_start_time,
    check_download_timeout,
    start_hourglass_animation,
    start_cycle_progress,
    clear_playlist_error_state,
    get_playlist_error_summary,
    mark_playlist_error,
)
from HELPERS.safe_messeger import safe_delete_messages, safe_edit_message_text, safe_forward_messages
from HELPERS.filesystem_hlp import sanitize_filename_strict, create_directory, check_disk_space, cleanup_user_temp_files
from DATABASE.firebase_init import write_logs
from URL_PARSERS.tags import generate_final_tags
from services.stats_events import update_download_progress
from URL_PARSERS.nocookie import is_no_cookie_domain
from URL_PARSERS.filter_check import is_no_filter_domain
from URL_PARSERS.filter_utils import create_smart_match_filter
from URL_PARSERS.youtube import is_youtube_url, download_thumbnail
from URL_PARSERS.thumbnail_downloader import download_thumbnail as download_universal_thumbnail
from HELPERS.pot_helper import add_pot_to_ytdl_opts
from CONFIG.limits import LimitsConfig
import subprocess
from urllib.parse import urlparse
from PIL import Image
import io
from CONFIG.config import Config
from CONFIG.messages import safe_get_messages
from COMMANDS.subtitles_cmd import is_subs_enabled, check_subs_availability, get_user_subs_auto_mode, _subs_check_cache, download_subtitles_ytdlp, is_subs_always_ask
from COMMANDS.mediainfo_cmd import send_mediainfo_if_enabled
from DOWN_AND_UP.gallery_command_result import (
    did_gallery_command_fail,
    did_gallery_command_succeed,
    is_handled_gallery_command_result,
)
from URL_PARSERS.playlist_utils import is_playlist_with_range
from URL_PARSERS.normalizer import get_clean_playlist_url
from DATABASE.cache_db import get_cached_playlist_videos, get_cached_message_ids, save_to_video_cache, save_to_playlist_cache
from pyrogram.types import ReplyParameters
from HELPERS.safe_messeger import safe_send_message
from pyrogram import enums
from URL_PARSERS.tags import extract_url_range_tags
from DOWN_AND_UP.branch_selection_result import (
    log_branch_selection,
    resolve_direct_link_preference,
)
from DOWN_AND_UP.direct_link_flow import (
    execute_direct_link_flow,
    send_standard_direct_link_response,
)
from DOWN_AND_UP.terminal_outcome_result import (
    downgrade_completed_outcome_to_partial,
    failed_terminal_outcome,
    format_playlist_error_summary_suffix,
    format_audio_terminal_status,
    format_audio_failure_status,
    upload_terminal_outcome,
)
from DOWN_AND_UP.runtime_task import RuntimeTask, ensure_runtime_task
from DOWN_AND_UP.task_terminal_flow import attach_and_render_terminal_outcome
from DOWN_AND_UP.playlist_flow import build_requested_indices, send_playlist_cache_status
from DOWN_AND_UP.retry_flow import (
    maybe_retry_with_different_cookies,
    maybe_retry_with_proxy_on_geo_error,
)
from DOWN_AND_UP.preflight_flow import (
    cleanup_download_dir_before_start,
    ensure_user_download_dir,
    start_processing_handshake,
)
from DOWN_AND_UP.cache_flow import (
    lookup_single_cached_ids,
    try_repost_single_cached_media,
)

# Get app instance for decorators
app = get_app()



def _send_audio_failure(
    message,
    user_id: int,
    *,
    failure_kind: str,
    error_text: str | None = None,
    rendered_text: str | None = None,
    attempted_count: int = 0,
    delivered_count: int = 0,
    use_error_channel: bool = False,
    task_context: RuntimeTask | None = None,
) -> None:
    outcome = failed_terminal_outcome(
        media_kind="audio",
        failure_kind=failure_kind,
        error_text=error_text,
        attempted_count=attempted_count,
        delivered_count=delivered_count,
    )
    _, text = attach_and_render_terminal_outcome(
        user_id=user_id,
        outcome=outcome,
        task_context=task_context,
        formatter=format_audio_failure_status,
        rendered_text=rendered_text,
    )
    if use_error_channel:
        send_error_to_user(message, text)
    else:
        send_to_user(message, text)


def _resolve_audio_task_inputs(
    *,
    task_context: RuntimeTask | None,
    user_id: int,
    message,
    url,
    tags,
    playlist_name,
    video_count,
    video_start_with,
    cached_video_info,
):
    task_context = ensure_runtime_task(
        task=task_context,
        user_id=user_id,
        source_message_id=getattr(message, "id", None),
        url=url or "",
        tags_text=" ".join(tags or []),
        tags=list(tags) if tags is not None else None,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        cached_video_info=cached_video_info,
    )
    resolved_tags = task_context.tags if task_context.tags is not None else tags
    if resolved_tags is None:
        resolved_tags = []
    resolved_cached_video_info = (
        task_context.cached_video_info
        if task_context.cached_video_info is not None
        else cached_video_info
    )
    return (
        task_context,
        task_context.url,
        resolved_tags,
        task_context.playlist_name,
        task_context.video_count,
        task_context.video_start_with,
        resolved_cached_video_info,
    )


def _is_nsfw_audio_delivery(url: str, user_forced_nsfw: bool) -> bool:
    from HELPERS.porn import is_porn

    detected_nsfw = is_porn(url, "", "", None)
    is_nsfw = detected_nsfw or user_forced_nsfw
    logger.info(
        f"[FALLBACK] is_porn check for {url}: {detected_nsfw}, "
        f"user_forced_nsfw: {user_forced_nsfw}, final is_nsfw: {is_nsfw}"
    )
    return is_nsfw


def _send_paid_audio_media(
    *,
    user_id: int,
    audio_file: str,
    telegram_thumb: str | None,
    message,
):
    from pyrogram.types import InputPaidMediaAudio

    paid_audio = InputPaidMediaAudio(
        media=audio_file,
        thumb=telegram_thumb if telegram_thumb and os.path.exists(telegram_thumb) else None,
    )
    return app.send_paid_media(
        chat_id=user_id,
        media=[paid_audio],
        star_count=LimitsConfig.NSFW_STAR_COST,
        payload=str(Config.STAR_RECEIVER),
        reply_parameters=ReplyParameters(message_id=message.id),
    )


def _send_regular_audio_media(
    *,
    user_id: int,
    audio_file: str,
    caption_with_link: str,
    telegram_thumb: str | None,
    message,
    file_ext: str,
):
    if file_ext in {".mp3", ".m4a"}:
        kwargs = {
            "chat_id": user_id,
            "audio": audio_file,
            "caption": caption_with_link,
            "reply_parameters": ReplyParameters(message_id=message.id),
        }
        if telegram_thumb and os.path.exists(telegram_thumb):
            kwargs["thumb"] = telegram_thumb
            logger.info(f"Audio sent with Telegram thumbnail: {telegram_thumb}")
        else:
            logger.info("Audio sent without thumbnail")
        return app.send_audio(**kwargs)
    logger.info(f"Audio sent as document (format: {file_ext})")
    return app.send_document(
        chat_id=user_id,
        document=audio_file,
        caption=caption_with_link,
        reply_parameters=ReplyParameters(message_id=message.id),
    )


def _send_audio_to_user(
    *,
    user_id: int,
    audio_file: str,
    caption_with_link: str,
    telegram_thumb: str | None,
    message,
    file_ext: str,
    is_paid: bool,
):
    if is_paid:
        try:
            audio_msg = _send_paid_audio_media(
                user_id=user_id,
                audio_file=audio_file,
                telegram_thumb=telegram_thumb,
                message=message,
            )
            logger.info("Paid NSFW audio sent to user")
            return audio_msg
        except Exception as e:
            logger.error(f"Failed to send paid audio, falling back to regular: {e}")
    return _send_regular_audio_media(
        user_id=user_id,
        audio_file=audio_file,
        caption_with_link=caption_with_link,
        telegram_thumb=telegram_thumb,
        message=message,
        file_ext=file_ext,
    )


def _route_uploaded_audio_to_logs(
    *,
    message,
    user_id: int,
    audio_msg,
    audio_file: str,
    caption_with_link: str,
    telegram_thumb: str | None,
    url: str,
    user_forced_nsfw: bool,
):
    is_nsfw = _is_nsfw_audio_delivery(url, user_forced_nsfw)
    is_private_chat = getattr(message.chat, "type", None) == enums.ChatType.PRIVATE
    is_paid = is_nsfw and is_private_chat
    result = {"forwarded_msg": None, "is_nsfw": is_nsfw, "is_paid": is_paid}

    if is_paid:
        log_channel_paid = get_log_channel("video", paid=True)
        try:
            safe_forward_messages(log_channel_paid, user_id, [audio_msg.id])
            logger.info("down_and_audio: NSFW audio paid copy sent to PAID channel")
        except Exception as e:
            logger.error(f"down_and_audio: failed to send paid copy to PAID channel: {e}")

        log_channel_nsfw = get_log_channel("video", nsfw=True)
        try:
            app.send_audio(
                chat_id=log_channel_nsfw,
                audio=audio_file,
                caption=caption_with_link,
                reply_parameters=ReplyParameters(message_id=message.id),
                thumb=telegram_thumb if telegram_thumb and os.path.exists(telegram_thumb) else None,
            )
            logger.info("down_and_audio: NSFW audio open copy sent to NSFW channel for history")
        except Exception as e:
            logger.error(f"down_and_audio: failed to send open copy to NSFW channel: {e}")

        logger.info(
            "down_and_audio: NSFW audio sent to user (paid), PAID channel "
            "(paid copy), and NSFW channel (open copy), not cached"
        )
        return result

    if is_nsfw:
        log_channel = get_log_channel("video", nsfw=True)
        result["forwarded_msg"] = safe_forward_messages(log_channel, user_id, [audio_msg.id])
        logger.info("down_and_audio: NSFW audio sent to NSFW channel, not cached")
        result["forwarded_msg"] = None
        return result

    log_channel = get_log_channel("video")
    result["forwarded_msg"] = safe_forward_messages(log_channel, user_id, [audio_msg.id])
    return result


def _cache_audio_delivery(
    *,
    forwarded_msg,
    is_nsfw: bool,
    quality_key,
    is_playlist: bool,
    original_playlist_index: int,
    url: str,
    message,
    user_id: int,
    playlist_indices: list,
    playlist_msg_ids: list,
) -> None:
    if not quality_key or not forwarded_msg or is_nsfw:
        if is_nsfw:
            logger.info(f"down_and_audio: skipping cache for NSFW content (url={url})")
        return

    msg_ids = [m.id for m in forwarded_msg] if isinstance(forwarded_msg, list) else [forwarded_msg.id]
    if is_playlist:
        logger.info(
            f"down_and_audio: saving to playlist cache: index={original_playlist_index}, msg_ids={msg_ids}"
        )
        save_to_playlist_cache(
            get_clean_playlist_url(url),
            quality_key,
            [original_playlist_index],
            msg_ids,
            original_text=message.text or message.caption or "",
            video_urls_dict=None,
        )
        cached_check = get_cached_playlist_videos(
            get_clean_playlist_url(url), quality_key, [original_playlist_index]
        )
        logger.info(f"Checking the cache immediately after writing: {cached_check}")
        playlist_indices.append(original_playlist_index)
        playlist_msg_ids.extend(msg_ids)
        return

    logger.info(f"down_and_audio: saving to video cache: msg_ids={msg_ids}")
    save_to_video_cache(
        url,
        quality_key,
        msg_ids,
        original_text=message.text or message.caption or "",
        user_id=user_id,
    )


def _finalize_completed_audio_outcome(
    *,
    user_id: int,
    proc_msg_id: int,
    message,
    outcome,
    task_context: RuntimeTask | None,
):
    credits_msg = safe_get_messages(user_id).CREDITS_MSG
    task_context, success_msg = attach_and_render_terminal_outcome(
        user_id=user_id,
        outcome=outcome,
        task_context=task_context,
        formatter=lambda messages, rendered_outcome: format_audio_terminal_status(
            messages,
            rendered_outcome,
            include_credits=not bool(getattr(Config, "HIDE_CREDITS_MSG", False)),
            credits_msg=credits_msg,
        ),
    )
    try:
        safe_edit_message_text(user_id, proc_msg_id, success_msg)
    except Exception as e:
        logger.error(f"Error updating final status: {e}")
    send_to_logger(message, success_msg + format_playlist_error_summary_suffix(outcome))
    return task_context


def _cleanup_successful_audio_download_dir(user_id: int) -> None:
    try:
        from DOWN_AND_UP.always_ask_menu import get_user_download_dir

        download_dir = get_user_download_dir(user_id)
        if download_dir and os.path.exists(download_dir):
            logger.info(f"Cleaning up download subdirectory after successful audio upload: {download_dir}")
            import shutil

            shutil.rmtree(download_dir)
            logger.info(f"Successfully removed download subdirectory: {download_dir}")
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up download subdirectory for user {user_id}: {cleanup_error}")


@dataclass(frozen=True)
class AudioCompletionPlan:
    mode: str
    should_finalize: bool
    should_cleanup_download_dir: bool
    should_send_playlist_status: bool


def _build_audio_completion_plan(
    *,
    is_playlist: bool,
    quality_key,
    outcome,
) -> AudioCompletionPlan:
    return AudioCompletionPlan(
        mode="playlist" if is_playlist and quality_key else "single",
        should_finalize=True,
        should_cleanup_download_dir=True,
        should_send_playlist_status=bool(is_playlist and quality_key and outcome.outcome_kind == "completed"),
    )


def _execute_audio_completion_plan(
    *,
    plan: AudioCompletionPlan,
    app,
    user_id: int,
    proc_msg_id: int,
    message,
    outcome,
    task_context: RuntimeTask | None,
    requested_indices: list,
    quality_key,
) -> RuntimeTask | None:
    if plan.should_finalize:
        task_context = _finalize_completed_audio_outcome(
            user_id=user_id,
            proc_msg_id=proc_msg_id,
            message=message,
            outcome=outcome,
            task_context=task_context,
        )
    if plan.should_cleanup_download_dir:
        _cleanup_successful_audio_download_dir(user_id)
    if plan.should_send_playlist_status:
        _send_playlist_audio_terminal_status(
            app=app,
            user_id=user_id,
            reply_to_message_id=message.id,
            message=message,
            outcome=outcome,
            requested_indices=requested_indices,
            quality_key=quality_key,
        )
    return task_context


def _send_playlist_audio_terminal_status(
    *,
    app,
    user_id: int,
    reply_to_message_id: int,
    message,
    outcome,
    requested_indices: list,
    quality_key,
):
    send_playlist_cache_status(
        app=app,
        user_id=user_id,
        reply_to_message_id=reply_to_message_id,
        text=safe_get_messages(user_id).PLAYLIST_SENT_MSG.format(
            sent=outcome.total_sent_count,
            total=len(requested_indices),
        ),
    )


@dataclass(frozen=True)
class AudioRetryOutcomePlan:
    mode: str
    should_retry: bool
    should_send_final_error: bool
    failure_kind: str | None = None


def _build_audio_retry_outcome_plan(
    *,
    error_text: str,
    error_message_sent: bool,
) -> AudioRetryOutcomePlan:
    if "Postprocessing" in error_text and "Error opening output files" in error_text:
        return AudioRetryOutcomePlan(
            mode="postprocessing_invalid_chars",
            should_retry=False,
            should_send_final_error=False,
            failure_kind="postprocessing_failed",
        )
    if "Postprocessing" in error_text and "Invalid argument" in error_text:
        return AudioRetryOutcomePlan(
            mode="postprocessing_invalid_argument",
            should_retry=False,
            should_send_final_error=False,
            failure_kind="postprocessing_failed",
        )
    return AudioRetryOutcomePlan(
        mode="generic",
        should_retry=not error_message_sent,
        should_send_final_error=not error_message_sent,
        failure_kind="download_failed",
    )
    send_to_logger(
        message,
        safe_get_messages(user_id).PLAYLIST_AUDIO_SENT_LOG_MSG.format(
            sent=outcome.total_sent_count,
            total=len(requested_indices),
            quality=quality_key,
            user_id=user_id,
        ) + format_playlist_error_summary_suffix(outcome),
    )


def _try_remote_audio_youtube_cookie_sources(
    *,
    user_id: int,
    url: str,
    cookie_urls: list[str],
    downloaded_cookie_path: str,
):
    from COMMANDS.cookies_cmd import (
        _download_content,
        get_unchecked_cookie_sources,
        mark_cookie_source_checked,
        test_youtube_cookies_on_url,
    )

    unchecked_indices = get_unchecked_cookie_sources(user_id, cookie_urls)
    if not unchecked_indices:
        logger.warning(
            "All cookie sources have been checked for user %s, no more sources to try",
            user_id,
        )
        return None

    for idx in unchecked_indices:
        cookie_url = cookie_urls[idx]
        logger.info(
            "Trying YouTube cookie source %s/%s for user %s",
            idx + 1,
            len(cookie_urls),
            user_id,
        )
        mark_cookie_source_checked(user_id, idx)
        try:
            ok, _status, content, _err = _download_content(
                cookie_url,
                timeout=30,
                user_id=user_id,
            )
            if ok and content and len(content) <= 100 * 1024:
                with open(downloaded_cookie_path, "wb") as cf:
                    cf.write(content)
                if test_youtube_cookies_on_url(downloaded_cookie_path, url, user_id):
                    logger.info(
                        "YouTube cookies from source %s work on user's URL for user %s",
                        idx + 1,
                        user_id,
                    )
                    return downloaded_cookie_path
                if os.path.exists(downloaded_cookie_path):
                    os.remove(downloaded_cookie_path)
        except Exception as e:
            logger.error(
                "Error processing YouTube cookie source %s for user %s: %s",
                idx + 1,
                user_id,
                e,
            )
    return None


def _resolve_audio_youtube_cookiefile(
    *,
    user_id: int,
    url: str,
    user_cookie_path: str,
    downloaded_cookie_path: str,
):
    from COMMANDS.cookies_cmd import (
        get_youtube_cookie_urls,
        test_youtube_cookies_on_url,
    )

    user_cookie_exists = os.path.exists(user_cookie_path)
    cookie_urls = get_youtube_cookie_urls()

    if user_cookie_exists:
        logger.info("Checking existing YouTube cookies on user's URL for user %s", user_id)
        if test_youtube_cookies_on_url(user_cookie_path, url, user_id):
            logger.info(
                "Existing YouTube cookies work on user's URL for user %s - using them",
                user_id,
            )
            return user_cookie_path

        logger.warning(
            "Existing YouTube cookies failed validation on user's URL for user %s; "
            "keeping them as download fallback and trying remote sources",
            user_id,
        )
        if cookie_urls:
            resolved_cookie = _try_remote_audio_youtube_cookie_sources(
                user_id=user_id,
                url=url,
                cookie_urls=cookie_urls,
                downloaded_cookie_path=downloaded_cookie_path,
            )
            if resolved_cookie:
                return resolved_cookie
        else:
            logger.warning(
                "No YouTube cookie sources configured for user %s; "
                "falling back to existing user cookie for actual download",
                user_id,
            )
        logger.warning(
            "All remote YouTube cookie sources failed for user %s; "
            "falling back to existing user cookie for actual download",
            user_id,
        )
        return user_cookie_path

    logger.info("No YouTube cookies found for user %s, attempting to get new ones", user_id)
    if not cookie_urls:
        logger.warning(
            "No YouTube cookie sources configured for user %s, will try without cookies",
            user_id,
        )
        return None

    resolved_cookie = _try_remote_audio_youtube_cookie_sources(
        user_id=user_id,
        url=url,
        cookie_urls=cookie_urls,
        downloaded_cookie_path=downloaded_cookie_path,
    )
    if resolved_cookie:
        return resolved_cookie

    logger.warning(
        "All YouTube cookie sources failed for user %s, will try without cookies",
        user_id,
    )
    return None


def _resolve_audio_cookiefile(*, user_id: int, url: str, user_folder: str):
    user_cookie_path = os.path.join(user_folder, "cookie.txt")
    downloaded_cookie_path = os.path.join(user_folder, "_downloaded_cookie.txt")

    if is_youtube_url(url):
        return _resolve_audio_youtube_cookiefile(
            user_id=user_id,
            url=url,
            user_cookie_path=user_cookie_path,
            downloaded_cookie_path=downloaded_cookie_path,
        )

    from COMMANDS.cookies_cmd import get_cookie_cache_result

    cache_result = get_cookie_cache_result(user_id, url)
    if cache_result and cache_result["result"]:
        logger.info("Using cached cookies for non-YouTube audio URL: %s", url)
        return cache_result["cookie_path"]

    if os.path.exists(user_cookie_path):
        logger.info("Using user cookies for non-YouTube audio URL: %s", url)
        return user_cookie_path

    logger.info(
        "No user cookies found for non-YouTube audio URL: %s, will try fallback during download",
        url,
    )
    return None


def _apply_audio_proxy_settings(ytdl_opts, *, use_proxy: bool, url: str, user_id: int):
    if use_proxy:
        from COMMANDS.proxy_cmd import get_proxy_config

        proxy_config = get_proxy_config()
        if proxy_config and "type" in proxy_config and "ip" in proxy_config and "port" in proxy_config:
            if proxy_config["type"] == "http":
                if proxy_config.get("user") and proxy_config.get("password"):
                    proxy_url = (
                        f"http://{proxy_config['user']}:{proxy_config['password']}@"
                        f"{proxy_config['ip']}:{proxy_config['port']}"
                    )
                else:
                    proxy_url = f"http://{proxy_config['ip']}:{proxy_config['port']}"
            elif proxy_config["type"] == "https":
                if proxy_config.get("user") and proxy_config.get("password"):
                    proxy_url = (
                        f"https://{proxy_config['user']}:{proxy_config['password']}@"
                        f"{proxy_config['ip']}:{proxy_config['port']}"
                    )
                else:
                    proxy_url = f"https://{proxy_config['ip']}:{proxy_config['port']}"
            elif proxy_config["type"] in ["socks4", "socks5", "socks5h"]:
                if proxy_config.get("user") and proxy_config.get("password"):
                    proxy_url = (
                        f"{proxy_config['type']}://{proxy_config['user']}:{proxy_config['password']}@"
                        f"{proxy_config['ip']}:{proxy_config['port']}"
                    )
                else:
                    proxy_url = f"{proxy_config['type']}://{proxy_config['ip']}:{proxy_config['port']}"
            else:
                if proxy_config.get("user") and proxy_config.get("password"):
                    proxy_url = (
                        f"http://{proxy_config['user']}:{proxy_config['password']}@"
                        f"{proxy_config['ip']}:{proxy_config['port']}"
                    )
                else:
                    proxy_url = f"http://{proxy_config['ip']}:{proxy_config['port']}"

            ytdl_opts["proxy"] = proxy_url
            logger.info("Force using proxy for audio download: %s", proxy_url)
            return ytdl_opts

        logger.warning("Proxy requested but proxy configuration is incomplete")
        return ytdl_opts

    from HELPERS.proxy_helper import add_proxy_to_ytdl_opts

    return add_proxy_to_ytdl_opts(ytdl_opts, url, user_id)


def _normalize_audio_extracted_info(info_dict, *, current_index: int, current_playlist_items_override):
    if isinstance(info_dict, list):
        info_dict = info_dict[0] if len(info_dict) > 0 else {}
    if isinstance(info_dict, dict) and "entries" in info_dict:
        entries = info_dict["entries"]
        if len(entries) > 1 and not current_playlist_items_override:
            actual_index = current_index - 1
            if 0 <= actual_index < len(entries):
                return entries[actual_index]
            raise Exception(
                f"Audio index {actual_index + 1} out of range (total {len(entries)})"
            )
        return entries[0]
    return info_dict


def _apply_audio_title_to_opts(ytdl_opts, *, info_dict, user_folder: str):
    def sanitize_title_for_filename(title):
        if not title:
            return "audio"
        return sanitize_filename_strict(title)

    original_title = info_dict.get("title", "audio")
    logger.info("DEBUG: info_dict.get('title') = '%s'", original_title)
    sanitized_title = sanitize_title_for_filename(original_title)
    info_dict["original_title"] = original_title
    logger.info("MANUAL sanitization: '%s' -> '%s'", original_title, sanitized_title)
    ytdl_opts["outtmpl"] = os.path.join(user_folder, f"{sanitized_title}.%(ext)s")
    logger.info("Set outtmpl to use literal filename: %s.%%(ext)s", sanitized_title)
    return info_dict


def _update_audio_download_mode_status(
    *,
    user_id: int,
    proc_msg_id: int,
    current_total_process: str,
    download_format: str,
    is_hls: bool,
):
    try:
        if is_hls:
            safe_edit_message_text(
                user_id,
                proc_msg_id,
                f"{current_total_process}\n<i>Detected HLS audio stream.\n"
                f"{safe_get_messages(user_id).ALWAYS_ASK_DOWNLOADING_HLS_MSG}</i>",
            )
        else:
            safe_edit_message_text(
                user_id,
                proc_msg_id,
                f"{current_total_process}\n> <i>"
                f"{safe_get_messages(user_id).ALWAYS_ASK_DOWNLOADING_AUDIO_FORMAT_USING_MSG} "
                f"{download_format}...</i>",
            )
    except Exception as e:
        logger.error("Status update error: %s", e)


def _run_audio_download_phase(
    *,
    ytdl_opts,
    url: str,
    user_id: int,
    proc_msg_id: int,
    current_total_process: str,
    user_folder: str,
    is_hls: bool,
    progress_hook,
):
    def download_operation(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            if is_hls:
                cycle_stop = threading.Event()
                progress_data = {"downloaded_bytes": 0, "total_bytes": 0}
                cycle_thread = start_cycle_progress(
                    user_id,
                    proc_msg_id,
                    current_total_process,
                    user_folder,
                    cycle_stop,
                    progress_data,
                )
                progress_hook.cycle_stop = cycle_stop
                progress_hook.progress_data = progress_data
                try:
                    ydl.download([url])
                finally:
                    cycle_stop.set()
                    cycle_thread.join(timeout=1)
            else:
                ydl.download([url])
        return True

    from HELPERS.proxy_helper import try_with_proxy_fallback

    return try_with_proxy_fallback(ytdl_opts, url, user_id, download_operation)


def _build_audio_error_summary(error_text: str):
    error_code = "UNKNOWN_ERROR"
    error_description = error_text

    if "HTTP Error 403" in error_text:
        error_code = "HTTP_403_FORBIDDEN"
        error_description = "Access forbidden - may need cookies or authentication"
    elif "HTTP Error 401" in error_text:
        error_code = "HTTP_401_UNAUTHORIZED"
        error_description = "Authentication required - cookies needed"
    elif "Video unavailable" in error_text:
        error_code = "VIDEO_UNAVAILABLE"
        error_description = "Video is not available or has been removed"
    elif "Private video" in error_text:
        error_code = "PRIVATE_VIDEO"
        error_description = "Video is private and requires authentication"
    elif "Sign in to confirm" in error_text:
        error_code = "SIGN_IN_REQUIRED"
        error_description = "Sign in required - cookies needed"
    elif "No video formats found" in error_text:
        error_code = "NO_FORMATS"
        error_description = "No downloadable formats available"
    elif "Unsupported URL" in error_text:
        error_code = "UNSUPPORTED_URL"
        error_description = "This URL is not supported by yt-dlp"
    elif "Network error" in error_text:
        error_code = "NETWORK_ERROR"
        error_description = "Network connection failed"
    elif "ffmpeg exited with code" in error_text or "ERROR: ffmpeg" in error_text:
        error_code = "FFMPEG_ERROR"
        if "code 1" in error_text:
            error_description = "FFmpeg processing failed - audio format may be incompatible or corrupted"
        elif "code 2" in error_text:
            error_description = "FFmpeg error - invalid arguments or unsupported format"
        else:
            error_description = "FFmpeg processing error occurred"

        ffmpeg_details = re.search(
            r"ffmpeg.*?error[:\s]+(.*?)(?:\n|$)",
            error_text,
            re.IGNORECASE | re.DOTALL,
        )
        if ffmpeg_details:
            details = ffmpeg_details.group(1).strip()[:200]
            if details:
                error_description += f"\n\nDetails: {details}"

        error_description += (
            "\n\n**Possible solutions:**\n"
            "• Try downloading with a different quality/format\n"
            "• The audio may be corrupted or in an unsupported format\n"
            "• Try downloading without post-processing\n"
            "• Check if ffmpeg is properly installed"
        )

    return error_code, error_description


def _maybe_auto_rotate_ip_for_audio_sign_in_required(user_id: int, error_text: str):
    if "Sign in to confirm" not in error_text:
        return
    try:
        from services.system_service import rotate_ip

        logger.warning("Auto-rotating IP due to SIGN_IN_REQUIRED error for user %s", user_id)
        rotate_result = rotate_ip()
        if rotate_result.get("status") == "ok":
            logger.info(
                "IP rotated successfully: IPv4=%s, IPv6=%s",
                rotate_result.get("ipv4"),
                rotate_result.get("ipv6"),
            )
        else:
            logger.error("Failed to auto-rotate IP: %s", rotate_result.get("message"))
    except Exception as rotate_error:
        logger.error("Error during auto-rotate IP: %s", rotate_error)


@dataclass(frozen=True)
class AudioRetryRoutePlan:
    mode: str
    should_retry_proxy: bool
    should_retry_cookie: bool
    should_skip: bool


def _build_audio_retry_route_plan(*, url: str, error_text: str) -> AudioRetryRoutePlan:
    if is_youtube_url(url):
        return AudioRetryRoutePlan(
            mode="proxy",
            should_retry_proxy=True,
            should_retry_cookie=False,
            should_skip=False,
        )

    error_str = error_text.lower()
    cookie_keywords = [
        "cookie",
        "auth",
        "login",
        "sign in",
        "403",
        "401",
        "forbidden",
        "unauthorized",
    ]
    if any(keyword in error_str for keyword in cookie_keywords):
        return AudioRetryRoutePlan(
            mode="cookie",
            should_retry_proxy=False,
            should_retry_cookie=True,
            should_skip=False,
        )

    return AudioRetryRoutePlan(
        mode="skip",
        should_retry_proxy=False,
        should_retry_cookie=False,
        should_skip=True,
    )


def _maybe_retry_audio_download_after_error(
    *,
    user_id: int,
    url: str,
    error_text: str,
    did_proxy_retry: bool,
    try_download_audio,
    current_index: int,
):
    retry_route_plan = _build_audio_retry_route_plan(url=url, error_text=error_text)
    if retry_route_plan.should_retry_proxy:
        retry_result, did_proxy_retry = maybe_retry_with_proxy_on_geo_error(
            user_id=user_id,
            url=url,
            error_text=error_text,
            did_proxy_retry=did_proxy_retry,
            is_youtube_url=is_youtube_url,
            is_youtube_geo_error=is_youtube_geo_error,
            retry_download_with_proxy=retry_download_with_proxy,
            download_fn=try_download_audio,
            download_args=(url, current_index),
            logger=logger,
            success_log_text="Audio download retry with proxy successful for user {user_id}",
            failure_log_text="Audio download retry with proxy failed for user {user_id}",
        )
        return retry_result, did_proxy_retry

    if retry_route_plan.should_skip:
        logger.info("Error appears to be non-cookie-related for %s, skipping cookie fallback", url)
        return None, did_proxy_retry

    logger.info(
        "Non-YouTube audio download error detected for user %s, attempting cookie fallback",
        user_id,
    )
    logger.info("Error appears to be cookie-related for %s, trying cookie fallback", url)
    from COMMANDS.cookies_cmd import try_non_youtube_cookie_fallback

    retry_result = try_non_youtube_cookie_fallback(
        user_id,
        url,
        try_download_audio,
        url,
        current_index,
    )
    if retry_result is not None:
        logger.info("Audio download retry with cookie fallback successful for user %s", user_id)
    else:
        logger.warning("Audio download retry with cookie fallback failed for user %s", user_id)
    return retry_result, did_proxy_retry


def _render_final_audio_download_error(error_text: str):
    error_code, error_description = _build_audio_error_summary(error_text)
    return (
        "<blockquote>Check <a href='https://github.com/chelaxian/tg-ytdlp-bot/wiki/YT_DLP#supported-sites'>here</a> if your site supported</blockquote>\n"
        "<blockquote>You may need <code>cookie</code> for downloading this audio. First, clean your workspace via <b>/clean</b> command</blockquote>\n"
        "<blockquote>For Youtube - get <code>cookie</code> via <b>/cookie</b> command. For any other supported site - send your own cookie (<a href='https://t.me/tg_ytdlp/203'>guide1</a>) (<a href='https://t.me/tg_ytdlp/214'>guide2</a>) and after that send your audio link again.</blockquote>\n"
        f"────────────────\n"
        f"❌ <b>Error Code:</b> <code>{error_code}</code>\n"
        f"📝 <b>Description:</b> {error_description}\n"
        f"🔧 <b>Full Error:</b> <code>{error_text}</code>"
    )


def _handle_generic_audio_download_exception(
    *,
    message,
    user_id: int,
    current_index: int,
    original_playlist_index: int,
    task_context: RuntimeTask | None,
    error: Exception,
):
    error_text = str(error)
    if "No videos found in playlist" in error_text or "Story might have expired" in error_text:
        rendered_text = safe_get_messages(user_id).DOWN_UP_NO_CONTENT_FOUND_MSG.format(
            index=original_playlist_index
        )
        _send_audio_failure(
            message,
            user_id,
            failure_kind="content_unavailable",
            error_text=error_text,
            rendered_text=rendered_text,
            use_error_channel=True,
            task_context=task_context,
        )
        logger.info("Skipping item at index %s (no content found)", current_index)
        return "SKIP"

    if "TikTok API keeps sending the same page" in error_text and "infinite loop" in error_text:
        rendered_text = safe_get_messages(user_id).AUDIO_TIKTOK_API_ERROR_SKIP_MSG.format(
            index=original_playlist_index
        )
        _send_audio_failure(
            message,
            user_id,
            failure_kind="source_api_error",
            error_text=error_text,
            rendered_text=rendered_text,
            task_context=task_context,
        )
        logger.info("Skipping TikTok audio at index %s due to API error", current_index)
        return "SKIP"

    _send_audio_failure(
        message,
        user_id,
        failure_kind="download_failed",
        error_text=error_text,
        rendered_text=safe_get_messages(user_id).ERROR_UNKNOWN_MSG.format(error=str(error)),
        task_context=task_context,
    )
    return None

def create_telegram_thumbnail(cover_path, output_path, size=320):
    """Create a Telegram-compliant thumbnail from cover image using center crop (no black bars)."""
    try:
        logger.info(f"Creating Telegram thumbnail: {cover_path} -> {output_path}")
        
        # Open image with PIL
        with Image.open(cover_path) as img:
            # Convert to RGB (handles CMYK and other color spaces)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Center-crop to a square (no padding)
            width, height = img.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            right = left + side
            bottom = top + side
            img_cropped = img.crop((left, top, right, bottom))
            
            # Resize to required size
            img_resized = img_cropped.resize((size, size), Image.Resampling.LANCZOS)
            
            # Save as JPEG with baseline encoding and quality 0.8
            img_resized.save(output_path, 'JPEG', quality=80, optimize=True, progressive=False)
            
            # Check file size and reduce quality if needed (<200KB)
            file_size = os.path.getsize(output_path)
            logger.info(f"Telegram thumbnail created: {output_path}, size: {file_size} bytes")
            
            if file_size and file_size > 200 * 1024:  # 200KB
                logger.warning(f"Thumbnail size ({file_size} bytes) exceeds 200KB limit, reducing quality")
                img_resized.save(output_path, 'JPEG', quality=60, optimize=True, progressive=False)
                new_size = os.path.getsize(output_path)
                logger.info(f"Reduced quality thumbnail size: {new_size} bytes")
            
            return True
            
    except Exception as e:
        logger.error(f"Error creating Telegram thumbnail: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def embed_cover_mp3(mp3_path, cover_path, title=None, artist=None, album=None):
    """Embed cover into MP3 using ID3v2 APIC via ffmpeg."""
    try:
        logger.info(f"Starting cover embedding: MP3={mp3_path}, Cover={cover_path}")
        
        # Check if files exist
        if not os.path.exists(mp3_path):
            logger.error(f"MP3 file not found: {mp3_path}")
            return False
        if not os.path.exists(cover_path):
            logger.error(f"Cover file not found: {cover_path}")
            return False
        
        # Convert cover to JPEG if needed
        if cover_path.lower().endswith(('.webp', '.png')):
            jpeg_path = cover_path.rsplit('.', 1)[0] + '.jpg'
            logger.info(f"Converting cover to JPEG: {cover_path} -> {jpeg_path}")
            result = subprocess.run([
                "ffmpeg", "-y", "-i", cover_path, jpeg_path
            ], check=True, capture_output=True, text=True)
            cover_path = jpeg_path
        
        out_path = mp3_path.rsplit('.', 1)[0] + '_tagged.mp3'
        
        # Build ffmpeg command for MP3 cover embedding
        cmd = [
            "ffmpeg", "-y",
            "-i", mp3_path,
            "-i", cover_path,
            "-map", "0:a:0", "-map", "1:v:0",
            "-c:a", "copy",
            "-c:v", "mjpeg",
            "-id3v2_version", "3",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)",
            "-disposition:v", "attached_pic"
        ]
        
        # Add metadata if provided
        if title:
            cmd.extend(["-metadata", f"title={title}"])
        if artist:
            cmd.extend(["-metadata", f"artist={artist}"])
        if album:
            cmd.extend(["-metadata", f"album={album}"])
        
        cmd.append(out_path)
        
        logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
        
        # Run ffmpeg command
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        logger.info(f"FFmpeg stdout: {result.stdout}")
        if result.stderr:
            logger.info(f"FFmpeg stderr: {result.stderr}")
        
        # Replace original file with tagged version
        if os.path.exists(out_path):
            os.replace(out_path, mp3_path)
            logger.info(f"Successfully embedded cover in MP3: {mp3_path}")
            return True
        else:
            logger.error(f"Failed to create tagged MP3 file: {out_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error embedding cover: {e.stderr}")
        logger.error(f"FFmpeg command that failed: {' '.join(cmd) if 'cmd' in locals() else 'Unknown'}")
        return False
    except Exception as e:
        logger.error(f"Error embedding cover: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

# @reply_with_keyboard
def down_and_audio(app, message, url=None, tags=None, quality_key=None, playlist_name=None, video_count=1, video_start_with=1, format_override=None, cookies_already_checked=False, use_proxy=False, cached_video_info=None, task_context: RuntimeTask | None = None):
    # Reset the checked cookie-source cache for a new download task
    user_id = message.chat.id
    from COMMANDS.cookies_cmd import reset_checked_cookie_sources
    reset_checked_cookie_sources(user_id)
    logger.info(f"🔄 [DEBUG] Reset checked cookie sources for new audio download task for user {user_id}")
    """
    Now if part of the playlist range is already cached, we first repost the cached indexes, then download and cache the missing ones, without finishing after reposting part of the range.
    """
    # Import required modules at the beginning
    from COMMANDS.cookies_cmd import is_youtube_cookie_error, is_youtube_geo_error, retry_download_with_different_cookies, retry_download_with_proxy
    
    playlist_indices = []
        
    (
        task_context,
        url,
        tags,
        playlist_name,
        video_count,
        video_start_with,
        cached_video_info,
    ) = _resolve_audio_task_inputs(
        task_context=task_context,
        user_id=user_id,
        message=message,
        url=url,
        tags=tags,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        cached_video_info=cached_video_info,
    )
    logger.info(f"down_and_audio called: url={url}, quality_key={quality_key}, video_count={video_count}, video_start_with={video_start_with}")
    branch_result = task_context.branch_selection_result
    if branch_result is not None:
        log_branch_selection(logger, branch_result, user_id=user_id)
    
    # STRICT: keep the original text with range tags for fallback parsing
    original_message_text = message.text or message.caption or ""
    logger.info(f"[ORIGINAL TEXT] Saved for fallback: {original_message_text}")
    
    # Initialize retry guards early to avoid UnboundLocalError
    did_proxy_retry = False
    did_cookie_retry = False
    is_hls = False
    
    # Determine forced NSFW via user tags
    try:
        _u, _s, _e, _p, _tags, _tags_text, _err = extract_url_range_tags(original_message_text)
        user_forced_nsfw = any(t.lower() in ("#nsfw", "#porn") for t in (_tags or []))
    except Exception:
        user_forced_nsfw = False
    
    try:
        from DOWN_AND_UP.always_ask_menu import get_link_mode

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
                response_sender=send_standard_direct_link_response,
                app=app,
                message=message,
                user_id=user_id,
                url=url,
                quality_key=quality_key,
                cookies_already_checked=cookies_already_checked,
                use_proxy=True,
            )
            if result.get('success'):
                send_to_logger(message, safe_get_messages(user_id).DIRECT_LINK_EXTRACTED_DOWN_AUDIO_LOG_MSG.format(user_id=user_id, url=url))
            else:
                error_msg = result.get('error', 'Unknown error')
                log_error_to_channel(message, safe_get_messages(user_id).DIRECT_LINK_FAILED_DOWN_AUDIO_LOG_MSG.format(user_id=user_id, url=url, error=error_msg), url)
            
            return
    except Exception as e:
        logger.error(f"Error checking direct-link path for user {user_id}: {e}")
        # Continue with normal download if direct-link check fails
    
    # We define a playlist not only by the number of videos, but also by the presence of a range in the URL
    original_text = message.text or message.caption or ""
    is_playlist = video_count > 1 or is_playlist_with_range(original_text)
    
    # Extract video_end_with from original_text (if present)
    from URL_PARSERS.tags import extract_url_range_tags
    _, parsed_start, parsed_end, _, _, _, _ = extract_url_range_tags(original_text)
    video_end_with = parsed_end if parsed_end != 1 or parsed_start != 1 else (video_start_with + video_count - 1)
    
    # Determine whether reverse order is needed (when start > end)
    # For negative indices: -1..-7 implies reverse order (7, 6, 5, 4, 3, 2, 1)
    is_reverse_order = False
    has_negative_indices = False
    if is_playlist and video_start_with is not None and video_end_with is not None:
        # If both are negative, always use reverse order
        if video_start_with < 0 and video_end_with < 0:
            is_reverse_order = True
            has_negative_indices = True
        # If start > end, it's reverse order
        elif video_start_with > video_end_with:
            is_reverse_order = True
    
    requested_indices = build_requested_indices(
        is_playlist=is_playlist,
        video_start_with=video_start_with,
        video_count=video_count,
        video_end_with=video_end_with if is_playlist else None,
    )
    playlist_indices_all = requested_indices[:] if requested_indices else []
    use_range_download = is_playlist and any(idx < 0 for idx in requested_indices)
    cached_videos = {}
    uncached_indices = []
    if quality_key and is_playlist:
        # Check if Always Ask mode is enabled - if yes, skip cache completely
        if not is_subs_always_ask(user_id):
            # Check if content is NSFW - if so, skip cache lookup
            from HELPERS.porn import is_porn
            is_nsfw = is_porn(url, "", "", None) or user_forced_nsfw
            logger.info(f"[FALLBACK] is_porn check for {url}: {is_porn(url, '', '', None)}, user_forced_nsfw: {user_forced_nsfw}, final is_nsfw: {is_nsfw}")
            if not is_nsfw:
                cached_videos = get_cached_playlist_videos(get_clean_playlist_url(url), quality_key, requested_indices)
                uncached_indices = [i for i in requested_indices if i not in cached_videos]
            else:
                logger.info(f"down_and_audio: skipping cache lookup for NSFW playlist content (url={url})")
                cached_videos = {}
                uncached_indices = requested_indices
        else:
            logger.info(f"[AUDIO CACHE] Skipping cache check for playlist because Always Ask mode is enabled: url={url}, quality={quality_key}")
            cached_videos = {}
            uncached_indices = requested_indices
        # First, repost the cached ones (skip if send_as_file is enabled)
        if cached_videos and (not use_range_download or len(uncached_indices) == 0):
            # Check if send_as_file is enabled - if so, skip cache repost
            from COMMANDS.args_cmd import get_user_args
            user_args = get_user_args(user_id)
            send_as_file = user_args.get("send_as_file", False)
            
            if not send_as_file:
                for index in requested_indices:
                    if index in cached_videos:
                        try:
                            # Determine the correct log channel based on content type
                            from HELPERS.porn import is_porn
                            is_nsfw = is_porn(url, "", "", None) or user_forced_nsfw
                            logger.info(f"[FALLBACK] is_porn check for {url}: {is_porn(url, '', '', None)}, user_forced_nsfw: {user_forced_nsfw}, final is_nsfw: {is_nsfw}")
                            is_private_chat = getattr(message.chat, "type", None) == enums.ChatType.PRIVATE
                            is_paid = is_nsfw and is_private_chat
                            
                            # Get the correct log channel for reposting
                            if is_paid:
                                from_chat_id = get_log_channel("video", paid=True)
                            elif is_nsfw:
                                from_chat_id = get_log_channel("video", nsfw=True)
                            else:
                                from_chat_id = get_log_channel("video")
                            
                            # Verify we're reposting from a valid log channel
                            valid_channels = [
                                get_log_channel("video"),
                                get_log_channel("video", nsfw=True),
                                get_log_channel("video", paid=True)
                            ]
                            if from_chat_id not in valid_channels:
                                logger.error(f"CRITICAL: Attempting to repost from wrong channel {from_chat_id}")
                                continue
                            
                            logger.info(f"[AUDIO CACHE] Reposting audio {index} from channel {from_chat_id} to user {user_id}, message_id={cached_videos[index]}")
                            forward_kwargs = {
                                'chat_id': user_id,
                                'from_chat_id': from_chat_id,
                                'message_ids': [cached_videos[index]]
                            }
                            # Only apply thread_id in groups/channels, not in private chats
                            if getattr(message.chat, "type", None) != enums.ChatType.PRIVATE:
                                thread_id = getattr(message, 'message_thread_id', None)
                                if thread_id:
                                    forward_kwargs['message_thread_id'] = thread_id
                            app.forward_messages(**forward_kwargs)
                        except Exception as e:
                            logger.error(f"down_and_audio: error reposting cached audio index={index}: {e}")
            else:
                # If send_as_file is enabled, treat all indices as uncached
                logger.info(f"[AUDIO CACHE] send_as_file enabled for user {user_id}, skipping cache repost for playlist")
                uncached_indices = requested_indices
            if len(uncached_indices) == 0:
                send_playlist_cache_status(
                    app=app,
                    user_id=user_id,
                    reply_to_message_id=message.id,
                    text=safe_get_messages(user_id).PLAYLIST_CACHE_SENT_MSG.format(
                        cached=len(cached_videos),
                        total=len(requested_indices),
                    ),
                )
                send_to_logger(message, LoggerMsg.PLAYLIST_AUDIO_SENT_FROM_CACHE.format(quality=quality_key, user_id=user_id))
                return
            else:
                send_playlist_cache_status(
                    app=app,
                    user_id=user_id,
                    reply_to_message_id=message.id,
                    text=safe_get_messages(user_id).CACHE_PARTIAL_MSG.format(
                        cached=len(cached_videos),
                        total=len(requested_indices),
                    ),
                )
        elif cached_videos:
            logger.info("[AUDIO CACHE] Skipping partial cache replay for negative range to avoid duplicate downloads")
            uncached_indices = requested_indices
    elif quality_key and not is_playlist:
        # Check if Always Ask mode is enabled - if yes, skip cache completely
        from HELPERS.porn import is_porn
        cached_ids, is_nsfw = lookup_single_cached_ids(
            user_id=user_id,
            url=url,
            quality_key=quality_key,
            user_forced_nsfw=user_forced_nsfw,
            always_ask_enabled=is_subs_always_ask(user_id),
            is_nsfw_detector=is_porn,
            get_cached_message_ids=get_cached_message_ids,
            logger=logger,
            nsfw_skip_log="down_and_audio: skipping cache lookup for NSFW single audio content (url={url})",
            always_ask_skip_log="[AUDIO CACHE] Skipping cache check because Always Ask mode is enabled: url={url}, quality={quality}",
        )
        
        if cached_ids:
            # Check if send_as_file is enabled - if so, skip cache repost
            from COMMANDS.args_cmd import get_user_args
            user_args = get_user_args(user_id)
            send_as_file = user_args.get("send_as_file", False)
            
            if not send_as_file:
                is_private_chat = getattr(message.chat, "type", None) == enums.ChatType.PRIVATE
                is_paid = is_nsfw and is_private_chat

                def resolve_from_chat_id():
                    if is_paid:
                        from_chat_id = get_log_channel("video", paid=True)
                    elif is_nsfw:
                        from_chat_id = get_log_channel("video", nsfw=True)
                    else:
                        from_chat_id = get_log_channel("video")
                    valid_channels = [
                        get_log_channel("video"),
                        get_log_channel("video", nsfw=True),
                        get_log_channel("video", paid=True),
                    ]
                    if from_chat_id not in valid_channels:
                        logger.error(f"CRITICAL: Attempting to repost from wrong channel {from_chat_id}")
                        raise Exception("Wrong channel for repost")
                    return from_chat_id

                replayed = try_repost_single_cached_media(
                    app=app,
                    message=message,
                    user_id=user_id,
                    cached_ids=cached_ids,
                    resolve_from_chat_id=resolve_from_chat_id,
                    success_text=safe_get_messages(user_id).AUDIO_SENT_FROM_CACHE_MSG,
                    success_log_text=LoggerMsg.AUDIO_SENT_FROM_CACHE.format(quality=quality_key, user_id=user_id),
                    logger=logger,
                    replay_log_prefix="[AUDIO CACHE] Reposting audio",
                    replay_error_prefix="Error reposting audio from cache",
                    on_replay_error=lambda: save_to_video_cache(url, quality_key, [], clear=True),
                    send_to_logger=send_to_logger,
                )
                if replayed:
                    return
            else:
                # If send_as_file is enabled, skip cache repost and continue with download
                logger.info(f"[AUDIO CACHE] send_as_file enabled for user {user_id}, skipping cache repost for single audio")
    else:
        logger.info(f"down_and_audio: quality_key is None, skipping cache check")

    anim_thread = None
    stop_anim = threading.Event()
    proc_msg = None
    proc_msg_id = None
    status_msg = None
    status_msg_id = None
    hourglass_msg = None
    hourglass_msg_id = None
    download_started_msg_id = None
    audio_files = []
    try:
        handshake = start_processing_handshake(
            app=app,
            message=message,
            user_id=user_id,
            messages=safe_get_messages(user_id),
            logger=logger,
        )
        if handshake is None:
            return
        proc_msg = handshake["proc_msg"]
        proc_msg_id = handshake["proc_msg_id"]
        download_started_msg_id = handshake["download_started_msg_id"]
        status_msg = safe_send_message(user_id, safe_get_messages(user_id).AUDIO_PROCESSING_MSG, message=message)
        hourglass_msg = safe_send_message(user_id, safe_get_messages(user_id).WAITING_HOURGLASS_MSG, message=message)
        try:
            from HELPERS.safe_messeger import schedule_delete_message
            if status_msg and hasattr(status_msg, 'id'):
                schedule_delete_message(user_id, status_msg.id, delete_after_seconds=5)
        except Exception:
            pass
        status_msg_id = status_msg.id
        hourglass_msg_id = hourglass_msg.id
        anim_thread = start_hourglass_animation(user_id, hourglass_msg_id, stop_anim)

        # Check if there's enough disk space (estimate 500MB per audio file)
        user_folder = os.path.abspath(os.path.join("users", str(user_id)))
        create_directory(user_folder)

        if not check_disk_space(user_folder, 500 * 1024 * 1024 * video_count):
            _send_audio_failure(
                message,
                user_id,
                failure_kind="resource_exhausted",
                rendered_text=safe_get_messages(user_id).ERROR_NO_DISK_SPACE_MSG,
                task_context=task_context,
            )
            return

        user_dir, user_folder = ensure_user_download_dir(
            user_id=user_id,
            url=url,
            logger=logger,
        )
        cleanup_download_dir_before_start(
            download_dir=user_folder,
            message=message,
            logger=logger,
        )

        # Reset of the flag of errors for the new launch of the playlist
        if playlist_name:
            clear_playlist_error_state(f"{user_id}_{playlist_name}")

        cookie_file = _resolve_audio_cookiefile(
            user_id=user_id,
            url=url,
            user_folder=user_folder,
        )
        last_update = 0
        progress_start_time = time.time()
        current_total_process = ""
        successful_uploads = 0
        error_message_sent = False
        
        # Check if this is an HLS stream (needed for progress_hook)
        # This will be updated later based on actual format detection
        is_hls = ("m3u8" in url.lower())

        def progress_hook(d):
            messages = safe_get_messages(message.chat.id)
            nonlocal last_update, is_hls
            # Check the timeout
            if check_download_timeout(user_id):
                raise Exception(f"Download timeout exceeded ({Config.DOWNLOAD_TIMEOUT // 3600} hours)")
            current_time = time.time()
            
            def build_progress_metadata(downloaded_bytes, total_bytes):
                info_dict = d.get("info_dict") or {}
                fmt = info_dict.get("requested_formats", [{}])[-1] if info_dict.get("requested_formats") else info_dict
                filesize = (
                    total_bytes
                    or fmt.get("filesize")
                    or fmt.get("filesize_approx")
                    or info_dict.get("filesize")
                    or info_dict.get("filesize_approx")
                )
                metadata_payload = {
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": total_bytes,
                    "filesize": filesize,
                    "duration": info_dict.get("duration"),
                    "bitrate": fmt.get("abr") or info_dict.get("abr"),
                    "ext": fmt.get("ext") or info_dict.get("ext"),
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "domain": urlparse(url).netloc,
                    "thumbnail": info_dict.get("thumbnail"),
                }
                return {k: v for k, v in metadata_payload.items() if v is not None}
            
            # Calculate elapsed time and minutes passed
            elapsed = max(0, current_time - progress_start_time)
            minutes_passed = int(elapsed // 60)
            
            # Adaptive throttle: linear; after 1h fixed 90s
            if minutes_passed and minutes_passed >= 60:
                interval = 90.0
            else:
                interval = 3.0 + max(0, minutes_passed // 5)
            
            if current_time - last_update < interval:
                return
                
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                percent = (downloaded / total * 100) if total else 0
                blocks = int(percent // 10)
                bar = "🟩" * blocks + "⬜️" * (10 - blocks)
                
                # Update progress in stats
                try:
                    update_download_progress(
                        user_id=user_id,
                        progress=percent,
                        url=url,
                        title=title,
                        metadata=build_progress_metadata(downloaded, total),
                    )
                except Exception as e:
                    logger.debug(f"Failed to update download progress: {e}")
                
                # For HLS audio, update progress data for cycle animation
                if hasattr(progress_hook, 'progress_data') and progress_hook.progress_data:
                    progress_hook.progress_data['downloaded_bytes'] = downloaded
                    progress_hook.progress_data['total_bytes'] = total
                
                try:
                    safe_edit_message_text(user_id, proc_msg_id, safe_get_messages(user_id).AUDIO_DOWNLOADING_PROGRESS_MSG.format(process=current_total_process, bar=bar, percent=percent))
                except Exception as e:
                    logger.error(f"Error updating progress: {e}")
                last_update = current_time
            elif d.get("status") == "finished":
                # Update progress to 100% on completion
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                try:
                    update_download_progress(
                        user_id=user_id,
                        progress=100.0,
                        url=url,
                        title=title,
                        metadata=build_progress_metadata(total or 0, total or 0),
                    )
                except Exception as e:
                    logger.debug(f"Failed to update download progress on finish: {e}")
                try:
                    full_bar = "🟩" * 10
                    safe_edit_message_text(user_id, proc_msg_id,
                        f"{current_total_process}\n{safe_get_messages(user_id).ALWAYS_ASK_DOWNLOADING_QUALITY_MSG} audio:\n{full_bar}   100.0%\n{safe_get_messages(user_id).AUDIO_DOWNLOAD_FINISHED_PROCESSING_MSG}")
                except Exception as e:
                    logger.error(f"Error updating progress: {e}")
                last_update = current_time
            elif d.get("status") == "error":
                # Reset progress on error
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                try:
                    update_download_progress(
                        user_id=user_id,
                        progress=None,
                        url=url,
                        title=title,
                        metadata=build_progress_metadata(downloaded, total),
                    )
                except Exception as e:
                    logger.debug(f"Failed to update download progress on error: {e}")
                try:
                    safe_edit_message_text(user_id, proc_msg_id, safe_get_messages(user_id).AUDIO_DOWNLOAD_ERROR_MSG)
                except Exception as e:
                    logger.error(f"Error updating progress: {e}")
                last_update = current_time

        # One-time retry guards to avoid infinite retry loops across attempts
        # (already initialized at the beginning of the function)

        def try_download_audio(url, current_index):
            messages = safe_get_messages(message.chat.id)
            nonlocal current_total_process, did_cookie_retry, did_proxy_retry, is_hls
            nonlocal is_reverse_order, current_playlist_items_override, use_range_download
            nonlocal range_entries_metadata, error_message_sent
            # Use format_override if provided, otherwise use default 'ba'
            download_format = format_override if format_override else 'ba'
            
            # Get user's audio format preference from args_cmd
            from COMMANDS.args_cmd import get_user_ytdlp_args
            user_args = get_user_ytdlp_args(user_id, url)
            audio_format = user_args.get('audio_format', 'mp3')  # Default to mp3
            
            # If audio_format is 'best', use mp3 as fallback
            if audio_format == 'best':
                audio_format = 'mp3'
            
            # Update is_hls based on actual URL analysis
            is_hls = ("m3u8" in url.lower())
            
            if current_playlist_items_override:
                playlist_items_value = current_playlist_items_override
            elif is_reverse_order and is_playlist:
                playlist_items_value = f"{current_index}:{current_index}:-1"
            else:
                playlist_items_value = str(current_index)

            ytdl_opts = {
               'format': download_format,
               'postprocessors': [{
                  'key': 'FFmpegExtractAudio',
                  'preferredcodec': audio_format,
                  'preferredquality': '192',
               },
               {
                  'key': 'FFmpegMetadata'   # equivalent to --add-metadata
               }                  
                ],
               'prefer_ffmpeg': True,
               'extractaudio': True,
               # For reverse order use START:STOP:-1, otherwise just the index
               'playlist_items': playlist_items_value,
               # outtmpl will be set later with sanitized title
               # Allow Unicode characters in filenames
               'restrictfilenames': False,
               'progress_hooks': [progress_hook],
               'extractor_args': {
                  'generic': {
                      'impersonate': ['chrome']
                  }
               },
               'referer': url,
               'geo_bypass': True,
               'check_certificate': False,
               'live_from_start': True,
               'writethumbnail': True,  # Enable thumbnail writing for manual embedding
               'writesubtitles': False,  # Disable subtitles for audio
               'writeautomaticsub': False,  # Disable auto subtitles for audio
            }
            
            # Configure HLS-specific options if detected
            if is_hls:
                ytdl_opts["downloader"] = "ffmpeg"
                ytdl_opts["hls_prefer_native"] = False
                ytdl_opts["hls_use_mpegts"] = True
                ytdl_opts.pop("http_chunk_size", None)
                # Reduce parallelism for fragile HLS endpoints
                ytdl_opts["concurrent_fragment_downloads"] = 1
            
            # Title sanitization is now handled manually before second extract_info call
            
            # Add match_filter for domain filtering only (no title sanitization needed)
            if not is_no_filter_domain(url):
                ytdl_opts['match_filter'] = create_smart_match_filter()
            else:
                logger.info(f"Skipping domain filter for domain in NO_FILTER_DOMAINS: {url}")
            
            # Add user's custom yt-dlp arguments
            from COMMANDS.args_cmd import get_user_ytdlp_args, log_ytdlp_options
            user_args = get_user_ytdlp_args(user_id, url)
            if user_args:
                ytdl_opts.update(user_args)
            
            # Log final yt-dlp options for debugging
            log_ytdlp_options(user_id, ytdl_opts, "audio_download")
            
            # Check if we need to use --no-cookies for this domain
            if is_no_cookie_domain(url):
                ytdl_opts['cookiefile'] = None  # Equivalent to --no-cookies
                logger.info(f"Using --no-cookies for domain: {url}")
            else:
                ytdl_opts['cookiefile'] = cookie_file
            
            ytdl_opts = _apply_audio_proxy_settings(
                ytdl_opts,
                use_proxy=use_proxy,
                url=url,
                user_id=user_id,
            )
            
            # Add PO token provider for YouTube domains
            ytdl_opts = add_pot_to_ytdl_opts(ytdl_opts, url)
            
            # match_filter will be added later for domain filtering only
            
            try:
                with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                info_dict = _normalize_audio_extracted_info(
                    info_dict,
                    current_index=current_index,
                    current_playlist_items_override=current_playlist_items_override,
                )
                
                # Check if this is a live stream and handle it if detection is disabled
                # Note: Live stream audio download is not supported, so we skip it for audio
                if info_dict and isinstance(info_dict, dict) and info_dict.get('is_live', False):
                    if not LimitsConfig.ENABLE_LIVE_STREAM_BLOCKING:
                        logger.warning(f"Live stream detected for audio download, but audio live streams are not supported: {url}")
                        _send_audio_failure(
                            message,
                            user_id,
                            failure_kind="live_stream_blocked",
                            rendered_text=safe_get_messages(user_id).LIVE_STREAM_DETECTED_MSG + "\n\nNote: Audio extraction from live streams is not supported.",
                            use_error_channel=True,
                            task_context=task_context,
                        )
                        return "LIVE_STREAM"
                
                info_dict = _apply_audio_title_to_opts(
                    ytdl_opts,
                    info_dict=info_dict,
                    user_folder=user_folder,
                )
                _update_audio_download_mode_status(
                    user_id=user_id,
                    proc_msg_id=proc_msg_id,
                    current_total_process=current_total_process,
                    download_format=download_format,
                    is_hls=is_hls,
                )
                
                result = _run_audio_download_phase(
                    ytdl_opts=ytdl_opts,
                    url=url,
                    user_id=user_id,
                    proc_msg_id=proc_msg_id,
                    current_total_process=current_total_process,
                    user_folder=user_folder,
                    is_hls=is_hls,
                    progress_hook=progress_hook,
                )
                if result is None:
                    raise Exception("Failed to download audio with all available proxies")
                
                try:
                    full_bar = "🟩" * 10
                    safe_edit_message_text(user_id, proc_msg_id, safe_get_messages(user_id).AUDIO_DOWNLOAD_COMPLETE_MSG.format(process=current_total_process, bar=full_bar))
                except Exception as e:
                    logger.error(f"Final progress update error: {e}")
                
                # Cache successful cookie result for future use
                if not is_youtube_url(url):
                    from COMMANDS.cookies_cmd import set_cookie_cache_result
                    cookie_file_path = ytdl_opts.get('cookiefile')
                    if cookie_file_path and os.path.exists(cookie_file_path):
                        set_cookie_cache_result(user_id, url, True, cookie_file_path)
                        logger.info(f"Cached successful cookie result for audio {url}")
                
                # Remove protection file after successful download
                from HELPERS.filesystem_hlp import remove_protection_file
                remove_protection_file(user_folder)
                
                return info_dict
            except yt_dlp.utils.DownloadError as e:
                error_text = str(e)
                logger.error(f"DownloadError: {error_text}")
                retry_plan = _build_audio_retry_outcome_plan(
                    error_text=error_text,
                    error_message_sent=error_message_sent,
                )
                
                # Check for live stream detection (only if detection is enabled)
                if "LIVE_STREAM_DETECTED" in error_text:
                    if LimitsConfig.ENABLE_LIVE_STREAM_BLOCKING:
                        live_stream_message = (
                            safe_get_messages(user_id).LIVE_STREAM_DETECTED_MSG +
                            "• You can see the final video length\n\n"
                            "Once the stream is completed, you'll be able to download it as a regular video."
                        )
                        _send_audio_failure(
                            message,
                            user_id,
                            failure_kind="live_stream_blocked",
                            error_text=error_text,
                            rendered_text=live_stream_message,
                            use_error_channel=True,
                            task_context=task_context,
                        )
                        return "LIVE_STREAM"
                    # If detection is disabled, continue with live stream download
                    # This will be handled by the live stream download function
                
                # Check for postprocessing errors
                if retry_plan.mode == "postprocessing_invalid_chars":
                    postprocessing_message = (
                        safe_get_messages(user_id).AUDIO_FILE_PROCESSING_ERROR_INVALID_CHARS_MSG +
                        "**Solutions:**\n"
                        "• Try downloading again - the system will use a safer filename\n"
                        "• If the problem persists, the audio title may contain unsupported characters\n"
                        "• Consider using a different audio source if available\n\n"
                        "The download will be retried automatically with a cleaned filename."
                    )
                    _send_audio_failure(
                        message,
                        user_id,
                        failure_kind="postprocessing_failed",
                        error_text=error_text,
                        rendered_text=postprocessing_message,
                        use_error_channel=True,
                        task_context=task_context,
                    )
                    logger.error(f"Postprocessing error: {error_text}")
                    return "POSTPROCESSING_ERROR"
                
                # Check for postprocessing errors with Invalid argument
                if retry_plan.mode == "postprocessing_invalid_argument":
                    logger.error(f"Postprocessing error (Invalid argument): {error_text}")
                    return "POSTPROCESSING_ERROR"
                
                retry_result, did_proxy_retry = _maybe_retry_audio_download_after_error(
                    user_id=user_id,
                    url=url,
                    error_text=error_text,
                    did_proxy_retry=did_proxy_retry,
                    try_download_audio=try_download_audio,
                    current_index=current_index,
                )
                if retry_result is not None:
                    return retry_result
                
                # Send full error message with instructions immediately (only once)
                if retry_plan.should_send_final_error:
                    _maybe_auto_rotate_ip_for_audio_sign_in_required(user_id, error_text)
                    
                    _send_audio_failure(
                        message,
                        user_id,
                        failure_kind="download_failed",
                        error_text=error_text,
                        rendered_text=_render_final_audio_download_error(error_text),
                        use_error_channel=True,
                        task_context=task_context,
                    )
                    error_message_sent = True
                return None
            except Exception as e:
                error_text = str(e)
                logger.error(f"Audio download attempt failed: {e}")
                
                return _handle_generic_audio_download_exception(
                    message=message,
                    user_id=user_id,
                    current_index=current_index,
                    original_playlist_index=original_playlist_index,
                    task_context=task_context,
                    error=e,
                )

        # Download thumbnail for embedding (only once for the URL)
        thumbnail_path = None
        try:
            logger.info(f"Downloading thumbnail for URL: {url}")
            # Try to download YouTube thumbnail first
            if ("youtube.com" in url or "youtu.be" in url):
                try:
                    # Extract YouTube video ID
                    import re
                    yt_id = None
                    if "youtube.com/watch?v=" in url:
                        yt_id = re.search(r'v=([^&]+)', url).group(1)
                    elif "youtu.be/" in url:
                        yt_id = re.search(r'youtu\.be/([^?]+)', url).group(1)
                    elif "youtube.com/shorts/" in url:
                        yt_id = re.search(r'shorts/([^?]+)', url).group(1)
                    
                    if yt_id:
                        youtube_thumb_path = os.path.join(user_folder, f"yt_thumb_{yt_id}.jpg")
                        download_thumbnail(yt_id, youtube_thumb_path, url)
                        if os.path.exists(youtube_thumb_path):
                            thumbnail_path = youtube_thumb_path
                            logger.info(f"Downloaded thumbnail to download directory: {youtube_thumb_path}")
                except Exception as e:
                    logger.warning(f"YouTube thumbnail download failed: {e}")
            
            # If not YouTube or YouTube thumb not found, try universal thumbnail downloader
            if not thumbnail_path:
                try:
                    universal_thumb_path = os.path.join(user_folder, "universal_thumb.jpg")
                    if download_universal_thumbnail(url, universal_thumb_path):
                        if os.path.exists(universal_thumb_path):
                            thumbnail_path = universal_thumb_path
                            logger.info(f"Downloaded universal thumbnail: {universal_thumb_path}")
                except Exception as e:
                    logger.info(f"Universal thumbnail not available: {e}")
        except Exception as e:
            logger.warning(f"Thumbnail download failed: {e}")

        # For negative indices, use the whole range at once (not a loop)
        total_playlist_count = None  # Total videos in playlist (for converting negative indices)
        has_negative_indices_for_download = False  # Flag for negative indices (do not use range_entries_metadata)
        if use_range_download:
            has_negative_indices_for_download = True  # For negative indices, download each one separately
            # For negative indices we need the total number of videos in the playlist
            # Do a preliminary request to get the total video count
            try:
                from DOWN_AND_UP.yt_dlp_hook import get_video_formats
                logger.info(f"Getting total playlist count for negative indices conversion (audio)...")
                temp_info = get_video_formats(url, user_id, 1, cookies_already_checked, use_proxy, 1)
                if temp_info and isinstance(temp_info, dict):
                    if "entries" in temp_info:
                        total_playlist_count = len(temp_info["entries"])
                    elif "_playlist_entries" in temp_info:
                        total_playlist_count = len(temp_info["_playlist_entries"])
                if total_playlist_count:
                    logger.info(f"Total playlist count (audio): {total_playlist_count}")
                    # Convert negative indices to positive:
                    # -1 = last video (total_playlist_count), -2 = second-to-last (total_playlist_count - 1), etc.
                    # Formula: positive_index = total_playlist_count + negative_index + 1
                    converted_indices = []
                    for neg_idx in playlist_indices_all:
                        if neg_idx < 0:
                            pos_idx = total_playlist_count + neg_idx + 1
                            converted_indices.append(pos_idx)
                        else:
                            converted_indices.append(neg_idx)
                    # Sort in reverse order to download from last to first
                    converted_indices.sort(reverse=True)
                    playlist_indices_all = converted_indices
                    logger.info(f"Converted negative indices to positive (audio): {converted_indices}")
            except Exception as e:
                logger.warning(f"Failed to get total playlist count for negative indices (audio): {e}, using original indices")
        
        if use_range_download:
            # For negative indices, use the whole range at once.
            # indices_to_download already contains converted positive indices.
            # For negative indices, always use reverse order (last to first).
            indices_to_download = playlist_indices_all  # Already sorted in reverse order
        elif is_playlist and quality_key:
            indices_to_download = uncached_indices
        elif is_playlist:
            indices_to_download = playlist_indices_all
        else:
            indices_to_download = range(video_count)
        
        # Define safe filename template for fallback
        timestamp = int(time.time())
        safe_outtmpl = os.path.join(user_folder, f"download_{timestamp}.%(ext)s")
        
        range_entries_metadata = None
        current_playlist_items_override = None
        for idx, current_index in enumerate(indices_to_download):
            original_playlist_index = current_index
            playlist_item_index = current_index if is_playlist else current_index + video_start_with
            messages = safe_get_messages(message.chat.id)
            total_process = f"""
<b>📶 {safe_get_messages(user_id).TOTAL_PROGRESS_MSG}</b>
<blockquote>{safe_get_messages(user_id).AUDIO_PROGRESS_MSG.format(current=idx + 1, total=len(indices_to_download))}</blockquote>
"""

            current_total_process = total_process

            # Playlist naming is handled by yt-dlp with our custom outtmpl

            # Reset retry flags for each new item in playlist
            did_cookie_retry = False
            did_proxy_retry = False
            error_message_sent = False

            # For negative indices, don't use reuse_range_download; download each index separately
            reuse_range_download = use_range_download and range_entries_metadata is not None and not has_negative_indices_for_download
            if reuse_range_download:
                if idx < len(range_entries_metadata):
                    info_dict = range_entries_metadata[idx]
                    logger.info(f"[AUDIO RANGE] Reusing cached entry #{idx + 1} for playlist index {original_playlist_index}")
                    result = info_dict
                else:
                    logger.warning(f"[AUDIO RANGE] Missing entry #{idx + 1} in cached metadata, stopping playlist download")
                    result = None
                    break
            else:
                if use_range_download:
                    current_playlist_items_override = f"{video_start_with}:{video_end_with}:-1" if is_reverse_order else f"{video_start_with}:{video_end_with}"
                else:
                    current_playlist_items_override = None
                result = try_download_audio(url, playlist_item_index)
                current_playlist_items_override = None
                # For negative indices, don't use range_entries_metadata; download each index separately
                if use_range_download and isinstance(result, dict) and not has_negative_indices_for_download:
                    if "entries" in result:
                        range_entries_metadata = result.get("entries") or []
                    else:
                        range_entries_metadata = [result]
                    if idx < len(range_entries_metadata):
                        info_dict = range_entries_metadata[idx]
                    else:
                        logger.warning(f"[AUDIO RANGE] Download returned {len(range_entries_metadata)} entries but missing entry #{idx + 1}")
                        break
                    result = info_dict
            
            # If download failed and it's a YouTube URL, try automatic cookie retry
            result, did_cookie_retry = maybe_retry_with_different_cookies(
                user_id=user_id,
                url=url,
                result=result,
                did_cookie_retry=did_cookie_retry,
                is_youtube_url=is_youtube_url,
                retry_download_with_different_cookies=retry_download_with_different_cookies,
                download_fn=try_download_audio,
                download_args=(url, playlist_item_index),
                logger=logger,
                media_label="Audio",
            )

            if result is None:
                mark_playlist_error(
                    f"{user_id}_{playlist_name}",
                    reason="download_attempt_failed",
                )

                break
            elif isinstance(result, str):
                # Handle string return values (like "POSTPROCESSING_ERROR", "SKIP", etc.)
                logger.info(f"Audio download attempt returned string result: {result}")
                if result == "POSTPROCESSING_ERROR":
                    # Try again with safe filename
                    logger.info("Audio download failed with postprocessing error, retrying with safe filename")
                    
                    # Create a simple retry with safe filename by modifying the ytdl_opts
                    # We'll create a new ytdl_opts with safe filename and retry
                    try:
                        # Get the same options as in try_download_audio but with safe filename
                        download_format = format_override if format_override else 'ba'
                        from COMMANDS.args_cmd import get_user_ytdlp_args
                        user_args = get_user_ytdlp_args(user_id, url)
                        audio_format = user_args.get('audio_format', 'mp3')
                        if audio_format == 'best':
                            audio_format = 'mp3'
                        
                        is_hls = ("m3u8" in url.lower())
                        
                        ytdl_opts = {
                           'format': download_format,
                           'postprocessors': [{
                              'key': 'FFmpegExtractAudio',
                              'preferredcodec': audio_format,
                              'preferredquality': '192',
                           },
                           {
                              'key': 'FFmpegMetadata'
                           }],
                           'prefer_ffmpeg': True,
                           'extractaudio': True,
                           # For reverse order use START:STOP:-1, otherwise just the index
                          'playlist_items': f"{playlist_item_index}:{playlist_item_index}:-1" if is_reverse_order and is_playlist else str(playlist_item_index),
                           'outtmpl': safe_outtmpl,  # Use safe filename
                           'restrictfilenames': False,
                           'progress_hooks': [progress_hook],
                           'extractor_args': {
                              'generic': {'impersonate': ['chrome']}
                           },
                           'referer': url,
                           'geo_bypass': True,
                           'check_certificate': False,
                           'live_from_start': True,
                           'writethumbnail': True,
                           'writesubtitles': False,
                           'writeautomaticsub': False,
                        }
                        
                        # Add match_filter only if domain is not in NO_FILTER_DOMAINS
                        if not is_no_filter_domain(url):
                            ytdl_opts['match_filter'] = create_smart_match_filter()
                        
                        # Add user's custom yt-dlp arguments
                        if user_args:
                            ytdl_opts.update(user_args)
                        
                        # Check if we need to use --no-cookies for this domain
                        if is_no_cookie_domain(url):
                            ytdl_opts['cookiefile'] = None
                        else:
                            ytdl_opts['cookiefile'] = cookie_file
                        
                        # Add proxy configuration
                        from HELPERS.proxy_helper import add_proxy_to_ytdl_opts
                        ytdl_opts = add_proxy_to_ytdl_opts(ytdl_opts, url, user_id)
                        
                        # Add PO token provider for YouTube domains
                        ytdl_opts = add_pot_to_ytdl_opts(ytdl_opts, url)
                        
                        # Try download with safe filename
                        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                            info_dict = ydl.extract_info(url, download=False)
                            if "entries" in info_dict:
                                entries = info_dict["entries"]
                                if len(entries) > 1:
                                    actual_index = playlist_item_index - 1
                                    if 0 <= actual_index < len(entries):
                                        info_dict = entries[actual_index]
                                    else:
                                        raise Exception(f"Audio index {actual_index + 1} out of range (total {len(entries)})")
                                else:
                                    info_dict = entries[0]
                            
                            # Download with safe filename
                            ydl.download([url])
                            
                            logger.info("Audio download with safe filename succeeded")
                            # Continue with the rest of the processing
                            
                    except Exception as e:
                        logger.error(f"Audio download with safe filename also failed: {e}")
                        continue
                elif result == "SKIP":
                    # Skip this item and continue with next
                    continue
                elif is_handled_gallery_command_result(result):
                    if did_gallery_command_succeed(result):
                        logger.info(
                            "Gallery-dl fallback succeeded for audio item %s, continuing with next item",
                            current_index,
                        )
                    else:
                        logger.warning(
                            "Gallery-dl fallback handled but failed for audio item %s, continuing with next item",
                            current_index,
                        )
                        if playlist_name and did_gallery_command_fail(result):
                            mark_playlist_error(
                                f"{user_id}_{playlist_name}",
                                reason="gallery_fallback_failed",
                            )
                    continue
                elif result == "LIVE_STREAM":
                    # Live stream detected, skip this item
                    continue
                else:
                    # Other string results, skip this attempt
                    continue
            else:
                # result is a dict (info_dict)
                info_dict = result

            successful_uploads += 1

            # Check if info_dict is None before accessing it
            if info_dict is None:
                logger.error("info_dict is None, cannot proceed with audio processing")
                # Send specific error message if available
                if error_text and "Postprocessing" in error_text and "Invalid argument" in error_text:
                    postprocessing_message = (
                        safe_get_messages(user_id).AUDIO_FILE_PROCESSING_ERROR_INVALID_ARG_MSG +
                        "**Possible causes:**\n"
                        "• Corrupted or incomplete download\n"
                        "• Unsupported audio format or codec\n"
                        "• File system permissions issue\n"
                        "• Insufficient disk space\n\n"
                        "**Solutions:**\n"
                        "• Try downloading again with different settings\n"
                        "• Check if you have enough disk space\n"
                        "• Try a different quality or format\n"
                        "• If the problem persists, the audio source may be corrupted"
                    )
                    _send_audio_failure(
                        message,
                        user_id,
                        failure_kind="postprocessing_failed",
                        rendered_text=postprocessing_message,
                        use_error_channel=True,
                        task_context=task_context,
                    )
                else:
                    _send_audio_failure(
                        message,
                        user_id,
                        failure_kind="extraction_failed",
                        rendered_text=safe_get_messages(user_id).AUDIO_EXTRACTION_FAILED_MSG,
                        task_context=task_context,
                    )
                break

            # Get original title for fallback (if MP3 metadata reading fails)
            original_audio_title = info_dict.get("original_title", info_dict.get("title", "audio"))
            
            # File naming is handled by yt-dlp with our custom outtmpl

            dir_path = user_folder

            downloaded_file = None
            downloaded_abs_path = None
            
            # Find the downloaded audio file
            filename_hints = []
            meta_filename = info_dict.get('_filename')
            if meta_filename:
                filename_hints.append(meta_filename)
            filepath_hint = info_dict.get('filepath')
            if filepath_hint:
                filename_hints.append(filepath_hint)
            requested_downloads = info_dict.get('requested_downloads') or []
            for rd in requested_downloads:
                rd_path = rd.get('filepath') or rd.get('_filename')
                if rd_path:
                    filename_hints.append(rd_path)
            
            for hint in filename_hints:
                if hint and os.path.exists(hint):
                    downloaded_abs_path = os.path.abspath(hint)
                    downloaded_file = os.path.basename(downloaded_abs_path)
                    logger.info(f"[AUDIO RANGE] Using yt-dlp reported file path: {downloaded_abs_path}")
                    break
            
            if not downloaded_file:
                allfiles = os.listdir(user_folder)
                logger.info(f"All files in user folder: {allfiles}")
                
                # Look for files with the user's preferred audio format extension
                audio_extensions = ['.mp3', '.aac', '.flac', '.m4a', '.opus', '.ogg', '.wav', '.alac', '.ac3']
                files = [fname for fname in allfiles if any(fname.endswith(ext) for ext in audio_extensions)]
                logger.info(f"Found audio files: {files}")
                files.sort()
                
                # If no files found with standard audio extensions, try additional formats
                if not files:
                    logger.warning(f"No files found with standard audio extensions, trying additional formats")
                    additional_extensions = ['.mka', '.wma', '.aiff', '.au', '.ra', '.rm', '.3ga', '.amr', '.awb', '.m4b', '.m4p', '.oga', '.spx', '.tta', '.weba']
                    files = [fname for fname in allfiles if any(fname.endswith(ext) for ext in additional_extensions)]
                    files.sort()
                    logger.info(f"Found audio files with additional formats: {files}")
                
                if not files:
                    logger.error(f"No audio files found in {user_folder}. Available files: {allfiles}")
                    _send_audio_failure(
                        message,
                        user_id,
                        failure_kind="unsupported_artifact",
                        rendered_text=safe_get_messages(user_id).AUDIO_UNSUPPORTED_FILE_TYPE_MSG.format(index=original_playlist_index),
                        use_error_channel=True,
                        task_context=task_context,
                    )
                    continue

                downloaded_file = files[0]
                downloaded_abs_path = os.path.abspath(os.path.join(user_folder, downloaded_file))

            write_logs(message, url, downloaded_file)
            
            # File is already sanitized by yt-dlp with our custom outtmpl
            audio_file = downloaded_abs_path or os.path.join(user_folder, downloaded_file)
            if not os.path.exists(audio_file):
                _send_audio_failure(
                    message,
                    user_id,
                    failure_kind="artifact_missing",
                    rendered_text=safe_get_messages(user_id).AUDIO_FILE_NOT_FOUND_MSG,
                    task_context=task_context,
                )
                continue

            # Embed cover into MP3 file if thumbnail is available
            try:
                logger.info(f"Looking for thumbnails for audio file: {audio_file}")
                logger.info(f"User folder contents: {os.listdir(user_folder)}")
                
                # Use pre-downloaded thumbnail if available
                cover_path = None
                if thumbnail_path and os.path.exists(thumbnail_path):
                    cover_path = thumbnail_path
                    logger.info(f"Using pre-downloaded thumbnail: {cover_path}")
                else:
                    # Fallback: look for any thumbnail files
                    logger.info("Pre-downloaded thumbnail not found, searching for any thumbnails")
                    for file in os.listdir(user_folder):
                        if file.endswith(('.jpg', '.jpeg', '.png', '.webp')) and file != downloaded_file:
                            thumb_path = os.path.join(user_folder, file)
                            if os.path.exists(thumb_path):
                                cover_path = thumb_path
                                logger.info(f"Found thumbnail: {cover_path}")
                                break
                
                # Embed cover if found
                if cover_path and os.path.exists(cover_path):
                    logger.info(f"Embedding cover {cover_path} into {audio_file}")
                    
                    # Extract metadata for embedding
                    original_title = info_dict.get("original_title", info_dict.get("title", ""))
                    artist = info_dict.get("artist") or info_dict.get("uploader") or info_dict.get("channel", "")
                    album = info_dict.get("album", "")
                    
                    # Remove artist name from title if it's included
                    title_for_metadata = original_title
                    if artist and artist in original_title:
                        # Remove artist name from title (e.g., "Rick Astley - Never Gonna Give You Up" -> "Never Gonna Give You Up")
                        title_for_metadata = original_title.replace(f"{artist} - ", "").replace(f"{artist}: ", "").strip()
                        logger.info(f"Removed artist from title: '{original_title}' -> '{title_for_metadata}'")
                    
                    logger.info(f"Metadata - Title: {title_for_metadata}, Artist: {artist}, Album: {album}")
                    
                    success = embed_cover_mp3(audio_file, cover_path, title=title_for_metadata, artist=artist, album=album)
                    if success:
                        logger.info(f"Successfully embedded cover in audio file: {audio_file}")
                    else:
                        logger.warning(f"Failed to embed cover in audio file: {audio_file}")
                else:
                    logger.warning(f"No thumbnail found for audio file: {audio_file}")
                    logger.warning(f"Available files in {user_folder}: {os.listdir(user_folder)}")
                    
            except Exception as e:
                logger.error(f"Error embedding cover in audio file {audio_file}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

            audio_files.append(audio_file)

            try:
                full_bar = "🟩" * 10
                safe_edit_message_text(user_id, proc_msg_id, safe_get_messages(user_id).AUDIO_UPLOADING_MSG.format(process=current_total_process, bar=full_bar))
            except Exception as e:
                logger.error(f"Error updating upload status: {e}")

            # We form a text with tags and a link for audio
            tags_for_final = tags if isinstance(tags, list) else (tags.split() if isinstance(tags, str) else [])
            tags_text_final = generate_final_tags(url, tags_for_final, info_dict)
            tags_block = (tags_text_final.strip() + '\n') if tags_text_final and tags_text_final.strip() else ''
            bot_name = getattr(Config, 'BOT_NAME', None) or 'bot'
            bot_mention = f' @{bot_name}' if not bot_name.startswith('@') else f' {bot_name}'
            # Create display title from MP3 metadata (artist + title)
            try:
                import mutagen
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3NoHeaderError
                
                # Try to read metadata from the MP3 file
                audio_metadata = MP3(audio_file)
                artist = audio_metadata.get('TPE1', ['Unknown Artist'])[0] if 'TPE1' in audio_metadata else 'Unknown Artist'
                title = audio_metadata.get('TIT2', ['Unknown Title'])[0] if 'TIT2' in audio_metadata else 'Unknown Title'
                
                # Create display title: "Artist - Title"
                display_title = f"{artist} - {title}"
                logger.info(f"MP3 metadata display title: '{display_title}'")
                
            except Exception as e:
                logger.warning(f"Failed to read MP3 metadata, using original title: {e}")
                display_title = original_audio_title
            
            # Use display title from metadata for caption
            caption_with_link = f"{display_title}\n{tags_block}[🔗 Audio URL]({url}){bot_mention}"
            
            # Trim caption to fit Telegram's 1024 character limit using truncate_caption
            from HELPERS.caption import truncate_caption
            title_html, pre_block, blockquote_content, tags_block, link_block, was_truncated = truncate_caption(
                title=display_title,
                description="",  # No description for audio
                url=url,
                tags_text=tags_text_final,
                max_length=1000,  # Reduced for safety
                user_id=user_id
            )
            # Rebuild caption from truncated parts
            caption_with_link = ""
            if title_html:
                caption_with_link += title_html + "\n"
            if tags_block:
                caption_with_link += tags_block
            caption_with_link += link_block
            
            try:
                # Create Telegram-compliant thumbnail if cover is available
                telegram_thumb = None
                if cover_path and os.path.exists(cover_path):
                    telegram_thumb_path = os.path.join(user_folder, f"telegram_thumb_{idx}.jpg")
                    if create_telegram_thumbnail(cover_path, telegram_thumb_path):
                        telegram_thumb = telegram_thumb_path
                        logger.info(f"Using Telegram thumbnail: {telegram_thumb}")
                    else:
                        logger.warning("Failed to create Telegram thumbnail")
                
                is_nsfw = _is_nsfw_audio_delivery(url, user_forced_nsfw)
                is_private_chat = getattr(message.chat, "type", None) == enums.ChatType.PRIVATE
                is_paid = is_nsfw and is_private_chat
                file_ext = os.path.splitext(audio_file)[1].lower()
                audio_msg = _send_audio_to_user(
                    user_id=user_id,
                    audio_file=audio_file,
                    caption_with_link=caption_with_link,
                    telegram_thumb=telegram_thumb,
                    message=message,
                    file_ext=file_ext,
                    is_paid=is_paid,
                )
                route_result = _route_uploaded_audio_to_logs(
                    message=message,
                    user_id=user_id,
                    audio_msg=audio_msg,
                    audio_file=audio_file,
                    caption_with_link=caption_with_link,
                    telegram_thumb=telegram_thumb,
                    url=url,
                    user_forced_nsfw=user_forced_nsfw,
                )
                _cache_audio_delivery(
                    forwarded_msg=route_result["forwarded_msg"],
                    is_nsfw=route_result["is_nsfw"],
                    quality_key=quality_key,
                    is_playlist=is_playlist,
                    original_playlist_index=original_playlist_index,
                    url=url,
                    message=message,
                    user_id=user_id,
                    playlist_indices=playlist_indices,
                    playlist_msg_ids=playlist_msg_ids,
                )
            except Exception as send_error:
                logger.error(f"Error sending audio: {send_error}")
                _send_audio_failure(
                    message,
                    user_id,
                    failure_kind="delivery_failed",
                    error_text=str(send_error),
                    rendered_text=safe_get_messages(user_id).AUDIO_SEND_FAILED_MSG.format(error=send_error),
                    attempted_count=len(indices_to_download) if 'indices_to_download' in locals() else 0,
                    delivered_count=successful_uploads,
                    task_context=task_context,
                )
                continue

            # Clean up the audio file after sending
            try:
                send_mediainfo_if_enabled(user_id, audio_file, message)
                os.remove(audio_file)
            except Exception as e:
                logger.error(f"Failed to delete audio file {audio_file}: {e}")

            # Add delay between uploads for playlists
            if idx and idx < len(indices_to_download) - 1:
                pass

        outcome = upload_terminal_outcome(
            media_kind="audio",
            attempted_count=len(indices_to_download),
            delivered_count=successful_uploads,
            cached_count=len(cached_videos) if is_playlist and quality_key else 0,
        )
        if playlist_name:
            error_summary = get_playlist_error_summary(f"{user_id}_{playlist_name}")
            if error_summary is not None:
                outcome = downgrade_completed_outcome_to_partial(
                    outcome,
                    playlist_error_summary=error_summary,
                )
        task_context = _execute_audio_completion_plan(
            plan=_build_audio_completion_plan(
                is_playlist=is_playlist,
                quality_key=quality_key,
                outcome=outcome,
            ),
            app=app,
            user_id=user_id,
            proc_msg_id=proc_msg_id,
            message=message,
            outcome=outcome,
            task_context=task_context,
            requested_indices=requested_indices,
            quality_key=quality_key,
        )

    except Exception as e:
        if "Download timeout exceeded" in str(e):
            _send_audio_failure(
                message,
                user_id,
                failure_kind="timeout",
                attempted_count=len(indices_to_download) if 'indices_to_download' in locals() else 0,
                delivered_count=successful_uploads if 'successful_uploads' in locals() else 0,
                task_context=task_context,
            )
            log_error_to_channel(message, LoggerMsg.DOWNLOAD_TIMEOUT_LOG, url)
        else:
            logger.error(f"Error in audio download: {e}")
            _send_audio_failure(
                message,
                user_id,
                failure_kind="download_failed",
                error_text=str(e),
                attempted_count=len(indices_to_download) if 'indices_to_download' in locals() else 0,
                delivered_count=successful_uploads if 'successful_uploads' in locals() else 0,
                task_context=task_context,
            )
        # Immediate cleanup on error
        try:
            if status_msg_id:
                safe_delete_messages(chat_id=user_id, message_ids=[status_msg_id], revoke=True)
            if hourglass_msg_id:
                safe_delete_messages(chat_id=user_id, message_ids=[hourglass_msg_id], revoke=True)
            if download_started_msg_id:
                safe_delete_messages(chat_id=user_id, message_ids=[download_started_msg_id], revoke=True)
            stop_anim.set()
        except Exception:
            pass
    finally:
        # Always clean up resources
        stop_anim.set()
        if anim_thread:
            anim_thread.join(timeout=1)  # Wait for animation thread with timeout

        try:
            if status_msg_id:
                safe_delete_messages(chat_id=user_id, message_ids=[status_msg_id], revoke=True)
            if hourglass_msg_id:
                safe_delete_messages(chat_id=user_id, message_ids=[hourglass_msg_id], revoke=True)
        except Exception as e:
            logger.error(f"Error deleting status messages: {e}")

        # Clean up any remaining audio files
        for audio_file in audio_files:
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except Exception as e:
                logger.error(f"Failed to delete file {audio_file}: {e}")
        
        # Clean up any downloaded thumbnails
        try:
            # Use the unique download directory for cleanup
            if os.path.exists(user_folder):
                # Clean up YouTube thumbnails
                for thumb_file in os.listdir(user_folder):
                    if thumb_file.startswith("yt_thumb_") and thumb_file.endswith(".jpg"):
                        try:
                            os.remove(os.path.join(user_folder, thumb_file))
                        except Exception as e:
                            logger.error(f"Failed to delete thumbnail {thumb_file}: {e}")
                
                # Clean up universal thumbnails
                universal_thumb = os.path.join(user_folder, "universal_thumb.jpg")
                if os.path.exists(universal_thumb):
                    try:
                        os.remove(universal_thumb)
                    except Exception as e:
                        logger.error(f"Failed to delete universal thumbnail: {e}")
                
                # Clean up any yt-dlp generated thumbnails
                for thumb_file in os.listdir(user_folder):
                    if thumb_file.endswith(('.jpg', '.jpeg', '.png', '.webp')) and not thumb_file.startswith("yt_thumb_"):
                        try:
                            os.remove(os.path.join(user_folder, thumb_file))
                        except Exception as e:
                            logger.error(f"Failed to delete thumbnail {thumb_file}: {e}")
                
                # Clean up Telegram thumbnails
                for thumb_file in os.listdir(user_folder):
                    if thumb_file.startswith("telegram_thumb_") and thumb_file.endswith(".jpg"):
                        try:
                            os.remove(os.path.join(user_folder, thumb_file))
                        except Exception as e:
                            logger.error(f"Failed to delete Telegram thumbnail {thumb_file}: {e}")
        except Exception as e:
            logger.error(f"Error cleaning up thumbnails: {e}")

        set_active_download(user_id, False)
        clear_download_start_time(user_id)  # Cleaning the start time

        # Clean up temporary files
        try:
            cleanup_user_temp_files(user_id)
        except Exception as e:
            logger.error(f"Error cleaning up temp files for user {user_id}: {e}")

        # Reset playlist errors if this was a playlist
        if playlist_name:
            clear_playlist_error_state(f"{user_id}_{playlist_name}")
