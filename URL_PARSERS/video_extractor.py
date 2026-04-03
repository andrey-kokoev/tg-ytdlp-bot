# URL Extractor
from HELPERS.app_instance import get_app
from HELPERS.download_status import get_active_download
from HELPERS.logger import logger
from HELPERS.request_execution import (
    build_url_runtime_execution_plan,
    build_message_execution_context,
    determine_url_runtime_decision,
    execute_url_runtime_plan,
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
    plan = build_url_runtime_execution_plan(decision)
    return execute_url_runtime_plan(
        app,
        execution_context,
        user_id=user_id,
        raw_input=full_string,
        plan=plan,
    )
