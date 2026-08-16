import re


_TEXT_ONLY_OPTION = re.compile(r"(?<!\S)(?:--|\u2014|\u2013)text(?:-only|=only)\b\s*")


def extract_text_only_option(text: str) -> tuple[str, bool]:
    """Remove a supported text-only option and report whether it was present."""
    text_only = _TEXT_ONLY_OPTION.search(text) is not None
    if text_only:
        text = _TEXT_ONLY_OPTION.sub("", text).strip()
    return text, text_only
