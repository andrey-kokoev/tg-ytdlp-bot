import pytest

from HELPERS.subtitle_options import extract_text_only_option


@pytest.mark.parametrize("prefix", ["--", "\u2014", "\u2013"])
def test_extract_text_only_option_accepts_common_dash_variants(prefix):
    url = "https://www.youtube.com/watch?v=example"

    text, text_only = extract_text_only_option(f"/sub {prefix}text-only {url}")

    assert text_only is True
    assert text == f"/sub {url}"


def test_extract_text_only_option_does_not_modify_unrelated_text():
    text = "/sub https://example.test/video--text-only"

    normalized, text_only = extract_text_only_option(text)

    assert text_only is False
    assert normalized == text
