"""Explicit live-provider check; consumes configured provider requests, never run by tests."""
import asyncio, json, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.config import Settings
from app.repositories.research import ResearchStore
from app.blood.engine import BloodEngine
from app.blood.schemas import ComparisonRequest


async def main():
    settings = Settings.from_env()
    store = ResearchStore(settings, workspace_id="blood-group")
    engine = BloodEngine(store, settings)
    run = engine.start(
        ComparisonRequest(
            question="Compare O positive and B negative in severe Plasmodium falciparum malaria. Investigate ABO and RhD separately, distinguish rosetting from invasion, reconcile contrasting evidence and retain unsupported distinctions.",
            max_seconds=240,
        )
    )
    print("LIVE_RUN", run["run_id"], flush=True)
    claimed = store.claim(engine.worker_id)
    if claimed["run_id"] != run["run_id"]:
        raise RuntimeError(
            "A different comparison was already queued; refusing to execute it."
        )
    await engine.execute(run["run_id"])
    doc = store.get(run["run_id"])
    (root / "artifacts/BLOOD_COMPARISON_LIVE.json").write_text(
        json.dumps(
            {
                k: doc.get(k)
                for k in [
                    "run_id",
                    "status",
                    "provider",
                    "model",
                    "interpretation",
                    "budget",
                    "tasks",
                    "result",
                    "error",
                    "visual",
                ]
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "run_id": doc["run_id"],
                "status": doc["status"],
                "requests": doc["budget"]["model_requests"],
                "tool_calls": doc["budget"]["tool_calls"],
                "tasks": [(t["role"], t["status"]) for t in doc["tasks"]],
                "error": doc.get("error"),
                "result_saved": bool(doc["result"]),
            }
        ),
        flush=True,
    )
    store.close()


asyncio.run(main())
