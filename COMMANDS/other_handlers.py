# #############################################################################################################################

import os
import re
from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from HELPERS.safe_messeger import safe_send_message
from HELPERS.ingress_models import (
    build_telegram_message_envelope,
    build_telegram_callback_envelope,
)
from HELPERS.ingress_requests import (
    build_audio_download_request,
    build_close_message_request,
    build_concat_request,
    build_help_command_request,
    build_playlist_help_request,
    build_rename_request,
)
from HELPERS.request_execution import (
    build_callback_execution_context,
    build_message_execution_context,
    handle_audio_download_request,
    handle_concat_request,
    handle_close_message_request,
    handle_help_command_request,
    handle_playlist_help_request,
    handle_rename_request,
)

from HELPERS.app_instance import get_app
from HELPERS.decorators import reply_with_keyboard, send_reply_keyboard_always, background_handler
from HELPERS.logger import logger, send_to_logger, send_to_user
from HELPERS.limitter import is_user_in_channel, check_user, check_playlist_range_limits
from HELPERS.download_status import get_active_download
from HELPERS.filesystem_hlp import create_directory

from CONFIG.config import Config
from CONFIG.messages import Messages, safe_get_messages
from CONFIG.logger_msg import LoggerMsg

from URL_PARSERS.tags import extract_url_range_tags

from DOWN_AND_UP.audio_concat import (
    parse_concat_name_override,
    resend_last_audio_concat_with_new_name,
)
from COMMANDS.link_cmd import link_command
from COMMANDS.proxy_cmd import proxy_command

# Get app instance for decorators
app = get_app()

# Command handlers moved to URL_PARSERS/url_extractor.py url_distractor function
# to avoid conflicts with the main text handler

# Keep only the callback handler for help close button
@app.on_callback_query(filters.regex(r"^help_msg\|"))
def help_msg_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="help_msg")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).OTHER_HELP_CLOSED_MSG,
        log_text=safe_get_messages(user_id).HELP_MESSAGE_CLOSED_LOG_MSG,
    )


def help_command(app, message):
    envelope = build_telegram_message_envelope(message, event_kind="command_message")
    request = build_help_command_request(envelope)
    handle_help_command_request(app, build_message_execution_context(message), request)


def help_command_logic(app, message, request=None):
    user_id = message.chat.id
    if not is_user_in_channel(app, message):
        return
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(safe_get_messages(user_id).SETTINGS_DEV_GITHUB_BUTTON_MSG, url="https://github.com/upekshaip/tg-ytdlp-bot"),
            InlineKeyboardButton(safe_get_messages(user_id).SETTINGS_CONTR_GITHUB_BUTTON_MSG, url="https://github.com/chelaxian/tg-ytdlp-bot")
        ],
        [InlineKeyboardButton(safe_get_messages(user_id).URL_EXTRACTOR_HELP_CLOSE_BUTTON_MSG, callback_data="help_msg|close")]
    ])
    try:
        safe_send_message(
            message.chat.id,
            safe_get_messages(user_id).HELP_MSG,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard,
            message=message,
        )
    except Exception:
        safe_send_message(
            message.chat.id,
            safe_get_messages(user_id).HELP_MSG,
            reply_markup=keyboard,
            message=message,
        )
    send_to_logger(message, LoggerMsg.HELP_SENT_TO_USER)


#############################################################################################################################

# Command to Download Audio from a Video url
@app.on_message(filters.command("audio") & filters.private)
# @reply_with_keyboard
@background_handler(label="audio_command")
def audio_command_handler(app, message):
    messages = safe_get_messages(message.chat.id)
    user_id = message.chat.id
    if get_active_download(user_id):
        safe_send_message(user_id, safe_get_messages(user_id).AUDIO_WAIT_MSG, reply_parameters=ReplyParameters(message_id=message.id))
        return
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)
    text = message.text
    # Range syntax normalization:
    # support "/audio 1-10 URL" -> convert to "/audio URL*1*10" for a single pipeline
    try:
        parts = (text or '').split()
        if len(parts) >= 3 and parts[0].lower().startswith('/audio'):
            import re
            if re.match(r"^\d+-\d*$", parts[1]):
                rng = parts[1]
                start_str, end_str = rng.split('-')
                start_val = int(start_str)
                end_val = int(end_str) if end_str != '' else None
                if start_val and start_val >= 1:
                    url_candidate = ' '.join(parts[2:]).strip()
                    if end_val is not None:
                        text = f"/audio {url_candidate}*{start_val}*{end_val}"
                    else:
                        text = f"/audio {url_candidate}*{start_val}*"
    except Exception:
        pass
    envelope = build_telegram_message_envelope(message, raw_text=text, event_kind="command_message")
    url, _, _, _, tags, tags_text, tag_error = extract_url_range_tags(text)
    if tag_error:
        wrong, example = tag_error
        error_msg = safe_get_messages(user_id).OTHER_TAG_ERROR_MSG.format(wrong=wrong, example=example)
        safe_send_message(user_id, error_msg, reply_parameters=ReplyParameters(message_id=message.id))
        from HELPERS.logger import log_error_to_channel
        log_error_to_channel(message, error_msg)
        return
    if not url:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(safe_get_messages(user_id).OTHER_AUDIO_HINT_CLOSE_BUTTON_MSG, callback_data="audio_hint|close")]
        ])
        safe_send_message(
            user_id,
            safe_get_messages(user_id).AUDIO_HELP_MSG,
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=message.id),
            reply_markup=keyboard
        )
        send_to_logger(message, safe_get_messages(user_id).AUDIO_HELP_SHOWN_LOG_MSG)
        return
    # Extract playlist parameters from the message
    full_string = text or message.caption or ""
    _, video_start_with, video_end_with, playlist_name, _, _, tag_error = extract_url_range_tags(full_string)
    # Correct video_count calculation for negative indices
    if video_start_with < 0 and video_end_with < 0:
        video_count = abs(video_end_with) - abs(video_start_with) + 1
    elif video_start_with > video_end_with:
        video_count = abs(video_start_with - video_end_with) + 1
    else:
        video_count = video_end_with - video_start_with + 1
    
    # Checking the range limit
    if not check_playlist_range_limits(url, video_start_with, video_end_with, app, message):
        return
    
    request = build_audio_download_request(
        envelope,
        url=url,
        quality_key="mp3",
        format_override="ba",
        tags=list(tags),
        tags_text=tags_text,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
    )
    handle_audio_download_request(app, build_message_execution_context(message), request)


def _normalize_concat_command_text(text: str) -> tuple[str, bool, bool]:
    normalized = (text or "").strip()
    reverse_output = False
    audio_only = False
    if not normalized:
        return "/concat", reverse_output, audio_only

    parts = normalized.split(maxsplit=2)
    if len(parts) >= 2 and parts[1].lower() in {"reverse", "rev", "--reverse"}:
        reverse_output = True
        normalized = f"{parts[0]} {parts[2]}" if len(parts) >= 3 else parts[0]

    if "--audio-only" in normalized:
        audio_only = True
        normalized = re.sub(r"\s*--audio-only\b", "", normalized).strip()

    return normalized, reverse_output, audio_only


@app.on_message(filters.command(["aconcat", "audioconcat", "concat"]) & filters.private)
@background_handler(label="audio_concat_command")
def audio_concat_command_handler(app, message):
    user_id = message.chat.id
    if get_active_download(user_id):
        safe_send_message(
            user_id,
            safe_get_messages(user_id).AUDIO_WAIT_MSG,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        return
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return

    text, reverse_output, audio_only = _normalize_concat_command_text(message.text or "")
    if not text:
        text = "/concat"
    envelope = build_telegram_message_envelope(message, raw_text=text, event_kind="command_message")

    command_name = text.split(maxsplit=1)[0].lower()

    output_name_override, text = parse_concat_name_override(text)

    try:
        parts = text.split()
        if len(parts) >= 3 and parts[0].lower() in {"/aconcat", "/audioconcat", "/concat"}:
            if re.match(r"^\d+-\d+$", parts[1]):
                start_str, end_str = parts[1].split('-')
                url_candidate = ' '.join(parts[2:]).strip()
                text = f"{parts[0]} {url_candidate}*{int(start_str)}*{int(end_str)}"
    except Exception:
        pass

    url, _, _, _, _, _, tag_error = extract_url_range_tags(text)
    if tag_error:
        wrong, example = tag_error
        error_msg = safe_get_messages(user_id).OTHER_TAG_ERROR_MSG.format(wrong=wrong, example=example)
        safe_send_message(user_id, error_msg, reply_parameters=ReplyParameters(message_id=message.id))
        return

    if not url:
        safe_send_message(
            user_id,
            (
                    "Use /concat with a playlist URL and range.\n\n"
                    "Examples:\n"
                    "/concat --audio-only https://www.youtube.com/playlist?list=...*2*5\n"
                    "/concat reverse --audio-only https://www.youtube.com/playlist?list=...*2*5\n"
                    "/concat --audio-only 2-5 https://www.youtube.com/playlist?list=...\n"
                    "/concat https://www.youtube.com/playlist?list=...*2*5\n"
                    "/concat reverse 2-5 https://www.youtube.com/playlist?list=..."
                ),
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        return

    _, video_start_with, video_end_with, playlist_name, tags, tags_text, _ = extract_url_range_tags(text)
    if not check_playlist_range_limits(url, video_start_with, video_end_with, app, message):
        return
    if video_start_with < 0 or video_end_with < 0:
        safe_send_message(
            user_id,
            f"Negative playlist indices are not supported for {'/aconcat' if audio_only else '/concat'} yet.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        return
    if video_start_with == video_end_with:
        safe_send_message(
            user_id,
            f"{'Audio' if audio_only else 'Video'} concat needs at least 2 playlist items.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        return

    video_count = abs(video_end_with - video_start_with) + 1
    request = build_concat_request(
        envelope,
        url=url,
        media_mode="audio" if audio_only else "video",
        reverse_output=reverse_output,
        output_name_override=output_name_override,
        tags=list(tags),
        tags_text=tags_text,
        playlist_name=playlist_name,
        video_count=video_count,
        video_start_with=video_start_with,
        video_end_with=video_end_with,
    )
    handle_concat_request(app, build_message_execution_context(message), request)

@app.on_message(filters.command(["arename", "rename"]) & filters.private)
@background_handler(label="audio_concat_rename_command")
def audio_concat_rename_command_handler(app, message):
    user_id = message.chat.id
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return

    text = (message.text or "").strip()
    match = re.match(r'^/(?:arename|rename)(?:@\w+)?\s+"([^"]+)"\s*$', text)
    if not match:
        safe_send_message(
            user_id,
            'Use: <code>/rename "New Name"</code>',
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        return

    envelope = build_telegram_message_envelope(message, raw_text=text, event_kind="command_message")
    request = build_rename_request(
        envelope,
        target_kind="audio_concat",
        new_name=match.group(1).strip(),
    )
    handle_rename_request(app, build_message_execution_context(message), request)


# /Link Command
@app.on_message(filters.command("link") & filters.private)
@background_handler(label="link_command")
def link_command_handler(app, message):
    user_id = message.chat.id
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return
    link_command(app, message)

# /Proxy Command
@app.on_message(filters.command("proxy") & filters.private)
@background_handler(label="proxy_command")
def proxy_command_handler(app, message):
    user_id = message.chat.id
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return
    proxy_command(app, message)


# /Playlist Command
@app.on_message(filters.command("playlist") & filters.private)
# @reply_with_keyboard
@background_handler(label="playlist_command")
def playlist_command(app, message):
    envelope = build_telegram_message_envelope(message, event_kind="command_message")
    request = build_playlist_help_request(envelope)
    handle_playlist_help_request(app, build_message_execution_context(message), request)


def playlist_command_logic(app, message, request=None):
    messages = safe_get_messages(message.chat.id)
    user_id = message.chat.id
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(safe_get_messages(user_id).OTHER_PLAYLIST_HELP_CLOSE_BUTTON_MSG, callback_data="playlist_help|close")]
    ])
    safe_send_message(user_id, safe_get_messages(user_id).PLAYLIST_HELP_MSG, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard, message=message)
    send_to_logger(message, safe_get_messages(user_id).PLAYLIST_HELP_REQUESTED_LOG_MSG)

@app.on_callback_query(filters.regex(r"^playlist_help\|"))
def playlist_help_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="playlist_help")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).PLAYLIST_HELP_CLOSED_MSG,
        log_text=safe_get_messages(user_id).PLAYLIST_HELP_CLOSED_LOG_MSG,
    )


@app.on_callback_query(filters.regex(r"^userlogs_close\|"))
def userlogs_close_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="userlogs_close")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).OTHER_LOGS_MESSAGE_CLOSED_MSG,
        log_text=safe_get_messages(user_id).USERLOGS_CLOSED_MSG,
    )

@app.on_callback_query(filters.regex(r"^audio_hint\|"))
def audio_hint_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="audio_hint")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).AUDIO_HELP_CLOSED_MSG,
        log_text=safe_get_messages(user_id).AUDIO_HINT_CLOSED_LOG_MSG,
    )
