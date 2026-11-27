"""What calls cost, and the budget that stops spending."""

import pytest

from src.core.errors import BudgetExceededError, UnknownModelPriceError
from src.core.usage import BudgetGuard, cost_usd
from src.llm.backend import Usage


def test_cost_prices_cached_input_apart_from_the_rest():
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000, cached_tokens=400_000)

    # 600k uncached at 0.10, 400k cached at 0.01, 1M output at 0.50
    assert cost_usd("gpt-6-luna", usage) == pytest.approx(0.06 + 0.004 + 0.50)


def test_a_model_without_a_price_is_an_error_not_a_free_call():
    with pytest.raises(UnknownModelPriceError):
        cost_usd("gpt-unknown", Usage(input_tokens=1))


def test_the_guard_adds_up_and_refuses_once_the_limit_is_reached():
    guard = BudgetGuard(limit_usd=0.000_05)
    guard.ensure_room()

    guard.charge("gpt-6-luna", Usage(input_tokens=1_000, output_tokens=0))  # $0.0001
    assert guard.spent_usd == pytest.approx(0.0001)
    with pytest.raises(BudgetExceededError):
        guard.ensure_room()
