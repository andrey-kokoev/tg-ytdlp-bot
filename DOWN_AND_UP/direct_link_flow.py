from pyrogram import enums
from pyrogram.types import ReplyParameters

from CONFIG.messages import safe_get_messages


def direct_link_quality_arg(quality_key: str | None) -> str | None:
    if quality_key and quality_key not in {"best", "mp3"}:
        return quality_key
    return None


def send_standard_direct_link_response(app, message, user_id: int, result: dict) -> None:
    messages = safe_get_messages(user_id)
    if result.get("success"):
        title = result.get("title", "Unknown")
        duration = result.get("duration", 0)
        video_url = result.get("video_url")
        audio_url = result.get("audio_url")
        format_spec = result.get("format", "best")

        response = messages.DIRECT_LINK_OBTAINED_MSG
        response += messages.TITLE_FIELD_MSG.format(title=title)
        try:
            duration_val = float(duration) if duration is not None else 0
            if duration_val > 0:
                response += messages.DURATION_FIELD_MSG.format(duration=duration_val)
        except (TypeError, ValueError):
            pass
        response += messages.FORMAT_FIELD_MSG.format(format_spec=format_spec)

        if video_url:
            response += messages.VIDEO_STREAM_FIELD_MSG.format(video_url=video_url)
        if audio_url:
            response += messages.AUDIO_STREAM_FIELD_MSG.format(audio_url=audio_url)
        if not video_url and not audio_url:
            response += messages.DOWN_UP_FAILED_STREAM_LINKS_MSG

        app.send_message(
            user_id,
            response,
            reply_parameters=ReplyParameters(message_id=message.id),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    error_msg = result.get("error", "Unknown error")
    app.send_message(
        user_id,
        messages.DOWN_UP_ERROR_GETTING_LINK_MSG.format(error_msg=error_msg),
        reply_parameters=ReplyParameters(message_id=message.id),
        parse_mode=enums.ParseMode.HTML,
    )


def send_always_ask_direct_link_response(app, message, user_id: int, result: dict) -> None:
    messages = safe_get_messages(user_id)
    if result.get("success"):
        title = result.get("title", "Unknown")
        duration = result.get("duration", 0)
        video_url = result.get("video_url")
        audio_url = result.get("audio_url")
        format_spec = result.get("format", "best")

        response = f"{messages.ALWAYS_ASK_DIRECT_LINK_OBTAINED_MSG}\n\n"
        response += f"{messages.ALWAYS_ASK_TITLE_MSG} {title}\n"
        try:
            duration_val = float(duration) if duration is not None else 0
            if duration_val > 0:
                response += f"{messages.ALWAYS_ASK_DURATION_SEC_MSG} {duration_val:g} sec\n"
        except (TypeError, ValueError):
            pass
        response += f"{messages.ALWAYS_ASK_FORMAT_CODE_MSG} <code>{format_spec}</code>\n\n"

        if video_url:
            response += (
                f"{messages.ALWAYS_ASK_VIDEO_STREAM_MSG}\n"
                f"<blockquote expandable><a href=\"{video_url}\">{video_url}</a></blockquote>\n\n"
            )
        if audio_url:
            response += (
                f"{messages.ALWAYS_ASK_AUDIO_STREAM_MSG}\n"
                f"<blockquote expandable><a href=\"{audio_url}\">{audio_url}</a></blockquote>\n\n"
            )
        if not video_url and not audio_url:
            response += messages.ALWAYS_ASK_FAILED_TO_GET_STREAM_LINKS_MSG

        app.send_message(
            user_id,
            response,
            reply_parameters=ReplyParameters(message_id=message.id),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    error_msg = result.get("error", "Unknown error")
    app.send_message(
        user_id,
        f"❌ <b>Error getting link:</b>\n{error_msg}",
        reply_parameters=ReplyParameters(message_id=message.id),
        parse_mode=enums.ParseMode.HTML,
    )


def send_always_ask_direct_link_response_legacy_error(app, message, user_id: int, result: dict) -> None:
    messages = safe_get_messages(user_id)
    if result.get("success"):
        send_always_ask_direct_link_response(app, message, user_id, result)
        return

    error_msg = result.get("error", "Unknown error")
    app.send_message(
        user_id,
        messages.AA_ERROR_GETTING_LINK_MSG.format(error_msg=error_msg),
        reply_parameters=ReplyParameters(message_id=message.id),
        parse_mode=enums.ParseMode.HTML,
    )


def execute_direct_link_flow(
    *,
    fetch_direct_link,
    response_sender,
    app,
    message,
    user_id: int,
    url: str,
    quality_key: str | None,
    cookies_already_checked: bool,
    use_proxy: bool,
) -> dict:
    result = fetch_direct_link(
        url,
        user_id,
        direct_link_quality_arg(quality_key),
        cookies_already_checked=cookies_already_checked,
        use_proxy=use_proxy,
    )
    response_sender(app, message, user_id, result)
    return result
