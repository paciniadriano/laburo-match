# Spike 1.4 — LLM layer (local notes, not committed)
Model: gpt-6-luna via ChatOpenAI(use_responses_api=True). GO on all thresholds.
- Strict structured output (`with_structured_output(method="json_schema", strict=True)`): 10/10 valid.
- Tool calling with reasoning (effort low): works.
- Prompt caching: 3254 of 3269 input tokens cached on the 2nd call (stable prefix ~3.2k tokens).
- Params: `temperature` REJECTED (400) for any value; reasoning effort `low` and `none` accepted, `minimal` rejected; max_tokens accepted.
- Opik: LLM span nested under the tool trace (OpikTracer inside an @track function). SDK reads project from OPIK_PROJECT_NAME; our .env uses OPIK_PROJECT, so settings must pass it explicitly.
- Models available on the key: gpt-6-astra, gpt-6-luna, gpt-6-sol, gpt-6.1-sol, gpt-6.1-terra, gpt-6.2-astra, gpt-6.2-sol. Prices not yet checked.
