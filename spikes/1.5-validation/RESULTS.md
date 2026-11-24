# Spike 1.5 — Idea validation (local notes, not committed)
15 Get on Board postings (programming category, 288 fetched), hand labels written BEFORE extraction (reference profile: AR citizen/resident, no US authorization). Model gpt-6-luna, reasoning low, strict structured output, text only. Verdicts computed in code. Single run, prompt not tuned.

| Threshold | Measured | |
|---|---|---|
| recall of explicit restrictions >= 90% | 19/20 strict (95%); the one miss is a quote-boundary artifact of my matching, effective 20/20 | GO |
| evidence_kind correct >= 80% | 17/19 (89%) | GO |
| 0 valid jobs marked not_eligible | 0 | GO |
| >= 3/15 with a location restriction the aggregator does not show | 8/15 (aggregator fields: remote_zone empty in all 288; countries = "Remote") | GO |
| cost per job recorded | 1,247 input + 257 output tokens/job (15 jobs: 18,715 in, 3,858 out, 0 cached). Price per token NOT verified yet | pending price check |

Verdict accuracy 15/15 (dev 10/10, test 5/5) after the label for 14 was corrected by the user.
Quotes verbatim: 46/46.

## Findings
- Aggregator hides location: remote_zone is empty for all 288 jobs; restrictions live in free text (residence in Colombia/Venezuela, "any US state", LATAM only, time zones, B1/B2 visa, 1099).
- Model false positive: posting 07 "remote role based in LATAM with required travel" flagged `contradictory` (it is not). A false contradictory turns an eligible job into doubtful.
- Posting 06 is a real contradiction (100% remote vs hybrid in Las Condes): detected.
- Posting 14 (hybrid, city not in the text, country Chile only in the source's structured field): needs the source country as an input to the verdict. User decided: country mismatch + hybrid/on-site => not_eligible (spec 11.3 and CLAUDE.md updated).
- Not covered by the sample: citizenship, work authorization, W2/SSN, clearance. Highest-risk categories remain untested: synthetic cases in the eligibility eval (phase 2/4).
- User answers: timezone overlap does not block eligibility (shown as a warning); "1099 Contractor" = inferred payroll; remote with no location text = doubtful.
- Labels are mine (Claude), extraction is GPT: different families, but n=15 and one labeler.
