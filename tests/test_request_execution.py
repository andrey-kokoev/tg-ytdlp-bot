import sys
from types import ModuleType, SimpleNamespace

from HELPERS.ingress_models import (
    AddBotToGroupSelectionRequested,
    AddBotToGroupRequested,
    ArgsCommandRequested,
    ArgsTextInputRequested,
    ArgsMenuSelectionRequested,
    AudioDownloadRequested,
    AutoCacheCommandRequested,
    AskFilterSelectionRequested,
    BanTimeCommandRequested,
    BrowserCookieSelectionRequested,
    BrowserCookiesRequested,
    BlockUserCommandRequested,
    BroadcastCommandRequested,
    CheckPornCommandRequested,
    CheckCookieRequested,
    CleanCommandRequested,
    CleanOptionSelectionRequested,
    CookieMenuRequested,
    GalleryFallbackSelectionRequested,
    ImageRangeSelectionRequested,
    KeyboardCommandRequested,
    KeyboardOptionSelectionRequested,
    LanguageCommandRequested,
    LanguageSelectionRequested,
    ListFormatsRequested,
    LinkCommandRequested,
    MediaInfoCommandRequested,
    MediaInfoOptionSelectionRequested,
    NsfwCommandRequested,
    AskQualitySelectionRequested,
    PlaylistHelpRequested,
    ConcatRequested,
    CloseMessageRequested,
    CookieMenuSelectionRequested,
    FormatCommandRequested,
    FormatMenuSelectionRequested,
    HelpCommandRequested,
    ImageCommandRequested,
    NsfwOptionSelectionRequested,
    ProxyCommandRequested,
    ProxyOptionSelectionRequested,
    ReloadCacheCommandRequested,
    ReloadPornCommandRequested,
    RenameRequested,
    RuntimeCommandRequested,
    SaveCookieTextRequested,
    SearchCommandRequested,
    StartCommandRequested,
    SettingsMenuOpenRequested,
    SettingsCommandSelectionRequested,
    SettingsMenuSelectionRequested,
    SplitCommandRequested,
    TagsCommandRequested,
    SplitSizeSelectionRequested,
    SubtitleOnlyRequested,
    SubtitleSettingsCommandRequested,
    SubtitleSettingsSelectionRequested,
    UncacheCommandRequested,
    UnblockUserCommandRequested,
    UpdatePornCommandRequested,
    UserDetailsCommandRequested,
    UserLogsCommandRequested,
    UsageCommandRequested,
    UrlDownloadRequested,
)
from HELPERS.request_execution import (
    TelegramExecutionContext,
    build_callback_execution_context,
    build_message_execution_context,
    clear_user_playlist_error_state,
    derive_url_runtime_media_policy,
    derive_saved_format_quality_key,
    derive_playlist_start_index,
    is_url_blacklisted,
    handle_add_bot_to_group_selection_request,
    handle_add_bot_to_group_request,
    handle_auto_cache_command_request,
    handle_audio_download_request,
    handle_args_command_request,
    handle_args_menu_selection_request,
    handle_args_text_input_request,
    handle_ask_filter_selection_request,
    handle_ask_quality_selection_request,
    handle_ban_time_command_request,
    handle_browser_cookie_selection_request,
    handle_browser_cookies_request,
    handle_block_user_command_request,
    handle_broadcast_command_request,
    handle_check_porn_command_request,
    handle_check_cookie_request,
    handle_clean_command_request,
    handle_clean_option_selection_request,
    handle_close_message_request,
    handle_cookie_menu_request,
    handle_cookie_menu_selection_request,
    handle_format_command_request,
    handle_format_menu_selection_request,
    handle_gallery_fallback_selection_request,
    handle_help_command_request,
    handle_image_command_request,
    handle_image_range_selection_request,
    handle_keyboard_command_request,
    handle_keyboard_option_selection_request,
    handle_language_command_request,
    handle_language_selection_request,
    handle_list_formats_request,
    handle_link_command_request,
    handle_mediainfo_command_request,
    handle_mediainfo_option_selection_request,
    handle_nsfw_command_request,
    handle_nsfw_option_selection_request,
    handle_playlist_help_request,
    handle_proxy_command_request,
    handle_proxy_option_selection_request,
    handle_reload_cache_command_request,
    handle_reload_porn_command_request,
    handle_concat_request,
    handle_rename_request,
    handle_runtime_command_request,
    handle_saved_format_url_runtime,
    handle_save_cookie_text_request,
    handle_search_command_request,
    handle_start_command_request,
    handle_settings_menu_open_request,
    handle_settings_command_selection_request,
    handle_settings_menu_selection_request,
    handle_split_command_request,
    handle_tags_command_request,
    handle_split_size_selection_request,
    handle_subtitle_only_request,
    handle_subtitle_settings_command_request,
    handle_subtitle_settings_selection_request,
    handle_uncache_command_request,
    handle_unblock_user_command_request,
    handle_update_porn_command_request,
    handle_user_details_command_request,
    handle_user_logs_command_request,
    handle_usage_command_request,
    handle_url_quality_menu_runtime,
    handle_url_download_request,
    normalize_url_download_runtime_request,
    resolve_saved_format_policy,
    send_url_runtime_error,
    send_url_tag_error,
    send_url_wait_download_notice,
)
from pathlib import Path


def test_build_message_execution_context_preserves_message_identity():
    message = SimpleNamespace(
        id=77,
        chat=SimpleNamespace(id=91363026),
        message_thread_id=555,
    )

    context = build_message_execution_context(message)

    assert context == TelegramExecutionContext(
        chat_id=91363026,
        source_message_id=77,
        source_message=message,
        callback_query=None,
        message_thread_id=555,
    )


def test_build_callback_execution_context_preserves_callback_message_identity():
    message = SimpleNamespace(
        id=88,
        chat=SimpleNamespace(id=91363026),
        message_thread_id=777,
    )
    callback_query = SimpleNamespace(message=message)

    context = build_callback_execution_context(callback_query)

    assert context == TelegramExecutionContext(
        chat_id=91363026,
        source_message_id=88,
        source_message=message,
        callback_query=callback_query,
        message_thread_id=777,
    )


def test_handle_args_command_request_routes_request_to_args_runtime(monkeypatch):
    captured = {}

    def fake_args_command_logic(app, message, request=None):
        captured["args_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_args_module = ModuleType("COMMANDS.args_cmd")
    fake_args_module.args_command_logic = fake_args_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.args_cmd", fake_args_module)

    request = ArgsCommandRequested(
        request_kind="ArgsCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=67,
        source_transport="telegram",
        raw_input="/args",
        provenance={"event_kind": "command_message", "command_tokens": ["args"]},
    )
    app = object()
    message = SimpleNamespace(id=67, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_args_command_request(app, execution_context, request)

    assert captured["args_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_args_menu_selection_request_routes_request_to_args_callback_runtime(monkeypatch):
    captured = {}

    def fake_args_callback_logic(app, callback_query, request=None):
        captured["args_callback_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_args_module = ModuleType("COMMANDS.args_cmd")
    fake_args_module.args_callback_logic = fake_args_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.args_cmd", fake_args_module)

    request = ArgsMenuSelectionRequested(
        request_kind="ArgsMenuSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=67,
        source_transport="telegram_callback",
        raw_input="args_view_current",
        provenance={"event_kind": "callback_query"},
        action_key="args_view_current",
    )
    app = object()
    callback_query = SimpleNamespace(
        data="args_view_current",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(id=67, chat=SimpleNamespace(id=91363026)),
    )
    execution_context = build_callback_execution_context(callback_query)

    handle_args_menu_selection_request(app, execution_context, request)

    assert captured["args_callback_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_args_text_input_request_routes_request_to_args_text_runtime(monkeypatch):
    captured = {}

    def fake_handle_args_text_input(app, message, request=None):
        captured["args_text_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_args_module = ModuleType("COMMANDS.args_cmd")
    fake_args_module.handle_args_text_input = fake_handle_args_text_input
    monkeypatch.setitem(sys.modules, "COMMANDS.args_cmd", fake_args_module)

    request = ArgsTextInputRequested(
        request_kind="ArgsTextInputRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=68,
        source_transport="telegram",
        raw_input="custom value",
        provenance={"event_kind": "args_text_input"},
    )
    app = object()
    message = SimpleNamespace(id=68, chat=SimpleNamespace(id=91363026), text="custom value")
    execution_context = build_message_execution_context(message)

    handle_args_text_input_request(app, execution_context, request)

    assert captured["args_text_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_subtitle_settings_command_request_routes_request_to_subs_runtime(monkeypatch):
    captured = {}

    def fake_subs_command_logic(app, message, request=None):
        captured["subs_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_subtitles_module = ModuleType("COMMANDS.subtitles_cmd")
    fake_subtitles_module.subs_command_logic = fake_subs_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.subtitles_cmd", fake_subtitles_module)

    request = SubtitleSettingsCommandRequested(
        request_kind="SubtitleSettingsCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=68,
        source_transport="telegram",
        raw_input="/subs en auto",
        provenance={"event_kind": "command_message", "command_tokens": ["subs", "en", "auto"]},
    )
    app = object()
    message = SimpleNamespace(id=68, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_subtitle_settings_command_request(app, execution_context, request)

    assert captured["subs_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_subtitle_only_request_routes_request_to_subtitle_runtime(monkeypatch):
    captured = {}

    def fake_save_user_tags(user_id, tags):
        captured["saved_tags"] = (user_id, list(tags))

    def fake_get_or_compute_subs_langs(user_id, url):
        captured["langs_for"] = (user_id, url)
        return ["en"], ["ru"]

    def fake_download_subtitles_only(
        app,
        message,
        url,
        tags,
        available_langs,
        playlist_name=None,
        video_count=1,
        video_start_with=1,
        text_only=False,
    ):
        captured["download_call"] = {
            "app": app,
            "message": message,
            "url": url,
            "tags": list(tags),
            "available_langs": list(available_langs),
            "playlist_name": playlist_name,
            "video_count": video_count,
            "video_start_with": video_start_with,
            "text_only": text_only,
        }

    fake_subtitles_module = ModuleType("COMMANDS.subtitles_cmd")
    fake_subtitles_module.get_or_compute_subs_langs = fake_get_or_compute_subs_langs
    fake_subtitles_module.download_subtitles_only = fake_download_subtitles_only
    fake_tags_module = ModuleType("URL_PARSERS.tags")
    fake_tags_module.save_user_tags = fake_save_user_tags

    monkeypatch.setitem(sys.modules, "COMMANDS.subtitles_cmd", fake_subtitles_module)
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tags", fake_tags_module)

    request = SubtitleOnlyRequested(
        request_kind="SubtitleOnlyRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=77,
        source_transport="telegram",
        raw_input="/sub --text-only https://youtu.be/example",
        provenance={"event_kind": "command_message"},
        url="https://youtu.be/example",
        subtitle_mode="text_only",
        text_only=True,
        tags=["#tag1"],
        playlist_name="Playlist",
        video_count=1,
        video_start_with=1,
    )
    app = object()
    message = SimpleNamespace(id=77, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_subtitle_only_request(app, execution_context, request)

    assert captured["saved_tags"] == (91363026, ["#tag1"])
    assert captured["langs_for"] == (91363026, "https://youtu.be/example")
    assert captured["download_call"] == {
        "app": app,
        "message": message,
        "url": "https://youtu.be/example",
        "tags": ["#tag1"],
        "available_langs": ["en", "ru"],
        "playlist_name": "Playlist",
        "video_count": 1,
        "video_start_with": 1,
        "text_only": True,
    }


def test_handle_ask_quality_selection_request_routes_request_to_callback_runtime(monkeypatch):
    captured = {}

    def fake_askq_callback_logic(
        app,
        execution_context,
        data,
        original_message,
        url,
        tags_text,
        available_langs,
        proc_msg=None,
    ):
        captured["askq_call"] = {
            "app": app,
            "execution_context": execution_context,
            "data": data,
            "original_message": original_message,
            "url": url,
            "tags_text": tags_text,
            "available_langs": available_langs,
            "proc_msg": proc_msg,
        }

    fake_menu_module = ModuleType("DOWN_AND_UP.always_ask_menu")
    fake_menu_module.askq_callback_logic = fake_askq_callback_logic
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.always_ask_menu", fake_menu_module)

    request = AskQualitySelectionRequested(
        request_kind="AskQualitySelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=205,
        source_transport="telegram",
        raw_input="askq|360p",
        provenance={"event_kind": "callback_query"},
        selection_token="360p",
        original_message_id=101,
    )
    app = object()
    callback_query = SimpleNamespace(id="cbq")
    original_message = SimpleNamespace(id=101)
    execution_context = TelegramExecutionContext(
        chat_id=91363026,
        source_message_id=205,
        source_message=original_message,
        callback_query=callback_query,
        message_thread_id=None,
    )
    proc_msg = SimpleNamespace(id=301)

    handle_ask_quality_selection_request(
        app,
        execution_context,
        request,
        original_message=original_message,
        url="https://youtube.com/watch?v=abc",
        tags_text="#tag1",
        available_langs=["en", "ru"],
        proc_msg=proc_msg,
    )

    assert captured["askq_call"] == {
        "app": app,
        "execution_context": execution_context,
        "data": "360p",
        "original_message": original_message,
        "url": "https://youtube.com/watch?v=abc",
        "tags_text": "#tag1",
        "available_langs": ["en", "ru"],
        "proc_msg": proc_msg,
    }


def test_handle_ask_filter_selection_request_routes_request_to_callback_runtime(monkeypatch):
    captured = {}

    def fake_ask_filter_callback_logic(app, execution_context, request):
        captured["askf_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_menu_module = ModuleType("DOWN_AND_UP.always_ask_menu")
    fake_menu_module.ask_filter_callback_logic = fake_ask_filter_callback_logic
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.always_ask_menu", fake_menu_module)

    request = AskFilterSelectionRequested(
        request_kind="AskFilterSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=206,
        source_transport="telegram",
        raw_input="askf|codec|avc1",
        provenance={"event_kind": "callback_query"},
        filter_kind="codec",
        filter_value="avc1",
        original_message_id=101,
    )
    app = object()
    callback_query = SimpleNamespace(id="cbq")
    execution_context = TelegramExecutionContext(
        chat_id=91363026,
        source_message_id=206,
        source_message=None,
        callback_query=callback_query,
        message_thread_id=None,
    )

    handle_ask_filter_selection_request(
        app,
        execution_context,
        request,
    )

    assert captured["askf_call"] == {
        "app": app,
        "execution_context": execution_context,
        "request": request,
    }


def test_handle_image_range_selection_request_routes_request_to_image_runtime(monkeypatch):
    captured = {}

    def fake_fake_message(
        text,
        user_id,
        original_chat_id=None,
        message_thread_id=None,
        original_message=None,
    ):
        captured["fake_message_call"] = {
            "text": text,
            "user_id": user_id,
            "original_chat_id": original_chat_id,
            "message_thread_id": message_thread_id,
            "original_message": original_message,
        }
        return {"mock_message": text}

    def fake_image_command(app, message):
        captured["image_command_call"] = {"app": app, "message": message}

    fake_safe_messeger_module = ModuleType("HELPERS.safe_messeger")
    fake_safe_messeger_module.fake_message = fake_fake_message
    fake_image_module = ModuleType("COMMANDS.image_cmd")
    fake_image_module.image_command = fake_image_command
    monkeypatch.setitem(sys.modules, "HELPERS.safe_messeger", fake_safe_messeger_module)
    monkeypatch.setitem(sys.modules, "COMMANDS.image_cmd", fake_image_module)

    request = ImageRangeSelectionRequested(
        request_kind="ImageRangeSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=401,
        source_transport="telegram",
        raw_input="img_range|2|5|https://example.com/gallery",
        provenance={"event_kind": "callback_query"},
        start_index=2,
        end_index=5,
        url="https://example.com/gallery",
    )
    app = object()
    callback_query = SimpleNamespace(
        message=SimpleNamespace(
            chat=SimpleNamespace(id=91363026),
            message_thread_id=777,
        )
    )
    execution_context = build_callback_execution_context(callback_query)

    handle_image_range_selection_request(app, execution_context, request)

    assert captured["fake_message_call"] == {
        "text": "/img 2-5 https://example.com/gallery",
        "user_id": 91363026,
        "original_chat_id": 91363026,
        "message_thread_id": 777,
        "original_message": callback_query.message,
    }
    assert captured["image_command_call"] == {
        "app": app,
        "message": {"mock_message": "/img 2-5 https://example.com/gallery"},
    }


def test_handle_cookie_menu_selection_request_routes_request_to_cookie_runtime(monkeypatch):
    captured = {}

    def fake_handle_cookie_menu_selection(
        app,
        *,
        user_id,
        selection_key,
        message,
        callback_query=None,
    ):
        captured["cookie_selection_call"] = {
            "app": app,
            "user_id": user_id,
            "selection_key": selection_key,
            "message": message,
            "callback_query": callback_query,
        }

    fake_cookies_module = ModuleType("COMMANDS.cookies_cmd")
    fake_cookies_module._handle_cookie_menu_selection = fake_handle_cookie_menu_selection
    monkeypatch.setitem(sys.modules, "COMMANDS.cookies_cmd", fake_cookies_module)

    request = CookieMenuSelectionRequested(
        request_kind="CookieMenuSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=501,
        source_transport="telegram",
        raw_input="download_cookie|youtube",
        provenance={"event_kind": "callback_query"},
        selection_key="youtube",
    )
    app = object()
    callback_query = SimpleNamespace(
        message=SimpleNamespace(id=501, chat=SimpleNamespace(id=91363026)),
    )
    execution_context = build_callback_execution_context(callback_query)

    handle_cookie_menu_selection_request(app, execution_context, request)

    assert captured["cookie_selection_call"] == {
        "app": app,
        "user_id": 91363026,
        "selection_key": "youtube",
        "message": callback_query.message,
        "callback_query": callback_query,
    }


def test_handle_subtitle_settings_selection_request_routes_request_to_subtitle_runtime(monkeypatch):
    captured = {}

    def fake_subtitle_settings_callback_logic(app, callback_query, request):
        captured["subtitle_settings_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_subtitles_module = ModuleType("COMMANDS.subtitles_cmd")
    fake_subtitles_module.subtitle_settings_callback_logic = fake_subtitle_settings_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.subtitles_cmd", fake_subtitles_module)

    request = SubtitleSettingsSelectionRequested(
        request_kind="SubtitleSettingsSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=601,
        source_transport="telegram",
        raw_input="subs_auto|toggle|0",
        provenance={"event_kind": "callback_query"},
        action_kind="auto",
        action_value="toggle",
        page=0,
    )
    app = object()
    callback_query = SimpleNamespace(id="cbq", message=None)
    execution_context = build_callback_execution_context(callback_query)

    handle_subtitle_settings_selection_request(app, execution_context, request)

    assert captured["subtitle_settings_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_format_menu_selection_request_routes_request_to_format_runtime(monkeypatch):
    captured = {}

    def fake_format_menu_callback_logic(app, callback_query, request):
        captured["format_menu_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_format_module = ModuleType("COMMANDS.format_cmd")
    fake_format_module.format_menu_callback_logic = fake_format_menu_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.format_cmd", fake_format_module)

    request = FormatMenuSelectionRequested(
        request_kind="FormatMenuSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=602,
        source_transport="telegram",
        raw_input="format_option|others",
        provenance={"event_kind": "callback_query"},
        action_kind="format_option",
        action_value="others",
    )
    app = object()
    callback_query = SimpleNamespace(id="cbq", message=None)
    execution_context = build_callback_execution_context(callback_query)

    handle_format_menu_selection_request(app, execution_context, request)

    assert captured["format_menu_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_format_command_request_routes_request_to_format_runtime(monkeypatch):
    captured = {}

    def fake_set_format_logic(app, message, request=None):
        captured["format_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_format_module = ModuleType("COMMANDS.format_cmd")
    fake_format_module.set_format_logic = fake_set_format_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.format_cmd", fake_format_module)

    request = FormatCommandRequested(
        request_kind="FormatCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=610,
        source_transport="telegram",
        raw_input="/format best",
        provenance={"event_kind": "command_message", "command_tokens": ["format", "best"]},
    )
    app = object()
    message = SimpleNamespace(id=610, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_format_command_request(app, execution_context, request)

    assert captured["format_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_settings_menu_selection_request_routes_request_to_settings_runtime(monkeypatch):
    captured = {}

    def fake_settings_menu_callback_logic(app, callback_query, request):
        captured["settings_menu_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_settings_module = ModuleType("COMMANDS.settings_cmd")
    fake_settings_module.settings_menu_callback_logic = fake_settings_menu_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.settings_cmd", fake_settings_module)

    request = SettingsMenuSelectionRequested(
        request_kind="SettingsMenuSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=603,
        source_transport="telegram",
        raw_input="settings__menu__more",
        provenance={"event_kind": "callback_query"},
        selection_key="more",
    )
    app = object()
    callback_query = SimpleNamespace(id="cbq", message=None)
    execution_context = build_callback_execution_context(callback_query)

    handle_settings_menu_selection_request(app, execution_context, request)

    assert captured["settings_menu_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_settings_menu_open_request_routes_request_to_settings_runtime(monkeypatch):
    captured = {}

    def fake_settings_command_logic(app, message, request=None):
        captured["settings_open_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_settings_module = ModuleType("COMMANDS.settings_cmd")
    fake_settings_module.settings_command_logic = fake_settings_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.settings_cmd", fake_settings_module)

    request = SettingsMenuOpenRequested(
        request_kind="SettingsMenuOpenRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=602,
        source_transport="telegram",
        raw_input="/settings",
        provenance={"event_kind": "command_message", "command_tokens": ["settings"]},
    )
    app = object()
    message = SimpleNamespace(id=602, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_settings_menu_open_request(app, execution_context, request)

    assert captured["settings_open_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_settings_command_selection_request_routes_request_to_settings_runtime(monkeypatch):
    captured = {}

    def fake_settings_cmd_callback_logic(app, callback_query, request):
        captured["settings_cmd_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_settings_module = ModuleType("COMMANDS.settings_cmd")
    fake_settings_module.settings_cmd_callback_logic = fake_settings_cmd_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.settings_cmd", fake_settings_module)

    request = SettingsCommandSelectionRequested(
        request_kind="SettingsCommandSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=604,
        source_transport="telegram",
        raw_input="settings__cmd__subs",
        provenance={"event_kind": "callback_query"},
        selection_key="subs",
    )
    app = object()
    callback_query = SimpleNamespace(id="cbq", message=None)
    execution_context = build_callback_execution_context(callback_query)

    handle_settings_command_selection_request(app, execution_context, request)

    assert captured["settings_cmd_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_list_formats_request_routes_request_to_list_runtime(monkeypatch):
    captured = {}

    def fake_list_command_logic(app, message, request=None):
        captured["list_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_list_module = ModuleType("COMMANDS.list_cmd")
    fake_list_module.list_command_logic = fake_list_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.list_cmd", fake_list_module)

    request = ListFormatsRequested(
        request_kind="ListFormatsRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=605,
        source_transport="telegram",
        raw_input="/list https://youtu.be/example",
        provenance={"event_kind": "command_message", "command_tokens": ["list", "https://youtu.be/example"]},
        url="https://youtu.be/example",
    )
    app = object()
    message = SimpleNamespace(id=605, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_list_formats_request(app, execution_context, request)

    assert captured["list_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_tags_command_request_routes_request_to_tags_runtime(monkeypatch):
    captured = {}

    def fake_tags_command_logic(app, message, request=None):
        captured["tags_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_tags_module = ModuleType("COMMANDS.tag_cmd")
    fake_tags_module.tags_command_logic = fake_tags_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.tag_cmd", fake_tags_module)

    request = TagsCommandRequested(
        request_kind="TagsCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=606,
        source_transport="telegram",
        raw_input="/tags",
        provenance={"event_kind": "command_message", "command_tokens": ["tags"]},
    )
    app = object()
    message = SimpleNamespace(id=606, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_tags_command_request(app, execution_context, request)

    assert captured["tags_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_browser_cookies_request_routes_request_to_cookie_runtime(monkeypatch):
    captured = {}

    def fake_cookies_from_browser_logic(app, message, request=None):
        captured["cookies_browser_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_cookies_module = ModuleType("COMMANDS.cookies_cmd")
    fake_cookies_module.cookies_from_browser_logic = fake_cookies_from_browser_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.cookies_cmd", fake_cookies_module)

    request = BrowserCookiesRequested(
        request_kind="BrowserCookiesRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=607,
        source_transport="telegram",
        raw_input="/cookies_from_browser",
        provenance={"event_kind": "command_message", "command_tokens": ["cookies_from_browser"]},
    )
    app = object()
    message = SimpleNamespace(id=607, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_browser_cookies_request(app, execution_context, request)

    assert captured["cookies_browser_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_cookie_menu_request_routes_request_to_cookie_runtime(monkeypatch):
    captured = {}

    def fake_download_cookie_logic(app, message, request=None):
        captured["cookie_menu_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_cookies_module = ModuleType("COMMANDS.cookies_cmd")
    fake_cookies_module.download_cookie_logic = fake_download_cookie_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.cookies_cmd", fake_cookies_module)

    request = CookieMenuRequested(
        request_kind="CookieMenuRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=608,
        source_transport="telegram",
        raw_input="/cookie youtube",
        provenance={"event_kind": "command_message", "command_tokens": ["cookie", "youtube"]},
    )
    app = object()
    message = SimpleNamespace(id=608, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_cookie_menu_request(app, execution_context, request)

    assert captured["cookie_menu_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_check_cookie_request_routes_request_to_cookie_runtime(monkeypatch):
    captured = {}

    def fake_checking_cookie_file_logic(app, message, request=None):
        captured["check_cookie_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_cookies_module = ModuleType("COMMANDS.cookies_cmd")
    fake_cookies_module.checking_cookie_file_logic = fake_checking_cookie_file_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.cookies_cmd", fake_cookies_module)

    request = CheckCookieRequested(
        request_kind="CheckCookieRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=609,
        source_transport="telegram",
        raw_input="/check_cookie",
        provenance={"event_kind": "command_message", "command_tokens": ["check_cookie"]},
    )
    app = object()
    message = SimpleNamespace(id=609, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_check_cookie_request(app, execution_context, request)

    assert captured["check_cookie_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_save_cookie_text_request_routes_request_to_cookie_runtime(monkeypatch):
    captured = {}

    def fake_save_as_cookie_file_logic(app, message, request=None):
        captured["save_cookie_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_cookies_module = ModuleType("COMMANDS.cookies_cmd")
    fake_cookies_module.save_as_cookie_file_logic = fake_save_as_cookie_file_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.cookies_cmd", fake_cookies_module)

    request = SaveCookieTextRequested(
        request_kind="SaveCookieTextRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=610,
        source_transport="telegram",
        raw_input="/save_as_cookie\n# Netscape HTTP Cookie File",
        provenance={"event_kind": "command_message", "command_tokens": ["save_as_cookie"]},
    )
    app = object()
    message = SimpleNamespace(id=610, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_save_cookie_text_request(app, execution_context, request)

    assert captured["save_cookie_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_mediainfo_command_request_routes_request_to_mediainfo_runtime(monkeypatch):
    captured = {}

    def fake_mediainfo_command_logic(app, message, request=None):
        captured["mediainfo_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_mediainfo_module = ModuleType("COMMANDS.mediainfo_cmd")
    fake_mediainfo_module.mediainfo_command_logic = fake_mediainfo_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.mediainfo_cmd", fake_mediainfo_module)

    request = MediaInfoCommandRequested(
        request_kind="MediaInfoCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=611,
        source_transport="telegram",
        raw_input="/mediainfo on",
        provenance={"event_kind": "command_message", "command_tokens": ["mediainfo", "on"]},
    )
    app = object()
    message = SimpleNamespace(id=611, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_mediainfo_command_request(app, execution_context, request)

    assert captured["mediainfo_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_language_command_request_routes_request_to_lang_runtime(monkeypatch):
    captured = {}

    def fake_lang_command_logic(app, message, request=None):
        captured["lang_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_lang_module = ModuleType("COMMANDS.lang_cmd")
    fake_lang_module.lang_command_logic = fake_lang_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.lang_cmd", fake_lang_module)

    request = LanguageCommandRequested(
        request_kind="LanguageCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6111,
        source_transport="telegram",
        raw_input="/lang ru",
        provenance={"event_kind": "command_message", "command_tokens": ["lang", "ru"]},
    )
    app = object()
    message = SimpleNamespace(id=6111, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_language_command_request(app, execution_context, request)

    assert captured["lang_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_playlist_help_request_routes_request_to_playlist_runtime(monkeypatch):
    captured = {}

    def fake_playlist_command_logic(app, message, request=None):
        captured["playlist_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_other_handlers_module = ModuleType("COMMANDS.other_handlers")
    fake_other_handlers_module.playlist_command_logic = fake_playlist_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.other_handlers", fake_other_handlers_module)

    request = PlaylistHelpRequested(
        request_kind="PlaylistHelpRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6112,
        source_transport="telegram",
        raw_input="/playlist",
        provenance={"event_kind": "command_message", "command_tokens": ["playlist"]},
    )
    app = object()
    message = SimpleNamespace(id=6112, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_playlist_help_request(app, execution_context, request)

    assert captured["playlist_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_help_command_request_routes_request_to_help_runtime(monkeypatch):
    captured = {}

    def fake_help_command_logic(app, message, request=None):
        captured["help_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_other_handlers_module = ModuleType("COMMANDS.other_handlers")
    fake_other_handlers_module.help_command_logic = fake_help_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.other_handlers", fake_other_handlers_module)

    request = HelpCommandRequested(
        request_kind="HelpCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6114,
        source_transport="telegram",
        raw_input="/help",
        provenance={"event_kind": "command_message", "command_tokens": ["help"]},
    )
    app = object()
    message = SimpleNamespace(id=6114, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_help_command_request(app, execution_context, request)

    assert captured["help_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_image_command_request_routes_request_to_image_runtime(monkeypatch):
    captured = {}

    def fake_image_command_logic(app, message, request=None):
        captured["image_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_image_module = ModuleType("COMMANDS.image_cmd")
    fake_image_module.image_command_logic = fake_image_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.image_cmd", fake_image_module)

    request = ImageCommandRequested(
        request_kind="ImageCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=1140,
        source_transport="telegram",
        raw_input="/img 1-3 https://example.com/post",
        provenance={"event_kind": "command_message", "command_tokens": ["img", "1-3", "https://example.com/post"]},
    )
    app = object()
    message = SimpleNamespace(id=1140, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_image_command_request(app, execution_context, request)

    assert captured["image_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_start_command_request_routes_request_to_start_runtime(monkeypatch):
    captured = {}

    def fake_start_command_logic(app, message, request=None):
        captured["start_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_url_extractor_module = ModuleType("URL_PARSERS.url_extractor")
    fake_url_extractor_module.start_command_logic = fake_start_command_logic
    monkeypatch.setitem(sys.modules, "URL_PARSERS.url_extractor", fake_url_extractor_module)

    request = StartCommandRequested(
        request_kind="StartCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6115,
        source_transport="telegram",
        raw_input="/start",
        provenance={"event_kind": "command_message", "command_tokens": ["start"]},
    )
    app = object()
    message = SimpleNamespace(id=6115, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_start_command_request(app, execution_context, request)

    assert captured["start_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_add_bot_to_group_request_routes_request_to_add_group_runtime(monkeypatch):
    captured = {}

    def fake_add_bot_to_group_command_logic(app, message, request=None):
        captured["add_group_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_url_extractor_module = ModuleType("URL_PARSERS.url_extractor")
    fake_url_extractor_module.add_bot_to_group_command_logic = fake_add_bot_to_group_command_logic
    monkeypatch.setitem(sys.modules, "URL_PARSERS.url_extractor", fake_url_extractor_module)

    request = AddBotToGroupRequested(
        request_kind="AddBotToGroupRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6116,
        source_transport="telegram",
        raw_input="/add_bot_to_group",
        provenance={"event_kind": "command_message", "command_tokens": ["add_bot_to_group"]},
    )
    app = object()
    message = SimpleNamespace(id=6116, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_add_bot_to_group_request(app, execution_context, request)

    assert captured["add_group_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_add_bot_to_group_selection_request_routes_request_to_add_group_callback_runtime(monkeypatch):
    captured = {}

    def fake_add_group_msg_callback_logic(app, callback_query, request):
        captured["add_group_selection_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_url_extractor_module = ModuleType("URL_PARSERS.url_extractor")
    fake_url_extractor_module.add_group_msg_callback_logic = fake_add_group_msg_callback_logic
    monkeypatch.setitem(sys.modules, "URL_PARSERS.url_extractor", fake_url_extractor_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    app = object()
    request = AddBotToGroupSelectionRequested(
        request_kind="AddBotToGroupSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6117,
        source_transport="telegram",
        raw_input="add_group_msg|close",
        provenance={"event_kind": "callback_query"},
        action_kind="close",
        action_value="close",
    )

    handle_add_bot_to_group_selection_request(app, execution_context, request)

    assert captured["add_group_selection_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_usage_command_request_routes_request_to_usage_runtime(monkeypatch):
    captured = {}

    def fake_get_user_usage_stats(app, message):
        captured["usage_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.get_user_usage_stats = fake_get_user_usage_stats
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = UsageCommandRequested(
        request_kind="UsageCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6118,
        source_transport="telegram",
        raw_input="/usage",
        provenance={"event_kind": "command_message", "command_tokens": ["usage"]},
    )
    app = object()
    message = SimpleNamespace(id=6118, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_usage_command_request(app, execution_context, request)

    assert captured["usage_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_uncache_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_uncache_command(app, message):
        captured["uncache_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.uncache_command = fake_uncache_command
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = UncacheCommandRequested(
        request_kind="UncacheCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6119,
        source_transport="telegram",
        raw_input="/uncache https://example.com/video",
        provenance={"event_kind": "command_message", "command_tokens": ["uncache", "https://example.com/video"]},
    )
    app = object()
    message = SimpleNamespace(id=6119, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_uncache_command_request(app, execution_context, request)

    assert captured["uncache_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_reload_cache_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_reload_firebase_cache_command_logic(app, message, request=None):
        captured["reload_cache_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.reload_firebase_cache_command_logic = fake_reload_firebase_cache_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = ReloadCacheCommandRequested(
        request_kind="ReloadCacheCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6120,
        source_transport="telegram",
        raw_input="/reload_cache",
        provenance={"event_kind": "command_message", "command_tokens": ["reload_cache"]},
    )
    app = object()
    message = SimpleNamespace(id=6120, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_reload_cache_command_request(app, execution_context, request)

    assert captured["reload_cache_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_auto_cache_command_request_routes_request_to_cache_runtime(monkeypatch):
    captured = {}

    def fake_auto_cache_command(app, message):
        captured["auto_cache_call"] = {
            "app": app,
            "message": message,
        }

    fake_cache_module = ModuleType("DATABASE.cache_db")
    fake_cache_module.auto_cache_command = fake_auto_cache_command
    monkeypatch.setitem(sys.modules, "DATABASE.cache_db", fake_cache_module)

    request = AutoCacheCommandRequested(
        request_kind="AutoCacheCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6121,
        source_transport="telegram",
        raw_input="/auto_cache on",
        provenance={"event_kind": "command_message", "command_tokens": ["auto_cache", "on"]},
    )
    app = object()
    message = SimpleNamespace(id=6121, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_auto_cache_command_request(app, execution_context, request)

    assert captured["auto_cache_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_runtime_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_check_runtime(message):
        captured["runtime_call"] = {"message": message}

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.check_runtime = fake_check_runtime
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = RuntimeCommandRequested(
        request_kind="RuntimeCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6122,
        source_transport="telegram",
        raw_input="/run_time",
        provenance={"event_kind": "command_message", "command_tokens": ["run_time"]},
    )
    message = SimpleNamespace(id=6122, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_runtime_command_request(object(), execution_context, request)

    assert captured["runtime_call"] == {
        "message": message,
    }


def test_handle_user_logs_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_get_user_log(app, message):
        captured["user_logs_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.get_user_log = fake_get_user_log
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = UserLogsCommandRequested(
        request_kind="UserLogsCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6123,
        source_transport="telegram",
        raw_input="/log 91363026",
        provenance={"event_kind": "command_message", "command_tokens": ["log", "91363026"]},
    )
    app = object()
    message = SimpleNamespace(id=6123, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_user_logs_command_request(app, execution_context, request)

    assert captured["user_logs_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_user_details_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_get_user_details(app, message):
        captured["user_details_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.get_user_details = fake_get_user_details
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = UserDetailsCommandRequested(
        request_kind="UserDetailsCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6124,
        source_transport="telegram",
        raw_input="/all 91363026",
        provenance={"event_kind": "command_message", "command_tokens": ["all", "91363026"]},
    )
    app = object()
    message = SimpleNamespace(id=6124, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_user_details_command_request(app, execution_context, request)

    assert captured["user_details_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_ban_time_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_ban_time_command(app, message):
        captured["ban_time_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.ban_time_command = fake_ban_time_command
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = BanTimeCommandRequested(
        request_kind="BanTimeCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6125,
        source_transport="telegram",
        raw_input="/ban_time 15m",
        provenance={"event_kind": "command_message", "command_tokens": ["ban_time", "15m"]},
    )
    app = object()
    message = SimpleNamespace(id=6125, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_ban_time_command_request(app, execution_context, request)

    assert captured["ban_time_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_broadcast_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_send_promo_message(app, message):
        captured["broadcast_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.send_promo_message = fake_send_promo_message
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = BroadcastCommandRequested(
        request_kind="BroadcastCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6126,
        source_transport="telegram",
        raw_input="/broadcast hello world",
        provenance={"event_kind": "command_message", "command_tokens": ["broadcast", "hello", "world"]},
    )
    app = object()
    message = SimpleNamespace(id=6126, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_broadcast_command_request(app, execution_context, request)

    assert captured["broadcast_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_block_user_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_block_user(app, message):
        captured["block_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.block_user = fake_block_user
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = BlockUserCommandRequested(
        request_kind="BlockUserCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6128,
        source_transport="telegram",
        raw_input="/block 91363026",
        provenance={"event_kind": "command_message", "command_tokens": ["block", "91363026"]},
    )
    app = object()
    message = SimpleNamespace(id=6128, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_block_user_command_request(app, execution_context, request)

    assert captured["block_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_unblock_user_command_request_routes_request_to_admin_runtime(monkeypatch):
    captured = {}

    def fake_unblock_user(app, message):
        captured["unblock_call"] = {
            "app": app,
            "message": message,
        }

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.unblock_user = fake_unblock_user
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = UnblockUserCommandRequested(
        request_kind="UnblockUserCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6129,
        source_transport="telegram",
        raw_input="/unblock 91363026",
        provenance={"event_kind": "command_message", "command_tokens": ["unblock", "91363026"]},
    )
    app = object()
    message = SimpleNamespace(id=6129, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_unblock_user_command_request(app, execution_context, request)

    assert captured["unblock_call"] == {
        "app": app,
        "message": message,
    }


def test_handle_clean_command_request_routes_request_to_clean_runtime(monkeypatch):
    captured = {}

    def fake_clean_command_logic(app, message, request=None):
        captured["clean_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_clean_module = ModuleType("COMMANDS.clean_cmd")
    fake_clean_module.clean_command_logic = fake_clean_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.clean_cmd", fake_clean_module)

    request = CleanCommandRequested(
        request_kind="CleanCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6127,
        source_transport="telegram",
        raw_input="/clean all",
        provenance={"event_kind": "command_message", "command_tokens": ["clean", "all"]},
    )
    app = object()
    message = SimpleNamespace(id=6127, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_clean_command_request(app, execution_context, request)

    assert captured["clean_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_clean_option_selection_request_routes_request_to_clean_callback_runtime(monkeypatch):
    captured = {}

    def fake_clean_option_callback_logic(app, callback_query, request=None):
        captured["clean_option_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_clean_module = ModuleType("COMMANDS.clean_cmd")
    fake_clean_module.clean_option_callback_logic = fake_clean_option_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.clean_cmd", fake_clean_module)

    request = CleanOptionSelectionRequested(
        request_kind="CleanOptionSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=77,
        source_transport="telegram_callback",
        raw_input="clean_option|logs",
        provenance={"event_kind": "callback_query"},
        action_key="logs",
    )
    app = object()
    callback_query = SimpleNamespace(
        data="clean_option|logs",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(id=77, chat=SimpleNamespace(id=91363026)),
    )
    execution_context = build_callback_execution_context(callback_query)

    handle_clean_option_selection_request(app, execution_context, request)

    assert captured["clean_option_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_browser_cookie_selection_request_routes_request_to_browser_callback_runtime(monkeypatch):
    captured = {}

    def fake_browser_choice_callback_logic(app, callback_query, request=None):
        captured["browser_choice_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_cookies_module = ModuleType("COMMANDS.cookies_cmd")
    fake_cookies_module.browser_choice_callback_logic = fake_browser_choice_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.cookies_cmd", fake_cookies_module)

    request = BrowserCookieSelectionRequested(
        request_kind="BrowserCookieSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=78,
        source_transport="telegram_callback",
        raw_input="browser_choice|firefox",
        provenance={"event_kind": "callback_query"},
        action_key="firefox",
    )
    app = object()
    callback_query = SimpleNamespace(
        data="browser_choice|firefox",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(id=78, chat=SimpleNamespace(id=91363026)),
    )
    execution_context = build_callback_execution_context(callback_query)

    handle_browser_cookie_selection_request(app, execution_context, request)

    assert captured["browser_choice_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_language_selection_request_routes_request_to_lang_callback_runtime(monkeypatch):
    captured = {}

    def fake_lang_callback_logic(app, callback_query, request):
        captured["lang_selection_call"] = {
            "app": app,
            "callback_query": callback_query,
            "request": request,
        }

    fake_url_extractor_module = ModuleType("URL_PARSERS.url_extractor")
    fake_url_extractor_module.lang_callback_logic = fake_lang_callback_logic
    monkeypatch.setitem(sys.modules, "URL_PARSERS.url_extractor", fake_url_extractor_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    app = object()
    request = LanguageSelectionRequested(
        request_kind="LanguageSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=6113,
        source_transport="telegram",
        raw_input="lang_select_ru",
        provenance={"event_kind": "callback_query"},
        action_kind="select",
        action_value="ru",
    )

    handle_language_selection_request(app, execution_context, request)

    assert captured["lang_selection_call"] == {
        "app": app,
        "callback_query": callback_query,
        "request": request,
    }


def test_handle_mediainfo_option_selection_request_routes_request_to_mediainfo_runtime(monkeypatch):
    captured = {}

    def fake_mediainfo_option_callback_logic(app, execution_context, request):
        captured["mediainfo_option_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_mediainfo_module = ModuleType("COMMANDS.mediainfo_cmd")
    fake_mediainfo_module.mediainfo_option_callback_logic = fake_mediainfo_option_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.mediainfo_cmd", fake_mediainfo_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    request = MediaInfoOptionSelectionRequested(
        request_kind="MediaInfoOptionSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=612,
        source_transport="telegram",
        raw_input="mediainfo_option|on",
        provenance={"event_kind": "callback_query"},
        selection_key="on",
    )

    handle_mediainfo_option_selection_request(object(), execution_context, request)

    assert captured["mediainfo_option_call"]["request"] == request
    assert captured["mediainfo_option_call"]["execution_context"] == execution_context


def test_handle_link_command_request_routes_request_to_link_runtime(monkeypatch):
    captured = {}

    def fake_link_command_logic(app, message, request=None):
        captured["link_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_link_module = ModuleType("COMMANDS.link_cmd")
    fake_link_module.link_command_logic = fake_link_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.link_cmd", fake_link_module)

    request = LinkCommandRequested(
        request_kind="LinkCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=613,
        source_transport="telegram",
        raw_input="/link 720 https://youtu.be/example",
        provenance={"event_kind": "command_message", "command_tokens": ["link", "720", "https://youtu.be/example"]},
    )
    app = object()
    message = SimpleNamespace(id=613, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_link_command_request(app, execution_context, request)

    assert captured["link_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_search_command_request_routes_request_to_search_runtime(monkeypatch):
    captured = {}

    def fake_search_command_logic(app, message, request=None):
        captured["search_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_search_module = ModuleType("COMMANDS.search")
    fake_search_module.search_command_logic = fake_search_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.search", fake_search_module)

    request = SearchCommandRequested(
        request_kind="SearchCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=614,
        source_transport="telegram",
        raw_input="/search kittens",
        provenance={"event_kind": "command_message", "command_tokens": ["search", "kittens"]},
    )
    app = object()
    message = SimpleNamespace(id=614, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_search_command_request(app, execution_context, request)

    assert captured["search_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_keyboard_command_request_routes_request_to_keyboard_runtime(monkeypatch):
    captured = {}

    def fake_keyboard_command_logic(app, message, request=None):
        captured["keyboard_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_keyboard_module = ModuleType("COMMANDS.keyboard_cmd")
    fake_keyboard_module.keyboard_command_logic = fake_keyboard_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.keyboard_cmd", fake_keyboard_module)

    request = KeyboardCommandRequested(
        request_kind="KeyboardCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=615,
        source_transport="telegram",
        raw_input="/keyboard full",
        provenance={"event_kind": "command_message", "command_tokens": ["keyboard", "full"]},
    )
    app = object()
    message = SimpleNamespace(id=615, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_keyboard_command_request(app, execution_context, request)

    assert captured["keyboard_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_keyboard_option_selection_request_routes_request_to_keyboard_runtime(monkeypatch):
    captured = {}

    def fake_keyboard_callback_logic(app, execution_context, request):
        captured["keyboard_option_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_keyboard_module = ModuleType("COMMANDS.keyboard_cmd")
    fake_keyboard_module.keyboard_callback_logic = fake_keyboard_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.keyboard_cmd", fake_keyboard_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    request = KeyboardOptionSelectionRequested(
        request_kind="KeyboardOptionSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=616,
        source_transport="telegram",
        raw_input="keyboard|FULL",
        provenance={"event_kind": "callback_query"},
        selection_key="FULL",
    )

    handle_keyboard_option_selection_request(object(), execution_context, request)

    assert captured["keyboard_option_call"]["request"] == request
    assert captured["keyboard_option_call"]["execution_context"] == execution_context


def test_handle_proxy_command_request_routes_request_to_proxy_runtime(monkeypatch):
    captured = {}

    def fake_proxy_command_logic(app, message, request=None):
        captured["proxy_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_proxy_module = ModuleType("COMMANDS.proxy_cmd")
    fake_proxy_module.proxy_command_logic = fake_proxy_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.proxy_cmd", fake_proxy_module)

    request = ProxyCommandRequested(
        request_kind="ProxyCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=617,
        source_transport="telegram",
        raw_input="/proxy on",
        provenance={"event_kind": "command_message", "command_tokens": ["proxy", "on"]},
    )
    app = object()
    message = SimpleNamespace(id=617, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_proxy_command_request(app, execution_context, request)

    assert captured["proxy_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_nsfw_command_request_routes_request_to_nsfw_runtime(monkeypatch):
    captured = {}

    def fake_nsfw_command_logic(app, message, request=None):
        captured["nsfw_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_nsfw_module = ModuleType("COMMANDS.nsfw_cmd")
    fake_nsfw_module.nsfw_command_logic = fake_nsfw_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.nsfw_cmd", fake_nsfw_module)

    request = NsfwCommandRequested(
        request_kind="NsfwCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=618,
        source_transport="telegram",
        raw_input="/nsfw off",
        provenance={"event_kind": "command_message", "command_tokens": ["nsfw", "off"]},
    )
    app = object()
    message = SimpleNamespace(id=618, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_nsfw_command_request(app, execution_context, request)

    assert captured["nsfw_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_split_command_request_routes_request_to_split_runtime(monkeypatch):
    captured = {}

    def fake_split_command_logic(app, message, request=None):
        captured["split_command_call"] = {
            "app": app,
            "message": message,
            "request": request,
        }

    fake_split_module = ModuleType("COMMANDS.split_sizer")
    fake_split_module.split_command_logic = fake_split_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.split_sizer", fake_split_module)

    request = SplitCommandRequested(
        request_kind="SplitCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=619,
        source_transport="telegram",
        raw_input="/split 500mb",
        provenance={"event_kind": "command_message", "command_tokens": ["split", "500mb"]},
    )
    app = object()
    message = SimpleNamespace(id=619, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_split_command_request(app, execution_context, request)

    assert captured["split_command_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_close_message_request_deletes_answers_and_logs(monkeypatch):
    captured = {}

    def fake_send_to_logger(message, text):
        captured["log_call"] = {"message": message, "text": text}

    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.send_to_logger = fake_send_to_logger
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)

    message = SimpleNamespace(id=701, delete=lambda: captured.setdefault("deleted", True))
    callback_query = SimpleNamespace(
        answer=lambda text: captured.setdefault("answered", text),
        edit_message_reply_markup=lambda reply_markup=None: captured.setdefault("fallback_markup", reply_markup),
    )
    execution_context = TelegramExecutionContext(
        chat_id=91363026,
        source_message_id=701,
        source_message=message,
        callback_query=callback_query,
        message_thread_id=None,
    )
    request = CloseMessageRequested(
        request_kind="CloseMessageRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=701,
        source_transport="telegram",
        raw_input="help_msg|close",
        provenance={"event_kind": "callback_query"},
        close_scope="help_msg",
    )

    handle_close_message_request(
        object(),
        execution_context,
        request,
        answer_text="closed",
        log_text="logged",
    )

    assert captured["deleted"] is True
    assert captured["answered"] == "closed"
    assert captured["log_call"] == {"message": message, "text": "logged"}


def test_handle_proxy_option_selection_request_routes_request_to_proxy_runtime(monkeypatch):
    captured = {}

    def fake_proxy_option_callback_logic(app, execution_context, request):
        captured["proxy_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_proxy_module = ModuleType("COMMANDS.proxy_cmd")
    fake_proxy_module.proxy_option_callback_logic = fake_proxy_option_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.proxy_cmd", fake_proxy_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    request = ProxyOptionSelectionRequested(
        request_kind="ProxyOptionSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=801,
        source_transport="telegram",
        raw_input="proxy_option|on",
        provenance={"event_kind": "callback_query"},
        selection_key="on",
    )

    handle_proxy_option_selection_request(object(), execution_context, request)

    assert captured["proxy_call"]["request"] == request
    assert captured["proxy_call"]["execution_context"] == execution_context


def test_handle_nsfw_option_selection_request_routes_request_to_nsfw_runtime(monkeypatch):
    captured = {}

    def fake_nsfw_option_callback_logic(app, execution_context, request):
        captured["nsfw_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_nsfw_module = ModuleType("COMMANDS.nsfw_cmd")
    fake_nsfw_module.nsfw_option_callback_logic = fake_nsfw_option_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.nsfw_cmd", fake_nsfw_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    request = NsfwOptionSelectionRequested(
        request_kind="NsfwOptionSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=802,
        source_transport="telegram",
        raw_input="nsfw_option|off",
        provenance={"event_kind": "callback_query"},
        selection_key="off",
    )

    handle_nsfw_option_selection_request(object(), execution_context, request)

    assert captured["nsfw_call"]["request"] == request
    assert captured["nsfw_call"]["execution_context"] == execution_context


def test_handle_split_size_selection_request_routes_request_to_split_runtime(monkeypatch):
    captured = {}

    def fake_split_size_callback_logic(app, execution_context, request):
        captured["split_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_split_module = ModuleType("COMMANDS.split_sizer")
    fake_split_module.split_size_callback_logic = fake_split_size_callback_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.split_sizer", fake_split_module)

    callback_query = SimpleNamespace(message=None)
    execution_context = build_callback_execution_context(callback_query)
    request = SplitSizeSelectionRequested(
        request_kind="SplitSizeSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=803,
        source_transport="telegram",
        raw_input="split_size|104857600",
        provenance={"event_kind": "callback_query"},
        selection_key="104857600",
    )

    handle_split_size_selection_request(object(), execution_context, request)

    assert captured["split_call"]["request"] == request
    assert captured["split_call"]["execution_context"] == execution_context


def test_handle_concat_request_routes_audio_request_to_audio_concat_runtime(monkeypatch):
    captured = {}

    def fake_audio_concat_branch(**kwargs):
        captured["audio_branch_kwargs"] = kwargs
        return {"branch_family": "audio_concat_download"}

    def fake_video_concat_branch(**kwargs):
        raise AssertionError("video concat branch should not be used for audio request")

    def fake_log_branch_selection(logger, branch_result, user_id):
        captured["logged_branch"] = {"branch_result": branch_result, "user_id": user_id}

    def fake_make_runtime_task(**kwargs):
        captured["task_kwargs"] = kwargs
        return {"task_seed": kwargs}

    def fake_with_branch_selection(task, branch_result):
        captured["task_branch"] = branch_result
        task["branch_result"] = branch_result
        return task

    def fake_concat_audio_playlist_range(app, message, **kwargs):
        captured["audio_exec"] = {"app": app, "message": message, **kwargs}

    def fake_concat_video_playlist_range(app, message, **kwargs):
        raise AssertionError("video concat executor should not be used for audio request")

    fake_branch_module = ModuleType("DOWN_AND_UP.branch_selection_result")
    fake_branch_module.audio_concat_branch = fake_audio_concat_branch
    fake_branch_module.video_concat_branch = fake_video_concat_branch
    fake_branch_module.log_branch_selection = fake_log_branch_selection

    fake_runtime_module = ModuleType("DOWN_AND_UP.runtime_task")
    fake_runtime_module.make_runtime_task = fake_make_runtime_task
    fake_runtime_module.with_branch_selection = fake_with_branch_selection

    fake_audio_concat_module = ModuleType("DOWN_AND_UP.audio_concat")
    fake_audio_concat_module.concat_audio_playlist_range = fake_concat_audio_playlist_range

    fake_video_concat_module = ModuleType("DOWN_AND_UP.video_concat")
    fake_video_concat_module.concat_video_playlist_range = fake_concat_video_playlist_range

    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.logger = object()

    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.branch_selection_result", fake_branch_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.runtime_task", fake_runtime_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.audio_concat", fake_audio_concat_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.video_concat", fake_video_concat_module)
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)

    request = ConcatRequested(
        request_kind="ConcatRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=88,
        source_transport="telegram",
        raw_input="/concat --audio-only 2-5 https://youtube.com/playlist?list=abc",
        provenance={"command_name": "/concat"},
        url="https://youtube.com/playlist?list=abc",
        media_mode="audio",
        reverse_output=True,
        output_name_override="My Mix",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_count=4,
        video_start_with=2,
        video_end_with=5,
        concat_policy="direct_concat_only",
        chapter_policy="none",
        concat_ordering="reverse",
    )
    app = object()
    message = SimpleNamespace(id=88, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_concat_request(app, execution_context, request)

    assert captured["audio_branch_kwargs"]["video_count"] == 4
    assert captured["audio_branch_kwargs"]["provenance"]["command"] == "/concat"
    assert captured["logged_branch"]["user_id"] == 91363026
    assert captured["task_kwargs"]["output_name_override"] == "My Mix"
    assert captured["audio_exec"] == {
        "app": app,
        "message": message,
        "url": "https://youtube.com/playlist?list=abc",
        "video_start_with": 2,
        "video_end_with": 5,
        "reverse_output": True,
        "output_name_override": "My Mix",
        "task_context": {
            "task_seed": captured["task_kwargs"],
            "branch_result": {"branch_family": "audio_concat_download"},
        },
    }


def test_handle_concat_request_routes_video_request_to_video_concat_runtime(monkeypatch):
    captured = {}

    def fake_audio_concat_branch(**kwargs):
        raise AssertionError("audio concat branch should not be used for video request")

    def fake_video_concat_branch(**kwargs):
        captured["video_branch_kwargs"] = kwargs
        return {"branch_family": "video_concat_download"}

    def fake_log_branch_selection(logger, branch_result, user_id):
        captured["logged_branch"] = {"branch_result": branch_result, "user_id": user_id}

    def fake_make_runtime_task(**kwargs):
        captured["task_kwargs"] = kwargs
        return {"task_seed": kwargs}

    def fake_with_branch_selection(task, branch_result):
        captured["task_branch"] = branch_result
        task["branch_result"] = branch_result
        return task

    def fake_concat_audio_playlist_range(app, message, **kwargs):
        raise AssertionError("audio concat executor should not be used for video request")

    def fake_concat_video_playlist_range(app, message, **kwargs):
        captured["video_exec"] = {"app": app, "message": message, **kwargs}

    fake_branch_module = ModuleType("DOWN_AND_UP.branch_selection_result")
    fake_branch_module.audio_concat_branch = fake_audio_concat_branch
    fake_branch_module.video_concat_branch = fake_video_concat_branch
    fake_branch_module.log_branch_selection = fake_log_branch_selection

    fake_runtime_module = ModuleType("DOWN_AND_UP.runtime_task")
    fake_runtime_module.make_runtime_task = fake_make_runtime_task
    fake_runtime_module.with_branch_selection = fake_with_branch_selection

    fake_audio_concat_module = ModuleType("DOWN_AND_UP.audio_concat")
    fake_audio_concat_module.concat_audio_playlist_range = fake_concat_audio_playlist_range

    fake_video_concat_module = ModuleType("DOWN_AND_UP.video_concat")
    fake_video_concat_module.concat_video_playlist_range = fake_concat_video_playlist_range

    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.logger = object()

    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.branch_selection_result", fake_branch_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.runtime_task", fake_runtime_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.audio_concat", fake_audio_concat_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.video_concat", fake_video_concat_module)
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)

    request = ConcatRequested(
        request_kind="ConcatRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=99,
        source_transport="telegram",
        raw_input="/concat reverse 1-3 https://youtube.com/playlist?list=abc",
        provenance={"command_name": "/concat"},
        url="https://youtube.com/playlist?list=abc",
        media_mode="video",
        reverse_output=False,
        output_name_override=None,
        tags=[],
        tags_text="",
        playlist_name="Playlist",
        video_count=3,
        video_start_with=1,
        video_end_with=3,
        concat_policy="direct_concat_only",
        chapter_policy="none",
        concat_ordering="original",
    )
    app = object()
    message = SimpleNamespace(id=99, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_concat_request(app, execution_context, request)

    assert captured["video_branch_kwargs"]["video_count"] == 3
    assert captured["video_branch_kwargs"]["provenance"]["concat_policy"] == "direct_concat_only"
    assert captured["logged_branch"]["user_id"] == 91363026
    assert captured["task_kwargs"]["concat_policy"] == "direct_concat_only"
    assert captured["video_exec"] == {
        "app": app,
        "message": message,
        "url": "https://youtube.com/playlist?list=abc",
        "video_start_with": 1,
        "video_end_with": 3,
        "reverse_output": False,
        "output_name_override": None,
        "task_context": {
            "task_seed": captured["task_kwargs"],
            "branch_result": {"branch_family": "video_concat_download"},
        },
    }


def test_handle_rename_request_routes_request_to_rename_runtime(monkeypatch):
    captured = {}

    def fake_resend_last_audio_concat_with_new_name(app, message, *, new_name):
        captured["rename_call"] = {"app": app, "message": message, "new_name": new_name}

    fake_audio_concat_module = ModuleType("DOWN_AND_UP.audio_concat")
    fake_audio_concat_module.resend_last_audio_concat_with_new_name = fake_resend_last_audio_concat_with_new_name
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.audio_concat", fake_audio_concat_module)

    request = RenameRequested(
        request_kind="RenameRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=101,
        source_transport="telegram",
        raw_input='/rename "My Better Mix"',
        provenance={"command_name": "/rename"},
        target_kind="audio_concat",
        new_name="My Better Mix",
    )
    app = object()
    message = SimpleNamespace(id=101, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_rename_request(app, execution_context, request)

    assert captured["rename_call"] == {
        "app": app,
        "message": message,
        "new_name": "My Better Mix",
    }


def test_handle_audio_download_request_routes_request_to_audio_runtime(monkeypatch):
    captured = {}

    def fake_save_user_tags(user_id, tags):
        captured["saved_tags"] = (user_id, list(tags))

    def fake_audio_download_branch(**kwargs):
        captured["audio_branch_kwargs"] = kwargs
        return {"branch_family": "audio_download"}

    def fake_log_branch_selection(logger, branch_result, user_id):
        captured["logged_branch"] = {"branch_result": branch_result, "user_id": user_id}

    def fake_make_runtime_task(**kwargs):
        captured["task_kwargs"] = kwargs
        return {"task_seed": kwargs}

    def fake_with_branch_selection(task, branch_result):
        task["branch_result"] = branch_result
        return task

    def fake_down_and_audio(app, message, **kwargs):
        captured["audio_exec"] = {"app": app, "message": message, **kwargs}

    fake_branch_module = ModuleType("DOWN_AND_UP.branch_selection_result")
    fake_branch_module.audio_download_branch = fake_audio_download_branch
    fake_branch_module.log_branch_selection = fake_log_branch_selection

    fake_runtime_module = ModuleType("DOWN_AND_UP.runtime_task")
    fake_runtime_module.make_runtime_task = fake_make_runtime_task
    fake_runtime_module.with_branch_selection = fake_with_branch_selection

    fake_audio_module = ModuleType("DOWN_AND_UP.down_and_audio")
    fake_audio_module.down_and_audio = fake_down_and_audio

    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.logger = object()

    fake_tags_module = ModuleType("URL_PARSERS.tags")
    fake_tags_module.save_user_tags = fake_save_user_tags

    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.branch_selection_result", fake_branch_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.runtime_task", fake_runtime_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.down_and_audio", fake_audio_module)
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tags", fake_tags_module)

    request = AudioDownloadRequested(
        request_kind="AudioDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=111,
        source_transport="telegram",
        raw_input="/audio 1-3 https://youtu.be/example",
        provenance={"command_name": "/audio"},
        url="https://youtu.be/example",
        quality_key="mp3",
        format_override="ba",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_count=3,
        video_start_with=1,
    )
    app = object()
    message = SimpleNamespace(id=111, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_audio_download_request(app, execution_context, request)

    assert captured["saved_tags"] == (91363026, ["#tag1"])
    assert captured["audio_branch_kwargs"]["provenance"]["command"] == "/audio"
    assert captured["logged_branch"]["user_id"] == 91363026
    assert captured["task_kwargs"]["playlist_name"] == "Playlist"
    assert captured["audio_exec"] == {
        "app": app,
        "message": message,
        "quality_key": "mp3",
        "format_override": "ba",
        "task_context": {
            "task_seed": captured["task_kwargs"],
            "branch_result": {"branch_family": "audio_download"},
        },
    }


def test_handle_url_download_request_routes_request_to_video_extractor(monkeypatch):
    captured = {}

    def fake_video_url_extractor(app, message=None, url_request=None, execution_context=None):
        captured["video_url_extractor_call"] = {
            "app": app,
            "message": message,
            "url_request": url_request,
            "execution_context": execution_context,
        }

    fake_video_extractor_module = ModuleType("URL_PARSERS.video_extractor")
    fake_video_extractor_module.video_url_extractor = fake_video_url_extractor
    monkeypatch.setitem(sys.modules, "URL_PARSERS.video_extractor", fake_video_extractor_module)

    request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=121,
        source_transport="telegram",
        raw_input="https://youtube.com/playlist?list=abc*2*5 #tag1",
        provenance={"event_kind": "text_message"},
        url="https://youtube.com/playlist?list=abc",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_start_with=2,
        video_end_with=5,
    )
    app = object()
    message = SimpleNamespace(id=121, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_url_download_request(app, execution_context, request)

    assert captured["video_url_extractor_call"] == {
        "app": app,
        "message": None,
        "url_request": request,
        "execution_context": execution_context,
    }


def test_derive_playlist_start_index_uses_first_item_only_when_no_range():
    assert derive_playlist_start_index(1, 1) == 1
    assert derive_playlist_start_index(3, 5) == 3
    assert derive_playlist_start_index(-1, -7) == -1


def test_resolve_saved_format_policy_defaults_to_ask_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    should_ask, saved_format = resolve_saved_format_policy(user_id=91363026)

    assert should_ask is True
    assert saved_format is None
    assert Path("users/91363026").is_dir()


def test_resolve_saved_format_policy_uses_saved_format_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    user_dir = Path("users/91363026")
    user_dir.mkdir(parents=True)
    (user_dir / "format.txt").write_text("bv*[height<=720]+ba", encoding="utf-8")

    should_ask, saved_format = resolve_saved_format_policy(user_id=91363026)

    assert should_ask is False
    assert saved_format == "bv*[height<=720]+ba"


def test_resolve_saved_format_policy_keeps_always_ask_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    user_dir = Path("users/91363026")
    user_dir.mkdir(parents=True)
    (user_dir / "format.txt").write_text("ALWAYS_ASK", encoding="utf-8")

    should_ask, saved_format = resolve_saved_format_policy(user_id=91363026)

    assert should_ask is True
    assert saved_format is None


def test_normalize_url_download_runtime_request_reuses_existing_request():
    request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=121,
        source_transport="telegram",
        raw_input="https://youtube.com/playlist?list=abc*2*5 #tag1",
        provenance={"event_kind": "text_message"},
        url="https://youtube.com/playlist?list=abc",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_start_with=2,
        video_end_with=5,
    )

    normalized, tag_error = normalize_url_download_runtime_request(
        user_id=91363026,
        source_message_id=121,
        raw_input=request.raw_input,
        request=request,
    )

    assert normalized is request
    assert tag_error is None


def test_normalize_url_download_runtime_request_parses_legacy_raw_input(monkeypatch):
    def fake_extract_url_range_tags(raw_input):
        assert raw_input == "https://youtube.com/playlist?list=abc*2*5 #tag1"
        return (
            "https://youtube.com/playlist?list=abc",
            2,
            5,
            "Playlist",
            ["#tag1"],
            "#tag1",
            None,
        )

    fake_tags_module = ModuleType("URL_PARSERS.tags")
    fake_tags_module.extract_url_range_tags = fake_extract_url_range_tags
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tags", fake_tags_module)

    normalized, tag_error = normalize_url_download_runtime_request(
        user_id=91363026,
        source_message_id=121,
        raw_input="https://youtube.com/playlist?list=abc*2*5 #tag1",
        request=None,
    )

    assert tag_error is None
    assert normalized.user_id == 91363026
    assert normalized.source_message_id == 121
    assert normalized.url == "https://youtube.com/playlist?list=abc"
    assert normalized.tags == ["#tag1"]
    assert normalized.tags_text == "#tag1"
    assert normalized.playlist_name == "Playlist"
    assert normalized.video_start_with == 2
    assert normalized.video_end_with == 5


def test_derive_url_runtime_media_policy_adds_auto_tags_and_tiktok_flag(monkeypatch):
    def fake_get_auto_tags(url, tags):
        assert url == "https://www.tiktok.com/@user/video/123"
        assert tags == ["#tag1"]
        return ["#autotag"]

    def fake_is_tiktok_url(url):
        return url.startswith("https://www.tiktok.com/")

    fake_tags_module = ModuleType("URL_PARSERS.tags")
    fake_tags_module.get_auto_tags = fake_get_auto_tags
    fake_tiktok_module = ModuleType("URL_PARSERS.tiktok")
    fake_tiktok_module.is_tiktok_url = fake_is_tiktok_url
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tags", fake_tags_module)
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tiktok", fake_tiktok_module)

    request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=141,
        source_transport="telegram",
        raw_input="https://www.tiktok.com/@user/video/123",
        provenance={"event_kind": "text_message"},
        url="https://www.tiktok.com/@user/video/123",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name=None,
        video_start_with=1,
        video_end_with=3,
    )

    policy = derive_url_runtime_media_policy(request)

    assert policy == {
        "force_no_title": True,
        "all_tags": ["#tag1", "#autotag"],
        "tags_text": "#tag1 #autotag",
        "video_count": 3,
    }


def test_derive_url_runtime_media_policy_handles_reverse_negative_ranges(monkeypatch):
    fake_tags_module = ModuleType("URL_PARSERS.tags")
    fake_tags_module.get_auto_tags = lambda url, tags: []
    fake_tiktok_module = ModuleType("URL_PARSERS.tiktok")
    fake_tiktok_module.is_tiktok_url = lambda url: False
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tags", fake_tags_module)
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tiktok", fake_tiktok_module)

    negative_request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=142,
        source_transport="telegram",
        raw_input="https://youtube.com/playlist?list=abc*-1*-7",
        provenance={"event_kind": "text_message"},
        url="https://youtube.com/playlist?list=abc",
        tags=[],
        tags_text="",
        playlist_name="Playlist",
        video_start_with=-1,
        video_end_with=-7,
    )
    reverse_request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=143,
        source_transport="telegram",
        raw_input="https://youtube.com/playlist?list=abc*5*3",
        provenance={"event_kind": "text_message"},
        url="https://youtube.com/playlist?list=abc",
        tags=[],
        tags_text="",
        playlist_name="Playlist",
        video_start_with=5,
        video_end_with=3,
    )

    negative_policy = derive_url_runtime_media_policy(negative_request)
    reverse_policy = derive_url_runtime_media_policy(reverse_request)

    assert negative_policy["video_count"] == 7
    assert reverse_policy["video_count"] == 3
    assert negative_policy["force_no_title"] is False


def test_send_url_tag_error_renders_and_logs(monkeypatch):
    captured = {}

    def fake_safe_get_messages(user_id):
        return SimpleNamespace(TAG_FORBIDDEN_CHARS_MSG="bad {tag} ex {example}")

    def fake_log_error_to_channel(message, error_msg):
        captured["logged_error"] = {"message": message, "error_msg": error_msg}

    fake_messages_module = ModuleType("CONFIG.messages")
    fake_messages_module.safe_get_messages = fake_safe_get_messages
    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.log_error_to_channel = fake_log_error_to_channel
    fake_types_module = ModuleType("pyrogram.types")
    fake_types_module.ReplyParameters = lambda message_id: {"message_id": message_id}

    monkeypatch.setitem(sys.modules, "CONFIG.messages", fake_messages_module)
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)
    monkeypatch.setitem(sys.modules, "pyrogram.types", fake_types_module)

    class FakeApp:
        def send_message(self, chat_id, text, reply_parameters=None):
            captured["send_message"] = {
                "chat_id": chat_id,
                "text": text,
                "reply_parameters": reply_parameters,
            }

    message = SimpleNamespace(id=501)
    execution_context = build_message_execution_context(message)
    send_url_tag_error(
        FakeApp(),
        execution_context,
        user_id=91363026,
        tag_error=("badtag", "#good"),
    )

    assert captured["send_message"] == {
        "chat_id": 91363026,
        "text": "bad badtag ex #good",
        "reply_parameters": {"message_id": 501},
    }
    assert captured["logged_error"]["error_msg"] == "bad badtag ex #good"


def test_send_url_wait_download_notice_uses_execution_context_reply_target(monkeypatch):
    captured = {}

    fake_types_module = ModuleType("pyrogram.types")
    fake_types_module.ReplyParameters = lambda message_id: {"message_id": message_id}
    monkeypatch.setitem(sys.modules, "pyrogram.types", fake_types_module)

    class FakeApp:
        def send_message(self, chat_id, text, reply_parameters=None):
            captured["send_message"] = {
                "chat_id": chat_id,
                "text": text,
                "reply_parameters": reply_parameters,
            }

    execution_context = TelegramExecutionContext(
        chat_id=91363026,
        source_message_id=777,
        source_message=SimpleNamespace(id=777),
        callback_query=None,
        message_thread_id=None,
    )

    send_url_wait_download_notice(
        FakeApp(),
        execution_context,
        user_id=91363026,
        text="wait",
    )

    assert captured["send_message"] == {
        "chat_id": 91363026,
        "text": "wait",
        "reply_parameters": {"message_id": 777},
    }


def test_send_url_runtime_error_uses_execution_context_source_message(monkeypatch):
    captured = {}

    def fake_send_error_to_user(message, text):
        captured["error_call"] = {"message": message, "text": text}

    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.send_error_to_user = fake_send_error_to_user
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)

    message = SimpleNamespace(id=909)
    execution_context = build_message_execution_context(message)

    send_url_runtime_error(execution_context, "boom")

    assert captured["error_call"] == {"message": message, "text": "boom"}


def test_clear_user_playlist_error_state_handles_full_and_named_cleanup(monkeypatch):
    fake_download_status_module = ModuleType("HELPERS.download_status")
    fake_download_status_module.playlist_errors = {
        "91363026_one": True,
        "91363026_two": True,
        "999_other": True,
    }

    class DummyLock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_download_status_module.playlist_errors_lock = DummyLock()
    monkeypatch.setitem(sys.modules, "HELPERS.download_status", fake_download_status_module)

    clear_user_playlist_error_state(user_id=91363026, playlist_name="one")
    assert fake_download_status_module.playlist_errors == {
        "91363026_two": True,
        "999_other": True,
    }

    clear_user_playlist_error_state(user_id=91363026)
    assert fake_download_status_module.playlist_errors == {"999_other": True}


def test_is_url_blacklisted_checks_against_config(monkeypatch):
    fake_config_module = ModuleType("CONFIG.config")
    fake_config_module.Config = SimpleNamespace(BLACK_LIST=["bad.example", "forbidden"])
    monkeypatch.setitem(sys.modules, "CONFIG.config", fake_config_module)

    assert is_url_blacklisted("https://bad.example/video") is True
    assert is_url_blacklisted("https://good.example/video") is False


def test_handle_url_quality_menu_runtime_routes_request_to_menu_runtime(monkeypatch):
    captured = {}

    def fake_ask_quality_menu(app, message, url, tags, playlist_start_index=1, cb=None, download_dir=None):
        captured["ask_quality_call"] = {
            "app": app,
            "message": message,
            "url": url,
            "tags": list(tags),
            "playlist_start_index": playlist_start_index,
            "cb": cb,
            "download_dir": download_dir,
        }

    fake_menu_module = ModuleType("DOWN_AND_UP.always_ask_menu")
    fake_menu_module.ask_quality_menu = fake_ask_quality_menu
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.always_ask_menu", fake_menu_module)

    request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=122,
        source_transport="telegram",
        raw_input="https://youtube.com/playlist?list=abc*2*5 #tag1",
        provenance={"event_kind": "text_message"},
        url="https://youtube.com/playlist?list=abc",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_start_with=2,
        video_end_with=5,
    )
    app = object()
    message = SimpleNamespace(id=122, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_url_quality_menu_runtime(app, execution_context, request)

    assert captured["ask_quality_call"] == {
        "app": app,
        "message": message,
        "url": "https://youtube.com/playlist?list=abc",
        "tags": ["#tag1"],
        "playlist_start_index": 2,
        "cb": None,
        "download_dir": None,
    }


def test_derive_saved_format_quality_key_maps_known_and_custom_formats():
    assert derive_saved_format_quality_key("best") == "best"
    assert derive_saved_format_quality_key("bestvideo+bestaudio") == "bestvideo"
    assert derive_saved_format_quality_key("bv*[height<=720]+ba") == "720p"
    assert derive_saved_format_quality_key("custom_format_selector").startswith("custom_")


def test_handle_saved_format_url_runtime_routes_request_to_saved_format_runtime(monkeypatch):
    captured = {}

    def fake_save_user_tags(user_id, tags):
        captured["saved_tags"] = (user_id, list(tags))

    def fake_saved_format_branch(**kwargs):
        captured["branch_kwargs"] = kwargs
        return {"branch_family": "saved_format_download"}

    def fake_log_branch_selection(logger, branch_result, user_id):
        captured["logged_branch"] = {"branch_result": branch_result, "user_id": user_id}

    def fake_make_runtime_task(**kwargs):
        captured["task_kwargs"] = kwargs
        return {"task_seed": kwargs}

    def fake_with_branch_selection(task, branch_result):
        task["branch_result"] = branch_result
        return task

    def fake_down_and_up(app, message, **kwargs):
        captured["video_exec"] = {"app": app, "message": message, **kwargs}

    fake_branch_module = ModuleType("DOWN_AND_UP.branch_selection_result")
    fake_branch_module.saved_format_branch = fake_saved_format_branch
    fake_branch_module.log_branch_selection = fake_log_branch_selection

    fake_runtime_module = ModuleType("DOWN_AND_UP.runtime_task")
    fake_runtime_module.make_runtime_task = fake_make_runtime_task
    fake_runtime_module.with_branch_selection = fake_with_branch_selection

    fake_down_and_up_module = ModuleType("DOWN_AND_UP.down_and_up")
    fake_down_and_up_module.down_and_up = fake_down_and_up

    fake_logger_module = ModuleType("HELPERS.logger")
    fake_logger_module.logger = object()

    fake_tags_module = ModuleType("URL_PARSERS.tags")
    fake_tags_module.save_user_tags = fake_save_user_tags

    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.branch_selection_result", fake_branch_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.runtime_task", fake_runtime_module)
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.down_and_up", fake_down_and_up_module)
    monkeypatch.setitem(sys.modules, "HELPERS.logger", fake_logger_module)
    monkeypatch.setitem(sys.modules, "URL_PARSERS.tags", fake_tags_module)

    request = UrlDownloadRequested(
        request_kind="UrlDownloadRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=131,
        source_transport="telegram",
        raw_input="https://youtube.com/watch?v=abc",
        provenance={"event_kind": "text_message"},
        url="https://youtube.com/watch?v=abc",
        tags=["#tag1"],
        tags_text="#tag1",
        playlist_name="Playlist",
        video_start_with=1,
        video_end_with=1,
    )
    app = object()
    message = SimpleNamespace(id=131, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_saved_format_url_runtime(
        app,
        execution_context,
        request,
        saved_format="bv*[height<=720]+ba",
        tags=["#tag1", "#auto"],
        tags_text="#tag1 #auto",
        video_count=1,
        force_no_title=True,
    )

    assert captured["saved_tags"] == (91363026, ["#tag1", "#auto"])
    assert captured["branch_kwargs"]["quality_key"] == "720p"
    assert captured["logged_branch"]["user_id"] == 91363026
    assert captured["task_kwargs"]["force_no_title"] is True
    assert captured["video_exec"] == {
        "app": app,
        "message": message,
        "format_override": "bv*[height<=720]+ba",
        "quality_key": "720p",
        "task_context": {
            "task_seed": captured["task_kwargs"],
            "branch_result": {"branch_family": "saved_format_download"},
        },
    }


def test_handle_update_porn_command_request_routes_request_to_update_porn_runtime(monkeypatch):
    captured = {}

    def fake_update_porn_command_logic(app, message, request=None):
        captured["update_porn_call"] = {"app": app, "message": message, "request": request}

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.update_porn_command_logic = fake_update_porn_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = UpdatePornCommandRequested(
        request_kind="UpdatePornCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=1301,
        source_transport="telegram",
        raw_input="/update_porn",
        provenance={"event_kind": "command_message", "command_tokens": ["update_porn"]},
    )
    app = object()
    message = SimpleNamespace(id=1301, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_update_porn_command_request(app, execution_context, request)

    assert captured["update_porn_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_reload_porn_command_request_routes_request_to_reload_porn_runtime(monkeypatch):
    captured = {}

    def fake_reload_porn_command_logic(app, message, request=None):
        captured["reload_porn_call"] = {"app": app, "message": message, "request": request}

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.reload_porn_command_logic = fake_reload_porn_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = ReloadPornCommandRequested(
        request_kind="ReloadPornCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=1302,
        source_transport="telegram",
        raw_input="/reload_porn",
        provenance={"event_kind": "command_message", "command_tokens": ["reload_porn"]},
    )
    app = object()
    message = SimpleNamespace(id=1302, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_reload_porn_command_request(app, execution_context, request)

    assert captured["reload_porn_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_check_porn_command_request_routes_request_to_check_porn_runtime(monkeypatch):
    captured = {}

    def fake_check_porn_command_logic(app, message, request=None):
        captured["check_porn_call"] = {"app": app, "message": message, "request": request}

    fake_admin_module = ModuleType("COMMANDS.admin_cmd")
    fake_admin_module.check_porn_command_logic = fake_check_porn_command_logic
    monkeypatch.setitem(sys.modules, "COMMANDS.admin_cmd", fake_admin_module)

    request = CheckPornCommandRequested(
        request_kind="CheckPornCommandRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=1303,
        source_transport="telegram",
        raw_input="/check_porn https://example.com",
        provenance={"event_kind": "command_message", "command_tokens": ["check_porn", "https://example.com"]},
    )
    app = object()
    message = SimpleNamespace(id=1303, chat=SimpleNamespace(id=91363026))
    execution_context = build_message_execution_context(message)

    handle_check_porn_command_request(app, execution_context, request)

    assert captured["check_porn_call"] == {
        "app": app,
        "message": message,
        "request": request,
    }


def test_handle_gallery_fallback_selection_request_routes_request_to_gallery_callback_runtime(monkeypatch):
    captured = {}

    def fake_fallback_gallery_dl_callback_logic(app, execution_context, request=None):
        captured["gallery_fallback_call"] = {
            "app": app,
            "execution_context": execution_context,
            "request": request,
        }

    fake_menu_module = ModuleType("DOWN_AND_UP.always_ask_menu")
    fake_menu_module.fallback_gallery_dl_callback_logic = fake_fallback_gallery_dl_callback_logic
    monkeypatch.setitem(sys.modules, "DOWN_AND_UP.always_ask_menu", fake_menu_module)

    request = GalleryFallbackSelectionRequested(
        request_kind="GalleryFallbackSelectionRequested",
        user_id=91363026,
        chat_id=91363026,
        source_message_id=79,
        source_transport="telegram_callback",
        raw_input="fallback_gallery_dl|abc123",
        provenance={"event_kind": "callback_query"},
        action_key="fallback_gallery_dl|abc123",
    )
    app = object()
    callback_query = SimpleNamespace(
        data="fallback_gallery_dl|abc123",
        from_user=SimpleNamespace(id=91363026),
        message=SimpleNamespace(id=79, chat=SimpleNamespace(id=91363026)),
    )
    execution_context = build_callback_execution_context(callback_query)

    handle_gallery_fallback_selection_request(app, execution_context, request)

    assert captured["gallery_fallback_call"] == {
        "app": app,
        "execution_context": execution_context,
        "request": request,
    }
