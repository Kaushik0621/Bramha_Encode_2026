import re
from Bio.Seq import Seq
from Bio.Align import PairwiseAligner
from Bio.Data.IUPACData import protein_letters_3to1
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from io import StringIO

AA = {**protein_letters_3to1, **{x: x for x in "ACDEFGHIKLMNPQRSTVWY"}}


def substitution(hgvs: str, reference: str) -> dict:
    match = re.fullmatch(
        r"p\.([A-Z][a-z]{2}|[A-Z])(\d+)([A-Z][a-z]{2}|[A-Z])", hgvs or ""
    )
    if not match:
        return {
            "status": "rejected",
            "reason": "Not a supported single missense substitution.",
        }
    ref, pos, alt = match.groups()
    pos = int(pos)
    ref = AA.get(ref)
    alt = AA.get(alt)
    if not ref or not alt or ref == alt:
        return {
            "status": "rejected",
            "reason": "Not a supported missense amino-acid change.",
        }
    if pos < 1 or pos > len(reference):
        return {
            "status": "rejected",
            "reason": "Position outside the pinned protein reference.",
        }
    if reference[pos - 1] != ref:
        return {
            "status": "rejected",
            "reason": "Reference amino acid mismatch.",
            "position": pos,
            "expected": reference[pos - 1],
            "observed": ref,
        }
    return {
        "status": "accepted",
        "position": pos,
        "ref": ref,
        "alt": alt,
        "protein_hgvs": f"p.{ref}{pos}{alt}",
        "representation_level": "protein_substitution",
        "dna_allele_status": "not_uniquely_inferred",
        "organism_taxonomy_id": 9606,
        "reference_accession": "P60484",
    }


def audit_target(metadata: dict, reference: str) -> dict:
    genes = metadata.get("targetGenes", [])
    targets = []
    for gene in genes:
        target = gene.get("targetSequence", {})
        raw = target.get("sequence", "")
        sequence = (
            str(Seq(raw).translate()).rstrip("*")
            if target.get("sequenceType") == "dna"
            else raw
        )
        organism = target.get("taxonomy", {}).get("code")
        identifiers = [
            x.get("identifier", {}).get("identifier")
            for x in gene.get("externalIdentifiers", [])
        ]
        status = (
            "accepted"
            if sequence == reference and organism == 9606 and "P60484" in identifiers
            else "unresolved"
        )
        targets.append(
            {
                "name": gene.get("name"),
                "organism_taxonomy_id": organism,
                "representation_level": target.get("sequenceType"),
                "translated_length": len(sequence),
                "reference_match": sequence == reference,
                "status": status,
                "reason": "Exact translated target/reference identity."
                if status == "accepted"
                else "Target identity, species or reference accession not established.",
            }
        )
    return {
        "status": "accepted"
        if len(targets) == 1 and targets[0]["status"] == "accepted"
        else "unresolved",
        "targets": targets,
    }


def structure_mapping(cif_text: str, reference: str) -> dict:
    cif = MMCIF2Dict(StringIO(cif_text))
    aa3 = {k.upper(): v for k, v in protein_letters_3to1.items()}
    rows = []

    def column(key, default="?"):
        return cif.get(
            "_pdbx_poly_seq_scheme." + key,
            [default] * len(cif["_pdbx_poly_seq_scheme.seq_id"]),
        )

    for i, chain in enumerate(column("asym_id")):
        if chain != "A":
            continue
        rows.append(
            {
                "label_seq_id": int(column("seq_id")[i]),
                "amino_acid": aa3.get(column("mon_id")[i], "X"),
                "auth_seq_id": column("pdb_seq_num")[i],
                "insertion_code": column("pdb_ins_code")[i],
                "chain_id": column("pdb_strand_id")[i],
                "label_asym_id": chain,
            }
        )
    target = "".join(r["amino_acid"] for r in rows)
    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.match_score = 3
    aligner.mismatch_score = -4
    aligner.open_gap_score = -8
    aligner.extend_gap_score = -0.5
    aligner.end_insertion_score = 0
    aligner.end_deletion_score = 0
    alignments = aligner.align(reference, target)
    first = alignments[0]
    ambiguous = len(alignments) > 1 and alignments[1].score == first.score
    lookup = {}
    for (ra, rb), (ta, tb) in zip(*first.aligned):
        for r, t in zip(range(ra, rb), range(ta, tb)):
            if reference[r] == target[t]:
                lookup[t + 1] = r + 1
    # Independently cross-check the exact alignment against depositor UniProt segments.
    depositor = {}
    refs = cif.get("_struct_ref_seq.pdbx_db_accession", [])
    for i, accession in enumerate(refs):
        if accession != "P60484":
            continue
        a = int(cif["_struct_ref_seq.seq_align_beg"][i])
        b = int(cif["_struct_ref_seq.seq_align_end"][i])
        r = int(cif["_struct_ref_seq.db_align_beg"][i])
        for label in range(a, b + 1):
            depositor[label] = r + label - a
    coords = {}
    for i, atom in enumerate(cif.get("_atom_site.label_atom_id", [])):
        if atom != "CA" or cif["_atom_site.label_asym_id"][i] != "A":
            continue
        if (
            cif.get(
                "_atom_site.pdbx_PDB_model_num",
                ["1"] * len(cif["_atom_site.label_atom_id"]),
            )[i]
            != "1"
        ):
            continue
        label = cif["_atom_site.label_seq_id"][i]
        if label in (".", "?"):
            continue
        alt = cif["_atom_site.label_alt_id"][i]
        if alt not in (".", "A", "?"):
            continue
        coords[int(label)] = {
            "x": float(cif["_atom_site.Cartn_x"][i]),
            "y": float(cif["_atom_site.Cartn_y"][i]),
            "z": float(cif["_atom_site.Cartn_z"][i]),
        }
    mappings = []
    mapped_positions = set()
    for row in rows:
        label = row["label_seq_id"]
        pos = lookup.get(label)
        agree = pos is not None and depositor.get(label) == pos
        if not agree:
            status = "unresolved"
            reason = (
                "Ambiguous alignment or disagreement with depositor UniProt mapping."
            )
        elif label not in coords:
            status = "missing_coordinates"
            reason = "Aligned residue has no experimental C-alpha coordinate."
        else:
            status = "mapped"
            reason = "Exact aligned identity agrees with depositor UniProt anchors; experimental C-alpha exists."
        if pos:
            mapped_positions.add(pos)
        mappings.append(
            dict(
                row,
                reference_position=pos,
                status=status,
                reason=reason,
                coordinate=coords.get(label) if status == "mapped" else None,
                mapping_id=f'P60484:1D5R:A:{pos or "unresolved"}:{label}',
                units="angstrom",
                coordinate_type="experimental",
            )
        )
    for pos in range(1, len(reference) + 1):
        if pos not in mapped_positions:
            mappings.append(
                {
                    "reference_position": pos,
                    "status": "outside_structure_coverage",
                    "reason": "No accepted construct-to-reference alignment at this position.",
                    "coordinate": None,
                    "mapping_id": f"P60484:1D5R:A:{pos}:unavailable",
                    "units": "angstrom",
                    "coordinate_type": "experimental",
                    "chain_id": "A",
                    "label_asym_id": "A",
                    "label_seq_id": None,
                    "auth_seq_id": None,
                    "insertion_code": None,
                    "amino_acid": reference[pos - 1],
                }
            )
    return {
        "structure_id": "1D5R",
        "chain_id": "A",
        "reference_accession": "P60484",
        "reference_length": len(reference),
        "construct_length": len(target),
        "alignment_score": first.score,
        "alignment_ambiguous": ambiguous,
        "alignment_text": str(first),
        "depositor_cross_check": True,
        "mappings": sorted(
            mappings,
            key=lambda m: (m["reference_position"] or 9999, m["label_seq_id"] or 0),
        ),
        "method": cif.get("_exptl.method", ["Unknown"])[0],
        "resolution_angstrom": float(cif.get("_refine.ls_d_res_high", ["nan"])[0]),
        "source_type": "experimental",
        "coordinate_metric": "C-alpha Euclidean distance",
        "units": "angstrom",
        "limitations": [
            "Reference structure, not a mutant conformation.",
            "Unresolved residues and deleted construct segments are not interpolated.",
        ],
    }
