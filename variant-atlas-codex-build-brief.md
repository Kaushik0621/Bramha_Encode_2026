# Variant Atlas — Codex prototype build brief

Draft · 23 October 2026

## 1. Instructions to the coding agent

Build a runnable local web application from this brief. Use **React + TypeScript for the frontend and Python + FastAPI for the backend**. The first milestone is a beautiful, interactive 3D research demonstration using deterministic dummy data. Implement that before external scientific integrations. Do not stop at a landing page, screenshots or a plan. Deliver working code, setup instructions, a seed command and the acceptance checks below.

The user has OpenRouter API credentials, to be supplied through the backend environment. Never request a key in source code or place it in frontend variables. Do not assume access to Atlas, a particular model or scientific APIs. The application must run without any external key using an explicitly labelled fixture mode.

## 2. What the application does

A researcher explores protein-altering variants, compares abundance and activity measurements, inspects their locations on a protein, and generates an evidence-backed follow-up shortlist. The UI has one workspace, not a marketing website. The initial dataset is synthetic and demonstrates behaviour only. It does not establish actual PTEN variant effects.

Primary demo task: **Find variants with demo abundance >= 0.70 and demo activity <= 0.35, inspect their structural neighbours, and prepare a reviewable shortlist.** Both thresholds are arbitrary demo criteria. Display them and allow editing. Never call them clinical cutoffs or a validated research ranking.

## 3. Scope

Build now:

- One seeded workspace and one synthetic protein-like structure.
- Eight fixture variants, two synthetic assay types and four fictional evidence records.
- Interactive 3D selection, filtering and a synchronized table.
- Deterministic analysis and a shortlist builder.
- Optional OpenRouter explanation of supplied evidence.
- Persisted investigations and a Markdown export.

Later: real PTEN data, authentic molecular ribbon rendering, validated sequence mapping, Atlas hybrid retrieval, richer tool use and expert evaluation. Do not build whole-genome ingestion, molecular dynamics, docking, drug recommendation, a mutation-induced folding animation or laboratory execution.

## 4. Visual direction — a core requirement

Make the product feel like a premium scientific instrument. Use a deep navy background, restrained cyan/teal highlights, warm amber for uncertainty, legible typography and thin borders. Avoid generic dashboard cards covering the canvas, excessive bloom, floating decorative DNA and random particles. Build a distinctive structure-led workspace.

Desktop layout:

- Top bar: product name, workspace selector, “Synthetic demo” badge, storage mode and model status.
- Left rail: editable assay thresholds, mapped/unmapped filter, evidence completeness and saved investigations.
- Centre: large 3D canvas with orbit controls, reset view, colour-layer legend and camera focus on selection.
- Right drawer: selected variant, assay measurements, mapping status, evidence and proposed follow-up questions.
- Bottom: linked variant table and collapsible investigation timeline.

Interaction requirements:

- Click a marker or a table row: select the same variant everywhere and move the camera smoothly.
- Hover: show a concise accessible tooltip. Keyboard/table interaction provides an equivalent selection path.
- Switch activity/abundance layer: recolour by the selected measurement with an explicit legend; missing values use grey, never zero.
- Filter: dim excluded markers without losing the current selection; indicate if the selected row is outside the filter.
- Inspect neighbours: highlight mapped markers within a configurable radius in demo coordinate units.
- Provide controls to pause idle rotation and respect prefers-reduced-motion. Stop idle rotation after user interaction.
- Use small, purposeful transitions. A camera animation must not imply a molecule is physically changing.
- At narrower widths, stack the canvas and evidence drawer; keep the table usable.
- If WebGL fails, retain the table, evidence and a clear viewer-unavailable state.

Use React Three Fiber + Drei for the synthetic scene. Render a deterministic curved backbone with marker spheres; label it **“Illustrative geometry — not a biological structure.”** Use local assets, no network dependency for the first demo. Introduce a StructureViewer adapter so Mol* can replace this renderer for real mmCIF data later. Do not attempt to invent a PTEN fold with Three.js.

## 5. Minimal architecture

Frontend: React, TypeScript, Vite, React Three Fiber/Drei and a small query/state layer of the implementer's choice. Backend: FastAPI, Pydantic, httpx and pytest. Pin dependencies after confirming compatible versions. Add a README with the tested Python/Node versions and exact commands.

Flow: React -> FastAPI -> analysis tools / research repository / LLM adapter. The browser never talks directly to OpenRouter or Atlas.

Persistence modes:

- `DATA_BACKEND=local`: JSON fixtures plus durable local investigation files. Suitable only for development; use atomic writes and document single-process limits.
- `DATA_BACKEND=atlas`: use MongoDB via its supported Python driver. Seed the same fixtures, and read/write core workspace state through Atlas. A configured Atlas failure must show an error, not silently switch to local mode.

Implement a small repository interface, not two separate application code paths. The final MongoDB challenge build requires working Atlas persistence and at least one actual listed Atlas search feature; a local demo or unimplemented adapter does not satisfy it.

## 6. Fixture data contract

Use `DEMO-PROT-001`, a fictional 120-position protein-like sequence. Generate coordinates deterministically for positions 1–110, except position 95 which is deliberately missing. Generate an artificial reference sequence and ensure every mapped fixture's reference amino acid matches it. These positions and scores are fabricated and must not be presented as PTEN observations.

Two assay records: `assay-abundance-demo` and `assay-activity-demo`. Both use an artificial 0–1 scale where higher means more of the measured property. This shared scale is a demo simplification, not a claim that real assays are interchangeable. Evidence is explicitly fictional, with IDs `demo-evidence-01` through `demo-evidence-04`; use internal document panels, not fake publications or real journal links supporting invented findings.

| Variant ID | Position | Abundance | Activity | Mapping | Expected default selection |
| --- | ---: | ---: | ---: | --- | --- |
| demo-v01 | 12 | 0.92 | 0.18 | mapped | yes |
| demo-v02 | 28 | 0.82 | 0.25 | mapped | yes |
| demo-v03 | 44 | 0.20 | 0.12 | mapped | no |
| demo-v04 | 60 | 0.90 | 0.88 | mapped | no |
| demo-v05 | 76 | 0.74 | 0.30 | mapped | yes |
| demo-v06 | 95 | 0.81 | 0.20 | missing coordinates | yes, unmapped |
| demo-v07 | 108 | 0.77 | null | mapped | no, insufficient measurement |
| demo-v08 | 118 | 0.91 | 0.22 | outside structure coverage | yes, unmapped |

With default thresholds and no mapping filter, return exactly v01, v02, v05, v06 and v08. With mapped-only enabled, return v01, v02 and v05. Null activity must never become zero. Keep all unmapped candidates in the table; do not silently drop them.

Suggested entities:

```json
{
  "variant": {
    "id": "demo-v01", "protein_id": "DEMO-PROT-001",
    "position": 12, "ref": "<from artificial reference sequence>",
    "alt": "<different valid amino acid>", "synthetic": true,
    "mapping_status": "mapped", "evidence_ids": ["demo-evidence-01"]
  },
  "measurement": {
    "variant_id": "demo-v01", "assay_id": "assay-activity-demo",
    "value": 0.18, "synthetic": true
  }
}
```

Separate variants, measurements, assays, structures, evidence and investigations. Each investigation records filters, selected IDs, tool outputs, source IDs, dataset version, model/provider, timestamps and result mode. Use stable application IDs; serialize database IDs safely.

## 7. Backend endpoints and tools

Implement:

- `GET /api/health`: storage and LLM configuration status; never reveal secrets.
- `GET /api/workspace`: fixture metadata, variants, assays, evidence and structure coordinates.
- `POST /api/analyze`: validate thresholds; return matching IDs, mapped/unmapped counts and reasons.
- `GET /api/variants/{id}`: measurements, evidence and mapping details.
- `GET /api/variants/{id}/neighbors?radius=...`: deterministic Euclidean distances, excluding self; unmapped variants return an explicit unavailable status.
- `POST /api/investigations`: run the bounded workflow below and save the result.
- `GET /api/investigations/{id}`: retrieve a saved investigation after restart.
- `GET /api/investigations/{id}/export`: download a Markdown brief with criteria, evidence, limitations and mode.

Use typed request/response schemas, useful validation errors, constrained numeric ranges, local-development CORS and controlled error responses. Unknown IDs return 404.

Minimal workflow: validate input -> filter variants -> check mapping/measurement coverage -> collect evidence -> optionally request an LLM narrative -> verify returned IDs/claims -> save. This first milestone is a deterministic workflow with optional AI explanation; do not label it an autonomous scientific discovery agent. Display actual completed steps, not a fabricated thinking transcript.

For the later agent milestone, expose allowlisted tools such as `filter_variants`, `get_variant_evidence`, `get_spatial_neighbors` and `validate_shortlist`. The model can choose and revise calls under a step/time budget. No arbitrary shell, code execution or internet browsing is needed.

## 8. LLM provider plan

Implement a provider-independent `ResearchExplainer` interface with mock and OpenRouter adapters. Future R1-family or required Gemini adapters should not change domain logic or response contracts. “R1” is a future configuration target, not a confirmed exact model identifier. Verify the account's available models and supported capabilities before selecting one. Do not assume Gemini-specific settings work through OpenRouter.

Backend `.env.example`:

```dotenv
DATA_BACKEND=local
MONGODB_URI=
MONGODB_DATABASE=variant_atlas
LLM_PROVIDER=mock
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_TIMEOUT_SECONDS=45
LLM_MAX_OUTPUT_TOKENS=1500
LLM_MAX_STEPS=6
```

Use server-side `POST /chat/completions` with Bearer authentication, an explicitly configured model and a bounded response. Model availability can be checked against OpenRouter's models catalog. Support plain JSON responses with validation when native structured outputs are unavailable. Do not force unsupported parameters or depend on exposing model reasoning.

Expected validated narrative object:

```json
{
  "summary": "...",
  "findings": [{"variant_ids": ["demo-v01"], "text": "...", "evidence_ids": ["demo-evidence-01"]}],
  "hypotheses": [{"text": "...", "status": "unverified"}],
  "follow_up_questions": ["..."],
  "limitations": ["Synthetic measurements and illustrative geometry"]
}
```

Provide only selected records and supplied evidence to the model. Require hypotheses to be labelled. Reject unknown source/variant IDs and numerical assertions that disagree with tool outputs. These checks do not guarantee scientific correctness; retain reviewer responsibility. The model cannot change the deterministic shortlist. Treat evidence text as data, not instructions. Use at most one repair attempt for invalid output. On timeout, 401, 429 or invalid JSON, show an honest error and the still-available deterministic results; offer explicit fixture mode rather than silently inventing an AI response. Never log API keys or return them to the frontend.

For competition delivery, add and actually demonstrate the required `gemini-4-argon` provider configuration according to the supplied brief. OpenRouter or future R1 use alone does not meet that Google requirement. Confirm permitted build timing and official rules before competition implementation.

## 9. Real-data migration: where to obtain it

| Source | Starting point | Intended use | Gate before integration |
| --- | --- | --- | --- |
| MaveDB | https://mavedb.org/genes/PTEN | Variant functional scores and assay metadata | Download a small activity/abundance slice; check score direction, versions, overlap and terms |
| PTEN study | https://pmc.ncbi.nlm.nih.gov/articles/PMC8518224/ | Methods and interpretation context | Distinguish published observations from our hypotheses |
| RCSB PDB | https://www.rcsb.org/structure/1D5R | Experimental structure | Inspect chains, engineered construct, numbering and missing coordinates |
| UniProt | https://www.uniprot.org/ | Reference sequence and accession | Pin accession/isoform/version and align with assay targets |
| ClinVar | https://www.ncbi.nlm.nih.gov/clinvar/ | Optional submitted classifications | Preserve condition, accession, review status, date and conflicting submissions |
| Ensembl VEP | https://www.ensembl.org/info/docs/tools/vep/index.html | Later DNA-to-transcript/protein annotation | Pin genome build, transcript and tool version |

Do not fetch a full genome or all ClinVar to build this demo. Start from a small, reproducible downloaded slice. Record source URL, retrieval date, dataset release, license/terms, checksum and transformation version in a manifest. Do not invent unverified API endpoints; use current documented download methods. Cache allowed assets so the demo does not require live scientific APIs.

Audit the joins before rendering real data: exact substitution -> assay target sequence -> reference protein -> structure chain/residue. Handle offsets, insertion codes, alternate isoforms, unresolved residues and reference mismatches. Reject ambiguous mappings. A protein-level assay must not be presented as measuring a particular DNA allele unless that link is established. Real activity and abundance comparisons need assay-specific interpretation and documented calibration; do not carry over the dummy thresholds.

Mol* becomes the real-structure renderer. Preserve measured, experimentally determined, calculated and predicted labels. Never present a reference structure as a validated mutated structure. Existing MaveDB already offers 3D effect views; our intended differentiation is the verified investigation-to-follow-up workflow, not a unique molecular viewer.

## 10. Atlas rollout

Initial collections: `workspaces`, `proteins`, `variants`, `assays`, `measurements`, `structures`, `evidence`, `investigations`, `reviews`. Add ordinary indexes for application IDs, workspace and exact variant/assay lookups. Atlas remains the core database when enabled; keep large raw assets in object storage with hashes and references.

After deterministic lookup works, add Atlas Search on evidence titles/text and identifiers, Vector Search on research-text embeddings and hybrid retrieval combining the two with gene/assay/source filters. Optional Voyage embeddings belong behind an embedding adapter with model/version metadata. Do not use prose embeddings to match DNA identities or infer biological equivalence. Implement index provisioning instructions, a seed command and one demonstrable search query. Do not claim a search feature works until its actual Atlas query succeeds. No Stream Processing unless a genuine live ingestion task is added.

## 11. Recommended repository layout

```text
variant-atlas/
  frontend/src/
    components/StructureViewer.tsx
    components/VariantTable.tsx
    components/EvidenceDrawer.tsx
    components/InvestigationPanel.tsx
    lib/api.ts
    types.ts
  backend/app/
    main.py
    schemas.py
    analysis.py
    workflow.py
    repositories/
    llm/
  backend/tests/
  data/fixtures/
  scripts/seed.py
  .env.example
  README.md
```

## 12. Build order and definition of done

1. Seed deterministic data and build typed analysis APIs.
2. Build the polished canvas, linked table and evidence drawer.
3. Add local persistence, restart retrieval and Markdown export.
4. Add optional OpenRouter explanation with validated responses.
5. Add Atlas persistence and documented seeding when credentials are available.
6. Only then begin real PTEN joins, Mol* rendering and search integrations.

Acceptance checks:

- Fresh checkout runs with documented commands and no external keys.
- Default filters produce exactly the five expected IDs; mapped-only produces the three expected IDs.
- Missing measurements and missing geometry remain distinct, visible states.
- Selecting table/3D items stays synchronized; colour changes match the legend.
- Neighbour distances match known fixture coordinates and exclude the selected variant.
- A saved investigation survives a backend restart, including criteria and evidence references.
- Exported Markdown includes the synthetic-data and illustrative-geometry labels.
- Mock mode is labelled. OpenRouter success is labelled with the configured model. API failure does not become a fake success.
- Atlas mode persists to Atlas and surfaces connection failures honestly.
- Unit tests cover filtering/nulls/mapping, geometry, persistence and invalid model references. One browser flow covers filter -> select -> investigate -> export. Do not add tests that only mirror component markup.
- No keys appear in browser bundles, network responses or git-tracked files.
- No button is decorative: implement it, disable it with an explanation, or remove it.

Deliver the working repository, exact startup/seed/test commands, a short list of implemented versus deferred features and any known limitations. Do not describe dummy-data results as research discoveries.

## References

- OpenRouter integration: https://openrouter.ai/docs/quickstart
- MaveDB visualizations and existing 3D functionality: https://www.mavedb.org/docs/mavedb/finding-data/visualizations.html
- MaveDB data access: https://www.mavedb.org/docs/mavedb/finding-data/index.html
- MongoDB hybrid retrieval: https://www.mongodb.com/docs/vector-search/hybrid-search/vector-search-with-full-text-search/
