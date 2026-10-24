import copy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.explorations import ExplorationJournal, CreateExploration, UpdateExploration
from app.agent_catalog import catalog


@pytest.fixture
def journal(tmp_path):
    settings = Settings(local_data_dir=tmp_path, worker_mode="external")
    data = ScientificData()
    store = ResearchStore(settings)
    store.seed(data.workspace())
    return ExplorationJournal(store, data)


def state(journal):
    w = journal.data.workspace()
    return {
        "selected_id": "PTEN:p.C124S",
        "picked_ids": [],
        "focus_ids": [],
        "layer": "activity",
        "view": "protein",
        "criteria": {
            k: w["defaults"][k] for k in ("activity_cutoff", "abundance_cutoff")
        },
        "run_id": None,
    }


def test_visual_observations_are_durable_idempotent_and_keep_reference_fixed(journal):
    w = journal.data.workspace()
    doc = journal.create(
        CreateExploration(dataset_version=w["dataset_version"], state=state(journal))
    )
    after = state(journal)
    after["picked_ids"] = ["PTEN:p.C124S", "PTEN:p.C124A"]
    after["layer"] = "abundance"
    request = UpdateExploration(
        expected_revision=0, change_id=str(uuid4()), state=after
    )
    changed = journal.update(doc["id"], request)
    assert changed["revision"] == 1 and len(changed["events"]) == 2
    event = changed["events"][-1]
    assert set(event["added_ids"]) == set(after["picked_ids"])
    assert event["reference_geometry_changed"] is False
    assert (
        event["before"]["layer"] == "activity"
        and event["after"]["layer"] == "abundance"
    )
    for row in event["after_geometry"]:
        assert (
            row["coordinate"]
            == journal.data.variant(row["variant_id"])["mapping"]["coordinate"]
        )
    assert journal.update(doc["id"], request) == changed
    assert ExplorationJournal(journal.store, journal.data).get(doc["id"]) == changed
    exported = journal.export(doc["id"])
    assert len(exported["knowledge_documents"]) == 2
    assert exported["retrieval_status"]["embedding_status"] == "not_generated"
    assert exported["exploration"]["source_manifest"] == w["sources"]


def test_concurrent_stale_unknown_and_cross_dataset_records_refused(journal):
    w = journal.data.workspace()
    doc = journal.create(
        CreateExploration(dataset_version=w["dataset_version"], state=state(journal))
    )
    update = UpdateExploration(
        expected_revision=0, change_id=str(uuid4()), state=state(journal)
    )
    journal.update(doc["id"], update)
    with pytest.raises(ValueError, match="changed elsewhere"):
        journal.update(doc["id"], update.model_copy(update={"change_id": str(uuid4())}))
    bad = state(journal)
    bad["picked_ids"] = ["PTEN:p.FAKE"]
    with pytest.raises(ValueError, match="Unknown"):
        journal.create(
            CreateExploration(dataset_version=w["dataset_version"], state=bad)
        )
    with pytest.raises(ValueError, match="Dataset version"):
        journal.create(CreateExploration(dataset_version="old", state=state(journal)))
    with pytest.raises(ValueError, match="Invalid exploration"):
        journal.get("../../secrets")
    next_doc = journal.create(
        CreateExploration(
            dataset_version=w["dataset_version"],
            state=state(journal),
            previous_id=doc["id"],
        )
    )
    assert next_doc["previous_id"] == doc["id"]


def test_agent_catalog_reports_roles_and_actual_activity_without_inventing_agents(
    journal,
):
    data = catalog(journal.store.settings, [])
    assert len(data["agents"]) == 7
    assert data["tool_count"] == 30
    assert all(not a["active_tasks"] for a in data["agents"])
    roles = {a["id"] for a in data["agents"]}
    assert {"coordinator", "structure", "assay", "verifier"} <= roles
    running = {
        "run_id": "research-" + "d" * 32,
        "status": "running",
        "tasks": [
            {
                "id": "child",
                "role": "structure",
                "status": "running",
                "question": "Inspect accepted reference geometry.",
            }
        ],
    }
    active = catalog(journal.store.settings, [running])
    assert (
        next(a for a in active["agents"] if a["id"] == "structure")["active_tasks"][0][
            "task_id"
        ]
        == "child"
    )


def test_journal_api_restore_export_and_agent_page_data(journal):
    with TestClient(create_app(journal.store.settings)) as client:
        w = journal.data.workspace()
        doc = client.post(
            "/api/research/explorations",
            json={"dataset_version": w["dataset_version"], "state": state(journal)},
        ).json()
        assert (
            client.get("/api/research/explorations/" + doc["id"]).json()["state"][
                "selected_id"
            ]
            == "PTEN:p.C124S"
        )
        assert len(client.get("/api/research/explorations").json()) == 1
        r = client.get("/api/research/explorations/" + doc["id"] + "/export")
        assert r.status_code == 200 and r.json()["product"] == "Bramha Atlas"
        assert (
            client.get("/api/research/agents").json()["agents"][0]["id"]
            == "coordinator"
        )
        before = client.get("/api/research/explorations/" + doc["id"]).json()
        bad = copy.deepcopy(before["state"])
        bad["run_id"] = "research-" + "e" * 32
        result = client.post(
            "/api/research/explorations/" + doc["id"] + "/observations",
            json={"expected_revision": 0, "change_id": str(uuid4()), "state": bad},
        )
        assert result.status_code == 409
        assert client.get("/api/research/explorations/" + doc["id"]).json() == before


def test_requested_reviewer_is_a_finalization_gate(journal):
    import asyncio
    from test_research import ScriptedProvider, request
    from app.orchestration.engine import ResearchEngine

    settings = journal.store.settings
    settings.openrouter_api_key = "test"
    settings.openrouter_model = "scripted"
    engine = ResearchEngine(journal.store, journal.data, settings, ScriptedProvider)
    req = request(journal.data).model_copy(update={"requested_roles": ["verifier"]})
    run = engine.start(req)
    asyncio.run(engine.execute(run["run_id"]))
    saved = journal.store.get(run["run_id"])
    assert saved["status"] == "abstained"
    assert any(
        "verifier" in a["data"].get("missing_independent_reviews", [])
        for a in saved["artifacts"]
    )
