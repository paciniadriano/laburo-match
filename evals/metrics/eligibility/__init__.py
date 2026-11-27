"""Scores for the eligibility eval: pure functions on (expected, predicted) pairs, no LLM."""

from dataclasses import dataclass

CLASSES = ("eligible", "doubtful", "not_eligible")


@dataclass(frozen=True)
class Outcome:
    job: str
    expected: str
    predicted: str
    reason: str = ""


@dataclass(frozen=True)
class ClassScore:
    precision: float | None  # None: the class was never predicted, so there is nothing to measure
    recall: float | None  # None: the class has no items in the dataset
    support: int  # items of this class in the dataset


@dataclass(frozen=True)
class Scores:
    total: int
    correct: int
    per_class: dict[str, ClassScore]
    confusion: dict[str, dict[str, int]]  # confusion[expected][predicted]
    # Jobs labelled `eligible` or `doubtful` that the system called `not_eligible`: a valid
    # job the user would never see. The gate of this eval is that this list is empty.
    wrongly_discarded: list[str]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def score(outcomes: list[Outcome]) -> Scores:
    confusion = {e: {p: 0 for p in CLASSES} for e in CLASSES}
    for outcome in outcomes:
        confusion[outcome.expected][outcome.predicted] += 1
    per_class = {}
    for name in CLASSES:
        hits = confusion[name][name]
        predicted = sum(confusion[e][name] for e in CLASSES)
        support = sum(confusion[name].values())
        per_class[name] = ClassScore(_ratio(hits, predicted), _ratio(hits, support), support)
    return Scores(
        total=len(outcomes),
        correct=sum(confusion[c][c] for c in CLASSES),
        per_class=per_class,
        confusion=confusion,
        wrongly_discarded=[
            o.job
            for o in outcomes
            if o.predicted == "not_eligible" and o.expected != "not_eligible"
        ],
    )
