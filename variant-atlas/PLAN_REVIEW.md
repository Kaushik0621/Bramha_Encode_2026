# Build brief and product plan review

Both supplied documents were read before implementation. This repository follows the build brief where it makes the long-term product plan more specific.

- **First milestone:** synthetic protein-like geometry and scores, not real PTEN. Real-data joins remain gated by source terms, assay interpretation and sequence-to-structure mapping.
- **Separate frontend and backend:** independent package/dependency systems and development servers. The frontend has no provider or database credentials. Domain rules and persistence live in Python.
- **Correct defaults:** five matching fixture IDs, including two unmapped candidates; mapped-only gives three. A missing activity value is insufficient measurement, not zero.
- **Viewer honesty:** a deterministic curved backbone, deliberately broken at missing position 95. The viewer is not a PTEN fold, molecular dynamics simulation or a mutated structure. `StructureViewer` is the adapter boundary for future Mol*.
- **Narrow interpretation of explanation verification:** exact extractive evidence claims plus verified references, with free-form numerical assertions rejected. This avoids claiming a complete validator for arbitrary scientific prose. Hypotheses remain unverified; model output never changes the deterministic candidate set.
- **Persistence first:** one repository interface with atomic local files or Atlas. A configured Atlas failure is an error. Credentials are needed to establish live Atlas acceptance.
- **Competition boundaries:** no claim of a live Argon run or Atlas Search until those integrations are implemented and exercised. A local fixture demo and ordinary database indexes do not satisfy those track requirements.
- **User validation:** no named researcher, time savings or willingness-to-pay claim has been invented. Recruitment and evaluation remain product gates.

The runtime UI contains only implemented actions. Workspace selection contains the one seeded workspace. Fictional evidence opens internally; it is never attached to fake publications.


## Business goal alignment

The business-goal document makes the primary deliverable an experimental decision brief: which candidates to investigate, why, and what uncertainty follow-up could address. The 3D view supplies context.

Implemented in this pass:

- A saved research question, separate from the numerical eligibility filters.
- A candidate-capacity constraint, with explicit researcher curation and no automatic importance ranking.
- Per-variant notes separating supplied synthetic observations, calculated inclusion rationale, unresolved questions, competing explanations and unverified follow-up approaches.
- Evidence/variant snapshots and exclusion reasons in the saved brief and Markdown export.
- Requested server settings, frontend port 8500 and backend-only OpenRouter credentials. Process environment takes precedence over private dotenv settings for safe isolated tests.
- Live catalog lookup and validated synthetic-evidence explanation with the configured `x-ai/grok-4.3` model.

Time savings, buyer demand, assay compatibility and scientific usefulness remain hypotheses for evaluation with an actual researcher. No biological insight, information-gain ranking or validated experimental outcome is claimed.

## Investigation chamber addendum

The chamber now consumes actual persisted workflow events over SSE, with an independent asynchronous worker, accessible task/artifact inspection, source/provider docks, replay, cancellation and a linked protein tab/split view. The existing synchronous API remains compatible through an opt-in asynchronous query parameter. The bundled deterministic recording is explicitly simulated; live synthetic-input runs are labelled separately. Workflow controllers/tools, model-backed explanation, provider and store roles stay distinct. See CHAMBER.md for execution contracts and restart/cancellation limits.
