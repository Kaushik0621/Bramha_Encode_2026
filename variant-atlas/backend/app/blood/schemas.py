import re
from typing import Literal
from pydantic import Field
from ..schemas import Model


class Scenario(Model):
    abo: Literal["O", "A", "B", "AB"]
    rhd: Literal["positive", "negative"]
    provenance: Literal["self-reported"] = "self-reported"


class ComparisonRequest(Model):
    project_id: str | None = Field(default=None, pattern=r"^project-[a-f0-9]{32}$")
    question: str = Field(min_length=10, max_length=1800)
    scenario_a: str | None = Field(default=None, max_length=20)
    scenario_b: str | None = Field(default=None, max_length=20)
    context: str = Field(default="severe P. falciparum malaria", max_length=100)
    focus: Literal[
        "molecular mechanism", "study evidence", "uncertainty"
    ] = "molecular mechanism"
    max_seconds: int = Field(default=300, ge=15, le=600)


GROUP = re.compile(r"(?<![A-Za-z])(AB|O|A|B)\s*(positive|negative|[+−-])", re.I)


def parse_group(raw):
    match = GROUP.fullmatch(raw.strip())
    if not match:
        raise ValueError("Use an ABO group and RhD sign, for example O positive or B−.")
    return Scenario(
        abo=match[1].upper(),
        rhd="positive" if match[2].lower() in ("positive", "+") else "negative",
    )


def interpret(body):
    if body.context.strip().lower() not in {
        "severe p. falciparum malaria",
        "severe plasmodium falciparum malaria",
    }:
        raise ValueError(
            "Unsupported scope: only severe P. falciparum malaria is supported."
        )
    # Explicit other disease requests must not be silently relabelled as malaria.
    if re.search(r"\b(cancer|dengue|covid|diabetes|vivax)\b", body.question, re.I):
        raise ValueError(
            "Unsupported disease in question; this module supports severe P. falciparum malaria only."
        )
    found = [parse_group(m[0]) for m in GROUP.finditer(body.question)]
    if bool(body.scenario_a) != bool(body.scenario_b):
        raise ValueError("Provide both scenarios or neither.")
    if body.scenario_a:
        a, b = parse_group(body.scenario_a), parse_group(body.scenario_b)
        if len(found) >= 2 and (found[0] != a or found[1] != b):
            raise ValueError(
                "Blood groups in the question conflict with the scenario fields. Review the interpretation."
            )
    elif len(found) == 2:
        a, b = found
    else:
        raise ValueError(
            "Specify exactly two blood groups in the question, or supply both scenario fields."
        )
    return {
        "a": a.model_dump(),
        "b": b.model_dump(),
        "abo_differs": a.abo != b.abo,
        "rhd_differs": a.rhd != b.rhd,
        "context": "severe P. falciparum malaria",
        "question": body.question,
        "focus": body.focus,
        "scope": "Literature-grounded comparison of reported phenotypes; no participant testing or individual predictions.",
    }


class Observation(Model):
    text: str = Field(min_length=10, max_length=1600)
    refs: list[str] = Field(min_length=1, max_length=8)
    system: Literal["ABO", "RhD", "shared"]
    domain: Literal["reference biology", "malaria", "uncertainty"]
    applicability: str = Field(min_length=10, max_length=1000)
    competing_explanations: list[str] = Field(default_factory=list, max_length=5)
    missing_evidence: list[str] = Field(default_factory=list, max_length=5)


class WorkerReport(Model):
    observations: list[Observation] = Field(max_length=6)
    limitations: list[str] = Field(min_length=1, max_length=8)
    next_retrieval: str = Field(max_length=1000)


class Finding(Observation):
    section: Literal[
        "supported differences",
        "shared features",
        "unknown or unsupported distinctions",
        "additional evidence needed",
    ]


class Job(Model):
    role: Literal[
        "scenario_a",
        "scenario_b",
        "mechanism",
        "applicability",
        "verifier",
        "reconciliation",
    ]
    question: str = Field(min_length=10, max_length=1000)


class Plan(Model):
    operation: Literal["search", "spawn", "revise", "finalize", "abstain"]
    query: str = Field(default="", max_length=500)
    system: Literal["ABO", "RhD", "all"] = "all"
    context: Literal["reference", "malaria", "all"] = "all"
    study: str = Field(default="all", max_length=80)
    jobs: list[Job] = Field(default_factory=list, max_length=4)
    findings: list[Finding] = Field(default_factory=list, max_length=16)
    presenter_summary: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=1000)


class StudyStatistic(Model):
    value: float
    measure: str
    lower: float
    upper: float
    uncertainty: str
    contrast: str
    endpoint: str
    population: str


class EvidenceSource(Model):
    id: str
    title: str
    url: str
    canonical_url: str | None = None
    system: Literal["ABO", "RhD"]
    context: Literal["reference", "malaria"]
    design: str
    population: str
    endpoint: str
    location: str
    passage: str
    limitations: list[str]
    retrieved_at: str
    passage_kind: str
    passage_id: str
    statistics: list[StudyStatistic] = Field(default_factory=list)
    download_status: Literal["cached", "unavailable"] = "unavailable"
    download_checked_at: str | None = None
    asset: dict | None = None
