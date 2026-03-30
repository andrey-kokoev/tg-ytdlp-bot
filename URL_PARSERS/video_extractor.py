# URL Extractor
from HELPERS.app_instance import get_app
from HELPERS.limitter import check_playlist_range_limits
from HELPERS.download_status import get_active_download
from HELPERS.logger import send_to_logger, logger
from HELPERS.request_execution import (
    build_message_execution_context,
    clear_user_playlist_error_state,
    determine_url_runtime_decision,
    derive_url_runtime_media_policy,
    handle_saved_format_url_runtime,
    handle_url_quality_menu_runtime,
    send_url_runtime_error,
    send_url_tag_error,
    send_url_wait_download_notice,
)
from CONFIG.messages import safe_get_messages

# Get app instance for decorators
app = get_app()

# Called from url_distractor - no decorator needed
def video_url_extractor(app, message=None, url_request=None, execution_context=None):
    if execution_context is not None and message is None:
        message = execution_context.source_message
    if message is None:
        raise ValueError("video_url_extractor requires a source message or execution context")
    if execution_context is None:
        execution_context = build_message_execution_context(message)
    messages = safe_get_messages(message.chat.id)
    global active_downloads
    user_id = message.chat.id
    full_string = getattr(url_request, "raw_input", None) or message.text
    decision = determine_url_runtime_decision(
        user_id=user_id,
        raw_input=full_string,
        source_message_id=getattr(message, "id", None),
        request=url_request,
        has_active_download=bool(get_active_download(user_id)),
        invalid_input_text=safe_get_messages(user_id).URL_PARSER_USER_ENTERED_INVALID_MSG.format(
            input=full_string,
            error_msg=safe_get_messages(user_id).ERROR1,
        ),
    )
    runtime_request = decision.request

    if decision.mode == "quality_menu":
        logger.info(f"🔍 [DEBUG] video_extractor: full_string='{full_string}'")
        logger.info(
            f"🔍 [DEBUG] video_extractor: after extract_url_range_tags: url='{runtime_request.url}', "
            f"video_start_with={runtime_request.video_start_with}, video_end_with={runtime_request.video_end_with}"
        )
        if decision.tag_error:
            send_url_tag_error(app, execution_context, user_id=user_id, tag_error=decision.tag_error)
            return
        logger.info(
            "🔍 [DEBUG] video_extractor: video_start_with=%s, video_end_with=%s",
            runtime_request.video_start_with,
            runtime_request.video_end_with,
        )
        handle_url_quality_menu_runtime(app, execution_context, runtime_request)
        return

    # This code is executed only if the user has selected a specific format
    if decision.should_clear_playlist_errors:
        clear_user_playlist_error_state(
            user_id=user_id,
            playlist_name=decision.playlist_name_to_clear,
        )

    if decision.mode == "wait_download":
        send_url_wait_download_notice(
            app,
            execution_context,
            user_id=user_id,
            text=safe_get_messages(user_id).VIDEO_EXTRACTOR_WAIT_DOWNLOAD_MSG,
        )
        return

    if decision.mode == "tag_error":
        send_url_tag_error(app, execution_context, user_id=user_id, tag_error=decision.tag_error)
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
    
    if decision.mode == "saved_format":
        users_first_name = message.chat.first_name
        send_to_logger(message, safe_get_messages(user_id).URL_PARSER_USER_ENTERED_URL_LOG_MSG.format(user_name=users_first_name, url=full_string))
        media_policy = derive_url_runtime_media_policy(runtime_request)
        return handle_saved_format_url_runtime(
            app,
            execution_context,
            runtime_request,
            saved_format=decision.saved_format,
            tags=list(media_policy["all_tags"]),
            tags_text=media_policy["tags_text"],
            video_count=media_policy["video_count"],
            force_no_title=media_policy["force_no_title"],
        )

    if decision.mode == "blacklisted":
        send_url_runtime_error(
            execution_context,
            safe_get_messages(user_id).PORN_CONTENT_CANNOT_DOWNLOAD_MSG,
        )
        return

    if decision.mode == "invalid_input":
        send_url_runtime_error(execution_context, decision.error_text)
