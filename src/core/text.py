"""Small text helpers shared by several domains."""


def normalize_name(name: str) -> str:
    """Lowercase with collapsed spaces: the key used to compare names."""
    return " ".join(name.lower().split())
