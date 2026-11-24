"""Eligibility verdicts, decided in code from the extracted restrictions and the profile.

Definitions (CLAUDE.md, `specs/system.md` 11.3):
- not_eligible: an explicit, uncontradicted restriction that the profile's known values do not meet.
- eligible: every explicit restriction is met, at least one explicit location signal is met,
  and nothing is doubtful.
- doubtful: everything else.

The LLM only extracts; it never decides. Facts must already have gone through `verify_facts`.
Phase 2 compares location only: other explicit restrictions make the job `doubtful` until
phase 4 teaches the code to compare them.
"""

import re
from dataclasses import dataclass, field

from src.app.eligibility.places import resolve_places
from src.app.eligibility.result import EligibilityResult
from src.config.data.locations import COUNTRIES, US_PAYROLL_MARKERS
from src.core.text import fold
from src.models.job_facts import JobFacts, Restriction
from src.models.profile import Constraints

_LABEL = {
    "location": "where you must live",
    "citizenship": "citizenship",
    "work_authorization": "work authorization",
    "payroll": "the type of contract",
    "visa": "a visa",
    "timezone": "working hours",
    "modality": "remote or on-site work",
}


@dataclass(frozen=True)
class _Issue:
    """Something that stops the code from being sure either way."""

    reason: str
    quotes: list[str] = field(default_factory=list)
    recruiter_question: str = ""
    profile_question: str = ""


@dataclass
class _Findings:
    met: list[Restriction] = field(default_factory=list)
    anywhere: list[Restriction] = field(default_factory=list)  # the met ones that say "anywhere"
    unmet: list[Restriction] = field(default_factory=list)
    issues: list[_Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _country_name(iso: str) -> str:
    return COUNTRIES.get(iso, (iso,))[0]


def _first_quote(restriction: Restriction) -> str:
    return restriction.quotes[0] if restriction.quotes else ""


def _judge_location(
    restriction: Restriction, constraints: Constraints, contradicted: set[str], found: _Findings
) -> None:
    country = constraints.country
    if country is None:  # never asked: it can only make the job doubtful
        found.issues.append(
            _Issue(
                "Your country is not in your profile yet.",
                restriction.quotes,
                profile_question="Which country do you live in?",
            )
        )
        return

    places = resolve_places(restriction.places)
    if country in places.countries:
        if restriction.evidence_kind == "explicit":
            found.met.append(restriction)  # an inferred hint is never a compatible signal
        return

    # "Work from anywhere" and nothing else about places: open to the user too. Any other
    # restriction of the posting is still judged on its own and can exclude them.
    pure_anywhere = (
        places.worldwide or (not restriction.places and restriction.place_scope == "worldwide")
    ) and not (places.countries or places.ambiguous or places.unknown)
    if pure_anywhere:
        if restriction.evidence_kind == "explicit":
            found.met.append(restriction)
            found.anywhere.append(restriction)
        return

    where = ", ".join(restriction.places) or "an unspecified place"
    question = f"Is the role open to candidates living in {_country_name(country)}?"
    undetermined = (
        places.ambiguous
        or places.unknown
        or places.worldwide
        or not restriction.places
        or restriction.place_scope == "worldwide"
    )
    if undetermined:
        # The unreadable part might include the user's country: not enough to rule them out.
        found.issues.append(
            _Issue(
                f"The posting names a place that cannot be matched to your country ({where}).",
                restriction.quotes,
                recruiter_question=question,
            )
        )
    elif restriction.evidence_kind == "explicit" and restriction.kind not in contradicted:
        found.unmet.append(restriction)
    else:
        found.issues.append(
            _Issue(
                f"The posting hints at a restriction to {where}, which does not include "
                f"{_country_name(country)}.",
                restriction.quotes,
                recruiter_question=question,
            )
        )


def _is_us_payroll(restriction: Restriction) -> bool:
    text = fold(" ".join(restriction.quotes))
    return any(
        re.search(rf"(?<![a-z0-9]){marker}(?![a-z0-9])", text) for marker in US_PAYROLL_MARKERS
    )


def _judge(
    restriction: Restriction, constraints: Constraints, contradicted: set[str], found: _Findings
) -> None:
    label = _LABEL[restriction.kind]
    quote = _first_quote(restriction)
    if restriction.kind == "timezone":  # decided in spike 1.5: shown, never blocks
        found.warnings.append(f'Working hours: "{quote}"' if quote else "Working hours mentioned.")
    elif restriction.evidence_kind == "contradictory":
        found.issues.append(
            _Issue(
                f"The posting contradicts itself about {label}.",
                restriction.quotes,
                recruiter_question=f"The posting says conflicting things about {label}. "
                "Which one applies?",
            )
        )
    elif restriction.kind == "modality":
        return  # covered by `work_modality`
    elif restriction.kind == "payroll" and not _is_us_payroll(restriction):
        # An ordinary contract type says nothing about where you may live: a badge, not a verdict.
        found.warnings.append(f'Contract type: "{quote}"' if quote else "Contract type mentioned.")
    elif restriction.kind == "location":
        _judge_location(restriction, constraints, contradicted, found)
    elif restriction.evidence_kind == "explicit":  # citizenship, authorization, visa, US payroll
        found.issues.append(
            _Issue(
                f"The posting asks about {label}, which is not checked yet.",
                restriction.quotes,
                recruiter_question=f"The posting mentions {label}. Does it apply to me?",
            )
        )
    else:
        found.warnings.append(f"Possible requirement about {label} (inferred, not checked).")


def _not_eligible(found: _Findings, constraints: Constraints) -> EligibilityResult:
    country = _country_name(constraints.country or "")
    parts = [
        f'The posting is limited to {", ".join(r.places)} ("{_first_quote(r)}"), '
        f"and your profile says {country}."
        for r in found.unmet
    ]
    return EligibilityResult(
        "not_eligible",
        " ".join(parts),
        quotes=[quote for r in found.unmet for quote in r.quotes],
        warnings=found.warnings,
    )


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def evaluate_eligibility(facts: JobFacts, constraints: Constraints) -> EligibilityResult:
    if not facts.is_job_posting:
        return EligibilityResult("doubtful", "The text does not look like a job posting.")

    contradicted = {r.kind for r in facts.restrictions if r.evidence_kind == "contradictory"}
    found = _Findings()
    for restriction in facts.restrictions:
        _judge(restriction, constraints, contradicted, found)

    if found.unmet:  # a certain "no" outweighs any doubt elsewhere
        return _not_eligible(found, constraints)

    if facts.work_modality in ("hybrid", "onsite"):
        found.issues.append(
            _Issue(
                f"The job is {facts.work_modality.replace('onsite', 'on-site')}; "
                "office location and distance are not checked yet."
            )
        )

    if found.issues:
        return EligibilityResult(
            "doubtful",
            " ".join(issue.reason for issue in found.issues),
            quotes=_unique([q for issue in found.issues for q in issue.quotes]),
            profile_questions=_unique([i.profile_question for i in found.issues]),
            recruiter_questions=_unique([i.recruiter_question for i in found.issues]),
            warnings=found.warnings,
        )

    country = _country_name(constraints.country or "")
    if found.met:
        first = found.met[0]
        audience = "candidates anywhere" if first in found.anywhere else country
        return EligibilityResult(
            "eligible",
            f'The posting is open to {audience} ("{_first_quote(first)}") and no '
            "restriction you do not meet was found.",
            quotes=[q for r in found.met for q in r.quotes],
            warnings=found.warnings,
        )
    return EligibilityResult(
        "doubtful",
        "The posting says nothing about where you can work from.",
        recruiter_questions=[f"Can this role be done from {country or 'my country'}?"],
        warnings=found.warnings,
    )
