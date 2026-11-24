"""Spike 1.4: is the LLM span nested under the tool trace in Opik?"""
import os
import time

import opik
from langchain_openai import ChatOpenAI
from opik import track
from opik.integrations.langchain import OpikTracer

PROJECT = os.environ.get("OPIK_PROJECT", "laburo-match-local")
os.environ["OPIK_PROJECT_NAME"] = PROJECT
llm = ChatOpenAI(model=os.environ.get("LLM_BASE_MODEL", "gpt-6-luna"), use_responses_api=True)


@track(name="spike_tool_call", project_name=PROJECT)
def fake_tool() -> str:
    """Stands in for an MCP tool: one LLM call made inside it."""
    r = llm.invoke("Say OK.", config={"callbacks": [OpikTracer(project_name=PROJECT)]})
    return str(r.content)


fake_tool()
opik.flush_tracker()
client = opik.Opik(project_name=PROJECT)
client.flush()
time.sleep(6)  # ingestion is asynchronous

traces = client.search_traces(project_name=PROJECT, max_results=5)
mine = [t for t in traces if t.name == "spike_tool_call"]
print(f"traces named spike_tool_call: {len(mine)}")
if mine:
    t = mine[0]
    spans = client.search_spans(project_name=PROJECT, trace_id=t.id, max_results=20)
    by_id = {s.id: s for s in spans}
    for s in spans:
        parent = by_id[s.parent_span_id].name if s.parent_span_id in by_id else ("(trace root)" if not s.parent_span_id else "?")
        print(f"  span {s.name!r:28} type={s.type:8} parent={parent}")
