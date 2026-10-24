import asyncio
import json
from fastapi import APIRouter, HTTPException, Request, Query, WebSocket
from fastapi.responses import FileResponse, StreamingResponse, Response
from .research_schemas import (
    ResearchRequest,
    ResearchCriteria,
    ReviewRequest,
    VoiceCommand,
)
from .orchestration.engine import TERMINAL, now
from .tools.registry import Registry
from .scenarios import ScenarioService, SuggestRequest, ApplyRequest


def router(app, config):
    r = APIRouter(prefix="/api")

    def services():
        if getattr(app.state, "research_error", None):
            raise HTTPException(503, app.state.research_error)
        if not getattr(app.state, "research_store", None):
            raise HTTPException(503, "Real-data services not initialized.")
        return app.state.research_store, app.state.science, app.state.research_engine

    def run(rid):
        store, _, _ = services()
        doc = store.get(rid)
        if not doc:
            raise HTTPException(404, "Research investigation not found.")
        return doc

    @r.post("/research/context")
    async def research_context(body: SuggestRequest):
        store, data, _ = services()
        lab = ScenarioService(data, config)
        try:
            w = lab.validate(body)
            anchor = data.variant(body.anchor_id)
            proposal = await lab.suggest(body)
            results = data.preview(body.criteria)["results"]
            neighbors = data.neighbors(body.anchor_id, 10)
            neighbor_ids = {n["variant_id"] for n in neighbors.get("neighbors", [])}
            alternatives = sorted(
                (v for v in w["variants"] if v["id"] != body.anchor_id),
                key=lambda v: (
                    v["position"] != anchor["position"],
                    v["id"] not in neighbor_ids,
                    abs(v["position"] - anchor["position"]),
                    v["id"],
                ),
            )[:12]
            history = []
            for saved in store.list():
                if body.anchor_id not in saved.get("request", {}).get(
                    "selected_ids", []
                ):
                    continue
                history.append(
                    {
                        "run_id": saved["run_id"],
                        "question": saved["request"]["question"],
                        "status": saved["status"],
                        "dataset_version": saved["dataset_version"],
                        "findings": [
                            {"text": f["text"], "claim_type": f["claim_type"]}
                            for f in saved.get("findings", [])[:3]
                        ],
                    }
                )
                if len(history) >= 6:
                    break
            return {
                "anchor": anchor,
                "proposal": proposal,
                "neighbors": neighbors,
                "criterion": next(
                    r for r in results if r["variant_id"] == body.anchor_id
                ),
                "alternatives": [
                    {
                        "variant": v,
                        "same_position": v["position"] == anchor["position"],
                        "spatial_neighbor": v["id"] in neighbor_ids,
                        "assay_ready": v["activity"] is not None
                        and v["abundance"] is not None,
                        "geometry_ready": v["mapping"]["status"] == "mapped",
                    }
                    for v in alternatives
                ],
                "history": history,
                "dataset_version": w["dataset_version"],
            }
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                502, "Context research unavailable. No changes applied."
            ) from exc

    @r.post("/research/scenarios/suggest")
    async def suggest_scenarios(body: SuggestRequest):
        _, data, _ = services()
        try:
            return await ScenarioService(data, config).suggest(body)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                502,
                "Scenario planner unavailable. No changes applied; try data-derived plans.",
            ) from exc

    @r.post("/research/scenarios/apply")
    def apply_scenario(body: ApplyRequest):
        _, data, _ = services()
        try:
            return ScenarioService(data, config).execute(body)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @r.get("/capabilities")
    def capabilities():
        data_ready = not bool(getattr(app.state, "research_error", "not initialized"))
        return {
            "profile": config.app_profile,
            "data_mode": "real",
            "data_ready": data_ready,
            "data_error": getattr(app.state, "research_error", None),
            "storage": config.data_backend,
            "execution": "durable leased worker",
            "argon": {
                "configured": bool(config.google_api_key),
                "model": config.argon_model,
                "verified": False,
                "background": config.google_background,
                "thinking_level": config.google_thinking_level,
            },
            "openrouter": {
                "configured": bool(config.openrouter_api_key),
                "model": config.openrouter_model,
                "challenge_qualifying": False,
            },
            "retrieval": {
                "method": "atlas_hybrid_configured"
                if config.data_backend == "atlas"
                and config.embedding_provider != "disabled"
                else "local_lexical",
                "atlas_configured": bool(config.mongodb_uri),
                "hybrid_verified": False,
            },
            "voice": {
                "configured": bool(config.google_api_key and config.gemini_live_model),
                "live_verified": False,
                "text_commands": True,
            },
            "scientific_review": {"status": "pending", "clinical_use": False},
            "tools": Registry(app.state.science).contracts() if data_ready else [],
        }

    @r.get("/workspaces/{wid}")
    def workspace(wid: str):
        store, _, _ = services()
        if wid != "pten-real":
            raise HTTPException(404, "Unknown real workspace.")
        return store.workspace()

    @r.get("/workspaces/{wid}/data-audit")
    def audit(wid: str):
        _, data, _ = services()
        if wid != "pten-real":
            raise HTTPException(404, "Unknown real workspace.")
        return data.audit()

    @r.get("/workspaces/{wid}/identity-audit")
    def identity_audit(wid: str):
        _, data, _ = services()
        if wid != "pten-real":
            raise HTTPException(404, "Unknown real workspace.")
        path = data.directory / "pten-identity-audit.json"
        with path.open() as f:
            header = f.read(200)
        if data.workspace()["dataset_version"] not in header:
            raise HTTPException(
                409,
                "Audit snapshot differs from workspace; reacquire and seed consistently.",
            )
        return FileResponse(
            path, media_type="application/json", filename="pten-identity-audit.json"
        )

    @r.get("/structures/{sid}")
    def structure(sid: str):
        _, data, _ = services()
        if sid != "1D5R":
            raise HTTPException(404, "Structure is not in pinned workspace.")
        w = data.workspace()
        data.assets.read(w["structure_asset"])
        return FileResponse(
            data.assets.resolve(w["structure_asset"]["key"]),
            media_type="chemical/x-mmcif",
            filename="1D5R.cif",
        )

    @r.post("/analysis/preview")
    def preview(criteria: ResearchCriteria):
        _, data, _ = services()
        return data.preview(criteria)

    @r.get("/research/variants/{vid}")
    def variant(vid: str):
        _, data, _ = services()
        try:
            return data.variant(vid)
        except KeyError:
            raise HTTPException(404, "Unknown real variant.") from None

    @r.get("/research/variants/{vid}/neighbors")
    def neighbors(
        vid: str, radius: float = Query(10, gt=0, le=100, allow_inf_nan=False)
    ):
        _, data, _ = services()
        try:
            return data.neighbors(vid, radius)
        except KeyError:
            raise HTTPException(404, "Unknown real variant.") from None

    @r.post("/research/investigations", status_code=202)
    def start(request: ResearchRequest):
        _, _, engine = services()
        try:
            return engine.start(request)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from None

    @r.get("/research/investigations")
    def investigations():
        store, _, _ = services()
        return [
            {k: v for k, v in d.items() if k not in ["events", "artifacts"]}
            for d in store.list()
        ]

    @r.get("/research/investigations/{rid}")
    def snapshot(rid: str):
        return run(rid)

    @r.post("/research/investigations/{rid}/cancel")
    def cancel(rid: str):
        doc = run(rid)
        store, _, engine = services()
        if doc["status"] in TERMINAL:
            return doc
        if doc["status"] == "queued":
            return engine.event(
                rid,
                "run.cancelled",
                "coordinator",
                "Queued investigation cancelled before execution.",
                status="cancelled",
            )
        return store.mutate(rid, lambda d: dict(d, cancel_requested=True))

    @r.get("/investigations/{rid}/artifacts/{aid}")
    @r.get("/research/investigations/{rid}/artifacts/{aid}")
    def artifact(rid: str, aid: str):
        match = next((a for a in run(rid)["artifacts"] if a["id"] == aid), None)
        if match is None:
            raise HTTPException(404, "Artifact is not in this investigation.")
        return match

    @r.get("/research/investigations/{rid}/events")
    async def events(rid: str, request: Request, after: int = Query(0, ge=0)):
        run(rid)
        header = request.headers.get("last-event-id", "").rsplit(":", 1)[-1]
        if header and (
            not header.isdigit()
            or request.headers["last-event-id"].rsplit(":", 1)[0] != rid
        ):
            raise HTTPException(400, "Invalid Last-Event-ID for this run.")
        cursor = max(after, int(header) if header.isdigit() else 0)

        async def stream():
            nonlocal cursor
            idle = 0
            while not await request.is_disconnected():
                doc = run(rid)
                for event in doc["events"]:
                    if event["sequence"] > cursor:
                        cursor = event["sequence"]
                        yield "id: " + event[
                            "event_id"
                        ] + "\nevent: research\ndata: " + json.dumps(event) + "\n\n"
                if doc["status"] in TERMINAL:
                    return
                idle += 1
                if idle % 20 == 0:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @r.get("/research/investigations/{rid}/export")
    def export(rid: str):
        doc = run(rid)
        _, data, _ = services()
        w = data.workspace()
        return Response(
            json.dumps(
                {
                    "investigation": doc,
                    "source_manifest": doc.get(
                        "source_manifest", doc.get("source_versions", [])
                    ),
                    "assay_dictionary": doc.get(
                        "assay_dictionary",
                        w["assays"]
                        if w["dataset_version"] == doc["dataset_version"]
                        else [],
                    ),
                    "reproduce": "Run scripts/acquire_pten.py and scripts/seed_research.py; match source hashes and dataset version.",
                    "review_status": "pending unless separately recorded",
                },
                indent=2,
            ),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{rid}.json"'},
        )

    @r.post("/investigations/{rid}/reviews")
    @r.post("/research/investigations/{rid}/reviews")
    def review(rid: str, request: ReviewRequest):
        doc = run(rid)
        store, _, _ = services()
        if not set(request.finding_ids) <= {f["id"] for f in doc["findings"]}:
            raise HTTPException(422, "Review references an unknown finding.")
        from uuid import uuid4

        def change(d):
            d["reviews"].append(
                {
                    "id": "review-" + uuid4().hex,
                    **request.model_dump(),
                    "created_at": now(),
                    "identity_verified": False,
                }
            )
            for f in d["findings"]:
                if f["id"] in request.finding_ids:
                    f["reviewer_status"] = (
                        "accepted"
                        if request.decision == "accepted"
                        else "disputed"
                        if request.decision == "disputed"
                        else "pending"
                    )
            return d

        return store.mutate(rid, change)

    @r.post("/voice/session")
    def voice_session():
        if not config.google_api_key or not config.gemini_live_model:
            raise HTTPException(
                503,
                "Google Live credentials/model are unavailable. Use contextual text commands.",
            )
        return {
            "websocket_path": "/api/voice/stream",
            "model": config.gemini_live_model,
            "verified": False,
            "max_seconds": 180,
        }

    @r.websocket("/voice/stream")
    async def live(ws: WebSocket):
        from .providers.voice import bridge

        _, data, _ = services()
        await bridge(ws, config, data)

    @r.post("/voice/command")
    def command(request: VoiceCommand):
        _, data, _ = services()
        w = data.workspace()
        c = request.context
        if (
            c.dataset_version != w["dataset_version"]
            or c.mapping_version != w["dataset_version"]
        ):
            raise HTTPException(409, "Voice context is stale; refresh workspace.")
        try:
            for vid in c.selected_variant_ids:
                data.variant(vid)
        except KeyError:
            raise HTTPException(422, "Unknown selection.") from None
        allowed = {m["mapping_id"] for m in w["mappings"]}
        if not set(c.selected_residue_ids) <= allowed:
            raise HTTPException(422, "Unknown residue context.")
        if len(set(c.selected_variant_ids)) != len(c.selected_variant_ids):
            raise HTTPException(422, "Duplicate selected variant identities.")
        text = request.utterance.lower().strip()
        if text in ["show activity", "show abundance"]:
            return {
                "action": "set_layer",
                "layer": text.split()[-1],
                "context": c.model_dump(),
            }
        if "close" in text or "distance" in text:
            if len(c.selected_variant_ids) != 2:
                return {
                    "action": "clarify",
                    "message": "Select exactly two variants for an experimental C-alpha distance.",
                }
            return {
                "action": "distance",
                "artifact": data.distance(*c.selected_variant_ids),
                "context": c.model_dump(),
            }
        if "compare" in text and "assay" in text:
            return {
                "action": "show_evidence",
                "artifact": w["comparability"],
                "context": c.model_dump(),
            }
        if text == "focus these variants" and not c.selected_variant_ids:
            return {
                "action": "clarify",
                "message": "Select at least one variant to focus.",
            }
        if text == "focus these variants" and not any(
            data.variant(vid)["mapping"]["status"] == "mapped"
            for vid in c.selected_variant_ids
        ):
            return {
                "action": "clarify",
                "message": "None of the selected variants has accepted experimental coordinates; focus is unavailable.",
            }
        if text == "focus these variants":
            return {
                "action": "focus",
                "variant_ids": c.selected_variant_ids,
                "context": c.model_dump(),
            }
        return {
            "action": "clarify",
            "message": "Supported text commands: Show activity; Show abundance; Focus these variants; Are these positions close?; Compare these assays. Criteria changes require explicit form controls.",
        }

    return r
