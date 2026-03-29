from pyrogram import enums
from pyrogram.types import ReplyParameters


def try_repost_single_cached_media(
    *,
    app,
    message,
    user_id: int,
    cached_ids,
    resolve_from_chat_id,
    success_text: str,
    success_log_text: str,
    logger,
    replay_log_prefix: str,
    replay_error_prefix: str,
    on_replay_error,
    send_to_logger,
) -> bool:
    try:
        from_chat_id = resolve_from_chat_id()
        logger.info(
            f"{replay_log_prefix} from channel {from_chat_id} to user {user_id}, "
            f"message_ids={cached_ids}"
        )
        forward_kwargs = {
            "chat_id": user_id,
            "from_chat_id": from_chat_id,
            "message_ids": cached_ids,
        }
        if getattr(message.chat, "type", None) != enums.ChatType.PRIVATE:
            thread_id = getattr(message, "message_thread_id", None)
            if thread_id:
                forward_kwargs["message_thread_id"] = thread_id
        app.forward_messages(**forward_kwargs)
        app.send_message(
            user_id,
            success_text,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        send_to_logger(message, success_log_text)
        return True
    except Exception as e:
        logger.error(f"{replay_error_prefix}: {e}")
        on_replay_error()
        return False


def lookup_single_cached_ids(
    *,
    user_id: int,
    url: str,
    quality_key: str,
    user_forced_nsfw: bool,
    always_ask_enabled: bool,
    is_nsfw_detector,
    get_cached_message_ids,
    logger,
    nsfw_skip_log: str,
    always_ask_skip_log: str,
):
    if always_ask_enabled:
        logger.info(always_ask_skip_log.format(url=url, quality=quality_key))
        return None, None

    is_nsfw = is_nsfw_detector(url, "", "", None) or user_forced_nsfw
    logger.info(
        f"[FALLBACK] is_porn check for {url}: {is_nsfw_detector(url, '', '', None)}, "
        f"user_forced_nsfw: {user_forced_nsfw}, final is_nsfw: {is_nsfw}"
    )
    if is_nsfw:
        logger.info(nsfw_skip_log.format(url=url, quality=quality_key))
        return None, is_nsfw

    return get_cached_message_ids(url, quality_key), is_nsfw
