"""The search plan. Phase 2 builds it by rule; an LLM planner replaces this in phase 4."""

from dataclasses import dataclass
from typing import Any

from src.models.profile import Preferences

# v1 targets tech roles, and one Get on Board category covers them all.
TECH_CATEGORIES = ("programming",)


@dataclass(frozen=True)
class SearchPlan:
    categories: tuple[str, ...]
    target_roles: tuple[str, ...]

    def summary(self) -> str:
        roles = ", ".join(self.target_roles) or "any role"
        return (
            f"Searched Get on Board, category: {', '.join(self.categories)}. Looking for: {roles}."
        )

    def to_json(self) -> dict[str, Any]:
        """Stored in the run, so every search can be audited later."""
        return {
            "kind": "deterministic",
            "sources": {"getonbrd": {"categories": list(self.categories)}},
            "target_roles": list(self.target_roles),
        }


def build_plan(preferences: Preferences) -> SearchPlan:
    return SearchPlan(
        categories=TECH_CATEGORIES, target_roles=tuple(preferences.target_roles or ())
    )
