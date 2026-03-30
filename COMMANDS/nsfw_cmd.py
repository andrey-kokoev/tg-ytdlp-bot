import os
from dataclasses import dataclass

from pyrogram import filters, enums
from CONFIG.config import Config
from CONFIG.messages import safe_get_messages
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from HELPERS.app_instance import get_app
from HELPERS.filesystem_hlp import create_directory
from HELPERS.logger import send_to_logger, logger
from CONFIG.logger_msg import LoggerMsg
from HELPERS.safe_messeger import safe_send_message, safe_edit_message_text
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_command_envelope
from HELPERS.ingress_requests import (
    build_close_message_request,
    build_nsfw_command_request,
    build_nsfw_option_selection_request,
)
from HELPERS.request_execution import (
    build_message_execution_context,
    build_callback_execution_context,
    handle_close_message_request,
    handle_nsfw_command_request,
    handle_nsfw_option_selection_request,
)
from HELPERS.decorators import background_handler
from HELPERS.limitter import is_user_in_channel

# Get app instance for decorators
app = get_app()


@dataclass(frozen=True)
class NsfwCommandContext:
    chat_id: int
    user_id: int
    storage_id: int
    chat_type: object
    source_message: object
    command_parts: list[str]


def _build_nsfw_command_context(message) -> NsfwCommandContext:
    chat_id = message.chat.id
    user_id = getattr(message.from_user, "id", None) or chat_id
    return NsfwCommandContext(
        chat_id=chat_id,
        user_id=user_id,
        storage_id=chat_id,
        chat_type=getattr(message.chat, "type", None),
        source_message=message,
        command_parts=(message.text or "").split(),
    )


def _nsfw_file_path(storage_id: int) -> str:
    user_dir = os.path.join("users", str(storage_id))
    create_directory(user_dir)
    return os.path.join(user_dir, "nsfw_blur.txt")


def _write_nsfw_setting(storage_id: int, value: str) -> None:
    with open(_nsfw_file_path(storage_id), "w", encoding="utf-8") as f:
        f.write(value)


def _build_nsfw_menu_keyboard(user_id: int, current_setting: bool) -> InlineKeyboardMarkup:
    messages = safe_get_messages(user_id)
    on_text = messages.NSFW_ON_NO_BLUR_MSG if not current_setting else messages.NSFW_ON_NO_BLUR_INACTIVE_MSG
    off_text = messages.NSFW_OFF_BLUR_MSG if current_setting else messages.NSFW_OFF_BLUR_INACTIVE_MSG
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(on_text, callback_data="nsfw_option|on"), InlineKeyboardButton(off_text, callback_data="nsfw_option|off")],
        [InlineKeyboardButton(messages.URL_EXTRACTOR_HELP_CLOSE_BUTTON_MSG, callback_data="nsfw_option|close")],
    ])


def _answer_nsfw_callback(callback_query, text: str | None = None) -> None:
    if text is None:
        callback_query.answer()
        return
    callback_query.answer(text)


def _edit_nsfw_callback_message(callback_query, text: str) -> None:
    safe_edit_message_text(
        callback_query.message.chat.id,
        callback_query.message.id,
        text,
        parse_mode=enums.ParseMode.HTML,
    )

# Like mediainfo: handle private here; groups are registered/wrapped in magic.py
@app.on_message(filters.command("nsfw"))
@background_handler(label="nsfw_command")
def nsfw_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_nsfw_command_request(envelope)
    handle_nsfw_command_request(app, build_message_execution_context(message), request)


def nsfw_command_logic(app, message, request=None):
    context = _build_nsfw_command_context(message)
    messages = safe_get_messages(context.user_id)
    if not bool(getattr(Config, "NSFW_CHECK_ENABLED", True)):
        safe_send_message(
            context.chat_id,
            "NSFW features are disabled by the bot owner.",
            parse_mode=enums.ParseMode.HTML,
            message=context.source_message,
        )
        return
    is_admin = int(context.user_id) in Config.ADMIN
    is_in_channel = is_user_in_channel(app, context.source_message)
    logger.info(LoggerMsg.NSFW_USER_REQUESTED_COMMAND_LOG_MSG.format(user_id=context.user_id))
    logger.info(LoggerMsg.NSFW_USER_IS_ADMIN_LOG_MSG.format(user_id=context.user_id, is_admin=is_admin))
    logger.info(LoggerMsg.NSFW_USER_IS_IN_CHANNEL_LOG_MSG.format(user_id=context.user_id, is_in_channel=is_in_channel))

    if context.chat_type == enums.ChatType.PRIVATE:
        if int(context.user_id) not in Config.ADMIN and not is_in_channel:
            logger.info(f"[NSFW] User {context.user_id} access denied - not admin and not in channel")
            return

    logger.info(f"[NSFW] User {context.user_id} access granted")
    _nsfw_file_path(context.storage_id)

    try:
        if len(context.command_parts) >= 2:
            arg = context.command_parts[1].lower()
            if arg in ("on", "off"):
                _write_nsfw_setting(context.storage_id, "ON" if arg == "on" else "OFF")
                if arg == "on":
                    safe_send_message(context.chat_id, messages.NSFW_ON_MSG, parse_mode=enums.ParseMode.HTML, message=context.source_message)
                else:
                    safe_send_message(context.chat_id, messages.NSFW_OFF_MSG, parse_mode=enums.ParseMode.HTML, message=context.source_message)
                send_to_logger(context.source_message, messages.NSFW_BLUR_SET_COMMAND_LOG_MSG.format(arg=arg))
                return
            else:
                safe_send_message(context.chat_id, messages.NSFW_INVALID_MSG, parse_mode=enums.ParseMode.HTML, message=context.source_message)
                return
    except Exception as e:
        logger.error(f"Error processing nsfw command: {e}")
        pass

    current_setting = is_nsfw_blur_enabled(context.storage_id)
    status_text = "currently blurred" if current_setting else "currently not blurred"
    safe_send_message(
        context.chat_id,
        messages.NSFW_BLUR_SETTINGS_TITLE_MSG.format(status=status_text),
        reply_markup=_build_nsfw_menu_keyboard(context.user_id, current_setting),
        parse_mode=enums.ParseMode.HTML,
        message=context.source_message
    )
    send_to_logger(context.source_message, messages.NSFW_MENU_OPENED_LOG_MSG)


@app.on_callback_query(filters.regex(r"^nsfw_option\|"))
def nsfw_option_callback(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_nsfw_option_selection_request(
        callback_envelope,
        selection_key=callback_query.data.split("|")[1],
    )
    handle_nsfw_option_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def nsfw_option_callback_logic(app, execution_context, request) -> None:
    callback_query = execution_context.callback_query
    user_id = callback_query.from_user.id
    messages = safe_get_messages(user_id)
    logger.info(f"[NSFW] callback: {callback_query.data}")
    data = request.selection_key
    chat = getattr(callback_query, "message", None).chat if getattr(callback_query, "message", None) else None
    chat_id = getattr(chat, "id", None) if chat else user_id
    storage_id = chat_id
    _nsfw_file_path(storage_id)
    
    if data == "close":
        close_request = build_close_message_request(
            build_telegram_callback_envelope(callback_query),
            close_scope="nsfw_option",
        )
        handle_close_message_request(
            app,
            execution_context,
            close_request,
            answer_text=messages.NSFW_MENU_CLOSED_MSG,
            log_text=messages.NSFW_MENU_CLOSED_LOG_MSG,
        )
        return
    
    if data == "on":
        _write_nsfw_setting(storage_id, "ON")
        _edit_nsfw_callback_message(callback_query, messages.NSFW_ON_MSG)
        send_to_logger(callback_query.message, messages.NSFW_BLUR_DISABLED_MSG)
        try:
            _answer_nsfw_callback(callback_query, messages.NSFW_BLUR_DISABLED_CALLBACK_MSG)
        except Exception:
            pass
        return
    
    if data == "off":
        _write_nsfw_setting(storage_id, "OFF")
        _edit_nsfw_callback_message(callback_query, messages.NSFW_OFF_MSG)
        send_to_logger(callback_query.message, messages.NSFW_BLUR_ENABLED_MSG)
        try:
            _answer_nsfw_callback(callback_query, messages.NSFW_BLUR_ENABLED_CALLBACK_MSG)
        except Exception:
            pass
        return


def is_nsfw_blur_enabled(user_id):
    """
    Check if NSFW blur is enabled for user.
    Returns True if blur should be applied (default behavior).
    Returns False if blur should be disabled.
    """
    nsfw_file = _nsfw_file_path(user_id)
    if not os.path.exists(nsfw_file):
        return True  # Default: blur enabled
    
    try:
        with open(nsfw_file, "r", encoding="utf-8") as f:
            content = f.read().strip().upper()
            return content != "ON"  # If file contains "ON", blur is disabled
    except Exception:
        return True  # Default: blur enabled on error


def should_apply_spoiler(user_id, is_nsfw, is_private_chat):
    """
    Determine if spoiler should be applied based on user settings and context.
    
    Args:
        user_id: User ID
        is_nsfw: Whether content is NSFW
        is_private_chat: Whether it's a private chat
    
    Returns:
        bool: True if spoiler should be applied
    """
    if not is_nsfw:
        return False
    
    # In groups, never apply spoiler for NSFW content
    if not is_private_chat:
        return False
    
    # In private chats, check user's blur setting
    return is_nsfw_blur_enabled(user_id)
