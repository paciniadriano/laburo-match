"""Compare extractions with hand labels; derive verdicts in code (never by the LLM)."""
import json
import re
import sys

from labels import LABELS

LATAM = {"latam", "latin america", "latinoamérica", "latinoamerica", "south america", "sudamérica", "americas"}
norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip(" .,;:")


def overlap(a, b):
    a, b = norm(a), norm(b)
    if a in b or b in a:
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / max(1, min(len(ta), len(tb))) >= 0.6


def places_compatible(r):
    if r["place_scope"] == "worldwide":
        return True
    places = {norm(p) for p in r["places"]}
    if places & LATAM or "argentina" in places:
        return True
    return False if places else None


def verdict(ex, source_country=None):
    """Formal definitions from the spec, applied to the reference profile (AR resident, no US authorization)."""
    rs = ex["restrictions"]
    if any(r["evidence_kind"] == "contradictory" for r in rs):
        return "doubtful"
    explicit_loc = [r for r in rs if r["kind"] == "location" and r["evidence_kind"] == "explicit"]
    if any(places_compatible(r) is False for r in explicit_loc):
        return "not_eligible"
    if ex["work_modality"] in ("hybrid", "onsite"):
        if ex["office_locations"]:
            if not any("argentina" in norm(o) for o in ex["office_locations"]):
                return "not_eligible"
        elif source_country and norm(source_country) != "argentina":
            return "not_eligible"  # office country known from the source, city unknown
    if any(r["kind"] in ("visa", "citizenship", "work_authorization") for r in rs):
        return "doubtful"
    if any(r["kind"] == "payroll" and r["evidence_kind"] != "explicit" for r in rs):
        return "doubtful"
    if explicit_loc and all(places_compatible(r) for r in explicit_loc):
        return "eligible"
    return "doubtful"


data = json.load(open("extractions.json"))
rows, tot = [], {"lab": 0, "hit": 0, "ev_ok": 0, "ev_n": 0, "quotes": 0, "quotes_ok": 0, "spurious": 0}
by_split = {}
for n, lab in sorted(LABELS.items()):
    ex = data[n]["extraction"]
    text = open(f"postings/{n}.txt").read()
    head = text.split("\n")[2]
    m = re.search(r"countries=\['([^']+)'\]", head)
    country = m.group(1) if m and m.group(1) != "Remote" else None
    v = verdict(ex, country)
    hit = 0
    for lr in lab["restrictions"]:
        tot["lab"] += 1
        m = [r for r in ex["restrictions"] if r["kind"] == lr["kind"] and any(overlap(q, lq) for q in r["quotes"] for lq in lr["quotes"])]
        if m:
            hit += 1; tot["hit"] += 1; tot["ev_n"] += 1; tot["ev_ok"] += m[0]["evidence_kind"] == lr["evidence_kind"]
    for r in ex["restrictions"]:
        for q in r["quotes"]:
            tot["quotes"] += 1; tot["quotes_ok"] += q in text
        if not any(r["kind"] == lr["kind"] and any(overlap(q, lq) for q in r["quotes"] for lq in lr["quotes"]) for lr in lab["restrictions"]):
            tot["spurious"] += 1
    s = by_split.setdefault(lab["split"], {"n": 0, "ok": 0})
    s["n"] += 1; s["ok"] += v == lab["verdict"]
    rows.append((n, lab["split"], lab["verdict"], v, f"{hit}/{len(lab['restrictions'])}", len(ex["restrictions"]), lab["doubt"]))

print(f"{'id':3} {'split':5} {'label':13} {'extracted':13} recall  n_extr  doubt")
for r in rows:
    flag = "" if r[2] == r[3] else "  <-- MISMATCH"
    print(f"{r[0]:3} {r[1]:5} {r[2]:13} {r[3]:13} {r[4]:6}  {r[5]:6}  {r[6] or ''}{flag}")
print()
print(f"restriction recall:            {tot['hit']}/{tot['lab']} = {tot['hit']/tot['lab']:.0%}   (threshold >= 90%)")
print(f"evidence_kind correct (hits):  {tot['ev_ok']}/{tot['ev_n']} = {tot['ev_ok']/max(1,tot['ev_n']):.0%}   (threshold >= 80%)")
print(f"quotes verbatim in posting:    {tot['quotes_ok']}/{tot['quotes']}")
print(f"extracted but not labeled:     {tot['spurious']}")
bad = [r for r in rows if r[2] in ("eligible", "doubtful") and r[3] == "not_eligible"]
print(f"valid jobs marked not_eligible: {len(bad)}   (threshold = 0) {[r[0] for r in bad]}")
for sp, s in by_split.items():
    print(f"verdict accuracy {sp}: {s['ok']}/{s['n']}")
print(f"verdict accuracy all: {sum(s['ok'] for s in by_split.values())}/15")
