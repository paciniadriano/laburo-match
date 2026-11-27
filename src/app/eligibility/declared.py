"""What the source itself declares about who may apply, as evidence for eligibility.

Get on Board pages carry a policy block the employer fills in: "Fully remote: candidates can
reside anywhere in the world", "Locally remote only: candidates must reside in Chile", or a
hybrid/on-site office country. It is explicit and structured, so it counts as an explicit
signal, apart from the posting text: it can open a job that "says nothing about where", and it
can rule one out. When it disagrees with a clear statement in the text, the job is doubtful,
never discarded.
"""

from dataclasses import dataclass

from src.core.places import resolve_places


@dataclass(frozen=True)
class Declared:
    source: str = ""  # "Get on Board": named in the evidence shown to the user
    modality: str = "unknown"  # remote / hybrid / onsite / unknown
    offices: str = ""  # countries of the office of a hybrid or on-site job: "Chile"
    residence: str = ""  # who may apply to a remote job: "anywhere", "Chile, Argentina", ""


@dataclass(frozen=True)
class DeclaredSignal:
    open: bool  # True: the source says the user may apply; False: it says they may not
    reason: str  # a sentence for the verdict
    quote: str  # the evidence shown on the card, marked as the source's, never as posting text


def _countries(text: str) -> list[str]:
    return [place.strip() for place in text.split(",") if place.strip()]


def read_declared(declared: Declared, country: str | None) -> DeclaredSignal | None:
    """None when the source says nothing the code can be sure of for this user."""
    if country is None or not declared.source:
        return None
    on = f"As listed on {declared.source}"
    if declared.modality == "remote" and declared.residence == "anywhere":
        return DeclaredSignal(
            True,
            f"{declared.source} lists it as fully remote, open to candidates anywhere",
            f"{on}: candidates can reside anywhere in the world",
        )
    if declared.modality == "remote" and declared.residence:
        places = resolve_places(_countries(declared.residence))
        quote = f"{on}: candidates must reside in {declared.residence}"
        if country in places.countries:
            reason = f"{declared.source} lists it as remote for people in {declared.residence}"
            return DeclaredSignal(True, reason, quote)
        if places.countries and not (places.unknown or places.ambiguous or places.worldwide):
            reason = f"{declared.source} lists it as remote only for people in {declared.residence}"
            return DeclaredSignal(False, reason, quote)
        return None
    if declared.modality in ("hybrid", "onsite") and declared.offices:
        places = resolve_places(_countries(declared.offices))
        clean = places.countries and not (places.unknown or places.ambiguous or places.worldwide)
        if clean and country not in places.countries:
            kind = "hybrid" if declared.modality == "hybrid" else "on-site"
            return DeclaredSignal(
                False,
                f"{declared.source} lists it as {kind} with its office in {declared.offices}",
                f"{on}: {kind} job in {declared.offices}",
            )
    return None
