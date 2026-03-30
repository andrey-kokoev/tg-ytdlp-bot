from types import SimpleNamespace

from HELPERS.ingress_models import build_telegram_command_envelope, build_telegram_message_envelope
from HELPERS.ingress_requests import (
    build_audio_download_request,
    build_ask_filter_selection_request,
    build_ask_quality_selection_request,
    build_concat_request,
    build_cookie_menu_selection_request,
    build_cookie_upload_request,
    build_format_menu_selection_request,
    build_image_range_selection_request,
    build_rename_request,
    build_subtitle_only_request,
    build_subtitle_settings_selection_request,
    build_url_download_request,
)
from HELPERS.ingress_models import build_telegram_callback_envelope, build_telegram_document_envelope


def test_build_telegram_command_envelope_preserves_command_context():
    message = SimpleNamespace(
        text="/sub --text-only https://youtu.be/example",
        caption=None,
        id=55,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["sub", "--text-only", "https://youtu.be/example"],
    )
    envelope = build_telegram_command_envelope(message, raw_text="/sub https://youtu.be/example")
    assert envelope.transport == "telegram"
    assert envelope.event_kind == "command_message"
    assert envelope.user_id == 91363026
    assert envelope.source_message_id == 55
    assert envelope.raw_text == "/sub https://youtu.be/example"
    assert envelope.raw_payload["command_tokens"] == ["sub", "--text-only", "https://youtu.be/example"]


def test_build_telegram_message_envelope_defaults_text_event_for_plain_text():
    message = SimpleNamespace(
        text="https://youtube.com/playlist?list=abc*2*5",
        caption=None,
        id=56,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=[],
    )
    envelope = build_telegram_message_envelope(message)
    assert envelope.transport == "telegram"
    assert envelope.event_kind == "text_message"
    assert envelope.user_id == 91363026
    assert envelope.source_message_id == 56
    assert envelope.raw_text == "https://youtube.com/playlist?list=abc*2*5"
    assert envelope.raw_payload["command_tokens"] == []


def test_build_subtitle_only_request_from_envelope():
    message = SimpleNamespace(
        text="/sub --text-only https://youtu.be/example",
        caption=None,
        id=77,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["sub", "--text-only", "https://youtu.be/example"],
    )
    envelope = build_telegram_command_envelope(message, raw_text="/sub https://youtu.be/example")
    request = build_subtitle_only_request(
        envelope,
        url="https://youtu.be/example",
        tags=["#tag1"],
        text_only=True,
        playlist_name=None,
        video_count=1,
        video_start_with=1,
    )
    assert request.request_kind == "SubtitleOnlyRequested"
    assert request.user_id == 91363026
    assert request.url == "https://youtu.be/example"
    assert request.subtitle_mode == "text_only"
    assert request.text_only is True
    assert request.tags == ["#tag1"]
    assert request.provenance["command_tokens"] == ["sub", "--text-only", "https://youtu.be/example"]


def test_build_concat_request_from_envelope():
    message = SimpleNamespace(
        text="/concat reverse 1-11 https://youtube.com/playlist?list=abc",
        caption=None,
        id=88,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["concat", "reverse", "1-11", "https://youtube.com/playlist?list=abc"],
    )
    envelope = build_telegram_command_envelope(
        message,
        raw_text="/concat 1-11 https://youtube.com/playlist?list=abc",
    )
    request = build_concat_request(
        envelope,
        url="https://youtube.com/playlist?list=abc",
        media_mode="video",
        reverse_output=True,
        output_name_override="My Mix",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_count=11,
        video_start_with=1,
        video_end_with=11,
    )
    assert request.request_kind == "ConcatRequested"
    assert request.user_id == 91363026
    assert request.media_mode == "video"
    assert request.reverse_output is True
    assert request.concat_ordering == "reverse"
    assert request.concat_policy == "direct_concat_only"
    assert request.chapter_policy == "none"
    assert request.output_name_override == "My Mix"
    assert request.provenance["command_tokens"] == ["concat", "reverse", "1-11", "https://youtube.com/playlist?list=abc"]


def test_build_rename_request_from_envelope():
    message = SimpleNamespace(
        text='/rename "My Better Mix"',
        caption=None,
        id=99,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["rename", "My Better Mix"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_rename_request(
        envelope,
        target_kind="audio_concat",
        new_name="My Better Mix",
    )
    assert request.request_kind == "RenameRequested"
    assert request.user_id == 91363026
    assert request.target_kind == "audio_concat"
    assert request.new_name == "My Better Mix"
    assert request.provenance["command_tokens"] == ["rename", "My Better Mix"]


def test_build_audio_download_request_from_envelope():
    message = SimpleNamespace(
        text="/audio 1-3 https://youtu.be/example",
        caption=None,
        id=111,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["audio", "1-3", "https://youtu.be/example"],
    )
    envelope = build_telegram_command_envelope(
        message,
        raw_text="/audio https://youtu.be/example*1*3",
    )
    request = build_audio_download_request(
        envelope,
        url="https://youtu.be/example",
        quality_key="mp3",
        format_override="ba",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_count=3,
        video_start_with=1,
    )
    assert request.request_kind == "AudioDownloadRequested"
    assert request.user_id == 91363026
    assert request.url == "https://youtu.be/example"
    assert request.quality_key == "mp3"
    assert request.format_override == "ba"
    assert request.tags == ["#tag1"]
    assert request.tags_text == "#tag1"
    assert request.playlist_name == "Playlist"
    assert request.video_count == 3
    assert request.video_start_with == 1
    assert request.provenance["command_tokens"] == ["audio", "1-3", "https://youtu.be/example"]


def test_build_url_download_request_from_envelope():
    message = SimpleNamespace(
        text="https://youtube.com/playlist?list=abc*2*5 #tag1",
        caption=None,
        id=121,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=[],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_url_download_request(
        envelope,
        url="https://youtube.com/playlist?list=abc",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_start_with=2,
        video_end_with=5,
    )
    assert request.request_kind == "UrlDownloadRequested"
    assert request.user_id == 91363026
    assert request.url == "https://youtube.com/playlist?list=abc"
    assert request.tags == ["#tag1"]
    assert request.tags_text == "#tag1"
    assert request.playlist_name == "Playlist"
    assert request.video_start_with == 2
    assert request.video_end_with == 5
    assert request.provenance["command_tokens"] == []


def test_build_telegram_callback_envelope_preserves_reply_context():
    callback_query = SimpleNamespace(
        data="askq|360p",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=205,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=101),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    assert envelope.transport == "telegram"
    assert envelope.event_kind == "callback_query"
    assert envelope.user_id == 91363026
    assert envelope.chat_id == 91363026
    assert envelope.source_message_id == 205
    assert envelope.raw_data == "askq|360p"
    assert envelope.reply_context["reply_to_message_id"] == 101


def test_build_ask_quality_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="askq|other_id|140",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=305,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=201),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_ask_quality_selection_request(
        envelope,
        selection_token="other_id_140",
    )
    assert request.request_kind == "AskQualitySelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 305
    assert request.raw_input == "askq|other_id|140"
    assert request.selection_token == "other_id_140"
    assert request.original_message_id == 201
    assert request.provenance["event_kind"] == "callback_query"


def test_build_ask_filter_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="askf|codec|av01",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=405,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=301),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_ask_filter_selection_request(
        envelope,
        filter_kind="codec",
        filter_value="av01",
    )
    assert request.request_kind == "AskFilterSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 405
    assert request.raw_input == "askf|codec|av01"
    assert request.filter_kind == "codec"
    assert request.filter_value == "av01"
    assert request.original_message_id == 301
    assert request.provenance["event_kind"] == "callback_query"


def test_build_image_range_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="img_range|3|7|https://example.com/post/1",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=505,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=401),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_image_range_selection_request(
        envelope,
        start_index=3,
        end_index=7,
        url="https://example.com/post/1",
    )
    assert request.request_kind == "ImageRangeSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 505
    assert request.raw_input == "img_range|3|7|https://example.com/post/1"
    assert request.start_index == 3
    assert request.end_index == 7
    assert request.url == "https://example.com/post/1"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_telegram_document_envelope_for_cookie_upload():
    message = SimpleNamespace(
        id=606,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        document=SimpleNamespace(
            file_name="cookie.txt",
            file_size=2959,
            mime_type="text/plain",
        ),
    )
    envelope = build_telegram_document_envelope(message)
    assert envelope.transport == "telegram"
    assert envelope.event_kind == "document_message"
    assert envelope.user_id == 91363026
    assert envelope.source_message_id == 606
    assert envelope.document_name == "cookie.txt"
    assert envelope.document_size == 2959
    assert envelope.mime_type == "text/plain"


def test_build_cookie_upload_request_from_document_envelope():
    message = SimpleNamespace(
        id=607,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        document=SimpleNamespace(
            file_name="cookie.txt",
            file_size=2959,
            mime_type="text/plain",
        ),
    )
    envelope = build_telegram_document_envelope(message)
    request = build_cookie_upload_request(envelope)
    assert request.request_kind == "CookieUploadRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 607
    assert request.file_name == "cookie.txt"
    assert request.file_size == 2959
    assert request.mime_type == "text/plain"
    assert request.provenance["event_kind"] == "document_message"


def test_build_cookie_menu_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="download_cookie|from_browser",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=705,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=601),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_cookie_menu_selection_request(
        envelope,
        selection_key="from_browser",
    )
    assert request.request_kind == "CookieMenuSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 705
    assert request.raw_input == "download_cookie|from_browser"
    assert request.selection_key == "from_browser"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_subtitle_settings_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="subs_auto|toggle|2",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=805,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=701),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_subtitle_settings_selection_request(
        envelope,
        action_kind="auto",
        action_value="toggle",
        page=2,
    )
    assert request.request_kind == "SubtitleSettingsSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 805
    assert request.raw_input == "subs_auto|toggle|2"
    assert request.action_kind == "auto"
    assert request.action_value == "toggle"
    assert request.page == 2
    assert request.provenance["event_kind"] == "callback_query"


def test_build_format_menu_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="format_codec|av01",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=905,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=801),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_format_menu_selection_request(
        envelope,
        action_kind="format_codec",
        action_value="av01",
    )
    assert request.request_kind == "FormatMenuSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 905
    assert request.raw_input == "format_codec|av01"
    assert request.action_kind == "format_codec"
    assert request.action_value == "av01"
    assert request.provenance["event_kind"] == "callback_query"
