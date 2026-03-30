from DOWN_AND_UP.audio_concat import (
    build_playlist_items_selector,
    maybe_reverse_concat_order,
    parse_concat_name_override,
)


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
