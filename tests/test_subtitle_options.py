import pytest

from HELPERS.subtitle_options import extract_text_only_option


@pytest.mark.parametrize("option", ["--text-only", "—text-only", "–text-only", "--text=only", "—text=only", "–text=only"])
def test_extract_text_only_option_accepts_common_spellings(option):
    url = "https://www.youtube.com/watch?v=example"

    text, text_only = extract_text_only_option(f"/sub {option} {url}")

    assert text_only is True
    assert text == f"/sub {url}"


def test_extract_text_only_option_does_not_modify_unrelated_text():
    text = "/sub https://example.test/video--text-only"

    normalized, text_only = extract_text_only_option(text)

    assert text_only is False
    assert normalized == text
