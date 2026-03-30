from DOWN_AND_UP.audio_concat import (
    build_playlist_items_selector,
    maybe_reverse_concat_order,
    parse_concat_name_override,
)


def normalize_concat_command_text_for_test(text: str):
    import re

    normalized = (text or "").strip()
    reverse_output = False
    audio_only = False
    if not normalized:
        return "/concat", reverse_output, audio_only
    parts = normalized.split(maxsplit=2)
    if len(parts) >= 2 and parts[1].lower() in {"reverse", "rev", "--reverse"}:
        reverse_output = True
        normalized = f"{parts[0]} {parts[2]}" if len(parts) >= 3 else parts[0]
    if "--audio-only" in normalized:
        audio_only = True
        normalized = re.sub(r"\s*--audio-only\b", "", normalized).strip()
    return normalized, reverse_output, audio_only


def test_build_playlist_items_selector_forward():
    assert build_playlist_items_selector(2, 5) == "2:5"


def test_build_playlist_items_selector_reverse():
    assert build_playlist_items_selector(5, 2) == "5:2:-1"


def test_maybe_reverse_concat_order():
    entries = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert [item["id"] for item in maybe_reverse_concat_order(entries, False)] == ["a", "b", "c"]
    assert [item["id"] for item in maybe_reverse_concat_order(entries, True)] == ["c", "b", "a"]


def test_parse_concat_name_override():
    name, cleaned = parse_concat_name_override(
        '/aconcat reverse name "My Mix" 1-11 https://youtube.com/playlist?list=abc'
    )
    assert name == "My Mix"
    assert cleaned == "/aconcat reverse 1-11 https://youtube.com/playlist?list=abc"


def test_normalize_concat_command_text():
    normalized, reverse_output, audio_only = normalize_concat_command_text_for_test(
        "/concat reverse --audio-only 1-11 https://youtube.com/playlist?list=abc"
    )
    assert normalized == "/concat 1-11 https://youtube.com/playlist?list=abc"
    assert reverse_output is True
    assert audio_only is True
