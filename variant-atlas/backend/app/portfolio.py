"""Project metadata and a catalogue over existing immutable scientific/paper stores.

No migration rewrites scientific snapshots or copies source bytes. Local-only
application access restrictions continue to be enforced by main.py.
"""
import copy
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import Field
from .schemas import Model
from .repositories.local import LocalRepository
from .research_schemas import ResearchRequest
from .blood.schemas import ComparisonRequest
from .papers import PaperLibrary, PaperUpload
from .paper_review import PaperReviewEngine, PaperReviewRequest
from .research_areas import registry


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def source_id(kind, original):
    return "source-" + digest([kind, original])[:24]


TERMINAL = {
    "completed_with_limitations",
    "abstained",
    "cancelled",
    "failed",
    "interrupted",
}
METHODS = {
    "pten": {
        "title": "PTEN variant investigation",
        "scope": "Human PTEN: audited single-substitution activity, abundance and experimental reference geometry. No mutant folding or clinical classification.",
        "context": "Human PTEN · P60484 · experimental 1D5R",
    },
    "blood": {
        "title": "Blood-group comparative evidence review",
        "scope": "Reported ABO/RhD phenotypes in severe P. falciparum malaria; inspected literature and schematic cells. No individual risk, genotyping or infection simulation.",
        "context": "Reported blood groups · severe P. falciparum malaria",
    },
    "papers": {
        "title": "Bounded paper review",
        "scope": "Review selected original-language passages with checked quotations. No new dataset analysis, clinical prediction or independent reproduction of a study.",
        "context": "Paper-led research · explicit passage coverage",
    },
}


class ProjectCreate(Model):
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=3000)
    objective: str = Field(min_length=10, max_length=1800)
    method: Literal["pten", "blood", "papers"]
    source_ids: list[str] = Field(default_factory=list, max_length=40)
    area: str = Field(default="", max_length=80)


class SourceLink(Model):
    source_id: str
    action: Literal["link", "unlink", "include", "exclude", "refresh"] = "link"


class ProjectState(Model):
    expected_revision: int = Field(ge=0)
    state: dict


class NoteCreate(Model):
    text: str = Field(min_length=1, max_length=8000)
    kind: Literal["researcher note", "review note"] = "researcher note"
    run_id: str | None = None
    source_id: str | None = None


class StartProjectRun(Model):
    confirmed: Literal[True]
    pten: ResearchRequest | None = None
    blood: ComparisonRequest | None = None
    paper: PaperReviewRequest | None = None
    continuation_id: str | None = None


class Visit(Model):
    tab: Literal["workspace", "evidence", "results", "notebook"]
    view: Literal["molecule", "table", "alternatives", "criteria", "analysis", "experiments"] | None = None
    source_id: str | None = None
    run_id: str | None = None


class ContinueRequest(Model):
    question: str = Field(min_length=10, max_length=1800)
    reason: str = Field(min_length=5, max_length=2000)


class ContinueUpdate(Model):
    expected_revision: int = Field(ge=0)
    inputs: dict


class AttachRun(Model):
    run_id: str


class JourneyLink(Model):
    journey_id: str = Field(pattern=r"^journey-[a-f0-9]{32}$")


class Portfolio:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.store = getattr(app.state, "blood_store", None) or getattr(
            app.state, "research_store", None
        )
        if self.store is None:
            raise ValueError("Metadata storage is unavailable.")
        self.db = self.store.db
        self.root = Path(settings.local_data_dir) / "portfolio"
        self.path = self.root / "metadata.json"
        if self.db is None:
            self.root.mkdir(parents=True, exist_ok=True)

    def empty(self):
        return {
            "schema_version": 1,
            "revision": 0,
            "projects": {},
            "run_links": {},
            "notes": {},
            "catalogue_versions": {},
            "created_at": now(),
        }

    def read(self):
        if self.db is not None:
            return (
                self.db.portfolio_metadata.find_one({"_id": "portfolio"}, {"_id": 0})
                or self.empty()
            )
        return json.loads(self.path.read_text()) if self.path.exists() else self.empty()

    def mutate(self, change, backup=False):
        if self.db is not None:
            self.db.portfolio_metadata.update_one(
                {"_id": "portfolio"}, {"$setOnInsert": self.empty()}, upsert=True
            )
            for _ in range(12):
                old = self.read()
                if backup:
                    self.db.portfolio_metadata_backups.insert_one(
                        {
                            "_id": uuid4().hex,
                            "saved_at": now(),
                            "metadata": copy.deepcopy(old),
                        }
                    )
                new = change(copy.deepcopy(old))
                new["revision"] = old["revision"] + 1
                if self.db.portfolio_metadata.replace_one(
                    {"_id": "portfolio", "revision": old["revision"]},
                    {"_id": "portfolio", **new},
                ).modified_count:
                    return new
            raise ValueError("Concurrent metadata change; refresh and retry.")
        with self.store.locked("portfolio-metadata"):
            old = self.read()
            new = change(copy.deepcopy(old))
            new["revision"] = old["revision"] + 1
            if self.path.exists() and (
                backup or old.get("schema_version") != new.get("schema_version")
            ):
                backup = self.root / "backups"
                backup.mkdir(exist_ok=True)
                shutil.copy2(
                    self.path,
                    backup / (now().replace(":", "-") + "-" + uuid4().hex + ".json"),
                )
            LocalRepository.atomic_write(self.path, new)
            return new

    def run_store(self, method):
        if method == "papers":
            return PaperReviewEngine(self.store, self.settings).store
        name = "research_store" if method == "pten" else "blood_store"
        store = getattr(self.app.state, name, None)
        if store:
            return store
        store = copy.copy(self.store)
        store.workspace_id = "pten-real" if method == "pten" else "blood-group"
        return store

    def method_available(self, method):
        if method == "papers":
            return True  # Extraction/navigation work without a paid provider.
        return bool(
            getattr(
                self.app.state,
                "research_engine" if method == "pten" else "blood_engine",
                None,
            )
        )

    def runs(self):
        if hasattr(self, "_runs_cache"):
            return self._runs_cache
        docs = []
        for method in ["pten", "blood", "papers"]:
            store = self.run_store(method)
            if not store:
                continue
            if store.db is None:
                docs.extend(
                    json.loads(p.read_text())
                    for p in store.root.glob("research-*.json")
                    if (
                        json.loads(p.read_text()).get("workspace_id", "pten-real")
                        == store.workspace_id
                    )
                )
            else:
                docs.extend(
                    store.db.investigations.find(
                        {"workspace_id": store.workspace_id}, {"_id": 0}
                    )
                    .sort("created_at", -1)
                    .limit(1000)
                )
        self._runs_cache = sorted(docs, key=lambda d: d["created_at"], reverse=True)
        return self._runs_cache

    def run(self, rid):
        for method in ["pten", "blood", "papers"]:
            store = self.run_store(method)
            if store:
                doc = store.get(rid)
                if doc:
                    return doc
        raise KeyError(
            "Investigation not found; historical missing sources do not remove a saved run."
        )

    def catalogue(self):
        rows = {}

        def add(kind, original, title, typ, version, method, **kw):
            sid = source_id(kind, original)
            row = {
                "id": sid,
                "origin_id": original,
                "family": kind,
                "title": title,
                "type": typ,
                "version": str(version),
                "method": method,
                "preparation": "ready",
                "scientific_eligibility": "Supported reference evidence; applicability must be reviewed.",
                "origin": "public reference",
                "url": None,
                "added_at": None,
                "licence": "See original source; no additional rights inferred.",
                "coverage": "Method-specific pinned evidence; no participant measurements.",
                "details": {},
                **kw,
            }
            rows.setdefault(sid, row)
            return row

        data = getattr(self.app.state, "science", None)
        if data:
            w = data.workspace()
            for s in w["sources"]:
                add(
                    "pten",
                    s["id"],
                    s["title"],
                    "dataset" if "mave" in s["url"].lower() else "reference",
                    digest(s),
                    "pten",
                    url=s["url"],
                    details=s,
                    coverage="Pinned PTEN source snapshot. Native assay scales and missing values are retained.",
                )
            sequence = rows.get(source_id("pten", "uniprot-P60484"))
            if sequence:
                sequence.update(
                    type="sequence",
                    aliases=["P60484"],
                    details={**sequence["details"], "protein": w["protein"]},
                    coverage=f"{w['protein']['length']} amino-acid reference; participant genotype not measured.",
                )
            structure = rows.get(source_id("pten", "pdb-1D5R"))
            if structure:
                structure.update(
                    type="structure",
                    aliases=["1D5R"],
                    details={**structure["details"], "structure": w["structure"]},
                    coverage="Experimental engineered/truncated reference; unresolved positions remain gaps. Not a mutant prediction.",
                )
        engine = getattr(self.app.state, "blood_engine", None)
        if engine:
            for s in engine.sources:
                add(
                    "blood",
                    s["id"],
                    s["title"],
                    "background evidence",
                    digest(s),
                    "blood",
                    url=s["url"],
                    added_at=s["retrieved_at"],
                    details=s,
                    coverage="Inspected curator paraphrase, not a verbatim quotation. Fixed comparative corpus; no genotyping or personal risk.",
                )
        for p in PaperLibrary(self.settings).list():
            status = {
                "extracted": "ready",
                "partial": "ready",
                "needs_ocr": "needs OCR",
            }.get(p["status"], "failed")
            add(
                "paper",
                p["id"],
                p["filename"],
                "paper",
                p["sha256"],
                None,
                preparation=status,
                origin=p.get("provenance",{}).get("provider","local upload"),
                url=p.get("provenance",{}).get("url") or p.get("provenance",{}).get("source_url"),
                added_at=p["created_at"],
                licence=p.get("provenance",{}).get("licence") or "Uploader-provided material; access does not establish redistribution rights.",
                scientific_eligibility="Bounded paper review: explicitly selected original-language passages. PTEN: optional paper evidence, subject to applicability review. Blood method: not runtime evidence.",
                coverage=f"{p['characters']} extracted characters; {'partial extraction' if p['status']=='partial' else p['status']}. Reading: up to 12 selected passages (first 12 when none selected). Translation: up to 3 per explicit request. PTEN investigation: first 6 passages per included paper; at most 3 papers.",
                details=p,
            )
        # Historical manifests supply missing catalogue entries, without assigning old work to a project.
        for run in self.runs():
            kind = self.run_method(run)
            for s in run.get("source_manifest", []):
                original = s.get("id")
                if original:
                    add(
                        kind,
                        original,
                        s.get("title", original),
                        "background evidence" if kind == "blood" else "reference",
                        digest(s),
                        kind,
                        url=s.get("url"),
                        details=s,
                        preparation="failed",
                        coverage="Historical frozen source manifest; current source is unavailable.",
                    )
            for p in run.get("paper_sources", []):
                add(
                    "paper",
                    p["id"],
                    p["filename"],
                    "paper",
                    p["sha256"],
                    None,
                    preparation="failed",
                    origin="frozen investigation source",
                    coverage="Frozen original-language passages retained in an investigation; current library original may be absent.",
                    details={k: v for k, v in p.items() if k != "chunks"},
                )
        return list(rows.values())

    def migrate(self):
        rows = self.catalogue()
        old = self.read()
        new_versions = {
            r["id"] + "@" + r["version"]: r
            for r in rows
            if r["id"] + "@" + r["version"] not in old["catalogue_versions"]
        }
        by_origin = {(r["family"], r["origin_id"]): r for r in rows}
        for run in self.runs():
            family = self.run_method(run)
            for original in run.get("source_manifest", []):
                base = by_origin.get((family, original.get("id")))
                if not base:
                    continue
                version = digest(original)
                key = base["id"] + "@" + version
                if key not in old["catalogue_versions"] and key not in new_versions:
                    new_versions[key] = {
                        **base,
                        "version": version,
                        "details": original,
                        "coverage": "Frozen investigation source manifest. Inspect the original run for actual context coverage.",
                    }
        if new_versions or not self.path.exists() and self.db is None:

            def change(d):
                d["catalogue_versions"].update(new_versions)
                return d

            self.mutate(change, backup=True)
        return rows

    def sources(self):
        rows = self.migrate()
        meta = self.read()
        for s in rows:
            s["projects"] = [
                {"id": p["id"], "title": p["title"]}
                for p in meta["projects"].values()
                if s["id"] in p["sources"]
            ]
            s["citing_investigations"] = [
                r["run_id"] for r in self.runs() if self.run_cites(r, s)
            ]
        return rows

    def source(self, sid):
        for s in self.sources():
            if s["id"] == sid:
                return s
        meta = self.read()
        old = [v for v in meta["catalogue_versions"].values() if v["id"] == sid]
        if old:
            return {
                **old[-1],
                "projects": [],
                "citing_investigations": [],
                "preparation": "failed",
                "coverage": "Historical catalogue record; current source is unavailable. Frozen runs remain inspectable.",
            }
        raise KeyError("Source not found.")

    def run_cites(self, r, s):
        method = self.run_method(r)
        if s["family"] == "paper":
            return any(p["id"] == s["origin_id"] for p in r.get("paper_sources", []))
        return s["family"] == method and (
            any(x["id"] == s["origin_id"] for x in r.get("source_manifest", []))
            or method == "pten"
            and s["origin_id"] in ("P60484", "1D5R")
        )

    def required(self, method):
        return [
            s
            for s in self.catalogue()
            if s["method"] == method and not s["coverage"].startswith("Historical")
        ]

    def raw_project(self, pid):
        p = self.read()["projects"].get(pid)
        if not p:
            raise KeyError("Project not found.")
        return p

    def project(self, pid):
        p = copy.deepcopy(self.raw_project(pid))
        runs = [r for r in self.runs() if self.project_for(r) == pid]
        catalog = {s["id"]: s for s in self.catalogue()}
        required = self.required(p["method"])
        missing = [
            s["id"]
            for s in required
            if s["id"] not in p["sources"]
            or p["sources"][s["id"]]["version"] != s["version"]
        ]
        if not runs:
            p["readiness"] = (
                "Source preparation required"
                if missing
                else (
                    "Investigation ready"
                    if p.get("exploration_state") or p.get("journey_id")
                    else "Ready to explore"
                )
            )
        elif any(r["status"] not in TERMINAL for r in runs):
            p["readiness"] = "Investigation running"
        elif runs[0]["status"] != "completed_with_limitations":
            p["readiness"] = "Investigation needs attention"
        else:
            p["readiness"] = "Results ready for review"
        p["missing_required_source_ids"] = missing
        if p["method"] == "papers" and not any(link.get("included") and catalog.get(sid, {}).get("preparation") == "ready" for sid, link in p["sources"].items()):
            p["readiness"] = "Add an extracted paper"
        p["method_info"] = {
            **METHODS[p["method"]],
            "available": self.method_available(p["method"]),
        }
        if not self.method_available(p["method"]):
            p["readiness"] = "Source preparation required"
        p["run_ids"] = [r["run_id"] for r in runs]
        for sid, link in p["sources"].items():
            link["source"] = self.read()["catalogue_versions"].get(
                sid + "@" + link["version"]
            ) or catalog.get(sid)
            if link["source"]:
                link["source"] = {
                    **link["source"],
                    "preparation": catalog.get(sid, {}).get("preparation", "failed"),
                }
            link["current_version"] = catalog.get(sid, {}).get("version")
            link["version_changed"] = link["version"] != link["current_version"]
        return p

    def projects(self):
        return [
            self.project(p["id"])
            for p in sorted(
                self.read()["projects"].values(),
                key=lambda p: p["updated_at"],
                reverse=True,
            )
        ]

    def create(self, body):
        if not self.method_available(body.method):
            raise ValueError(
                "This method data is unavailable. Restore the supported source assets before creating this project."
            )
        self.migrate()
        rows = {s["id"]: s for s in self.catalogue()}
        if not set(body.source_ids) <= rows.keys():
            raise ValueError("Unknown source selection.")
        pid = "project-" + uuid4().hex
        p = {
            "id": pid,
            **body.model_dump(exclude={"source_ids"}),
            "context": METHODS[body.method]["context"],
            "created_at": now(),
            "updated_at": now(),
            "revision": 0,
            "sources": {
                sid: {
                    "version": rows[sid]["version"],
                    "included": False,
                    "linked_at": now(),
                }
                for sid in set(body.source_ids)
            },
            "exploration_state": {},
            "journey_id": None,
            "activity": [
                {
                    "at": now(),
                    "kind": "researcher action",
                    "text": "Project created with an explicit supported research method.",
                }
            ],
        }
        self.mutate(lambda d: dict(d, projects={**d["projects"], pid: p}))
        return self.project(pid)

    def edit_project(self, pid, fn):
        def change(d):
            if pid not in d["projects"]:
                raise KeyError("Project not found.")
            p = fn(d["projects"][pid])
            p["updated_at"] = now()
            p["revision"] += 1
            d["projects"][pid] = p
            return d

        self.mutate(change)
        return self.project(pid)

    def link(self, pid, body):
        self.migrate()
        s = self.source(body.source_id)
        p = self.raw_project(pid)
        if body.action == "include" and (
            s["preparation"] != "ready"
            or s["family"] == "paper"
            and p["method"] not in ("pten", "papers")
            or s["method"] not in (None, p["method"])
        ):
            raise ValueError(
                "This source is not eligible for this method. Extraction readiness is separate from scientific eligibility."
            )

        def edit(p):
            sid = s["id"]
            if body.action == "unlink":
                p["sources"].pop(sid, None)
            elif body.action == "link":
                p["sources"].setdefault(
                    sid,
                    {"version": s["version"], "included": False, "linked_at": now()},
                )
            else:
                if sid not in p["sources"]:
                    raise ValueError("Link the source to this project first.")
                if body.action == "refresh":
                    p["sources"][sid]["version"] = s["version"]
                else:
                    p["sources"][sid]["included"] = body.action == "include"
            p["activity"].append(
                {
                    "at": now(),
                    "kind": "researcher action",
                    "text": body.action.title() + " source: " + s["title"],
                }
            )
            return p

        return self.edit_project(pid, edit)

    def project_for(self, run):
        links = self.read()["run_links"]
        pid = links.get(run["run_id"], {}).get("project_id") or run.get(
            "request", {}
        ).get("project_id")
        return pid if pid in self.read()["projects"] else None

    def run_summaries(self):
        meta = self.read()
        out = []
        for r in self.runs():
            pid = self.project_for(r)
            out.append(
                {
                    "id": r["run_id"],
                    "question": r["request"]["question"],
                    "status": r["status"],
                    "method": self.run_method(r),
                    "created_at": r["created_at"],
                    "project_id": pid,
                    "project_title": meta["projects"][pid]["title"]
                    if pid
                    else "Unassigned",
                    "provider": r.get("provider"),
                    "model": r.get("model"),
                    "has_result": bool(r.get("result") or r.get("findings")),
                }
            )
        return out

    def attach(self, pid, rid):
        p = self.raw_project(pid)
        r = self.run(rid)
        method = self.run_method(r)
        if method != p["method"]:
            raise ValueError("The investigation method does not match this project.")
        if self.project_for(r) not in (None, pid):
            raise ValueError("Investigation is already assigned to another project.")

        def change(d):
            d["run_links"][rid] = {
                "project_id": pid,
                "linked_at": now(),
                "provenance": "Explicit researcher link; no historical membership inferred.",
            }
            return d

        self.mutate(change)
        return self.project(pid)

    def start(self, pid, body):
        if body.continuation_id and self.db is None:
            # A repeated click or concurrent local request cannot start the same
            # saved draft twice. The original scientific run remains untouched.
            with self.store.locked("followup-" + digest([pid, body.continuation_id])):
                return self._start(pid, body)
        return self._start(pid, body)

    def _start(self, pid, body):
        p = self.project(pid)
        frozen_links = copy.deepcopy(self.raw_project(pid)["sources"])
        if not self.method_available(p["method"]):
            raise ValueError(
                "The selected scientific method is unavailable. Historical run snapshots remain inspectable."
            )
        if p["missing_required_source_ids"]:
            raise ValueError(
                "Link the current method-required source versions before starting."
            )
        paper_ids = []
        for sid, link in p["sources"].items():
            if link["included"]:
                source = self.source(sid)
                if source["preparation"] != "ready" or link["version_changed"]:
                    raise ValueError(
                        "An included source is not ready or its pinned version changed."
                    )
                if source["family"] == "paper":
                    if p["method"] not in ("pten", "papers"):
                        raise ValueError(
                            "Uploaded papers are not runtime evidence for the fixed blood corpus."
                        )
                    paper_ids.append(source["origin_id"])
        if p["method"] == "pten" and len(paper_ids) > 3:
            raise ValueError("At most three included papers are supported by PTEN.")
        continuation = None
        if body.continuation_id:
            continuation = self.raw_project(pid).get("continuations", {}).get(body.continuation_id)
            if not continuation or continuation.get("run_id"):
                raise ValueError("Follow-up draft is missing or has already started.")
        if p["method"] == "pten":
            if not body.pten or body.blood or body.paper:
                raise ValueError("Provide PTEN-specific inputs only.")
            if len(body.pten.selected_ids) > body.pten.capacity:
                raise ValueError(
                    "Selected variants exceed the explicit candidate capacity. No candidates were dropped."
                )
            req = body.pten.model_copy(
                update={"project_id": pid, "paper_ids": paper_ids}
            )
            run = self.app.state.research_engine.start(req)
        elif p["method"] == "blood":
            if not body.blood or body.pten or body.paper:
                raise ValueError("Provide comparative-method inputs only.")
            run = self.app.state.blood_engine.start(
                body.blood.model_copy(update={"project_id": pid})
            )
        else:
            if not body.paper or body.pten or body.blood:
                raise ValueError("Provide paper review inputs only.")
            link = p["sources"].get(body.paper.source_id)
            if not link or not link["included"] or link["version_changed"] or link["source"]["family"] != "paper" or link["version"] != body.paper.source_version:
                raise ValueError("Link, include and review this exact paper version before starting.")
            extra=[]
            seen={body.paper.source_id}
            for selected in body.paper.additional_sources:
                other=p["sources"].get(selected.source_id)
                if selected.source_id in seen or not other or not other["included"] or other["version_changed"] or other["version"]!=selected.source_version or other["source"]["family"]!="paper" or other["source"]["preparation"]!="ready":
                    raise ValueError("Every comparison study must be a distinct included paper at its reviewed source version.")
                seen.add(selected.source_id);extra.append(other["source"])
            run = PaperReviewEngine(self.store, self.settings).start(pid, link["source"], body.paper, extra)

        def change(d):
            d["run_links"][run["run_id"]] = {
                "project_id": pid,
                "linked_at": now(),
                "sources": frozen_links,
                "provenance": "Created through reviewed project inputs.",
            }
            if continuation:
                d["run_links"][run["run_id"]]["parent_run_id"] = continuation["parent_run_id"]
                d["run_links"][run["run_id"]]["continuation_id"] = body.continuation_id
                draft = d["projects"][pid]["continuations"][body.continuation_id]
                draft["run_id"] = run["run_id"]
                draft["submitted_inputs"] = copy.deepcopy(run["request"])
                draft["submitted_sources"] = copy.deepcopy(d["run_links"][run["run_id"]]["sources"])
            return d

        self.mutate(change)
        return run

    @staticmethod
    def run_method(run):
        return {"blood-group": "blood", "paper-review": "papers"}.get(run.get("workspace_id"), "pten")

    def continue_run(self, pid, rid, body):
        run = self.run(rid)
        if self.project_for(run) != pid:
            raise ValueError("Follow-up must stay in the parent investigation's project.")
        if run["status"] not in TERMINAL:
            raise ValueError("Review the completed or stopped investigation before creating a follow-up.")
        cid = "followup-" + uuid4().hex
        draft = {"id": cid, "parent_run_id": rid, "created_at": now(), "revision": 0, "reason": body.reason, "previous_question": run["request"]["question"], "baseline_inputs": copy.deepcopy(run["request"]), "inputs": {**copy.deepcopy(run["request"]), "question": body.question}, "baseline_sources": copy.deepcopy(self.read()["run_links"].get(rid, {}).get("sources", {})), "run_id": None}
        self.edit_project(pid, lambda p: dict(p, continuations={**p.get("continuations", {}), cid: draft}))
        return draft


def router(app, settings):
    r = APIRouter(prefix="/api/portfolio")

    def service():
        return Portfolio(app, settings)

    def wrap(fn):
        try:
            return fn()
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @r.get("/bootstrap")
    def bootstrap():
        s = service()
        sources = s.sources()
        return {
            "methods": {
                key: {**value, "available": s.method_available(key)}
                for key, value in METHODS.items()
            },
            "projects": s.projects(),
            "sources": sources,
            "investigations": s.run_summaries(),
            "notes": list(s.read()["notes"].values()),
            "search_method": "lexical local workspace catalogue",
            "local_only": True,
            "areas": registry(s.method_available),
        }

    @r.get("/sources")
    def sources():
        return service().sources()

    @r.get("/sources/{sid}")
    def source(sid: str):
        def go():
            s = service()
            row = s.source(sid)
            row["versions"] = [
                v for v in s.read()["catalogue_versions"].values() if v["id"] == sid
            ]
            return row

        return wrap(go)

    @r.post("/sources/import")
    def import_source(body: PaperUpload):
        def go():
            s = service()
            p = PaperLibrary(settings).upload(body)
            s.migrate()
            return s.source(source_id("paper", p["id"]))

        return wrap(go)

    @r.get("/projects")
    def projects():
        return service().projects()

    @r.post("/projects")
    def create(body: ProjectCreate):
        return wrap(lambda: service().create(body))

    @r.get("/projects/{pid}")
    def project(pid: str):
        return wrap(lambda: service().project(pid))

    @r.post("/projects/{pid}/sources")
    def link(pid: str, body: SourceLink):
        return wrap(lambda: service().link(pid, body))

    @r.post("/projects/{pid}/state")
    def state(pid: str, body: ProjectState):
        def go():
            s = service()

            def change(p):
                if p["revision"] != body.expected_revision:
                    raise ValueError(
                        "Project changed; reload before saving exploration state."
                    )
                if len(json.dumps(body.state)) > 50000:
                    raise ValueError("Exploration state is too large.")
                state = copy.deepcopy(body.state)
                if p["method"] == "papers" and state.get("source_id"):
                    link = p["sources"].get(state["source_id"])
                    if not link:
                        raise ValueError("Link this source to the research before saving its reading position.")
                    source = s.source(state["source_id"])
                    if source["family"] != "paper":
                        raise ValueError("Reading position requires an extracted paper.")
                    ids = state.get("chunk_ids", [])
                    if not isinstance(ids, list) or len(ids) > 12 or any(not isinstance(i, str) for i in ids):
                        raise ValueError("Select up to 12 valid passage identities.")
                    PaperLibrary.selected_chunks(PaperLibrary(settings).get(source["origin_id"]), ids, 12)
                if p["method"] == "blood" and "blood_request" in state:
                    from .blood.schemas import interpret

                    state["interpretation"] = interpret(
                        ComparisonRequest.model_validate(state["blood_request"])
                    )
                p["exploration_state"] = state
                return p

            return s.edit_project(pid, change)

        return wrap(go)

    @r.post("/projects/{pid}/journey")
    def journey(pid: str, body: JourneyLink):
        def go():
            from .explorations import ExplorationJournal

            s = service()
            p = s.raw_project(pid)
            if p["method"] != "pten":
                raise ValueError("This method does not use a PTEN exploration journal.")
            if p.get("journey_id") == body.journey_id:
                return s.project(pid)
            ExplorationJournal(app.state.research_store, app.state.science).get(
                body.journey_id
            )
            if any(
                x["id"] != pid
                and body.journey_id in [x.get("journey_id"), *x.get("journey_ids", [])]
                for x in s.read()["projects"].values()
            ):
                raise ValueError("This scene is already linked to another project.")
            return s.edit_project(
                pid,
                lambda p: dict(
                    p,
                    journey_id=body.journey_id,
                    journey_ids=list(
                        dict.fromkeys([*p.get("journey_ids", []), body.journey_id])
                    ),
                ),
            )

        return wrap(go)

    @r.post("/projects/{pid}/notes")
    def note(pid: str, body: NoteCreate):
        def go():
            s = service()
            s.raw_project(pid)
            if body.run_id:
                s.run(body.run_id)
            if body.source_id:
                s.source(body.source_id)
            n = {
                "id": "note-" + uuid4().hex,
                "project_id": pid,
                "at": now(),
                **body.model_dump(),
                "authorship": "researcher-authored; not a verified scientific finding",
            }
            s.mutate(lambda d: dict(d, notes={**d["notes"], n["id"]: n}))
            return n

        return wrap(go)

    @r.post("/projects/{pid}/investigations")
    def start(pid: str, body: StartProjectRun, background: BackgroundTasks):
        s = service()
        run = wrap(lambda: s.start(pid, body))
        if s.run_method(run) == "papers":
            background.add_task(PaperReviewEngine(s.store, settings).execute, run["run_id"])
        return run

    @r.post("/projects/{pid}/visit")
    def visit(pid: str, body: Visit):
        def go():
            s = service()
            value = body.model_dump()
            if body.source_id and body.source_id not in s.raw_project(pid)["sources"]:
                raise ValueError("The selected source is not linked to this project.")
            if body.run_id and s.project_for(s.run(body.run_id)) != pid:
                raise ValueError("The investigation does not belong to this research.")
            if s.raw_project(pid).get("last_context") == value:
                return s.project(pid)
            return s.edit_project(pid, lambda p: dict(p, last_context=value, last_opened_at=now()))
        return wrap(go)

    @r.post("/projects/{pid}/investigations/{rid}/continue")
    def continue_run(pid: str, rid: str, body: ContinueRequest):
        return wrap(lambda: service().continue_run(pid, rid, body))

    @r.post("/projects/{pid}/continuations/{cid}")
    def update_continuation(pid: str, cid: str, body: ContinueUpdate):
        def go():
            s = service()
            def edit(p):
                draft = p.get("continuations", {}).get(cid)
                if not draft or draft.get("run_id") or draft["revision"] != body.expected_revision:
                    raise ValueError("Follow-up draft changed or already started. Reload before saving.")
                if len(json.dumps(body.inputs)) > 50000:
                    raise ValueError("Follow-up inputs are too large.")
                draft["inputs"] = copy.deepcopy(body.inputs)
                draft["revision"] += 1
                return p
            return s.edit_project(pid, edit)
        return wrap(go)

    @r.post("/investigations/{rid}/cancel")
    def cancel_paper(rid: str):
        def go():
            s = service()
            run = s.run(rid)
            if s.run_method(run) != "papers":
                raise ValueError("Use this scientific method's original cancellation endpoint.")
            return PaperReviewEngine(s.store, settings).cancel(rid)
        return wrap(go)

    @r.post("/projects/{pid}/attach-investigation")
    def attach(pid: str, body: AttachRun):
        return wrap(lambda: service().attach(pid, body.run_id))

    @r.get("/investigations/{rid}")
    def run_detail(rid: str):
        def go():
            s = service()
            doc = s.run(rid)
            pid = s.project_for(doc)
            return {
                "run": doc,
                "project": s.project(pid) if pid else None,
                "method": s.run_method(doc),
                "lineage": s.read()["run_links"].get(rid, {}),
                "sources": [
                    {
                        **x,
                        "cited_version": next(
                            (
                                digest(m)
                                for m in doc.get("source_manifest", [])
                                if m.get("id") == x["origin_id"]
                            ),
                            x["version"],
                        ),
                    }
                    for x in s.sources()
                    if s.run_cites(doc, x)
                ],
            }

        return wrap(go)

    return r
