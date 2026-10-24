"""Validated public exploration plans. These record decisions, not hidden reasoning."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field
from ..schemas import Model


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class PathProposal(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    title: str = Field(min_length=5, max_length=140)
    question: str = Field(min_length=10, max_length=1200)
    rationale: str = Field(min_length=10, max_length=1000)
    expected_tools: list[str] = Field(min_length=1, max_length=12)
    parent_path_id: str | None = None


class PlanPaths(Model):
    paths: list[PathProposal] = Field(min_length=1, max_length=10)


class UpdatePath(Model):
    path_id: str
    status: Literal["exploring", "parked", "rejected", "completed", "inconclusive"]
    reason: str = Field(min_length=10, max_length=1200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    next_path_id: str | None = None


def add_paths(state, task_id, raw):
    plan = PlanPaths.model_validate(raw)
    task = next(t for t in state["tasks"] if t["id"] == task_id)
    paths = state.setdefault("paths", [])
    existing = {p["id"] for p in paths}
    new_ids = [p.id for p in plan.paths]
    if (
        len(paths) + len(new_ids) > 10
        or len(new_ids) != len(set(new_ids))
        or existing & set(new_ids)
    ):
        raise ValueError(
            "At most ten unique scenario paths per run; update existing paths instead."
        )
    # Parents must already exist: no cycles or forward references.
    for p in plan.paths:
        if not set(p.expected_tools) <= set(task["allowed_tools"]):
            raise ValueError("Path requests tools outside task permissions.")
        if p.parent_path_id and p.parent_path_id not in existing:
            raise ValueError("Parent path must already exist.")
    for p in plan.paths:
        paths.append(
            {
                **p.model_dump(),
                "owner_task_id": task_id,
                "status": "proposed",
                "rank": len(paths) + 1,
                "created_at": timestamp(),
                "history": [],
                "evidence_refs": [],
                "outcome": None,
            }
        )
    return state


def update_path(state, task_id, raw):
    change = UpdatePath.model_validate(raw)
    paths = state.get("paths", [])
    path = next((p for p in paths if p["id"] == change.path_id), None)
    if not path or (task_id != "coordinator" and path["owner_task_id"] != task_id):
        raise ValueError("Unknown or unowned path.")
    if path["status"] in ("completed", "rejected"):
        raise ValueError("Resolved paths are immutable; propose a new child direction.")
    available = {a["id"] for a in state["artifacts"]}
    if not set(change.evidence_refs) <= available:
        raise ValueError("Path references unknown artifacts.")
    if change.status == "completed" and not any(
        a["id"] in change.evidence_refs and a["data"].get("outcome") == "ok"
        for a in state["artifacts"]
    ):
        raise ValueError(
            "Completed paths require a successful tool artifact; completion is a model judgment, not scientific validation."
        )
    task = next(t for t in state["tasks"] if t["id"] == task_id)
    if change.next_path_id:
        nxt = next((p for p in paths if p["id"] == change.next_path_id), None)
        if (
            not nxt
            or nxt["status"] in ("completed", "rejected")
            or (task_id != "coordinator" and nxt["owner_task_id"] != task_id)
        ):
            raise ValueError("Next direction is unavailable or unowned.")
        if change.next_path_id == change.path_id or change.status == "exploring":
            raise ValueError(
                "Switching requires parking or resolving the current path first."
            )
    now = timestamp()
    if change.status == "exploring":
        for other in paths:
            if (
                other["id"] != path["id"]
                and other["owner_task_id"] == path["owner_task_id"]
                and other["status"] == "exploring"
            ):
                other["status"] = "parked"
                other["history"].append(
                    {
                        "at": now,
                        "status": "parked",
                        "reason": "Agent switched to " + path["id"],
                        "evidence_refs": [],
                    }
                )
        task["path_id"] = path["id"]
    elif task.get("path_id") == path["id"]:
        task["path_id"] = None
    path["status"] = change.status
    path["evidence_refs"] = list(
        dict.fromkeys(path["evidence_refs"] + change.evidence_refs)
    )
    path["history"].append(
        {
            "at": now,
            "status": change.status,
            "reason": change.reason,
            "evidence_refs": change.evidence_refs,
        }
    )
    if change.status in ("completed", "inconclusive", "rejected"):
        path["outcome"] = change.reason
    if change.next_path_id:
        nxt["status"] = "exploring"
        nxt["history"].append(
            {
                "at": now,
                "status": "exploring",
                "reason": "Direction selected after " + path["id"],
                "evidence_refs": change.evidence_refs,
            }
        )
        task["path_id"] = nxt["id"]
    return state


def route_tool(state, task_id, tool):
    """Route the model's actual capability selection; never invent a research result."""
    task = next(t for t in state["tasks"] if t["id"] == task_id)
    paths = state.get("paths", [])
    active = next((p for p in paths if p["id"] == task.get("path_id")), None)
    if task_id == "coordinator" and active and tool not in active["expected_tools"]:
        target = next(
            (
                p
                for p in paths
                if p["status"] not in ("completed", "rejected")
                and tool in p["expected_tools"]
            ),
            None,
        )
        if target:
            refs = [
                a["id"]
                for a in state["artifacts"]
                if a.get("path_id") == active["id"] and a["data"].get("outcome") == "ok"
            ][-3:]
            update_path(
                state,
                task_id,
                {
                    "path_id": active["id"],
                    "status": "parked",
                    "reason": f'The brain selected {tool}; route this capability to the planned {target["title"]} direction.',
                    "evidence_refs": refs,
                    "next_path_id": target["id"],
                },
            )
            active = target
    if active and active["status"] in ("proposed", "parked"):
        active["status"] = "exploring"
        active["history"].append(
            {
                "at": timestamp(),
                "status": "exploring",
                "reason": f"Assigned agent {task_id} began executing {tool}. This is an execution-state transition, not a scientific conclusion.",
                "evidence_refs": [],
            }
        )
    return state
