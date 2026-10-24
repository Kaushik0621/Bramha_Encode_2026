import asyncio
import json
import math
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.science import ScientificData
from app.research_schemas import ResearchCriteria, ResearchRequest, AgentAction
from app.repositories.research import ResearchStore
from app.orchestration.engine import ResearchEngine
from app.tools.registry import Registry


@pytest.fixture
def data():
    return ScientificData()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        local_data_dir=tmp_path,
        openrouter_api_key="test-placeholder",
        openrouter_model="test-actions",
        worker_mode="external",
    )


@pytest.fixture
def store(settings, data):
    s = ResearchStore(settings)
    s.seed(data.workspace())
    return s


def request(data):
    w = data.workspace()
    return ResearchRequest(
        question="Compare activity and abundance while excluding unsupported spatial claims.",
        criteria=ResearchCriteria(
            **{
                k: v
                for k, v in w["defaults"].items()
                if k in ResearchCriteria.model_fields
            }
        ),
        selected_ids=[v["id"] for v in w["variants"][:5]],
        provider="openrouter",
        max_seconds=30,
    )


def test_real_identity_missing_and_geometry(data):
    w = data.workspace()
    assert w["data_mode"] == "real" and len(w["protein"]["sequence"]) == 403
    assert all(v["synthetic"] is False for v in w["variants"])
    mapped = [v for v in w["variants"] if v["mapping"]["status"] == "mapped"]
    unmapped = next(v for v in w["variants"] if v["mapping"]["status"] != "mapped")
    a = mapped[0]
    b = next(v for v in mapped if v["position"] != a["position"])
    expected = math.dist(
        [a["mapping"]["coordinate"][k] for k in "xyz"],
        [b["mapping"]["coordinate"][k] for k in "xyz"],
    )
    assert data.distance(a["id"], b["id"])["distance"] == pytest.approx(
        expected, abs=1e-6
    )
    assert data.distance(unmapped["id"], a["id"])["distance"] is None
    assert data.neighbors(unmapped["id"])["status"] == "mapping_failed"
    with pytest.raises(KeyError):
        data.variant("demo-v01")


def test_preview_matches_native_values(data):
    req = request(data)
    w = data.workspace()
    p = data.preview(req.criteria)
    expected = {
        v["id"]
        for v in w["variants"]
        if v["activity"] is not None
        and v["abundance"] is not None
        and v["activity"] <= req.criteria.activity_cutoff
        and v["abundance"] >= req.criteria.abundance_cutoff
    }
    assert set(p["matching_ids"]) == expected
    assert any(v["activity"] is not None and v["activity"] < 0 for v in w["variants"])
    assert len(expected) > 0


def test_registry_refuses_injection_and_fabricated_claims(data, store, settings):
    e = ResearchEngine(store, data, settings)
    r = e.start(request(data))
    reg = Registry(data)
    assert (
        reg.execute("filter_measurements", {"sql": "DROP TABLE"}, r).outcome
        == "invalid_input"
    )
    assert reg.execute("shell", {"command": "echo"}, r).outcome == "unsupported"
    bad = reg.execute(
        "validate_evidence_references",
        {
            "findings": [
                {
                    "id": "f",
                    "claim_type": "hypothesis",
                    "text": "Unknown support",
                    "evidence_refs": ["invented-source"],
                }
            ]
        },
        r,
    )
    assert not bad.data["passed"]
    r["artifacts"] = [{"id": "a", "data": {"distance": 3.0}}]
    assert not reg.execute(
        "validate_numeric_claims",
        {"numeric_claims": [{"artifact_id": "a", "path": ["distance"], "value": 4}]},
        r,
    ).data["passed"]
    assert reg.execute(
        "validate_numeric_claims",
        {"numeric_claims": [{"artifact_id": "a", "path": ["distance"], "value": 3}]},
        r,
    ).data["passed"]


def test_store_survives_reconstruction_and_lease(store, data, settings):
    r = ResearchEngine(store, data, settings).start(request(data))
    claimed = store.claim("a")
    assert claimed["run_id"] == r["run_id"]
    assert store.claim("b") is None
    assert ResearchStore(settings).get(r["run_id"])["status"] == "running"
    with pytest.raises(Exception):
        store.renew(r["run_id"], "b")


def test_real_api_context_export_and_cross_run_artifacts(settings, store, data):
    with TestClient(create_app(settings)) as client:
        w = client.get("/api/workspaces/pten-real").json()
        assert w["dataset_version"] == data.workspace()["dataset_version"]
        assert client.get("/api/structures/1D5R").text.startswith("data_1D5R")
        r = client.post("/api/investigations", json=request(data).model_dump()).json()
        assert (
            client.get("/api/investigations/" + r["run_id"]).json()["data_mode"]
            == "real"
        )
        assert (
            client.get("/api/investigations?workspace_id=pten-real").json()[0]["run_id"]
            == r["run_id"]
        )
        assert (
            client.get(
                f"/api/research/investigations/{r['run_id']}/artifacts/not-real"
            ).status_code
            == 404
        )
        exported = client.get(f"/api/research/investigations/{r['run_id']}/export").text
        assert "test-placeholder" not in exported and "source_manifest" in exported
        context = {
            "workspace_id": "pten-real",
            "dataset_version": "stale",
            "mapping_version": "stale",
            "selected_variant_ids": [],
        }
        assert (
            client.post(
                "/api/voice/command",
                json={"utterance": "show activity", "context": context},
            ).status_code
            == 409
        )
        assert client.post("/api/voice/session").status_code == 503
        assert (
            client.post(f"/api/research/investigations/{r['run_id']}/cancel").json()[
                "status"
            ]
            == "cancelled"
        )


class ScriptedProvider:
    """Explicit test fixture; not a demonstration of model intelligence."""

    def __init__(self, *args):
        self.counts = {}

    async def generate_action(self, prompt, on_remote=None):
        context = json.loads(prompt.split(" Context: ")[-1])
        tid = context["task"]["id"]
        i = self.counts.get(tid, 0)
        self.counts[tid] = i + 1
        if tid != "coordinator":
            await asyncio.sleep(0.05)
            action = {
                "action": "finalize",
                "summary": "Scoped test result; not a live model.",
                "findings": [],
            }
        else:
            tools = [
                "validate_variant_identity",
                "assess_comparability",
                "map_variant_residues",
                "filter_measurements",
            ]
            if i < 4:
                action = {
                    "action": "invoke_tool",
                    "tool": tools[i],
                    "summary": "Execute test check.",
                }
            elif i in [4, 5]:
                action = {
                    "action": "spawn_specialist",
                    "summary": "Independent fixture branch.",
                    "arguments": {
                        "role": "assay" if i == 4 else "structure",
                        "question": "Inspect declared scope with existing artifacts.",
                        "allowed_tools": ["inspect_assay"],
                        "input_artifact_ids": [],
                    },
                }
            elif i == 6:
                action = {
                    "action": "wait_for_tasks",
                    "summary": "Wait for test branches.",
                }
            elif i == 7:
                action = {
                    "action": "revise_hypothesis",
                    "summary": "Fixture revision to test persisted event.",
                }
            else:
                action = {
                    "action": "finalize",
                    "summary": "Fixture-only completed result.",
                    "findings": [
                        {
                            "id": "fixture-finding",
                            "claim_type": "hypothesis",
                            "text": "Fixture conclusion for orchestration testing only.",
                            "evidence_refs": [context["artifacts"][0]["id"]],
                        }
                    ],
                }
        return AgentAction.model_validate(action), {
            "provider": "fixture",
            "model": "scripted-test",
            "usage": {},
            "cost_usd": None,
        }

    async def close(self):
        pass


def test_durable_concurrent_action_loop_and_budget(data, settings, store):
    async def run():
        e = ResearchEngine(store, data, settings, ScriptedProvider)
        r = e.start(request(data))
        store.claim(e.worker_id)
        await e.execute(r["run_id"])
        return store.get(r["run_id"])

    r = asyncio.run(run())
    assert r["status"] == "completed_with_limitations"
    assert len(r["tasks"]) == 3 and r["budget"]["tool_calls"] == 4
    assert any(ev["type"] == "hypothesis.revised" for ev in r["events"])
    assert [ev["sequence"] for ev in r["events"]] == list(
        range(1, len(r["events"]) + 1)
    )
    assert any(a["kind"] == "verification" for a in r["artifacts"])
    assert r["budget"]["model_requests"] <= 20
    assert r["events"][0]["type"] == "task.queued"
    assert r["events"][-1]["type"] == "run.completed_with_limitations"


class DelayedProvider:
    def __init__(self, *args):
        pass

    async def generate_action(self, *args, **kwargs):
        await asyncio.sleep(10)

    async def close(self):
        pass


def test_cancel_stops_inflight_and_does_not_restart(data, settings, store):
    async def exercise():
        e = ResearchEngine(store, data, settings, DelayedProvider)
        r = e.start(request(data))
        store.claim(e.worker_id)
        task = asyncio.create_task(e.execute(r["run_id"]))
        await asyncio.sleep(0.3)
        store.mutate(r["run_id"], lambda d: dict(d, cancel_requested=True))
        await asyncio.wait_for(task, 2)
        await e.launch()
        await asyncio.sleep(0.6)
        await e.shutdown()
        return store.get(r["run_id"])

    r = asyncio.run(exercise())
    assert r["status"] == "cancelled"
    assert r["budget"]["model_requests"] == 1
    assert r["tasks"][0]["status"] == "cancelled"


def test_worker_crash_marks_interrupted_without_replaying(data, settings, store):
    e = ResearchEngine(store, data, settings, DelayedProvider)
    r = e.start(request(data))
    store.claim("dead-worker")
    store.mutate(r["run_id"], lambda d: dict(d, lease_until=0))

    async def exercise():
        await e.launch()
        await asyncio.sleep(0.1)
        await e.shutdown()

    asyncio.run(exercise())
    assert store.get(r["run_id"])["status"] == "interrupted"


def test_frozen_reference_and_distinct_heldout_contracts(data):
    from app.config import ROOT
    import hashlib

    for name in ["pten-reference-v1", "pten-heldout-v1"]:
        p = ROOT / "data/reference_cases" / f"{name}.json"
        assert (
            hashlib.sha256(p.read_bytes()).hexdigest()
            == p.with_suffix(".sha256").read_text().strip()
        )
    ref = json.loads((ROOT / "data/reference_cases/pten-reference-v1.json").read_text())
    assert (
        data.preview(ResearchCriteria(**ref["criteria"]))["matching_ids"]
        == ref["expected_matching_ids"]
    )
    held = json.loads((ROOT / "data/reference_cases/pten-heldout-v1.json").read_text())
    assert not {r["id"] for r in held["rows"]} & {
        v["id"] for v in data.workspace()["variants"]
    }


def test_hybrid_pipeline_pins_sources_without_claiming_live_execution(
    settings, store, data
):
    from app.retrieval.hybrid import HybridRetrieval

    h = HybridRetrieval(store, settings)
    assert h.readiness()["ready"] is False
    with pytest.raises(RuntimeError):
        h.search(data.workspace(), "assay differences")
    p = h.pipeline(data.workspace(), "assay differences", [0.1, 0.2], "activity")
    assert "$rankFusion" in p[0]
    pipelines = p[0]["$rankFusion"]["input"]["pipelines"]
    assert (
        "$search" in pipelines["lexical"][0]
        and "$vectorSearch" in pipelines["semantic"][0]
    )
    assert (
        pipelines["semantic"][0]["$vectorSearch"]["filter"]["dataset_version"]
        == data.workspace()["dataset_version"]
    )


def test_numeric_units_are_checked_against_explicit_artifact_metadata():
    from app.research_schemas import NumericClaim

    run = {
        "artifacts": [
            {
                "id": "distance-proof",
                "data": {
                    "outcome": "ok",
                    "data": {"distance": 3.25, "units": "angstrom"},
                },
            }
        ]
    }
    claim = {
        "artifact_id": "distance-proof",
        "path": ["data", "distance"],
        "value": 3.25,
    }
    assert not Registry.check_numbers([NumericClaim(**claim, units="millimeter")], run)[
        "passed"
    ]
    assert not Registry.check_numbers([NumericClaim(**claim)], run)["passed"]
    assert Registry.check_numbers([NumericClaim(**claim, units="angstrom")], run)[
        "passed"
    ]


def test_normalized_task_projection_keeps_coordinators_separate_across_runs():
    class Collection:
        def __init__(self):
            self.rows = []

        def replace_one(self, query, row, upsert=False):
            match = next(
                (
                    i
                    for i, old in enumerate(self.rows)
                    if all(old.get(k) == v for k, v in query.items())
                ),
                None,
            )
            if match is None:
                self.rows.append(row)
            else:
                self.rows[match] = row

        def update_one(self, *args, **kwargs):
            pass

    class Database:
        def __init__(self):
            self.collections = {}
            self.events = Collection()

        def __getitem__(self, name):
            return self.collections.setdefault(name, Collection())

    store = object.__new__(ResearchStore)
    store.db = Database()
    for rid in ["research-" + "a" * 32, "research-" + "b" * 32]:
        store._project(
            {
                "run_id": rid,
                "workspace_id": "pten-real",
                "tasks": [{"id": "coordinator", "role": "coordinator"}],
                "artifacts": [],
                "findings": [],
                "reviews": [],
                "events": [],
            }
        )
    assert len(store.db["tasks"].rows) == 2
    assert len({row["run_id"] for row in store.db["tasks"].rows}) == 2
