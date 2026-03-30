# URL Extractor
from HELPERS.app_instance import get_app
from HELPERS.limitter import check_playlist_range_limits
from HELPERS.download_status import get_active_download
from HELPERS.logger import send_to_logger, send_error_to_user, logger
from HELPERS.request_execution import (
    clear_user_playlist_error_state,
    derive_url_runtime_media_policy,
    handle_saved_format_url_runtime,
    handle_url_quality_menu_runtime,
    is_url_blacklisted,
    normalize_url_download_runtime_request,
    resolve_saved_format_policy,
    send_url_tag_error,
)
from CONFIG.messages import safe_get_messages

# Get app instance for decorators
app = get_app()

# Called from url_distractor - no decorator needed
def video_url_extractor(app, message, url_request=None):
    messages = safe_get_messages(message.chat.id)
    global active_downloads
    user_id = message.chat.id
    full_string = getattr(url_request, "raw_input", None) or message.text
    runtime_request, tag_error = normalize_url_download_runtime_request(
        user_id=user_id,
        source_message_id=getattr(message, "id", None),
        raw_input=full_string,
        request=url_request,
    )
    should_ask, saved_format = resolve_saved_format_policy(user_id=user_id)

    if should_ask:
        logger.info(f"🔍 [DEBUG] video_extractor: full_string='{full_string}'")
        logger.info(
            f"🔍 [DEBUG] video_extractor: after extract_url_range_tags: url='{runtime_request.url}', "
            f"video_start_with={runtime_request.video_start_with}, video_end_with={runtime_request.video_end_with}"
        )
        if tag_error:
            send_url_tag_error(app, message, user_id=user_id, tag_error=tag_error)
            return
        logger.info(
            "🔍 [DEBUG] video_extractor: video_start_with=%s, video_end_with=%s",
            runtime_request.video_start_with,
            runtime_request.video_end_with,
        )
        handle_url_quality_menu_runtime(app, message, runtime_request)
        return

    # This code is executed only if the user has selected a specific format
    clear_user_playlist_error_state(user_id=user_id)
            
    if get_active_download(user_id):
        app.send_message(user_id, safe_get_messages(user_id).VIDEO_EXTRACTOR_WAIT_DOWNLOAD_MSG, reply_parameters=ReplyParameters(message_id=message.id))
        return
        
    if tag_error:
        send_url_tag_error(app, message, user_id=user_id, tag_error=tag_error)
        return
    
    # Checking the range limit
    if not check_playlist_range_limits(
        runtime_request.url,
        runtime_request.video_start_with,
        runtime_request.video_end_with,
        app,
        message,
    ):
        return
    
    if runtime_request.url:
        users_first_name = message.chat.first_name
        send_to_logger(message, safe_get_messages(user_id).URL_PARSER_USER_ENTERED_URL_LOG_MSG.format(user_name=users_first_name, url=full_string))
        if is_url_blacklisted(full_string):
            send_error_to_user(message, safe_get_messages(user_id).PORN_CONTENT_CANNOT_DOWNLOAD_MSG)
            return
        media_policy = derive_url_runtime_media_policy(runtime_request)
        if runtime_request.playlist_name:
            clear_user_playlist_error_state(
                user_id=user_id,
                playlist_name=runtime_request.playlist_name,
            )
        handle_saved_format_url_runtime(
            app,
            message,
            runtime_request,
            saved_format=saved_format,
            tags=list(media_policy["all_tags"]),
            tags_text=media_policy["tags_text"],
            video_count=media_policy["video_count"],
            force_no_title=media_policy["force_no_title"],
        )
    else:
        send_error_to_user(message, safe_get_messages(user_id).URL_PARSER_USER_ENTERED_INVALID_MSG.format(input=full_string, error_msg=safe_get_messages(user_id).ERROR1))
