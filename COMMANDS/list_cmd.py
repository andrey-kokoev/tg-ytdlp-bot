# ####################################################################################
# List Command - Get available formats for video URL
# ####################################################################################

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from HELPERS.app_instance import get_app
from HELPERS.logger import logger, send_to_user, send_error_to_user
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_command_envelope
from HELPERS.ingress_requests import build_close_message_request, build_list_formats_request
from HELPERS.limitter import is_user_in_channel
from HELPERS.request_execution import (
    build_message_execution_context,
    build_callback_execution_context,
    handle_close_message_request,
    handle_list_formats_request,
)
from HELPERS.safe_messeger import safe_send_message
from HELPERS.decorators import background_handler
from CONFIG.config import Config
from CONFIG.messages import Messages, safe_get_messages
from CONFIG.logger_msg import LoggerMsg
from HELPERS.pot_helper import build_cli_extractor_args
from COMMANDS.proxy_cmd import get_proxy_url

# Get app instance
app = get_app()


@dataclass(frozen=True)
class ListHelpCallbackResultPlan:
    mode: str
    answer_text: str | None = None
    log_text: str | None = None
    show_alert: bool = False

def get_user_cookie_path(user_id: int) -> Optional[str]:
    """Get user's cookie file path if it exists"""
    user_dir = os.path.join("users", str(user_id))
    cookie_file = os.path.join(user_dir, "cookie.txt")
    
    if os.path.exists(cookie_file):
        return cookie_file
    return None

def run_ytdlp_list(url: str, user_id: int) -> tuple[bool, str]:
    """
    Run yt-dlp -F command to get available formats
    Returns (success, output)
    """
    try:
        # Get user's cookie file if available
        cookie_file = get_user_cookie_path(user_id)
        
        # Build command: options BEFORE URL to ensure they apply
        # Use the same yt-dlp as Python API: python -m yt_dlp
        cmd = [sys.executable, "-m", "yt_dlp"]
        # Add PO token extractor-args for CLI if applicable
        cmd.extend(build_cli_extractor_args(url))
        # Verbose for clearer diagnostics
        cmd.extend(["-v", "-F"])
        
        # Respect per-user proxy settings
        proxy_url, proxy_reason = get_proxy_url(user_id=user_id, url=url)
        if proxy_url:
            cmd.extend(["--proxy", proxy_url])
            logger.info(LoggerMsg.LIST_USING_PROXY_LOG_MSG.format(user_id=user_id, proxy_url=proxy_url, reason=proxy_reason or "user"))
        
        if cookie_file:
            cmd.extend(["--cookies", cookie_file])
        # Append URL last
        cmd.append(url)
        
        logger.info(f"Running yt-dlp list command: {' '.join(cmd)}")
        
        # Run command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            error_msg = result.stderr or "Unknown error"
            logger.error(f"yt-dlp list failed: {error_msg}")
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp list command timed out")
        return False, "Command timed out after 60 seconds"
    except Exception as e:
        logger.error(f"Error running yt-dlp list: {e}")
        return False, str(e)

@app.on_message(filters.command("list") & filters.private)
@background_handler(label="list_command")
def list_command(app, message):
    parts = message.text.strip().split(maxsplit=1)
    url = parts[1].strip() if len(parts) >= 2 else None
    envelope = build_telegram_command_envelope(message)
    request = build_list_formats_request(envelope, url=url)
    handle_list_formats_request(app, build_message_execution_context(message), request)


def list_command_logic(app, message, request=None):
    messages = safe_get_messages(message.chat.id)
    """Handle /list command"""
    user_id = message.chat.id
    
    # Subscription check for non-admins
    if int(user_id) not in Config.ADMIN and not is_user_in_channel(app, message):
        return  # is_user_in_channel already sends subscription message
    
    # Parse command arguments
    try:
        url = request.url if request is not None else None
        if not url:
            # Show help message
            help_text = (
safe_get_messages(user_id).LIST_HELP_MSG
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(safe_get_messages(user_id).LIST_CLOSE_BUTTON_MSG, callback_data="list_help|close")
            ]])
            safe_send_message(
                user_id,
                help_text,
                reply_markup=keyboard,
                message=message
            )
            return

        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://")):
            send_error_to_user(message, safe_get_messages(user_id).LIST_INVALID_URL_MSG)
            return
        
        # Send processing message
        processing_msg = safe_send_message(
            user_id,
safe_get_messages(user_id).LIST_PROCESSING_MSG,
            message=message
        )
        
        # Run yt-dlp list command
        success, output = run_ytdlp_list(url, user_id)
        
        if success:
            # Check if any format contains "audio only" and "video only" and extract format IDs
            audio_only_formats = []
            video_only_formats = []
            lines = output.split('\n')
            for line in lines:
                if 'audio only' in line.lower() or 'audio_only' in line.lower():
                    # Extract format ID from the line (usually at the beginning)
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        format_id = parts[0]
                        audio_only_formats.append(format_id)
                elif 'video only' in line.lower() or 'video_only' in line.lower():
                    # Extract format ID from the line (usually at the beginning)
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        format_id = parts[0]
                        video_only_formats.append(format_id)
            
            # Create temporary file with output
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(safe_get_messages(user_id).LIST_AVAILABLE_FORMATS_HEADER_MSG.format(url=url) + "\n")
                temp_file.write("=" * 50 + "\n\n")
                temp_file.write(output)
                temp_file.write("\n\n" + "=" * 50 + "\n")
                temp_file.write(safe_get_messages(user_id).LIST_HOW_TO_USE_FORMAT_IDS_TITLE)
                temp_file.write(safe_get_messages(user_id).LIST_FORMAT_USAGE_INSTRUCTIONS)
                temp_file.write(safe_get_messages(user_id).LIST_FORMAT_EXAMPLE_401)
                temp_file.write(safe_get_messages(user_id).LIST_FORMAT_EXAMPLE_401_SHORT)
                temp_file.write(safe_get_messages(user_id).LIST_FORMAT_EXAMPLE_140_AUDIO)
                temp_file.write(safe_get_messages(user_id).LIST_FORMAT_EXAMPLE_140_AUDIO_SHORT)
                
                # Add special note for audio-only formats
                if audio_only_formats:
                    temp_file.write(f"\n{safe_get_messages(user_id).LIST_AUDIO_FORMATS_DETECTED.format(formats=', '.join(audio_only_formats))}")
                    temp_file.write(safe_get_messages(user_id).LIST_AUDIO_FORMATS_NOTE)
                
                temp_file_path = temp_file.name
            
            try:
                # Send the file
                caption = safe_get_messages(user_id).LIST_CAPTION_MSG.format(url=url, audio_note="")
                
                # Add video-only formats info first
                if video_only_formats:
                    video_formats_text = ', '.join([f'<code>{fmt}</code>' for fmt in video_only_formats])
                    caption += f"\n{safe_get_messages(user_id).LIST_VIDEO_ONLY_FORMATS_MSG.format(formats=video_formats_text)}"
                
                # Add special note for audio-only formats with monospace formatting
                if audio_only_formats:
                    audio_formats_text = ', '.join([f'<code>{fmt}</code>' for fmt in audio_only_formats])
                    caption += safe_get_messages(user_id).LIST_AUDIO_FORMATS_MSG.format(formats=audio_formats_text)
                
                caption += f"\n{safe_get_messages(user_id).LIST_USE_FORMAT_ID_MSG}"
                
                app.send_document(
                    user_id,
                    document=temp_file_path,
                    file_name=safe_get_messages(user_id).LIST_FORMATS_FILE_NAME_MSG.format(user_id=user_id),
                    caption=caption,
                    reply_to_message_id=message.id
                )
                
                # Delete processing message
                try:
                    processing_msg.delete()
                except Exception:
                    pass
                    
            except Exception as e:
                logger.error(f"Error sending formats file: {e}")
                send_error_to_user(message, safe_get_messages(user_id).LIST_ERROR_SENDING_MSG.format(error=str(e)))
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
        else:
            # Delete processing message
            try:
                processing_msg.delete()
            except Exception:
                pass
                
            send_error_to_user(message, safe_get_messages(user_id).LIST_ERROR_GETTING_MSG.format(error=output))
            
    except Exception as e:
        logger.error(f"Error in list command: {e}")
        send_error_to_user(message, safe_get_messages(user_id).LIST_ERROR_OCCURRED_MSG)


def _build_list_help_callback_result_plan(user_id: int, data: str) -> ListHelpCallbackResultPlan:
    if data == "list_help|close":
        return ListHelpCallbackResultPlan(
            mode="close",
            answer_text=safe_get_messages(user_id).HELP_CLOSED_MSG,
            log_text=safe_get_messages(user_id).HELP_CLOSED_MSG,
        )
    return ListHelpCallbackResultPlan(
        mode="error",
        answer_text=safe_get_messages(user_id).LIST_ERROR_CALLBACK_MSG,
        show_alert=True,
    )


def _execute_list_help_callback_result_plan(app, callback_query, plan: ListHelpCallbackResultPlan) -> None:
    if plan.mode == "close":
        callback_envelope = build_telegram_callback_envelope(callback_query)
        request = build_close_message_request(callback_envelope, close_scope="list_help")
        handle_close_message_request(
            app,
            build_callback_execution_context(callback_query),
            request,
            answer_text=plan.answer_text,
            log_text=plan.log_text,
        )
        return
    callback_query.answer(plan.answer_text, show_alert=plan.show_alert)

@app.on_callback_query(filters.regex("^list_help\\|"))
def list_help_callback(app, callback_query):
    user_id = callback_query.from_user.id
    """Handle list help callback"""
    try:
        plan = _build_list_help_callback_result_plan(user_id, callback_query.data)
        _execute_list_help_callback_result_plan(app, callback_query, plan)
    except Exception as e:
        logger.error(LoggerMsg.LIST_ERROR_IN_HELP_CALLBACK_LOG_MSG.format(e=e))
        callback_query.answer(safe_get_messages(user_id).LIST_ERROR_CALLBACK_MSG, show_alert=True)
