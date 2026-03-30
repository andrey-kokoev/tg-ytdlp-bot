# Search Command Module
# This module handles the /search command to activate inline search via @vid bot

from dataclasses import dataclass

from HELPERS.app_instance import get_app
from HELPERS.ingress_models import (
    build_telegram_callback_envelope,
    build_telegram_command_envelope,
)
from HELPERS.ingress_requests import (
    build_close_message_request,
    build_search_command_request,
)
from HELPERS.logger import send_to_logger
from CONFIG.logger_msg import LoggerMsg
from CONFIG.messages import safe_get_messages
from HELPERS.request_execution import (
    build_callback_execution_context,
    build_message_execution_context,
    handle_close_message_request,
    handle_search_command_request,
)
from HELPERS.safe_messeger import safe_send_message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import enums, filters

# Get app instance
app = get_app()


@dataclass(frozen=True)
class SearchCommandContext:
    user_id: int
    source_message: object


def _build_search_command_context(message) -> SearchCommandContext:
    return SearchCommandContext(
        user_id=message.chat.id,
        source_message=message,
    )


def _build_search_keyboard(user_id: int) -> InlineKeyboardMarkup:
    bot_name = Config.BOT_NAME
    messages = safe_get_messages(user_id)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                messages.SEARCH_MOBILE_ACTIVATE_SEARCH_MSG,
                url=f"tg://msg?text=%40vid%20%E2%80%8B&to=%40{bot_name}"
            )
        ],
        [
            InlineKeyboardButton(
                messages.SEARCH_CLOSE_BUTTON_MSG,
                callback_data="search_msg|close"
            )
        ]
    ])

def search_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_search_command_request(envelope)
    handle_search_command_request(app, build_message_execution_context(message), request)


def search_command_logic(app, message, request=None):
    context = _build_search_command_context(message)
    messages = safe_get_messages(context.user_id)
    safe_send_message(
        context.user_id,
        messages.SEARCH_MSG,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=_build_search_keyboard(context.user_id),
        message=context.source_message
    )

    send_to_logger(context.source_message, LoggerMsg.SEARCH_HELPER_OPENED.format(user_id=context.user_id))

# Callback handler for search command buttons
@app.on_callback_query(filters.regex(r"^search_msg\|"))
def handle_search_callback(client, callback_query):
    user_id = callback_query.from_user.id
    try:
        data = callback_query.data
        
        if data == "search_msg|close":
            callback_envelope = build_telegram_callback_envelope(callback_query)
            request = build_close_message_request(callback_envelope, close_scope="search_msg")
            handle_close_message_request(
                client,
                build_callback_execution_context(callback_query),
                request,
                answer_text=safe_get_messages(user_id).SEARCH_CLOSED_MSG,
                log_text=LoggerMsg.SEARCH_HELPER_CLOSED.format(user_id=user_id),
            )
            
    except Exception as e:
        send_to_logger(callback_query.message, LoggerMsg.SEARCH_CALLBACK_ERROR.format(error=e))
        callback_query.answer(safe_get_messages(user_id).ERROR_OCCURRED_SHORT_MSG, show_alert=True)
