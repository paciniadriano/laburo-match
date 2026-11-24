"""Spike 1.4: ChatOpenAI on the Responses API with the base model."""
import os
import sys
import time
from typing import Literal

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

MODEL = os.environ.get("LLM_BASE_MODEL", "gpt-6-luna")


class Restriction(BaseModel):
    kind: Literal["location", "citizenship", "payroll", "none"]
    evidence_kind: Literal["explicit", "inferred", "contradictory"]
    quote: str


def make(**kw):
    return ChatOpenAI(model=MODEL, use_responses_api=True, **kw)


def t_structured(n=10):
    llm = make().with_structured_output(Restriction, method="json_schema", strict=True)
    posting = "We are hiring a backend engineer. Candidates must be US citizens. Fully remote."
    ok = 0
    for i in range(n):
        try:
            r = llm.invoke(f"Extract the main restriction of this posting:\n{posting}")
            assert isinstance(r, Restriction)
            ok += 1
        except Exception as e:
            print(f"   call {i} failed: {type(e).__name__}: {str(e)[:150]}")
    print(f"1) strict structured output valid: {ok}/{n}")
    return r if ok else None


def t_tool_calling():
    @tool
    def get_weather(city: str) -> str:
        """Get the weather for a city."""
        return "sunny"

    llm = make(reasoning={"effort": "low"}).bind_tools([get_weather])
    r = llm.invoke("What is the weather in Rosario? Use the tool.")
    print(f"2) tool call with reasoning: tool_calls={[(c['name'], c['args']) for c in r.tool_calls]}")


def t_cache():
    prefix = "You are a careful job-posting analyst. Rules:\n" + "\n".join(
        f"Rule {i}: always cite the exact quote from the posting for claim number {i}, never invent facts, and keep answers short."
        for i in range(120)
    )
    llm = make()
    for n in (1, 2):
        r = llm.invoke([("system", prefix), ("user", f"Say OK. (call {n})")])
        u = r.usage_metadata
        print(f"3) call {n}: input={u['input_tokens']} cached={u.get('input_token_details', {}).get('cache_read')} output={u['output_tokens']}")
        time.sleep(2)


def t_params():
    for name, kw in [("temperature=0", {"temperature": 0}), ("temperature=0.7", {"temperature": 0.7}),
                     ("reasoning low", {"reasoning": {"effort": "low"}}), ("reasoning minimal", {"reasoning": {"effort": "minimal"}}),
                     ("reasoning none", {"reasoning": {"effort": "none"}}), ("max_output_tokens=50", {"max_tokens": 50})]:
        try:
            make(**kw).invoke("Say OK.")
            print(f"4) {name:22s} accepted")
        except Exception as e:
            print(f"4) {name:22s} REJECTED: {str(e)[:110]}")


if __name__ == "__main__":
    print("model:", MODEL)
    for f in (t_structured, t_tool_calling, t_cache, t_params):
        try:
            f()
        except Exception as e:
            print(f"{f.__name__} CRASHED: {type(e).__name__}: {str(e)[:200]}")
