"""A fingerprint of the profile inputs that change a job's verdict.

Each screened row stores the fingerprint it was computed with. A row whose fingerprint differs
from today's was computed for a profile the user no longer has, so it is `stale` and must be
screened again (cheap: the extracted job facts are cached, only code runs).

Today the verdict depends on the constraints alone. Later phases add the evidence set hash and
the preferences used for fit and seniority; they join the payload here.
"""

import hashlib
import json
from typing import Any

from src.models.profile import Constraints


def _canonical(value: Any) -> Any:
    """Lists are sets for our purposes: ["AR", "ES"] and ["ES", "AR"] mean the same thing."""
    return sorted(value) if isinstance(value, list) else value


def screening_hash(constraints: Constraints) -> str:
    payload = {key: _canonical(value) for key, value in constraints.model_dump().items()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
