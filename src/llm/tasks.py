"""The registry of LLM tasks.

Every call to a model is a named task declared here: its prompt, its output contract and its
parameters. Callers say `llm.run("job_extraction", text)` and never touch a provider.
`temperature` is deliberately absent: the base model rejects it with a 400.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from src.models.job_facts import JobFacts
from src.prompts.job_extraction import SYSTEM_PROMPT as JOB_EXTRACTION_PROMPT


@dataclass(frozen=True)
class LLMTask:
    name: str
    system_prompt: str  # stable prefix: no dates, ids or user data
    output_schema: type[BaseModel]
    # Tag that fences the untrusted input in the user message, e.g. "posting".
    input_tag: str
    # (input, expected JSON) pairs, also part of the stable prefix.
    few_shots: tuple[tuple[str, str], ...] = ()
    model: str = ""  # "" = use LLM_BASE_MODEL
    # `minimal` is rejected by the base model; `none` and `low` work.
    reasoning_effort: Literal["none", "low", "medium", "high"] = "low"
    max_output_tokens: int | None = None


JOB_EXTRACTION = LLMTask(
    name="job_extraction",
    system_prompt=JOB_EXTRACTION_PROMPT,
    output_schema=JobFacts,
    input_tag="posting",
)

LLM_TASKS: dict[str, LLMTask] = {task.name: task for task in (JOB_EXTRACTION,)}


def get_task(name: str) -> LLMTask:
    try:
        return LLM_TASKS[name]
    except KeyError:
        raise KeyError(f"Unknown LLM task {name!r}. Known tasks: {sorted(LLM_TASKS)}") from None
