from typing import Literal
from pydantic import Field
from .schemas import Model, Investigation, InvestigationRequest

RunStatus = Literal['queued','running','cancellation_requested','completed','needs_review','failed','cancelled']
WorkerStatus = Literal['queued','running','completed','failed','cancelled','skipped']
WorkerKind = Literal['deterministic_tool','llm_call','database','output']
TERMINAL = {'completed','needs_review','failed','cancelled'}

class Worker(Model):
    id: str
    name: str
    kind: WorkerKind
    depends_on: list[str]
    description: str

class Artifact(Model):
    id: str
    name: str
    worker_id: str
    summary: str
    refs: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)

class RunEvent(Model):
    event_id: str
    run_id: str
    sequence: int
    timestamp: str
    type: str
    worker_id: str
    worker_kind: WorkerKind
    task_id: str
    parent_task_id: str = 'investigate'
    status: str
    summary: str
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    sender: str | None = None
    recipient: str | None = None
    mode: str

class RunSnapshot(Model):
    run_id: str
    status: RunStatus
    created_at: str
    updated_at: str
    request: InvestigationRequest
    workers: list[Worker]
    events: list[RunEvent] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    dataset_version: str | None = None
    data_mode: Literal['synthetic'] = 'synthetic'
    execution_mode: Literal['live','simulated'] = 'live'
    storage: str
    provider: str
    model: str | None
    result_id: str | None = None
    result: Investigation | None = None
    error: str | None = None
