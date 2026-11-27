"""What model calls cost, and a budget that stops spending when it runs out."""

from dataclasses import dataclass

from src.core.errors import BudgetExceededError, UnknownModelPriceError
from src.llm.backend import Usage

_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    cached_input_per_million: float  # input tokens served from the provider's prompt cache
    output_per_million: float


# Standard rates in USD per million tokens, read on 2026-11-27 from
# https://developers.openai.com/api/docs/pricing and the model page. Prices change: check them
# again before trusting a cost figure, and add a model here before using it in an eval.
PRICES: dict[str, ModelPrice] = {
    "gpt-6-luna": ModelPrice(
        input_per_million=0.10, cached_input_per_million=0.01, output_per_million=0.50
    ),
}


def cost_usd(model: str, usage: Usage) -> float:
    """An unknown model is an error, not a free call: a guard that cannot price a call is blind."""
    price = PRICES.get(model)
    if price is None:
        raise UnknownModelPriceError(model)
    uncached = usage.input_tokens - usage.cached_tokens  # `input_tokens` includes the cached ones
    return (
        uncached * price.input_per_million
        + usage.cached_tokens * price.cached_input_per_million
        + usage.output_tokens * price.output_per_million
    ) / _MILLION


class BudgetGuard:
    """Adds up what was spent and refuses new calls once the limit is reached.

    Calls running in parallel when the limit is crossed still finish, so the real total can
    exceed the limit by the cost of a few calls.
    """

    def __init__(self, limit_usd: float) -> None:
        self.limit_usd = limit_usd
        self.spent_usd = 0.0

    def ensure_room(self) -> None:
        if self.spent_usd >= self.limit_usd:
            raise BudgetExceededError(self.limit_usd)

    def charge(self, model: str, usage: Usage) -> float:
        cost = cost_usd(model, usage)
        self.spent_usd += cost
        return cost
