"""Which model runs a task and the automatic version of everything that shapes its output."""

import hashlib
import json

from src.config.settings import Settings
from src.llm.tasks import LLMTask


def resolve_model(task: LLMTask, settings: Settings) -> str:
    return task.model or settings.llm_base_model


def version_hash(task: LLMTask, settings: Settings) -> str:
    """Hash of prompt + examples + output schema + model + parameters.

    Cached results (extractions, links) are stored with this hash and reused only while it is
    unchanged, so changing any of those inputs invalidates the cache without anyone having to
    remember to.
    """
    payload = {
        "system_prompt": task.system_prompt,
        "few_shots": task.few_shots,
        "schema": task.output_schema.model_json_schema(),
        "model": resolve_model(task, settings),
        "reasoning_effort": task.reasoning_effort,
        "max_output_tokens": task.max_output_tokens,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
