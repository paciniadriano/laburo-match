"""Order jobs by how much their title looks like the roles the user wants.

This only decides which jobs go first in the queue (and fit under the safety limit); it never
discards.
"""

from src.app.jobs.candidate import Candidate
from src.core.relevance import title_relevance


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
