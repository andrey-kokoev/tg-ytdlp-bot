from pyrogram import filters
from CONFIG.config import Config
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dataclasses import dataclass

from HELPERS.app_instance import get_app
from HELPERS.filesystem_hlp import create_directory
from HELPERS.logger import send_to_logger, logger
from HELPERS.safe_messeger import safe_send_message, safe_edit_message_text
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_command_envelope
from HELPERS.ingress_requests import (
    build_close_message_request,
    build_split_command_request,
    build_split_size_selection_request,
)
from HELPERS.request_execution import (
    build_message_execution_context,
    build_callback_execution_context,
    handle_close_message_request,
    handle_split_command_request,
    handle_split_size_selection_request,
)
from HELPERS.decorators import background_handler
from HELPERS.limitter import humanbytes, is_user_in_channel
from CONFIG.messages import safe_get_messages
import re


@dataclass(frozen=True)
class SplitCommandContext:
    user_id: int
    source_message: object
    command_parts: list[str]


def _build_split_command_context(message) -> SplitCommandContext:
    return SplitCommandContext(
        user_id=message.chat.id,
        source_message=message,
        command_parts=list(getattr(message, "command", []) or []),
    )


def _split_file_path(user_id: int) -> str:
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)
    return os.path.join(user_dir, "split.txt")


def _save_split_size(user_id: int, size: int) -> None:
    with open(_split_file_path(user_id), "w", encoding="utf-8") as f:
        f.write(str(size))


def _build_split_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    messages = safe_get_messages(user_id)
    sizes = [
        ("100 MB", 100 * 1024 * 1024),
        ("250 MB", 250 * 1024 * 1024),
        ("500 MB", 500 * 1024 * 1024),
        ("750 MB", 750 * 1024 * 1024),
        ("1 GB", 1024 * 1024 * 1024),
        ("1.5 GB", 1536 * 1024 * 1024),
        ("2 GB (max)", 2 * 1024 * 1024 * 1024),
    ]
    buttons = []
    for i in range(0, len(sizes), 2):
        row = []
        for j in range(2):
            if i + j < len(sizes):
                text, size = sizes[i + j]
                row.append(InlineKeyboardButton(text, callback_data=f"split_size|{size}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(messages.SPLIT_CLOSE_BUTTON_MSG, callback_data="split_size|close")])
    return InlineKeyboardMarkup(buttons)


def _answer_split_callback(callback_query, text: str | None = None) -> None:
    if text is None:
        callback_query.answer()
        return
    callback_query.answer(text)


def _edit_split_callback_message(callback_query, text: str) -> None:
    safe_edit_message_text(callback_query.message.chat.id, callback_query.message.id, text)

def parse_size_argument(arg):
    """
    Parse size argument and return size in bytes
    
    Args:
        arg (str): Size argument (e.g., "250mb", "1.5gb", "2GB", "100mb", "2000mb")
        
    Returns:
        int: Size in bytes or None if invalid
    """
    if not arg:
        return None
    
    # Remove spaces and convert to lowercase
    arg = arg.lower().replace(" ", "")
    
    # Match patterns like "250mb", "1.5gb", "2GB", "100mb", "2000mb"
    match = re.match(r'^(\d+(?:\.\d+)?)(mb|gb)$', arg)
    if not match:
        return None
    
    number = float(match.group(1))
    unit = match.group(2)
    
    # Convert to bytes
    if unit.lower() == "mb":
        size_bytes = int(number * 1024 * 1024)
    elif unit.lower() == "gb":
        size_bytes = int(number * 1024 * 1024 * 1024)
    else:
        return None
    
    # Check limits: 100MB to 2GB
    min_size = 100 * 1024 * 1024  # 100MB
    max_size = 2 * 1024 * 1024 * 1024  # 2GB
    
    if size_bytes and size_bytes < min_size:
        return None  # Too small
    elif size_bytes and size_bytes > max_size:
        return None  # Too large
    
    return size_bytes

# Get app instance for decorators
app = get_app()

@app.on_message(filters.command("split") & filters.private)
# @reply_with_keyboard
@background_handler(label="split_command")
def split_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_split_command_request(envelope)
    handle_split_command_request(app, build_message_execution_context(message), request)


def split_command_logic(app, message, request=None):
    context = _build_split_command_context(message)
    messages = safe_get_messages(context.user_id)
    user_id = context.user_id
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, context.source_message):
        return
    
    if len(context.command_parts) > 1:
        arg = context.command_parts[1].lower()
        size = parse_size_argument(arg)
        if size:
            _save_split_size(user_id, size)
            safe_send_message(user_id, messages.SPLIT_SIZE_SET_MSG.format(size=humanbytes(size)), message=context.source_message)
            send_to_logger(context.source_message, messages.SPLIT_SIZE_SET_ARGUMENT_LOG_MSG.format(size=size))
            return
        else:
            safe_send_message(user_id, messages.SPLIT_INVALID_SIZE_MSG, message=context.source_message)
            return

    _split_file_path(user_id)
    safe_send_message(
        user_id,
        messages.SPLIT_MENU_TITLE_MSG,
        reply_markup=_build_split_menu_keyboard(user_id),
        message=context.source_message
    )
    send_to_logger(context.source_message, messages.SPLIT_MENU_OPENED_LOG_MSG)

@app.on_callback_query(filters.regex(r"^split_size\|"))
# @reply_with_keyboard
def split_size_callback(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_split_size_selection_request(
        callback_envelope,
        selection_key=callback_query.data.split("|")[1],
    )
    handle_split_size_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def split_size_callback_logic(app, execution_context, request) -> None:
    callback_query = execution_context.callback_query
    user_id = callback_query.from_user.id
    messages = safe_get_messages(user_id)
    logger.info(f"[SPLIT] callback: {callback_query.data}")
    data = request.selection_key
    if data == "close":
        close_request = build_close_message_request(
            build_telegram_callback_envelope(callback_query),
            close_scope="split_size",
        )
        handle_close_message_request(
            app,
            execution_context,
            close_request,
            answer_text=safe_get_messages(user_id).SPLIT_MENU_CLOSED_MSG,
            log_text=safe_get_messages(user_id).SPLIT_SELECTION_CLOSED_LOG_MSG,
        )
        return
    try:
        size = int(data)
    except Exception:
        _answer_split_callback(callback_query, messages.SPLIT_INVALID_SIZE_CALLBACK_MSG)
        return
    _save_split_size(user_id, size)
    _edit_split_callback_message(callback_query, messages.SPLIT_SIZE_SET_MSG.format(size=humanbytes(size)))
    send_to_logger(callback_query.message, messages.SPLIT_SIZE_SET_CALLBACK_LOG_MSG.format(size=size))

# --- Function for reading split.txt ---
def get_user_split_size(user_id):
    split_file = _split_file_path(user_id)
    if os.path.exists(split_file):
        try:
            with open(split_file, "r", encoding="utf-8") as f:
                size = int(f.read().strip())
                return size
        except Exception:
            pass
    return 1950 * 1024 * 1024  # default 1.95GB
