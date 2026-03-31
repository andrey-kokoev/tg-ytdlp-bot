# ####################################################################################

# Checking Actions
# Text Message Handler for General Commands
from HELPERS.app_instance import get_app
from HELPERS.decorators import reply_with_keyboard, background_handler
from HELPERS.limitter import is_user_in_channel, check_user
from HELPERS.logger import send_to_all, send_to_logger, send_to_user
from CONFIG.logger_msg import LoggerMsg, get_logger_msg
from CONFIG.messages import Messages, safe_get_messages
from HELPERS.caption import caption_editor
from HELPERS.filesystem_hlp import remove_media
from COMMANDS.cookies_cmd import save_as_cookie_file, download_cookie, check_cookie_command, cookies_from_browser
from COMMANDS.subtitles_cmd import subs_command, clear_subs_check_cache
from COMMANDS.other_handlers import audio_command_handler, help_command, playlist_command
from COMMANDS.format_cmd import set_format
from COMMANDS.mediainfo_cmd import mediainfo_command
from COMMANDS.settings_cmd import settings_command
from COMMANDS.split_sizer import split_command
from COMMANDS.tag_cmd import tags_command
from COMMANDS.search import search_command
from COMMANDS.keyboard_cmd import keyboard_command, keyboard_callback_handler
from COMMANDS.proxy_cmd import proxy_command
from COMMANDS.link_cmd import link_command
from COMMANDS.image_cmd import image_command
from DATABASE.firebase_init import is_user_blocked
import os
from URL_PARSERS.video_extractor import video_url_extractor
from URL_PARSERS.playlist_utils import is_playlist_with_range
from URL_PARSERS.tags import extract_url_range_tags
from pyrogram import filters
import re
from CONFIG.config import Config
from HELPERS.logger import logger
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import enums
from HELPERS.safe_messeger import fake_message
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_message_envelope
from HELPERS.ingress_requests import (
    build_auto_cache_command_request,
    build_ban_time_command_request,
    build_block_user_command_request,
    build_close_message_request,
    build_add_bot_to_group_selection_request,
    build_add_bot_to_group_request,
    build_broadcast_command_request,
    build_language_selection_request,
    build_reload_cache_command_request,
    build_runtime_command_request,
    build_start_command_request,
    build_uncache_command_request,
    build_unblock_user_command_request,
    build_user_details_command_request,
    build_user_logs_command_request,
    build_usage_command_request,
    build_url_download_request,
)
from HELPERS.request_execution import (
    handle_auto_cache_command_request,
    handle_ban_time_command_request,
    handle_block_user_command_request,
    handle_close_message_request,
    handle_add_bot_to_group_selection_request,
    handle_add_bot_to_group_request,
    handle_broadcast_command_request,
    build_callback_execution_context,
    build_message_execution_context,
    handle_language_selection_request,
    handle_reload_cache_command_request,
    handle_runtime_command_request,
    handle_start_command_request,
    handle_uncache_command_request,
    handle_unblock_user_command_request,
    handle_user_details_command_request,
    handle_user_logs_command_request,
    handle_usage_command_request,
    handle_url_download_request,
)

# Get app instance for decorators
app = get_app()


EMOJI_COMMAND_MAP = {
    "🧹": Config.CLEAN_COMMAND,
    "🍪": Config.DOWNLOAD_COOKIE_COMMAND,
    "⚙️": Config.SETTINGS_COMMAND,
    "🔍": Config.SEARCH_COMMAND,
    "🌐": Config.COOKIES_FROM_BROWSER_COMMAND,
    "🔗": Config.LINK_COMMAND,
    "📼": Config.FORMAT_COMMAND,
    "📊": Config.MEDIINFO_COMMAND,
    "✂️": Config.SPLIT_COMMAND,
    "🎧": Config.AUDIO_COMMAND,
    "💬": Config.SUBS_COMMAND,
    "#️⃣": Config.TAGS_COMMAND,
    "🆘": "/help",
    "📃": Config.USAGE_COMMAND,
    "⏯️": Config.PLAYLIST_COMMAND,
    "🎹": Config.KEYBOARD_COMMAND,
    "🌎": Config.PROXY_COMMAND,
    "✅": Config.CHECK_COOKIE_COMMAND,
    "🖼": Config.IMG_COMMAND,
    "🧰": Config.ARGS_COMMAND,
    "🔞": Config.NSFW_COMMAND,
    "🧾": Config.LIST_COMMAND,
}


class UrlRouterContext:
    def __init__(self, message, text: str, user_id: int, is_admin: bool, is_command: bool):
        self.message = message
        self.text = text
        self.user_id = user_id
        self.is_admin = is_admin
        self.is_command = is_command


class UrlRouterTerminalPlan:
    def __init__(self, mode: str):
        self.mode = mode


def _ensure_command_tokens(message, text: str) -> None:
    if hasattr(message, "command") and message.command is not None:
        return

    parts = text.strip().split()
    if parts:
        cmd = parts[0][1:] if len(parts[0]) > 1 else ""
        args = parts[1:] if len(parts) > 1 else []
        message.command = [cmd] + args
    else:
        message.command = []


def _is_admin_only_command(text: str) -> bool:
    return (
        text.startswith(Config.UNCACHE_COMMAND)
        or text.startswith(Config.AUTO_CACHE_COMMAND)
        or Config.GET_USER_DETAILS_COMMAND in text
        or Config.UNBLOCK_USER_COMMAND in text
        or Config.BLOCK_USER_COMMAND in text
        or text.startswith(Config.BROADCAST_MESSAGE)
        or Config.GET_USER_LOGS_COMMAND in text
        or text.startswith(Config.RELOAD_CACHE_COMMAND)
    )


def _dispatch_emoji_command(app, message, *, mapped: str, user_id: int):
    if mapped == Config.AUDIO_COMMAND:
        return audio_command_handler(app, message)

    if mapped == Config.CLEAN_COMMAND:
        from COMMANDS.clean_cmd import clean_command

        logger.info(get_logger_msg().EMOJI_CLEAN_TRIGGERED_LOG_MSG.format(user_id=user_id))
        clean_command(app, message)
        logger.info(get_logger_msg().EMOJI_CLEAN_COMPLETED_LOG_MSG.format(user_id=user_id))
        return

    if mapped == Config.USAGE_COMMAND:
        logger.info(get_logger_msg().EMOJI_STATS_TRIGGERED_LOG_MSG.format(user_id=user_id))
        envelope = build_telegram_message_envelope(message, event_kind="command_message")
        request = build_usage_command_request(envelope)
        handle_usage_command_request(app, build_message_execution_context(message), request)
        logger.info(get_logger_msg().EMOJI_STATS_COMPLETED_LOG_MSG.format(user_id=user_id))
        return

    if mapped == "/help":
        return help_command(app, message)

    if mapped == Config.ARGS_COMMAND:
        from COMMANDS.args_cmd import args_command

        return args_command(app, message)

    if mapped == Config.NSFW_COMMAND:
        from COMMANDS.nsfw_cmd import nsfw_command

        return nsfw_command(app, message)

    if mapped == Config.LIST_COMMAND:
        from COMMANDS.list_cmd import list_command

        return list_command(app, message)

    handler_map = {
        Config.DOWNLOAD_COOKIE_COMMAND: download_cookie,
        Config.SETTINGS_COMMAND: settings_command,
        Config.SEARCH_COMMAND: search_command,
        Config.COOKIES_FROM_BROWSER_COMMAND: cookies_from_browser,
        Config.LINK_COMMAND: link_command,
        Config.FORMAT_COMMAND: set_format,
        Config.MEDIINFO_COMMAND: mediainfo_command,
        Config.SPLIT_COMMAND: split_command,
        Config.SUBS_COMMAND: subs_command,
        Config.TAGS_COMMAND: tags_command,
        Config.PLAYLIST_COMMAND: playlist_command,
        Config.KEYBOARD_COMMAND: keyboard_command,
        Config.PROXY_COMMAND: proxy_command,
        Config.CHECK_COOKIE_COMMAND: check_cookie_command,
        Config.IMG_COMMAND: image_command,
    }
    handler = handler_map.get(mapped)
    if handler is not None:
        return handler(app, message)

    logger.warning(get_logger_msg().EMOJI_UNKNOWN_COMMAND_LOG_MSG.format(mapped=mapped))
    return


def _dispatch_direct_command(app, message, text: str) -> bool:
    direct_commands = [
        (lambda value: value.startswith(Config.SEARCH_COMMAND), search_command, False),
        (lambda value: value == Config.KEYBOARD_COMMAND, keyboard_command, True),
        (lambda value: value.startswith(Config.SAVE_AS_COOKIE_COMMAND), save_as_cookie_file, False),
        (lambda value: value.startswith(Config.SUBS_COMMAND), subs_command, False),
        (lambda value: value.startswith(Config.PROXY_COMMAND), proxy_command, True),
        (lambda value: value.startswith(Config.LINK_COMMAND), link_command, True),
        (lambda value: value.startswith(Config.IMG_COMMAND), image_command, False),
        (lambda value: value.startswith(Config.ARGS_COMMAND), __import__("COMMANDS.args_cmd", fromlist=["args_command"]).args_command, False),
        (lambda value: value.startswith(Config.LIST_COMMAND), __import__("COMMANDS.list_cmd", fromlist=["list_command"]).list_command, False),
        (lambda value: value.startswith(Config.NSFW_COMMAND), __import__("COMMANDS.nsfw_cmd", fromlist=["nsfw_command"]).nsfw_command, False),
        (lambda value: value == Config.DOWNLOAD_COOKIE_COMMAND or value.startswith(Config.DOWNLOAD_COOKIE_COMMAND + " "), download_cookie, False),
        (lambda value: value == Config.CHECK_COOKIE_COMMAND, check_cookie_command, False),
        (lambda value: value.startswith(Config.COOKIES_FROM_BROWSER_COMMAND), cookies_from_browser, False),
        (lambda value: value.startswith(Config.AUDIO_COMMAND), audio_command_handler, False),
        (lambda value: value.startswith(Config.FORMAT_COMMAND), set_format, False),
        (lambda value: value.startswith(Config.MEDIINFO_COMMAND), mediainfo_command, False),
        (lambda value: value.startswith(Config.SETTINGS_COMMAND), settings_command, False),
        (lambda value: Config.USAGE_COMMAND in value, usage_command, False),
        (lambda value: value.startswith(Config.PLAYLIST_COMMAND), playlist_command, False),
        (lambda value: value.startswith(Config.CLEAN_COMMAND), __import__("COMMANDS.clean_cmd", fromlist=["clean_command"]).clean_command, False),
        (lambda value: Config.TAGS_COMMAND in value, tags_command, False),
        (lambda value: value.startswith(Config.SPLIT_COMMAND), split_command, True),
    ]

    for predicate, handler, ensure_tokens in direct_commands:
        if predicate(text):
            if ensure_tokens:
                _ensure_command_tokens(message, text)
            handler(app, message)
            return True
    return False


def _dispatch_admin_command(app, message, text: str) -> bool:
    envelope = build_telegram_message_envelope(message, event_kind="command_message")
    execution_context = build_message_execution_context(message)
    admin_commands = [
        (
            lambda value: value.startswith(Config.BROADCAST_MESSAGE),
            build_broadcast_command_request,
            handle_broadcast_command_request,
        ),
        (
            lambda value: Config.BLOCK_USER_COMMAND in value,
            build_block_user_command_request,
            handle_block_user_command_request,
        ),
        (
            lambda value: Config.UNBLOCK_USER_COMMAND in value,
            build_unblock_user_command_request,
            handle_unblock_user_command_request,
        ),
        (
            lambda value: Config.BAN_TIME_COMMAND in value,
            build_ban_time_command_request,
            handle_ban_time_command_request,
        ),
        (
            lambda value: Config.RUN_TIME in value,
            build_runtime_command_request,
            handle_runtime_command_request,
        ),
        (
            lambda value: Config.GET_USER_DETAILS_COMMAND in value,
            build_user_details_command_request,
            handle_user_details_command_request,
        ),
        (
            lambda value: Config.GET_USER_LOGS_COMMAND in value,
            build_user_logs_command_request,
            handle_user_logs_command_request,
        ),
        (
            lambda value: Config.RELOAD_CACHE_COMMAND in value,
            build_reload_cache_command_request,
            handle_reload_cache_command_request,
        ),
        (
            lambda value: Config.AUTO_CACHE_COMMAND in value,
            build_auto_cache_command_request,
            handle_auto_cache_command_request,
        ),
        (
            lambda value: value.startswith(Config.UNCACHE_COMMAND),
            build_uncache_command_request,
            handle_uncache_command_request,
        ),
    ]

    for predicate, request_builder, request_handler in admin_commands:
        if predicate(text):
            request = request_builder(envelope)
            request_handler(app, execution_context, request)
            return True
    return False


def _dispatch_basic_command(app, message, text: str) -> bool:
    from COMMANDS.lang_cmd import lang_command

    basic_commands = [
        (
            lambda value: value == "/start",
            lambda current_message: handle_start_command_request(
                app,
                build_message_execution_context(current_message),
                build_start_command_request(
                    build_telegram_message_envelope(
                        current_message,
                        event_kind="command_message",
                    )
                ),
            ),
        ),
        (
            lambda value: value == "/help",
            lambda current_message: help_command(app, current_message),
        ),
        (
            lambda value: value == Config.ADD_BOT_TO_GROUP_COMMAND,
            lambda current_message: handle_add_bot_to_group_request(
                app,
                build_message_execution_context(current_message),
                build_add_bot_to_group_request(
                    build_telegram_message_envelope(
                        current_message,
                        event_kind="command_message",
                    )
                ),
            ),
        ),
        (
            lambda value: value.startswith("/lang"),
            lambda current_message: lang_command(app, current_message),
        ),
    ]

    for predicate, handler in basic_commands:
        if predicate(text):
            handler(message)
            return True
    return False


def _has_args_import_header(text: str) -> bool:
    args_headers = [
        "📋 Current yt-dlp Arguments:",
        "📋 वर्तमान yt-dlp तर्क:",
        "📋 وسائط yt-dlp الحالية:",
    ]
    return any(header in text for header in args_headers)


def _looks_like_args_import_template(text: str, user_id: int, *, final_check: bool = False) -> bool:
    if not _has_args_import_header(text):
        return False

    if final_check:
        has_settings_line = any(
            ":" in line and ("✅" in line or "❌" in line or "True" in line or "False" in line)
            for line in text.split("\n")
        )
    else:
        messages = safe_get_messages(user_id)
        has_settings_line = any(
            ":" in line
            and (
                "✅" in line
                or "❌" in line
                or "True" in line
                or "False" in line
                or messages.ARGS_STATUS_TRUE_DISPLAY_MSG in line
                or messages.ARGS_STATUS_FALSE_DISPLAY_MSG in line
            )
            for line in text.split("\n")
        )

    has_forward_instruction = (
        safe_get_messages(user_id).ARGS_FORWARD_TEMPLATE_MSG in text
        or "apply these settings" in text
    )
    has_separator = ("---" in text or "-" in text)
    logger.info(
        LoggerMsg.URL_EXTRACTOR_SETTINGS_CHECK_LOG_MSG.format(
            has_settings_line=has_settings_line,
            has_forward_instruction=has_forward_instruction,
            has_separator=has_separator,
        )
    )
    return has_settings_line or has_forward_instruction or has_separator


def _rewrite_vid_command_text(text: str) -> str | None:
    parts_full = text.strip().split(maxsplit=2)
    if len(parts_full) < 3 or not re.match(r"^-?\d+-\d*$", parts_full[1]):
        return None

    rng = parts_full[1]
    url_only = parts_full[2]
    if rng.startswith("-"):
        match = re.match(r"^-(\d+)-(\d*)$", rng)
        if match:
            first_num = f"-{match.group(1)}"
            second_num = f"-{match.group(2)}" if match.group(2) else None
            if second_num:
                return f"{url_only}*{first_num}*{second_num}"
            return f"{url_only}*{first_num}*"

        first_value, second_value = rng.split("-", 1)
        if second_value != "":
            second_value = f"-{second_value}"
        return (
            f"{url_only}*{first_value}*{second_value}"
            if second_value
            else f"{url_only}*{first_value}*"
        )

    first_value, second_value = rng.split("-", 1)
    if second_value == "":
        return f"{url_only}*{first_value}*"
    return f"{url_only}*{first_value}*{second_value}"


def _render_vid_help(message, user_id: int) -> None:
    from HELPERS.safe_messeger import safe_send_message

    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                safe_get_messages(user_id).URL_EXTRACTOR_VID_HELP_CLOSE_BUTTON_MSG,
                callback_data="vid_help|close",
            )
        ]]
    )
    help_text = (
        f"<b>{safe_get_messages(user_id).URL_EXTRACTOR_VID_HELP_TITLE_MSG}</b>\n\n"
        f"{safe_get_messages(user_id).URL_EXTRACTOR_VID_HELP_USAGE_MSG}\n\n"
        f"<b>{safe_get_messages(user_id).URL_EXTRACTOR_VID_HELP_EXAMPLES_MSG}</b>\n"
        f"{safe_get_messages(user_id).URL_EXTRACTOR_VID_HELP_EXAMPLE_1_MSG}\n\n"
        f"{safe_get_messages(user_id).URL_EXTRACTOR_VID_HELP_ALSO_SEE_MSG}"
    )
    safe_send_message(
        message.chat.id,
        help_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
        message=message,
    )


def _maybe_handle_args_import(
    app,
    message,
    text: str,
    user_id: int,
    args_import_handler,
    *,
    final_check: bool = False,
) -> bool:
    if not _has_args_import_header(text):
        return False

    if final_check:
        logger.info(f"Final check: Found potential args import template in message from user {user_id}")
    else:
        logger.info(LoggerMsg.URL_EXTRACTOR_FOUND_ARGS_TEMPLATE_LOG_MSG.format(user_id=user_id))

    if not _looks_like_args_import_template(text, user_id, final_check=final_check):
        return False

    if final_check:
        logger.info(f"Final check: Calling args_import_handler for user {user_id}")
    else:
        logger.info(LoggerMsg.URL_EXTRACTOR_CALLING_ARGS_IMPORT_LOG_MSG.format(user_id=user_id))

    args_import_handler(app, message)
    return True


def _maybe_handle_vid_or_url_message(app, message, text: str, user_id: int, is_admin: bool) -> bool:
    from HELPERS.safe_messeger import fake_message, safe_send_message

    range_processed = False
    if text.strip().lower().startswith("/vid"):
        new_text = _rewrite_vid_command_text(text)
        if new_text is not None:
            try:
                message.text = new_text
                range_processed = True
                logger.info(f"🔍 [DEBUG] /vid command transformed in url_extractor: '{text}' -> '{new_text}'")
                logger.info(f"🔍 [DEBUG] message.text after transformation: '{message.text}'")
            except Exception as e:
                logger.error(f"🔍 [DEBUG] Error while updating message.text: {e}")
        else:
            parts = text.strip().split(maxsplit=1)
            if len(parts) == 1:
                try:
                    _render_vid_help(message, user_id)
                except Exception:
                    pass
                return True
            if not range_processed:
                try:
                    message.text = parts[1]
                except Exception:
                    pass

    final_text = message.text if hasattr(message, "text") and message.text else text
    if ("https://" not in final_text) and ("http://" not in final_text):
        return False

    if is_user_blocked(message):
        return True

    from HELPERS.rate_limiter import check_rate_limit

    allowed, rate_limit_msg = check_rate_limit(user_id, is_admin)
    if not allowed:
        messages = safe_get_messages(user_id)
        safe_send_message(
            user_id,
            rate_limit_msg or messages.RATE_LIMIT_EXCEEDED_MSG if hasattr(messages, "RATE_LIMIT_EXCEEDED_MSG") else "Rate limit exceeded. Please wait.",
            message=message,
        )
        return True

    from COMMANDS.subtitles_cmd import clear_subs_check_cache

    clear_subs_check_cache()
    try:
        try:
            from .engine_router import route_if_gallerydl_only  # type: ignore
        except Exception:
            from URL_PARSERS.engine_router import route_if_gallerydl_only  # type: ignore
        if route_if_gallerydl_only(app, message):
            return True
    except Exception as route_e:
        logger.error(LoggerMsg.URL_EXTRACTOR_ENGINE_ROUTER_ERROR_LOG_MSG.format(error=route_e))

    try:
        logger.info(f"🔍 [DEBUG] url_extractor: before calling video_url_extractor, message.text='{message.text}'")
        envelope = build_telegram_message_envelope(message, raw_text=final_text, event_kind="text_message")
        url, video_start_with, video_end_with, playlist_name, tags, tags_text, tag_error = extract_url_range_tags(final_text)
        if tag_error:
            wrong, example = tag_error
            error_msg = safe_get_messages(user_id).TAG_FORBIDDEN_CHARS_MSG.format(tag=wrong, example=example)
            safe_send_message(user_id, error_msg, message=message)
            from HELPERS.logger import log_error_to_channel
            log_error_to_channel(message, error_msg)
            return True
        if not url:
            raise ValueError("URL message reached download path without extractable URL")
        request = build_url_download_request(
            envelope,
            url=url,
            tags=list(tags),
            tags_text=tags_text,
            playlist_name=playlist_name,
            video_start_with=video_start_with,
            video_end_with=video_end_with,
        )
        handle_url_download_request(app, build_message_execution_context(message), request)
    except Exception as e:
        logger.error(LoggerMsg.URL_EXTRACTOR_VIDEO_EXTRACTOR_FAILED_LOG_MSG.format(e=e))
        try:
            url, video_start_with, video_end_with, playlist_name, tags, tags_text, tag_error = extract_url_range_tags(message.text)

            if url:
                if video_start_with and video_end_with and (video_start_with != 1 or video_end_with != 1):
                    fallback_text = f"/img {video_start_with}-{video_end_with} {url}"
                else:
                    fallback_text = f"/img {url}"

                if tags_text:
                    fallback_text += f" {tags_text}"

                original_chat_id = message.chat.id if hasattr(message, "chat") else message.chat.id
                message_thread_id = getattr(message, "message_thread_id", None) if hasattr(message, "message_thread_id") else None
                fake_msg = fake_message(
                    fallback_text,
                    message.chat.id,
                    original_chat_id=original_chat_id,
                    message_thread_id=message_thread_id,
                    original_message=message,
                )

                image_command(app, fake_msg)
                logger.info(get_logger_msg().URL_EXTRACTOR_GALLERY_DL_FALLBACK_LOG_MSG.format(fallback_text=fallback_text))
            else:
                logger.error("No URL found for gallery-dl fallback")

        except Exception as e2:
            logger.error(LoggerMsg.URL_EXTRACTOR_GALLERY_DL_FALLBACK_FAILED_LOG_MSG.format(e2=e2))
    return True


def _maybe_handle_reply_message(app, message) -> bool:
    if not message.reply_to_message:
        return False

    if not is_user_blocked(message):
        if message.reply_to_message and message.reply_to_message.video:
            caption_editor(app, message)
    return True


def _determine_url_router_terminal_plan(message) -> UrlRouterTerminalPlan:
    if message.reply_to_message:
        return UrlRouterTerminalPlan("reply_message")
    return UrlRouterTerminalPlan("unmatched_message")


def _execute_url_router_terminal_plan(
    app,
    plan: UrlRouterTerminalPlan,
    *,
    message,
    text: str,
    user_id: int,
    args_import_handler,
) -> bool:
    if plan.mode == "reply_message":
        return _maybe_handle_reply_message(app, message)
    if plan.mode == "unmatched_message":
        _finalize_unmatched_message(app, message, text, user_id, args_import_handler)
        return True
    return False


def _finalize_unmatched_message(
    app,
    message,
    text: str,
    user_id: int,
    args_import_handler,
) -> None:
    if _maybe_handle_args_import(
        app,
        message,
        text,
        user_id,
        args_import_handler,
        final_check=True,
    ):
        return

    logger.info(LoggerMsg.URL_EXTRACTOR_NO_MATCHING_COMMAND_LOG_MSG.format(user_id=user_id))
    from COMMANDS.subtitles_cmd import clear_subs_check_cache

    clear_subs_check_cache()


def _build_url_router_context(message) -> UrlRouterContext:
    user_id = message.chat.id
    raw_text = message.text or ""
    text = raw_text.strip()
    is_admin = int(user_id) in Config.ADMIN
    is_command = text.startswith('/') or text in EMOJI_COMMAND_MAP
    return UrlRouterContext(
        message=message,
        text=text,
        user_id=user_id,
        is_admin=is_admin,
        is_command=is_command,
    )


def _route_url_text_message(app, route_context: UrlRouterContext, args_import_handler) -> bool:
    message = route_context.message
    text = route_context.text
    user_id = route_context.user_id

    if _maybe_handle_args_import(app, message, text, user_id, args_import_handler):
        return True

    try:
        bot_mention = f"@{getattr(Config, 'BOT_NAME', '').strip()}"
        if bot_mention and bot_mention in text:
            text = text.replace(bot_mention, "").strip()
            route_context.text = text
    except Exception:
        pass

    if text in EMOJI_COMMAND_MAP:
        mapped = EMOJI_COMMAND_MAP[text]
        from HELPERS.message_bridge import bridge_message_from_existing
        fake_msg = bridge_message_from_existing(message, mapped)
        fake_msg._is_emoji_command = True
        _dispatch_emoji_command(app, fake_msg, mapped=mapped, user_id=user_id)
        return True

    if not route_context.is_admin and _is_admin_only_command(text):
        send_to_user(message, safe_get_messages(user_id).ACCESS_DENIED_ADMIN)
        return True

    if _dispatch_basic_command(app, message, text):
        return True

    if not route_context.is_admin and not is_user_in_channel(app, message):
        return True

    if _dispatch_direct_command(app, message, text):
        return True

    if _maybe_handle_vid_or_url_message(app, message, text, user_id, route_context.is_admin):
        return True

    if route_context.is_admin and _dispatch_admin_command(app, message, text):
        return True

    terminal_plan = _determine_url_router_terminal_plan(message)
    return _execute_url_router_terminal_plan(
        app,
        terminal_plan,
        message=message,
        text=text,
        user_id=user_id,
        args_import_handler=args_import_handler,
    )

@app.on_message(filters.text & filters.private)
@background_handler(label="url_distractor")
def url_distractor(app, message):
    from_user = getattr(message, "from_user", None)
    if getattr(from_user, "is_bot", False) or getattr(message, "outgoing", False):
        return

    route_context = _build_url_router_context(message)
    user_id = route_context.user_id
    logger.info(f"🔍 [DEBUG] url_distractor: message.text at function start='{message.text}'")
    logger.info(f"🔍 [DEBUG] url_distractor: text after strip='{route_context.text}'")
    
    # Check command rate limit (for all commands, not just URLs)
    from HELPERS.command_limiter import check_command_limit
    from CONFIG.messages import safe_get_messages
    from HELPERS.safe_messeger import safe_send_message
    
    if route_context.is_command:
        allowed, cmd_limit_msg = check_command_limit(user_id, route_context.is_admin)
        if not allowed:
            messages = safe_get_messages(user_id)
            safe_send_message(
                user_id,
                cmd_limit_msg or "Too many commands. Please wait.",
                message=message
            )
            return
    
    # Import get_messages_instance locally to avoid UnboundLocalError
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from HELPERS.filesystem_hlp import remove_media
    from COMMANDS.cookies_cmd import download_cookie
    
    # Debug logging (logger already imported globally)
    logger.info(LoggerMsg.URL_EXTRACTOR_DISTRACTOR_CALLED_LOG_MSG.format(text=route_context.text[:100]))
    
    # Prevent recursion for emoji commands
    if hasattr(message, '_is_emoji_command') and message._is_emoji_command:
        return
    
    # Check if user is in args input state
    from COMMANDS.args_cmd import user_input_states, handle_args_text_input, args_import_handler
    if user_id in user_input_states:
        handle_args_text_input(app, message)
        return
    logger.info(f"Full message text length: {len(route_context.text) if route_context.text else 0}")
    logger.info(f"Message text preview: {route_context.text[:200] if route_context.text else 'None'}...")
    _route_url_text_message(app, route_context, args_import_handler)

@app.on_callback_query(filters.regex("^keyboard\\|"))
def keyboard_callback_handler_wrapper(app, callback_query):
    """Handle keyboard setting callbacks"""
    keyboard_callback_handler(app, callback_query)

# The function is_playlist_with_range is now imported from URL_PARSERS.playlist_utils

# Callback handler for add_bot_to_group close button
@app.on_callback_query(filters.regex(r"^add_group_msg\|"))
def add_group_msg_callback(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_add_bot_to_group_selection_request(
        callback_envelope,
        action_kind="close",
        action_value=callback_query.data.split("|")[1],
    )
    handle_add_bot_to_group_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def add_group_msg_callback_logic(app, callback_query, request) -> None:
    """Handle add_bot_to_group command callback queries"""
    try:
        user_id = callback_query.from_user.id
        
        if request.action_kind == "close" and request.action_value == "close":
            # Delete the message with add_bot_to_group instructions
            try:
                app.delete_messages(
                    callback_query.message.chat.id,
                    callback_query.message.id
                )
            except Exception:
                # If can't delete, just edit to show closed message
                app.edit_message_text(
                    callback_query.message.chat.id,
                    callback_query.message.id,
                    LoggerMsg.URL_EXTRACTOR_ADD_GROUP_HELPER_CLOSED_LOG_MSG
                )
            
            # Answer callback query
            callback_query.answer(safe_get_messages(user_id).URL_EXTRACTOR_CLOSED_MSG)
            
            # Log the action
            send_to_logger(callback_query.message, safe_get_messages(user_id).URL_EXTRACTOR_ADD_GROUP_USER_CLOSED_MSG.format(user_id=user_id))
            
    except Exception as e:
        # Log error and answer callback
        send_to_logger(callback_query.message, LoggerMsg.URL_EXTRACTOR_ADD_GROUP_CALLBACK_ERROR_LOG_MSG.format(e=e))
        callback_query.answer(safe_get_messages(user_id).URL_EXTRACTOR_ERROR_OCCURRED_MSG, show_alert=True)

# Callback handler for audio hint close button
@app.on_callback_query(filters.regex(r"^audio_hint\|"))
def audio_hint_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="audio_hint")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).URL_EXTRACTOR_CLOSED_MSG,
        log_text=safe_get_messages(user_id).URL_EXTRACTOR_AUDIO_HINT_CLOSED_MSG.format(user_id=user_id),
    )


@app.on_callback_query(filters.regex(r"^vid_help\|"))
def vid_help_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="vid_help")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).URL_EXTRACTOR_CLOSED_MSG,
        log_text=safe_get_messages(user_id).URL_EXTRACTOR_CLOSED_MSG,
    )

# Callback handler for link hint close button
@app.on_callback_query(filters.regex(r"^link_hint\|"))
def link_hint_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="link_hint")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).URL_EXTRACTOR_CLOSED_MSG,
        log_text=safe_get_messages(user_id).URL_EXTRACTOR_LINK_HINT_CLOSED_MSG.format(user_id=user_id),
    )

# Callback handler for language selection
@app.on_callback_query(filters.regex(r"^lang_"))
def lang_callback(app, callback_query):
    data = callback_query.data
    callback_envelope = build_telegram_callback_envelope(callback_query)
    if data.startswith("lang_select_"):
        request = build_language_selection_request(
            callback_envelope,
            action_kind="select",
            action_value=data.replace("lang_select_", ""),
        )
    else:
        request = build_language_selection_request(
            callback_envelope,
            action_kind="close",
            action_value="close",
        )
    handle_language_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def lang_callback_logic(app, callback_query, request) -> None:
    """Handle language selection callback queries"""
    from HELPERS.logger import send_to_logger, logger
    try:
        user_id = callback_query.from_user.id
        logger.info(f"Language callback triggered: {request.raw_input} for user {user_id}")
        
        if request.action_kind == 'select' and request.action_value:
            lang_code = request.action_value
            
            # Set user language
            from CONFIG.LANGUAGES.language_router import set_user_language
            logger.info(f"Setting language {lang_code} for user {user_id}")
            success = set_user_language(user_id, lang_code)
            logger.info(f"Language set result: {success}")
            
            if success:
                # Get messages in new language for this user
                from CONFIG.LANGUAGES.language_router import get_messages
                new_messages = get_messages(user_id, lang_code)
                
                # Get language name
                from CONFIG.LANGUAGES.language_router import language_router
                available_languages = language_router.get_available_languages()
                lang_name = available_languages.get(lang_code, lang_code)
                
                # Send confirmation message
                confirmation_msg = getattr(new_messages, 'LANG_CHANGED_MSG', 
                    f"✅ Language changed to {lang_name}"
                )
                
                # Format the message with lang_name
                if '{lang_name}' in confirmation_msg:
                    confirmation_msg = confirmation_msg.format(lang_name=lang_name)
                
                callback_query.answer(confirmation_msg)
                callback_query.edit_message_text(
                    confirmation_msg,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                error_msg = safe_get_messages(user_id).LANG_ERROR_MSG if hasattr(safe_get_messages(user_id), 'LANG_ERROR_MSG') else "❌ Error changing language"
                callback_query.answer(error_msg)
                
        elif request.action_kind == 'close':
            # Close language selection
            close_msg = safe_get_messages(user_id).LANG_CLOSED_MSG if hasattr(safe_get_messages(user_id), 'LANG_CLOSED_MSG') else "Language selection closed"
            callback_query.answer(close_msg)
            callback_query.edit_message_text(close_msg)
            
    except Exception as e:
        # Log error and answer callback
        from CONFIG.logger_msg import LoggerMsg
        send_to_logger(callback_query.message, LoggerMsg.URL_EXTRACTOR_LANGUAGE_CALLBACK_ERROR_LOG_MSG.format(e=e))
        callback_query.answer(safe_get_messages(user_id).URL_EXTRACTOR_ERROR_OCCURRED_MSG, show_alert=True)

######################################################  


def start_command_logic(app, message, request=None) -> None:
    user_id = message.chat.id
    is_admin = int(user_id) in Config.ADMIN
    if is_admin:
        send_to_user(message, safe_get_messages(user_id).WELCOME_MASTER)
        return

    if not is_user_in_channel(app, message):
        return

    from HELPERS.safe_messeger import safe_send_message

    safe_send_message(
        message.chat.id,
        safe_get_messages(user_id).URL_EXTRACTOR_WELCOME_MSG.format(
            first_name=message.chat.first_name,
            credits=safe_get_messages(user_id).CREDITS_MSG,
        ),
        parse_mode=enums.ParseMode.HTML,
        message=message,
    )
    send_to_logger(message, LoggerMsg.USER_STARTED_BOT.format(chat_id=message.chat.id))


def add_bot_to_group_command_logic(app, message, request=None) -> None:
    user_id = message.chat.id
    if not is_user_in_channel(app, message):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            safe_get_messages(user_id).URL_EXTRACTOR_ADD_GROUP_CLOSE_BUTTON_MSG,
            callback_data="add_group_msg|close",
        )]
    ])
    from HELPERS.safe_messeger import safe_send_message

    try:
        safe_send_message(
            message.chat.id,
            safe_get_messages(user_id).ADD_BOT_TO_GROUP_MSG,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard,
            message=message,
        )
    except Exception:
        safe_send_message(
            message.chat.id,
            safe_get_messages(user_id).ADD_BOT_TO_GROUP_MSG,
            reply_markup=keyboard,
            message=message,
        )
    send_to_logger(message, LoggerMsg.ADD_BOT_TO_GROUP_SENT)
