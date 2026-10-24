import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from .schemas import ComparisonRequest, interpret
from ..orchestration.engine import TERMINAL


def router(app):
    r = APIRouter(prefix="/api/blood")

    def engine():
        e = getattr(app.state, "blood_engine", None)
        if e is None:
            raise HTTPException(
                503,
                getattr(app.state, "blood_error", None)
                or "Blood comparison services unavailable.",
            )
        return e

    def saved(rid):
        doc = engine().store.get(rid)
        if not doc or doc["workspace_id"] != "blood-group":
            raise HTTPException(404, "Blood comparison not found.")
        return doc

    @r.post("/interpret")
    def interpretation(body: ComparisonRequest):
        try:
            return interpret(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @r.get("/sources")
    def sources(
        q: str = "", system: str = "all", context: str = "all", study: str = "all"
    ):
        if (
            system not in ("all", "ABO", "RhD")
            or context not in ("all", "reference", "malaria")
            or len(q) > 500
        ):
            raise HTTPException(422, "Unsupported evidence filter.")
        e = engine()
        if study != "all" and study not in {s["id"] for s in e.sources}:
            raise HTTPException(422, "Unknown study filter.")
        return {
            "sources": e.search(q, system, context, study=study),
            "retrieval": "bounded lexical corpus of inspected sources",
            "vector_status": "not configured or verified for this module",
            "provider": "google"
            if e.settings.google_api_key
            else e.settings.llm_provider,
            "model": e.settings.argon_model
            if e.settings.google_api_key
            else e.settings.openrouter_model,
            "data_version": e.version,
        }

    @r.post("/investigations")
    def start(body: ComparisonRequest):
        try:
            return engine().start(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @r.get("/investigations")
    def history():
        return engine().store.list()

    @r.get("/investigations/{rid}")
    def snapshot(rid: str):
        return saved(rid)

    @r.post("/investigations/{rid}/cancel")
    def cancel(rid: str):
        doc = saved(rid)
        if doc["status"] in TERMINAL:
            return doc
        return engine().edit(rid, lambda d: dict(d, cancel_requested=True))

    @r.get("/investigations/{rid}/events")
    async def events(rid: str, request: Request, after: int = 0):
        saved(rid)

        async def stream():
            cursor = max(0, after)
            while not await request.is_disconnected():
                doc = saved(rid)
                for event in doc["events"]:
                    if event["sequence"] > cursor:
                        cursor = event["sequence"]
                        yield "id: " + str(
                            cursor
                        ) + "\nevent: research\ndata: " + json.dumps(event) + "\n\n"
                if doc["status"] in TERMINAL:
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @r.get("/investigations/{rid}/export")
    def export(rid: str):
        doc = saved(rid)

        def safe(text):
            return str(text).replace("<", "&lt;").replace(">", "&gt;")

        text = (
            "# Blood-group comparative investigation\n\n"
            + safe(doc["request"]["question"])
            + "\n\nStatus: "
            + doc["status"]
            + "\n\n"
            + safe(json.dumps(doc["interpretation"]))
            + "\n\n"
        )
        if doc.get("result"):
            for section in [
                "supported differences",
                "shared features",
                "unknown or unsupported distinctions",
                "additional evidence needed",
            ]:
                text += "## " + section.title() + "\n\n"
                for finding in doc["result"]["findings"]:
                    if finding["section"] == section:
                        text += (
                            "- "
                            + safe(finding["text"])
                            + "\n  Applicability: "
                            + safe(finding["applicability"])
                            + "\n  Sources: "
                            + ", ".join(finding["refs"])
                            + "\n"
                        )
            text += (
                "\n## Presenter summary\n\n"
                + safe(doc["result"]["presenter_summary"])
                + "\n"
            )
        else:
            text += (
                "No verified final comparison. Saved branch outputs and limitations remain in the JSON checkpoint.\n\n"
                + safe(doc.get("error", ""))
                + "\n"
            )
        text += "\n## Inspected source provenance\n\n"
        for s in doc["source_manifest"]:
            text += f"- [{safe(s['title'])}]({s['url']}) — {s['passage_id']}\n  {safe(s['design'])}; {safe(s['population'])}; endpoint: {safe(s['endpoint'])}; location: {safe(s['location'])}; retrieved {s['retrieved_at']}.\n  Passage ({s['passage_kind']}): {safe(s['passage'])}\n  Limitations: {safe('; '.join(s['limitations']))}\n"
            for stat in s.get("statistics", []):
                text += "  Study statistic: " + safe(json.dumps(stat)) + "\n"
        text += "\nEvidence-informed schematic — not a validated physical simulation. Reference example; participant genotype not measured. No diagnosis, genome or personal risk is inferred.\n"
        return Response(
            text,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{rid}.md"'},
        )

    return r
