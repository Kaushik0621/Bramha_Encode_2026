# Real-data Variant Atlas

The final specification replaces the old synthetic-only mission. The frontend and backend remain separate. The frontend now opens the project dashboard; PTEN projects contain the real observatory. See [the current workflow route map](RESEARCH_WORKFLOW_ROUTES.md). `/developer/demo` preserves the eight-variant demonstration and its fixed workflow.

## Run locally

From `variant-atlas/`:

```sh
backend/.venv/bin/python scripts/acquire_pten.py
backend/.venv/bin/python scripts/seed_research.py
```

Then start these in separate terminals:

```sh
cd backend
.venv/bin/python -m app.server
```

```sh
cd frontend
npm run dev
```

Open http://localhost:8500. Backend: http://127.0.0.1:8000. The local profile requires a loopback host. This is a single-user research application; public deployment needs authentication, workspace authorization and deployment hardening.

Install locked dependencies with `uv pip sync backend/requirements.txt --python backend/.venv/bin/python` and `npm ci --prefix frontend` when setting up a checkout. Python 3.11+ is required. Raw scientific assets are not committed; acquisition must finish before seeding. Manifests contain source URLs, licenses, acquisition method and SHA-256 checksums. If current upstream bytes differ, the rebuilt snapshot gets a different version and frozen evaluation should fail until a deliberately reviewed new case is created.

## Data and scientific boundaries

- Human canonical PTEN, UniProt P60484, sequence version 1, 403 amino acids.
- MaveDB activity `urn:mavedb:00000054-a-1` and combined VAMP-seq abundance `urn:mavedb:00000102-0-1`. Original VAMP-seq metadata `urn:mavedb:00000013-a-1` supplies explicitly distinguished calibration context. Both score datasets are CC0 in the acquired metadata.
- The full accepted protein-substitution union contains 7,657 substitutions. Of 5,083 shared identities, 4,839 have both numeric measurements. The initial deterministic workspace subset contains 131 substitutions. Rejected rows, synonyms/control rows, uncertainty and missing measurements remain auditable.
- Activity is yeast growth/enrichment reflecting lipid phosphatase activity. Abundance is a VAMP-seq score. The scales are retained, including negative and above-one values. Null is never zero. The comparison is descriptive and does not establish a causal mechanism, pathogenicity or a cure.
- Activity selection defaults to the source methods' lower synonymous interval boundary, −1.11. The exploratory abundance boundary is the actual fifth percentile of 193 synonymous controls, approximately 0.61219. It is labelled as a derived exploratory boundary, not an author-endorsed or clinical classifier.
- RCSB 1D5R is an experimental engineered/truncated construct. Mapping requires exact aligned identity agreeing with depositor UniProt segment anchors. Global alignment ties and engineered residues are retained in the audit. 307 canonical positions have accepted experimental C-alpha coordinates; missing coordinates, construct exclusions and unresolved construct residues remain explicit.
- Distances are Euclidean C-alpha distances in angstroms in the reference structure. Different substitutions at one residue share a coordinate; there is no mutant folding simulation.

## Real model execution

Investigations are persisted before execution. A leased worker polls durable state, while SSE only transports saved events. Snapshot revisions serialize updates; local mode uses file locks and atomic writes, Atlas uses revision compare-and-swap. Atlas normalized collections are repairable projections of the authoritative investigation snapshot, not an atomic cross-collection transaction.

The model chooses bounded actions, tools, scoped workers, waiting, reconciliation, revision, finalization or abstention. Independent scoped workers may run concurrently; their actual intervals are recorded. Task deduplication includes objective, input artifact IDs and dataset version. Limits default to four concurrent model calls, depth two, twelve spawned tasks, forty tool calls, twenty model requests and six hundred seconds. Step limits include finalization. Unknown provider cost stays unknown; an optional cost ceiling stops after a response and cannot guarantee prepaid spend.

The planner sees only implemented capabilities. Core tools are exposed through typed contracts; orchestration tools 32/34/35 pass through the durable action boundary. DNA annotation, clinical/population assertions, predicted confidence and unsupported replicate resampling remain unavailable. Source/reference checks validate existence and identity, not scientific truth. Numeric checks compare declared values with artifacts and reject unmatched numeric tokens outside known scientific identifiers. Review remains necessary for semantic applicability and unit interpretation.

Provider errors never silently become fixture output. Google uses the installed SDK's Interactions API with configured medium/high thinking and background execution. OpenRouter uses its own supported request format, labelled as a development provider. Google/Argon access has not been verified in this environment.

For a separate job process, set `WORKER_MODE=external` on the API and run:

```sh
backend/.venv/bin/python scripts/research_worker.py
```

Worker shutdown or an expired lease leaves an interrupted run with checkpoints. Automatic replay of uncertain model requests is intentionally refused; retry starts a new investigation. Cancel stops new work and cancels active awaitables; provider cancellation is requested for Google background interactions where an interaction ID is available.

## UI and APIs

Mol* renders the acquired mmCIF, supports residue/table linking, native assay layers and experimental C-alpha distance annotations for exactly two mapped picked variants. Grey indicates missing measurement. The per-residue display uses the mean of visible subset substitutions, with the selected substitution overriding its residue; the legend states that aggregation. Multiple substitutions remain separate table rows.

The new glass chamber contains actual delegated tasks, dependency edges and inspectable persisted artifacts. It offers a 2D timeline, replay and keyboard buttons. Replay changes only displayed historical chamber state; saved output remains the current persisted result. No particle animation or fake completion percentage represents model work.

Canonical real-data routes include `/api/capabilities`, `/api/workspaces/pten-real`, `/api/workspaces/pten-real/data-audit`, `/api/structures/1D5R`, `/api/analysis/preview` and `/api/investigations` with the real research request. Scientific investigations also have the explicit `/api/research/investigations` namespace so legacy fixture clients remain compatible. Run snapshots, events, cancel, artifact, review and JSON exports are implemented. Real substitution IDs also resolve at `/api/variants/{id}`. Local reviewer names are self-identified and not independently credential-verified.

## Atlas hybrid retrieval

Local mode is explicitly lexical retrieval. Configured Atlas + embeddings uses real Search/Vector Search and `$rankFusion`; failures do not become local lexical success. Set `DATA_BACKEND=atlas`, `MONGODB_URI`, `EMBEDDING_PROVIDER=voyage`, `EMBEDDING_MODEL` to an available exact ID, and `VOYAGE_API_KEY`, then seed the real workspace and run:

```sh
backend/.venv/bin/python scripts/atlas_retrieval.py embed
backend/.venv/bin/python scripts/atlas_retrieval.py indexes --dimension ACTUAL_EMBEDDING_DIMENSION
backend/.venv/bin/python scripts/atlas_retrieval.py ready
backend/.venv/bin/python scripts/atlas_retrieval.py query --output artifacts/ATLAS_HYBRID_QUERY.json
```

Use the dimension returned by `embed`. Index creation is asynchronous; run readiness again when Atlas reports both indexes queryable. Filters pin workspace, dataset version, human gene/taxonomy, embedding model and optional assay. Source release is fixed through the immutable dataset snapshot. Query artifacts retain passage IDs and embedding usage. Cluster/operator support and an actual successful query still require account access. Do not claim hybrid retrieval is verified without that artifact.

## Voice

Set `GOOGLE_API_KEY` and an account-supported `GEMINI_LIVE_MODEL`. The backend-mediated WebSocket keeps credentials server-side, streams bounded PCM audio, transcriptions and navigation function calls. Exact selected IDs, reference, dataset and mapping version travel with the session. Selection changes stop the old session. Text commands validate this same context, support layer changes, comparisons, selection focus and mapped distances; ambiguous selections request clarification. Scientific criteria are edited explicitly in the form. The Live model must not invent numeric or clinical conclusions.

Live audio is configured integration code, not an account-verified capability in this environment. Contextual text commands are tested independently and remain available.

## Evaluation and outstanding gates

Frozen cases and checksums are in `data/reference_cases/`. `scripts/freeze_reference.py` refuses overwriting the reference case. The numerical and evidence rubric was frozen before live model evaluation. The held-out set excludes every visible workspace substitution; this checks numerical behavior, not medical utility. Live development diagnostics use a smaller six-variant scope and are not a completed evaluation of the full frozen reference.

```sh
backend/.venv/bin/python scripts/evaluate_research.py
backend/.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend run build
# Browser executable may need PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH locally:
npm --prefix frontend run test:e2e
# Opt-in, spends configured credits:
backend/.venv/bin/python scripts/check_research_live.py --live --provider openrouter
```

The strict live reference has not yet passed: the current Grok configuration can reach a completed concurrent workflow, but later stricter verification runs stopped or abstained within budget. A failed initial live experiment is preserved in `artifacts/RESEARCH_LIVE_INITIAL_FAILURE.json`; later verification is separate. See `IMPLEMENTATION_STATUS.md` for current gates. Missing Google/Atlas credentials and independent researcher review prevent claiming full challenge completion.

## Verified documentation references

- [MaveDB API](https://www.mavedb.org/docs/mavedb/programmatic-access/api-quickstart.html)
- [Google Interactions](https://ai.google.dev/gemini-api/docs/interactions-overview)
- [Google Live capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
- [Atlas hybrid search](https://www.mongodb.com/docs/vector-search/hybrid-search/hybrid-search-overview/)
- [Voyage embeddings](https://docs.voyageai.com/docs/embeddings)

These documents informed adapter shapes; documentation access is not proof that this account can execute the models or cluster features.
