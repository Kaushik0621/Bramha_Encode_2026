import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.blood.engine import BloodEngine
from app.blood.schemas import ComparisonRequest, interpret, Finding
from app.repositories.research import ResearchStore
from app.research_schemas import AgentAction


def request(a="O+", b="B-", **extra):
    return ComparisonRequest(
        question="Compare these reported blood groups in severe falciparum malaria.",
        scenario_a=a,
        scenario_b=b,
        **extra
    )


@pytest.mark.parametrize(
    "a,b,abo,rhd",
    [
        ("O+", "B-", True, True),
        ("O+", "O-", False, True),
        ("B-", "B-", False, False),
        ("AB positive", "A positive", True, False),
    ],
)
def test_interpretation_separates_factors(a, b, abo, rhd):
    d = interpret(request(a, b))
    assert d["abo_differs"] == abo and d["rhd_differs"] == rhd
    assert d["a"]["provenance"] == "self-reported"
    assert "genotype" not in d["a"]


def test_text_parsing_and_unsupported_context():
    d = interpret(
        ComparisonRequest(
            question="Compare O positive and B negative in severe P. falciparum malaria."
        )
    )
    assert d["a"]["abo"] == "O" and d["b"]["rhd"] == "negative"
    with pytest.raises(ValueError, match="Unsupported scope"):
        interpret(request(context="dengue"))
    with pytest.raises(ValueError, match="conflict"):
        interpret(
            ComparisonRequest(
                question="Compare O+ and B- in malaria.",
                scenario_a="O+",
                scenario_b="O-",
            )
        )


class ScriptedProvider:
    def __init__(self, *args):
        pass

    async def close(self):
        pass

    async def generate_action(self, prompt):
        p = json.loads(prompt[prompt.index("{") :])
        if "task" in p:
            args = {
                "observations": [
                    {
                        "text": "The inspected evidence has population and assay applicability limits.",
                        "refs": ["rowe-2007#summary"],
                        "system": "ABO",
                        "domain": "uncertainty",
                        "applicability": "This is population evidence rather than an individual prediction.",
                    }
                ],
                "limitations": ["Self-reported phenotypes do not establish genotypes."],
                "next_retrieval": "Check population-specific contrasting evidence.",
            }
            tool = "blood_worker_report"
        else:
            complete = {t["role"] for t in p["tasks"] if t["status"] == "completed"}
            missing = {
                "scenario_a",
                "scenario_b",
                "mechanism",
                "applicability",
            } - complete
            if missing:
                args = {
                    "operation": "spawn",
                    "jobs": [
                        {
                            "role": r,
                            "question": "Inspect evidence applicability for this scoped comparison.",
                        }
                        for r in sorted(missing)
                    ],
                }
            elif "verifier" not in complete:
                args = {
                    "operation": "spawn",
                    "jobs": [
                        {
                            "role": "verifier",
                            "question": "Verify citations and reject unsupported RhD disease distinctions.",
                        }
                    ],
                }
            elif "reconciliation" not in complete:
                args = {
                    "operation": "spawn",
                    "jobs": [
                        {
                            "role": "reconciliation",
                            "question": "Reconcile the source-limited branch findings and uncertainties.",
                        }
                    ],
                }
            else:
                fs = []
                for section in [
                    "supported differences",
                    "shared features",
                    "unknown or unsupported distinctions",
                    "additional evidence needed",
                ]:
                    fs.append(
                        {
                            "section": section,
                            "text": "The current evidence supports reference biology but leaves disease attribution uncertain.",
                            "refs": ["abo-reference#summary"],
                            "system": "ABO",
                            "domain": "reference biology"
                            if p["interpretation"]["abo_differs"]
                            else "uncertainty",
                            "applicability": "This comparison requires source-specific interpretation.",
                        }
                    )
                args = {
                    "operation": "finalize",
                    "findings": fs,
                    "presenter_summary": "We reviewed reported phenotypes and population evidence, without measuring participants; important distinctions remain uncertain.",
                }
            tool = "blood_plan"
        return AgentAction(
            action="invoke_tool",
            tool=tool,
            arguments=args,
            summary="Scripted test action.",
        ), {"provider": "test", "model": "scripted", "cost_usd": 0}


def engine(tmp_path, **overrides):
    s = Settings(
        local_data_dir=tmp_path,
        llm_provider="openrouter",
        openrouter_api_key="test",
        openrouter_model="test",
        worker_mode="external",
        **overrides
    )
    return BloodEngine(
        ResearchStore(s, workspace_id="blood-group"), s, ScriptedProvider
    )


def execute(e, r):
    claimed = e.store.claim(e.worker_id)
    assert claimed["run_id"] == r["run_id"]
    asyncio.run(e.execute(r["run_id"]))
    return e.store.get(r["run_id"])


def test_real_handoffs_shared_retrieval_complete_and_isolated_store(tmp_path):
    e = engine(tmp_path)
    r = execute(e, e.start(request()))
    assert r["status"] == "completed_with_limitations", r.get("error")
    assert r["budget"]["spawned_tasks"] == 6
    assert r["budget"]["model_requests"] == 10
    assert r["budget"]["tool_calls"] == 1
    assert len([a for a in r["artifacts"] if a["kind"] == "read_shared_evidence"]) == 1
    assert len([x for x in r["events"] if x["type"] == "handoff"]) == 6
    assert (
        r["visual"]["rosetting_supported"]
        and not r["visual"]["different_behavior_supported"]
    )
    assert len(ResearchStore(e.settings).list()) == 0
    assert ResearchStore(e.settings).get(r["run_id"]) is None
    assert all(t["input_artifact_ids"] for t in r["tasks"] if t["id"] != "coordinator")
    assert ResearchStore(e.settings).claim("pten-worker") is None


def test_same_abo_has_no_forced_behavior_and_budget_stops(tmp_path):
    e = engine(tmp_path)
    r = execute(e, e.start(request("O+", "O-")))
    assert r["status"] == "completed_with_limitations"
    assert not r["visual"]["different_behavior_supported"]
    e2 = engine(tmp_path / "limited", max_model_requests=2)
    partial = execute(e2, e2.start(request()))
    assert partial["status"] == "abstained" and partial["result"] is None
    assert partial["budget"]["model_requests"] == 2


def test_reference_checks_reject_rhd_malaria_and_invented_numbers(tmp_path):
    e = engine(tmp_path)
    r = execute(e, e.start(request()))

    def f(**change):
        return Finding(
            section="supported differences",
            text="A source supports a biological distinction for this comparison.",
            refs=["rhd-reference#summary"],
            system="RhD",
            domain="malaria",
            applicability="Applies only to a literature comparison.",
            **change
        )

    with pytest.raises(ValueError, match="RhD malaria"):
        e.validate_observations([f()], r, True)
    bad = f().model_copy(
        update={
            "domain": "reference biology",
            "text": "A fabricated effect is 25 percent.",
        }
    )
    with pytest.raises(ValueError, match="qualitative"):
        e.validate_observations([bad], r, True)
    with pytest.raises(ValueError, match="unknown"):
        e.validate_observations([f().model_copy(update={"refs": ["fake"]})], r, True)


def test_provider_failure_never_becomes_comparison(tmp_path):
    e = engine(tmp_path)

    class Broken(ScriptedProvider):
        async def generate_action(self, *args):
            raise ConnectionError("Provider unavailable")

    e.factory = Broken
    r = execute(e, e.start(request()))
    assert (
        r["status"] == "failed"
        and r["result"] is None
        and not r["visual"]["rosetting_supported"]
    )


def test_api_text_contract_history_sources_and_markdown(tmp_path):
    settings = Settings(
        local_data_dir=tmp_path,
        worker_mode="external",
        llm_provider="openrouter",
        openrouter_api_key="test",
        openrouter_model="test",
    )
    from app.science import ScientificData

    ResearchStore(settings).seed(ScientificData().workspace())
    with TestClient(create_app(settings)) as c:
        assert c.post("/api/blood/interpret", json=request().model_dump()).json()[
            "abo_differs"
        ]
        assert (
            c.post(
                "/api/blood/interpret", json=request(context="unsupported").model_dump()
            ).status_code
            == 422
        )
        sources = c.get("/api/blood/sources?system=RhD&context=malaria").json()
        assert sources["sources"] == []
        assert len(c.get("/api/blood/sources?study=rowe-2007").json()["sources"]) == 1
        assert c.get("/api/blood/sources?study=unknown").status_code == 422
        doc = c.post("/api/blood/investigations", json=request().model_dump()).json()
        assert c.get("/api/blood/investigations").json()[0]["run_id"] == doc["run_id"]
        response = c.get("/api/blood/investigations/" + doc["run_id"] + "/export")
        assert (
            response.status_code == 200
            and "No verified final comparison" in response.text
        )
        assert "odds ratio" in response.text and "Malian children" in response.text
        assert c.get("/api/research/investigations").json() == []
        assert c.get("/api/research/investigations/" + doc["run_id"]).status_code == 404


def test_pooled_study_cannot_become_supported_pairwise_malaria_difference(tmp_path):
    e = engine(tmp_path)
    r = execute(e, e.start(request()))
    finding = Finding(
        section="supported differences",
        text="Group B has a greater severe malaria effect than group O.",
        refs=["rowe-2007#summary"],
        system="ABO",
        domain="malaria",
        applicability="An O versus pooled non-O association was observed.",
    )
    with pytest.raises(ValueError, match="pairwise malaria effect"):
        e.validate_observations([finding], r, True)
