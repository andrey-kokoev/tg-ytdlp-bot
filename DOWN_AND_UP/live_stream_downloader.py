# Live Stream Downloader
# Downloads live streams in chunks and sends them immediately

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any
import yt_dlp
import time
from datetime import datetime
from CONFIG.limits import LimitsConfig
from CONFIG.messages import safe_get_messages
from HELPERS.logger import logger
from DOWN_AND_UP.sender import send_videos
from DOWN_AND_UP.ffmpeg import (
    FfmpegExecutionContext,
    _build_ffmpeg_execution_context,
    get_duration_thumb,
    get_video_info_ffprobe,
)
from DOWN_AND_UP.runtime_task import RuntimeTask
from DOWN_AND_UP.task_plan_executor import execute_completion_plan


@dataclass(frozen=True)
class LiveStreamExecutionContext:
    user_id: int
    source_message: object
    proc_msg_id: int
    current_total_process: str
    ffmpeg_context: FfmpegExecutionContext | None


@dataclass(frozen=True)
class LiveStreamCompletionPlan:
    mode: str
    should_emit_final_status: bool
    successful_chunks: int


def _build_live_stream_execution_context(
    *,
    message,
    user_id: int,
    proc_msg_id: int,
    current_total_process: str,
) -> LiveStreamExecutionContext:
    return LiveStreamExecutionContext(
        user_id=user_id,
        source_message=message,
        proc_msg_id=proc_msg_id,
        current_total_process=current_total_process,
        ffmpeg_context=_build_ffmpeg_execution_context(message),
    )


def _emit_live_stream_progress(
    execution_context: LiveStreamExecutionContext,
    *,
    chunk_idx: int,
    max_chunks: int,
    split_hours: int,
) -> None:
    from HELPERS.safe_messeger import safe_edit_message_text

    progress_text = (
        f"{execution_context.current_total_process}\n"
        f"📡 <b>Live Stream Download</b>\n"
        f"Chunk {chunk_idx + 1}/{max_chunks}\n"
        f"Duration: {split_hours} hour(s) per chunk"
    )
    safe_edit_message_text(execution_context.user_id, execution_context.proc_msg_id, progress_text)


def _emit_live_stream_final_status(
    execution_context: LiveStreamExecutionContext,
    *,
    successful_chunks: int,
) -> None:
    from HELPERS.safe_messeger import safe_edit_message_text

    final_text = (
        f"{execution_context.current_total_process}\n"
        f"✅ <b>Live Stream Download Complete</b>\n"
        f"Downloaded {successful_chunks} chunk(s)"
    )
    safe_edit_message_text(execution_context.user_id, execution_context.proc_msg_id, final_text)


def _send_live_stream_chunk(
    execution_context: LiveStreamExecutionContext,
    *,
    chunk_file: str,
    chunk_caption: str,
    duration: int,
    thumb_file: str,
    chunk_idx: int,
    max_chunks: int,
    video_title: str,
    tags_text: str,
):
    return send_videos(
        execution_context.source_message,
        chunk_file,
        chunk_caption,
        duration,
        thumb_file or "",
        f"Chunk {chunk_idx + 1}/{max_chunks}",
        execution_context.proc_msg_id,
        f"{video_title} - Chunk {chunk_idx + 1}",
        tags_text,
    )


def _execute_live_stream_chunk(
    *,
    app,
    message,
    execution_context: LiveStreamExecutionContext,
    base_opts: dict,
    url: str,
    user_dir_name: str,
    date_str: str,
    safe_channel: str,
    safe_title: str,
    split_hours: int,
    segment_time: int,
    max_chunks: int,
    chunk_idx: int,
    video_title: str,
    tags_text: str,
) -> bool:
    chunk_opts = base_opts.copy()
    chunk_filename = f"{date_str}_{safe_channel}_{safe_title}_{chunk_idx:03d}.ts"
    chunk_file = os.path.join(user_dir_name, chunk_filename)
    chunk_opts["outtmpl"] = chunk_file.replace(".ts", ".%(ext)s")

    segment_hours = int(segment_time / 3600)
    segment_minutes = int((segment_time % 3600) / 60)
    segment_seconds = int(segment_time % 60)
    chunk_opts["downloader_args"] = {
        "ffmpeg_i": f"-t {segment_hours:02d}:{segment_minutes:02d}:{segment_seconds:02d}",
        "ffmpeg_o": "-f mpegts",
    }

    with yt_dlp.YoutubeDL(chunk_opts) as ydl:
        ydl.download([url])

    if not os.path.exists(chunk_file):
        import glob
        chunk_pattern = os.path.join(
            user_dir_name,
            f"{date_str}_{safe_channel}_{safe_title}_{chunk_idx:03d}.*",
        )
        chunk_files = glob.glob(chunk_pattern)
        if chunk_files:
            chunk_file = chunk_files[0]
        else:
            logger.warning(f"Could not find chunk file for index {chunk_idx}")
            return False

    if not os.path.exists(chunk_file):
        logger.warning(f"Chunk file not found: {chunk_file}")
        return False

    try:
        _, _, duration = get_video_info_ffprobe(chunk_file)
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        duration = segment_time

    thumb_file = None
    try:
        thumb_name = f"{safe_title}_chunk_{chunk_idx:03d}"
        result = get_duration_thumb(
            message,
            user_dir_name,
            chunk_file,
            thumb_name,
            execution_context=execution_context.ffmpeg_context,
        )
        if result:
            duration_from_thumb, thumb_file = result
            if duration_from_thumb:
                duration = duration_from_thumb
    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        thumb_path = os.path.join(user_dir_name, f"{safe_title}.jpg")
        if os.path.exists(thumb_path):
            thumb_file = thumb_path

    chunk_caption = f"📡 <b>Live Stream - Chunk {chunk_idx + 1}/{max_chunks}</b>\n"
    chunk_caption += f"⏱ Duration: {split_hours} hour(s)\n"
    if tags_text:
        chunk_caption += f"\n{tags_text}"

    logger.info(f"Sending chunk {chunk_idx + 1} to user: {chunk_file}")
    chunk_msg = _send_live_stream_chunk(
        execution_context,
        chunk_file=chunk_file,
        chunk_caption=chunk_caption,
        duration=int(duration) if duration else segment_time,
        thumb_file=thumb_file or "",
        chunk_idx=chunk_idx,
        max_chunks=max_chunks,
        video_title=video_title,
        tags_text=tags_text,
    )
    if chunk_msg:
        logger.info(f"Successfully sent chunk {chunk_idx + 1}")
        return True

    logger.warning(f"Failed to send chunk {chunk_idx + 1}")
    return False


def _build_live_stream_completion_plan(*, successful_chunks: int) -> LiveStreamCompletionPlan:
    return LiveStreamCompletionPlan(
        mode="final",
        should_emit_final_status=True,
        successful_chunks=successful_chunks,
    )


def _execute_live_stream_completion_plan_core(
    execution_context: LiveStreamExecutionContext,
    *,
    plan: LiveStreamCompletionPlan,
) -> dict[str, Any]:
    """
    Core logic for executing LiveStreamCompletionPlan.
    Returns execution result summary for evidence recording.
    """
    result = {
        "final_status_emitted": False,
        "successful_chunks": plan.successful_chunks,
    }

    if not plan.should_emit_final_status:
        return result

    _emit_live_stream_final_status(
        execution_context,
        successful_chunks=plan.successful_chunks,
    )
    result["final_status_emitted"] = True

    return result


def _execute_live_stream_completion_plan(
    execution_context: LiveStreamExecutionContext,
    *,
    plan: LiveStreamCompletionPlan,
) -> None:
    """Legacy executor - for backward compatibility."""
    _execute_live_stream_completion_plan_core(
        execution_context,
        plan=plan,
    )


def _execute_live_stream_completion_plan_with_evidence(
    execution_context: LiveStreamExecutionContext,
    *,
    plan: LiveStreamCompletionPlan,
    task_context: RuntimeTask | None,
) -> tuple[dict[str, Any], RuntimeTask | None]:
    """
    PDA-refactored executor using TaskPlanExecutor.
    Returns (execution_result, updated_task) with execution evidence recorded.
    """
    if task_context is None:
        result = _execute_live_stream_completion_plan_core(
            execution_context,
            plan=plan,
        )
        return result, task_context

    def _executor(p: LiveStreamCompletionPlan) -> dict[str, Any]:
        return _execute_live_stream_completion_plan_core(
            execution_context,
            plan=p,
        )

    new_task, result = execute_completion_plan(
        task_context,
        plan,
        _executor,
        executor_name="_execute_live_stream_completion_plan",
    )
    return result, new_task


def download_live_stream_chunked(
    app, message, url, user_id, user_dir_name, info_dict, 
    proc_msg_id, current_total_process, tags_text="", 
    cookies_already_checked=False, use_proxy=False,
    format_override=None, quality_key=None
):
    """
    Download live stream in chunks and send each chunk immediately.
    
    Args:
        app: Pyrogram app instance
        message: Telegram message object
        url: Live stream URL
        user_id: User ID
        user_dir_name: Directory for downloads
        info_dict: Video info dict from yt-dlp
        proc_msg_id: Progress message ID
        current_total_process: Progress text
        tags_text: Tags text
        cookies_already_checked: Whether cookies were already checked
        use_proxy: Whether to use proxy
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        execution_context = _build_live_stream_execution_context(
            message=message,
            user_id=user_id,
            proc_msg_id=proc_msg_id,
            current_total_process=current_total_process,
        )
        # Get configuration
        split_hours = LimitsConfig.SPLIT_LIVE_STREAM_BY_HOURS
        max_duration = LimitsConfig.MAX_LIVE_STREAM_DURATION
        max_chunks = int(max_duration / (split_hours * 3600))
        
        logger.info(f"Starting live stream download: url={url}, split_hours={split_hours}, max_duration={max_duration}s, max_chunks={max_chunks}")
        
        # Get video title for filename
        video_title = info_dict.get('title', 'live_stream')
        if not video_title or video_title == 'live_stream':
            # Try to get channel name
            channel = info_dict.get('channel', 'live')
            video_title = f"{channel}_live_stream"
        
        # Sanitize title
        from HELPERS.filesystem_hlp import sanitize_filename_strict
        safe_title = sanitize_filename_strict(video_title)
        
        # Get upload date for filename
        upload_date = info_dict.get('upload_date')
        if upload_date:
            try:
                # Parse YYYYMMDD format
                date_obj = datetime.strptime(upload_date, '%Y%m%d')
                date_str = date_obj.strftime('%Y-%m-%d')
            except:
                date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Get channel name
        channel = info_dict.get('channel', 'live')
        safe_channel = sanitize_filename_strict(channel)
        
        # Prepare base yt-dlp options
        base_opts = {
            'live_from_start': True,  # Start from beginning when DVR is available
            'concurrent_fragment_downloads': 4,  # -N 4
            'retries': float('inf'),  # -R infinite
            'fragment_retries': float('inf'),  # --fragment-retries infinite
            'retry_sleep': 'fragment:exp=1:30',  # --retry-sleep fragment:exp=1:30
            'continue_dl': True,  # --continue
            'noverwrites': True,  # --no-overwrites
            'hls_prefer_ffmpeg': True,  # --hls-prefer-ffmpeg
            'hls_use_mpegts': True,  # --hls-use-mpegts
            'downloader': 'ffmpeg',  # --downloader ffmpeg
            'quiet': False,
            'no_warnings': False,
        }
        
        # Add user's custom yt-dlp arguments from /args command
        from COMMANDS.args_cmd import get_user_ytdlp_args, log_ytdlp_options
        user_args = get_user_ytdlp_args(user_id, url)
        if user_args:
            # Update base_opts with user args, but preserve live stream specific settings
            # Don't override critical live stream options
            preserved_keys = {
                'live_from_start', 'concurrent_fragment_downloads', 'retries', 
                'fragment_retries', 'retry_sleep', 'continue_dl', 'noverwrites',
                'hls_prefer_ffmpeg', 'hls_use_mpegts', 'downloader', 'downloader_args'
            }
            for key, value in user_args.items():
                if key not in preserved_keys:
                    base_opts[key] = value
                    logger.info(f"Applied user arg for live stream: {key} = {value}")
        
        # Apply format_override if provided (from always_ask_menu or /format)
        if format_override:
            base_opts['format'] = format_override
            logger.info(f"Applied format_override for live stream: {format_override}")
        elif quality_key and quality_key != "best":
            # Convert quality_key to format if no format_override
            try:
                from DOWN_AND_UP.always_ask_menu import get_user_args
                user_args_local = get_user_args(user_id)
                user_codec = user_args_local.get('codec', 'avc1')
                
                # Build format based on quality_key and codec preference
                if quality_key.endswith('p'):
                    quality_val = int(quality_key[:-1])
                    # Determine previous quality
                    if quality_val >= 4320:
                        prev = 2160
                    elif quality_val >= 2160:
                        prev = 1440
                    elif quality_val >= 1440:
                        prev = 1080
                    elif quality_val >= 1080:
                        prev = 720
                    elif quality_val >= 720:
                        prev = 480
                    elif quality_val >= 480:
                        prev = 360
                    elif quality_val >= 360:
                        prev = 240
                    elif quality_val >= 240:
                        prev = 144
                    else:
                        prev = 0
                    
                    if user_codec == "av01":
                        format_str = f"bv*[vcodec*=av01][height<={quality_val}][height>{prev}]+ba[acodec*=mp4a]/bv*[vcodec*=av01][height<={quality_val}]+ba[acodec*=opus]/bv*[vcodec*=av01]+ba/bv+ba/best"
                    elif user_codec == "vp9":
                        format_str = f"bv*[vcodec*=vp9][height<={quality_val}][height>{prev}]+ba[acodec*=mp4a]/bv*[vcodec*=vp9][height<={quality_val}]+ba[acodec*=opus]/bv*[vcodec*=vp9]+ba/bv+ba/best"
                    else:  # avc1
                        format_str = f"bv*[vcodec*=avc1][height<={quality_val}][height>{prev}]+ba[acodec*=mp4a]/bv*[vcodec*=avc1][height<={quality_val}]+ba/bv*[vcodec*=avc1]+ba/bv+ba/best"
                    base_opts['format'] = format_str
                    logger.info(f"Applied quality_key format for live stream: {format_str}")
            except Exception as e:
                logger.warning(f"Error converting quality_key to format: {e}")
        
        # Apply MKV preference from /format command
        try:
            from COMMANDS.format_cmd import get_user_mkv_preference
            mkv_on = get_user_mkv_preference(user_id)
            if mkv_on:
                base_opts['remux_video'] = 'mkv'
                logger.info(f"Applied MKV preference for live stream")
        except Exception as e:
            logger.debug(f"Could not get MKV preference: {e}")
        
        # Log final yt-dlp options for debugging
        log_ytdlp_options(user_id, base_opts, "live_stream_download")
        
        # Add cookies if available
        user_cookie_path = os.path.join("users", str(user_id), "cookie.txt")
        if os.path.exists(user_cookie_path):
            base_opts['cookiefile'] = user_cookie_path
        
        # Add proxy if needed
        if use_proxy:
            from COMMANDS.proxy_cmd import get_proxy_config
            proxy_config = get_proxy_config()
            if proxy_config and 'type' in proxy_config and 'ip' in proxy_config and 'port' in proxy_config:
                if proxy_config['type'] == 'http':
                    if proxy_config.get('user') and proxy_config.get('password'):
                        proxy_url = f"http://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                    else:
                        proxy_url = f"http://{proxy_config['ip']}:{proxy_config['port']}"
                elif proxy_config['type'] == 'https':
                    if proxy_config.get('user') and proxy_config.get('password'):
                        proxy_url = f"https://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                    else:
                        proxy_url = f"https://{proxy_config['ip']}:{proxy_config['port']}"
                elif proxy_config['type'] in ['socks4', 'socks5', 'socks5h']:
                    if proxy_config.get('user') and proxy_config.get('password'):
                        proxy_url = f"{proxy_config['type']}://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                    else:
                        proxy_url = f"{proxy_config['type']}://{proxy_config['ip']}:{proxy_config['port']}"
                else:
                    proxy_url = f"http://{proxy_config['ip']}:{proxy_config['port']}"
                base_opts['proxy'] = proxy_url
        else:
            from HELPERS.proxy_helper import add_proxy_to_ytdl_opts
            base_opts = add_proxy_to_ytdl_opts(base_opts, url, user_id)
        
        # Add PO token provider for YouTube
        from HELPERS.pot_helper import add_pot_to_ytdl_opts
        base_opts = add_pot_to_ytdl_opts(base_opts, url)
        
        # Calculate segment time in seconds
        segment_time = split_hours * 3600  # Convert hours to seconds
        
        # Download chunks sequentially
        successful_chunks = 0
        start_time = time.time()
        
        for chunk_idx in range(max_chunks):
            elapsed_time = time.time() - start_time
            if elapsed_time >= max_duration:
                logger.info(f"Reached max duration limit ({max_duration}s), stopping live stream download")
                break
            
            logger.info(f"Downloading live stream chunk {chunk_idx + 1}/{max_chunks}")
            
            # Update progress
            try:
                _emit_live_stream_progress(
                    execution_context,
                    chunk_idx=chunk_idx,
                    max_chunks=max_chunks,
                    split_hours=split_hours,
                )
            except Exception as e:
                logger.error(f"Error updating progress: {e}")
            try:
                if _execute_live_stream_chunk(
                    app=app,
                    message=message,
                    execution_context=execution_context,
                    base_opts=base_opts,
                    url=url,
                    user_dir_name=user_dir_name,
                    date_str=date_str,
                    safe_channel=safe_channel,
                    safe_title=safe_title,
                    split_hours=split_hours,
                    segment_time=segment_time,
                    max_chunks=max_chunks,
                    chunk_idx=chunk_idx,
                    video_title=video_title,
                    tags_text=tags_text,
                ):
                    successful_chunks += 1
            except Exception as e:
                logger.error(f"Error downloading chunk {chunk_idx + 1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
            
            # Check if we've reached max duration
            elapsed_time = time.time() - start_time
            if elapsed_time >= max_duration:
                logger.info(f"Reached max duration limit, stopping")
                break
        
        # Final progress update
        try:
            _execute_live_stream_completion_plan(
                execution_context,
                plan=_build_live_stream_completion_plan(successful_chunks=successful_chunks),
            )
        except Exception as e:
            logger.error(f"Error updating final progress: {e}")
        
        logger.info(f"Live stream download completed: {successful_chunks} chunks downloaded")
        return successful_chunks > 0
        
    except Exception as e:
        logger.error(f"Error in download_live_stream_chunked: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
