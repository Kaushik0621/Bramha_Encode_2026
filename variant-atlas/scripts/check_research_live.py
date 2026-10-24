"""Opt-in bounded live provider run. Reads backend-only secrets; prints no credentials."""
import argparse, asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Settings, ROOT
from app.repositories.research import ResearchStore
from app.science import ScientificData
from app.research_schemas import ResearchCriteria, ResearchRequest
from app.orchestration.engine import ResearchEngine

p = argparse.ArgumentParser()
p.add_argument("--live", action="store_true")
p.add_argument("--provider", choices=["google", "openrouter"], default="openrouter")
a = p.parse_args()
if not a.live:
    p.error(
        "--live is required: this spends configured API credits within request/time ceilings; monetary cost may be unknown."
    )


async def main():
    s = Settings.from_env()
    store = ResearchStore(s)
    data = ScientificData(s.asset_root, store)
    w = data.workspace()
    criteria = ResearchCriteria(
        **{k: v for k, v in w["defaults"].items() if k in ResearchCriteria.model_fields}
    )
    matches = data.preview(criteria)["matching_ids"]
    unmapped = next(
        v["id"] for v in w["variants"] if v["mapping"]["status"] != "mapped"
    )
    ids = list(
        dict.fromkeys(
            [*matches[:2], "PTEN:p.C124S", "PTEN:p.G129E", "PTEN:p.R130Q", unmapped]
        )
    )
    req = ResearchRequest(
        question="Investigate preserved abundance with reduced activity among these PTEN substitutions. Delegate independent assay-context and structure reviews. Inspect identity, comparability, declared filtering and mapping. Record a revision when actual source or coordinate limitations narrow the plan, reconcile the branches, and finalize a brief with checked evidence. Stay within 20 model calls: use scoped workers with at most two tools each. Do not make causal or clinical claims.",
        criteria=criteria,
        selected_ids=ids,
        capacity=10,
        provider=a.provider,
        max_seconds=600,
    )
    e = ResearchEngine(store, data, s)
    r = e.start(req)
    store.claim(e.worker_id)
    print("Queued live real-data run " + r["run_id"], flush=True)
    try:
        await e.execute(r["run_id"])
    finally:
        store.close()
    r = ResearchStore(s).get(r["run_id"])
    summary = {
        "run_id": r["run_id"],
        "status": r["status"],
        "provider": r["provider"],
        "model": r["model"],
        "dataset_version": r["dataset_version"],
        "selected_ids": ids,
        "budget": r["budget"],
        "tasks": r["tasks"],
        "event_types": list(dict.fromkeys(ev["type"] for ev in r["events"])),
        "artifact_kinds": [x["kind"] for x in r["artifacts"]],
        "findings": r["findings"],
        "error": r.get("error"),
        "challenge_qualifying": a.provider == "google",
        "independent_researcher_review": "pending",
    }
    out = ROOT / "artifacts/RESEARCH_LIVE_CHECK.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "run_id",
                    "status",
                    "provider",
                    "model",
                    "error",
                    "event_types",
                ]
            },
            indent=2,
        ),
        flush=True,
    )


asyncio.run(main())
