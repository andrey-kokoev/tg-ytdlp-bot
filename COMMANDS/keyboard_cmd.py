import os
from dataclasses import dataclass

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, ReplyParameters
from pyrogram import enums
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_command_envelope
from HELPERS.ingress_requests import (
    build_close_message_request,
    build_keyboard_command_request,
    build_keyboard_option_selection_request,
)
from HELPERS.logger import send_to_logger
from CONFIG.messages import safe_get_messages
from HELPERS.request_execution import (
    build_callback_execution_context,
    build_message_execution_context,
    handle_close_message_request,
    handle_keyboard_command_request,
    handle_keyboard_option_selection_request,
)
from HELPERS.safe_messeger import safe_send_message, safe_edit_message_text


@dataclass(frozen=True)
class KeyboardCommandContext:
    user_id: str
    chat_id: int
    message_id: int
    command_parts: list[str]
    source_message: object


@dataclass(frozen=True)
class KeyboardCallbackResultPlan:
    mode: str
    setting: str | None = None
    answer_text: str | None = None
    show_alert: bool = False
    edit_text: str | None = None
    log_text: str | None = None


def _build_keyboard_command_context(message) -> KeyboardCommandContext:
    return KeyboardCommandContext(
        user_id=str(message.chat.id),
        chat_id=message.chat.id,
        message_id=message.id,
        command_parts=list(getattr(message, "command", []) or []),
        source_message=message,
    )


def _ensure_keyboard_user_dir(user_dir: str) -> None:
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)


def _keyboard_file_for_user(user_id: str) -> tuple[str, str]:
    user_dir = f"./users/{user_id}"
    return user_dir, os.path.join(user_dir, "keyboard.txt")


def _read_keyboard_setting(keyboard_file: str) -> str:
    current_setting = "2x3"
    if not os.path.exists(keyboard_file):
        return current_setting
    try:
        with open(keyboard_file, "r", encoding="utf-8") as f:
            setting = f.read().strip()
        if setting in ["OFF", "1x3", "2x3", "FULL"]:
            return setting
    except Exception:
        pass
    return current_setting


def _write_keyboard_setting(keyboard_file: str, setting: str) -> None:
    with open(keyboard_file, "w", encoding="utf-8") as f:
        f.write(setting)


def _build_keyboard_settings_markup(user_id: str) -> InlineKeyboardMarkup:
    messages = safe_get_messages(user_id)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(messages.KEYBOARD_OFF_BUTTON_MSG, callback_data="keyboard|OFF"),
            InlineKeyboardButton(messages.KEYBOARD_FULL_BUTTON_MSG, callback_data="keyboard|FULL"),
        ],
        [
            InlineKeyboardButton(messages.KEYBOARD_1X3_BUTTON_MSG, callback_data="keyboard|1x3"),
            InlineKeyboardButton(messages.KEYBOARD_2X3_BUTTON_MSG, callback_data="keyboard|2x3"),
        ],
        [
            InlineKeyboardButton(
                messages.URL_EXTRACTOR_HELP_CLOSE_BUTTON_MSG,
                callback_data="keyboard|close",
            )
        ],
    ])


def _edit_or_send_keyboard_message(source_message, text: str, *, parse_mode=None, reply_markup=None):
    result = safe_edit_message_text(
        source_message.chat.id,
        source_message.id,
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )
    if result is None:
        safe_send_message(
            source_message.chat.id,
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message=source_message,
        )
    return result


def _answer_keyboard_callback(callback_query, text: str, *, show_alert: bool = False) -> None:
    callback_query.answer(text, show_alert=show_alert)


def _send_keyboard_layout_preview(chat_id: int, source_message_id: int | None, user_id: str, setting: str) -> None:
    messages = safe_get_messages(user_id)
    reply_parameters = None
    if source_message_id:
        reply_parameters = ReplyParameters(message_id=source_message_id)
    if setting == "OFF":
        try:
            safe_send_message(
                chat_id,
                messages.KEYBOARD_HIDDEN_MSG,
                reply_markup=ReplyKeyboardRemove(selective=False),
                reply_parameters=reply_parameters,
            )
        except Exception as e:
            from HELPERS.logger import logger
            logger.warning(messages.KEYBOARD_FAILED_HIDE_MSG.format(error=e))
        return
    if setting == "1x3":
        reply_markup = ReplyKeyboardMarkup([["/clean", "/cookie", "/settings"]], resize_keyboard=True)
        text = messages.KEYBOARD_1X3_ACTIVATED_MSG
    elif setting == "2x3":
        reply_markup = ReplyKeyboardMarkup([
            ["/clean", "/cookie", "/settings"],
            ["/playlist", "/search", "/help"],
        ], resize_keyboard=True)
        text = messages.KEYBOARD_2X3_ACTIVATED_MSG
    else:
        reply_markup = ReplyKeyboardMarkup([
            ["🧹", "🍪", "⚙️", "🌐", "🖼", "🔍", "🧰"],
            ["📼", "📊", "✂️", "🎧", "💬", "🌎", "🔞"],
            ["#️⃣", "🆘", "📃", "⏯️", "🎹", "🔗", "🧾"],
        ], resize_keyboard=True)
        text = messages.KEYBOARD_EMOJI_ACTIVATED_MSG
    safe_send_message(
        chat_id,
        text,
        reply_markup=reply_markup,
        reply_parameters=reply_parameters,
    )


def _apply_keyboard_setting_and_preview(chat_id: int, source_message_id: int, user_id: str, setting: str) -> None:
    _send_keyboard_layout_preview(chat_id, source_message_id, user_id, setting)


def _build_keyboard_callback_result_plan(user_id: str, setting: str) -> KeyboardCallbackResultPlan:
    messages = safe_get_messages(user_id)
    if setting == "close":
        return KeyboardCallbackResultPlan(
            mode="close",
            setting="CLOSE",
            answer_text=messages.URL_EXTRACTOR_CLOSED_MSG,
            log_text=messages.KEYBOARD_SET_CALLBACK_LOG_MSG.format(
                user_id=user_id,
                setting="CLOSE",
            ),
        )
    if setting in ["OFF", "1x3", "2x3", "FULL"]:
        return KeyboardCallbackResultPlan(
            mode="apply",
            setting=setting,
            answer_text=messages.KEYBOARD_SET_TO_MSG.format(setting=setting),
            edit_text=messages.KEYBOARD_SETTING_UPDATED_MSG.format(setting=setting),
            log_text=messages.KEYBOARD_SET_CALLBACK_LOG_MSG.format(
                user_id=user_id,
                setting=setting,
            ),
        )
    return KeyboardCallbackResultPlan(
        mode="error",
        setting=setting,
        answer_text=messages.KEYBOARD_ERROR_PROCESSING_MSG,
        show_alert=True,
    )


def _execute_keyboard_callback_result_plan(app, execution_context, callback_query, user_id: str, plan: KeyboardCallbackResultPlan) -> None:
    messages = safe_get_messages(user_id)

    if plan.mode == "close":
        close_request = build_close_message_request(
            build_telegram_callback_envelope(callback_query),
            close_scope="keyboard",
        )
        handle_close_message_request(
            app,
            execution_context,
            close_request,
            answer_text=plan.answer_text,
            log_text=plan.log_text,
        )
        return

    if plan.mode == "error" or plan.setting is None:
        _answer_keyboard_callback(
            callback_query,
            plan.answer_text or messages.KEYBOARD_ERROR_PROCESSING_MSG,
            show_alert=plan.show_alert,
        )
        return

    user_dir, keyboard_file = _keyboard_file_for_user(user_id)
    _ensure_keyboard_user_dir(user_dir)
    _write_keyboard_setting(keyboard_file, plan.setting)
    _edit_or_send_keyboard_message(
        callback_query.message,
        plan.edit_text or messages.KEYBOARD_SETTING_UPDATED_MSG.format(setting=plan.setting),
        parse_mode=enums.ParseMode.MARKDOWN,
    )
    _answer_keyboard_callback(
        callback_query,
        plan.answer_text or messages.KEYBOARD_SET_TO_MSG.format(setting=plan.setting),
    )
    _send_keyboard_layout_preview(
        callback_query.message.chat.id,
        callback_query.message.id,
        user_id,
        plan.setting,
    )
    if plan.log_text:
        send_to_logger(callback_query.message, plan.log_text)


def keyboard_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_keyboard_command_request(envelope)
    handle_keyboard_command_request(app, build_message_execution_context(message), request)


def keyboard_command_logic(app, message, request=None):
    context = _build_keyboard_command_context(message)
    messages = safe_get_messages(context.user_id)
    user_dir, keyboard_file = _keyboard_file_for_user(context.user_id)
    _ensure_keyboard_user_dir(user_dir)

    if len(context.command_parts) > 1:
        arg = context.command_parts[1].lower()
        if arg in ["off", "1x3", "2x3", "full"]:
            setting = arg.upper()
            _write_keyboard_setting(keyboard_file, setting)
            _edit_or_send_keyboard_message(
                context.source_message,
                messages.KEYBOARD_UPDATED_MSG.format(setting=setting),
                parse_mode=enums.ParseMode.MARKDOWN,
            )
            _apply_keyboard_setting_and_preview(
                context.chat_id,
                context.message_id,
                context.user_id,
                setting,
            )
            send_to_logger(
                context.source_message,
                messages.KEYBOARD_SET_LOG_MSG.format(user_id=context.user_id, setting=setting),
            )
            return
        _edit_or_send_keyboard_message(
            context.source_message,
            messages.KEYBOARD_INVALID_ARG_MSG,
            parse_mode=enums.ParseMode.MARKDOWN,
        )
        return

    current_setting = _read_keyboard_setting(keyboard_file)
    _edit_or_send_keyboard_message(
        context.source_message,
        messages.KEYBOARD_SETTINGS_MSG.format(current=current_setting),
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=_build_keyboard_settings_markup(context.user_id),
    )
    safe_send_message(
        context.chat_id,
        messages.KEYBOARD_ACTIVATED_MSG,
        reply_markup=ReplyKeyboardMarkup([
            ["/clean", "/cookie", "/settings"],
            ["/playlist", "/search", "/help"],
        ], resize_keyboard=True),
        message=context.source_message,
    )

def keyboard_callback_handler(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_keyboard_option_selection_request(
        callback_envelope,
        selection_key=callback_query.data.split("|")[1],
    )
    handle_keyboard_option_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def keyboard_callback_logic(app, execution_context, request):
    callback_query = execution_context.callback_query
    user_id = str(callback_query.from_user.id)
    setting = request.selection_key
    try:
        plan = _build_keyboard_callback_result_plan(user_id, setting)
        _execute_keyboard_callback_result_plan(
            app,
            execution_context,
            callback_query,
            user_id,
            plan,
        )
    except Exception as e:
        messages = safe_get_messages(user_id)
        _answer_keyboard_callback(
            callback_query,
            messages.KEYBOARD_ERROR_PROCESSING_MSG,
            show_alert=True,
        )
        from HELPERS.logger import logger
        logger.error(f"Error processing keyboard setting: {e}")

def apply_keyboard_setting(app, chat_id, setting, message_id=None, user_id=None):
    """Apply keyboard setting immediately."""
    try:
        _send_keyboard_layout_preview(chat_id, message_id, user_id, setting)
    except Exception as e:
        from HELPERS.logger import logger
        logger.error(safe_get_messages(user_id).KEYBOARD_ERROR_APPLYING_MSG.format(setting=setting, error=e))
