"""Spike 1.7: levels computed in code from the LLM links, compared with the hand labels.

    uv run python spikes/1.7-linking/evaluate.py [links_runs.json]

Measurement rule (fixed before the first run): thresholds are measured on the requirements WITHOUT a
rule conflict; the conflicts (label != level the rules give from the labelled links) are reported apart.
"""

import json
import sys
from pathlib import Path

from evidence import BY_ID, EDUCATION_RANK, LANGUAGES
from labels import CONFLICTS, LABELS
from levels import is_scored, level_education, level_from_links, level_from_parts, level_language
from model import Link, Requirement
from requirements import BY_KEY, LLM_TYPES, dedupe_key

REP = {}  # dedupe_key -> key of the requirement that was actually sent to the LLM
for _r in BY_KEY.values():
    if _r.type in LLM_TYPES:
        REP.setdefault(dedupe_key(_r), _r.key)


def compute(req: Requirement, run: dict) -> str | None:
    """Level in code. Runs with `parts` (v3) combine per-part levels; older runs use the flat links."""
    if not is_scored(req):
        return None
    if req.type == "education":
        return level_education(req, EDUCATION_RANK).level
    if req.type == "language":
        return level_language(req, LANGUAGES[req.language]).level
    key = REP[dedupe_key(req)]
    if "parts" in run:
        entry = run["parts"].get(key)
        if entry is None:
            return "missing"
        parts = [[Link(i, rel) for i, rel in p["links"]] for p in entry["parts"]]
        return level_from_parts(req, parts, entry["combinator"], BY_ID).level
    raw = run["links"].get(key, [])
    return level_from_links(req, [Link(i, rel) for i, rel in raw], BY_ID).level


def link_sets(req: Requirement, run_links: dict) -> tuple[frozenset, frozenset]:
    raw = run_links.get(REP[dedupe_key(req)], [])
    return (frozenset(i for i, r in raw if r in ("direct", "same", "equivalent")), frozenset(i for i, r in raw if r == "related"))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} = {100 * n / d:.0f}%" if d else "n/a"


def main() -> None:
    path = Path(__file__).with_name(sys.argv[1] if len(sys.argv) > 1 else "links_runs.json")
    data = json.loads(path.read_text())
    runs = data["runs"]
    scored = [k for k, lab in LABELS.items() if lab["level"] is not None]
    conflicts = [k for k in scored if k in CONFLICTS]
    measured = [k for k in scored if k not in conflicts]
    llm_measured = [k for k in measured if BY_KEY[k].type in LLM_TYPES]
    doubtful = [k for k in measured if LABELS[k]["doubt"]]

    def ok(k: str, got: str | None) -> bool:
        return got == LABELS[k]["level"] or got in LABELS[k]["also_ok"]

    print(f"model={data['model']} chunk={data['chunk']} runs={len(runs)} | scored={len(scored)} "
          f"measured={len(measured)} (LLM-linked {len(llm_measured)}) conflicts={conflicts} doubtful={len(doubtful)}\n")

    all_false_met, all_acc, all_acc_llm, all_acc_strict, all_exact = [], [], [], [], []
    for i, run in enumerate(runs, 1):
        got = {k: compute(BY_KEY[k], run) for k in scored}
        false_met = [k for k in measured if got[k] == "met" and LABELS[k]["level"] != "met"]
        conflict_met = [k for k in conflicts if got[k] == "met"]
        acc = sum(ok(k, got[k]) for k in measured)
        acc_llm = sum(ok(k, got[k]) for k in llm_measured)
        strict = [k for k in measured if k not in doubtful]
        acc_strict = sum(ok(k, got[k]) for k in strict)
        exact = sum(
            link_sets(BY_KEY[k], run["links"]) == (frozenset(LABELS[k]["strong"]), frozenset(LABELS[k]["related"]))
            for k in llm_measured
        )
        all_false_met.append(false_met)
        all_acc.append(acc)
        all_acc_llm.append(acc_llm)
        all_acc_strict.append(acc_strict)
        all_exact.append(exact)
        print(f"run {i}: false-met={len(false_met)} {false_met} | accuracy all {pct(acc, len(measured))} "
              f"| LLM-linked {pct(acc_llm, len(llm_measured))} | without doubtful {pct(acc_strict, len(strict))} "
              f"| exact links {pct(exact, len(llm_measured))} | rules-gap rows at `met`: {conflict_met}")

    # Stability: same level (and same links) for every LLM-linked requirement across the runs
    llm_all = [k for k in scored if BY_KEY[k].type in LLM_TYPES]
    lv_same = sum(len({compute(BY_KEY[k], r) for r in runs}) == 1 for k in llm_all)
    lk_same = sum(len({link_sets(BY_KEY[k], r["links"]) for r in runs}) == 1 for k in llm_all)
    print(f"\nstability over {len(runs)} runs ({len(llm_all)} LLM-linked requirements): "
          f"identical level {pct(lv_same, len(llm_all))} | identical links {pct(lk_same, len(llm_all))}")

    # Every disagreement with the labels, for inspection
    print("\nrequirements where any run differs from the label (L=label, then each run's level and links):")
    for k in scored:
        levels = [compute(BY_KEY[k], r) for r in runs]
        exact = all(link_sets(BY_KEY[k], r["links"]) == (frozenset(LABELS[k]["strong"]), frozenset(LABELS[k]["related"]))
                    for r in runs) if BY_KEY[k].type in LLM_TYPES else True
        if all(ok(k, lv) for lv in levels) and exact:
            continue
        tag = " [RULE CONFLICT]" if k in conflicts else (" [doubtful]" if LABELS[k]["doubt"] else "")
        print(f"- {k}{tag}: {BY_KEY[k].text[:70]}")
        print(f"    L={LABELS[k]['level']} strong={LABELS[k]['strong']} related={LABELS[k]['related']}")
        for i, r in enumerate(runs, 1):
            if BY_KEY[k].type in LLM_TYPES:
                if "parts" in r:
                    entry = r["parts"].get(REP[dedupe_key(BY_KEY[k])], {"combinator": "?", "parts": []})
                    shown = "; ".join(
                        f"{p['text'][:28]}: {','.join(f'{i}/{rel[:3]}' for i, rel in p['links']) or '-'}"
                        for p in entry["parts"]
                    )
                    print(f"    run{i}: {levels[i - 1]:<8} {entry['combinator']} | {shown}")
                else:
                    s, rel = link_sets(BY_KEY[k], r["links"])
                    print(f"    run{i}: {levels[i - 1]:<8} strong={sorted(s)} related={sorted(rel)}")
            else:
                print(f"    run{i}: {levels[i - 1]}")

    # Verdict against the thresholds written in specs/phase-1-spikes.md
    print("\n== go / no-go ==")
    fm = max(len(x) for x in all_false_met)
    print(f"0 false `met` (measured set):   {'GO' if fm == 0 else 'NO-GO'}  (worst run: {fm})")
    worst = min(all_acc) / len(measured)
    print(f"level accuracy >= 80%:          {'GO' if worst >= 0.8 else 'NO-GO'}  (worst run: {100 * worst:.0f}%)")
    stab = lv_same / len(llm_all)
    print(f">= 90% identical across runs:   {'GO' if stab >= 0.9 else 'NO-GO'}  ({100 * stab:.0f}%)")


if __name__ == "__main__":
    main()
