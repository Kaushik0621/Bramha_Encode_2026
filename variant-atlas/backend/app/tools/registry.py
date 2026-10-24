"""Bounded read/calculation registry. No arbitrary query, path, URL or executable input."""
import math
import httpx
from pymongo.errors import PyMongoError
from ..retrieval.hybrid import RetrievalUnavailable
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from ..research_schemas import (
    ResearchCriteria,
    Finding,
    NumericClaim,
    ToolResult,
    SpawnRequest,
)


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant_id: str | None = None
    variant_ids: list[str] | None = Field(default=None, max_length=200)
    other_variant_id: str | None = None
    assay_id: Literal["activity", "abundance"] | None = None
    source_id: str | None = None
    passage_id: str | None = None
    query: str = Field(default="", max_length=1200)
    radius: float = Field(default=10, gt=0, le=100, allow_inf_nan=False)
    criteria: ResearchCriteria | None = None
    alternative_criteria: ResearchCriteria | None = None
    findings: list[Finding] = Field(default_factory=list, max_length=20)
    numeric_claims: list[NumericClaim] = Field(default_factory=list, max_length=20)
    layer: Literal["activity", "abundance"] = "activity"


NAMES = [
    "discover_tools",
    "fetch_source_snapshot",
    "inspect_table_schema",
    "resolve_reference_sequence",
    "validate_variant_identity",
    "inspect_assay",
    "check_score_direction",
    "assess_comparability",
    "join_measurements",
    "filter_measurements",
    "summarize_measurement_coverage",
    "compare_measurement_patterns",
    "load_structure_metadata",
    "align_structure_reference",
    "map_variant_residues",
    "calculate_residue_distances",
    "find_spatial_neighbors",
    "retrieve_functional_annotations",
    "search_methods_text",
    "retrieve_passage",
    "validate_evidence_references",
    "validate_numeric_claims",
    "compare_analysis_scenarios",
    "update_scene_selection",
    "validate_shortlist",
    "inspect_run_budget",
    "export_reproducibility_package",
    "save_research_brief",
    "spawn_specialist",
    "request_reconciliation",
]

TOOL_HELP = {
    "discover_tools": "query: search the real tool catalog by scientific purpose or name. Only permitted capabilities returned; no execution or invented tools.",
    "fetch_source_snapshot": "source_id optional; read and checksum pinned source assets only.",
    "inspect_table_schema": "No arguments; report fixed Parquet column types and audited missingness.",
    "resolve_reference_sequence": "No arguments; return canonical P60484 sequence/version.",
    "validate_variant_identity": "variant_ids optional; return accepted_count and validated identities.",
    "inspect_assay": "assay_id activity or abundance; report endpoint, model system, scale, controls and limitations.",
    "check_score_direction": "assay_id; report supported higher/lower interpretation.",
    "assess_comparability": "No arguments; report shared identity and descriptive-only cross-assay limitations.",
    "join_measurements": "variant_ids optional; return original-scale measurements and reported SE.",
    "filter_measurements": "criteria optional (defaults to declared request), variant_ids optional; return matching_count, mapped_count, unmapped_count and exact selection reasons.",
    "summarize_measurement_coverage": "variant_ids optional; return both_measured count, total, values and missingness.",
    "compare_measurement_patterns": "criteria and variant_ids optional; descriptive patterns only.",
    "load_structure_metadata": "No arguments; report experimental construct, resolution and coverage.",
    "align_structure_reference": "No arguments; return audited alignment and ambiguity, never fabricate coordinates.",
    "map_variant_residues": "variant_ids optional; return mappings, mapped_count, missing_coordinates_count and outside_coverage_count.",
    "calculate_residue_distances": "variant_id and other_variant_id required; accepted experimental C-alpha positions only, angstroms.",
    "find_spatial_neighbors": "variant_id required, radius in angstroms; reference geometry only.",
    "retrieve_functional_annotations": "No arguments; source-linked UniProt regions.",
    "search_methods_text": "query and optional assay_id; permitted methods passages, retrieval method explicit.",
    "retrieve_passage": "passage_id required; exact permitted text and source location.",
    "validate_evidence_references": "findings array required for draft checks; each finding has id, claim_type, text, variant_ids, evidence_refs and limitations. Not artifact_ids. Checks existence/identity, not scientific truth.",
    "validate_numeric_claims": 'numeric_claims array: [{artifact_id: exact ID, path: ["data","matching_count"], value: actual number, units: null}]. Tool result artifacts have an inner data object. Do not pass artifact_ids alone.',
    "compare_analysis_scenarios": "criteria and alternative_criteria required; compare explicit selections.",
    "update_scene_selection": "variant_ids and layer activity/abundance; validated command only.",
    "validate_shortlist": "variant_ids and criteria; enforce actual matching rules and declared capacity.",
    "inspect_run_budget": "No arguments; actual counters and limits.",
    "export_reproducibility_package": "No arguments; source manifest, declared settings and saved findings.",
    "save_research_brief": "findings and numeric_claims; durable finalization gate, equivalent to finalize action.",
    "spawn_specialist": "SpawnRequest fields role, question, input_artifact_ids, allowed_tools, max_steps, max_seconds. Every action including finalization consumes one step.",
    "request_reconciliation": "SpawnRequest with role reconciliation; input_artifact_ids from both branches. Scope comparison, preserve unresolved disagreement.",
}


class Registry:
    def __init__(self, data):
        self.data = data

    def contracts(self):
        return [
            {
                "name": n,
                "purpose": TOOL_HELP[n],
                "input_schema": SpawnRequest.model_json_schema()
                if n in ["spawn_specialist", "request_reconciliation"]
                else Arguments.model_json_schema(),
                "output_schema": ToolResult.model_json_schema(),
                "scope": "Pinned human PTEN P60484 workspace subset only",
                "cost": "local deterministic read/calculation",
                "preconditions": [
                    "Audited immutable data acquired",
                    "Run workspace and dataset versions agree",
                ],
                "verification": "Typed arguments; accepted identities and coordinates; explicit missing-data outcomes",
            }
            for n in NAMES
        ]

    def execute(self, name, raw, run):
        if name not in NAMES:
            return ToolResult(
                tool=name,
                outcome="unsupported",
                summary="Tool is unavailable to this planner.",
            )
        try:
            a = Arguments.model_validate(raw)
            w = self.data.workspace()
            if w["dataset_version"] != run["dataset_version"]:
                raise ValueError(
                    "Workspace version changed; start a new pinned investigation."
                )
            ids = (
                a.variant_ids
                if a.variant_ids is not None
                else run["request"]["selected_ids"]
            )
            rows = [self.data.variant(x) for x in ids]
            criteria = a.criteria or ResearchCriteria.model_validate(
                run["request"]["criteria"]
            )
            assay = next(
                (x for x in w["assays"] if x["id"] == (a.assay_id or "activity")), None
            )
            if name == "discover_tools":
                terms = a.query.lower().split()
                permitted = set(run.get("_allowed_tools", NAMES))
                result = {
                    "tools": [
                        c
                        for c in self.contracts()
                        if c["name"] in permitted
                        and (
                            not terms
                            or any(
                                t in (c["name"] + " " + c["purpose"]).lower()
                                for t in terms
                            )
                        )
                    ],
                    "catalog_size": len(permitted),
                    "query": a.query,
                }
            elif name == "fetch_source_snapshot":
                sources = [
                    s for s in w["sources"] if not a.source_id or s["id"] == a.source_id
                ]
                if not sources:
                    raise ValueError("Unknown pinned source.")
                for s in sources:
                    if "asset" in s:
                        self.data.assets.read(s["asset"])
                result = {"sources": sources}
            elif name == "inspect_table_schema":
                import duckdb

                with duckdb.connect() as db:
                    result = {
                        "columns": db.execute(
                            "DESCRIBE SELECT * FROM read_parquet(?)",
                            [str(self.data.assets.resolve(w["parquet"]["key"]))],
                        ).fetchall(),
                        "scope": "Full derived substitution union",
                        "coverage": self.data.audit()["coverage"],
                    }
            elif name == "resolve_reference_sequence":
                result = w["protein"]
            elif name == "validate_variant_identity":
                result = {
                    "accepted_count": len(rows),
                    "identities": [
                        {
                            k: v[k]
                            for k in [
                                "id",
                                "position",
                                "ref",
                                "alt",
                                "protein_hgvs",
                                "reference_sequence_version",
                            ]
                        }
                        for v in rows
                    ],
                    "dna_ambiguity": "Protein substitutions do not uniquely identify DNA alleles.",
                }
            elif name in ["inspect_assay", "check_score_direction"]:
                result = assay
            elif name == "assess_comparability":
                result = w["comparability"]
            elif name in ["join_measurements", "summarize_measurement_coverage"]:
                result = {
                    "rows": [
                        {
                            k: v[k]
                            for k in [
                                "id",
                                "activity",
                                "abundance",
                                "activity_record",
                                "abundance_record",
                                "activity_se",
                                "abundance_se",
                            ]
                        }
                        for v in rows
                    ],
                    "both_measured": sum(
                        v["activity"] is not None and v["abundance"] is not None
                        for v in rows
                    ),
                    "total": len(rows),
                    "missing_policy": "null remains unknown",
                }
            elif name in ["filter_measurements", "compare_measurement_patterns"]:
                result = self.data.preview(criteria, ids)
            elif name == "load_structure_metadata":
                result = w["structure"]
            elif name == "align_structure_reference":
                result = self.data.audit()["mapping"]
            elif name == "map_variant_residues":
                result = {
                    "mappings": [dict(v["mapping"], variant_id=v["id"]) for v in rows],
                    "mapped_count": sum(
                        v["mapping"]["status"] == "mapped" for v in rows
                    ),
                    "missing_coordinates_count": sum(
                        v["mapping"]["status"] == "missing_coordinates" for v in rows
                    ),
                    "outside_coverage_count": sum(
                        v["mapping"]["status"] == "outside_structure_coverage"
                        for v in rows
                    ),
                }
            elif name == "calculate_residue_distances":
                result = self.data.distance(a.variant_id, a.other_variant_id)
            elif name == "find_spatial_neighbors":
                result = self.data.neighbors(a.variant_id, a.radius)
            elif name == "retrieve_functional_annotations":
                result = {
                    "annotations": w["functional_annotations"],
                    "source_id": "uniprot-P60484",
                }
            elif name == "search_methods_text":
                result = (
                    self.data.retrieval.search(w, a.query, a.assay_id)
                    if self.data.retrieval
                    else self.data.lexical_search(a.query, a.assay_id)
                )
            elif name == "retrieve_passage":
                passage = next(
                    (p for p in w["evidence"] if p["id"] == a.passage_id), None
                )
                if passage is None:
                    raise ValueError("Unknown permitted passage ID.")
                result = passage
            elif name == "validate_evidence_references":
                result = self.check_references(a.findings, run, w)
            elif name == "validate_numeric_claims":
                result = self.check_numbers(a.numeric_claims, run)
            elif name == "compare_analysis_scenarios":
                if not a.alternative_criteria:
                    raise ValueError("Explicit alternative criteria are required.")
                first = self.data.preview(criteria, ids)
                second = self.data.preview(a.alternative_criteria, ids)
                result = {
                    "baseline": first,
                    "alternative": second,
                    "added": sorted(
                        set(second["matching_ids"]) - set(first["matching_ids"])
                    ),
                    "removed": sorted(
                        set(first["matching_ids"]) - set(second["matching_ids"])
                    ),
                }
            elif name == "update_scene_selection":
                result = {
                    "variant_ids": ids,
                    "residue_ids": sorted(
                        {
                            v["mapping"]["mapping_id"]
                            for v in rows
                            if v["mapping"]["status"] == "mapped"
                        }
                    ),
                    "layer": a.layer,
                    "dataset_version": w["dataset_version"],
                    "command_only": True,
                }
            elif name == "validate_shortlist":
                preview = self.data.preview(criteria, ids)
                result = {
                    "eligible": all(r["matches"] for r in preview["results"]),
                    "within_capacity": len(ids) <= run["request"]["capacity"],
                    "count": len(ids),
                    "capacity": run["request"]["capacity"],
                    "audit": preview,
                }
            elif name == "inspect_run_budget":
                result = run["budget"]
            elif name == "export_reproducibility_package":
                result = {
                    "run_id": run["run_id"],
                    "dataset_version": run["dataset_version"],
                    "source_manifest": w["sources"],
                    "declared_request": run["request"],
                    "findings": run["findings"],
                    "analysis_artifact_ids": [a["id"] for a in run["artifacts"]],
                    "review_status": "pending unless separately recorded",
                }
            elif name in [
                "save_research_brief",
                "spawn_specialist",
                "request_reconciliation",
            ]:
                return ToolResult(
                    tool=name,
                    outcome="unsupported",
                    summary="This capability is executed only by the durable orchestration action boundary, not a direct data-tool invocation.",
                )
            else:
                raise ValueError("Unavailable implementation.")
            outcome = (
                "mapping_failed" if result.get("status") == "mapping_failed" else "ok"
            )
            return ToolResult(
                tool=name,
                outcome=outcome,
                summary=f"{name}: {outcome}",
                data=result,
                source_ids=[s["id"] for s in w["sources"]],
                limitations=[
                    "Research use; observational measurements do not establish causality or clinical pathogenicity."
                ],
            )
        except (RetrievalUnavailable, httpx.HTTPError, PyMongoError, OSError):
            return ToolResult(
                tool=name,
                outcome="source_unavailable",
                summary="The configured scientific source or retrieval service is unavailable; no fallback was used.",
                limitations=[
                    "Use another available pinned evidence tool or explicitly abstain."
                ],
            )
        except (ValueError, KeyError, TypeError) as exc:
            return ToolResult(
                tool=name, outcome="invalid_input", summary=str(exc)[:500]
            )

    @staticmethod
    def check_references(findings, run, w):
        valid = (
            {s["id"] for s in w["sources"]}
            | {p["id"] for p in w["evidence"]}
            | {a["id"] for a in run["artifacts"]}
        )
        valid |= {
            p["id"] + "#" + c["id"]
            for p in run.get("paper_sources", [])
            for c in p["chunks"][:6]
        }
        variants = {v["id"] for v in w["variants"]}
        checks = [
            {
                "finding_id": f.id,
                "references_exist": bool(f.evidence_refs)
                and set(f.evidence_refs) <= valid,
                "identities_valid": set(f.variant_ids) <= variants,
                "support_assessment": "Existence only; applicability and scientific truth require review.",
            }
            for f in findings
        ]
        return {
            "passed": all(
                c["references_exist"] and c["identities_valid"] for c in checks
            ),
            "checks": checks,
            "scientific_truth_established": False,
        }

    @staticmethod
    def numeric_candidates(run, values):
        candidates = []

        def visit(value, path, artifact_id):
            if len(path) > 10 or len(candidates) >= 40:
                return
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and any(
                    math.isclose(value, x, rel_tol=1e-8, abs_tol=1e-8) for x in values
                )
            ):
                candidates.append(
                    {
                        "artifact_id": artifact_id,
                        "path": path,
                        "value": value,
                        "units": Registry.read_numeric(
                            next(a for a in run["artifacts"] if a["id"] == artifact_id)[
                                "data"
                            ],
                            path,
                        )[1],
                    }
                )
            elif isinstance(value, dict):
                for key, v in value.items():
                    visit(v, path + [str(key)], artifact_id)
            elif isinstance(value, list):
                for index, v in enumerate(value[:200]):
                    visit(v, path + [str(index)], artifact_id)

        for artifact in run["artifacts"]:
            if (
                artifact["kind"]
                in [
                    "filter_measurements",
                    "map_variant_residues",
                    "validate_variant_identity",
                    "calculate_residue_distances",
                    "find_spatial_neighbors",
                ]
                and artifact["data"].get("outcome") == "ok"
            ):
                visit(artifact["data"], [], artifact["id"])
        return candidates

    @staticmethod
    def read_numeric(artifact_data, path):
        value = artifact_data
        units = None
        for key in path:
            if isinstance(value, dict) and "units" in value:
                units = value["units"]
            value = value[int(key)] if isinstance(value, list) else value[key]
        field = path[-1]
        dimensional = field in {
            "distance",
            "radius",
            "x",
            "y",
            "z",
            "activity",
            "abundance",
            "activity_se",
            "abundance_se",
        }
        if isinstance(units, dict):
            units = units.get(field.removesuffix("_se"))
        return value, units if dimensional else None

    @staticmethod
    def check_numbers(claims, run):
        checks = []
        for claim in claims:
            expected_units = None
            try:
                artifact = next(
                    a for a in run["artifacts"] if a["id"] == claim.artifact_id
                )
                value, expected_units = Registry.read_numeric(
                    artifact["data"], claim.path
                )
                numeric_passed = (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isclose(value, claim.value, rel_tol=1e-8, abs_tol=1e-8)
                )
                units_passed = (
                    claim.units == expected_units
                    if expected_units
                    else claim.units in (None, "count", "dimensionless")
                )
                passed = numeric_passed and units_passed
            except (KeyError, StopIteration, ValueError, IndexError, TypeError):
                value = None
                passed = False
                units_passed = False
            checks.append(
                {
                    "claim": claim.model_dump(),
                    "actual": value,
                    "expected_units": expected_units,
                    "units_matched": units_passed,
                    "passed": passed,
                }
            )
        return {"passed": all(c["passed"] for c in checks), "checks": checks}
