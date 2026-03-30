from types import SimpleNamespace

from HELPERS.ingress_models import build_telegram_command_envelope, build_telegram_message_envelope
from HELPERS.ingress_requests import (
    build_add_bot_to_group_selection_request,
    build_add_bot_to_group_request,
    build_args_command_request,
    build_audio_download_request,
    build_auto_cache_command_request,
    build_ask_filter_selection_request,
    build_ask_quality_selection_request,
    build_ban_time_command_request,
    build_browser_cookies_request,
    build_block_user_command_request,
    build_broadcast_command_request,
    build_check_cookie_request,
    build_clean_command_request,
    build_concat_request,
    build_cookie_menu_request,
    build_cookie_menu_selection_request,
    build_cookie_upload_request,
    build_format_command_request,
    build_keyboard_command_request,
    build_keyboard_option_selection_request,
    build_format_menu_selection_request,
    build_help_command_request,
    build_image_command_request,
    build_image_range_selection_request,
    build_language_command_request,
    build_language_selection_request,
    build_list_formats_request,
    build_link_command_request,
    build_mediainfo_command_request,
    build_mediainfo_option_selection_request,
    build_nsfw_command_request,
    build_playlist_help_request,
    build_proxy_command_request,
    build_reload_cache_command_request,
    build_rename_request,
    build_runtime_command_request,
    build_save_cookie_text_request,
    build_search_command_request,
    build_start_command_request,
    build_settings_menu_open_request,
    build_settings_command_selection_request,
    build_settings_menu_selection_request,
    build_split_command_request,
    build_tags_command_request,
    build_subtitle_only_request,
    build_subtitle_settings_command_request,
    build_subtitle_settings_selection_request,
    build_uncache_command_request,
    build_unblock_user_command_request,
    build_user_details_command_request,
    build_user_logs_command_request,
    build_usage_command_request,
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


def test_build_image_command_request_from_envelope():
    message = SimpleNamespace(
        text="/img 1-3 https://example.com/post",
        caption=None,
        id=78,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["img", "1-3", "https://example.com/post"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_image_command_request(envelope)
    assert request.request_kind == "ImageCommandRequested"
    assert request.user_id == 91363026
    assert request.chat_id == 91363026
    assert request.raw_input == "/img 1-3 https://example.com/post"
    assert request.provenance["command_tokens"] == ["img", "1-3", "https://example.com/post"]


def test_build_subtitle_settings_command_request_from_envelope():
    message = SimpleNamespace(
        text="/subs en auto",
        caption=None,
        id=67,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["subs", "en", "auto"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_subtitle_settings_command_request(envelope)
    assert request.request_kind == "SubtitleSettingsCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 67
    assert request.raw_input == "/subs en auto"
    assert request.provenance["command_tokens"] == ["subs", "en", "auto"]


def test_build_args_command_request_from_envelope():
    message = SimpleNamespace(
        text="/args",
        caption=None,
        id=66,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["args"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_args_command_request(envelope)
    assert request.request_kind == "ArgsCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 66
    assert request.raw_input == "/args"
    assert request.provenance["command_tokens"] == ["args"]


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


def test_build_settings_menu_open_request_from_envelope():
    message = SimpleNamespace(
        text="/settings",
        caption=None,
        id=112,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["settings"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_settings_menu_open_request(envelope)
    assert request.request_kind == "SettingsMenuOpenRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 112
    assert request.raw_input == "/settings"
    assert request.provenance["command_tokens"] == ["settings"]


def test_build_list_formats_request_from_envelope():
    message = SimpleNamespace(
        text="/list https://youtu.be/example",
        caption=None,
        id=113,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["list", "https://youtu.be/example"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_list_formats_request(envelope, url="https://youtu.be/example")
    assert request.request_kind == "ListFormatsRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 113
    assert request.raw_input == "/list https://youtu.be/example"
    assert request.url == "https://youtu.be/example"
    assert request.provenance["command_tokens"] == ["list", "https://youtu.be/example"]


def test_build_tags_command_request_from_envelope():
    message = SimpleNamespace(
        text="/tags",
        caption=None,
        id=114,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["tags"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_tags_command_request(envelope)
    assert request.request_kind == "TagsCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 114
    assert request.raw_input == "/tags"
    assert request.provenance["command_tokens"] == ["tags"]


def test_build_browser_cookies_request_from_envelope():
    message = SimpleNamespace(
        text="/cookies_from_browser",
        caption=None,
        id=115,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["cookies_from_browser"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_browser_cookies_request(envelope)
    assert request.request_kind == "BrowserCookiesRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 115
    assert request.raw_input == "/cookies_from_browser"
    assert request.provenance["command_tokens"] == ["cookies_from_browser"]


def test_build_cookie_menu_request_from_envelope():
    message = SimpleNamespace(
        text="/cookie youtube",
        caption=None,
        id=116,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["cookie", "youtube"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_cookie_menu_request(envelope)
    assert request.request_kind == "CookieMenuRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 116
    assert request.raw_input == "/cookie youtube"
    assert request.provenance["command_tokens"] == ["cookie", "youtube"]


def test_build_check_cookie_request_from_envelope():
    message = SimpleNamespace(
        text="/check_cookie",
        caption=None,
        id=117,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["check_cookie"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_check_cookie_request(envelope)
    assert request.request_kind == "CheckCookieRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 117
    assert request.raw_input == "/check_cookie"
    assert request.provenance["command_tokens"] == ["check_cookie"]


def test_build_save_cookie_text_request_from_envelope():
    message = SimpleNamespace(
        text="/save_as_cookie\n# Netscape HTTP Cookie File",
        caption=None,
        id=118,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["save_as_cookie"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_save_cookie_text_request(envelope)
    assert request.request_kind == "SaveCookieTextRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 118
    assert request.raw_input == "/save_as_cookie\n# Netscape HTTP Cookie File"
    assert request.provenance["command_tokens"] == ["save_as_cookie"]


def test_build_mediainfo_command_request_from_envelope():
    message = SimpleNamespace(
        text="/mediainfo on",
        caption=None,
        id=119,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["mediainfo", "on"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_mediainfo_command_request(envelope)
    assert request.request_kind == "MediaInfoCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 119
    assert request.raw_input == "/mediainfo on"
    assert request.provenance["command_tokens"] == ["mediainfo", "on"]


def test_build_mediainfo_option_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="mediainfo_option|on",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=908,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=804),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_mediainfo_option_selection_request(
        envelope,
        selection_key="on",
    )
    assert request.request_kind == "MediaInfoOptionSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 908
    assert request.raw_input == "mediainfo_option|on"
    assert request.selection_key == "on"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_language_command_request_from_envelope():
    message = SimpleNamespace(
        text="/lang ru",
        caption=None,
        id=1191,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["lang", "ru"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_language_command_request(envelope)
    assert request.request_kind == "LanguageCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1191
    assert request.raw_input == "/lang ru"
    assert request.provenance["command_tokens"] == ["lang", "ru"]


def test_build_playlist_help_request_from_envelope():
    message = SimpleNamespace(
        text="/playlist",
        caption=None,
        id=1192,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["playlist"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_playlist_help_request(envelope)
    assert request.request_kind == "PlaylistHelpRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1192
    assert request.raw_input == "/playlist"
    assert request.provenance["command_tokens"] == ["playlist"]


def test_build_help_command_request_from_envelope():
    message = SimpleNamespace(
        text="/help",
        caption=None,
        id=1193,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["help"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_help_command_request(envelope)
    assert request.request_kind == "HelpCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1193
    assert request.raw_input == "/help"
    assert request.provenance["command_tokens"] == ["help"]


def test_build_start_command_request_from_envelope():
    message = SimpleNamespace(
        text="/start",
        caption=None,
        id=1194,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["start"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_start_command_request(envelope)
    assert request.request_kind == "StartCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1194
    assert request.raw_input == "/start"
    assert request.provenance["command_tokens"] == ["start"]


def test_build_add_bot_to_group_request_from_envelope():
    message = SimpleNamespace(
        text="/add_bot_to_group",
        caption=None,
        id=1195,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["add_bot_to_group"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_add_bot_to_group_request(envelope)
    assert request.request_kind == "AddBotToGroupRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1195
    assert request.raw_input == "/add_bot_to_group"
    assert request.provenance["command_tokens"] == ["add_bot_to_group"]


def test_build_add_bot_to_group_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="add_group_msg|close",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=911,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=807),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_add_bot_to_group_selection_request(
        envelope,
        action_kind="close",
        action_value="close",
    )
    assert request.request_kind == "AddBotToGroupSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 911
    assert request.raw_input == "add_group_msg|close"
    assert request.action_kind == "close"
    assert request.action_value == "close"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_usage_command_request_from_envelope():
    message = SimpleNamespace(
        text="/usage",
        caption=None,
        id=1196,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["usage"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_usage_command_request(envelope)
    assert request.request_kind == "UsageCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1196
    assert request.raw_input == "/usage"
    assert request.provenance["command_tokens"] == ["usage"]


def test_build_uncache_command_request_from_envelope():
    message = SimpleNamespace(
        text="/uncache https://example.com/video",
        caption=None,
        id=1197,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["uncache", "https://example.com/video"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_uncache_command_request(envelope)
    assert request.request_kind == "UncacheCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1197
    assert request.raw_input == "/uncache https://example.com/video"
    assert request.provenance["command_tokens"] == ["uncache", "https://example.com/video"]


def test_build_reload_cache_command_request_from_envelope():
    message = SimpleNamespace(
        text="/reload_cache",
        caption=None,
        id=1198,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["reload_cache"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_reload_cache_command_request(envelope)
    assert request.request_kind == "ReloadCacheCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1198
    assert request.raw_input == "/reload_cache"
    assert request.provenance["command_tokens"] == ["reload_cache"]


def test_build_auto_cache_command_request_from_envelope():
    message = SimpleNamespace(
        text="/auto_cache on",
        caption=None,
        id=1200,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["auto_cache", "on"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_auto_cache_command_request(envelope)
    assert request.request_kind == "AutoCacheCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1200
    assert request.raw_input == "/auto_cache on"
    assert request.provenance["command_tokens"] == ["auto_cache", "on"]


def test_build_runtime_command_request_from_envelope():
    message = SimpleNamespace(
        text="/run_time",
        caption=None,
        id=1201,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["run_time"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_runtime_command_request(envelope)
    assert request.request_kind == "RuntimeCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1201
    assert request.raw_input == "/run_time"
    assert request.provenance["command_tokens"] == ["run_time"]


def test_build_user_logs_command_request_from_envelope():
    message = SimpleNamespace(
        text="/log 91363026",
        caption=None,
        id=1202,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["log", "91363026"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_user_logs_command_request(envelope)
    assert request.request_kind == "UserLogsCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1202
    assert request.raw_input == "/log 91363026"
    assert request.provenance["command_tokens"] == ["log", "91363026"]


def test_build_user_details_command_request_from_envelope():
    message = SimpleNamespace(
        text="/all 91363026",
        caption=None,
        id=1203,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["all", "91363026"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_user_details_command_request(envelope)
    assert request.request_kind == "UserDetailsCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1203
    assert request.raw_input == "/all 91363026"
    assert request.provenance["command_tokens"] == ["all", "91363026"]


def test_build_ban_time_command_request_from_envelope():
    message = SimpleNamespace(
        text="/ban_time 15m",
        caption=None,
        id=1204,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["ban_time", "15m"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_ban_time_command_request(envelope)
    assert request.request_kind == "BanTimeCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1204
    assert request.raw_input == "/ban_time 15m"
    assert request.provenance["command_tokens"] == ["ban_time", "15m"]


def test_build_broadcast_command_request_from_envelope():
    message = SimpleNamespace(
        text="/broadcast hello world",
        caption=None,
        id=1205,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["broadcast", "hello", "world"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_broadcast_command_request(envelope)
    assert request.request_kind == "BroadcastCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1205
    assert request.raw_input == "/broadcast hello world"
    assert request.provenance["command_tokens"] == ["broadcast", "hello", "world"]


def test_build_block_user_command_request_from_envelope():
    message = SimpleNamespace(
        text="/block 91363026",
        caption=None,
        id=1207,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["block", "91363026"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_block_user_command_request(envelope)
    assert request.request_kind == "BlockUserCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1207
    assert request.raw_input == "/block 91363026"
    assert request.provenance["command_tokens"] == ["block", "91363026"]


def test_build_unblock_user_command_request_from_envelope():
    message = SimpleNamespace(
        text="/unblock 91363026",
        caption=None,
        id=1208,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["unblock", "91363026"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_unblock_user_command_request(envelope)
    assert request.request_kind == "UnblockUserCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1208
    assert request.raw_input == "/unblock 91363026"
    assert request.provenance["command_tokens"] == ["unblock", "91363026"]


def test_build_clean_command_request_from_envelope():
    message = SimpleNamespace(
        text="/clean all",
        caption=None,
        id=1206,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["clean", "all"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_clean_command_request(envelope)
    assert request.request_kind == "CleanCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 1206
    assert request.raw_input == "/clean all"
    assert request.provenance["command_tokens"] == ["clean", "all"]


def test_build_language_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="lang_select_ru",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=910,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=806),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_language_selection_request(
        envelope,
        action_kind="select",
        action_value="ru",
    )
    assert request.request_kind == "LanguageSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 910
    assert request.raw_input == "lang_select_ru"
    assert request.action_kind == "select"
    assert request.action_value == "ru"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_format_command_request_from_envelope():
    message = SimpleNamespace(
        text="/format best",
        caption=None,
        id=120,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["format", "best"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_format_command_request(envelope)
    assert request.request_kind == "FormatCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 120
    assert request.raw_input == "/format best"
    assert request.provenance["command_tokens"] == ["format", "best"]


def test_build_link_command_request_from_envelope():
    message = SimpleNamespace(
        text="/link 720 https://youtu.be/example",
        caption=None,
        id=120,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["link", "720", "https://youtu.be/example"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_link_command_request(envelope)
    assert request.request_kind == "LinkCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 120
    assert request.raw_input == "/link 720 https://youtu.be/example"
    assert request.provenance["command_tokens"] == ["link", "720", "https://youtu.be/example"]


def test_build_search_command_request_from_envelope():
    message = SimpleNamespace(
        text="/search kittens",
        caption=None,
        id=121,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["search", "kittens"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_search_command_request(envelope)
    assert request.request_kind == "SearchCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 121
    assert request.raw_input == "/search kittens"
    assert request.provenance["command_tokens"] == ["search", "kittens"]


def test_build_keyboard_command_request_from_envelope():
    message = SimpleNamespace(
        text="/keyboard full",
        caption=None,
        id=122,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["keyboard", "full"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_keyboard_command_request(envelope)
    assert request.request_kind == "KeyboardCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 122
    assert request.raw_input == "/keyboard full"
    assert request.provenance["command_tokens"] == ["keyboard", "full"]


def test_build_keyboard_option_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="keyboard|FULL",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=909,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=805),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_keyboard_option_selection_request(
        envelope,
        selection_key="FULL",
    )
    assert request.request_kind == "KeyboardOptionSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 909
    assert request.raw_input == "keyboard|FULL"
    assert request.selection_key == "FULL"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_proxy_command_request_from_envelope():
    message = SimpleNamespace(
        text="/proxy on",
        caption=None,
        id=123,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["proxy", "on"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_proxy_command_request(envelope)
    assert request.request_kind == "ProxyCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 123
    assert request.raw_input == "/proxy on"
    assert request.provenance["command_tokens"] == ["proxy", "on"]


def test_build_nsfw_command_request_from_envelope():
    message = SimpleNamespace(
        text="/nsfw off",
        caption=None,
        id=124,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["nsfw", "off"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_nsfw_command_request(envelope)
    assert request.request_kind == "NsfwCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 124
    assert request.raw_input == "/nsfw off"
    assert request.provenance["command_tokens"] == ["nsfw", "off"]


def test_build_split_command_request_from_envelope():
    message = SimpleNamespace(
        text="/split 500mb",
        caption=None,
        id=125,
        chat=SimpleNamespace(id=91363026),
        reply_to_message=None,
        command=["split", "500mb"],
    )
    envelope = build_telegram_command_envelope(message)
    request = build_split_command_request(envelope)
    assert request.request_kind == "SplitCommandRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 125
    assert request.raw_input == "/split 500mb"
    assert request.provenance["command_tokens"] == ["split", "500mb"]


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


def test_build_settings_menu_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="settings__menu__media",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=906,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=802),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_settings_menu_selection_request(
        envelope,
        selection_key="media",
    )
    assert request.request_kind == "SettingsMenuSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 906
    assert request.raw_input == "settings__menu__media"
    assert request.selection_key == "media"
    assert request.provenance["event_kind"] == "callback_query"


def test_build_settings_command_selection_request_from_callback_envelope():
    callback_query = SimpleNamespace(
        data="settings__cmd__subs",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(
            id=907,
            chat=SimpleNamespace(id=91363026),
            reply_to_message=SimpleNamespace(id=803),
        ),
    )
    envelope = build_telegram_callback_envelope(callback_query)
    request = build_settings_command_selection_request(
        envelope,
        selection_key="subs",
    )
    assert request.request_kind == "SettingsCommandSelectionRequested"
    assert request.user_id == 91363026
    assert request.source_message_id == 907
    assert request.raw_input == "settings__cmd__subs"
    assert request.selection_key == "subs"
    assert request.provenance["event_kind"] == "callback_query"
