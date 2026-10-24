"""Run separately with WORKER_MODE=external; durable queue survives HTTP disconnects."""
import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Settings
from app.repositories.research import ResearchStore
from app.science import ScientificData
from app.orchestration.engine import ResearchEngine


async def main():
    s = Settings.from_env()
    store = ResearchStore(s)
    data = ScientificData(s.asset_root, store)
    if s.data_backend == "atlas" and s.embedding_provider != "disabled":
        from app.retrieval.hybrid import HybridRetrieval

        data.retrieval = HybridRetrieval(store, s)
    engine = ResearchEngine(store, data, s)
    from app.blood.engine import BloodEngine

    blood_store = ResearchStore(s, workspace_id="blood-group")
    blood = BloodEngine(blood_store, s)
    try:
        data.workspace()
        await engine.launch()
        await blood.launch()
        await asyncio.gather(engine.loop, blood.loop)
    finally:
        await blood.shutdown()
        blood_store.close()
        await engine.shutdown()
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
