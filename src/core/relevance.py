"""How much a job title looks like the roles the user wants, as a count of shared words.

Shared by search (which jobs go first in the queue), the shortlist and `list_jobs` (which cards
go first until matching gives a fit band, phase 5). It compares words, so it cannot tell that
"UI Engineer" is close to "Frontend Developer": smarter matching comes later.
"""

import re
import unicodedata

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
