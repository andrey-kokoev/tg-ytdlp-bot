from HELPERS.app_instance import get_app
from pyrogram import filters
import os
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from HELPERS.safe_messeger import safe_send_message
from HELPERS.decorators import background_handler
from CONFIG.config import Config
from HELPERS.logger import send_to_logger
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_command_envelope
from HELPERS.ingress_requests import build_close_message_request, build_tags_command_request
from HELPERS.limitter import is_user_in_channel
from HELPERS.request_execution import (
    build_message_execution_context,
    build_callback_execution_context,
    handle_close_message_request,
    handle_tags_command_request,
)
from CONFIG.messages import Messages, safe_get_messages

# Get app instance for decorators
app = get_app()

@app.on_message(filters.command("tags") & filters.private)
# @reply_with_keyboard
@background_handler(label="tags_command")
def tags_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_tags_command_request(envelope)
    handle_tags_command_request(app, build_message_execution_context(message), request)


def tags_command_logic(app, message, request=None):
    messages = safe_get_messages(message.chat.id)
    user_id = message.chat.id
    # Subscription check for non-admins
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return
    user_dir = os.path.join("users", str(user_id))
    tags_file = os.path.join(user_dir, "tags.txt")
    if not os.path.exists(tags_file):
        reply_text = safe_get_messages(user_id).TAGS_NO_TAGS_MSG
        safe_send_message(user_id, reply_text, reply_parameters=ReplyParameters(message_id=message.id))
        send_to_logger(message, reply_text)
        return
    with open(tags_file, "r", encoding="utf-8") as f:
        tags = [line.strip() for line in f if line.strip()]
    if not tags:
        reply_text = safe_get_messages(user_id).TAGS_NO_TAGS_MSG
        safe_send_message(user_id, reply_text, reply_parameters=ReplyParameters(message_id=message.id))
        send_to_logger(message, reply_text)
        return
    # We form posts by 4096 characters
    msg = ''
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(safe_get_messages(user_id).TAG_CLOSE_BUTTON_MSG, callback_data="tags_close|close")]
    ])
    for tag in tags:
        if len(msg) + len(tag) + 1 > 4096:
            safe_send_message(user_id, msg, reply_parameters=ReplyParameters(message_id=message.id), reply_markup=keyboard)
            send_to_logger(message, msg)
            msg = ''
        msg += tag + '\n'
    if msg:
        safe_send_message(user_id, msg, reply_parameters=ReplyParameters(message_id=message.id), reply_markup=keyboard)
        send_to_logger(message, msg)

@app.on_callback_query(filters.regex(r"^tags_close\|"))
def tags_close_callback(app, callback_query):
    user_id = callback_query.from_user.id
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_close_message_request(callback_envelope, close_scope="tags_close")
    handle_close_message_request(
        app,
        build_callback_execution_context(callback_query),
        request,
        answer_text=safe_get_messages(user_id).TAGS_MESSAGE_CLOSED_MSG,
        log_text=safe_get_messages(user_id).TAGS_MESSAGE_CLOSED_MSG,
    )
