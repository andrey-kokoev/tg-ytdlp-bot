import os

from HELPERS.filesystem_hlp import create_directory
from HELPERS.safe_messeger import safe_send_message
from pyrogram import enums
from pyrogram.errors import FloodWait
from pyrogram.types import ReplyParameters


MEDIA_EXTENSIONS_FOR_CLEANUP = (
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
    ".mp4", ".m4v", ".avi", ".mov", ".mkv", ".webm", ".flv",
    ".mp3", ".wav", ".ogg", ".m4a",
    ".pdf", ".doc", ".docx", ".zip", ".rar", ".7z",
)


def ensure_user_download_dir(*, user_id: int, url: str, logger):
    user_dir = os.path.join("users", str(user_id))
    create_directory(user_dir)

    from DOWN_AND_UP.always_ask_menu import get_user_download_dir, generate_download_dir_name

    download_dir = get_user_download_dir(user_id)
    if download_dir and os.path.exists(download_dir):
        return user_dir, download_dir

    try:
        dir_name = generate_download_dir_name(url)
        unique_download_dir = os.path.join(user_dir, "downloads", dir_name)
        os.makedirs(unique_download_dir, exist_ok=True)
        logger.info(f"Created download directory: {unique_download_dir}")
        return user_dir, unique_download_dir
    except Exception as e:
        logger.warning(f"Failed to create download directory, using default: {e}")
        return user_dir, os.path.abspath(os.path.join("users", str(user_id)))


def cleanup_download_dir_before_start(*, download_dir: str, message, logger):
    try:
        logger.info(f"Pre-cleanup: removing old media files from unique directory {download_dir}")
        if os.path.exists(download_dir):
            for root, dirs, files in os.walk(download_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if file.lower().endswith(MEDIA_EXTENSIONS_FOR_CLEANUP):
                            os.remove(file_path)
                            logger.info(f"Pre-cleanup: removed file {file_path}")
                    except Exception as e:
                        logger.warning(f"Pre-cleanup: failed to remove file {file_path}: {e}")

                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if os.path.exists(dir_path) and not os.listdir(dir_path) and dir_path != download_dir:
                            os.rmdir(dir_path)
                            logger.info(f"Pre-cleanup: removed empty directory {dir_path}")
                    except Exception as e:
                        logger.warning(f"Pre-cleanup: failed to remove directory {dir_path}: {e}")

        from HELPERS.filesystem_hlp import is_parallel_download_allowed, create_protection_file

        if is_parallel_download_allowed(message):
            create_protection_file(download_dir)

        logger.info(f"Pre-cleanup completed for unique directory {download_dir}")
    except Exception as e:
        logger.warning(f"Pre-cleanup failed for unique directory {download_dir}: {e}")


def start_processing_handshake(
    *,
    app,
    message,
    user_id: int,
    messages,
    logger,
    on_edit_error=None,
):
    user_dir = os.path.join("users", str(user_id))
    flood_time_file = os.path.join(user_dir, "flood_wait.txt")

    if os.path.exists(flood_time_file):
        with open(flood_time_file, "r") as f:
            wait_time = int(f.read().strip())
        hours = wait_time // 3600
        minutes = (wait_time % 3600) // 60
        seconds = wait_time % 60
        time_str = f"{hours}h {minutes}m {seconds}s"
        proc_msg = safe_send_message(
            user_id,
            messages.RATE_LIMIT_WITH_TIME_MSG.format(time=time_str),
            message=message,
        )
    else:
        proc_msg = safe_send_message(user_id, messages.RATE_LIMIT_NO_TIME_MSG, message=message)

    try:
        app.edit_message_text(
            chat_id=user_id,
            message_id=proc_msg.id,
            text=messages.DOWNLOAD_STARTED_MSG,
            parse_mode=enums.ParseMode.HTML,
        )
        try:
            from HELPERS.safe_messeger import schedule_delete_message

            schedule_delete_message(user_id, proc_msg.id, delete_after_seconds=5)
        except Exception as e:
            logger.error(f"Error scheduling download started message deletion: {e}")
        if os.path.exists(flood_time_file):
            os.remove(flood_time_file)
    except FloodWait as e:
        wait_time = e.value
        os.makedirs(user_dir, exist_ok=True)
        with open(flood_time_file, "w") as f:
            f.write(str(wait_time))
        return None
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        if on_edit_error is not None:
            on_edit_error(e)
        return None

    proc_msg = app.send_message(
        user_id,
        messages.PROCESSING_MSG,
        reply_parameters=ReplyParameters(message_id=message.id),
    )
    try:
        app.pin_chat_message(user_id, proc_msg.id, disable_notification=True)
    except Exception:
        pass

    return {
        "proc_msg": proc_msg,
        "proc_msg_id": proc_msg.id,
        "download_started_msg_id": proc_msg.id,
    }
