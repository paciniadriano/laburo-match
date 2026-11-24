from src.core.text import normalize_name


def test_normalize_name_ignores_case_and_extra_spaces():
    assert normalize_name("  Next.JS  ") == "next.js"
    assert normalize_name("Senior  Frontend   Engineer") == "senior frontend engineer"
