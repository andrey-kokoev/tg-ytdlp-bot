import sys
import types
from pathlib import Path
from types import SimpleNamespace


def _install_pyrogram_stub():
    if "pyrogram" in sys.modules:
        return

    pyrogram_module = types.ModuleType("pyrogram")
    enums_ns = SimpleNamespace(
        ParseMode=SimpleNamespace(HTML="HTML"),
        ChatType=SimpleNamespace(PRIVATE="private", SUPERGROUP="supergroup"),
    )
    pyrogram_module.enums = enums_ns
    pyrogram_module.Client = object

    pyrogram_errors = types.ModuleType("pyrogram.errors")

    class FloodWait(Exception):
        def __init__(self, value=0):
            self.value = value

    pyrogram_errors.FloodWait = FloodWait

    pyrogram_types = types.ModuleType("pyrogram.types")

    class ReplyParameters:
        def __init__(self, message_id):
            self.message_id = message_id

    pyrogram_types.ReplyParameters = ReplyParameters
    pyrogram_types.InlineKeyboardButton = type("InlineKeyboardButton", (), {})
    pyrogram_types.InlineKeyboardMarkup = type("InlineKeyboardMarkup", (), {})
    pyrogram_enums = types.ModuleType("pyrogram.enums")
    pyrogram_enums.ParseMode = enums_ns.ParseMode
    pyrogram_enums.ChatType = enums_ns.ChatType
    pyrogram_enums.ChatMemberStatus = SimpleNamespace(
        OWNER="owner",
        ADMINISTRATOR="administrator",
        MEMBER="member",
    )

    sys.modules["pyrogram"] = pyrogram_module
    sys.modules["pyrogram.errors"] = pyrogram_errors
    sys.modules["pyrogram.types"] = pyrogram_types
    sys.modules["pyrogram.enums"] = pyrogram_enums


_install_pyrogram_stub()


def _install_logger_stub():
    if "HELPERS.logger" in sys.modules:
        return

    logger_module = types.ModuleType("HELPERS.logger")
    dummy_logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
    )
    logger_module.logger = dummy_logger
    logger_module.send_to_logger = lambda *args, **kwargs: None
    logger_module.send_to_user = lambda *args, **kwargs: None
    logger_module.send_error_to_user = lambda *args, **kwargs: None
    logger_module.log_error_to_channel = lambda *args, **kwargs: None
    logger_module.get_log_channel = lambda *args, **kwargs: -1000
    sys.modules["HELPERS.logger"] = logger_module


_install_logger_stub()

from pyrogram import enums

import DOWN_AND_UP.direct_link_flow as direct_link_flow
import DOWN_AND_UP.preflight_flow as preflight_flow
from DOWN_AND_UP.cache_flow import lookup_single_cached_ids, try_repost_single_cached_media
from DOWN_AND_UP.direct_link_flow import (
    direct_link_quality_arg,
    execute_direct_link_flow,
    send_always_ask_direct_link_response,
    send_always_ask_direct_link_response_legacy_error,
    send_standard_direct_link_response,
)
from DOWN_AND_UP.playlist_flow import build_requested_indices, send_playlist_cache_status
from DOWN_AND_UP.preflight_flow import (
    cleanup_download_dir_before_start,
    ensure_user_download_dir,
    start_processing_handshake,
)
from DOWN_AND_UP.retry_flow import (
    maybe_retry_with_different_cookies,
    maybe_retry_with_proxy_on_geo_error,
)
from HELPERS.download_status import (
    clear_playlist_error_state,
    get_playlist_error_summary,
    mark_playlist_error,
)


class DummyLogger:
    def __init__(self):
        self.records = []

    def info(self, msg, *args):
        self.records.append(("info", msg % args if args else msg))

    def warning(self, msg, *args):
        self.records.append(("warning", msg % args if args else msg))

    def error(self, msg, *args):
        self.records.append(("error", msg % args if args else msg))


class DummyApp:
    def __init__(self):
        self.sent_messages = []
        self.forwarded = []
        self.edited = []
        self.pinned = []

    def send_message(self, chat_id, text, **kwargs):
        msg = SimpleNamespace(id=len(self.sent_messages) + 1, chat_id=chat_id, text=text, kwargs=kwargs)
        self.sent_messages.append(msg)
        return msg

    def forward_messages(self, **kwargs):
        self.forwarded.append(kwargs)

    def edit_message_text(self, **kwargs):
        self.edited.append(kwargs)

    def pin_chat_message(self, *args, **kwargs):
        self.pinned.append((args, kwargs))


def _message(user_id=123, message_id=77, private=True, thread_id=None):
    chat_type = enums.ChatType.PRIVATE if private else enums.ChatType.SUPERGROUP
    return SimpleNamespace(
        id=message_id,
        chat=SimpleNamespace(id=user_id, type=chat_type),
        message_thread_id=thread_id,
    )


def _direct_messages():
    return SimpleNamespace(
        DIRECT_LINK_OBTAINED_MSG="Direct link\n",
        TITLE_FIELD_MSG="Title: {title}\n",
        DURATION_FIELD_MSG="Duration: {duration}\n",
        FORMAT_FIELD_MSG="Format: {format_spec}\n",
        VIDEO_STREAM_FIELD_MSG="Video: {video_url}\n",
        AUDIO_STREAM_FIELD_MSG="Audio: {audio_url}\n",
        DOWN_UP_FAILED_STREAM_LINKS_MSG="No streams\n",
        DOWN_UP_ERROR_GETTING_LINK_MSG="Error: {error_msg}",
        ALWAYS_ASK_DIRECT_LINK_OBTAINED_MSG="AA OK",
        ALWAYS_ASK_TITLE_MSG="Title:",
        ALWAYS_ASK_DURATION_SEC_MSG="Duration:",
        ALWAYS_ASK_FORMAT_CODE_MSG="Format:",
        ALWAYS_ASK_VIDEO_STREAM_MSG="Video stream",
        ALWAYS_ASK_AUDIO_STREAM_MSG="Audio stream",
        ALWAYS_ASK_FAILED_TO_GET_STREAM_LINKS_MSG="AA No streams",
        AA_ERROR_GETTING_LINK_MSG="AA Error: {error_msg}",
        RATE_LIMIT_NO_TIME_MSG="rate-limit",
        DOWNLOAD_STARTED_MSG="started",
        PROCESSING_MSG="processing",
    )


def test_direct_link_quality_arg_and_execute_flow(monkeypatch):
    assert direct_link_quality_arg("720p") == "720p"
    assert direct_link_quality_arg("best") is None
    assert direct_link_quality_arg("mp3") is None
    assert direct_link_quality_arg(None) is None

    captured = {}

    def fake_fetch(url, user_id, quality_arg, **kwargs):
        captured["fetch"] = (url, user_id, quality_arg, kwargs)
        return {"success": True, "title": "Clip"}

    def fake_sender(app, message, user_id, result):
        captured["sender"] = (app, message, user_id, result)

    app = object()
    message = _message()
    result = execute_direct_link_flow(
        fetch_direct_link=fake_fetch,
        response_sender=fake_sender,
        app=app,
        message=message,
        user_id=123,
        url="https://example.com/v",
        quality_key="480p",
        cookies_already_checked=True,
        use_proxy=False,
    )

    assert result["success"] is True
    assert captured["fetch"][2] == "480p"
    assert captured["sender"][2] == 123
    assert captured["sender"][3] == result


def test_direct_link_response_senders(monkeypatch):
    monkeypatch.setattr(direct_link_flow, "safe_get_messages", lambda _user_id: _direct_messages())
    app = DummyApp()
    message = _message()

    send_standard_direct_link_response(
        app,
        message,
        123,
        {
            "success": True,
            "title": "Example",
            "duration": 12,
            "format": "best",
            "video_url": "https://video",
            "audio_url": "https://audio",
        },
    )
    assert "Title: Example" in app.sent_messages[-1].text
    assert app.sent_messages[-1].kwargs["parse_mode"] == enums.ParseMode.HTML

    send_always_ask_direct_link_response(
        app,
        message,
        123,
        {"success": False, "error": "boom"},
    )
    assert "Error getting link" in app.sent_messages[-1].text

    send_always_ask_direct_link_response_legacy_error(
        app,
        message,
        123,
        {"success": False, "error": "bad"},
    )
    assert app.sent_messages[-1].text == "AA Error: bad"


def test_playlist_flow_builds_indices_and_sends_status():
    assert build_requested_indices(
        is_playlist=False,
        video_start_with=1,
        video_count=1,
    ) == []
    assert build_requested_indices(
        is_playlist=True,
        video_start_with=1,
        video_count=3,
    ) == [1, 2, 3]
    assert build_requested_indices(
        is_playlist=True,
        video_start_with=5,
        video_count=1,
        video_end_with=3,
    ) == [5, 4, 3]
    assert build_requested_indices(
        is_playlist=True,
        video_start_with=-1,
        video_count=1,
        video_end_with=-3,
    ) == [-1, -2, -3]

    app = DummyApp()
    send_playlist_cache_status(app=app, user_id=123, reply_to_message_id=77, text="cache hit")
    assert app.sent_messages[-1].text == "cache hit"


def test_retry_flow_cookie_and_proxy_retries():
    logger = DummyLogger()

    retry_result, did_cookie_retry = maybe_retry_with_different_cookies(
        user_id=1,
        url="https://youtube.com/watch?v=1",
        result=None,
        did_cookie_retry=False,
        is_youtube_url=lambda url: "youtube" in url,
        retry_download_with_different_cookies=lambda user_id, url, fn, *args: "ok",
        download_fn=lambda *_args: None,
        download_args=("u", 1),
        logger=logger,
        media_label="Audio",
    )
    assert retry_result == "ok"
    assert did_cookie_retry is True

    retry_result, did_proxy_retry = maybe_retry_with_proxy_on_geo_error(
        user_id=1,
        url="https://youtube.com/watch?v=1",
        error_text="geo blocked",
        did_proxy_retry=False,
        is_youtube_url=lambda url: "youtube" in url,
        is_youtube_geo_error=lambda text: text == "geo blocked",
        retry_download_with_proxy=lambda user_id, url, fn, *args: "proxy-ok",
        download_fn=lambda *_args: None,
        download_args=("u", 1),
        logger=logger,
        success_log_text="proxy success for {user_id}",
        failure_log_text="proxy failure for {user_id}",
    )
    assert retry_result == "proxy-ok"
    assert did_proxy_retry is True


def test_cache_flow_lookup_and_repost_paths():
    logger = DummyLogger()
    cached, is_nsfw = lookup_single_cached_ids(
        user_id=1,
        url="https://example.com",
        quality_key="720p",
        user_forced_nsfw=False,
        always_ask_enabled=False,
        is_nsfw_detector=lambda *args: False,
        get_cached_message_ids=lambda url, quality: [10, 11],
        logger=logger,
        nsfw_skip_log="skip nsfw {url} {quality}",
        always_ask_skip_log="skip always ask {url} {quality}",
    )
    assert cached == [10, 11]
    assert is_nsfw is False

    app = DummyApp()
    sent_logs = []
    ok = try_repost_single_cached_media(
        app=app,
        message=_message(private=False, thread_id=55),
        user_id=1,
        cached_ids=[10],
        resolve_from_chat_id=lambda: -1001,
        success_text="sent from cache",
        success_log_text="cache logged",
        logger=logger,
        replay_log_prefix="repost",
        replay_error_prefix="repost failed",
        on_replay_error=lambda: sent_logs.append("error"),
        send_to_logger=lambda _message, text: sent_logs.append(text),
    )
    assert ok is True
    assert app.forwarded[-1]["message_thread_id"] == 55
    assert app.sent_messages[-1].text == "sent from cache"
    assert "cache logged" in sent_logs


def test_preflight_flow_helpers(tmp_path, monkeypatch):
    logger = DummyLogger()
    user_id = 123
    user_dir = tmp_path / "users" / str(user_id)
    download_dir = user_dir / "downloads" / "abc"
    download_dir.mkdir(parents=True)
    media_file = download_dir / "old.mp4"
    media_file.write_text("x", encoding="utf-8")
    nested = download_dir / "nested"
    nested.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        preflight_flow,
        "create_directory",
        lambda path: Path(path).mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(
        preflight_flow,
        "safe_send_message",
        lambda user_id, text, message: SimpleNamespace(id=77, text=text),
    )

    import HELPERS.filesystem_hlp as filesystem_hlp
    import HELPERS.safe_messeger as safe_messenger

    always_ask_stub = types.ModuleType("DOWN_AND_UP.always_ask_menu")
    always_ask_stub.get_user_download_dir = lambda _user_id: None
    always_ask_stub.generate_download_dir_name = lambda _url: "abc"
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.always_ask_menu", always_ask_stub)
    monkeypatch.setattr(filesystem_hlp, "is_parallel_download_allowed", lambda _message: True)
    protection_calls = []
    monkeypatch.setattr(filesystem_hlp, "create_protection_file", lambda path: protection_calls.append(path))
    schedule_calls = []
    monkeypatch.setattr(safe_messenger, "schedule_delete_message", lambda *args, **kwargs: schedule_calls.append((args, kwargs)))

    resolved_user_dir, resolved_download_dir = ensure_user_download_dir(
        user_id=user_id,
        url="https://example.com",
        logger=logger,
    )
    assert resolved_user_dir.endswith(f"users/{user_id}")
    assert resolved_download_dir.endswith("users/123/downloads/abc")

    cleanup_download_dir_before_start(
        download_dir=str(download_dir),
        message=_message(),
        logger=logger,
    )
    assert not media_file.exists()
    assert protection_calls[-1] == str(download_dir)

    app = DummyApp()
    messages = _direct_messages()
    handshake = start_processing_handshake(
        app=app,
        message=_message(user_id=user_id),
        user_id=user_id,
        messages=messages,
        logger=logger,
    )
    assert handshake["proc_msg_id"] == app.sent_messages[-1].id
    assert app.edited[-1]["text"] == "started"
    assert schedule_calls


def test_playlist_error_summary_tracks_reasons_and_clears():
    error_key = "u_p"
    clear_playlist_error_state(error_key)

    mark_playlist_error(error_key, reason="gallery_fallback_failed")
    mark_playlist_error(error_key, reason="gallery_fallback_failed")
    mark_playlist_error(error_key, reason="download_attempt_failed")

    summary = get_playlist_error_summary(error_key)
    assert summary == {
        "count": 3,
        "reasons": {
            "gallery_fallback_failed": 2,
            "download_attempt_failed": 1,
        },
    }

    clear_playlist_error_state(error_key)
    assert get_playlist_error_summary(error_key) is None
