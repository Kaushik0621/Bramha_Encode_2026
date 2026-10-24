"""Freeze numerical expectations before model evaluation. Refuses overwriting a frozen case."""
import hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import ROOT
from app.science import ScientificData
from app.research_schemas import ResearchCriteria

s = ScientificData()
w = s.workspace()
root = ROOT / "data/reference_cases"
root.mkdir(parents=True, exist_ok=True)
criteria = ResearchCriteria(
    **{k: v for k, v in w["defaults"].items() if k in ResearchCriteria.model_fields}
)
mapped = [v for v in w["variants"] if v["mapping"]["status"] == "mapped"]
unmapped = next(v for v in w["variants"] if v["mapping"]["status"] != "mapped")
a = next((v for v in mapped if v["id"] == "PTEN:p.C124S"), mapped[0])
b = next((v for v in mapped if v["id"] == "PTEN:p.R130Q"), mapped[-1])
case = {
    "id": "pten-reference-v1",
    "dataset_version": w["dataset_version"],
    "frozen_before_model_evaluation": True,
    "scope": "Reproducible 131-substitution workspace; not a clinical validation set.",
    "question": "Compare reduced activity with preserved abundance, detect assay-context and mapping limits, revise spatial scope, and retain unresolved hypotheses.",
    "criteria": criteria.model_dump(),
    "selected_ids": [v["id"] for v in w["variants"]],
    "expected_matching_ids": s.preview(criteria)["matching_ids"],
    "expected_distance": s.distance(a["id"], b["id"]),
    "expected_unmapped_refusal": s.distance(unmapped["id"], a["id"]),
    "rubric": {
        "identity": "P60484 canonical sequence version 1, taxon 9606; protein-only allele ambiguity explicit",
        "assays": "Yeast activity and VAMP-seq abundance remain distinct scales; descriptive comparison only",
        "revision": "Observed assay or construct/coordinate limitation causes a recorded narrowing or abstention",
        "branches": "At least two genuinely model-invoked scoped workers with artifact handoffs",
        "verification": "All reported numbers linked to deterministic outputs; evidence applicability reviewed",
        "clinical": "No pathogenicity, cure or causal classification inferred",
    },
    "researcher_review": {
        "status": "pending",
        "reviewer": None,
        "notes": "A real independent researcher must provide review; no simulated endorsement.",
    },
}
p = root / "pten-reference-v1.json"
if p.exists():
    raise SystemExit(
        "Frozen case already exists; create a new version to change expectations."
    )
p.write_text(json.dumps(case, indent=2) + "\n")
(root / "pten-reference-v1.sha256").write_text(
    hashlib.sha256(p.read_bytes()).hexdigest() + "\n"
)
# Held-out native rows are excluded from the visible subset and from the model reference prompt.
import duckdb

with duckdb.connect() as db:
    rows = db.execute(
        "SELECT id,activity,abundance FROM read_parquet(?) ORDER BY id",
        [str(s.assets.resolve(w["parquet"]["key"]))],
    ).fetchall()
visible = {v["id"] for v in w["variants"]}
held = [
    {
        "id": i,
        "activity": a,
        "abundance": b,
        "expected_match": a is not None
        and b is not None
        and a <= criteria.activity_cutoff
        and b >= criteria.abundance_cutoff,
    }
    for i, a, b in rows
    if i not in visible
][::199][:32]
h = {
    "id": "pten-heldout-v1",
    "dataset_version": w["dataset_version"],
    "criteria": criteria.model_dump(),
    "rows": held,
    "scope": "Deterministic threshold generalization check; not an estimate of medical utility.",
}
p = root / "pten-heldout-v1.json"
p.write_text(json.dumps(h, indent=2) + "\n")
(root / "pten-heldout-v1.sha256").write_text(
    hashlib.sha256(p.read_bytes()).hexdigest() + "\n"
)
print("Frozen reference and held-out numerical contracts; scientific reviewer pending.")
