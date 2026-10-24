"""Bounded research interventions: model chooses plans; pinned data determines results."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from .providers.actions import ActionProvider
from .repositories.local import LocalRepository
from .research_schemas import ResearchCriteria, AgentAction
from .schemas import Model


class ScenarioContext(Model):
    dataset_version: str
    selected_ids: list[str] = Field(default_factory=list, max_length=131)
    anchor_id: str
    criteria: ResearchCriteria
    layer: Literal["activity", "abundance"] = "activity"


class SuggestRequest(ScenarioContext):
    use_model: bool = False


class ApplyRequest(ScenarioContext):
    proposal_id: str
    candidate_id: str


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(context):
    payload = context.model_dump(include=set(ScenarioContext.model_fields))
    payload["selected_ids"] = sorted(set(payload["selected_ids"]))
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class ScenarioService:
    def __init__(self, data, settings):
        self.data, self.settings = data, settings
        self.root = settings.local_data_dir / "scenario-lab"
        self.root.mkdir(parents=True, exist_ok=True)

    def validate(self, context):
        w = self.data.workspace()
        if context.dataset_version != w["dataset_version"]:
            raise ValueError("Dataset changed. Request fresh suggestions.")
        ids = {v["id"] for v in w["variants"]}
        if len(context.selected_ids) != len(set(context.selected_ids)):
            raise ValueError("Duplicate cohort identifiers.")
        if not set(context.selected_ids) <= ids or context.anchor_id not in ids:
            raise ValueError("Unknown substitution in research context.")
        return w

    def catalog(self, context):
        w = self.validate(context)
        rows = {v["id"]: v for v in w["variants"]}
        before = context.selected_ids
        anchor = rows[context.anchor_id]
        out = []

        def add(key, title, why, after, focus, question, layer="activity"):
            after = list(dict.fromkeys(after))
            if after == before or not after:
                return
            out.append(
                dict(
                    id=key,
                    title=title,
                    rationale=why,
                    after_ids=after,
                    added_ids=[i for i in after if i not in before],
                    removed_ids=[i for i in before if i not in after],
                    focus_ids=focus,
                    layer=layer,
                    question=question,
                )
            )

        pairs = [
            v
            for v in rows.values()
            if v["position"] == anchor["position"] and v["id"] != anchor["id"]
        ]
        if not pairs:
            anchor = rows.get("PTEN:p.C124S", anchor)
            pairs = [
                v
                for v in rows.values()
                if v["position"] == anchor["position"] and v["id"] != anchor["id"]
            ]
        if pairs:
            other = sorted(pairs, key=lambda v: v["id"])[0]
            pair = [anchor["id"], other["id"]]
            add(
                "same-position",
                "Change the substitution, hold the position fixed",
                "Compare two separately measured substitutions at the same reference residue. Differences in the assays can motivate a substitution-specific hypothesis; a shared coordinate cannot explain their mechanism.",
                pair,
                pair,
                "Compare these independently measured substitutions at the same position. Report both assay values and uncertainties; explain why their shared reference coordinate is not mutant geometry.",
            )

        complete = [
            v
            for v in rows.values()
            if v["activity"] is not None and v["abundance"] is not None
        ]
        c = context.criteria
        discordant = [
            v
            for v in complete
            if v["activity"] <= c.activity_cutoff
            and v["abundance"] >= c.abundance_cutoff
        ]
        concordant = [
            v
            for v in complete
            if v["activity"] <= c.activity_cutoff
            and v["abundance"] < c.abundance_cutoff
        ]
        if discordant and concordant:
            # Match activity as closely as possible, without claiming confounding is controlled.
            a, b = min(
                ((a, b) for a in discordant for b in concordant),
                key=lambda p: (
                    abs(p[0]["activity"] - p[1]["activity"]),
                    p[0]["id"],
                    p[1]["id"],
                ),
            )
            pair = [a["id"], b["id"]]
            add(
                "assay-contrast",
                "Similar activity. Different abundance.",
                "Replace the cohort with an activity-matched contrast across the abundance boundary. This tests whether the research question should distinguish loss of activity from loss of measured abundance. Assays use different systems; this does not establish a mechanism.",
                pair,
                pair,
                "Compare the activity-matched contrast. Distinguish measured abundance from activity, retain assay system differences and uncertainty, and suggest an experiment rather than asserting a mechanism.",
                "abundance",
            )
        if discordant:
            candidate = next(
                (
                    v
                    for v in sorted(discordant, key=lambda v: (v["activity"], v["id"]))
                    if v["id"] not in before
                ),
                None,
            )
            if candidate:
                add(
                    "add-discordant",
                    "Add an informative discordant measurement",
                    "Expand the cohort with a measured low-activity, preserved-abundance substitution under the current exploratory cutoffs. It is a candidate for follow-up, not a clinical classification.",
                    before + [candidate["id"]],
                    [candidate["id"]],
                    "Evaluate the added low-activity, preserved-abundance substitution against the existing cohort. Explain what these separate measurements can and cannot establish.",
                )
        mapped = [i for i in before if rows[i]["mapping"]["status"] == "mapped"]
        if mapped and len(mapped) < len(before):
            add(
                "remove-unmapped",
                "Remove unsupported spatial claims",
                "Exclude substitutions without accepted experimental coordinates from this spatial cohort. Their assay evidence remains valid and available in the table. Report the coverage bias introduced by this exclusion.",
                mapped,
                mapped,
                "Analyze only the mapped spatial cohort. Explicitly account for the excluded unmapped assay evidence and coverage bias. Do not interpret exclusion as biological insignificance.",
            )
        spatial_anchor = rows[context.anchor_id]
        if spatial_anchor["mapping"]["status"] == "mapped":
            near = self.data.neighbors(spatial_anchor["id"], 10)
            neighbor = next(
                (
                    n
                    for n in near["neighbors"]
                    if not n["same_residue"] and n["variant_id"] not in before
                ),
                None,
            )
            if neighbor:
                pair = [spatial_anchor["id"], neighbor["variant_id"]]
                add(
                    "spatial-neighbor",
                    "Bring a reference-space neighbor into the comparison",
                    "Add a substitution at a different residue within the declared reference C-alpha radius. Proximity helps plan a spatial comparison; it does not prove interaction or a shared functional effect.",
                    list(dict.fromkeys(before + pair)),
                    pair,
                    "Compare the added reference-space neighbor with the anchor. Verify the C-alpha distance and independently compare assay measurements; do not infer a physical interaction.",
                )
        for plan in out:
            plan["observations"] = [
                {
                    "id": rows[i]["id"],
                    "activity": rows[i]["activity"],
                    "abundance": rows[i]["abundance"],
                    "mapping_status": rows[i]["mapping"]["status"],
                }
                for i in plan["focus_ids"]
            ]
        return out

    async def suggest(self, request, provider_factory=ActionProvider):
        candidates = self.catalog(request)
        planner = {
            "provider": "deterministic",
            "model": None,
            "status": "data-derived plans; no model invoked",
        }
        if request.use_model and candidates:
            provider_name = (
                "google"
                if self.settings.llm_provider in ("google", "gemini")
                else "openrouter"
            )
            provider = provider_factory(self.settings, provider_name)
            try:
                prompt = json.dumps(
                    {
                        "task": "Rank the supplied executable research plans by usefulness for this context. Return AgentAction action=invoke_tool, tool=rank_scenarios, arguments={candidate_ids:[all candidate IDs, best first]}, summary a short explanation. Do not supply measurements, new actions, or findings.",
                        "schema": AgentAction.model_json_schema(),
                        "context": request.model_dump(),
                        "candidates": candidates,
                    }
                )
                action, usage = await provider.generate_action(prompt)
                ordered = action.arguments.get("candidate_ids")
                expected = {c["id"] for c in candidates}
                if (
                    action.action != "invoke_tool"
                    or action.tool != "rank_scenarios"
                    or not isinstance(ordered, list)
                    or any(not isinstance(i, str) for i in ordered)
                    or len(ordered) != len(expected)
                    or set(ordered) != expected
                ):
                    raise ValueError(
                        "Model returned an invalid bounded research plan; no changes applied."
                    )
                candidates = sorted(candidates, key=lambda c: ordered.index(c["id"]))
                planner = {
                    **usage,
                    "status": "model ranked validated executable plans",
                    "summary": action.summary,
                }
            finally:
                await provider.close()
        doc = {
            "id": "scenario-" + uuid.uuid4().hex,
            "created_at": stamp(),
            "context": request.model_dump(include=set(ScenarioContext.model_fields)),
            "fingerprint": fingerprint(request),
            "candidates": candidates,
            "planner": planner,
        }
        LocalRepository.atomic_write(self.root / (doc["id"] + ".json"), doc)
        return doc

    def execute(self, request):
        self.validate(request)
        if not re.fullmatch(r"scenario-[a-f0-9]{32}", request.proposal_id):
            raise ValueError("Invalid proposal identifier.")
        path = self.root / (request.proposal_id + ".json")
        if not path.exists():
            raise ValueError("Proposal not found; request new suggestions.")
        doc = json.loads(path.read_text())
        if fingerprint(request) != doc["fingerprint"]:
            raise ValueError(
                "Selection, focus, layer or criteria changed. Refresh suggestions before applying."
            )
        # Rebuild all actions from authoritative data; client/model cannot inject edits.
        candidate = next(
            (c for c in self.catalog(request) if c["id"] == request.candidate_id), None
        )
        if candidate is None:
            raise ValueError("Plan no longer applicable.")
        w = self.data.workspace()
        rows = {v["id"]: v for v in w["variants"]}

        def summary(ids):
            values = [rows[i] for i in ids]
            return {
                "count": len(ids),
                "mapped": sum(v["mapping"]["status"] == "mapped" for v in values),
                "complete_assays": sum(
                    v["activity"] is not None and v["abundance"] is not None
                    for v in values
                ),
                "criteria_matches": self.data.preview(request.criteria, ids)[
                    "matching_count"
                ],
            }

        after = candidate["after_ids"]
        preview = self.data.preview(request.criteria, after)
        focus = candidate["focus_ids"]
        distance = self.data.distance(*focus) if len(focus) == 2 else None
        result = {
            "id": "execution-" + uuid.uuid4().hex,
            "created_at": stamp(),
            "proposal_id": doc["id"],
            "dataset_version": w["dataset_version"],
            "plan": candidate,
            "before_ids": request.selected_ids,
            "after_ids": after,
            "before": summary(request.selected_ids),
            "after": summary(after),
            "measurements": [rows[i] for i in after],
            "criteria_results": preview["results"],
            "distance": distance,
            "planner": doc["planner"],
            "checks": [
                {"name": "Identity and dataset version", "status": "passed"},
                {
                    "name": "Recomputed assay criteria from pinned measurements",
                    "status": "passed",
                },
                {
                    "name": "Reference coordinate coverage",
                    "status": "passed"
                    if all(rows[i]["mapping"]["status"] == "mapped" for i in focus)
                    else "limited",
                },
            ],
            "steps": [
                "Read pinned dataset and validate current context",
                "Rebuild permitted cohort change",
                "Recompute assay criteria and mapping coverage",
                "Measure reference distance where available",
                "Persist verified result and return scene command",
            ],
            "scene": {"variant_ids": focus, "layer": candidate["layer"]},
            "limitations": [
                "Independent single-substitution measurements; no combined mutant is simulated.",
                "Reference backbone remains unchanged. No mutant fold, rescue, pathogenicity or treatment effect is predicted.",
                "Matching thresholds are exploratory; excluded variants remain available in the source table.",
            ],
            "source_ids": [s["id"] for s in w["sources"]],
        }
        LocalRepository.atomic_write(self.root / (result["id"] + ".json"), result)
        return result
