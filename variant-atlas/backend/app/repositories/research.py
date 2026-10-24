"""Authoritative scientific state: atomically locked local files or optimistic Atlas updates.

The same revision-controlled state is used by HTTP and an independent leased job
worker. Process memory is never used as the scientific run's source of truth.
"""
import copy
import fcntl
import json
import re
import time
from contextlib import contextmanager
from pymongo import MongoClient, ASCENDING, ReturnDocument
from .local import LocalRepository
from . import RepositoryError

COLLECTIONS = [
    "workspaces",
    "sources",
    "proteins",
    "variant_representations",
    "variants",
    "assays",
    "measurements",
    "structures",
    "residue_mappings",
    "evidence_passages",
    "investigations",
    "tasks",
    "events",
    "artifacts",
    "findings",
    "hypotheses",
    "reviews",
]


class ResearchStore:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.local_data_dir / "research"
        self.client = None
        self.db = None
        if settings.data_backend == "atlas":
            if not settings.mongodb_uri:
                raise RepositoryError(
                    "Atlas configured without MONGODB_URI; no local fallback."
                )
            try:
                self.client = MongoClient(
                    settings.mongodb_uri,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                )
                self.client.admin.command("ping")
                self.db = self.client[settings.mongodb_database]
                for name in COLLECTIONS:
                    self.db[name].create_index(
                        [("workspace_id", ASCENDING)]
                        + (
                            [("run_id", ASCENDING)]
                            if name
                            in {
                                "tasks",
                                "artifacts",
                                "findings",
                                "hypotheses",
                                "reviews",
                            }
                            else []
                        )
                        + [("id", ASCENDING)],
                        unique=True,
                        partialFilterExpression={"id": {"$exists": True}},
                    )
                self.db.events.create_index(
                    [("run_id", ASCENDING), ("sequence", ASCENDING)], unique=True
                )
                self.db.investigations.create_index(
                    [("run_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"run_id": {"$exists": True}},
                )
                self.db.investigations.create_index(
                    [("status", ASCENDING), ("lease_until", ASCENDING)]
                )
            except Exception:
                if self.client is not None:
                    self.client.close()
                raise RepositoryError(
                    "Atlas research store is unavailable. Check access and cluster configuration."
                ) from None
        elif settings.data_backend == "local":
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            raise RepositoryError("Unsupported DATA_BACKEND.")

    @contextmanager
    def locked(self, name):
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / (name + ".lock"), "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def get(self, run_id):
        if not re.fullmatch(r"research-[a-f0-9]{32}", run_id):
            return None
        if self.db is not None:
            return self.db.investigations.find_one({"run_id": run_id}, {"_id": 0})
        path = self.root / (run_id + ".json")
        return json.loads(path.read_text()) if path.exists() else None

    def create(self, run):
        doc = copy.deepcopy(run)
        doc.setdefault("id", doc["run_id"])
        doc["revision"] = 0
        if self.db is not None:
            self.db.investigations.insert_one(copy.deepcopy(doc))
        else:
            with self.locked("queue"):
                LocalRepository.atomic_write(self.root / (doc["run_id"] + ".json"), doc)
        return doc

    def mutate(self, run_id, change):
        if self.db is not None:
            for _ in range(12):
                old = self.get(run_id)
                if old is None:
                    raise KeyError("Research run not found.")
                new = change(copy.deepcopy(old))
                new["revision"] = old["revision"] + 1
                result = self.db.investigations.replace_one(
                    {"run_id": run_id, "revision": old["revision"]}, copy.deepcopy(new)
                )
                if result.modified_count:
                    self._project(new)
                    return new
            raise RepositoryError(
                "Concurrent state update could not be committed; retry safely."
            )
        with self.locked(run_id):
            old = self.get(run_id)
            if old is None:
                raise KeyError("Research run not found.")
            new = change(copy.deepcopy(old))
            new["revision"] = old["revision"] + 1
            LocalRepository.atomic_write(self.root / (run_id + ".json"), new)
            return new

    def list(self):
        if self.db is not None:
            return list(
                self.db.investigations.find(
                    {"run_id": {"$exists": True}, "workspace_id": "pten-real"},
                    {"_id": 0},
                )
                .sort("created_at", -1)
                .limit(100)
            )
        return sorted(
            [json.loads(p.read_text()) for p in self.root.glob("research-*.json")],
            key=lambda x: x["created_at"],
            reverse=True,
        )[:100]

    def claim(self, worker_id, lease_seconds=30):
        if self.db is not None:
            return self.db.investigations.find_one_and_update(
                {"workspace_id": "pten-real", "status": "queued"},
                {
                    "$set": {
                        "status": "running",
                        "lease_owner": worker_id,
                        "lease_until": time.time() + lease_seconds,
                    },
                    "$inc": {"revision": 1},
                },
                return_document=ReturnDocument.AFTER,
                projection={"_id": 0},
            )
        with self.locked("queue"):
            for item in self.list():
                if item["status"] == "queued":
                    return self.mutate(
                        item["run_id"],
                        lambda d: dict(
                            d,
                            status="running",
                            lease_owner=worker_id,
                            lease_until=time.time() + lease_seconds,
                        ),
                    )
        return None

    def renew(self, run_id, worker_id):
        def update(d):
            if d.get("lease_owner") != worker_id:
                raise RepositoryError("Job lease lost.")
            d["lease_until"] = time.time() + 30
            return d

        return self.mutate(run_id, update)

    def seed(self, w):
        if self.db is None:
            LocalRepository.atomic_write(self.root / "workspace.json", w)
            return
        entities = {
            "workspaces": [
                {
                    "id": w["id"],
                    "dataset_version": w["dataset_version"],
                    "data_mode": "real",
                    "name": w["name"],
                    "snapshot": w,
                }
            ],
            "sources": w["sources"],
            "proteins": [w["protein"]],
            "variants": w["variants"],
            "variant_representations": [
                {
                    "id": v["id"] + ":protein",
                    "variant_id": v["id"],
                    "reference_accession": "P60484",
                    "sequence_version": v["reference_sequence_version"],
                    "representation_level": "protein_substitution",
                    "protein_hgvs": v["protein_hgvs"],
                    "dna_allele_status": "not_uniquely_inferred",
                    "taxonomy_id": 9606,
                }
                for v in w["variants"]
            ],
            "assays": w["assays"],
            "measurements": [
                {
                    "id": v["id"] + ":" + a,
                    "variant_id": v["id"],
                    "assay_id": a,
                    "value": v[a],
                    "source_record_id": v[a + "_record"],
                    "source_id": "mavedb-" + a + "-scores",
                }
                for v in w["variants"]
                for a in ["activity", "abundance"]
            ],
            "structures": [
                {"id": "1D5R", **w["structure"], "asset": w["structure_asset"]}
            ],
            "residue_mappings": [{"id": m["mapping_id"], **m} for m in w["mappings"]],
            "evidence_passages": w["evidence"],
        }
        for name, docs in entities.items():
            for doc in docs:
                row = dict(doc, workspace_id=w["id"])
                self.db[name].replace_one(
                    {"workspace_id": w["id"], "id": row["id"]}, row, upsert=True
                )

    def workspace(self):
        if self.db is not None:
            record = self.db.workspaces.find_one(
                {"workspace_id": "pten-real", "id": "pten-real"}
            )
            if not record:
                raise RepositoryError(
                    "Atlas PTEN workspace is unseeded. Run scripts/seed_research.py."
                )
            return record["snapshot"]
        path = self.root / "workspace.json"
        if not path.exists():
            raise RepositoryError(
                "Research workspace is unseeded. Run scripts/seed_research.py."
            )
        return json.loads(path.read_text())

    def _project(self, run):
        # The revision-committed investigation snapshot is authoritative. Normalized
        # projections are idempotent and can be repaired from it after an interruption.
        for name, key in [
            ("tasks", "tasks"),
            ("artifacts", "artifacts"),
            ("findings", "findings"),
            ("reviews", "reviews"),
            ("hypotheses", "hypotheses"),
        ]:
            for row in run.get(key, []):
                identifier = row.get("id") or row.get("task_id")
                self.db[name].replace_one(
                    {
                        "workspace_id": run["workspace_id"],
                        "run_id": run["run_id"],
                        "id": identifier,
                    },
                    dict(
                        row,
                        id=identifier,
                        workspace_id=run["workspace_id"],
                        run_id=run["run_id"],
                    ),
                    upsert=True,
                )
        for event in run["events"]:
            self.db.events.update_one(
                {"run_id": run["run_id"], "sequence": event["sequence"]},
                {"$setOnInsert": dict(event, workspace_id=run["workspace_id"])},
                upsert=True,
            )

    def repair_projections(self, run_id):
        run = self.get(run_id)
        if run is None:
            raise KeyError("Research investigation not found.")
        if self.db is None:
            raise RepositoryError(
                "Local snapshots need no normalized Atlas projection repair."
            )
        self._project(run)
        return {"run_id": run_id, "revision": run["revision"], "repaired": True}

    def close(self):
        if self.client is not None:
            self.client.close()
