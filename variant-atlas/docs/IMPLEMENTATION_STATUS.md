# Final scope: implementation status

The final specification and final product/data plan supersede the earlier synthetic-only milestone. The existing fixture workspace and synchronous APIs are retained as development/regression paths.

## Confirmed access blockers at start

- Google API credentials are absent. Actual Argon and Live invocation cannot be claimed before successful account/model verification.
- Atlas credentials are absent. No local retrieval result can establish a working Atlas text/vector/hybrid query.
- No named researcher has reviewed a reference investigation. Scientific usefulness and commercial value remain unvalidated.

## Repository audit (M0)

Reusable: separate React/FastAPI applications; bounded OpenRouter explanation; synthetic fixture tests; explicit selection/capacity rules; local and optional Atlas persistence; event/SSE/replay/cancellation plumbing; execution chamber.

Required upgrades: authentic assay/reference/structure ingestion and audit; real Mol* structure rendering; native-scale analysis; model-selected tools and scoped dynamic workers; durable leased jobs/checkpoints; verified provider adapters; Atlas retrieval and contextual voice; frozen reference/held-out evaluation and capability reporting.

## Data gate findings

The two selected assay targets translate exactly to canonical human P60484 sequence version 1. Activity is a yeast-assay fitness proxy; abundance is a composite VAMP-seq endpoint. They are not a shared numerical scale. Dataset snapshots expose CC0 licenses. Native values and uncertainty columns are retained. No original dummy threshold is applied.

1D5R is an experimental, truncated/engineered construct with unresolved coordinates. Alignment is audited per residue against depositor UniProt segments. Globally ambiguous alignment or engineered construct residues do not justify silently mapped coordinates. Canonical residues lacking accepted coordinates remain unavailable for geometry.

Detailed machine-readable coverage, mappings, identity decisions, assay context and source checksums are under `data/manifests/`. Raw assets are content-addressed, ignored by Git and reproducibly reacquirable; exports do not include access-restricted source bytes.

## Delivered implementation and measured gates

| Gate | Status | Evidence / remaining requirement |
| --- | --- | --- |
| M0 repository audit | Complete | Separate frontend/backend retained; legacy fixture is explicitly separate. |
| M1 real-data scientific core | Deterministic checks pass | Acquired immutable source assets; audited P60484 identities, assay context, uncertainty, native values, construct alignment, partial mappings; Parquet/DuckDB calculations and frozen numerical reference. Independent scientific endorsement is pending. |
| M2 adaptive investigation | Implemented; strict reference acceptance incomplete | Actual Grok run `research-dd775fe90cc54cfe9828364e4149c65c` completed with overlapping assay/structure specialists and reconciliation: 15 model requests, 6 tool calls. Later, stricter numeric-coverage and mandatory spatial-revision gates exposed non-convergent outputs; the latest recorded run abstained within budget. The earlier workflow success does **not** pass the final stricter scientific acceptance rubric. |
| M3 spatial workflow | Implemented; browser checked | Authentic Mol* mmCIF, assay layers, selection, reference C-alpha distance annotations, real task graph, persisted artifacts, accessible timeline/replay and responsive UI. Browser evidence is separate from scientific validity. |
| M4 retrieval and voice | Configured adapters; live verification blocked | Atlas Search/Vector Search provisioning, Voyage embeddings and filtered hybrid pipeline implemented. Backend-mediated Gemini Live audio/navigation and contextual text fallback implemented. No Google, Atlas or Voyage credentials were available; no successful live hybrid/audio artifact is claimed. |
| M5 evaluation | Numerical contracts pass; final review incomplete | Frozen reference identities/selection/distance/refusal and 32 distinct held-out native rows checked. Actual independent researcher review, strict end-to-end model reference success and commercial usefulness remain unvalidated. |

The live diagnostics use a six-variant development scope. The full frozen workspace reference has not passed a live model evaluation.

### Real model evidence is not all green

The development experiments are preserved in `artifacts/RESEARCH_LIVE_*.json`: initial invalid delegation failure; step-limited abstention; invalid structured-summary failure; a completed concurrent workflow before stricter gates; request-budget stop under strict numeric validation; and the latest strict result. These are real provider runs on the audited public data, not scripted acceptance successes. No automatic retry swaps providers or labels an older result as passing newer checks.

The model can recover some numeric claims from verifier feedback, but the current Grok configuration did not reliably finalize the strict reference case within the declared global/task budgets. This remains an explicit M2 gate. Credential access alone is not proof that Argon will pass it; it needs an actual run and rubric evaluation.

### Capability scope

Twenty-nine named capabilities are exposed. Tools 32, 34 and 35 execute through the durable finalization/delegation boundary; they are not direct read-tool stubs. Unsupported capabilities remain unavailable to the planner: broad dataset discovery, DNA consequence annotation, replicate bootstrapping without validated exchangeability, predicted-model confidence, clinical assertions, population context and automated conflicting-evidence assembly beyond explicit reconciliation. This does not claim that all 36 tools have been built.

Mechanical checks establish source existence, reference identity, numeric agreement with artifacts and declared eligibility. They cannot establish scientific truth or whether a hypothesis will help a researcher. Free-text numeric tokens outside known scientific identifiers require matching structured claims; semantic applicability and units still require review when not explicitly represented in an artifact.

### Operational limits

Local single-user mode is enforced at the application boundary and normal startup binds loopback. Other profiles are rejected pending authentication/workspace authorization. Local atomic files and Atlas compare-and-swap snapshots are authoritative; normalized Atlas projections are repairable, not a cross-collection transaction. Interrupted jobs keep checkpoints and require an explicit new run rather than replaying uncertain model calls. Configured but failing model/storage/retrieval providers do not fall back silently.

See [run instructions and implementation details](REAL_DATA_BUILD.md) and [architecture diagrams](ARCHITECTURE.md).
