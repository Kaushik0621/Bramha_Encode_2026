"""Bounded document review using the existing paper reader and run repository.

This reviews reported passages; it is not a new disease analysis engine. All
observable transitions are persisted and provider failure never becomes success.
"""
import asyncio
import copy
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from pydantic import Field
from .schemas import Model
from .papers import PaperLibrary, PaperRead

TERMINAL = {"completed_with_limitations", "abstained", "failed", "cancelled", "interrupted"}


def now():
    return datetime.now(timezone.utc).isoformat()


class AdditionalPaper(Model):
    source_id: str
    source_version: str


class PaperReviewRequest(Model):
    question: str = Field(min_length=10, max_length=1800)
    source_id: str
    source_version: str
    chunk_ids: list[str] = Field(min_length=1, max_length=12)
    language: str = Field(default="English", min_length=1, max_length=80)
    depth: Literal["quick", "standard", "deep"] = "quick"
    max_seconds: int = Field(default=120, ge=30, le=600)
    additional_sources: list[AdditionalPaper] = Field(default_factory=list, max_length=2)


class PaperReviewEngine:
    def __init__(self, store, settings):
        self.store = copy.copy(store)
        self.store.workspace_id = "paper-review"
        self.settings = settings

    @staticmethod
    def event(doc, kind, summary, refs=None):
        doc["events"].append({"event_id": uuid4().hex, "sequence": len(doc["events"]) + 1, "timestamp": now(), "type": kind, "task_id": "paper-review", "summary": summary, "input_refs": refs or [], "output_refs": [], "status": doc["status"]})
        return doc

    def start(self, project_id, source, body, additional_sources=None):
        # Fail before queueing when no actual provider is available.
        if not self.settings.google_api_key and not self.settings.openrouter_api_key:
            raise ValueError("A model provider is required for paper review. Original text and notebook work remain available.")
        paper = PaperLibrary(self.settings).get(source["origin_id"])
        chunks = PaperLibrary.selected_chunks(paper, body.chunk_ids, 12)
        if not chunks or paper["sha256"] != body.source_version:
            raise ValueError("Review the current extracted source version and selected passages before starting.")
        paper_sources=[{**paper,"chunks":chunks}]
        for source in additional_sources or []:
            extra=PaperLibrary(self.settings).get(source["origin_id"])
            paper_sources.append({**extra,"chunks":extra["chunks"][:3]})
        if sum(len(p["chunks"]) for p in paper_sources)>12:
            raise ValueError("Select at most 12 passages across the compared studies. Reduce the main paper selection before adding studies.")
        max_reviewers={"quick":1,"standard":2,"deep":3}[body.depth]
        if len(paper_sources)>max_reviewers:
            raise ValueError("Choose Comparative or Extended investigation size to review multiple studies.")
        worker_count = len(paper_sources) if len(paper_sources)>1 else min(max_reviewers,len(chunks))
        if worker_count+1>self.settings.max_tool_calls:
            raise ValueError("This investigation exceeds the configured retrieval/verification tool budget. Choose a smaller size or adjust Settings.")
        request = {**body.model_dump(), "project_id": project_id}
        doc = {"run_id": "research-" + uuid4().hex, "workspace_id": "paper-review", "created_at": now(), "status": "queued", "request": request, "provider": "google" if self.settings.google_api_key else "openrouter", "model": self.settings.argon_model if self.settings.google_api_key else self.settings.openrouter_model, "data_mode": "original-language document passages", "storage_mode": self.settings.data_backend, "dataset_version": paper["sha256"], "source_manifest": [], "paper_sources": paper_sources, "events": [], "tasks": [], "artifacts": [], "findings": [], "budget": {"model_requests": 0, "tool_calls": 0, "spawned_tasks": 0, "cost_status": "unknown unless reported"}}
        doc["budget"].update(usage=[],max_model_requests=self.settings.max_model_requests,max_tool_calls=self.settings.max_tool_calls)
        self.event(doc, "queued", f"Selected original-language passages saved. Up to {worker_count} source reviewers queued; each Argon failure may add one OpenRouter attempt within the shared budget.")
        return self.store.create(doc)

    def cancel(self, rid):
        def change(d):
            if d["status"] not in TERMINAL:
                d["status"] = "cancelled"
                for t in d.get("tasks",[]):
                    if t["status"] in ("running","queued"):t["status"]="cancelled"
                self.event(d, "cancelled", "Researcher cancelled the document review; no finding is accepted after cancellation.")
            return d
        return self.store.mutate(rid, change)

    def recover(self):
        for d in self.store.list():
            if d["status"] not in TERMINAL:
                def change(run):
                    run["status"] = "interrupted"
                    for task in run.get("tasks",[]):
                        if task["status"] in ("running","queued"):task["status"]="interrupted"
                    return self.event(run, "interrupted", "The local review process stopped. Original inputs remain saved; start a separate review to retry.")
                self.store.mutate(d["run_id"], change)

    async def execute(self, rid):
        doc=self.store.get(rid)
        if not doc or doc["status"] in TERMINAL:return
        request=doc["request"]
        max_workers={"quick":1,"standard":2,"deep":3}[request.get("depth","quick")]
        jobs=[]
        for paper in doc["paper_sources"]:
            jobs.append((paper,[c["id"] for c in paper["chunks"]]))
        if len(jobs)==1 and len(jobs[0][1])>1 and max_workers>1:
            paper,ids=jobs[0]
            jobs=[(paper,ids[i::max_workers]) for i in range(min(max_workers,len(ids)))]
        def begin(d):
            if d["status"] in TERMINAL:return d
            d["status"]="running"
            d["budget"]["tool_calls"]=1
            d["tasks"]=[{"id":"retriever","role":"evidence retrieval","status":"completed","engine":"deterministic","question":"Freeze selected source passages","parent_task_id":None,"allowed_tools":[],"input_artifact_ids":[]},*[{"id":"reviewer-"+str(i),"role":"source reviewer","status":"queued","engine":"language model","question":p["filename"],"parent_task_id":"retriever","allowed_tools":["read_paper"],"input_artifact_ids":[]} for i,(p,_) in enumerate(jobs)],{"id":"quote-verifier","role":"quotation verifier","status":"queued","engine":"deterministic","question":"Check exact quotations and source identities","parent_task_id":"retriever","allowed_tools":[],"input_artifact_ids":[]}]
            return self.event(d,"retrieval.completed",str(sum(len(ids) for _,ids in jobs))+" explicitly selected passages frozen across "+str(len(d["paper_sources"]))+" studies. No new assay measurements are produced.")
        if self.store.mutate(rid,begin)["status"] in TERMINAL:return
        deadline=asyncio.get_running_loop().time()+min(request.get("max_seconds",120),self.settings.max_run_seconds)
        semaphore=asyncio.Semaphore(self.settings.max_concurrent_workers)
        def reserve(_=None):
            def count(d):
                if d["status"] in TERMINAL:raise asyncio.CancelledError()
                if d["budget"]["model_requests"]>=d["budget"]["max_model_requests"]:raise RuntimeError("Model request budget exhausted.")
                d["budget"]["model_requests"]+=1
                return d
            self.store.mutate(rid,count)
        def attempt(usage):
            def save(d):
                d["budget"]["usage"].append(usage)
                return d
            self.store.mutate(rid,save)
        async def review(index,paper,ids):
            tid="reviewer-"+str(index)
            async with semaphore:
                reserve()
                def running(d):
                    next(t for t in d["tasks"] if t["id"]==tid)["status"]="running"
                    return self.event(d,"reviewer.started","Source reviewer "+str(index+1)+" is reading "+str(len(ids))+" passages from "+paper["filename"]+".")
                self.store.mutate(rid,running)
                def fallback(failed):
                    reserve()
                    self.store.mutate(rid,lambda d:self.event(d,"model.fallback","Source reviewer "+str(index+1)+" switched from Argon to OpenRouter after "+failed["failure_type"]+"."))
                result=await PaperLibrary(self.settings).read(paper["id"],PaperRead(question=request["question"],language=request["language"],chunk_ids=ids),before_fallback=fallback,on_attempt=attempt)
                def finished(d):
                    if d["status"] in TERMINAL:return d
                    next(t for t in d["tasks"] if t["id"]==tid)["status"]="completed"
                    d["budget"]["usage"].append(result["provider"])
                    d["budget"]["tool_calls"]+=1
                    return self.event(d,"reviewer.completed","Source reviewer "+str(index+1)+" saved source-linked observations; exact original quotes passed their checks.")
                self.store.mutate(rid,finished)
                return result
        tasks=[asyncio.create_task(review(i,p,ids)) for i,(p,ids) in enumerate(jobs)]
        aggregate=asyncio.gather(*tasks)
        try:
            while not aggregate.done():
                await asyncio.wait({aggregate},timeout=.2)
                if self.store.get(rid)["status"]=="cancelled":
                    aggregate.cancel();await asyncio.gather(aggregate,return_exceptions=True);return
                if asyncio.get_running_loop().time()>=deadline:raise TimeoutError("The selected document investigation time limit was reached.")
            results=await aggregate
            def finish(d):
                if d["status"] in TERMINAL:return d
                d["reading"]=results[0]
                d["readings"]=results
                d["findings"]=[];d["artifacts"]=[];coverage={}
                for result in results:
                    coverage.setdefault(result["paper_id"],set()).update(result["covered_chunk_ids"])
                    d["artifacts"].append({"id":"reading-"+result["id"],"task_id":"quote-verifier","kind":"verified_original_quotes","data":{"covered_chunk_ids":result["covered_chunk_ids"],"total_chunks":result["total_chunks"],"source_version":result["source_version"],"outcome":"Exact original-language quotes checked; scientific interpretation remains unreviewed."}})
                    for c in result["reading"]["claims"]:
                        d["findings"].append({"id":"claim-"+str(len(d["findings"])),"text":c["text"],"claim_type":"reported observation","evidence_refs":[result["paper_id"]+"#"+c["chunk_id"]],"variant_ids":[],"limitations":result["reading"]["limitations"],"reviewer_status":"unreviewed"})
                d["source_coverage"]=[{"paper_id":p["id"],"title":p["filename"],"covered_chunk_ids":sorted(coverage.get(p["id"],set())),"selected_chunks":len(p["chunks"])} for p in d["paper_sources"]]
                d["comparison_summary"]={"studies":len(d["paper_sources"]),"reviewers":len(results),"verified_quotations":len(d["findings"]),"method":"Parallel source reading and exact-text verification; no statistical meta-analysis or newly trained model."}
                next(t for t in d["tasks"] if t["id"]=="quote-verifier")["status"]="completed"
                usage=results[-1]["provider"];d["provider_usage"]=usage
                d["requested_provider"],d["requested_model"]=d["provider"],d["model"]
                d["provider"],d["model"]=usage.get("provider",d["provider"]),usage.get("model",d["model"])
                d["status"]="completed_with_limitations" if d["findings"] else "abstained"
                return self.event(d,"review_saved","Review complete: "+str(len(d["findings"]))+" source-linked observations. Review the reported outcomes, coverage and uncertainties before drawing a conclusion.")
            self.store.mutate(rid,finish)
        except asyncio.CancelledError:
            aggregate.cancel();await asyncio.gather(aggregate,return_exceptions=True);raise
        except Exception as exc:
            aggregate.cancel();await asyncio.gather(aggregate,return_exceptions=True)
            def fail(d):
                if d["status"] in TERMINAL:return d
                d["status"]="failed"
                for t in d["tasks"]:
                    if t["status"] in ("running","queued"):t["status"]="failed"
                d["error"]="Document investigation failed ("+type(exc).__name__+"). Saved source evidence is retained; no unchecked result was accepted."
                return self.event(d,"failed",d["error"])
            self.store.mutate(rid,fail)
