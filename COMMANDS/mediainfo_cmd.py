import os
import subprocess
from dataclasses import dataclass

from pyrogram import filters
from CONFIG.config import Config
from CONFIG.messages import safe_get_messages
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters

from HELPERS.app_instance import get_app
from HELPERS.ingress_models import (
    build_telegram_callback_envelope,
    build_telegram_command_envelope,
)
from HELPERS.ingress_requests import (
    build_close_message_request,
    build_mediainfo_command_request,
    build_mediainfo_option_selection_request,
)
from HELPERS.filesystem_hlp import create_directory
from HELPERS.logger import send_to_logger, logger, send_error_to_user
from HELPERS.request_execution import (
    build_callback_execution_context,
    build_message_execution_context,
    handle_close_message_request,
    handle_mediainfo_command_request,
    handle_mediainfo_option_selection_request,
)
from HELPERS.safe_messeger import safe_send_message, safe_edit_message_text
from HELPERS.decorators import background_handler
from HELPERS.limitter import is_user_in_channel

# Get app instance for decorators
app = get_app()


@dataclass(frozen=True)
class MediaInfoCommandContext:
    user_id: int
    source_message: object
    command_parts: list[str]


@dataclass(frozen=True)
class MediaInfoCallbackResultPlan:
    mode: str
    enabled: bool | None = None
    answer_text: str | None = None
    edit_text: str | None = None
    log_text: str | None = None


def _build_mediainfo_command_context(message) -> MediaInfoCommandContext:
    return MediaInfoCommandContext(
        user_id=message.chat.id,
        source_message=message,
        command_parts=[str(part) for part in (message.text or "").split()],
    )


def _mediainfo_file_path(user_id: int) -> str:
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)
    return os.path.join(user_dir, "mediainfo.txt")


def _write_mediainfo_setting(user_id: int, enabled: bool) -> str:
    mediainfo_file = _mediainfo_file_path(user_id)
    with open(mediainfo_file, "w", encoding="utf-8") as f:
        f.write("ON" if enabled else "OFF")
    return mediainfo_file


def _build_mediainfo_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    messages = safe_get_messages(user_id)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(messages.MEDIAINFO_ON_BUTTON_MSG, callback_data="mediainfo_option|on"),
            InlineKeyboardButton(messages.MEDIAINFO_OFF_BUTTON_MSG, callback_data="mediainfo_option|off"),
        ],
        [
            InlineKeyboardButton(
                messages.MEDIAINFO_CLOSE_BUTTON_MSG,
                callback_data="mediainfo_option|close",
            )
        ],
    ])


def _answer_mediainfo_callback(callback_query, text: str | None = None) -> None:
    if text is None:
        callback_query.answer()
        return
    callback_query.answer(text)


def _edit_mediainfo_callback_message(callback_query, text: str) -> None:
    safe_edit_message_text(callback_query.message.chat.id, callback_query.message.id, text)


def _build_mediainfo_callback_result_plan(user_id: int, selection_key: str) -> MediaInfoCallbackResultPlan:
    messages = safe_get_messages(user_id)
    if selection_key == "close":
        return MediaInfoCallbackResultPlan(
            mode="close",
            answer_text=messages.MEDIAINFO_MENU_CLOSED_MSG,
            log_text=messages.MEDIAINFO_MENU_CLOSED_LOG_MSG,
        )
    if selection_key == "on":
        return MediaInfoCallbackResultPlan(
            mode="apply",
            enabled=True,
            answer_text=messages.MEDIAINFO_ENABLED_CALLBACK_MSG,
            edit_text=messages.MEDIAINFO_ENABLED_CONFIRM_MSG,
            log_text=messages.MEDIAINFO_ENABLED_LOG_MSG,
        )
    if selection_key == "off":
        return MediaInfoCallbackResultPlan(
            mode="apply",
            enabled=False,
            answer_text=messages.MEDIAINFO_DISABLED_CALLBACK_MSG,
            edit_text=messages.MEDIAINFO_DISABLED_MSG,
            log_text=messages.MEDIAINFO_DISABLED_LOG_MSG,
        )
    return MediaInfoCallbackResultPlan(mode="noop")


def _execute_mediainfo_callback_result_plan(app, execution_context, callback_query, user_id: int, plan: MediaInfoCallbackResultPlan) -> None:
    if plan.mode == "close":
        close_request = build_close_message_request(
            build_telegram_callback_envelope(callback_query),
            close_scope="mediainfo_option",
        )
        handle_close_message_request(
            app,
            execution_context,
            close_request,
            answer_text=plan.answer_text or "",
            log_text=plan.log_text or "",
        )
        return

    if plan.mode == "apply" and plan.enabled is not None:
        _write_mediainfo_setting(user_id, plan.enabled)
        if plan.edit_text:
            _edit_mediainfo_callback_message(callback_query, plan.edit_text)
        if plan.log_text:
            send_to_logger(callback_query.message, plan.log_text)
        if plan.answer_text:
            try:
                _answer_mediainfo_callback(callback_query, plan.answer_text)
            except Exception:
                pass

@app.on_message(filters.command("mediainfo") & filters.private)
# @reply_with_keyboard
@background_handler(label="mediainfo_command")
def mediainfo_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_mediainfo_command_request(envelope)
    handle_mediainfo_command_request(app, build_message_execution_context(message), request)


def mediainfo_command_logic(app, message, request=None):
    context = _build_mediainfo_command_context(message)
    messages = safe_get_messages(context.user_id)
    logger.info(messages.MEDIAINFO_USER_REQUESTED_MSG.format(user_id=context.user_id))
    logger.info(messages.MEDIAINFO_USER_IS_ADMIN_MSG.format(user_id=context.user_id, is_admin=int(context.user_id) in Config.ADMIN))

    is_in_channel = is_user_in_channel(app, context.source_message)
    logger.info(messages.MEDIAINFO_USER_IS_IN_CHANNEL_MSG.format(user_id=context.user_id, is_in_channel=is_in_channel))

    if int(context.user_id) not in Config.ADMIN and not is_in_channel:
        logger.info(messages.MEDIAINFO_ACCESS_DENIED_MSG.format(user_id=context.user_id))
        return

    logger.info(messages.MEDIAINFO_ACCESS_GRANTED_MSG.format(user_id=context.user_id))
    try:
        if len(context.command_parts) >= 2:
            arg = context.command_parts[1].lower()
            if arg in ("on", "off"):
                _write_mediainfo_setting(context.user_id, arg == "on")
                safe_send_message(
                    context.user_id,
                    messages.MEDIAINFO_ENABLED_MSG.format(status='enabled' if arg == 'on' else 'disabled'),
                    message=context.source_message,
                )
                send_to_logger(context.source_message, messages.MEDIAINFO_SET_COMMAND_LOG_MSG.format(arg=arg))
                return
    except Exception:
        pass

    safe_send_message(
        context.user_id,
        messages.MEDIAINFO_MENU_TITLE_MSG,
        reply_markup=_build_mediainfo_menu_keyboard(context.user_id),
        message=context.source_message,
    )
    send_to_logger(context.source_message, messages.MEDIAINFO_MENU_OPENED_LOG_MSG)


@app.on_callback_query(filters.regex(r"^mediainfo_option\|"))
# @reply_with_keyboard
def mediainfo_option_callback(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_mediainfo_option_selection_request(
        callback_envelope,
        selection_key=callback_query.data.split("|")[1],
    )
    handle_mediainfo_option_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def mediainfo_option_callback_logic(app, execution_context, request):
    callback_query = execution_context.callback_query
    user_id = callback_query.from_user.id
    messages = safe_get_messages(user_id)
    logger.info(messages.MEDIAINFO_CALLBACK_MSG.format(callback_data=callback_query.data))
    plan = _build_mediainfo_callback_result_plan(user_id, request.selection_key)
    _execute_mediainfo_callback_result_plan(
        app,
        execution_context,
        callback_query,
        user_id,
        plan,
    )


def is_mediainfo_enabled(user_id):
    mediainfo_file = _mediainfo_file_path(user_id)
    if not os.path.exists(mediainfo_file):
        return False
    try:
        with open(mediainfo_file, "r", encoding="utf-8") as f:
            return f.read().strip().upper() == "ON"
    except Exception:
        return False


def get_mediainfo_cli(file_path):
    try:
        result = subprocess.run(
            ["mediainfo", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except Exception as e:
        logger.error(f"mediainfo CLI error: {e}")
        return "MediaInfo CLI error: " + str(e)


def send_mediainfo_if_enabled(user_id, file_path, message):
    messages = safe_get_messages(user_id)
    if is_mediainfo_enabled(user_id):
        try:
            # Extract msg_id safely
            msg_id = message.id if hasattr(message, "id") else message.get("message_id") or message.get("id")

            mediainfo_text = get_mediainfo_cli(file_path)
            # Remove any absolute paths from mediainfo output for security
            mediainfo_text = mediainfo_text.replace(os.path.abspath("users"), "users")
            mediainfo_path = os.path.splitext(file_path)[0] + "_mediainfo.txt"

            with open(mediainfo_path, "w", encoding="utf-8") as f:
                f.write(mediainfo_text)

            app.send_document(user_id, mediainfo_path, caption=safe_get_messages(user_id).MEDIAINFO_DOCUMENT_CAPTION_MSG,
                              reply_parameters=ReplyParameters(message_id=msg_id))
            # MediaInfo files are no longer sent to log channel to avoid polluting video cache
            # from HELPERS.logger import get_log_channel
            # app.send_document(get_log_channel("video"), mediainfo_path,
            #                   caption=f"<blockquote>📊 MediaInfo</blockquote> for user {user_id}")

            if os.path.exists(mediainfo_path):
                os.remove(mediainfo_path)

        except Exception as e:
            logger.error(f"Error MediaInfo: {e}")
            send_error_to_user(message, safe_get_messages(user_id).MEDIAINFO_ERROR_SENDING_MSG.format(error=e))
