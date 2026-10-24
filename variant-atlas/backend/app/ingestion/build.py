import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from .identity import substitution, audit_target, structure_mapping
from .assets import AssetStore
from ..config import ROOT

VERSION = "pten-transform-1.0"


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def build_workspace(manifest: dict, asset_root: Path, subset_size=128):
    store = AssetStore(asset_root)
    sources = {s["id"]: s for s in manifest["sources"]}

    def raw(id):
        return store.read(sources[id]["asset"])

    def obj(id):
        return json.loads(raw(id))

    ref = obj("uniprot-P60484")
    sequence = ref["sequence"]["value"]
    metadata = {
        kind: obj(f"mavedb-{kind}-metadata") for kind in ["activity", "abundance"]
    }
    for kind in metadata:
        if sources[f"mavedb-{kind}-metadata"]["terms_status"] != "verified_dataset_CC0":
            raise ValueError(f"{kind}: dataset terms need review before integration.")
    target_audit = {
        kind: audit_target(meta, sequence) for kind, meta in metadata.items()
    }
    if any(a["status"] != "accepted" for a in target_audit.values()):
        raise ValueError("Assay targets did not pass species/reference identity audit.")
    mapping = structure_mapping(raw("pdb-1D5R").decode(), sequence)
    mapping_by_pos = {
        m["reference_position"]: m
        for m in mapping["mappings"]
        if m["reference_position"]
    }
    assays = []
    tables = {}
    audits = []
    all_measurements = []
    passages = []
    for kind, meta in metadata.items():
        source_id = f"mavedb-{kind}-metadata"
        score_id = f"mavedb-{kind}-scores"
        rows = list(csv.DictReader(io.StringIO(raw(score_id).decode())))
        table = {}
        duplicates = []
        for i, row in enumerate(rows):
            identity = substitution(row.get("hgvs_pro", ""), sequence)
            audit = {
                "source_id": score_id,
                "row": i + 2,
                "source_record_id": row.get("accession"),
                "submitted_hgvs": row.get("hgvs_pro"),
                **identity,
            }
            audits.append(audit)
            if identity["status"] != "accepted":
                continue
            key = identity["protein_hgvs"]
            if key in table:
                duplicates.append(key)
                continue
            measurement = {
                "variant_id": "PTEN:" + key,
                "assay_id": kind,
                "source_id": score_id,
                "source_record_id": row.get("accession"),
                "value": number(row.get("score")),
                "standard_error": number(row.get("SE" if kind == "activity" else "se")),
                "lower_ci": number(row.get("lower_ci")),
                "upper_ci": number(row.get("upper_ci")),
                "replicate_values": [
                    number(row[f"score{n}"])
                    for n in range(1, 16)
                    if f"score{n}" in row and number(row[f"score{n}"]) is not None
                ],
                "reported_confidence": row.get("High_conf")
                if kind == "activity"
                else None,
                "identity": identity,
                "submitted_dna_hgvs": row.get("hgvs_nt")
                if row.get("hgvs_nt") not in ("NA", "_wt", "", None)
                else None,
                "representation_level": "protein_substitution",
                "organism_taxonomy_id": 9606,
                "reference_accession": "P60484",
                "reference_sequence_version": ref["entryAudit"]["sequenceVersion"],
                "genome_build": None,
                "transcript": None,
                "synthetic": False,
            }
            table[key] = measurement
            all_measurements.append(measurement)
        if duplicates:
            raise ValueError(
                f"Ambiguous duplicate substitutions in {kind}: {duplicates[:3]}. No silent averaging is permitted."
            )
        tables[kind] = table
        for field in ["methodText"]:
            text = meta.get(field, "")
            size = 650
            for start in range(0, len(text), size):
                passages.append(
                    {
                        "id": f"passage-{kind}-{start}",
                        "source_id": source_id,
                        "source_version": sources[source_id]["release"],
                        "title": meta["title"],
                        "text": text[start : start + size],
                        "section": field,
                        "start_offset": start,
                        "end_offset": min(start + size, len(text)),
                        "workspace_id": "pten-real",
                        "gene": "PTEN",
                        "organism_taxonomy_id": 9606,
                        "assay_id": kind,
                        "url": f'https://mavedb.org/score-sets/{meta["urn"]}',
                        "license": "CC0",
                    }
                )
        system = (
            "humanized yeast model"
            if kind == "activity"
            else "VAMP-seq abundance measurements; composite of original/fill-in datasets"
        )
        original = (
            obj("mavedb-abundance-original-metadata") if kind == "abundance" else meta
        )
        assays.append(
            {
                "id": kind,
                "title": meta["title"],
                "urn": meta["urn"],
                "endpoint": "lipid phosphatase-associated yeast fitness"
                if kind == "activity"
                else "relative intracellular abundance",
                "system": system,
                "organism_of_target": "Homo sapiens",
                "target_taxonomy_id": 9606,
                "model_system_is_target_organism": False
                if kind == "activity"
                else None,
                "scale": "published enrichment/fitness score; original scale"
                if kind == "activity"
                else "published VAMP-seq abundance score; original scale (not clamped to 0–1)",
                "direction": "higher indicates more assay-associated activity"
                if kind == "activity"
                else "higher indicates greater relative abundance",
                "construct": "Translated target matches canonical P60484 sequence version "
                + str(ref["entryAudit"]["sequenceVersion"]),
                "controls": "Synonymous distribution: metadata describes wild-type-like interval [-1.11, 0.89]."
                if kind == "activity"
                else "Original method describes WT score 1 and average nonsense score 0; composite dataset averages available replicate scores.",
                "replicate_availability": "Biological A/B and technical subreplicate aggregate scores are supplied; not treated as independent raw observations."
                if kind == "activity"
                else "Up to 15 per-replicate scores with missingness; exchangeability is not established.",
                "uncertainty_availability": "Reported standard errors retained."
                if kind == "activity"
                else "Reported SE and confidence intervals retained.",
                "source_ids": [source_id, score_id]
                + (
                    ["mavedb-abundance-original-metadata"]
                    if kind == "abundance"
                    else []
                ),
                "limitations": [
                    "Scale and endpoint differ across assays; no shared normalization is performed.",
                    "Descriptive cross-assay patterns do not establish mechanism or disease effect.",
                ],
                "methods": meta.get("methodText"),
                "original_methods": original.get("methodText")
                if kind == "abundance"
                else None,
                "target_audit": target_audit[kind],
            }
        )
    # A derived exploratory abundance cutoff, computed from actual synonymous controls;
    # explicitly not the fabricated prototype cutoff nor an author-endorsed classifier.
    abundance_rows = list(
        csv.DictReader(io.StringIO(raw("mavedb-abundance-scores").decode()))
    )
    controls = []
    import re

    for row in abundance_rows:
        m = re.fullmatch(
            r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})", row.get("hgvs_pro", "")
        )
        if m and m[1] == m[3] and number(row["score"]) is not None:
            controls.append(number(row["score"]))
    if not controls:
        raise ValueError(
            "No usable synonymous abundance controls; no default cutoff is invented."
        )
    abundance_cutoff = float(np.quantile(controls, 0.05, method="linear"))
    keys = sorted(
        set(tables["activity"]) | set(tables["abundance"]),
        key=lambda k: (substitution(k, sequence)["position"], k),
    )
    joined = []
    for key in keys:
        a = tables["activity"].get(key)
        b = tables["abundance"].get(key)
        identity = (a or b)["identity"]
        pos = identity["position"]
        m = mapping_by_pos[pos]
        joined.append(
            {
                "id": "PTEN:" + key,
                **identity,
                "reference_sequence_version": ref["entryAudit"]["sequenceVersion"],
                "reference_entry_version": ref["entryAudit"]["entryVersion"],
                "activity": a["value"] if a else None,
                "abundance": b["value"] if b else None,
                "activity_se": a["standard_error"] if a else None,
                "abundance_se": b["standard_error"] if b else None,
                "activity_record": a["source_record_id"] if a else None,
                "abundance_record": b["source_record_id"] if b else None,
                "mapping": m,
                "synthetic": False,
                "evidence_ids": [
                    p["id"]
                    for p in passages
                    if (p["assay_id"] == "activity" and a)
                    or (p["assay_id"] == "abundance" and b)
                ],
            }
        )
    flat = [
        {k: v for k, v in row.items() if k not in ["mapping", "evidence_ids"]}
        for row in joined
    ]
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(flat), buffer, compression="zstd")
    parquet = store.put(buffer.getvalue(), "parquet")
    # Reproducible subset spanning the accepted table; named reference residues are
    # additional explicit research-demo curation, not an importance ranking.
    indices = np.linspace(0, len(joined) - 1, min(subset_size, len(joined)), dtype=int)
    selected = {joined[int(i)]["id"] for i in indices}
    selected |= {
        r["id"]
        for r in joined
        if r["protein_hgvs"] in ["p.C124S", "p.R130Q", "p.G129E", "p.C124A"]
    }
    subset = [r for r in joined if r["id"] in selected]
    source_hash = hashlib.sha256(
        json.dumps(
            [s["asset"]["sha256"] for s in manifest["sources"]], sort_keys=True
        ).encode()
    ).hexdigest()
    version = VERSION + "-" + source_hash[:12]
    workspace = {
        "id": "pten-real",
        "name": "Human PTEN · audited public data",
        "data_mode": "real",
        "dataset_version": version,
        "organism": "Homo sapiens",
        "taxonomy_id": 9606,
        "gene": "PTEN",
        "protein": {
            "id": "P60484",
            "sequence": sequence,
            "length": len(sequence),
            "sequence_version": ref["entryAudit"]["sequenceVersion"],
            "entry_version": ref["entryAudit"]["entryVersion"],
            "isoform": "canonical",
            "genome_build": None,
            "transcript": None,
        },
        "variants": subset,
        "assays": assays,
        "evidence": passages,
        "sources": manifest["sources"],
        "parquet": parquet,
        "structure": {
            k: v for k, v in mapping.items() if k not in ["mappings", "alignment_text"]
        },
        "structure_asset": sources["pdb-1D5R"]["asset"],
        "mappings": mapping["mappings"],
        "functional_annotations": [
            c
            for c in ref.get("features", [])
            if c.get("type")
            in ["Active site", "Binding site", "Domain", "Region", "Motif"]
        ],
        "defaults": {
            "scenario": "preserved_abundance_reduced_activity",
            "activity_cutoff": -1.11,
            "abundance_cutoff": abundance_cutoff,
            "activity_cutoff_basis": "Source methods lower synonymous interval boundary; exploratory selection, not a clinical threshold.",
            "abundance_cutoff_basis": f"Derived 5th percentile of {len(controls)} reported synonymous-control scores using numpy linear quantile. Exploratory, not author-endorsed classification.",
            "capacity": 10,
            "mapping": "all",
        },
        "comparability": {
            "status": "descriptive_only",
            "shared_reference": True,
            "endpoints_interchangeable": False,
            "normalization_supported": False,
            "limitations": [
                "Activity is a humanized-yeast fitness proxy; abundance is a separate VAMP-seq endpoint.",
                "Combining the two scores describes a pattern; it does not prove a causal mechanism.",
                "Replicate scores are not automatically exchangeable raw biological replicates.",
                "Protein-substitution measurements are not uniquely assigned DNA-allele measurements.",
            ],
        },
    }
    coverage = {
        "workspace_id": "pten-real",
        "dataset_version": version,
        "raw_rows": {
            k: len(
                list(csv.DictReader(io.StringIO(raw(f"mavedb-{k}-scores").decode())))
            )
            for k in metadata
        },
        "identity_status_counts": dict(Counter(a["status"] for a in audits)),
        "accepted_substitutions": {k: len(t) for k, t in tables.items()},
        "union_substitutions": len(joined),
        "intersection_substitutions": len(
            set(tables["activity"]) & set(tables["abundance"])
        ),
        "both_measurements_available": sum(
            r["activity"] is not None and r["abundance"] is not None for r in joined
        ),
        "mapping_counts_full": dict(Counter(r["mapping"]["status"] for r in joined)),
        "displayed_subset": len(subset),
        "subset_policy": "Evenly spaced accepted substitution IDs, plus explicitly named reference-case substitutions when present. No universal importance ranking.",
        "subset_requested_size": subset_size,
        "synonymous_abundance_controls": len(controls),
        "comparability": workspace["comparability"],
        "structure_construct_length": mapping["construct_length"],
        "mapping_statuses": dict(Counter(m["status"] for m in mapping["mappings"])),
        "alignment_ambiguous": mapping["alignment_ambiguous"],
        "alignment_policy": "Per-residue exact alignment must agree with depositor UniProt segments; unanchored/engineered residues are unresolved.",
    }
    out = ROOT / "data/manifests"
    out.mkdir(exist_ok=True, parents=True)
    for name, data in [
        ("pten-workspace.json", workspace),
        ("pten-coverage-report.json", coverage),
        ("pten-assay-dictionary.json", assays),
        (
            "pten-mapping-audit.json",
            {
                "dataset_version": version,
                "target_audits": target_audit,
                "structure": mapping,
            },
        ),
        ("pten-identity-audit.json", {"dataset_version": version, "rows": audits}),
    ]:
        (out / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    return workspace, coverage
