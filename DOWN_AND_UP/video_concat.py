from __future__ import annotations

import os
import re
import subprocess
from fractions import Fraction
from typing import Any, Sequence, cast


def maybe_reverse_concat_order(items: Sequence[Any], reverse_output: bool) -> list[Any]:
    if not reverse_output:
        return list(items)
    return list(reversed(items))


def build_selected_playlist_indices(start: int, end: int) -> list[int]:
    if start > end:
        return list(range(start, end - 1, -1))
    return list(range(start, end + 1))


def canonicalize_video_concat_playlist_url(url: str) -> str:
    match = re.search(r"list=([A-Za-z0-9_-]+)", url or "")
    if match:
        return f"https://www.youtube.com/playlist?list={match.group(1)}"
    return url


def _sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^\w\s\-\.]+", "_", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")
    return cleaned[:80] or "video"


def _fps_to_float(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        return round(float(Fraction(value)), 3)
    except Exception:
        return None


def _container_from_path(path: str) -> str | None:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return ext or None


def probe_video_concat_item(path: str) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,width,height,r_frame_rate",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ffprobe failed")

    import json

    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video_stream:
        raise RuntimeError("staged artifact has no video stream")

    return {
        "container": _container_from_path(path),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": _fps_to_float(video_stream.get("r_frame_rate")),
        "has_audio": audio_stream is not None,
        "duration": payload.get("format", {}).get("duration"),
    }


def build_video_concat_manifest(
    *,
    playlist_url: str,
    playlist_id: str | None,
    playlist_title: str | None,
    selected_indices: list[int],
    ordered_indices: list[int],
    staged_items: list[dict[str, Any]],
    ordering: str,
    concat_policy: str,
) -> dict[str, Any]:
    staged_indices = [int(item["playlist_index"]) for item in staged_items]
    missing_indices = [index for index in selected_indices if index not in staged_indices]
    return {
        "playlist_url": playlist_url,
        "playlist_id": playlist_id,
        "playlist_title": playlist_title,
        "selected_indices": list(selected_indices),
        "ordered_indices": list(ordered_indices),
        "requested_count": len(selected_indices),
        "staged_items": list(staged_items),
        "missing_indices": missing_indices,
        "ordering": ordering,
        "concat_policy": concat_policy,
    }


def evaluate_video_concat_compatibility(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("missing_indices"):
        return {
            "compatible": False,
            "policy": manifest.get("concat_policy"),
            "reason_code": "missing_staged_artifact",
            "reason_text": "One or more selected items did not produce a staged video file.",
            "mismatch_surface": "artifact_presence",
            "evidence": {"missing_indices": list(manifest.get("missing_indices") or [])},
        }

    staged_items = manifest.get("staged_items") or []
    if len(staged_items) < 2:
        return {
            "compatible": False,
            "policy": manifest.get("concat_policy"),
            "reason_code": "concat_scope_too_small",
            "reason_text": "Video concat needs at least two staged video items.",
            "mismatch_surface": "artifact_presence",
            "evidence": {"count": len(staged_items)},
        }

    base = staged_items[0]
    checks = [
        ("container", "mixed_container", "container_shape", "Selected videos do not share one container."),
        ("video_codec", "mixed_video_codec", "video_stream_shape", "Selected videos do not share one video codec."),
        ("audio_codec", "mixed_audio_codec", "audio_stream_shape", "Selected videos do not share one audio codec."),
        ("width", "mixed_resolution", "video_stream_shape", "Selected videos do not share one resolution."),
        ("height", "mixed_resolution", "video_stream_shape", "Selected videos do not share one resolution."),
        ("fps", "mixed_framerate", "video_stream_shape", "Selected videos do not share one frame rate."),
        ("has_audio", "mixed_stream_layout", "stream_layout", "Selected videos do not share one stream layout."),
    ]

    for field, reason_code, mismatch_surface, reason_text in checks:
        values = [item.get(field) for item in staged_items]
        normalized = set(values)
        if len(normalized) > 1:
            evidence_key = "values"
            if field in {"width", "height"}:
                evidence_key = field + "s"
            return {
                "compatible": False,
                "policy": manifest.get("concat_policy"),
                "reason_code": reason_code,
                "reason_text": reason_text,
                "mismatch_surface": mismatch_surface,
                "evidence": {evidence_key: sorted(normalized, key=lambda value: str(value))},
            }

    return {
        "compatible": True,
        "policy": manifest.get("concat_policy"),
        "reason_code": None,
        "reason_text": None,
        "mismatch_surface": None,
        "evidence": {
            "container": base.get("container"),
            "video_codec": base.get("video_codec"),
            "audio_codec": base.get("audio_codec"),
            "width": base.get("width"),
            "height": base.get("height"),
            "fps": base.get("fps"),
            "count": len(staged_items),
        },
    }


def concat_video_files(*, ordered_paths: list[str], output_path: str) -> dict[str, Any]:
    from DOWN_AND_UP.ffmpeg import get_ffmpeg_path

    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return {
            "succeeded": False,
            "artifact_path": None,
            "reason_code": "ffmpeg_missing",
            "phase": "concat_execution",
            "evidence": {},
        }

    concat_file = os.path.join(os.path.dirname(output_path), "video_concat_inputs.txt")
    with open(concat_file, "w", encoding="utf-8") as handle:
        for video_file in ordered_paths:
            escaped_path = os.path.abspath(video_file).replace("'", "'\\''")
            handle.write(f"file '{escaped_path}'\n")

    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c",
        "copy",
        output_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not os.path.exists(output_path):
        return {
            "succeeded": False,
            "artifact_path": None,
            "reason_code": "ffmpeg_concat_failed",
            "phase": "concat_execution",
            "evidence": {"stderr": (result.stderr or result.stdout or "").strip()[:1000]},
        }

    return {
        "succeeded": True,
        "artifact_path": output_path,
        "reason_code": None,
        "phase": "concat_execution",
        "evidence": {},
    }


def _extract_playlist_entries(*, url: str, user_id: int, start: int, end: int) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    import yt_dlp

    from DOWN_AND_UP.audio_concat import build_playlist_items_selector
    from HELPERS.pot_helper import add_pot_to_ytdl_opts
    from HELPERS.proxy_helper import add_proxy_to_ytdl_opts

    canonical_url = canonicalize_video_concat_playlist_url(url)
    selector = build_playlist_items_selector(start, end)
    ytdl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlist_items": selector,
        "extractor_args": {"generic": {"impersonate": ["chrome"]}},
        "referer": canonical_url,
        "geo_bypass": True,
        "check_certificate": False,
        "live_from_start": True,
    }
    cookie_file = os.path.join("users", str(user_id), "cookie.txt")
    if os.path.exists(cookie_file):
        ytdl_opts["cookiefile"] = cookie_file
    ytdl_opts = add_proxy_to_ytdl_opts(ytdl_opts, canonical_url, user_id=user_id)
    ytdl_opts = add_pot_to_ytdl_opts(ytdl_opts, canonical_url)

    with yt_dlp.YoutubeDL(cast(Any, ytdl_opts)) as ydl:
        info = ydl.extract_info(canonical_url, download=False)

    playlist_title = None
    playlist_id = None
    entries: list[dict[str, Any]] = []
    if isinstance(info, dict):
        playlist_title = info.get("title") or info.get("playlist_title")
        playlist_id = info.get("id") or info.get("playlist_id")
        entries = [cast(dict[str, Any], entry) for entry in (info.get("entries") or []) if isinstance(entry, dict)]
    return playlist_title, playlist_id, entries


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


def _download_video_entry(
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
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "prefer_ffmpeg": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"generic": {"impersonate": ["chrome"]}},
        "referer": entry_url,
        "geo_bypass": True,
        "check_certificate": False,
        "live_from_start": True,
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
        if file_name.lower().endswith(".mp4")
    )
    if not new_files:
        for file_name in sorted(after_files):
            if file_name.lower().endswith(".mp4"):
                new_files.append(file_name)
    if not new_files:
        raise RuntimeError(f"No MP4 output produced for {entry_url}")
    return os.path.join(download_dir, new_files[-1])


def concat_video_playlist_range(
    app,
    message,
    *,
    url: str,
    video_start_with: int,
    video_end_with: int,
    reverse_output: bool,
    output_name_override: str | None = None,
    task_context=None,
) -> None:
    from pyrogram.types import ReplyParameters

    from DOWN_AND_UP.preflight_flow import cleanup_download_dir_before_start, ensure_user_download_dir
    from DOWN_AND_UP.runtime_task import with_terminal_outcome
    from DOWN_AND_UP.terminal_outcome_result import failed_terminal_outcome, upload_terminal_outcome
    from HELPERS.download_status import set_active_download
    from HELPERS.logger import logger, send_error_to_user, send_to_logger
    from HELPERS.safe_messeger import safe_delete_messages, safe_send_message

    user_id = message.chat.id
    status_msg = None
    ordering = "reverse" if reverse_output else "original"

    if task_context is not None:
        task_context = task_context.with_concat_request(
            concat_policy="direct_concat_only",
            concat_ordering=ordering,
            chapter_policy="none",
            output_name_override=output_name_override,
        )

    if video_start_with < 0 or video_end_with < 0:
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                failed_terminal_outcome(
                    media_kind="video_concat",
                    failure_kind="unsupported_range",
                    error_text="negative_indices_not_supported",
                ),
            )
        send_error_to_user(message, "Negative playlist indices are not supported for /concat video yet.")
        return

    if video_start_with == video_end_with:
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                failed_terminal_outcome(
                    media_kind="video_concat",
                    failure_kind="insufficient_items",
                    error_text="need_at_least_two_items",
                ),
            )
        send_error_to_user(message, "Video concat needs at least 2 playlist items.")
        return

    set_active_download(user_id, True)
    try:
        canonical_url = canonicalize_video_concat_playlist_url(url)
        if task_context is not None:
            task_context = task_context.with_url(canonical_url)
        _, download_dir = ensure_user_download_dir(user_id=user_id, url=canonical_url, logger=logger)
        cleanup_download_dir_before_start(download_dir=download_dir, message=message, logger=logger)

        status_msg = safe_send_message(
            user_id,
            "🎬 Preparing playlist video concat...",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

        playlist_title, playlist_id, entries = _extract_playlist_entries(
            url=canonical_url,
            user_id=user_id,
            start=video_start_with,
            end=video_end_with,
        )
        if len(entries) < 2:
            raise RuntimeError("Selected playlist range did not resolve to at least 2 downloadable items")

        requested_indices = build_selected_playlist_indices(video_start_with, video_end_with)
        entry_pairs = list(zip(requested_indices, entries))
        ordered_pairs = cast(list[tuple[int, dict[str, Any]]], maybe_reverse_concat_order(entry_pairs, reverse_output))
        staged_items: list[dict[str, Any]] = []

        for sequence_index, (playlist_index, entry) in enumerate(ordered_pairs, start=1):
            entry_url = _playlist_entry_web_url(entry)
            if not entry_url:
                raise RuntimeError(f"Failed to resolve entry URL for playlist item #{playlist_index}")
            entry_title = entry.get("title") or f"Item {playlist_index}"
            app.edit_message_text(
                chat_id=user_id,
                message_id=status_msg.id,
                text=f"🎬 Downloading {sequence_index}/{len(ordered_pairs)}\n{entry_title}",
            )
            artifact_path = _download_video_entry(
                entry_url=entry_url,
                download_dir=download_dir,
                user_id=user_id,
                sequence_index=sequence_index,
            )
            media_info = probe_video_concat_item(artifact_path)
            staged_items.append(
                {
                    "playlist_index": playlist_index,
                    "source_url": entry_url,
                    "artifact_path": artifact_path,
                    **media_info,
                }
            )

        selected_indices = sorted(set(requested_indices))
        ordered_indices = [pair[0] for pair in ordered_pairs]
        manifest = build_video_concat_manifest(
            playlist_url=canonical_url,
            playlist_id=playlist_id,
            playlist_title=playlist_title,
            selected_indices=selected_indices,
            ordered_indices=ordered_indices,
            staged_items=staged_items,
            ordering=ordering,
            concat_policy="direct_concat_only",
        )
        if task_context is not None:
            task_context = task_context.with_video_concat_manifest(manifest)

        compatibility = evaluate_video_concat_compatibility(manifest)
        if task_context is not None:
            task_context = task_context.with_video_concat_compatibility(compatibility)
        if not compatibility["compatible"]:
            if task_context is not None:
                with_terminal_outcome(
                    task_context,
                    failed_terminal_outcome(
                        media_kind="video_concat",
                        failure_kind="determinate_rejection",
                        error_text=compatibility["reason_code"],
                        attempted_count=len(selected_indices),
                    ),
                )
            send_error_to_user(
                message,
                "Video concat is not possible under direct concat mode: "
                f"{compatibility['reason_text']}",
            )
            return

        display_title = output_name_override or playlist_title or "playlist_video_concat"
        output_name = _sanitize_component(display_title) + ".mp4"
        output_path = os.path.join(download_dir, output_name)
        app.edit_message_text(
            chat_id=user_id,
            message_id=status_msg.id,
            text=f"🧩 Concatenating {len(staged_items)} video files...",
        )
        execution = concat_video_files(
            ordered_paths=[item["artifact_path"] for item in staged_items],
            output_path=output_path,
        )
        if task_context is not None:
            task_context = task_context.with_video_concat_execution(execution)
        if not execution["succeeded"]:
            if task_context is not None:
                with_terminal_outcome(
                    task_context,
                    failed_terminal_outcome(
                        media_kind="video_concat",
                        failure_kind="acquisition_or_transformation_failure",
                        error_text=execution["reason_code"],
                        attempted_count=len(selected_indices),
                    ),
                )
            send_error_to_user(message, "Video concat failed while building the composite video.")
            return

        caption = (
            f"🎬 <b>Concatenated playlist video</b>\n"
            f"<b>Playlist:</b> {display_title}\n"
            f"<b>Items:</b> {len(staged_items)}\n"
            f"<b>Order:</b> {'Reverse order' if reverse_output else 'Original order'}"
        )
        app.send_video(
            chat_id=user_id,
            video=output_path,
            caption=caption,
            reply_parameters=ReplyParameters(message_id=message.id),
            supports_streaming=True,
        )
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                upload_terminal_outcome(
                    media_kind="video_concat",
                    attempted_count=1,
                    delivered_count=1,
                ),
            )
        send_to_logger(
            message,
            f"Video concat sent: {playlist_title or url} items={len(staged_items)} reverse={reverse_output}",
        )
    except Exception as e:
        logger.error(f"Video concat failed for user {user_id}: {e}")
        if task_context is not None:
            with_terminal_outcome(
                task_context,
                failed_terminal_outcome(
                    media_kind="video_concat",
                    failure_kind="concat_failed",
                    error_text=str(e),
                    attempted_count=max(0, abs(video_end_with - video_start_with) + 1),
                ),
            )
        send_error_to_user(message, f"Video concat failed: {e}")
    finally:
        set_active_download(user_id, False)
        if status_msg is not None:
            try:
                safe_delete_messages(chat_id=user_id, message_ids=[status_msg.id])
            except Exception:
                pass
