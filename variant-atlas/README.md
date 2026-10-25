> The current product flow and canonical routes are documented in [Final experience implementation](docs/FINAL_EXPERIENCE_IMPLEMENTATION.md): Home → My Research / Library → Workspace, Evidence, Results and Notebook. PTEN, blood-group evidence and bounded paper review share one project flow. Scientific provenance remains in [REAL_DATA_BUILD.md](docs/REAL_DATA_BUILD.md); the synthetic demonstration stays at `/developer/demo`.

# Bramha Atlas

For a shareable, step-by-step product discussion with diagrams, see [Connected research workflow](docs/BRAMHA_ATLAS_VISUAL_WORKFLOW.md). It separates the existing application from proposed visual improvements.

A runnable local research workspace built from `variant-atlas-codex-build-brief.md` , `variant-atlas-product-plan.md` and `variant-atlas-business-goal.md`. React/TypeScript frontend and Python/FastAPI backend are separate applications, communicating exclusively through HTTP.

PTEN projects use audited public PTEN measurements and an unchanged experimental reference structure. The separate synthetic workspace contains eight fictional variants and illustrative geometry. Both support evidence-led exploration; neither predicts cures or a validated mutant fold.

See [the molecular overview, screenshots and asset provenance](docs/MOLECULAR_OVERVIEW.md), and [Bramha product context, agent roles, and storage](docs/BRAMHA_PRODUCT_AND_STORAGE.md) for the current exploration flow and migration boundaries.

## Quick start (no external keys)

Tested with Node **23.10.0**, npm **10.9.2**, Python **3.11.4**, and macOS arm64. Use Python 3.11+ and a Node version supported by the pinned Vite release (Node 22.12+ or a current supported release recommended). Browser and Python dependencies are pinned in `frontend/package-lock.json` and `backend/requirements.txt`.

From `variant-atlas/`:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp .env.example backend/.env
backend/.venv/bin/python scripts/acquire_pten.py
backend/.venv/bin/python scripts/seed_research.py
```

Terminal 1 — **backend**, port 8000:

```sh
cd variant-atlas/backend
.venv/bin/python -m app.server
```

Terminal 2 — **frontend**, port 8500:

```sh
cd variant-atlas/frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:8500**. API schemas and interactive API documentation: **http://127.0.0.1:8000/docs**. If already inside `variant-atlas/`, omit that prefix in the `cd` commands.

No MongoDB or LLM credentials are needed. Local mode also seeds a fresh store automatically on first startup. The explicit seed command is idempotent: it refreshes fixture entities and retains investigations. Regenerate the tracked fixture with:

```sh
backend/.venv/bin/python scripts/seed.py --write-fixture
```

This development milestone has no authentication, authorization or multi-user isolation. The implemented local profile requires a loopback `BACKEND_HOST` such as `127.0.0.1`; the frontend development server is also local. This is not a production hosting setup.

## Live investigation chamber

The **Start investigation** action now opens the glass execution chamber with real backend events, worker inspection, source docks, output tray, cancellation and recorded replay. Use **Preview simulated chamber** for a labelled, key-free recording. [Chamber guide and API contracts](CHAMBER.md). The original synchronous API remains available.

## Historical synthetic demonstration walkthrough

The following walkthrough describes `/developer/demo`, not the production Home page. For project creation, central Sources, method-specific exploration and canonical investigation detail, follow the [current workflow guide](docs/RESEARCH_WORKFLOW_ROUTES.md).

1. Default arbitrary criteria: abundance **≥ 0.70**, activity **≤ 0.35**. Five IDs qualify: `demo-v01`, `demo-v02`, `demo-v05`, `demo-v06`, `demo-v08`.
2. Select **Mapped only**. Exactly `demo-v01`, `demo-v02`, `demo-v05` qualify. All eight table rows remain visible; excluded markers are dimmed.
3. Click a table-row variant button or a sphere to synchronize selection and evidence. The camera moves smoothly to mapped selections; it does not simulate biological motion. Keyboard users can Tab to a variant button and press Enter.
4. Switch **Activity / Abundance**. Warm-to-teal colour scale maps artificial values from 0 to 1; grey is missing. `demo-v07` has missing activity, never zero.
5. Open **Neighbours**. Adjust the radius in demo coordinate units. Distances are Euclidean, exclude self and ignore unmapped markers. `demo-v06` has missing coordinates; `demo-v08` is outside coverage.
6. Check or uncheck matching rows to curate the shortlist. The inspector button does the same. Filter changes reset the shortlist to the newly matching set. Empty investigations are allowed and explicitly recorded.
7. Enter the research question, candidate capacity and investigation title. Curate the shortlist within capacity: exceeding it blocks the run and never silently ranks or discards candidates. Choose explanation mode and press **Start investigation**. The asynchronous backend runs the checks, streams structured events and saves the result. Inspect workers in the chamber, then open the saved review brief from its output tray. Timelines contain actual completed steps, not model reasoning.
8. Read per-variant decision notes: supplied synthetic observations, calculated inclusion rationale, unresolved question, alternative explanation and planning-level follow-up approach. The source snapshots and omitted-candidate reasons are included. Hypotheses and proposed approaches remain unverified.
9. Download **Export Markdown**, reload and reopen the saved investigation. Saved snapshots keep their original criteria independently of the currently edited workspace; **Restore run criteria** explicitly restores them.

The viewer supports orbit, zoom, reset and optional slow rotation. User interaction stops idle rotation. Reduced-motion preferences disable rotation and snap camera navigation. WebGL failure leaves the table, evidence, investigation and export paths available. At narrow widths, the viewer and drawer stack; the table scrolls horizontally within its own container.

## Repository layout

```text
variant-atlas/
  frontend/                 # Own npm dependencies, Vite server, TS build and browser tests
    src/components/         # StructureViewer adapter, table, evidence and investigation views
    src/lib/api.ts          # Typed HTTP client; no provider SDK or secrets
    e2e/
  backend/                  # Own Python venv, requirements and FastAPI server
    app/analysis.py         # Deterministic filtering and spatial tools
    app/workflow.py         # Bounded, persisted workflow and Markdown export
    app/repositories/       # One repository contract; local and Atlas implementations
    app/llm/                # ResearchExplainer contract, fixture and OpenRouter adapters
    tests/
  data/fixtures/workspace.json
  scripts/seed.py
  var/                      # Ignored local state, created at runtime
```

The frontend does not access MongoDB or OpenRouter. Vite proxies `/api` to `127.0.0.1:8000`. For separate hosting, configure the frontend's **non-secret** `VITE_API_BASE_URL` at build time and the backend's `CORS_ORIGINS`. `npm run preview` serves static production assets but does not configure an API proxy; set `VITE_API_BASE_URL=http://127.0.0.1:8000` when building for that setup and add its origin to CORS. A production deployment needs authentication, secure secret management and an appropriate serving configuration; it is outside this local milestone.

## Backend configuration

Copy `.env.example` to `backend/.env`. Environment files are ignored. Configuration precedence is process environment > `backend/.env` > root `.env` > defaults. Reading configuration does not mutate process environment; tests can explicitly override the provider to mock. The supplied live credential is stored only in the private, git-ignored `backend/.env` with file permissions `0600`. Do not create frontend variables for provider credentials.

- `BACKEND_HOST=127.0.0.1`, `BACKEND_PORT=8000`: consumed by `python -m app.server`.
- `FRONTEND_ORIGIN=http://localhost:8500`: sets the allowed browser origin (with the matching localhost/127.0.0.1 alias). Vite reads only the non-secret server/origin settings to use frontend port 8500 and proxy API calls to backend port 8000. `CORS_ORIGINS` can explicitly override the origin allowlist.
- `DATA_BACKEND=local`: fixtures plus durable JSON files under `var/`, or `LOCAL_DATA_DIR` if specified. Uses temporary files, `fsync` and atomic replacement. **Local development only**; research/portfolio stores use locks and atomic snapshots, with no cross-file transaction. Do not run multiple workers against this store.
- `DATA_BACKEND=atlas`: uses PyMongo for core workspace entities and investigations. Requires `MONGODB_URI` and `MONGODB_DATABASE`. A connection/seed failure returns 503, with no local fallback.
- `LLM_PROVIDER=mock`: deterministic extractive fixture explanation, explicitly labelled **not AI**.
- `LLM_PROVIDER=openrouter`: requires `OPENROUTER_API_KEY` and an explicit `OPENROUTER_MODEL`. The model is configurable, not assumed to be available.
- `LLM_TIMEOUT_SECONDS`: clamped to 1–120 seconds per request.
- `LLM_MAX_OUTPUT_TOKENS`: clamped to 256–4000.
- `LLM_MAX_STEPS`: 1–6; this milestone performs at most **two** provider calls (initial + one repair), tightened to one if this setting is one. It is not an autonomous tool-use budget yet.

### OpenRouter (optional)

1. Check the account's current [model catalog](https://openrouter.ai/models) and [integration documentation](https://openrouter.ai/docs/quickstart); select a supported model available to that account.
2. Set provider, key and exact model ID in `backend/.env`, then restart the backend.
3. Run an investigation with **Configured** explanation. The UI/export identifies the provider, configured model and actual result mode. The browser receives no credential.

Only selected records and their fictional evidence go to the model. Responses must match the narrative schema. Findings are deliberately **extractive** in this milestone: exact supplied evidence text with verified in-scope variant/source relationships. Free-form numerical assertions in other narrative fields are rejected; numeric measurements come from deterministic tools. Unknown references, unlabelled hypotheses and missing synthetic-data limitations are rejected. This is narrower than a free-form scientific claim verifier and does not establish scientific correctness. A single repair is allowed for invalid output; authentication/rate-limit/timeouts produce an explicit saved `llm_error` result. The deterministic shortlist remains available. **Fixture mode must be selected explicitly** to bypass a failed provider; it is never silently substituted.

Provider success, invalid JSON, repair limits, reference checks, HTTP errors and timeout handling are tested with a simulated HTTP transport. The configured `x-ai/grok-4.3` model was found in the live OpenRouter catalog and returned a successfully validated explanation using only synthetic records. This verifies provider integration, not scientific accuracy. Use `backend/.venv/bin/python scripts/check_llm.py` to check configuration/catalog. Adding `--explain` makes a bounded live generation call (initial response plus at most one repair), so run it deliberately. The script never logs keys or raw provider error bodies.

Future R1/Gemini implementations belong behind `ResearchExplainer`; they are not implemented or claimed here. OpenRouter-only use does not satisfy the Argon competition requirement.

### MongoDB Atlas (optional)

1. Create an Atlas deployment, a database user and appropriate network access. Keep the connection string only in the backend environment.
2. Set `DATA_BACKEND=atlas`, `MONGODB_URI`, `MONGODB_DATABASE`.
3. Run `backend/.venv/bin/python scripts/seed.py` from the repository root with those settings.
4. Start/restart FastAPI. Verify `GET /api/health` reports `storage: atlas`, `storage_ready: true`; perform a saved investigation and retrieve it after restart.

Seeding provisions ordinary application-ID and workspace indexes and stores separate collections: `workspaces`, `proteins`, `variants`, `assays`, `measurements`, `structures`, `evidence`, `investigations`, `reviews`, `runs`. Database-generated `_id` values are omitted from API serialization. Fixture reseeding does not remove investigations. Save/exported numeric results, selected variant records and evidence records are persisted as snapshots. New exports are stable if the workspace is reseeded or edited. Older investigations remain readable with default fields but need rerunning to gain decision notes and source snapshots. This is not a full dataset revision manager.

**Live Atlas persistence was not verified without supplied credentials. Atlas Search/Vector Search/hybrid retrieval are deferred.** Ordinary PyMongo indexes are not Atlas Search. This local prototype does **not** satisfy the MongoDB competition track until a real supported search feature is implemented and its query succeeds on Atlas. Follow [MongoDB's hybrid retrieval documentation](https://www.mongodb.com/docs/vector-search/hybrid-search/vector-search-with-full-text-search/) when progressing that milestone.

## APIs

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Storage/readability and configured LLM status, no credentials |
| GET | `/api/workspace` | Typed synthetic workspace and separate fixture entities |
| POST | `/api/analyze` | Criteria, exact matching IDs, counts and reasons for every variant |
| GET | `/api/variants/{id}` | Measurement, source and mapping detail |
| GET | `/api/variants/{id}/neighbors?radius=12` | Mapped marker distances, or explicit unavailable state |
| POST | `/api/investigations` | Run, validate and save an investigation |
| GET | `/api/investigations` | List saved investigation summaries |
| GET | `/api/investigations/{id}` | Retrieve a saved snapshot |
| GET | `/api/investigations/{id}/export` | Markdown attachment |

Thresholds are finite values in [0,1]. Neighbour radius is finite and >0, ≤100. Unknown IDs return 404. Invalid/out-of-filter shortlist IDs return 422. Configured storage failures return controlled errors. `GET /api/health` checks configuration/readability, not whether an external LLM call will succeed.

## Verification

From `variant-atlas/`:

```sh
backend/.venv/bin/python -m pytest -q -c backend/pytest.ini backend/tests
npm run build --prefix frontend
```

For the full browser flow, install Chromium once and run:

```sh
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright starts its own backend and frontend on ports 8000/8500; stop development servers before running the suite. It explicitly forces mock mode and an empty provider key, overriding private `.env` configuration. Its backend uses an isolated `variant-atlas-e2e` directory under the operating system's temporary directory. Playwright refuses to reuse an existing server, preventing browser tests from accidentally invoking the live provider. An optional `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` selects an existing compatible Chromium executable. Browser tests cover the end-to-end shortlist/export flow, keyboard selection, empty results, WebGL-unavailable fallback and narrow/reduced-motion layouts.

The Python test suite verifies research context, capacity enforcement, source-snapshot stability, environment precedence, origin handling, default/mapped filters, missing values, sequence-reference consistency, geometry distances, response validation, persistence across app restart, reseeding, export labels, provider reference/numeric guards, error modes and secret exclusion. No external service is required.

## Implemented / deferred

Implemented: structure-led responsive workspace, deterministic synthetic scene, linked marker/table/evidence selection, editable criteria and null handling, curated shortlist, neighbour checks, colour legend, motion controls, WebGL fallback, local persistence, saved timeline, research question/capacity enforcement, per-variant decision notes, immutable source snapshots, exclusion reasons, export, OpenRouter adapter and Atlas repository.

Deferred by the brief: real PTEN/MaveDB ingestion and audited joins, real mmCIF/Mol* molecular rendering, validated assay calibration, Atlas text/vector/hybrid search, authentic Gemini/Argon invocation, bounded model-chosen scientific tools, shared reviews, a production job queue, authentication and expert evaluation. These are meaningful later milestones, not simulated working features.

Before entering a competition, confirm build timing and current rules. This repository is prototype implementation; do not represent it as code written after a future kickoff. No pre-kickoff eligibility claim is made.

The molecular hero includes an [agent research workbench](docs/AGENT_RESEARCH_WORKBENCH.md): model-prioritized, executable PTEN comparisons with verified before/after measurements, linked molecular selection, undo, export, and handoff to the research agent.

New investigations also support [live scenario exploration](docs/LIVE_SCENARIO_EXPLORATION.md): up to ten ranked directions, scoped agents, discoverable tools, evidence-linked path changes and inspectable outcomes.

The [visual research companion](docs/VISUAL_RESEARCH_GUIDE.md) explains selected residues, suggests grounded comparison paths, connects prior investigations, and replaces JSON-first checkpoints with plots, coverage graphics and visual replay. Both authentic and synthetic workspaces have contextual exploration and return navigation.

Branding and color themes: [preview, reusable assets and implementation notes](docs/BRAND_AND_THEME.md).

Argon now has a configured OpenRouter fallback: [behavior, provenance and verification](docs/MODEL_FALLBACK.md).

### Connected research workspace

See [the visual workflow and implementation guide](docs/RESEARCH_WORKSPACE_V2.md) for title-based biological suggestions, searchable public references, online evidence, saved structural proposals, the cited assistant, investigation sizes and storage details.

### Research Observatory and Atlas public corpus

Open **Live research** to watch a saved, bounded multi-agent expedition, or **Worldwide studies** to search published work and inspect source-linked molecular references. Projects link to both views, and project Results includes its public expeditions. The public evidence guide is separate from the executing research team.

See [Research Observatory implementation and walkthrough](docs/RESEARCH_OBSERVATORY_IMPLEMENTATION.md) for the connected flow, actual data counts, Atlas collections, model fallback, public-data expansion and verified limits. [The implementation plan](docs/RESEARCH_OBSERVATORY_PLAN.md) records the design. Existing local projects remain intact; the public corpus and new expedition records use `CORPUS_BACKEND=atlas`. The separately approved local-file backup is additive, rather than continuous project synchronization.

## Executable investigation upgrade

See [the delivery walkthrough and feature matrix](docs/EXPERIMENT_ANALYSIS_DELIVERY.md) and [the operation execution audit](docs/EXPERIMENT_EXECUTION_AUDIT.md) for the real-data baseline/follow-up, autonomous team handoffs, geographic map and supplied-structure alignment.

The separate [MongoDB & Data console](docs/MONGODB_DATA_CONSOLE.md) shows live corpus counts, inspectable documents, storage flows, vector/backup status and the local workspace inventory at `/data`.

Library sources now open a [visual evidence and saved-results view](docs/LIBRARY_VISUAL_EVIDENCE.md), with sequence/coordinate gaps, amino-acid annotations, frozen computation results and failure history.
