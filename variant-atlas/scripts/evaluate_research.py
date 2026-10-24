"""Evaluate frozen scientific contracts; model/researcher gates are reported separately."""
import hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import ROOT
from app.science import ScientificData
from app.research_schemas import ResearchCriteria

s = ScientificData()
root = ROOT / "data/reference_cases"
cases = {}
for name in ["pten-reference-v1", "pten-heldout-v1"]:
    p = root / (name + ".json")
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == (root / (name + ".sha256")).read_text().strip()
    )
    cases[name] = json.loads(p.read_text())
r = cases["pten-reference-v1"]
assert s.workspace()["dataset_version"] == r["dataset_version"]
p = s.preview(ResearchCriteria(**r["criteria"]))
assert p["matching_ids"] == r["expected_matching_ids"]
d = r["expected_distance"]
assert s.distance(*d["variant_ids"]) == d
assert s.distance(*r["expected_unmapped_refusal"]["variant_ids"])["distance"] is None
h = cases["pten-heldout-v1"]
c = h["criteria"]
visible = {v["id"] for v in s.workspace()["variants"]}
import duckdb

with duckdb.connect() as db:
    measured = db.execute(
        "SELECT id,activity,abundance FROM read_parquet(?) WHERE id IN (SELECT unnest(?))",
        [
            str(s.assets.resolve(s.workspace()["parquet"]["key"])),
            [r["id"] for r in h["rows"]],
        ],
    ).fetchall()
    selected = {
        r[0]
        for r in db.execute(
            "SELECT id FROM read_parquet(?) WHERE id IN (SELECT unnest(?)) AND activity <= ? AND abundance >= ?",
            [
                str(s.assets.resolve(s.workspace()["parquet"]["key"])),
                [r["id"] for r in h["rows"]],
                c["activity_cutoff"],
                c["abundance_cutoff"],
            ],
        ).fetchall()
    }
    observed = {i: (a, b) for i, a, b in measured}
for row in h["rows"]:
    assert row["id"] not in visible
    assert observed[row["id"]] == (row["activity"], row["abundance"])
    assert (row["id"] in selected) == row["expected_match"]
result = {
    "deterministic_reference": "passed",
    "heldout_rows": len(h["rows"]),
    "heldout_numeric_contract": "passed",
    "model_reference_case": "not_passed; full frozen case still requires live evaluation",
    "independent_researcher_review": "pending",
    "clinical_validation": False,
}
print(json.dumps(result, indent=2))
(ROOT / "artifacts/RESEARCH_EVALUATION.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
