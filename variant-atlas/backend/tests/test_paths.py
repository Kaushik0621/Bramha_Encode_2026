import asyncio
import json
import pytest
from app.config import Settings
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.orchestration.engine import ResearchEngine
from app.orchestration.paths import add_paths, update_path
from app.research_schemas import ResearchRequest, AgentAction
from app.tools.registry import Registry, NAMES


def proposal(key="activity"):
    return {
        "id": key,
        "title": "Inspect " + key + " measurements",
        "question": "What do the actual measurements support?",
        "rationale": "Read the pinned observations before proposing a research direction.",
        "expected_tools": ["inspect_assay"],
    }


def state():
    return {
        "tasks": [{"id": "coordinator", "allowed_tools": NAMES}],
        "artifacts": [],
        "paths": [],
    }


def test_ten_ranked_paths_without_pretending_they_are_explored():
    s = state()
    add_paths(
        s, "coordinator", {"paths": [proposal("path-" + str(i)) for i in range(10)]}
    )
    assert len(s["paths"]) == 10
    assert all(p["status"] == "proposed" and not p["history"] for p in s["paths"])
    with pytest.raises(ValueError, match="ten unique"):
        add_paths(s, "coordinator", {"paths": [proposal("extra")]})


def test_switch_has_evidence_outcome_and_cannot_forge_completion():
    s = state()
    add_paths(s, "coordinator", {"paths": [proposal(), proposal("structure")]})
    update_path(
        s,
        "coordinator",
        {
            "path_id": "activity",
            "status": "exploring",
            "reason": "Read the activity assay first.",
        },
    )
    assert s["tasks"][0]["path_id"] == "activity"
    with pytest.raises(ValueError, match="successful tool"):
        update_path(
            s,
            "coordinator",
            {
                "path_id": "activity",
                "status": "completed",
                "reason": "The observation is now established.",
            },
        )
    s["artifacts"] = [{"id": "evidence", "data": {"outcome": "ok"}}]
    update_path(
        s,
        "coordinator",
        {
            "path_id": "activity",
            "status": "inconclusive",
            "reason": "Assay limitations require checking geometry next.",
            "evidence_refs": ["evidence"],
            "next_path_id": "structure",
        },
    )
    assert s["tasks"][0]["path_id"] == "structure"
    assert s["paths"][0]["status"] == "inconclusive"
    assert s["paths"][1]["status"] == "exploring"
    assert s["paths"][0]["history"][-1]["evidence_refs"] == ["evidence"]
    update_path(
        s,
        "coordinator",
        {
            "path_id": "structure",
            "status": "completed",
            "reason": "Reference mapping read; no mutant fold is inferred.",
            "evidence_refs": ["evidence"],
        },
    )
    with pytest.raises(ValueError, match="immutable"):
        update_path(
            s,
            "coordinator",
            {
                "path_id": "structure",
                "status": "exploring",
                "reason": "Try to rewrite a resolved path.",
            },
        )


def test_path_scope_and_parent_validation():
    s = state()
    s["tasks"].append({"id": "child", "allowed_tools": ["inspect_assay"]})
    with pytest.raises(ValueError, match="permissions"):
        add_paths(s, "child", {"paths": [{**proposal(), "expected_tools": ["shell"]}]})
    with pytest.raises(ValueError, match="Parent path"):
        add_paths(
            s, "coordinator", {"paths": [{**proposal(), "parent_path_id": "missing"}]}
        )
    add_paths(s, "coordinator", {"paths": [proposal()]})
    with pytest.raises(ValueError, match="unowned"):
        update_path(
            s,
            "child",
            {
                "path_id": "activity",
                "status": "exploring",
                "reason": "Cannot take ownership of another agent path.",
            },
        )


def test_discovery_reports_real_scoped_capabilities():
    data = ScientificData()
    w = data.workspace()
    run = {
        "dataset_version": w["dataset_version"],
        "request": {
            "selected_ids": ["PTEN:p.C124S"],
            "criteria": {
                k: w["defaults"][k] for k in ("activity_cutoff", "abundance_cutoff")
            },
        },
        "_allowed_tools": ["discover_tools", "inspect_assay"],
    }
    result = Registry(data).execute("discover_tools", {"query": "assay"}, run)
    assert result.outcome == "ok"
    assert {t["name"] for t in result.data["tools"]} == {"inspect_assay"}
    assert len(set(NAMES)) == 30


class PathProvider:
    """Explicit scripted integration provider; exercises actual engine state transitions."""

    def __init__(self, *args):
        pass

    async def close(self):
        pass

    async def generate_action(self, prompt, on_remote=None, **kwargs):
        c = json.loads(prompt.split(" Context: ", 1)[1])
        task = c["task"]
        paths = c["paths"]

        def action(name, arguments, summary):
            return AgentAction(action=name, arguments=arguments, summary=summary), {
                "provider": "scripted",
                "model": "path-test",
            }

        if not paths:
            return action(
                "plan_paths",
                {"paths": [proposal(), proposal("structure")]},
                "Consider assay and structural evidence as separate directions.",
            )
        if not task.get("path_id"):
            return action(
                "update_path",
                {
                    "path_id": "activity",
                    "status": "exploring",
                    "reason": "First establish the assay endpoint and limitations.",
                },
                "Begin with assay context.",
            )
        artifacts = c["artifacts"]
        if task["id"] == "coordinator" and not any(
            t["role"] == "assay" for t in c["tasks"]
        ):
            return action(
                "spawn_specialist",
                {
                    "role": "assay",
                    "question": "Inspect the activity endpoint and report limitations.",
                    "path_id": "activity",
                    "allowed_tools": ["inspect_assay"],
                    "max_steps": 3,
                },
                "Delegate an assay review on the active path.",
            )
        if task["id"] != "coordinator":
            if not any(
                a["kind"] == "inspect_assay" and a["task_id"] == task["id"]
                for a in artifacts
            ):
                a, u = action(
                    "invoke_tool",
                    {"assay_id": "activity"},
                    "Read the pinned activity assay.",
                )
                a.tool = "inspect_assay"
                return a, u
            return action(
                "abstain",
                {},
                "Assay checkpoint saved; causal interpretation remains unsupported.",
            )
        if any(
            t["status"] in ("running", "queued") and t["id"] != "coordinator"
            for t in c["tasks"]
        ):
            return action(
                "wait_for_tasks",
                {},
                "Wait for independent assay evidence before changing direction.",
            )
        evidence = next((a for a in artifacts if a["kind"] == "inspect_assay"), None)
        if task["path_id"] == "activity":
            return action(
                "update_path",
                {
                    "path_id": "activity",
                    "status": "inconclusive",
                    "reason": "Activity assay alone cannot establish a spatial mechanism.",
                    "evidence_refs": [evidence["id"]],
                    "next_path_id": "structure",
                },
                "Switch from assay evidence to the structural question.",
            )
        return action(
            "abstain",
            {},
            "Structural path remains unresolved; no mechanism is inferred.",
        )


def test_engine_persists_live_path_switches_and_scoped_tool_outputs(tmp_path):
    settings = Settings(
        local_data_dir=tmp_path,
        openrouter_api_key="test",
        openrouter_model="scripted",
        worker_mode="external",
    )
    data = ScientificData()
    store = ResearchStore(settings)
    store.seed(data.workspace())
    engine = ResearchEngine(store, data, settings, PathProvider)
    w = data.workspace()
    request = ResearchRequest(
        question="Compare actual assay evidence and reference mapping.",
        selected_ids=["PTEN:p.C124S"],
        criteria={k: w["defaults"][k] for k in ("activity_cutoff", "abundance_cutoff")},
        provider="openrouter",
        explore_paths=True,
    )
    run = engine.start(request)
    asyncio.run(engine.execute(run["run_id"]))
    saved = store.get(run["run_id"])
    assert saved["status"] == "abstained"
    assert saved["paths"][0]["status"] == "inconclusive"
    assert saved["paths"][1]["status"] == "exploring"
    child = next(t for t in saved["tasks"] if t["role"] == "assay")
    assert child["path_id"] == "activity"
    artifact = next(a for a in saved["artifacts"] if a["kind"] == "inspect_assay")
    assert artifact["path_id"] == "activity"
    assert any(e["type"] == "path.updated" for e in saved["events"])
    assert any(a["kind"] == "research_path_state" for a in saved["artifacts"])


def test_actual_tool_selection_routes_directions_and_enters_specialist_path():
    from app.orchestration.paths import route_tool

    s = state()
    add_paths(
        s,
        "coordinator",
        {
            "paths": [
                proposal(),
                {**proposal("structure"), "expected_tools": ["map_variant_residues"]},
            ]
        },
    )
    update_path(
        s,
        "coordinator",
        {
            "path_id": "activity",
            "status": "exploring",
            "reason": "Start by reviewing the assay context.",
        },
    )
    route_tool(s, "coordinator", "map_variant_residues")
    assert s["tasks"][0]["path_id"] == "structure"
    assert s["paths"][0]["status"] == "parked"
    assert s["paths"][1]["status"] == "exploring"
    s["paths"][0]["status"] = "proposed"
    s["tasks"].append(
        {
            "id": "assay-worker",
            "path_id": "activity",
            "allowed_tools": ["inspect_assay"],
        }
    )
    route_tool(s, "assay-worker", "inspect_assay")
    assert s["paths"][0]["status"] == "exploring"
    assert "began executing inspect_assay" in s["paths"][0]["history"][-1]["reason"]
