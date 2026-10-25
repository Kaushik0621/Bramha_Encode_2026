from typing import Literal
from pydantic import Field
from .schemas import Model


class ResearchCriteria(Model):
    scenario: Literal[
        "preserved_abundance_reduced_activity", "reduced_abundance_reduced_activity"
    ] = "preserved_abundance_reduced_activity"
    activity_cutoff: float = Field(default=-1.11, ge=-100, le=100, allow_inf_nan=False)
    abundance_cutoff: float = Field(ge=-100, le=100, allow_inf_nan=False)
    mapping: Literal["all", "mapped", "unmapped"] = "all"
    require_both_measurements: Literal[True] = True


class ResearchRequest(Model):
    project_id: str | None = Field(default=None, pattern=r"^project-[a-f0-9]{32}$")
    paper_ids: list[str] = Field(default_factory=list, max_length=3)
    workspace_id: Literal["pten-real"] = "pten-real"
    title: str = Field(
        default="PTEN evidence investigation", min_length=1, max_length=120
    )
    question: str = Field(min_length=10, max_length=1800)
    criteria: ResearchCriteria
    selected_ids: list[str] = Field(min_length=1, max_length=200)
    capacity: int = Field(default=10, ge=1, le=200, strict=True)
    provider: Literal["configured", "google", "openrouter", "fixture"] = "configured"
    requested_roles: list[
        Literal[
            "identity", "assay", "structure", "evidence", "verifier", "reconciliation"
        ]
    ] = Field(default_factory=list, max_length=6)
    explore_paths: bool = False
    neighbor_radius: float = Field(default=10,gt=0,le=100,allow_inf_nan=False)
    autonomous_team: bool = False  # Explicit UI opt-in; legacy API action loops retain their contract.
    require_independent_reviews: bool = True
    max_seconds: int = Field(default=600, ge=10, le=600)


class ToolResult(Model):
    tool: str
    outcome: Literal[
        "ok",
        "unsupported",
        "missing_data",
        "incompatible",
        "mapping_failed",
        "timeout",
        "source_unavailable",
        "invalid_input",
    ]
    summary: str
    data: dict = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Finding(Model):
    id: str
    claim_type: Literal[
        "reported_observation", "computed_result", "hypothesis", "unknown"
    ]
    text: str = Field(min_length=1, max_length=1800)
    variant_ids: list[str] = Field(default_factory=list, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=12)
    verifier_outcomes: dict = Field(default_factory=dict)
    reviewer_status: Literal["pending", "accepted", "disputed"] = "pending"


class NumericClaim(Model):
    artifact_id: str
    path: list[str] = Field(min_length=1, max_length=10)
    value: float = Field(allow_inf_nan=False)
    units: str | None = None


class AgentAction(Model):
    action: Literal[
        "plan_paths",
        "update_path",
        "inspect_state",
        "invoke_tool",
        "spawn_specialist",
        "wait_for_tasks",
        "request_reconciliation",
        "revise_hypothesis",
        "request_missing_information",
        "finalize",
        "abstain",
    ]
    summary: str = Field(
        min_length=1,
        max_length=500,
        description="Short public action summary, not private chain-of-thought.",
    )
    tool: str | None = None
    arguments: dict = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list, max_length=12)
    numeric_claims: list[NumericClaim] = Field(default_factory=list, max_length=20)


class SpawnRequest(Model):
    path_id: str | None = Field(default=None, max_length=48)
    role: Literal[
        "identity", "assay", "structure", "evidence", "verifier", "reconciliation"
    ]
    question: str = Field(min_length=10, max_length=1200)
    input_artifact_ids: list[str] = Field(default_factory=list, max_length=20)
    allowed_tools: list[str] = Field(default_factory=list, max_length=20)
    max_steps: int = Field(default=8, ge=1, le=12)
    max_seconds: int = Field(default=180, ge=5, le=180)


class ReviewRequest(Model):
    reviewer: str = Field(min_length=2, max_length=100)
    decision: Literal["accepted", "needs_revision", "disputed"]
    comment: str = Field(min_length=5, max_length=2000)
    finding_ids: list[str] = Field(default_factory=list, max_length=100)


class VoiceContext(Model):
    workspace_id: Literal["pten-real"] = "pten-real"
    dataset_version: str
    selected_variant_ids: list[str] = Field(default_factory=list, max_length=20)
    selected_residue_ids: list[str] = Field(default_factory=list, max_length=20)
    reference_accession: Literal["P60484"] = "P60484"
    mapping_version: str
    active_layer: Literal["activity", "abundance"] = "activity"


class VoiceCommand(Model):
    utterance: str = Field(min_length=1, max_length=600)
    context: VoiceContext
