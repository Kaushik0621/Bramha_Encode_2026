import asyncio
import json

import pytest

from app.config import Settings
from app.science import ScientificData
from app.scenarios import ScenarioService, SuggestRequest, ApplyRequest
from app.research_schemas import AgentAction


@pytest.fixture
def lab(tmp_path):
    return ScenarioService(ScientificData(), Settings(local_data_dir=tmp_path))


def context(lab, ids=None, **kwargs):
    w = lab.data.workspace()
    return SuggestRequest(
        dataset_version=w["dataset_version"],
        selected_ids=ids or [],
        anchor_id="PTEN:p.C124S",
        criteria={
            "activity_cutoff": w["defaults"]["activity_cutoff"],
            "abundance_cutoff": w["defaults"]["abundance_cutoff"],
        },
        **kwargs
    )


def apply(lab, ctx, proposal, key):
    return lab.execute(
        ApplyRequest(
            **ctx.model_dump(exclude={"use_model"}),
            proposal_id=proposal["id"],
            candidate_id=key
        )
    )


def test_same_residue_comparison_has_real_scores_and_no_mutant_distance(lab):
    ctx = context(lab)
    proposal = asyncio.run(lab.suggest(ctx))
    result = apply(lab, ctx, proposal, "same-position")
    assert result["after"]["count"] == 2
    assert result["distance"]["same_residue"] is True
    assert result["distance"]["distance"] == 0
    for row in result["measurements"]:
        assert row == lab.data.variant(row["id"])
    assert result["before"]["count"] == 0
    assert json.loads((lab.root / (result["id"] + ".json")).read_text()) == result


def test_remove_unmapped_preserves_source_and_reports_coverage(lab):
    w = lab.data.workspace()
    mapped = next(v["id"] for v in w["variants"] if v["mapping"]["status"] == "mapped")
    unmapped = next(
        v["id"] for v in w["variants"] if v["mapping"]["status"] != "mapped"
    )
    ctx = context(lab, [mapped, unmapped])
    result = apply(lab, ctx, asyncio.run(lab.suggest(ctx)), "remove-unmapped")
    assert result["after_ids"] == [mapped]
    assert result["plan"]["removed_ids"] == [unmapped]
    assert result["before"]["mapped"] == result["after"]["mapped"] == 1
    assert lab.data.variant(unmapped)["id"] == unmapped


def test_stale_context_unknown_ids_and_forged_actions_are_rejected(lab):
    ctx = context(lab)
    proposal = asyncio.run(lab.suggest(ctx))
    changed = ctx.model_copy(update={"layer": "abundance"})
    with pytest.raises(ValueError, match="changed"):
        apply(lab, changed, proposal, "same-position")
    with pytest.raises(ValueError, match="applicable"):
        apply(lab, ctx, proposal, "invent-a-cure")
    with pytest.raises(ValueError, match="Unknown"):
        lab.catalog(ctx.model_copy(update={"selected_ids": ["PTEN:p.fake"]}))
    with pytest.raises(ValueError, match="Dataset changed"):
        lab.catalog(ctx.model_copy(update={"dataset_version": "old"}))


def test_assay_contrast_is_independent_measurements_across_boundary(lab):
    ctx = context(lab)
    result = apply(lab, ctx, asyncio.run(lab.suggest(ctx)), "assay-contrast")
    a, b = result["measurements"]
    assert a["activity"] <= ctx.criteria.activity_cutoff
    assert b["activity"] <= ctx.criteria.activity_cutoff
    assert a["abundance"] >= ctx.criteria.abundance_cutoff > b["abundance"]
    assert result["after"]["criteria_matches"] == 1
    assert len(result["limitations"]) >= 3


def test_model_can_rank_only_known_plans_and_failure_is_explicit(lab):
    closed = []

    class Provider:
        def __init__(self, *args):
            pass

        async def close(self):
            closed.append(True)

        async def generate_action(self, prompt):
            candidates = json.loads(prompt)["candidates"]
            return AgentAction(
                action="invoke_tool",
                tool="rank_scenarios",
                summary="Prioritize a measured contrast.",
                arguments={"candidate_ids": [c["id"] for c in candidates][::-1]},
            ), {"provider": "test", "model": "scripted"}

    ctx = context(lab, use_model=True)
    result = asyncio.run(lab.suggest(ctx, Provider))
    assert result["planner"]["model"] == "scripted"
    assert result["candidates"][0]["id"] == lab.catalog(ctx)[-1]["id"]

    class Bad(Provider):
        async def generate_action(self, prompt):
            return (
                AgentAction(
                    action="invoke_tool",
                    tool="rank_scenarios",
                    summary="Invalid plan.",
                    arguments={"candidate_ids": ["invent-a-cure"]},
                ),
                {},
            )

    with pytest.raises(ValueError, match="invalid bounded"):
        asyncio.run(lab.suggest(ctx, Bad))
    assert len(closed) == 2
