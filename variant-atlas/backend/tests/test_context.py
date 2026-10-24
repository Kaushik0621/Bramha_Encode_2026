from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.repositories.research import ResearchStore
from app.science import ScientificData


def test_context_grounded_alternatives_history_and_stale_refusal(tmp_path):
    settings = Settings(local_data_dir=tmp_path, worker_mode="external")
    data = ScientificData()
    w = data.workspace()
    store = ResearchStore(settings)
    store.seed(w)
    store.create(
        {
            "run_id": "research-" + "c" * 32,
            "request": {
                "selected_ids": ["PTEN:p.C124S"],
                "question": "Previous assay comparison.",
            },
            "status": "abstained",
            "created_at": "2026-10-24T10:00:00Z",
            "dataset_version": w["dataset_version"],
            "findings": [],
        }
    )
    with TestClient(create_app(settings)) as client:
        body = {
            "dataset_version": w["dataset_version"],
            "anchor_id": "PTEN:p.C124S",
            "selected_ids": [],
            "criteria": {
                k: w["defaults"][k] for k in ("activity_cutoff", "abundance_cutoff")
            },
            "layer": "activity",
            "use_model": False,
        }
        r = client.post("/api/research/context", json=body)
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["anchor"]["id"] == "PTEN:p.C124S"
        assert result["proposal"]["planner"]["provider"] == "deterministic"
        assert any(
            a["same_position"] and a["variant"]["id"] == "PTEN:p.C124A"
            for a in result["alternatives"]
        )
        assert result["history"][0]["status"] == "abstained"
        assert result["history"][0]["findings"] == []
        for a in result["alternatives"]:
            v = a["variant"]
            assert a["assay_ready"] == (
                v["activity"] is not None and v["abundance"] is not None
            )
            assert a["geometry_ready"] == (v["mapping"]["status"] == "mapped")
        body["dataset_version"] = "old"
        assert client.post("/api/research/context", json=body).status_code == 409
