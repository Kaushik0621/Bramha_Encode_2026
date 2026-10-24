"""Versioned visual observations, stored locally or in the configured Atlas database."""
import copy
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field
from .schemas import Model
from .research_schemas import ResearchCriteria
from .repositories.local import LocalRepository


def now():
    return datetime.now(timezone.utc).isoformat()


class SceneState(Model):
    reference_visible: bool = True
    paper_ids: list[str] = Field(default_factory=list, max_length=3)
    selected_id: str
    picked_ids: list[str] = Field(default_factory=list, max_length=131)
    focus_ids: list[str] = Field(default_factory=list, max_length=131)
    layer: Literal["activity", "abundance"] = "activity"
    view: Literal["protein", "workflow", "split", "evidence"] = "protein"
    criteria: ResearchCriteria
    question: str = Field(default="", max_length=1800)
    capacity: int = Field(default=10, ge=1, le=200)
    run_id: str | None = None
    scenario_execution_id: str | None = None


class CreateExploration(Model):
    previous_id: str | None = None
    dataset_version: str
    state: SceneState
    title: str = Field(
        default="PTEN research exploration", min_length=1, max_length=120
    )


class UpdateExploration(Model):
    expected_revision: int = Field(ge=0)
    change_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    state: SceneState


class ExplorationJournal:
    def __init__(self, store, data):
        self.store, self.data = store, data
        self.root = store.settings.local_data_dir / "explorations"
        self.db = store.db
        if self.db is None:
            self.root.mkdir(parents=True, exist_ok=True)

    def validate(self, state, version):
        w = self.data.workspace()
        if version != w["dataset_version"]:
            raise ValueError("Dataset version changed; start a new exploration.")
        ids = {v["id"] for v in w["variants"]}
        if (
            state.selected_id not in ids
            or not set(state.picked_ids + state.focus_ids) <= ids
        ):
            raise ValueError("Unknown substitution in visual observation.")
        if len(state.picked_ids) != len(set(state.picked_ids)) or len(
            state.focus_ids
        ) != len(set(state.focus_ids)):
            raise ValueError("Duplicate visual selection.")
        from .papers import PaperLibrary

        for pid in state.paper_ids:
            try:
                PaperLibrary(self.store.settings).get(pid)
            except KeyError as exc:
                raise ValueError(
                    "Linked paper must exist in the local library."
                ) from exc
        if state.run_id:
            run = self.store.get(state.run_id)
            if not run or run["dataset_version"] != version:
                raise ValueError("Investigation must exist in the same dataset.")
        if state.scenario_execution_id:
            if not re.fullmatch(r"execution-[a-f0-9]{32}", state.scenario_execution_id):
                raise ValueError("Invalid comparison execution reference.")
            path = (
                self.store.settings.local_data_dir
                / "scenario-lab"
                / (state.scenario_execution_id + ".json")
            )
            if (
                not path.exists()
                or json.loads(path.read_text())["dataset_version"] != version
            ):
                raise ValueError("Comparison execution must exist in this dataset.")
        return w

    def spatial(self, state, w):
        ids = set(state.picked_ids + state.focus_ids + [state.selected_id])
        return [
            {
                "variant_id": v["id"],
                "position": v["position"],
                "mapping_id": v["mapping"]["mapping_id"],
                "status": v["mapping"]["status"],
                "coordinate": v["mapping"]["coordinate"],
                "activity": v["activity"],
                "abundance": v["abundance"],
                "activity_se": v["activity_se"],
                "abundance_se": v["abundance_se"],
            }
            for v in w["variants"]
            if v["id"] in ids
        ]

    def observation(self, before, after, w, change_id):
        first = set(before.picked_ids) if before else set()
        last = set(after.picked_ids)
        changes = []
        if not before:
            changes.append("Exploration started")
        else:
            if before.selected_id != after.selected_id:
                changes.append("Inspected a different substitution")
            if first != last:
                changes.append("Updated the comparison cohort")
            if before.reference_visible != after.reference_visible:
                changes.append(
                    "Restored experimental reference to scene"
                    if after.reference_visible
                    else "Removed experimental reference from scene"
                )
            if before.paper_ids != after.paper_ids:
                changes.append("Changed linked research papers")
            if before.layer != after.layer:
                changes.append("Changed the measurement layer")
            if before.focus_ids != after.focus_ids:
                changes.append("Focused a different reference region")
            if before.criteria != after.criteria:
                changes.append("Changed exploratory filter criteria")
            if before.question != after.question:
                changes.append("Updated the research question draft")
            if before.capacity != after.capacity:
                changes.append("Changed comparison capacity")
            if before.run_id != after.run_id:
                changes.append("Opened an investigation checkpoint")
            if before.view != after.view:
                changes.append("Changed the research view")
        return {
            "id": change_id,
            "at": now(),
            "summary": " · ".join(changes) or "Saved the current research context",
            "before": before.model_dump() if before else None,
            "after": after.model_dump(),
            "added_ids": sorted(last - first),
            "removed_ids": sorted(first - last),
            "before_geometry": self.spatial(before, w) if before else [],
            "after_geometry": self.spatial(after, w),
            "reference_geometry_changed": False,
            "geometry_units": "angstrom",
            "interpretation": "Selection and evidence annotations changed. The experimental reference coordinates remain fixed.",
        }

    def create(self, body):
        w = self.validate(body.state, body.dataset_version)
        if body.previous_id:
            previous = self.get(body.previous_id)
            if previous["dataset_version"] != body.dataset_version:
                raise ValueError("Previous exploration belongs to another dataset.")
        doc = {
            "id": "journey-" + uuid.uuid4().hex,
            "schema_version": 1,
            "previous_id": body.previous_id,
            "workspace_id": w["id"],
            "dataset_version": w["dataset_version"],
            "title": body.title,
            "revision": 0,
            "created_at": now(),
            "updated_at": now(),
            "state": body.state.model_dump(),
            "source_manifest": w["sources"],
            "events": [self.observation(None, body.state, w, str(uuid.uuid4()))],
        }
        if self.db is None:
            LocalRepository.atomic_write(self.root / (doc["id"] + ".json"), doc)
        else:
            self.db.visual_explorations.insert_one(
                {"_id": doc["id"], **copy.deepcopy(doc)}
            )
        return doc

    def get(self, sid):
        if not re.fullmatch(r"journey-[a-f0-9]{32}", sid):
            raise ValueError("Invalid exploration identifier.")
        if self.db is not None:
            doc = self.db.visual_explorations.find_one({"_id": sid}, {"_id": 0})
        else:
            path = self.root / (sid + ".json")
            doc = json.loads(path.read_text()) if path.exists() else None
        if doc is None:
            raise KeyError("Exploration not found.")
        return doc

    def update(self, sid, body):
        def change(doc):
            if any(e["id"] == body.change_id for e in doc["events"]):
                return doc
            if body.expected_revision != doc["revision"]:
                raise ValueError(
                    "Exploration changed elsewhere. Reload before saving more changes."
                )
            if len(doc["events"]) >= 1000:
                raise ValueError(
                    "This exploration has reached its observation limit; start a new one. Existing records remain saved."
                )
            w = self.validate(body.state, doc["dataset_version"])
            doc["events"].append(
                self.observation(
                    SceneState.model_validate(doc["state"]),
                    body.state,
                    w,
                    body.change_id,
                )
            )
            doc["state"] = body.state.model_dump()
            doc["revision"] += 1
            doc["updated_at"] = now()
            if len(json.dumps(doc).encode()) > 12_000_000:
                raise ValueError(
                    "Observation storage limit reached; start a fresh exploration to continue the saved chain."
                )
            return doc

        if self.db is None:
            with self.store.locked(sid):
                doc = change(self.get(sid))
                LocalRepository.atomic_write(self.root / (sid + ".json"), doc)
                return doc
        previous = self.get(sid)
        doc = change(copy.deepcopy(previous))
        result = self.db.visual_explorations.replace_one(
            {"_id": sid, "revision": previous["revision"]}, {"_id": sid, **doc}
        )
        if not result.matched_count:
            raise ValueError("Concurrent exploration update; reload before saving.")
        return doc

    def list(self):
        if self.db is not None:
            docs = list(
                self.db.visual_explorations.find(
                    {"workspace_id": "pten-real"}, {"_id": 0}
                )
                .sort("updated_at", -1)
                .limit(100)
            )
        else:
            docs = sorted(
                (json.loads(p.read_text()) for p in self.root.glob("journey-*.json")),
                key=lambda d: d["updated_at"],
                reverse=True,
            )[:100]
        return [
            {
                k: d[k]
                for k in [
                    "id",
                    "title",
                    "dataset_version",
                    "revision",
                    "updated_at",
                    "state",
                ]
            }
            for d in docs
        ]

    def export(self, sid):
        doc = self.get(sid)
        linked = sorted(
            {e["after"]["run_id"] for e in doc["events"] if e["after"].get("run_id")}
        )
        executions = []
        for eid in sorted(
            {
                e["after"].get("scenario_execution_id")
                for e in doc["events"]
                if e["after"].get("scenario_execution_id")
            }
        ):
            path = self.store.settings.local_data_dir / "scenario-lab" / (eid + ".json")
            executions.append(
                json.loads(path.read_text())
                if path.exists()
                else {"id": eid, "status": "source_record_unavailable"}
            )
        return {
            "schema_version": 1,
            "product": "Bramha Atlas",
            "comparison_executions": executions,
            "linked_papers": self.export_papers(doc),
            "exploration": doc,
            "linked_investigations": [self.store.get(rid) for rid in linked],
            "knowledge_documents": [
                {
                    "id": doc["id"] + ":" + e["id"],
                    "workspace_id": doc["workspace_id"],
                    "dataset_version": doc["dataset_version"],
                    "kind": "visual_observation",
                    "text": e["summary"] + ". " + e["interpretation"],
                    "source_event_id": e["id"],
                    "scientific_validation": "observation_only",
                    "variant_ids": sorted(
                        set(e["after"]["picked_ids"] + [e["after"]["selected_id"]])
                    ),
                }
                for e in doc["events"]
            ],
            "retrieval_status": {
                "embedding_status": "not_generated",
                "vector_index_status": "not_indexed",
                "note": "Portable source-linked documents are prepared for later indexing; no vector retrieval is claimed.",
            },
            "migration": {
                "atlas_collection": "visual_explorations",
                "document_id_field": "id",
                "source_references": "Preserve dataset versions, source manifests, run IDs and observation IDs.",
            },
        }

    def export_papers(self, doc):
        from .papers import PaperLibrary

        library = PaperLibrary(self.store.settings)
        ids = sorted(
            {pid for e in doc["events"] for pid in e["after"].get("paper_ids", [])}
        )
        result = []
        for pid in ids:
            paper = library.get(pid)
            result.append(
                {
                    "source": paper,
                    "readings": [
                        json.loads(p.read_text())
                        for p in sorted(library.root.glob(pid + "-reading-*.json"))
                    ],
                }
            )
        return result
