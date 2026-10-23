from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
MappingStatus = Literal['mapped', 'missing_coordinates', 'outside_structure_coverage']

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Point(Model):
    position: int
    x: float
    y: float
    z: float

class Protein(Model):
    id: str
    name: str
    sequence: str
    length: int
    synthetic: Literal[True] = True

class Variant(Model):
    id: str
    protein_id: str
    position: int
    ref: str
    alt: str
    synthetic: Literal[True] = True
    mapping_status: MappingStatus
    evidence_ids: list[str]

class Measurement(Model):
    variant_id: str
    assay_id: str
    value: Score | None
    synthetic: Literal[True] = True

class Assay(Model):
    id: str
    name: str
    property: Literal['activity', 'abundance']
    scale: str
    synthetic: Literal[True] = True

class Evidence(Model):
    id: str
    title: str
    text: str
    variant_ids: list[str]
    kind: Literal['fictional_record'] = 'fictional_record'
    synthetic: Literal[True] = True

class Structure(Model):
    id: str
    protein_id: str
    label: str
    coordinate_units: str
    points: list[Point]
    synthetic: Literal[True] = True

class Workspace(Model):
    id: str
    name: str
    dataset_version: str
    synthetic: Literal[True] = True
    protein: Protein
    variants: list[Variant]
    measurements: list[Measurement]
    assays: list[Assay]
    evidence: list[Evidence]
    structure: Structure

class Criteria(Model):
    abundance_min: Score = 0.70
    activity_max: Score = 0.35
    mapping: Literal['all', 'mapped', 'unmapped'] = 'all'
    evidence: Literal['all', 'present', 'missing'] = 'all'

class VariantResult(Model):
    variant_id: str
    matches: bool
    abundance: Score | None
    activity: Score | None
    mapping_status: MappingStatus
    evidence_count: int
    reasons: list[str]

class Analysis(Model):
    criteria: Criteria
    matching_ids: list[str]
    mapped_count: int
    unmapped_count: int
    missing_measurement_count: int
    results: list[VariantResult]

class VariantDetail(Model):
    variant: Variant
    measurements: list[Measurement]
    evidence: list[Evidence]
    coordinate: Point | None

class Neighbor(Model):
    variant_id: str
    position: int
    distance: float

class Neighbors(Model):
    variant_id: str
    radius: float
    units: str = 'demo coordinate units'
    status: Literal['available', 'unavailable']
    reason: str | None = None
    neighbors: list[Neighbor]

class Finding(Model):
    variant_ids: list[str] = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=1600)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)

class Hypothesis(Model):
    text: str = Field(min_length=1, max_length=1000)
    status: Literal['unverified']

class Narrative(Model):
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[Finding] = Field(max_length=16)
    hypotheses: list[Hypothesis] = Field(max_length=8)
    follow_up_questions: list[str] = Field(max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=10)

DEFAULT_RESEARCH_QUESTION = 'Which variants meet our declared assay criteria, and what uncertainty should follow-up resolve?'

class DecisionNote(Model):
    variant_id: str
    observations: list[Measurement]
    selection_reason: str
    evidence_ids: list[str]
    unresolved_question: str
    alternative_explanation: str
    follow_up_approach: str
    hypothesis_status: Literal['unverified'] = 'unverified'
    limitations: list[str]

class InvestigationRequest(Model):
    title: str = Field(default='Preserved abundance · reduced activity', min_length=1, max_length=120)
    research_question: str = Field(default=DEFAULT_RESEARCH_QUESTION, min_length=10, max_length=1000)
    candidate_budget: int = Field(default=10, ge=1, le=1000, strict=True)
    criteria: Criteria = Field(default_factory=Criteria)
    selected_ids: list[str] | None = Field(default=None, max_length=8)
    explanation_mode: Literal['configured', 'fixture', 'none'] = 'configured'

class Step(Model):
    name: str
    status: Literal['completed', 'failed', 'skipped']
    detail: str
    completed_at: str

class Investigation(Model):
    id: str
    title: str
    created_at: str
    dataset_version: str
    research_question: str = DEFAULT_RESEARCH_QUESTION
    candidate_budget: int = 10
    decision_notes: list[DecisionNote] = Field(default_factory=list)
    evidence_snapshot: list[Evidence] = Field(default_factory=list)
    variant_snapshot: list[Variant] = Field(default_factory=list)
    criteria: Criteria
    selected_ids: list[str]
    source_ids: list[str]
    analysis: Analysis
    narrative: Narrative | None
    result_mode: Literal['fixture', 'openrouter', 'deterministic', 'llm_error']
    provider: str
    model: str | None
    explanation_error: str | None
    steps: list[Step]
    synthetic: Literal[True] = True

class InvestigationSummary(Model):
    id: str
    title: str
    created_at: str
    selected_count: int
    result_mode: str

class Health(Model):
    status: Literal['ok', 'error']
    storage: str
    storage_ready: bool
    storage_error: str | None
    llm_provider: str
    llm_model: str | None
    llm_configured: bool
    dataset_mode: Literal['synthetic'] = 'synthetic'
