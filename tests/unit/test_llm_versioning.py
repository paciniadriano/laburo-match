from dataclasses import replace

import pytest
from pydantic import BaseModel

from src.config.settings import Settings
from src.llm.tasks import JOB_EXTRACTION, LLM_TASKS, get_task
from src.llm.versioning import resolve_model, version_hash

SETTINGS = Settings.from_env_file(None)


class OtherSchema(BaseModel):
    answer: str


def test_the_hash_is_deterministic():
    assert version_hash(JOB_EXTRACTION, SETTINGS) == version_hash(JOB_EXTRACTION, SETTINGS)


@pytest.mark.parametrize(
    "changed",
    [
        replace(JOB_EXTRACTION, system_prompt=JOB_EXTRACTION.system_prompt + " Be brief."),
        replace(JOB_EXTRACTION, few_shots=(("in", "out"),)),
        replace(JOB_EXTRACTION, output_schema=OtherSchema),
        replace(JOB_EXTRACTION, reasoning_effort="high"),
        replace(JOB_EXTRACTION, max_output_tokens=500),
        replace(JOB_EXTRACTION, model="another-model"),
    ],
    ids=["prompt", "few_shots", "schema", "effort", "max_tokens", "task_model"],
)
def test_the_hash_changes_when_anything_that_shapes_the_output_changes(changed):
    assert version_hash(changed, SETTINGS) != version_hash(JOB_EXTRACTION, SETTINGS)


def test_the_hash_changes_when_the_base_model_changes():
    other = SETTINGS.model_copy(update={"llm_base_model": "some-other-model"})

    assert version_hash(JOB_EXTRACTION, other) != version_hash(JOB_EXTRACTION, SETTINGS)


def test_a_task_override_wins_over_the_base_model():
    overridden = replace(JOB_EXTRACTION, model="bigger-model")

    assert resolve_model(JOB_EXTRACTION, SETTINGS) == SETTINGS.llm_base_model
    assert resolve_model(overridden, SETTINGS) == "bigger-model"


def test_every_registered_task_is_found_by_its_name():
    for name, task in LLM_TASKS.items():
        assert get_task(name) is task


def test_an_unknown_task_fails_with_the_list_of_known_ones():
    with pytest.raises(KeyError, match="job_extraction"):
        get_task("does_not_exist")
