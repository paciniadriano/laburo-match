import pytest

from src.core.errors import (
    DomainError,
    ProfileRequiredError,
    RunExpiredError,
    RunNotFoundError,
)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ProfileRequiredError(), "PROFILE_REQUIRED"),
        (RunNotFoundError(), "RUN_NOT_FOUND"),
        (RunExpiredError(), "RUN_EXPIRED"),
    ],
)
def test_each_error_has_a_stable_code_and_an_actionable_message(error: DomainError, code: str):
    assert error.error_code == code
    assert error.message  # never empty
    assert str(error) == error.message


def test_codes_are_unique():
    codes = [cls.error_code for cls in DomainError.__subclasses__()]
    assert len(codes) == len(set(codes))
