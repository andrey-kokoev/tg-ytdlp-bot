from pyrogram.types import ReplyParameters


def build_requested_indices(
    *,
    is_playlist: bool,
    video_start_with: int,
    video_count: int,
    video_end_with: int | None = None,
) -> list[int]:
    if not is_playlist:
        return []

    if video_end_with is not None:
        if video_start_with < 0 and video_end_with < 0:
            return list(range(video_start_with, video_end_with - 1, -1))
        if video_start_with > video_end_with:
            return list(range(video_start_with, video_end_with - 1, -1))
        return list(range(video_start_with, video_end_with + 1, 1))

    return list(range(video_start_with, video_start_with + video_count))


def send_playlist_cache_status(
    *,
    app,
    user_id: int,
    reply_to_message_id: int,
    text: str,
) -> None:
    app.send_message(
        user_id,
        text,
        reply_parameters=ReplyParameters(message_id=reply_to_message_id),
    )
