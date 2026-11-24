"""Decide whether extracted CV text is usable, scanned (no text layer) or unreadable.

Language-agnostic on purpose: no dictionary, only Unicode categories, so a CV in
any language or script passes as long as its text maps to real characters.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

MIN_CHARS_PER_PAGE = 100  # below this on average there is no real text layer
MAX_BAD_CHAR_RATIO = 0.05  # control, private-use, unassigned or U+FFFD characters
MIN_WORD_RATIO = 0.60  # share of letter-bearing tokens made only of letters

# Cc = control, Co = private use (icon fonts), Cn = unassigned.
BAD_CATEGORIES = {"Cc", "Co", "Cn"}
ALLOWED_CONTROL = {"\n", "\t", "\r"}

Verdict = Literal["ok", "scanned", "unreadable"]


@dataclass
class TextQuality:
    verdict: Verdict
    chars_per_page: float
    bad_char_ratio: float
    word_ratio: float


def is_bad_char(char: str) -> bool:
    if char in ALLOWED_CONTROL:
        return False
    return char == "�" or unicodedata.category(char) in BAD_CATEGORIES


def word_ratio(text: str) -> float:
    """Share of tokens that are pure letters once punctuation is stripped.

    Only tokens with at least one letter or bad character count, so numbers,
    dates and bullets ("2019", "–", "|") neither help nor hurt.
    """
    candidates = [
        token.strip(".,;:()[]{}!?\"'«»“”‘’/-+%&*#")
        for token in text.split()
        if any(c.isalpha() or is_bad_char(c) for c in token)
    ]
    if not candidates:
        return 0.0
    readable = sum(1 for token in candidates if token and all(c.isalpha() or c in "-'’." for c in token))
    return readable / len(candidates)


def assess(pages: list[str]) -> TextQuality:
    text = "\n".join(pages)
    visible = [c for c in text if not c.isspace()]
    chars_per_page = len(visible) / max(len(pages), 1)
    bad_count = sum(1 for c in visible if is_bad_char(c))
    # pdfminer writes unmapped glyphs as the literal "(cid:N)"; count those characters as bad too.
    bad_count += sum(len(m) for m in re.findall(r"\(cid:\d+\)", text))
    bad_ratio = min(bad_count / max(len(visible), 1), 1.0)
    words = word_ratio(text)

    verdict: Verdict = "ok"
    if chars_per_page < MIN_CHARS_PER_PAGE:
        verdict = "scanned"
    elif bad_ratio > MAX_BAD_CHAR_RATIO or words < MIN_WORD_RATIO:
        verdict = "unreadable"
    return TextQuality(verdict, chars_per_page, bad_ratio, words)
