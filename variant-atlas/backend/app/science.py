"""Real PTEN source snapshots and deterministic scientific calculations."""
import json
import math
from pathlib import Path
import duckdb
from .config import ROOT
from .ingestion.assets import AssetStore
from .research_schemas import ResearchCriteria


class ScientificData:
    def __init__(self, asset_root: Path | None = None, store=None):
        self.store = store
        self.retrieval = None
        self.directory = ROOT / "data/manifests"
        self.assets = AssetStore(asset_root or ROOT / "data/assets")

    def workspace(self):
        path = self.directory / "pten-workspace.json"
        if not path.exists():
            raise FileNotFoundError(
                "Real PTEN data is not acquired. Run scripts/acquire_pten.py; no fixture fallback is used."
            )
        w = self.store.workspace() if self.store else json.loads(path.read_text())
        self.assets.read(w["parquet"])
        self.assets.read(w["structure_asset"])
        return w

    def audit(self):
        return {
            name: json.loads((self.directory / f"pten-{file}.json").read_text())
            for name, file in [
                ("coverage", "coverage-report"),
                ("mapping", "mapping-audit"),
                ("assays", "assay-dictionary"),
                ("sources", "source-manifest"),
            ]
        }

    def variant(self, vid):
        w = self.workspace()
        row = next((r for r in w["variants"] if r["id"] == vid), None)
        if row is None:
            raise KeyError("Variant is not in the audited workspace subset.")
        return row

    def preview(self, criteria: ResearchCriteria, variant_ids: list[str] | None = None):
        w = self.workspace()
        allowed = {v["id"] for v in w["variants"]}
        ids = allowed if variant_ids is None else set(variant_ids)
        if not ids <= allowed:
            raise ValueError("Unknown or out-of-workspace substitution identifier.")
        path = self.assets.resolve(w["parquet"]["key"])
        op = (
            ">=" if criteria.scenario == "preserved_abundance_reduced_activity" else "<"
        )
        # Only a fixed comparison operator is interpolated. No SQL is model supplied.
        with duckdb.connect() as conn:
            rows = conn.execute(
                f"SELECT id,activity,abundance FROM read_parquet(?) WHERE activity <= ? AND abundance {op} ?",
                [str(path), criteria.activity_cutoff, criteria.abundance_cutoff],
            ).fetchall()
        eligible = {r[0] for r in rows} & ids
        results = []
        for v in w["variants"]:
            if v["id"] not in ids:
                continue
            reasons = []
            if v["activity"] is None or v["abundance"] is None:
                reasons.append("Missing assay measurement; not coerced to zero.")
            elif v["id"] not in eligible:
                reasons.append(
                    "Does not meet the declared assay-specific exploratory criteria."
                )
            if criteria.mapping == "mapped" and v["mapping"]["status"] != "mapped":
                reasons.append("No accepted experimental coordinate mapping.")
            if criteria.mapping == "unmapped" and v["mapping"]["status"] == "mapped":
                reasons.append("Excluded by unmapped-only criterion.")
            results.append(
                {
                    "variant_id": v["id"],
                    "matches": not reasons,
                    "reasons": reasons
                    or ["Matches the explicit descriptive criteria."],
                    "activity": v["activity"],
                    "abundance": v["abundance"],
                    "mapping_status": v["mapping"]["status"],
                }
            )
        matches = [r["variant_id"] for r in results if r["matches"]]
        return {
            "criteria": criteria.model_dump(),
            "matching_ids": matches,
            "matching_count": len(matches),
            "results": results,
            "selected_scope_count": len(ids),
            "mapped_count": sum(
                r["matches"] and r["mapping_status"] == "mapped" for r in results
            ),
            "unmapped_count": sum(
                r["matches"] and r["mapping_status"] != "mapped" for r in results
            ),
            "units": {
                "activity": w["assays"][0]["scale"],
                "abundance": w["assays"][1]["scale"],
            },
            "dataset_version": w["dataset_version"],
            "limitations": w["comparability"]["limitations"],
        }

    def neighbors(self, vid, radius=10):
        w = self.workspace()
        v = self.variant(vid)
        mapping = v["mapping"]
        if mapping["status"] != "mapped":
            return {
                "status": "mapping_failed",
                "variant_id": vid,
                "mapping_status": mapping["status"],
                "neighbors": [],
                "reason": mapping["reason"],
                "units": "angstrom",
                "metric": "C-alpha Euclidean",
            }
        p = mapping["coordinate"]
        out = []
        for row in w["variants"]:
            if row["id"] == vid or row["mapping"]["status"] != "mapped":
                continue
            q = row["mapping"]["coordinate"]
            distance = math.dist([p["x"], p["y"], p["z"]], [q["x"], q["y"], q["z"]])
            if distance <= radius:
                out.append(
                    {
                        "variant_id": row["id"],
                        "position": row["position"],
                        "distance": round(distance, 6),
                        "same_residue": row["position"] == v["position"],
                    }
                )
        return {
            "status": "available",
            "variant_id": vid,
            "neighbors": sorted(out, key=lambda r: (r["distance"], r["variant_id"]))[
                :100
            ],
            "radius": radius,
            "units": "angstrom",
            "metric": "C-alpha Euclidean",
            "mapping_version": w["dataset_version"],
            "limitations": [
                "Reference structure, not mutant geometry.",
                "Other substitutions at the same residue share the same reference coordinate.",
            ],
        }

    def distance(self, a, b):
        first, second = self.variant(a), self.variant(b)
        if any(v["mapping"]["status"] != "mapped" for v in [first, second]):
            return {
                "status": "mapping_failed",
                "variant_ids": [a, b],
                "reason": "Both accepted experimental C-alpha mappings are required.",
                "distance": None,
                "units": "angstrom",
            }
        p, q = [v["mapping"]["coordinate"] for v in [first, second]]
        return {
            "status": "available",
            "variant_ids": [a, b],
            "distance": round(
                math.dist(
                    [p[k] for k in ["x", "y", "z"]], [q[k] for k in ["x", "y", "z"]]
                ),
                6,
            ),
            "units": "angstrom",
            "metric": "C-alpha Euclidean",
            "same_residue": first["position"] == second["position"],
        }

    def lexical_search(self, query, assay_id=None, limit=5):
        import re

        w = self.workspace()
        words = set(re.findall(r"[a-z]{3,}", query.lower()))
        candidates = [
            p for p in w["evidence"] if not assay_id or p["assay_id"] == assay_id
        ]
        ranked = sorted(
            candidates,
            key=lambda p: (-sum(x in p["text"].lower() for x in words), p["id"]),
        )
        return {
            "method": "local_lexical",
            "query": query,
            "filters": {
                "assay_id": assay_id,
                "workspace_id": w["id"],
                "dataset_version": w["dataset_version"],
            },
            "passages": ranked[:limit],
            "limitations": [
                "Lexical retrieval, not Atlas hybrid search. Relevance does not establish scientific support."
            ],
        }
