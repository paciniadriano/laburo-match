"""Seed the fictional sample profile (dev and demo only; never real data).

Everything is an upsert (`INSERT ... ON CONFLICT DO UPDATE`): the database decides whether a row
exists, atomically, so running the seed twice never duplicates anything and picks up edits made
to the sample file. The real profile arrives through CV upload in phase 3.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.profile.evidence import content_hash, union_years
from src.core.text import normalize_name
from src.db.models import Evidence, Profile, User
from src.models.profile import Constraints, Exclusions, Preferences

LOCAL_USER = "local"


@dataclass(frozen=True)
class SeedResult:
    user_id: Any
    evidence_seeded: int
    languages_skipped: int


def _evidence_row(user_id: Any, item: dict[str, Any]) -> dict[str, Any]:
    periods = item.get("periods", [])
    quote = item.get("note", "")
    return {
        "user_id": user_id,
        "label": item["id"],
        "kind": item["kind"],
        "name": item["name"],
        "normalized_name": normalize_name(item["name"]),
        "periods": periods,
        "years": union_years(periods) if periods else None,
        "quote": quote,
        "strength": item["strength"],
        "source": "cv",
        "content_hash": content_hash(
            kind=item["kind"],
            name=item["name"],
            strength=item["strength"],
            periods=periods,
            quote=quote,
        ),
        "active": True,
    }


async def seed_sample_profile(
    session: AsyncSession, sample: dict[str, Any], max_job_age_days: int
) -> SeedResult:
    """`sample` is the parsed sample file: the caller reads the disk, not this async function."""

    # The upsert returns the id whether the row was just created or already existed.
    users = insert(User).values(external_id=LOCAL_USER)
    user_id = await session.scalar(
        users.on_conflict_do_update(
            index_elements=["external_id"], set_={"external_id": users.excluded.external_id}
        ).returning(User.id)
    )

    profile = {
        "user_id": user_id,
        "constraints": Constraints(
            country="AR",
            citizenships=["AR"],
            work_authorizations=["AR"],
            accepted_modalities=["remote"],
        ).model_dump(mode="json"),
        "preferences": Preferences(
            target_roles=["Frontend Engineer", "Full-Stack Developer"]
        ).model_dump(mode="json"),
        "exclusions": Exclusions(max_job_age_days=max_job_age_days).model_dump(mode="json"),
        "is_complete": True,
    }
    profiles = insert(Profile).values(**profile)
    await session.execute(
        profiles.on_conflict_do_update(
            index_elements=["user_id"],
            set_={key: profiles.excluded[key] for key in profile if key != "user_id"},
        )
    )

    # Language levels (CEFR) need columns and a mapping table that arrive in phase 3.
    items = [item for item in sample["evidence"] if item["kind"] != "language"]
    rows = [_evidence_row(user_id, item) for item in items]
    evidence = insert(Evidence)
    await session.execute(
        evidence.on_conflict_do_update(
            index_elements=["user_id", "label"],
            set_={
                key: evidence.excluded[key] for key in rows[0] if key not in ("user_id", "label")
            },
        ),
        rows,
    )
    return SeedResult(
        user_id=user_id,
        evidence_seeded=len(rows),
        languages_skipped=len(sample["evidence"]) - len(items),
    )
