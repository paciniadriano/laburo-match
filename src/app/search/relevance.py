"""Order jobs by how much their title looks like the roles the user wants.

This only decides which jobs fit under the cap; it never discards. It compares words, so it
cannot tell that "UI Engineer" is close to "Frontend Developer": the role-family blocklist and
smarter matching come in phase 4.
"""

import re
import unicodedata

from src.app.jobs.candidate import Candidate

# Words that name the kind of work in different ways but mean the same thing here.
_DEV = {
    "developer", "developers", "engineer", "engineers", "dev",
    "desarrollador", "desarrolladora", "ingeniero", "ingeniera", "programador", "programadora",
}  # fmt: skip
# Seniority and filler say nothing about which role it is.
_IGNORED = {
    "senior", "sr", "ssr", "semi", "semisenior", "junior", "jr", "lead", "de", "del", "la", "el",
    "en", "y", "and", "the", "a", "for", "of", "con", "para",
}  # fmt: skip


def _words(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    found = re.findall(r"[a-z0-9+#]+", plain)
    return {"dev" if word in _DEV else word for word in found if word not in _IGNORED}


def title_relevance(title: str, target_roles: tuple[str, ...]) -> int:
    """Words the title shares with the best-matching target role."""
    title_words = _words(title)
    return max((len(_words(role) & title_words) for role in target_roles), default=0)


def rank(candidates: list[Candidate], target_roles: tuple[str, ...]) -> list[Candidate]:
    """Most relevant first, then newest first; jobs with no date go last among equals."""
    no_date = 0.0
    return sorted(
        candidates,
        key=lambda c: (
            -title_relevance(c.title, target_roles),
            -(c.posted_at.timestamp() if c.posted_at else no_date),
            c.title,  # a stable order when everything else ties
        ),
    )
