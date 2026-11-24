"""Export the spike labels to the committed datasets (run once; the JSON is the source of truth afterwards).

    uv run python spikes/export_datasets.py
"""

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SP15 = ROOT / "spikes" / "1.5-validation"
SP17 = ROOT / "spikes" / "1.7-linking"
FIX = "fixtures/postings/getonbrd/{}.txt"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compact(d: dict) -> dict:
    """Drop empty defaults so the JSON reads like the labels did."""
    return {k: v for k, v in d.items() if v is not None and v != "" and v != []}  # keep False: it is a value


def squash(s: str) -> str:
    return " ".join(s.split()).casefold()


def write(rel: str, data: dict) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {rel}")


def eligibility() -> None:
    labels = load("labels_15", SP15 / "labels.py").LABELS
    for split in ("dev", "test"):
        items = []
        for job, lab in sorted(labels.items()):
            if lab["split"] != split:
                continue
            fixture = FIX.format(job)
            text = squash((ROOT / fixture).read_text(encoding="utf-8"))
            for r in lab["restrictions"]:
                for q in r["quotes"]:
                    assert squash(q) in text, f"quote not in {fixture}: {q}"
            items.append(compact({
                "job": job, "fixture": fixture, "verdict": lab["verdict"],
                "hidden_by_aggregator": lab["hidden"], "doubt": lab["doubt"],
                "restrictions": lab["restrictions"],
            }))
        write(f"evals/datasets/{split}/eligibility.json", {
            "dataset": "eligibility", "split": split,
            "source": "spike 1.5: hand labels written before any extraction run",
            "reference_profile": "Argentine citizen, resident in Argentina, no US work authorization",
            "items": items,
        })


def matching() -> None:
    sys.path.insert(0, str(SP17))
    import evidence, labels, requirements  # noqa: E401  (the 1.7 spike modules)

    write("data/samples/sample_evidence.json", {
        "profile": "Martina Sosa (fictional), data/samples/sample_cv.pdf",
        "as_of": "2026-11-22",
        "education_rank": evidence.EDUCATION_RANK,
        "evidence": [
            compact({**asdict(e), "periods": [[s.isoformat(), t.isoformat()] for s, t in e.periods]})
            for e in evidence.EVIDENCE
        ],
    })
    ids = {e.id for e in evidence.EVIDENCE}
    sets = {
        "dev": (requirements.REQUIREMENTS_MAIN, labels.LABELS_MAIN, ["p01-r04"],
                ["p04-r03 relabelled missing -> met (partial accepted) after seeing the v4 results; recorded as such"]),
        "test": (requirements.REQUIREMENTS_HOLDOUT, labels.LABELS_HOLDOUT, [],
                 ["held out: never used while designing or tuning the linking"]),
    }
    for split, (reqs, labs, excluded, notes) in sets.items():
        items = []
        for r in reqs:
            lab = labs[r.key]
            for i in lab["strong"] + lab["related"]:
                assert i in ids, (r.key, i)
            assert (ROOT / FIX.format(r.job)).exists(), r.job
            items.append({**compact(asdict(r)), "label": compact(dict(lab)) | {"level": lab["level"]}})
        write(f"evals/datasets/{split}/matching.json", {
            "dataset": "matching", "split": split,
            "source": "spike 1.7: labels written before each set was run",
            "profile_evidence": "data/samples/sample_evidence.json",
            "postings": {j: FIX.format(j) for j in sorted({r.job for r in reqs})},
            "excluded_from_thresholds": excluded,
            "notes": notes,
            "items": items,
        })


if __name__ == "__main__":
    eligibility()
    matching()
    counts = {}
    for f in sorted((ROOT / "evals/datasets").rglob("*.json")):
        counts[str(f.relative_to(ROOT))] = len(json.loads(f.read_text())["items"])
    ev = len(json.loads((ROOT / "data/samples/sample_evidence.json").read_text())["evidence"])
    print("items:", counts, "| evidence:", ev)
