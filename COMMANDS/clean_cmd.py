from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import enums

from HELPERS.app_instance import get_app
from HELPERS.message_bridge import bridge_message_from_existing
from HELPERS.logger import logger, send_to_all
from CONFIG.logger_msg import LoggerMsg, get_logger_msg
from CONFIG.messages import Messages, safe_get_messages
from CONFIG.config import Config
from HELPERS.filesystem_hlp import remove_media
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_command_envelope
from HELPERS.ingress_requests import build_clean_command_request, build_clean_option_selection_request
from HELPERS.request_execution import (
    build_callback_execution_context,
    build_message_execution_context,
    handle_clean_command_request,
    handle_clean_option_selection_request,
)

# Get app instance for decorators
app = get_app()


def _clear_clean_caches(chat_id: int) -> None:
    from COMMANDS.subtitles_cmd import clear_subs_check_cache
    from COMMANDS.cookies_cmd import clear_youtube_cookie_cache

    try:
        clear_youtube_cookie_cache(chat_id)
    except Exception as e:
        logger.error(LoggerMsg.URL_EXTRACTOR_FAILED_CLEAR_YOUTUBE_CACHE_LOG_MSG.format(e=e))

    clear_subs_check_cache()


def _scan_and_remove_recursive(path, *, prefix="", protected_files=None):
    import os
    import shutil

    items = []
    protected_files = set(protected_files or [])
    try:
        if os.path.isfile(path):
            if os.path.basename(path) not in protected_files:
                os.remove(path)
                items.append(f"{prefix}📄 {os.path.basename(path)}")
                logger.info(LoggerMsg.URL_EXTRACTOR_REMOVED_FILE_LOG_MSG.format(file_path=path))
        elif os.path.isdir(path):
            dir_items = []
            try:
                for subitem in os.listdir(path):
                    subitem_path = os.path.join(path, subitem)
                    sub_items = _scan_and_remove_recursive(
                        subitem_path,
                        prefix=prefix + "  ",
                        protected_files=protected_files,
                    )
                    dir_items.extend(sub_items)
            except Exception as e:
                logger.error(get_logger_msg().URL_EXTRACTOR_ERROR_SCANNING_DIRECTORY_LOG_MSG.format(path=path, e=e))

            shutil.rmtree(path)
            items.append(f"{prefix}📁 {os.path.basename(path)}/")
            items.extend(dir_items)
            logger.info(get_logger_msg().URL_EXTRACTOR_REMOVED_DIRECTORY_LOG_MSG.format(path=path))
    except Exception as e:
        logger.error(LoggerMsg.URL_EXTRACTOR_FAILED_REMOVE_FILE_LOG_MSG.format(file_path=path, e=e))
    return items


def _render_removed_items(message, user_id: int, removed_items: list[str]) -> None:
    if removed_items:
        from HELPERS.text_helper import format_clean_output_as_html

        items_list = "\n".join([f"• {item}" for item in removed_items])
        formatted_output = format_clean_output_as_html(items_list, user_id)
        send_to_all(message, formatted_output, parse_mode=enums.ParseMode.HTML)
    else:
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_NO_FILES_TO_REMOVE_MSG)


def clean_command(app, message):
    envelope = build_telegram_command_envelope(message)
    request = build_clean_command_request(envelope)
    execution_context = build_message_execution_context(message)
    handle_clean_command_request(app, execution_context, request)


def clean_command_logic(app, message, request=None):
    import os

    user_id = message.chat.id
    text = (message.text or "").strip()
    clean_args = text[len(Config.CLEAN_COMMAND):].strip().lower() if text.startswith(Config.CLEAN_COMMAND) else ""

    if clean_args in ["cookie", "cookies"]:
        remove_media(message, only=["cookie.txt"])
        try:
            from COMMANDS.cookies_cmd import clear_youtube_cookie_cache
            clear_youtube_cookie_cache(message.chat.id)
        except Exception as e:
            logger.error(LoggerMsg.URL_EXTRACTOR_FAILED_CLEAR_YOUTUBE_CACHE_LOG_MSG.format(e=e))
        send_to_all(message, safe_get_messages(user_id).COOKIE_FILE_REMOVED_CACHE_CLEARED_MSG)
        return
    if clean_args in ["log", "logs"]:
        remove_media(message, only=["logs.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_LOGS_FILE_REMOVED_MSG)
        return
    if clean_args in ["tag", "tags"]:
        remove_media(message, only=["tags.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_TAGS_FILE_REMOVED_MSG)
        return
    if clean_args == "format":
        remove_media(message, only=["format.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_FORMAT_FILE_REMOVED_MSG)
        return
    if clean_args == "split":
        remove_media(message, only=["split.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_SPLIT_FILE_REMOVED_MSG)
        return
    if clean_args == "mediainfo":
        remove_media(message, only=["mediainfo.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_MEDIAINFO_FILE_REMOVED_MSG)
        return
    if clean_args == "subs":
        remove_media(message, only=["subs.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_SUBS_SETTINGS_REMOVED_MSG)
        from COMMANDS.subtitles_cmd import clear_subs_check_cache
        clear_subs_check_cache()
        return
    if clean_args == "keyboard":
        remove_media(message, only=["keyboard.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_KEYBOARD_SETTINGS_REMOVED_MSG)
        return
    if clean_args == "args":
        remove_media(message, only=["args.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_ARGS_SETTINGS_REMOVED_MSG)
        return
    if clean_args == "nsfw":
        remove_media(message, only=["nsfw_blur.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_NSFW_SETTINGS_REMOVED_MSG)
        return
    if clean_args == "proxy":
        remove_media(message, only=["proxy.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_PROXY_SETTINGS_REMOVED_MSG)
        return
    if clean_args == "flood_wait":
        remove_media(message, only=["flood_wait.txt"])
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_CLEAN_FLOOD_WAIT_SETTINGS_REMOVED_MSG)
        return

    user_dir = f"./users/{str(message.chat.id)}"
    if not os.path.exists(user_dir):
        send_to_all(message, safe_get_messages(user_id).URL_EXTRACTOR_NO_FILES_TO_REMOVE_MSG)
        from COMMANDS.subtitles_cmd import clear_subs_check_cache
        clear_subs_check_cache()
        return

    removed_items = []
    allitems = os.listdir(user_dir)

    if clean_args == "all":
        for item in allitems:
            item_path = os.path.join(user_dir, item)
            removed_items.extend(_scan_and_remove_recursive(item_path))
        try:
            from COMMANDS.cookies_cmd import clear_youtube_cookie_cache
            clear_youtube_cookie_cache(message.chat.id)
        except Exception as e:
            logger.error(LoggerMsg.URL_EXTRACTOR_FAILED_CLEAR_YOUTUBE_CACHE_LOG_MSG.format(e=e))
        _render_removed_items(message, user_id, removed_items)
        return

    protected_files = {"keyboard.txt", "tags.txt", "logs.txt", "lang.txt"}
    for item in allitems:
        if item not in protected_files:
            item_path = os.path.join(user_dir, item)
            removed_items.extend(_scan_and_remove_recursive(item_path, protected_files=protected_files))

    _clear_clean_caches(message.chat.id)
    _render_removed_items(message, user_id, removed_items)
    return

@app.on_callback_query(filters.regex(r"^clean_option\|"))
# @reply_with_keyboard
def clean_option_callback(app, callback_query):
    callback_envelope = build_telegram_callback_envelope(callback_query)
    request = build_clean_option_selection_request(
        callback_envelope,
        action_key=callback_query.data.split("|")[1],
    )
    handle_clean_option_selection_request(
        app,
        build_callback_execution_context(callback_query),
        request,
    )


def clean_option_callback_logic(app, callback_query, request):
    # Get user_id first
    user_id = getattr(callback_query, 'from_user', None)
    if user_id is None:
        user_id = getattr(callback_query, 'user', None)
    if user_id is None:
        return
    user_id = getattr(user_id, 'id', None)
    if user_id is None:
        return
    
    messages = safe_get_messages(user_id)
    def _bridged_command_message(text: str):
        return bridge_message_from_existing(callback_query.message, text)
    data = request.action_key

    if data == "cookies":
        clean_command(app, _bridged_command_message("/clean cookie"))
        callback_query.answer(messages.CLEAN_COOKIES_CLEANED_MSG)
        return
    elif data == "logs":
        clean_command(app, _bridged_command_message("/clean logs"))
        callback_query.answer(messages.CLEAN_LOGS_CLEANED_MSG)
        return
    elif data == "tags":
        clean_command(app, _bridged_command_message("/clean tags"))
        callback_query.answer(messages.CLEAN_TAGS_CLEANED_MSG)
        return
    elif data == "format":
        clean_command(app, _bridged_command_message("/clean format"))
        callback_query.answer(messages.CLEAN_FORMAT_CLEANED_MSG)
        return
    elif data == "split":
        clean_command(app, _bridged_command_message("/clean split"))
        callback_query.answer(messages.CLEAN_SPLIT_CLEANED_MSG)
        return
    elif data == "mediainfo":
        clean_command(app, _bridged_command_message("/clean mediainfo"))
        callback_query.answer(messages.CLEAN_MEDIAINFO_CLEANED_MSG)
        return
    elif data == "subs":
        clean_command(app, _bridged_command_message("/clean subs"))
        callback_query.answer(messages.CLEAN_SUBS_CLEANED_MSG)
        return
    elif data == "keyboard":
        clean_command(app, _bridged_command_message("/clean keyboard"))
        callback_query.answer(messages.CLEAN_KEYBOARD_CLEANED_MSG)
        return
    elif data == "args":
        clean_command(app, _bridged_command_message("/clean args"))
        callback_query.answer(messages.CLEAN_ARGS_CLEANED_MSG)
        return
    elif data == "nsfw":
        clean_command(app, _bridged_command_message("/clean nsfw"))
        callback_query.answer(messages.CLEAN_NSFW_CLEANED_MSG)
        return
    elif data == "proxy":
        clean_command(app, _bridged_command_message("/clean proxy"))
        callback_query.answer(messages.CLEAN_PROXY_CLEANED_MSG)
        return
    elif data == "flood_wait":
        clean_command(app, _bridged_command_message("/clean flood_wait"))
        callback_query.answer(messages.CLEAN_FLOOD_WAIT_CLEANED_MSG)
        return
    elif data == "all":
        clean_command(app, _bridged_command_message("/clean all"))
        callback_query.answer(messages.CLEAN_ALL_CLEANED_MSG)
        return
    elif data == "back":
        # Back to the cookies menu
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(messages.CLEAN_COOKIE_DOWNLOAD_BUTTON_MSG,
                                  callback_data="settings__cmd__download_cookie")],
            [InlineKeyboardButton(messages.CLEAN_COOKIES_FROM_BROWSER_BUTTON_MSG,
                                  callback_data="settings__cmd__cookies_from_browser")],
            [InlineKeyboardButton(messages.CLEAN_CHECK_COOKIE_BUTTON_MSG,
                                  callback_data="settings__cmd__check_cookie")],
            [InlineKeyboardButton(messages.CLEAN_SAVE_AS_COOKIE_BUTTON_MSG,
                                  callback_data="settings__cmd__save_as_cookie")],
            [InlineKeyboardButton("🔙Back", callback_data="settings__menu__back")]
        ])
        callback_query.edit_message_text(
            messages.CLEAN_COOKIES_MENU_TITLE_MSG,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        callback_query.answer()
        return
