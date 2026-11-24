import pytest

from src.app.profile.evidence import content_hash, union_years


def test_overlapping_periods_are_counted_once():
    # Two jobs overlapping for one year: 2019-2022 and 2021-2024 cover 5 years, not 6.
    assert union_years([("2019-01-01", "2022-01-01"), ("2021-01-01", "2024-01-01")]) == 5.0


def test_adjacent_and_disjoint_periods_add_up():
    adjacent = [("2019-06-01", "2022-03-01"), ("2022-03-01", "2026-11-22")]
    assert union_years(adjacent) == pytest.approx(7.48, abs=0.01)
    assert union_years(
        [("2020-01-01", "2021-01-01"), ("2023-01-01", "2024-01-01")]
    ) == pytest.approx(2.0, abs=0.01)


def test_a_period_inside_another_adds_nothing():
    assert union_years([("2019-01-01", "2024-01-01"), ("2020-01-01", "2021-01-01")]) == union_years(
        [("2019-01-01", "2024-01-01")]
    )


def test_no_periods_means_zero_years():
    assert union_years([]) == 0.0


def _hash(
    kind: str = "skill",
    name: str = "React",
    strength: str = "detailed",
    periods: list[list[str]] | None = None,
    quote: str = "x",
) -> str:
    periods = [["2019-06-01", "2022-03-01"]] if periods is None else periods
    return content_hash(kind=kind, name=name, strength=strength, periods=periods, quote=quote)


def test_content_hash_is_stable():
    assert _hash() == _hash()


@pytest.mark.parametrize(
    "change",
    [
        {"name": "Vue"},
        {"strength": "weak"},
        {"quote": "y"},
        {"kind": "project"},
        {"periods": []},
    ],
)
def test_content_hash_changes_when_any_field_changes(change: dict[str, object]):
    assert _hash(**change) != _hash()  # pyright: ignore[reportArgumentType]
