# Variant Atlas — complete Codex implementation specification

Version 1.0 · 24 October 2026 · Companion to `variant-atlas-final-product-and-data-plan.md`

## 0. Instructions and completion standard

Implement the product described here and in the companion plan. These two documents supersede earlier synthetic-only briefs for final scope. Do not deliver just a plan, landing page, fixed loading animation, tool registry of stubs or model-written explanation. Build and verify an end-to-end computational investigation workspace. Inspect the supplied repository and applicable AGENTS.md first; adapt existing code without destructive rewrites. If no repository exists, create a clean project.

Work through milestones in dependency order. Continue independently on work not blocked by credentials or data. Surface concrete blockers and an accurate capability matrix; do not fabricate successful integrations. Missing access can justify an explicitly incomplete milestone, not a claim that challenge requirements are satisfied. Confirm official competition timing/rules before competition code if relevant.

The final core mission: human PTEN missense-variant evidence investigation, comparing supported activity/abundance patterns, auditing mappings, inspecting structural context and delivering a source-linked follow-up brief. Two supported hypothesis scenarios are abundance-associated impairment and preserved-abundance/reduced-activity impairment. Neither is a proven mechanism merely because measurements match a pattern.

## 1. Product stack and layout

- Frontend: React, TypeScript, Vite; a query/state library as appropriate.
- Scientific viewer: Mol* for actual molecular structures.
- Workflow visualisation: React Three Fiber + Drei for a transparent 3D chamber.
- Backend: Python, FastAPI, Pydantic, supported MongoDB driver, httpx; scientific parsing/alignment libraries selected after compatibility checks.
- Analysis: Parquet and DuckDB for pinned derived measurement tables; explicit numerical functions for geometry and selection.
- Storage: Atlas metadata/state/events and text/vector indexes; local filesystem/object-store adapter for immutable assets and exports.
- Model adapters: actual Google Argon, supported Gemini companions/Live, OpenRouter development adapter and explicit fixture mode.

Pin tested dependency versions; document Python/Node versions and install commands. Avoid unsupported SDK assumptions. Do not add Kubernetes, unrelated databases or unnecessary infrastructure.

Suggested structure:

```text
variant-atlas/
  frontend/src/{views,components,scene,events,api,types}/
  backend/app/
    api/
    domain/
    ingestion/
    analysis/
    tools/
    orchestration/
    providers/
    retrieval/
    repositories/
    exports/
  backend/tests/
  data/{manifests,fixtures,reference_cases}/
  scripts/
  docs/
  .env.example
  README.md
```

## 2. Data acquisition is the first hard gate

Use the companion plan's source URLs. Implement a reproducible acquisition command using current documented downloads/APIs; do not guess endpoints. Start with UniProt human PTEN P60484, one PTEN activity dataset, one PTEN abundance dataset and RCSB 1D5R as candidates. Their compatibility and coverage must be inspected, not assumed. Original study: https://pmc.ncbi.nlm.nih.gov/articles/PMC8518224/ . MaveDB exports/API guidance: https://www.mavedb.org/docs/mavedb/finding-data/index.html .

Produce `data/manifests/pten-source-manifest.json`, a mapping audit, assay dictionary and coverage report. Store immutable raw bytes/checksums before transformations. Record source/accession/version, URL, retrieval timestamp, licence/terms status, SHA-256, parser/transformation version, size and asset reference. An access/terms uncertainty remains explicit; do not redistribute assets without appropriate permission.

Select a modest, configurable subset after auditing overlap. Do not fabricate a record count or silently substitute predicted/synthetic evidence. If required data is inaccessible, support importing a documented permitted local export, report the blocker and keep integration status incomplete.

Required ingestion rules:

- Preserve organism, representation level, reference accession/version, isoform/transcript and genome build where applicable.
- Validate substitutions against the reference amino acid.
- Distinguish exact DNA measurements, protein-substitution measurements and related evidence.
- Preserve assay endpoints, direction, scale, model system, construct, controls, replicate/uncertainty availability and source IDs.
- Never treat real activity/abundance scores as interchangeable or reuse prototype 0–1 cutoffs without documented interpretation.
- Align assay target -> pinned reference -> structure chain, retaining numbering/insertion codes and ambiguity.
- Missing coordinates are unavailable, not generated or silently interpolated.
- Keep accepted, rejected and unresolved joins with reasons.

ClinVar, gnomAD, alternative structures and literature enter on demand for relevant tasks, not via whole-database ingestion. No gnomAD record is not zero frequency. Predicted coordinates/confidence remain distinct from experimental evidence. No raw whole-genome read processing is required.

## 3. Storage and domain contracts

Atlas collections: `workspaces`, `sources`, `proteins`, `variant_representations`, `variants`, `assays`, `measurements`, `structures`, `residue_mappings`, `evidence_passages`, `investigations`, `tasks`, `events`, `artifacts`, `findings`, `hypotheses`, `reviews`.

Use stable app IDs and workspace scoping throughout. Enforce unique keys for source/version records and per-run event sequence; index workspace/run/task IDs and exact scientific lookup keys. Keep authoritative run state in Atlas, not in process memory. Analytical Parquet snapshots are derived artifacts identified by checksum; do not maintain a competing mutable source of truth in DuckDB.

Use object-store keys or constrained local asset paths with checksums. Do not place binary structures or full documents inside every task prompt. Vector passages store embedding model/version and chunk/source references. Exact sequence/variant identity uses structured lookup and biological tools, never prose similarity.

Minimum investigation fields: ID, workspace, question, organism/gene, pinned input artifact IDs, criteria, capacity, data mode, execution mode, status, budget, root task, model/provider metadata, created/updated timestamps, findings and unresolved issues.

Task contract:

```json
{
  "task_id": "task-example",
  "run_id": "run-example",
  "parent_task_id": null,
  "role": "assay_specialist",
  "question": "Can these two assays support the requested comparison?",
  "input_artifact_ids": ["artifact-assay-metadata"],
  "allowed_tools": ["inspect_assay", "assess_comparability", "retrieve_passage"],
  "expected_output_schema": "comparability_report_v1",
  "stop_condition": "report produced or evidence exhausted",
  "status": "queued",
  "budget": {"max_steps": 8, "max_seconds": 180},
  "model": {"provider": "configured", "id": "configured"}
}
```

Findings carry claim type (`reported_observation`, `computed_result`, `hypothesis`, `unknown`), text, variant IDs, evidence/artifact references, limitations, verifier outcomes and reviewer status. A validated JSON schema does not prove a claim scientifically true.

## 4. Bounded agent orchestration

Argon is the lead in challenge mode. It selects actions/tools dynamically using typed structured outputs or native function calling verified against the provider's current API. Build a bounded state machine/graph around model decisions; a framework is optional. A hardcoded plan followed by a narrative is development scaffolding only.

Supported actions: inspect state, invoke allowed tool, spawn specialist task, request reconciliation, revise hypothesis, request missing information, finalise supported result, abstain. Agent-generated actions undergo schema, permission, precondition and budget validation before execution.

Worker roles: identity/data, assay, structure, evidence, verifier and reconciliation. Dynamic spawn creates a scoped task with input references; no OS process replication, new credentials, arbitrary network access or unbounded recursion. Default limits: 4 concurrent workers, depth 2, 12 spawned tasks, 40 total tool calls and 10 minutes per run; all configurable. Enforce a total model-request cap and optional monetary cap when pricing metadata exists. Persist token usage and costs as unknown when unavailable, never invented.

Use task deduplication keyed by objective, input versions and role. Independent branches may run concurrently; dependent steps wait for validated artifacts. Workers share structured findings through stored artifacts; messages link sender/recipient/task IDs. The lead resolves contradictions or explicitly leaves them unresolved. Reviewer disagreement triggers checks, not majority-vote truth.

Create a registry of model capabilities and worker permissions. Specialist fast-model selection is configurable. Use Argon for hard reasoning where justified; do not assign expensive models to deterministic work. Record actual provider/model per call.

## 5. Tool registry — 36 real capabilities

Implement explicit typed functions. Group capabilities for discoverability; do not force every tool into every run. Prioritise the core mission first. A tool not implemented is unavailable to the planner, not a callable fake. Read-only data tools may fetch/cache pinned evidence; write tools create scoped investigation artifacts.

| ID/tool | Input -> output and important boundary |
| --- | --- |
| 01 `discover_datasets` | Supported gene/source filters -> dataset candidates with provenance |
| 02 `fetch_source_snapshot` | Allowlisted accession/version -> cached immutable asset and manifest |
| 03 `inspect_table_schema` | Asset -> column/types/missingness report |
| 04 `resolve_reference_sequence` | Accession/version -> sequence identity artifact |
| 05 `validate_variant_identity` | Variant + reference -> valid/rejected/ambiguous result |
| 06 `annotate_supported_dna_variant` | Pinned DNA variant/transcript/build -> consequence; unavailable if annotation integration absent |
| 07 `inspect_assay` | Assay ID -> endpoint/system/construct/controls/limitations |
| 08 `check_score_direction` | Assay metadata -> supported interpretation or unknown |
| 09 `assess_comparability` | Assay pair + question -> supported constraints and unresolved differences |
| 10 `join_measurements` | Audited identities and assay snapshots -> join with exclusions |
| 11 `filter_measurements` | Declared assay-specific criteria -> matching IDs and reasons |
| 12 `summarize_measurement_coverage` | Candidate IDs -> missing/available/uncertainty report |
| 13 `compare_measurement_patterns` | Supported measurements -> descriptive pattern groups, not causal classes |
| 14 `bootstrap_supported_statistic` | Real replicate data + declared statistic/seed -> resampling result; refuse without suitable data |
| 15 `load_structure_metadata` | Structure ID/version -> chains/construct/coverage/source type |
| 16 `align_structure_reference` | Structure sequence + reference -> audited alignment |
| 17 `map_variant_residues` | Accepted alignment + variants -> mapped/unmapped table |
| 18 `calculate_residue_distances` | Mapped residues + metric -> distances with units |
| 19 `find_spatial_neighbors` | Mapped residue + radius -> neighbours/coverage caveat |
| 20 `inspect_structure_confidence` | Predicted-model metadata -> local confidence; not pathogenicity |
| 21 `retrieve_functional_annotations` | Reference/version -> source-linked annotation regions |
| 22 `search_methods_text` | Question + source filters -> ranked permitted evidence passages |
| 23 `retrieve_passage` | Passage ID -> exact text and source location |
| 24 `retrieve_classification_context` | Exact variant/condition -> submitted assertions/version/review status |
| 25 `retrieve_population_context` | Exact supported variant -> observations/coverage or missing status |
| 26 `assemble_conflicting_evidence` | Findings/source set -> disagreement table with context |
| 27 `validate_evidence_references` | Draft findings -> existence/identity/source-link checks |
| 28 `validate_numeric_claims` | Structured claims + tool artifacts -> agreement/failure report |
| 29 `compare_analysis_scenarios` | Declared alternative parameters -> changed selections/results |
| 30 `update_scene_selection` | Valid scene objects/layers -> validated UI command; no arbitrary code |
| 31 `validate_shortlist` | Candidates + criteria/capacity -> deterministic eligibility audit |
| 32 `save_research_brief` | Checked findings + limitations -> versioned brief artifact |
| 33 `export_reproducibility_package` | Run -> Markdown/JSON/source manifest and analysis settings |
| 34 `spawn_specialist` | Scoped task contract -> bounded worker task |
| 35 `request_reconciliation` | Branch artifact IDs -> explicit comparison task |
| 36 `inspect_run_budget` | Run -> remaining steps/time/request limits |

Every contract defines purpose, input schema, output schema, preconditions, supported scope, expected resource cost, failure states and verification. Return `unsupported`, `missing_data`, `incompatible`, `mapping_failed`, `timeout` or `source_unavailable` as structured outcomes. No arbitrary SQL, shell, Python or URLs from the model. Use parameterised queries and allowlisted data access.

Final core acceptance requires tools 02–05, 07–13, 15–19, 22–23, 27–36 where relevant. Optional tools may be honestly disabled; the registry is expandable rather than a quota. Do not claim all 36 are finished if some are adapters without execution.

## 6. Complicated reference investigation

Build one real reference case selected after data inspection. Freeze its expected identities, mapping coverage, numerical results and evidence rubric before final evaluation. Include:

1. Resolve supported variant/reference identities.
2. Branch into abundance and activity/context review.
3. Detect at least one real limitation or disagreement.
4. Revise the plan: narrow a comparison, investigate a different source or abstain from a spatial claim.
5. Run structural analysis only for accepted mapped residues.
6. Reconcile the branch artifacts and check claims.
7. Save an evidence-linked brief with unresolved hypotheses and follow-up questions.

If no convenient real failure exists, add a separately labelled adversarial fixture such as a mismatched reference or missing mapping to test control behaviour. Never alter a public measurement and label it authentic. Distinguish the real-data demonstration from robustness fixtures.

Follow-up suggestions are research questions/approaches for expert review, not detailed wet-lab protocols, prescriptions or claims of optimal information gain. The model cannot override eligibility rules or fabricate a reference publication.

## 7. Model integrations

Implement an adapter with `generate_action`, `generate_structured_result`, usage metadata and cancellation/timeout handling. Verify current Google SDK/API support for `gemini-4-argon`, medium/high thinking and long-running/background execution before implementation. Use documented settings only; do not assume OpenRouter accepts Google-specific parameters. If background operation differs, implement the application's durable job lifecycle separately and report actual provider support.

OpenRouter is allowed for development, including the existing Grok configuration. Exact model ID comes from environment/configuration and supported catalogue, not an invented alias. An alternative model run remains visibly non-Argon. Later R1-family support is an adapter/configuration change after confirming the intended model.

Argon does not provide Live audio. Add a current, supported Live-capable Gemini companion for voice; confirm the account's exact available model ID. Use a faster Gemini companion for bounded extraction only when configured and verified. Missing credentials leave the relevant capability unavailable, not secretly substituted.

Never expose keys in client bundles. Voice sessions use backend-mediated credentials or documented short-lived tokens. Constrain input/output sizes, request timeouts, retries and run budgets. Retry transient transport/rate errors with bounded backoff; do not retry invalid credentials indefinitely. Treat retrieved content as untrusted data, not agent instructions. Log concise observable summaries, not private chain-of-thought or raw system prompts.

## 8. UI: spatial research observatory

Create a premium scientific instrument aesthetic: deep navy, translucent glass, cyan/teal highlights, restrained amber uncertainty, readable labels and clear units. Scientific objects should dominate, not generic dashboard cards or decorative DNA. Maintain usability over bloom/refraction effects.

### Molecular view

Render authentic structure in Mol*, with assay-specific colour legends, selection, orbit/zoom, reset and distance annotations. Show missing mappings in the linked table. Switching measurement layers changes only supported values; missing values are grey/null. No fake mutation-induced folding. Show experimental/predicted structure type, source version and confidence/coverage where applicable.

Linked table/evidence drawer: selecting a row selects its mapped residue; selecting a residue reveals associated variants and evidence. Multiple substitutions at one residue remain distinguishable. Scene state uses stable scientific IDs and versioned mapping IDs, not screen positions.

### Glass chamber

Use R3F/Drei for a transparent chamber containing coordinator, actual specialist workers, tools, source docks and outputs. Edges represent actual task dependencies/handoffs and name the artifact. Queued/running/completed/needs-review/failed/cancelled states have icons and text as well as colour. Show concurrency only when recorded task intervals overlap.

Click a node for task, permitted input summary, source/artifact links, observable tool activity, timestamps, checks and outputs. Click a handoff to inspect passed artifacts. Continuous particle traffic is forbidden when no event occurred. Unknown progress uses elapsed time, not invented percentages. Graph updates must not depend on animation completion.

Offer workflow/protein/evidence tabs and a desktop split view. Keep the research question, declared filters, capacity, source versions and mode labels visible. Provide reduced-motion support, keyboard-equivalent controls, WebGL failure fallback and accessible 2D timeline. Replay is explicitly recorded playback; pausing visuals does not pause execution.

### Voice

Support commands such as “Show activity,” “Focus these variants,” “Are these positions close?” and “Compare these assays.” Send selected variant/residue IDs, gene/reference, mapping version, active layers and dataset snapshot with the utterance. Clarify ambiguous references rather than selecting a random object. Navigation is immediate; changes to scientific criteria are displayed and confirmed when ambiguous. Spoken claims reference verified artifacts; transcripts and text entry provide fallback.

## 9. Events and API

Create durable run/task state before starting work. Use a persisted job worker with leases/checkpoints; support one worker for development. Do not execute the whole investigation solely inside an HTTP request or rely on SSE connection lifetime. Reconnection does not restart a run. A crashed worker produces a recoverable/interrupted state; resume only idempotent/checkpointed tasks or request an explicit retry.

Endpoints:

```text
GET  /api/capabilities
GET  /api/workspaces/{id}
GET  /api/workspaces/{id}/data-audit
GET  /api/variants/{id}
GET  /api/structures/{id}
POST /api/analysis/preview
POST /api/investigations
GET  /api/investigations/{id}
GET  /api/investigations/{id}/events
POST /api/investigations/{id}/cancel
GET  /api/investigations/{id}/artifacts/{artifact_id}
GET  /api/investigations/{id}/export
POST /api/investigations/{id}/reviews
POST /api/voice/session
```

Scope every operation to the authenticated workspace when deployed. Local single-user development can omit account setup behind an explicit localhost-only profile; do not expose it publicly. Validate uploads, size/type limits and paths. Export excludes secrets and access-restricted source bytes.

SSE event contract:

```json
{
  "event_id": "run-001:12", "run_id": "run-001", "sequence": 12,
  "timestamp": "<server UTC>", "type": "task.revised",
  "task_id": "structure-review", "parent_task_id": "investigate",
  "worker_kind": "llm_agent", "status": "running",
  "summary": "Experimental coordinates are unavailable for one selected residue; limiting spatial claims.",
  "input_refs": ["mapping-audit"], "output_refs": ["revised-scope"],
  "data_mode": "real", "execution_mode": "live"
}
```

Persist before broadcast; unique sequence per run; replay from Last-Event-ID; client de-duplication and snapshot reconciliation. Heartbeats communicate connection health, not work progress. Include task queued/started/completed/failed/cancelled, tool started/completed, handoff, hypothesis revised, verification result, artifact created and run terminal events. Store public reason summaries, not hidden reasoning.

Cancellation is cooperative: stop new work, request provider cancellation where supported, and report any in-flight limitation. Separate completed-with-limitations from technical failure and cancellation. A green node does not imply a hypothesis is proven.

## 10. Retrieval implementation

Implement Atlas Search plus Vector Search and a real hybrid query over permitted evidence passages. Provide scripts/instructions for index creation, embedding generation and readiness checks, and an actual successful query artifact when credentials permit. Verify available Atlas tier/operator/model support from current documentation. Optional Voyage adapter is configured separately.

Chunk methods text with stable source/page/section offsets, not arbitrary unsupported citations. Filter by workspace, organism/gene, assay and source release as appropriate. Persist query, filters, retrieved passage IDs, retrieval method and embedding version. Retrieved relevance is not scientific support; the evidence specialist checks applicability.

## 11. Configuration and operating modes

```dotenv
APP_PROFILE=local
DATA_MODE=fixture
DATA_BACKEND=local
MONGODB_URI=
MONGODB_DATABASE=variant_atlas
ASSET_BACKEND=local
ASSET_ROOT=./data/assets
OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_BUCKET=
LLM_PROVIDER=mock
GOOGLE_API_KEY=
ARGON_MODEL=gemini-4-argon
GEMINI_SPECIALIST_MODEL=
GEMINI_LIVE_MODEL=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_PROVIDER=disabled
EMBEDDING_MODEL=
VOYAGE_API_KEY=
MAX_CONCURRENT_WORKERS=4
MAX_SPAWN_DEPTH=2
MAX_SPAWNED_TASKS=12
MAX_TOOL_CALLS=40
MAX_MODEL_REQUESTS=20
MAX_RUN_SECONDS=600
```

Separate data mode (real/fixture), execution mode (live/replay), model provider and storage mode in UI and persisted state. Fixture/mock runs remain runnable without secrets for development. A configured Atlas or provider failure must surface honestly, not silently switch to mock/local data. `.env` is ignored by git; no browser `VITE_` secrets. Validate configuration at startup and expose a redacted capabilities report.

## 12. Milestones and gates

### M0 — repository audit

Document existing working features, migrations and gaps. Preserve prior API behaviour or version changes. Add a concise capability matrix: implemented, tested-live, fixture-only, blocked, deferred.

### M1 — real-data scientific core

Deliver source acquisition, manifests, assay dictionary, mapping/coverage audits, a real structure and deterministic analysis. This is the first major gate; no fake 3D geometry in real mode.

### M2 — working adaptive investigation

Actual Argon tool selection, scoped worker creation, branch exchange, reconciliation and verification. Demonstrate a limitation changing the plan. Save the result and provenance. No requirement to invoke all workers/tools unnecessarily.

### M3 — spatial workflow

Link Mol* selections, evidence and chamber events. Demonstrate one calculated spatial question and an unavailable-coordinate case. Complete error/reconnect/replay handling before adding decorative effects.

### M4 — retrieval and voice

Demonstrate Atlas hybrid retrieval and a contextual Live voice interaction. Retain full text interaction. If credentials block these features, document them as incomplete rather than claiming Pathway 2 completion.

### M5 — evaluation and presentation

Freeze a reference case/rubric, test a held-out case, obtain named researcher review and create a repeatable demo script. Describe measured outcomes and limits accurately. Final competition compliance needs required Argon integration, real scientific/spatial work, the real-user story and working Atlas functionality, not just passing unit tests.

## 13. Acceptance tests

- Identity: reference mismatch rejected; ambiguity and representation levels preserved; organism/build/version not dropped.
- Assays: missing values are null; score direction and assay context retained; unsupported normalisation/comparison refused.
- Mapping: known accepted sequence-to-chain pairs checked; missing residue/insertion-code cases handled; no interpolation of absent coordinates.
- Geometry: known-coordinate distance fixtures, metric/units, self-exclusion and unmapped refusal.
- Orchestration: allowed-tool selection, dynamic independent branches, task deduplication, budget/depth limits, revision after failed precondition, checkpoint/reconnect and cancellation.
- Evidence: unknown citation IDs rejected; numbers checked against artifacts; hypotheses labelled; source existence does not masquerade as entailment validation.
- Retrieval: actual text/vector/hybrid query in Atlas integration profile; no fallback claimed as successful hybrid retrieval.
- Persistence: saved run, artifacts and ordered events survive restart; source versions frozen.
- UI: selection synchronisation, legends, chamber state, keyboard/reduced motion and fallback; one browser flow from question through branch inspection to export.
- Voice: selected-object reference resolved; ambiguous selection clarified; unavailable voice shows text fallback.
- Providers: fixture tests plus explicitly opt-in live tests; invalid credentials/429/timeouts never become fake successful responses.
- Security: secrets absent from frontend/logs/exports, bounded access and validated uploads; no model-controlled arbitrary commands.

Scientific evaluation is separate: a researcher reviews correctness, usefulness, missed caveats and follow-up relevance against a frozen rubric. Measure task time and errors before claiming efficiency gains. Do not claim clinical validation.

## 14. Delivery checklist

Deliver working code, README, pinned dependencies, `.env.example`, exact setup/seed/worker/test commands, source manifests, audits, index setup, reproducible analysis settings, demo script, capability matrix and blocker list. Include screenshots only if useful for documenting the implemented UI; they are not a substitute for working interaction.

The first showcase is a real PTEN investigation. A separate fixture replay may demonstrate resilience, but must be labelled. No claims of cures, autonomous wet experiments, validated mutant simulation or Phase 1/2 testing. No claim that all tools, agents or integrations work unless they have actually been executed and checked.

## 15. Documentation to verify during implementation

- Product/data companion: `variant-atlas-final-product-and-data-plan.md`
- Google Argon: https://ai.google.dev/gemini-api/docs/models/gemini-4-argon
- Gemini Live: https://ai.google.dev/gemini-api/docs/live
- OpenRouter: https://openrouter.ai/docs/quickstart
- MaveDB data access: https://www.mavedb.org/docs/mavedb/finding-data/index.html
- MaveDB representations: https://mavedb.org/docs/mavedb/interpreting-annotated-variants.html
- RCSB PTEN candidate structure: https://www.rcsb.org/structure/1D5R
- MongoDB hybrid retrieval: https://www.mongodb.com/docs/vector-search/hybrid-search/vector-search-with-full-text-search/

Use current official documentation and primary research for API/scientific details. These sources identify starting points; they do not establish that assets are already downloaded or integrations complete. Build the real capability, verify it, and label the remaining limits clearly.
