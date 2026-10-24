"""Pinned, allowlisted PTEN acquisition; no arbitrary model-controlled URLs."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx
from .assets import AssetStore
from ..config import ROOT

CATALOG = {
    "uniprot-P60484": {
        "url": "https://rest.uniprot.org/uniprotkb/P60484.json",
        "suffix": "json",
        "terms": "CC BY 4.0; UniProt database terms",
        "terms_url": "https://www.uniprot.org/help/license",
    },
    "pdb-1D5R": {
        "url": "https://files.rcsb.org/download/1D5R.cif",
        "suffix": "cif",
        "terms": "wwPDB data freely available under CC0",
        "terms_url": "https://www.wwpdb.org/about/usage-policies",
    },
    "pdb-1D5R-metadata": {
        "url": "https://data.rcsb.org/rest/v1/core/entry/1D5R",
        "suffix": "json",
        "terms": "RCSB PDB/wwPDB data policy",
        "terms_url": "https://www.rcsb.org/pages/policies",
    },
}
for role, urn in [
    ("activity", "urn:mavedb:00000054-a-1"),
    ("abundance", "urn:mavedb:00000102-0-1"),
    ("abundance-original", "urn:mavedb:00000013-a-1"),
]:
    CATALOG[f"mavedb-{role}-metadata"] = {
        "url": f"https://api.mavedb.org/api/v1/score-sets/{urn}",
        "suffix": "json",
        "terms": "Inspect the returned score-set license before use.",
        "terms_url": "https://www.mavedb.org/docs/mavedb/finding-data/downloading.html",
        "accession": urn,
    }
    if role != "abundance-original":
        CATALOG[f"mavedb-{role}-scores"] = {
            "url": f"https://api.mavedb.org/api/v1/score-sets/{urn}/scores",
            "suffix": "csv",
            "terms": "License inherited from the corresponding score-set metadata.",
            "terms_url": "https://www.mavedb.org/docs/mavedb/finding-data/downloading.html",
            "accession": urn,
        }


async def acquire(asset_root: Path, refresh=False, imports: Path | None = None):
    store = AssetStore(asset_root)
    path = ROOT / "data/manifests/pten-source-manifest.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    old = {x["id"]: x for x in previous.get("sources", [])}
    sources = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for source_id, config in CATALOG.items():
            if not refresh and source_id in old:
                try:
                    store.read(old[source_id]["asset"])
                    sources.append(old[source_id])
                    continue
                except (OSError, ValueError):
                    pass
            if imports and (imports / f'{source_id}.{config["suffix"]}').is_file():
                raw = (imports / f'{source_id}.{config["suffix"]}').read_bytes()
                method = "permitted_local_export"
            else:
                method = "documented_public_download"
                raw = None
                for attempt in range(3):
                    response = await client.get(config["url"])
                    if response.status_code in (429, 503) and attempt < 2:
                        await asyncio.sleep(
                            min(
                                10,
                                max(1, int(response.headers.get("retry-after", "2"))),
                            )
                        )
                        continue
                    response.raise_for_status()
                    if len(response.content) > 20_000_000:
                        raise ValueError("Source exceeds acquisition size limit.")
                    raw = response.content
                    break
                if raw is None:
                    raise ValueError(f"Source unavailable: {source_id}")
            asset = store.put(raw, config["suffix"])
            entry = {
                "id": source_id,
                "title": source_id,
                "url": config["url"],
                "canonical_url": config["url"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "accession": config.get("accession", source_id),
                "release": None,
                "license": config["terms"],
                "terms_url": config["terms_url"],
                "terms_status": "source_policy_recorded",
                "asset": asset,
                "parser_version": "pten-ingestion-1.0",
                "acquisition_method": method,
            }
            if config["suffix"] == "json":
                obj = json.loads(raw)
                if source_id.startswith("mavedb"):
                    entry["title"] = obj["title"]
                    entry["release"] = obj.get("modificationDate")
                    license = obj.get("license", {})
                    entry["license"] = license.get("shortName", "unknown")
                    entry["license_url"] = license.get("link")
                    entry["terms_status"] = (
                        "verified_dataset_CC0"
                        if license.get("shortName") == "CC0"
                        else "requires_terms_review"
                    )
                elif source_id == "uniprot-P60484":
                    entry["release"] = obj["entryAudit"]
                    entry["title"] = "UniProtKB human PTEN P60484"
                elif source_id == "pdb-1D5R-metadata":
                    entry["release"] = obj.get("rcsb_accession_info")
                    entry["title"] = "RCSB 1D5R experimental entry metadata"
            sources.append(entry)
    manifest = {
        "manifest_version": "1.0",
        "organism_taxonomy_id": 9606,
        "gene": "PTEN",
        "reference_accession": "P60484",
        "sources": sources,
        "data_mode": "real",
        "notes": [
            "Immutable raw bytes are stored locally by SHA-256 before transformation.",
            "No genome assembly or DNA allele is inferred from a protein substitution.",
            "Primary study DOI 10.1186/s13073-021-00984-x / PMC8518224 is referenced through the MaveDB metadata; full-text bytes are not required or redistributed.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
