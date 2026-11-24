# Spike 1.7 — Linking + level rules (in progress)

Setup: reference profile Martina Sosa (31 evidence items, 27 visible to the LLM, built by hand);
5 postings (01, 04, 09, 11, 14), 35 requirements (32 scored, 27 linked by the LLM, 33 unique keys).
Labels written before any run; 8 doubtful (user-reviewed: p01-r04 -> partial, p11-r02 missing or partial).
Measurement rule fixed before the first run: thresholds on the 30 requirements without a rule conflict;
the 2 rule conflicts (p01-r04 "advanced", p14-r05 "familiar with CI/CD") reported apart.
Model gpt-6-luna, effort low, chunk 15 (2 calls per run), ~2.2-2.5k tokens in (99% cached from run 2), ~1.3-1.7k out.

## Level rules (levels.py): all table tests pass, $0
Union of intervals (8.9y union vs 10.5y sum for the overlapping jobs), gap not counted, §11.4 table, CEFR, education.

## Results
| version | false met (per run) | accuracy (worst / best) | identical level across 3 runs | exact links |
|---|---|---|---|---|
| v1 (compound rule per item) | 0 / 0 / 1 | 73% / 80% | 81% | 56-60% |
| v2 (Plan B: judge items together + 4 one-line examples) | 2 / 0 / 1 | 83% / 90% | 93% | 60-72% |
Go/no-go: v1 NO-GO x3; v2 accuracy GO, stability GO, **false met NO-GO**.

## Findings
1. The compound decision is the fragile part, in both directions. v1 (each item judged alone) was too cautious:
   "React and TypeScript" with both items -> related. v2 (items judged together) was too generous:
   "developing and consuming APIs, microservices and event-driven" -> E9 (builds APIs) + E13 (consumes APIs)
   linked as same in 2/3 runs, ignoring microservices and event-driven -> false met on a non-doubtful label.
2. p04-r03 "Third-party API integrations" <- GraphQL/Apollo as same in 1/3 runs in both versions (semantic stretch).
3. Rule gaps are real: in v2 both conflicts went to `met` in 3/3 runs (the model now links "familiar with CI/CD"
   and "advanced Node.js" as same). In v1 the model had compensated by linking them as related, reading the qualifier
   from the evidence note. Qualifiers ("advanced", "basic", "coursework", "familiar with") are not handled by code.
4. Over-linking on missing requirements is harmless here (partial, never met): p11-r02 <- E7/E19 (code migration),
   p14-r07 <- E19.
5. Prompt prefix caching works (2521/2527 tokens cached on runs 2-3).

## Iteration v3 (re-plan): link per part + `weak` evidence strength (pre-registered thresholds unchanged)
Rules: level per part with the §11.4 table, combined in code (all: met only if every part met; any: best part).
Evidence E22 Docker, E23 Python, E26 Cloud platforms, E27 CI/CD -> `weak` (never `met`). p14-r05 joins the measured set (31).
Re-evaluation of old runs with the weak rule (no LLM calls): v1 false met 0/0/1, acc 74-81%, stab 81%;
v2 false met 2/0/1 (p14-r04, p04-r03 remain: linking errors, not rule errors), acc 84-90%, stab 93%.

| version | false met (per run) | accuracy (worst / best) | identical level | tokens per run |
|---|---|---|---|---|
| v3 parts, no examples | **0 / 0 / 0** | 77% / 94% | 78% | 2.5k in (99% cached) / 2.6-3.2k out |
Go/no-go v3: false met GO; accuracy NO-GO (worst 77%); stability NO-GO (78%).

Findings v3:
- Every compound trap is `partial` in 3/3 runs, whatever the per-part relations were: p14-r04 (APIs + microservices +
  event-driven), p14-r03 (Python coursework + AWS + distributed), p09-r03 (Postgres + Supabase), p01-r05 (relational + NoSQL).
  The decision moved to code and stopped depending on the model's mood.
- All remaining errors and flips are between adjacent levels and in the cautious direction (met->partial, missing->partial);
  none produces a `met`.
- Main sources: years requirements linked as related in run 1 (p01-r03, p04-r01; v2 had them right with its examples);
  "JavaScript or TypeScript for writing migration scripts" split with the purpose phrase -> related (p11-r05);
  over-linking E19/E7 on missing requirements (p14-r07, p11-r02).
- Output tokens roughly double vs v1/v2 (parts are verbose).
- Caveat: three iterations tuned on the same 35 requirements -> numbers are optimistic; a held-out check is needed.

## Iteration v4: split once into atoms (split.py) + relation direct/related, only `direct` counts (link_atoms.py)
27 requirements -> 64 atoms (58 unique). Linking per unique atom, chunk 15 (4 calls/run), ~4.2k tokens in (99.7% cached
from run 2), ~1k out (v3: 2.5-3.2k out). Combination in code (level_from_parts). Labels changed before the run:
p04-r03, p09-r04, p11-r06 partial -> missing (partial only through a related link). Measured set 31, conflict p01-r04.

| version | false met (per run) | accuracy (worst / best) | identical level | out tokens/run |
|---|---|---|---|---|
| v3 | 0 / 0 / 0 | 77% / 94% | 78% | 2.6-3.2k |
| v4 atoms | 0 / **1 / 1** (p04-r03 both) | **84% / 87%** | **93%** | ~1k |
Go/no-go v4: accuracy GO, stability GO, false met strict NO-GO (one requirement, 2 of 3 runs).

Findings v4:
- The only false `met` is p04-r03 "Third-party API integrations" <- E13 (consumes a GraphQL API) as direct in 2/3 runs.
  Label was already doubtful and was changed by definition before the run; it is a genuine semantic stretch.
- Open rule gap unchanged: p01-r04 "Advanced" is `met` in 3/3 runs (rules cannot see the requirement qualifier).
- Compound traps (p14-r03, p14-r04, p09-r03, p01-r05) stay `partial` 3/3, as in v3, with a third of the output tokens.
- Cost of the new definition: a relation-boundary error now costs a full level. p04-r02 "SQL" <- PostgreSQL was linked
  `related` in 3/3 runs -> missing (label met). Also p04-r01 "software engineering": model linked achievements
  (E19/E20) instead of the jobs, while the identical-meaning atom "software development" (p01-r03, p14-r01) was right.
- Remaining differences vs labels are in the cautious direction, except p04-r03 and p01-r04.
- Four iterations on the same 35 requirements: held-out postings (05, 12) still pending; Plan B (larger model for
  linking only) still unused.

### Post-result relabel (decided by the user after seeing v4, recorded as such)
p04-r03 "Third-party API integrations": label `missing` -> `met` (`partial` also accepted). The `missing` label came from the
mechanical effect of the new related definition, not from a judgment; consuming GraphQL APIs is a defensible `met`.
Strict numbers (original label): false met 0/1/1, accuracy 84-87%, stability 93%. Adjusted numbers: see the next run of
evaluate.py on links_runs_v4.json. Both are to be quoted together.

### v4 on the main set with the post-result relabel (p04-r03 -> met, partial accepted)
False met 0/0/0, accuracy 84% / 87% / 87%, identical level 93%. Strict numbers (original label): false met 0/1/1.

## Held-out check: postings 05 and 12 (never seen during v1-v4)
Requirements and labels written before any run (23 requirements, 20 scored, 18 to the LLM, 7 doubtful; no rule conflict
declared). User decisions before the run: p12-r01 -> partial (conservative), p05-r02 -> met with partial accepted.
Split once (48 atoms, 48 unique), linking chunk 15 (4 calls/run), 3 runs, same thresholds.

| false met per run | accuracy | identical level | identical links |
|---|---|---|---|
| **0 / 0 / 0** | **90% / 90% / 90%** (100% without the 7 doubtful) | **94%** | 72% |
Go/no-go held-out: all three GO.
Disagreements with the labels: p05-r01 (full-stack 5+ years: only E9 linked as direct -> partial, label met) and p05-r07
(SQL <- PostgreSQL linked related -> partial/missing, label met): both doubtful, both in the cautious direction, 3/3 runs.

## Final verdict spike 1.7: GO (design v4)
- Design: split each requirement once per job into atoms (combinator all/any); the LLM links atoms to evidence with one
  level-affecting relation (`direct`; `related` is only an argument hint); code computes atom levels (years union,
  detailed/mention/weak) and combines atoms. No judgement of "does the evidence cover the whole requirement" by the LLM.
- Evidence: main set 31 measured requirements, held-out 20: 0 false met after the final design; accuracy 84-90%; 93-94% stable.
- Cost per run: ~4.1-4.2k tokens in (up to 99.7% cached), ~1k out; split ~1k in / ~1k out once per job.
- Known limits, not hidden: (1) qualifiers inside the REQUIREMENT ("advanced", "strong") are not checked by code (p01-r04
  is `met` in 3/3 runs); (2) SQL <- PostgreSQL judged related in 3/3 runs on both sets (cautious, costs a level; needs an
  example in the prompt, to re-validate with a new held-out set); (3) the split itself was run once per set: its stability
  across calls is unmeasured (cached per job in the product); (4) one profile, 58 requirements, one model; (5) four design
  iterations on the first set, one label changed after seeing results (recorded); (6) criteria fixed on the main set were
  reused for the held-out labels, so the held-out is untouched in data, not in criteria.
