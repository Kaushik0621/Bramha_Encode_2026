"""Opt-in live-provider check; never run in the credential-free automated suite."""
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Settings, ROOT
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.orchestration.engine import ResearchEngine
from app.research_schemas import ResearchRequest


async def main():
    settings = replace(
        Settings.from_env(),
        local_data_dir=ROOT / "var/exploration-live-proof",
        worker_mode="external",
    )
    data = ScientificData()
    store = ResearchStore(settings)
    store.seed(data.workspace())
    engine = ResearchEngine(store, data, settings)
    w = data.workspace()
    request = ResearchRequest(
        question="Rank up to ten distinct PTEN research scenarios for the selected substitutions. Choose informative paths, delegate assay and structural evidence reviews, and change direction when limitations warrant it. Record actual tools, outcomes and unvisited paths. Do not infer a cure or mutant fold.",
        selected_ids=["PTEN:p.C124S", "PTEN:p.C124A", "PTEN:p.G129E", "PTEN:p.R130Q"],
        criteria={
            k: w["defaults"][k]
            for k in ("scenario", "activity_cutoff", "abundance_cutoff")
        },
        provider="configured",
        explore_paths=True,
        max_seconds=240,
    )
    run = engine.start(request)
    rid = run["run_id"]
    job = asyncio.create_task(engine.execute(rid))
    last = 0
    while not job.done():
        snapshot = store.get(rid)
        for event in snapshot["events"][last:]:
            if event["type"] in (
                "path.planned",
                "path.updated",
                "tool.started",
                "tool.completed",
                "handoff",
                "run.abstained",
                "run.completed_with_limitations",
                "run.failed",
            ):
                print(
                    json.dumps(
                        {
                            k: event.get(k)
                            for k in (
                                "sequence",
                                "type",
                                "task_id",
                                "path_id",
                                "summary",
                            )
                        }
                    ),
                    flush=True,
                )
        last = len(snapshot["events"])
        await asyncio.sleep(0.5)
    await job
    result = store.get(rid)
    (ROOT / "artifacts/RESEARCH_EXPLORATION_LIVE.json").write_text(
        json.dumps(result, indent=2)
    )
    print(
        json.dumps(
            {
                "run_id": rid,
                "status": result["status"],
                "paths": [(p["id"], p["status"]) for p in result.get("paths", [])],
                "agents": len(result["tasks"]),
                "tools": result["budget"]["tool_calls"],
                "requests": result["budget"]["model_requests"],
            }
        ),
        flush=True,
    )


asyncio.run(main())
