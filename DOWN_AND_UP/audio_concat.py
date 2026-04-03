from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, cast

from DOWN_AND_UP.runtime_task import RuntimeTask

def build_playlist_items_selector(start: int, end: int) -> str:
    if start > end:
        return f"{start}:{end}:-1"
    return f"{start}:{end}"


def maybe_reverse_concat_order(items: list[dict[str, Any]], reverse_output: bool) -> list[dict[str, Any]]:
    if not reverse_output:
        return list(items)
    return list(reversed(items))


def _build_concat_caption(messages, *, playlist_title: str | None, item_count: int, reverse_output: bool) -> str:
    title = playlist_title or "Playlist"
    order_line = "Reverse order" if reverse_output else "Original order"
    return (
        f"🔊 <b>Concatenated playlist audio</b>\n"
        f"<b>Playlist:</b> {title}\n"
        f"<b>Items:</b> {item_count}\n"
        f"<b>Order:</b> {order_line}"
    )


def _playlist_entry_web_url(entry: dict[str, Any]) -> str | None:
    webpage_url = entry.get("webpage_url") or entry.get("url")
    if not webpage_url:
        return None
    if isinstance(webpage_url, str) and webpage_url.startswith("http"):
        return webpage_url
    entry_id = entry.get("id") or webpage_url
    if not entry_id:
        return None
    return f"https://www.youtube.com/watch?v={entry_id}"


def _sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^\w\s\-\.]+", "_", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")
    return cleaned[:80] or "audio"


def parse_concat_name_override(text: str) -> tuple[str | None, str]:
    match = re.search(r"\b(?:name|title)\s+\"([^\"]+)\"", text)
    if not match:
        return None, text
    name_override = match.group(1).strip()
    cleaned_text = (text[:match.start()] + text[match.end():]).strip()
    cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text)
    return name_override or None, cleaned_text


def _concat_meta_path(user_id: int) -> str:
    return os.path.join("users", str(user_id), "last_audio_concat.json")


def save_last_audio_concat_meta(
    *,
    user_id: int,
    output_path: str,
    display_title: str,
    item_count: int,
    reverse_output: bool,
    source_url: str,
) -> None:
    user_dir = os.path.join("users", str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    with open(_concat_meta_path(user_id), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "output_path": output_path,
                "display_title": display_title,
                "item_count": item_count,
                "reverse_output": reverse_output,
                "source_url": source_url,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def load_last_audio_concat_meta(user_id: int) -> dict[str, Any] | None:
    meta_path = _concat_meta_path(user_id)
    if not os.path.exists(meta_path):
        return None
    with open(meta_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_playlist_entries(*, url: str, user_id: int, start: int, end: int) -> tuple[str | None, list[dict[str, Any]]]:
    import yt_dlp
    from HELPERS.pot_helper import add_pot_to_ytdl_opts
    from HELPERS.proxy_helper import add_proxy_to_ytdl_opts

    selector = build_playlist_items_selector(start, end)
    ytdl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlist_items": selector,
        "extractor_args": {
            "generic": {"impersonate": ["chrome"]},
        },
        "referer": url,
        "geo_bypass": True,
        "check_certificate": False,
        "live_from_start": True,
    }

    cookie_file = os.path.join("users", str(user_id), "cookie.txt")
    if os.path.exists(cookie_file):
        ytdl_opts["cookiefile"] = cookie_file
    ytdl_opts = add_proxy_to_ytdl_opts(ytdl_opts, url, user_id=user_id)
    ytdl_opts = add_pot_to_ytdl_opts(ytdl_opts, url)

    with yt_dlp.YoutubeDL(cast(Any, ytdl_opts)) as ydl:
        info = ydl.extract_info(url, download=False)

    playlist_title = None
    entries: list[dict[str, Any]] = []
    if isinstance(info, dict):
        playlist_title = info.get("title") or info.get("playlist_title")
        raw_entries = info.get("entries") or []
        entries = [entry for entry in raw_entries if entry]
    return playlist_title, entries


def _download_audio_entry(
    *,
    entry_url: str,
    download_dir: str,
    user_id: int,
    sequence_index: int,
) -> str:
    import yt_dlp
    from HELPERS.pot_helper import add_pot_to_ytdl_opts
    from HELPERS.proxy_helper import add_proxy_to_ytdl_opts

    output_template = os.path.join(download_dir, f"{sequence_index:03d}_%(title).80s.%(ext)s")
    ytdl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {"key": "FFmpegMetadata"},
        ],
        "prefer_ffmpeg": True,
        "extractaudio": True,
        "restrictfilenames": False,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "generic": {"impersonate": ["chrome"]},
        },
        "referer": entry_url,
        "geo_bypass": True,
        "check_certificate": False,
        "live_from_start": True,
        "writethumbnail": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
    }

    cookie_file = os.path.join("users", str(user_id), "cookie.txt")
    if os.path.exists(cookie_file):
        ytdl_opts["cookiefile"] = cookie_file
    ytdl_opts = add_proxy_to_ytdl_opts(ytdl_opts, entry_url, user_id=user_id)
    ytdl_opts = add_pot_to_ytdl_opts(ytdl_opts, entry_url)

    before_files = set(os.listdir(download_dir))
    with yt_dlp.YoutubeDL(cast(Any, ytdl_opts)) as ydl:
        ydl.download([entry_url])
    after_files = set(os.listdir(download_dir))
    new_files = sorted(
        file_name for file_name in (after_files - before_files)
        if file_name.lower().endswith(".mp3")
    )
    if not new_files:
        for file_name in sorted(after_files):
            if file_name.lower().endswith(".mp3"):
                new_files.append(file_name)
    if not new_files:
        raise RuntimeError(f"No MP3 output produced for {entry_url}")
    return os.path.join(download_dir, new_files[-1])


def concat_audio_files(*, audio_files: list[str], output_path: str) -> str:
    from DOWN_AND_UP.ffmpeg import get_ffmpeg_path

    if len(audio_files) < 2:
        raise ValueError("Need at least two audio files to concatenate")

    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    concat_file = os.path.join(os.path.dirname(output_path), "concat_inputs.txt")
    with open(concat_file, "w", encoding="utf-8") as handle:
        for audio_file in audio_files:
            escaped_path = os.path.abspath(audio_file).replace("'", "'\\''")
            handle.write(f"file '{escaped_path}'\n")

    cmd = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-vn",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ffmpeg concat failed")
    return output_path


def concat_audio_playlist_range(
    app,
    message,
    *,
    url: str,
    video_start_with: int,
    video_end_with: int,
    reverse_output: bool,
    output_name_override: str | None = None,
    task_context: RuntimeTask | None = None,
) -> None:
    from pyrogram.types import ReplyParameters
    from CONFIG.messages import safe_get_messages
    from DOWN_AND_UP.preflight_flow import cleanup_download_dir_before_start, ensure_user_download_dir
    from DOWN_AND_UP.runtime_task import with_terminal_outcome
    from DOWN_AND_UP.terminal_outcome_result import failed_terminal_outcome, upload_terminal_outcome
    from HELPERS.download_status import set_active_download
    from HELPERS.logger import logger, send_error_to_user, send_to_logger
    from HELPERS.safe_messeger import safe_delete_messages, safe_send_message

    user_id = message.chat.id
    messages = safe_get_messages(user_id)
    status_msg = None

    if video_start_with < 0 or video_end_with < 0:
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                failed_terminal_outcome(
                    media_kind="audio_concat",
                    failure_kind="unsupported_range",
                    error_text="negative_indices_not_supported",
                ),
            )
        send_error_to_user(message, "Negative playlist indices are not supported for /aconcat yet.")
        return

    if video_start_with == video_end_with:
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                failed_terminal_outcome(
                    media_kind="audio_concat",
                    failure_kind="insufficient_items",
                    error_text="need_at_least_two_items",
                ),
            )
        send_error_to_user(message, "Audio concat needs at least 2 playlist items.")
        return

    set_active_download(user_id, True)
    try:
        _, download_dir = ensure_user_download_dir(user_id=user_id, url=url, logger=logger)
        cleanup_download_dir_before_start(download_dir=download_dir, message=message, logger=logger)

        status_msg = safe_send_message(
            user_id,
            "🔗 Preparing playlist audio concat...",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

        playlist_title, entries = _extract_playlist_entries(
            url=url,
            user_id=user_id,
            start=video_start_with,
            end=video_end_with,
        )
        if len(entries) < 2:
            raise RuntimeError("Selected playlist range did not resolve to at least 2 downloadable items")

        ordered_entries = maybe_reverse_concat_order(entries, reverse_output)
        audio_files: list[str] = []

        for sequence_index, entry in enumerate(ordered_entries, start=1):
            entry_url = _playlist_entry_web_url(entry)
            if not entry_url:
                raise RuntimeError(f"Failed to resolve entry URL for playlist item #{sequence_index}")
            entry_title = entry.get("title") or f"Item {sequence_index}"
            app.edit_message_text(
                chat_id=user_id,
                message_id=status_msg.id,
                text=f"🎧 Downloading {sequence_index}/{len(ordered_entries)}\n{entry_title}",
            )
            audio_files.append(
                _download_audio_entry(
                    entry_url=entry_url,
                    download_dir=download_dir,
                    user_id=user_id,
                    sequence_index=sequence_index,
                )
            )

        display_title = output_name_override or playlist_title or "playlist_audio_concat"
        output_name = _sanitize_component(display_title) + ".mp3"
        output_path = os.path.join(download_dir, output_name)
        app.edit_message_text(
            chat_id=user_id,
            message_id=status_msg.id,
            text=f"🧩 Concatenating {len(audio_files)} audio files...",
        )
        concat_audio_files(audio_files=audio_files, output_path=output_path)

        caption = _build_concat_caption(
            messages,
            playlist_title=display_title,
            item_count=len(audio_files),
            reverse_output=reverse_output,
        )
        app.send_audio(
            chat_id=user_id,
            audio=output_path,
            caption=caption,
            title=display_title,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        save_last_audio_concat_meta(
            user_id=user_id,
            output_path=output_path,
            display_title=display_title,
            item_count=len(audio_files),
            reverse_output=reverse_output,
            source_url=url,
        )
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                upload_terminal_outcome(
                    media_kind="audio_concat",
                    attempted_count=len(audio_files),
                    delivered_count=1,
                ),
            )
        send_to_logger(
            message,
            f"Audio concat sent: {playlist_title or url} items={len(audio_files)} reverse={reverse_output}",
        )
    except Exception as e:
        logger.error(f"Audio concat failed for user {user_id}: {e}")
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                failed_terminal_outcome(
                    media_kind="audio_concat",
                    failure_kind="concat_failed",
                    error_text=str(e),
                    attempted_count=max(0, abs(video_end_with - video_start_with) + 1),
                ),
            )
        send_error_to_user(message, f"Audio concat failed: {e}")
    finally:
        set_active_download(user_id, False)
        if status_msg is not None:
            try:
                safe_delete_messages(chat_id=user_id, message_ids=[status_msg.id])
            except Exception:
                pass


def resend_last_audio_concat_with_new_name(app, message, *, new_name: str) -> None:
    from pyrogram.types import ReplyParameters
    from CONFIG.messages import safe_get_messages
    from HELPERS.logger import send_error_to_user

    user_id = message.chat.id
    meta = load_last_audio_concat_meta(user_id)
    if not meta:
        send_error_to_user(message, "No recent audio concat output found to rename.")
        return

    original_path = meta.get("output_path")
    if not original_path or not os.path.exists(original_path):
        send_error_to_user(message, "Saved audio concat file is no longer available on disk.")
        return

    safe_name = _sanitize_component(new_name)
    renamed_path = os.path.join(os.path.dirname(original_path), safe_name + ".mp3")
    if os.path.abspath(renamed_path) != os.path.abspath(original_path):
        os.replace(original_path, renamed_path)
    else:
        renamed_path = original_path

    messages = safe_get_messages(user_id)
    caption = _build_concat_caption(
        messages,
        playlist_title=new_name,
        item_count=int(meta.get("item_count") or 1),
        reverse_output=bool(meta.get("reverse_output")),
    )
    app.send_audio(
        chat_id=user_id,
        audio=renamed_path,
        caption=caption,
        title=new_name,
        reply_parameters=ReplyParameters(message_id=message.id),
    )
    save_last_audio_concat_meta(
        user_id=user_id,
        output_path=renamed_path,
        display_title=new_name,
        item_count=int(meta.get("item_count") or 1),
        reverse_output=bool(meta.get("reverse_output")),
        source_url=str(meta.get("source_url") or ""),
    )
