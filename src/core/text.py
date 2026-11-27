"""Small text helpers shared by several domains."""


def normalize_name(name: str) -> str:
    """Lowercase with collapsed spaces: the key used to compare names."""
    return " ".join(name.lower().split())


def fold(text: str) -> str:
    """Lowercase, accents removed, punctuation turned into spaces: a form that compares reliably.

    "México", "MEXICO" and "mexico." all fold to "mexico"; "U.S.A." folds to "u s a".
    """
    import re
    import unicodedata

    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())
