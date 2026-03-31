# @reply_with_keyboard
from dataclasses import dataclass
import json
import os
import subprocess
import time

from pyrogram import enums
from pyrogram.types import ReplyParameters, InputPaidMediaVideo
from HELPERS.app_instance import get_app
from HELPERS.logger import logger
from HELPERS.download_status import progress_bar
from HELPERS.limitter import TimeFormatter
from HELPERS.caption import truncate_caption
from DOWN_AND_UP.ffmpeg import get_video_info_ffprobe
from URL_PARSERS.thumbnail_downloader import download_thumbnail
from CONFIG.config import Config
from CONFIG.messages import safe_get_messages
from CONFIG.limits import LimitsConfig


@dataclass(frozen=True)
class SenderExecutionContext:
    user_id: int
    source_message: object
    reply_parameters: ReplyParameters
    chat_type: object
    text: str
    is_private_chat: bool


@dataclass(frozen=True)
class SenderDeliveryPlan:
    mode: str
    send_as_paid: bool = False
    send_as_document: bool = False
    timeout_attempts: int = 0
    timeout_log_text: str | None = None


@dataclass(frozen=True)
class SenderDeliveryOutcomePlan:
    mode: str
    result_kind: str
    log_text: str | None = None


@dataclass(frozen=True)
class SenderCaptionFallbackPlan:
    mode: str
    timeout_attempts: int
    use_minimal_caption: bool
    send_as_document: bool
    timeout_log_text: str | None = None


@dataclass(frozen=True)
class SenderDescriptionArtifactPlan:
    mode: str
    should_send: bool
    should_cleanup: bool


def _build_sender_execution_context(message) -> SenderExecutionContext:
    chat_type = getattr(message.chat, "type", None)
    return SenderExecutionContext(
        user_id=message.chat.id,
        source_message=message,
        reply_parameters=ReplyParameters(message_id=message.id),
        chat_type=chat_type,
        text=message.text or "",
        is_private_chat=(chat_type == enums.ChatType.PRIVATE),
    )


def _send_paid_video_media(
    *,
    sender_context: SenderExecutionContext,
    media_path: str,
    duration: int,
    width: int | None,
    height: int | None,
    cover_path: str | None,
):
    try:
        safe_paid_dur = float(duration) if duration and float(duration) > 0 else 1.0
    except Exception:
        safe_paid_dur = 1.0
    try:
        safe_w = int(width) if width and int(width) > 0 else 640
    except Exception:
        safe_w = 640
    try:
        safe_h = int(height) if height and int(height) > 0 else 360
    except Exception:
        safe_h = 360

    try:
        paid_media = InputPaidMediaVideo(
            media=media_path,
            cover=cover_path,
            width=safe_w,
            height=safe_h,
            duration=safe_paid_dur,
            supports_streaming=True,
        )
    except TypeError:
        paid_media = InputPaidMediaVideo(media=media_path)

    allow_broadcast = sender_context.chat_type != enums.ChatType.PRIVATE
    result = app.send_paid_media(
        chat_id=sender_context.user_id,
        media=[paid_media],
        star_count=LimitsConfig.NSFW_STAR_COST,
        **({"allow_paid_broadcast": True} if allow_broadcast else {}),
        payload=str(Config.STAR_RECEIVER),
        reply_parameters=sender_context.reply_parameters,
    )
    try:
        return result[0] if isinstance(result, list) and result else result
    except Exception:
        return result


def _send_regular_video_media(
    *,
    sender_context: SenderExecutionContext,
    media_path: str,
    caption_text: str,
    duration: int,
    width: int | None,
    height: int | None,
    thumb_path: str | None,
    info_text: str,
    progress_message_id: int,
):
    return app.send_video(
        chat_id=sender_context.user_id,
        video=media_path,
        caption=caption_text,
        duration=int(duration) if duration else None,
        width=int(width) if width else None,
        height=int(height) if height else None,
        supports_streaming=True,
        thumb=thumb_path,
        has_spoiler=False,
        progress=progress_bar,
        progress_args=(
            sender_context.user_id,
            progress_message_id,
            f"{info_text}\n<b>{safe_get_messages(sender_context.user_id).SENDER_VIDEO_DURATION_MSG}</b> <i>{TimeFormatter(duration*1000)}</i>\n\n<i>{safe_get_messages(sender_context.user_id).SENDER_UPLOADING_VIDEO_MSG}</i>"
        ),
        reply_parameters=sender_context.reply_parameters,
        parse_mode=enums.ParseMode.HTML,
    )


def _send_document_media(
    *,
    sender_context: SenderExecutionContext,
    media_path: str,
    caption_text: str,
    thumb_path: str | None,
    info_text: str,
    progress_message_id: int,
    duration: int,
):
    return app.send_document(
        chat_id=sender_context.user_id,
        document=media_path,
        file_name=os.path.basename(media_path),
        caption=caption_text,
        thumb=thumb_path,
        progress=progress_bar,
        progress_args=(
            sender_context.user_id,
            progress_message_id,
            f"{info_text}\n<b>{safe_get_messages(sender_context.user_id).SENDER_VIDEO_DURATION_MSG}</b> <i>{TimeFormatter(duration*1000)}</i>\n\n<i>{safe_get_messages(sender_context.user_id).SENDER_UPLOADING_FILE_MSG}</i>"
        ),
        reply_parameters=sender_context.reply_parameters,
        parse_mode=enums.ParseMode.HTML,
    )


def _send_description_document(
    *,
    sender_context: SenderExecutionContext,
    description_path: str,
):
    return app.send_document(
        chat_id=sender_context.user_id,
        document=description_path,
        caption=safe_get_messages(sender_context.user_id).CHANGE_CAPTION_HINT_MSG,
        reply_parameters=sender_context.reply_parameters,
        parse_mode=enums.ParseMode.HTML,
    )


def _build_sender_description_artifact_plan(*, was_truncated: bool, temp_desc_path: str) -> SenderDescriptionArtifactPlan:
    return SenderDescriptionArtifactPlan(
        mode="send_and_cleanup" if was_truncated and os.path.exists(temp_desc_path) else "skip",
        should_send=was_truncated and os.path.exists(temp_desc_path),
        should_cleanup=True,
    )


def _execute_sender_description_artifact_plan(
    *,
    plan: SenderDescriptionArtifactPlan,
    sender_context: SenderExecutionContext,
    temp_desc_path: str,
    message,
) -> None:
    if plan.should_send:
        try:
            _send_description_document(
                sender_context=sender_context,
                description_path=temp_desc_path,
            )
        except Exception as e:
            logger.error(safe_get_messages(sender_context.user_id).SENDER_ERROR_SENDING_FULL_DESCRIPTION_FILE_MSG.format(error=e))
            from HELPERS.logger import send_error_to_user
            send_error_to_user(message, safe_get_messages(sender_context.user_id).ERROR_SENDING_DESCRIPTION_FILE_MSG.format(error=str(e)))
    if plan.should_cleanup and os.path.exists(temp_desc_path):
        try:
            os.remove(temp_desc_path)
        except Exception as e:
            logger.error(safe_get_messages(sender_context.user_id).SENDER_ERROR_REMOVING_TEMP_DESCRIPTION_FILE_MSG.format(error=e))


def _is_timeout_error(exc: Exception) -> bool:
    return "Request timed out" in str(exc) or isinstance(exc, TimeoutError)


def _send_with_timeout_fallback(
    *,
    primary_send,
    fallback_send,
    attempts: int,
    timeout_log_text: str,
):
    attempts_left = attempts
    while True:
        try:
            return primary_send()
        except Exception as exc:
            if not _is_timeout_error(exc):
                raise
            attempts_left -= 1
            if attempts_left <= 0:
                logger.warning(timeout_log_text)
                return fallback_send()
            time.sleep(2)


def _build_sender_delivery_plan(
    *,
    is_private_chat: bool,
    is_spoiler: bool,
    send_as_file: bool,
    caption_too_long: bool,
    timeout_attempts: int = 3,
) -> SenderDeliveryPlan:
    if is_spoiler and is_private_chat:
        return SenderDeliveryPlan(mode="paid", send_as_paid=True)
    if send_as_file:
        return SenderDeliveryPlan(mode="document", send_as_document=True)
    if caption_too_long:
        return SenderDeliveryPlan(mode="caption_fallback", timeout_attempts=max(1, timeout_attempts - 1))
    return SenderDeliveryPlan(mode="video", timeout_attempts=timeout_attempts)


def _build_sender_delivery_outcome_plan(mode: str, *, log_text: str | None = None) -> SenderDeliveryOutcomePlan:
    if mode == "paid":
        return SenderDeliveryOutcomePlan(mode=mode, result_kind="paid", log_text=log_text)
    if mode == "document":
        return SenderDeliveryOutcomePlan(mode=mode, result_kind="document", log_text=log_text)
    if mode == "video":
        return SenderDeliveryOutcomePlan(mode=mode, result_kind="video", log_text=log_text)
    return SenderDeliveryOutcomePlan(mode=mode, result_kind=mode, log_text=log_text)


def _build_sender_caption_fallback_plan(
    *,
    sender_context: SenderExecutionContext,
    is_spoiler: bool,
    send_as_file: bool,
    caption_too_long: bool,
    timeout_attempts: int,
) -> SenderCaptionFallbackPlan:
    delivery_plan = _build_sender_delivery_plan(
        is_private_chat=sender_context.is_private_chat,
        is_spoiler=is_spoiler,
        send_as_file=send_as_file,
        caption_too_long=caption_too_long,
        timeout_attempts=timeout_attempts,
    )
    return SenderCaptionFallbackPlan(
        mode=delivery_plan.mode,
        timeout_attempts=delivery_plan.timeout_attempts,
        use_minimal_caption=caption_too_long,
        send_as_document=delivery_plan.send_as_document,
        timeout_log_text=delivery_plan.timeout_log_text,
    )


def _execute_sender_caption_fallback(
    *,
    sender_context: SenderExecutionContext,
    is_spoiler: bool,
    send_as_file: bool,
    user_id: int,
    timeout_attempts: int,
    minimal_caption: str,
    send_video_fn,
    send_document_fn,
) -> object:
    caption_fallback_plan = _build_sender_caption_fallback_plan(
        sender_context=sender_context,
        is_spoiler=is_spoiler,
        send_as_file=send_as_file,
        caption_too_long=True,
        timeout_attempts=timeout_attempts,
    )
    if caption_fallback_plan.send_as_document:
        return send_document_fn(minimal_caption)
    try:
        return _send_with_timeout_fallback(
            primary_send=lambda: send_video_fn(minimal_caption),
            fallback_send=lambda: send_document_fn(minimal_caption),
            attempts=caption_fallback_plan.timeout_attempts,
            timeout_log_text=caption_fallback_plan.timeout_log_text
            or safe_get_messages(user_id).SENDER_SEND_VIDEO_MINIMAL_CAPTION_TIMED_OUT_MSG,
        )
    except Exception as e:
        logger.error(safe_get_messages(user_id).SENDER_ERROR_SENDING_VIDEO_MINIMAL_CAPTION_MSG.format(error=e))
        final_plan = _build_sender_caption_fallback_plan(
            sender_context=sender_context,
            is_spoiler=is_spoiler,
            send_as_file=send_as_file,
            caption_too_long=True,
            timeout_attempts=1,
        )
        if final_plan.send_as_document:
            return send_document_fn("")
        try:
            return send_video_fn("")
        except Exception as e3:
            if _is_timeout_error(e3):
                return send_document_fn("")
            raise

# Get app instance for decorators
app = get_app()

# Import function to get user args
def get_user_args(user_id: int):
    """Get user's saved args settings"""
    messages = safe_get_messages(user_id)
    import os
    import json
    user_dir = os.path.join("users", str(user_id))
    args_file = os.path.join(user_dir, "args.txt")
    
    if not os.path.exists(args_file):
        return {}
    
    try:
        with open(args_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(safe_get_messages(user_id).SENDER_ERROR_READING_USER_ARGS_MSG.format(user_id=user_id, error=e))
        return {}

def send_videos(
    message,
    video_abs_path: str,
    caption: str,
    duration: int,
    thumb_file_path: str,
    info_text: str,
    msg_id: int,
    full_video_title: str,
    tags_text: str = '',
):
    import re
    sender_context = _build_sender_execution_context(message)
    user_id = sender_context.user_id
    messages = safe_get_messages(user_id)
    text = sender_context.text
    m = re.search(r'https?://[^\s\*]+', text)
    video_url = m.group(0) if m else ""
    temp_desc_path = os.path.join(os.path.dirname(video_abs_path), "full_description.txt")
    was_truncated = False
    
    # Check if user has send_as_file enabled
    user_args = get_user_args(user_id)
    send_as_file = user_args.get("send_as_file", False)

    # --- Define the size of the preview/video ---
    width = None
    height = None
    if video_url and ("youtube.com" in video_url or "youtu.be" in video_url):
        if "youtube.com/shorts/" in video_url or "/shorts/" in video_url:
            width, height = 360, 640
        else:
            width, height = 640, 360
    else:
        # For the rest - define the size of the video dynamically
        try:
            width, height, _ = get_video_info_ffprobe(video_abs_path)
        except Exception as e:
            logger.error(safe_get_messages(user_id).SENDER_FFPROBE_BYPASS_ERROR_MSG.format(video_path=video_abs_path, error=e))
            import traceback
            logger.error(traceback.format_exc())
            width, height = 0, 0

    try:
        # Logic simplified: use tags that were already generated in down_and_up.
        # Use original title for caption, but truncated description
        title_html, pre_block, blockquote_content, tags_block, link_block, was_truncated = truncate_caption(
            title=caption,  # Original title for caption
            description=full_video_title,  # Full description to be truncated
            url=video_url,
            tags_text=tags_text, # Use final tags for calculation
            max_length=1000,  # Reduced for safety
            user_id=user_id
        )
        # Define spoiler flag for porn-tagged content
        try:
            is_spoiler = bool(re.search(r"(?i)(?:^|\s)#nsfw(?:\s|$)", tags_text or ""))
        except Exception:
            is_spoiler = False
        # Flag: whether it was sent as paid media
        was_paid = False
        # Form HTML caption: title outside the quote, timecodes outside the quote, description in the quote, tags and link outside the quote
        cap = ''
        if title_html:
            cap += title_html + '\n\n'
        if pre_block:
            cap += pre_block + '\n'
        cap += f'<blockquote expandable>{blockquote_content}</blockquote>\n'
        if tags_block:
            cap += tags_block
        cap += link_block

        def _should_generate_cover(video_path: str, duration_seconds: int) -> bool:
            try:
                size_mb = os.path.getsize(video_path) / (1024 * 1024)
            except Exception:
                size_mb = 0.0
            try:
                dur = float(duration_seconds or 0)
            except Exception:
                dur = 0.0
            # Generate unless both duration<60 and size<10
            return (dur >= 60.0) or (size_mb >= 10.0)

        def _gen_thumb(video_path: str) -> str | None:
            try:
                if not _should_generate_cover(video_path, duration):
                    return None
                base_dir = os.path.dirname(video_path)
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                thumb_path = os.path.join(base_dir, base_name + '.__tgthumb.jpg')
                if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                    return thumb_path
                middle_sec = max(1, int(duration) // 2 if isinstance(duration, int) else 1)
                subprocess.run([
                    'ffmpeg','-y','-ss', str(middle_sec), '-i', video_abs_path,
                    '-vframes','1','-vf','scale=320:-1', thumb_path
                ], capture_output=True, text=True, timeout=30)
                return thumb_path if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0 else None
            except Exception:
                return None

        def _resize_to_cover(src_path: str, dest_path: str) -> bool:
            try:
                subprocess.run([
                    'ffmpeg','-y','-i', src_path,
                    '-vf','scale=if(gte(a,1),320,-2):if(gte(a,1),-2,320),pad=320:320:(320-iw)/2:(320-ih)/2:color=black',
                    '-vframes','1','-q:v','4', dest_path
                ], capture_output=True, text=True, timeout=30)
                return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
            except Exception:
                return False

        def _gen_paid_cover(video_path: str) -> str | None:
            try:
                if not _should_generate_cover(video_path, duration):
                    return None
                base_dir = os.path.dirname(video_path)
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                cover_path = os.path.join(base_dir, base_name + '.__tgcover_paid.jpg')
                if os.path.exists(cover_path) and os.path.getsize(cover_path) > 0:
                    return cover_path
                # 1) Try downloading an external thumbnail (preferred)
                try:
                    tmp_dl = os.path.join(base_dir, base_name + '.__ext_thumb.jpg')
                    if video_url:
                        if download_thumbnail(video_url, tmp_dl):
                            if _resize_to_cover(tmp_dl, cover_path):
                                try:
                                    if os.path.exists(tmp_dl):
                                        os.remove(tmp_dl)
                                except Exception:
                                    pass
                                return cover_path
                    # Remove temporary file if it still exists
                    try:
                        if os.path.exists(tmp_dl):
                            os.remove(tmp_dl)
                    except Exception:
                        pass
                except Exception:
                    pass
                # 2) Fallback: extract a video frame, then resize to the target size without padding (preserving aspect ratio)
                try:
                    tmp_frame = os.path.join(base_dir, base_name + '.__frame.jpg')
                    middle_sec = max(1, int(duration) // 2 if isinstance(duration, int) else 1)
                    subprocess.run([
                        'ffmpeg','-y','-ss', str(middle_sec), '-i', video_path,
                        '-vframes','1','-q:v','4', tmp_frame
                    ], capture_output=True, text=True, timeout=30)
                    if os.path.exists(tmp_frame) and os.path.getsize(tmp_frame) > 0:
                        if _resize_to_cover(tmp_frame, cover_path):
                            try:
                                if os.path.exists(tmp_frame):
                                    os.remove(tmp_frame)
                            except Exception:
                                pass
                            return cover_path
                    try:
                        if os.path.exists(tmp_frame):
                            os.remove(tmp_frame)
                    except Exception:
                        pass
                except Exception:
                    pass
                return cover_path if os.path.exists(cover_path) and os.path.getsize(cover_path) > 0 else None
            except Exception:
                return None

        def _resize_to_thumb_free(src_path: str, dest_path: str) -> bool:
            try:
                subprocess.run([
                    'ffmpeg','-y','-i', src_path,
                    '-vf','scale=320:-1',
                    '-vframes','1','-q:v','4', dest_path
                ], capture_output=True, text=True, timeout=30)
                return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
            except Exception:
                return False

        def _gen_free_cover(video_path: str) -> str | None:
            try:
                # Generate thumbnail only if file >10MB or duration >=60s
                if not _should_generate_cover(video_path, duration):
                    return None
                base_dir = os.path.dirname(video_path)
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                cover_path = os.path.join(base_dir, base_name + '.__tgthumb_ext.jpg')
                if os.path.exists(cover_path) and os.path.getsize(cover_path) > 0:
                    return cover_path
                # 1) Try downloading an external thumbnail (no padding, scale width to 640)
                try:
                    tmp_dl = os.path.join(base_dir, base_name + '.__ext_thumb.jpg')
                    if video_url and download_thumbnail(video_url, tmp_dl):
                        if _resize_to_thumb_free(tmp_dl, cover_path):
                            try:
                                if os.path.exists(tmp_dl):
                                    os.remove(tmp_dl)
                            except Exception:
                                pass
                            return cover_path
                    try:
                        if os.path.exists(tmp_dl):
                            os.remove(tmp_dl)
                    except Exception:
                        pass
                except Exception:
                    pass
                # 2) Fallback: extract a frame from the video (as before)
                return _gen_thumb(video_path)
            except Exception:
                return _gen_thumb(video_path)

        def _try_send_video(caption_text: str):
            nonlocal was_paid
            # For free messages: external preview without padding; for paid: 320x320 cover
            local_thumb_free = _gen_free_cover(video_abs_path)
            # Paid media only in private chats; in groups/channels send regular video
            delivery_plan = _build_sender_delivery_plan(
                is_private_chat=sender_context.is_private_chat,
                is_spoiler=is_spoiler,
                send_as_file=send_as_file,
                caption_too_long=False,
                timeout_attempts=3,
            )
            if delivery_plan.send_as_paid:
                try:
                    v_w, v_h, v_dur = get_video_info_ffprobe(video_abs_path)
                except Exception:
                    v_w, v_h, v_dur = width, height, duration
                was_paid = True
                return _send_paid_video_media(
                    sender_context=sender_context,
                    media_path=video_abs_path,
                    duration=v_dur or duration,
                    width=v_w or width,
                    height=v_h or height,
                    cover_path=_gen_paid_cover(video_abs_path),
                )
            # For free media, also keep correct metadata and thumbnail
            try:
                v_w2, v_h2, v_dur2 = get_video_info_ffprobe(video_abs_path)
            except Exception:
                v_w2, v_h2, v_dur2 = width, height, duration
            result = _send_regular_video_media(
                sender_context=sender_context,
                media_path=video_abs_path,
                caption_text=caption_text,
                duration=int(v_dur2) if v_dur2 else duration,
                width=int(v_w2) if v_w2 else width,
                height=int(v_h2) if v_h2 else height,
                thumb_path=local_thumb_free,
                info_text=info_text,
                progress_message_id=msg_id,
            )
            # Cleanup special thumb (free-only temp files)
            try:
                if local_thumb_free and (
                    local_thumb_free.endswith('.__tgthumb.jpg') or local_thumb_free.endswith('.__tgthumb_ext.jpg')
                ) and os.path.exists(local_thumb_free):
                    os.remove(local_thumb_free)
            except Exception:
                pass
            return result

        def _fallback_send_document(caption_text: str):
            nonlocal was_paid
            # For free documents: external preview without padding
            local_thumb = _gen_free_cover(video_abs_path) or thumb_file_path
            try:
                if not local_thumb or not os.path.exists(local_thumb):
                    local_thumb = os.path.join(os.path.dirname(video_abs_path), os.path.splitext(os.path.basename(video_abs_path))[0] + ".jpg")
                    import subprocess
                    try:
                        middle_sec = max(1, int(duration) // 2 if isinstance(duration, int) else 1)
                        subprocess.run([
                            'ffmpeg','-y','-ss', str(middle_sec), '-i', video_abs_path,
                            '-vframes','1','-vf','scale=320:-1', local_thumb
                        ], capture_output=True, text=True, timeout=30)
                        if not os.path.exists(local_thumb):
                            local_thumb = None
                    except Exception:
                        local_thumb = None
            except Exception:
                local_thumb = thumb_file_path
            delivery_plan = _build_sender_delivery_plan(
                is_private_chat=sender_context.is_private_chat,
                is_spoiler=is_spoiler,
                send_as_file=True,
                caption_too_long=False,
                timeout_attempts=3,
            )
            if delivery_plan.send_as_paid:
                try:
                    v_w, v_h, v_dur = get_video_info_ffprobe(video_abs_path)
                except Exception:
                    v_w, v_h, v_dur = width, height, duration
                was_paid = True
                return _send_paid_video_media(
                    sender_context=sender_context,
                    media_path=video_abs_path,
                    duration=v_dur or duration,
                    width=v_w or width,
                    height=v_h or height,
                    cover_path=_gen_paid_cover(video_abs_path),
                )
            result = _send_document_media(
                sender_context=sender_context,
                media_path=video_abs_path,
                caption_text=caption_text,
                thumb_path=local_thumb,
                info_text=info_text,
                progress_message_id=msg_id,
                duration=duration,
            )
            # Cleanup special thumb
            try:
                if local_thumb and (local_thumb.endswith('.__tgthumb.jpg') or local_thumb.endswith('.__tgcover_paid.jpg')) and os.path.exists(local_thumb):
                    os.remove(local_thumb)
            except Exception:
                pass
            return result

        try:
            # Check if user wants to send as file
            delivery_plan = _build_sender_delivery_plan(
                is_private_chat=sender_context.is_private_chat,
                is_spoiler=is_spoiler,
                send_as_file=send_as_file,
                caption_too_long=False,
                timeout_attempts=3,
            )
            if delivery_plan.send_as_document:
                logger.info(safe_get_messages(user_id).SENDER_USER_SEND_AS_FILE_ENABLED_MSG.format(user_id=user_id))
                video_msg = _fallback_send_document(cap)
            else:
                video_msg = _send_with_timeout_fallback(
                    primary_send=lambda: _try_send_video(cap),
                    fallback_send=lambda: _fallback_send_document(cap),
                    attempts=delivery_plan.timeout_attempts,
                    timeout_log_text=delivery_plan.timeout_log_text
                    or safe_get_messages(user_id).SENDER_SEND_VIDEO_TIMED_OUT_MSG,
                )
        except Exception as e:
            if "MEDIA_CAPTION_TOO_LONG" in str(e):
                logger.info(safe_get_messages(user_id).SENDER_CAPTION_TOO_LONG_MSG)
                # If the caption is too long, try sending only with the main information
                minimal_cap = ''
                if title_html:
                    minimal_cap += title_html + '\n\n'
                minimal_cap += link_block
                video_msg = _execute_sender_caption_fallback(
                    sender_context=sender_context,
                    is_spoiler=is_spoiler,
                    send_as_file=send_as_file,
                    user_id=user_id,
                    timeout_attempts=2,
                    minimal_caption=minimal_cap,
                    send_video_fn=_try_send_video,
                    send_document_fn=_fallback_send_document,
                )
            else:
                # If the error is not related to the length of the caption, log it and pass it further
                from HELPERS.logger import send_error_to_user
                send_error_to_user(message, safe_get_messages(user_id).ERROR_SENDING_VIDEO_MSG.format(error=str(e)))
                raise e
        # Note: Forwarding to log channels is now handled in down_and_up.py
        # to avoid double forwarding and ensure proper channel routing

        if was_truncated and full_video_title:
            with open(temp_desc_path, "w", encoding="utf-8") as f:
                f.write(full_video_title)
        _execute_sender_description_artifact_plan(
            plan=_build_sender_description_artifact_plan(
                was_truncated=was_truncated,
                temp_desc_path=temp_desc_path,
            ),
            sender_context=sender_context,
            temp_desc_path=temp_desc_path,
            message=message,
        )
        return video_msg
    finally:
        if os.path.exists(temp_desc_path):
            try:
                os.remove(temp_desc_path)
            except Exception as e:
                logger.error(safe_get_messages(user_id).SENDER_ERROR_REMOVING_TEMP_DESCRIPTION_FILE_MSG.format(error=e))
                # This is not critical enough to log to LOG_EXCEPTION channel

#####################################################################################
