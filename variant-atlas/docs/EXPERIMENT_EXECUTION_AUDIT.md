# Bramha Atlas — execution audit

25 October 2026. This audit follows executable code and persisted output; a catalogue entry alone is not evidence that an operation ran.

## Trace from researcher action to result

The existing PTEN path is `ReviewSheet → portfolio project start → ResearchEngine.start → durable ResearchStore queue → ResearchEngine.execute → Registry.execute → artifact/analysis result → persisted events → Chamber/AnalysisResults → saved InvestigationDetail`.

New UI investigations explicitly set `autonomous_team=true`. The research lead declares a bounded path plan. The scheduler translates it into identity validation followed by independent assay and structural teams, then cross-team reference verification. Each model reviewer has a separate provider context. Typed, version-checked internal agent messages record assignments, peer artifact handoffs and returned results. The parent awaits actual task futures; researcher follow-up is not required to progress the team. These are internal agent-to-agent task contracts, not a claim of interoperability with external A2A servers.

The deterministic reference mission is `Workspace → Quantitative analysis → review inputs → Run & save baseline analysis → /api/analysis/projects/{pid}/run → actual registry computations → immutable run/artifacts/typed analysis descriptions → linked plots/reference structure → separate one-factor follow-up`. It uses no LLM. Actual native measurements determine the selection.

## Operation audit

**Shared inputs:** pinned PTEN dataset/source versions, explicit selected substitution IDs, native assay criteria and accepted reference mappings. **Shared persistence:** original `ResearchStore` artifacts and ordered events, plus typed `analysis_results` in the same run. Exact numerical outputs remain in their originating artifacts.

| Operation / user action | Implementation and method | Inputs / preconditions | Actual output | Trigger policy | Verification / UI / status |
|---|---|---|---|---|---|
| Identity — run baseline or team | `tools/registry.py: Registry.execute(validate_variant_identity)`; compare reference residue, range, alternative identity and sequence version | Selected audited IDs and pinned canonical sequence | Accepted identities or incompatible result with rejected IDs | Required | Mismatch regression blocks mapping/filtering. Sequence-position strip and identity rows. Implemented/tested |
| Reference sequence — same mission | Registry `resolve_reference_sequence`; read immutable reference | P60484, sequence version and checksum-backed workspace | Actual amino-acid sequence and metadata | Required for identity team | Exact sequence and substitution annotation. Implemented/tested; not a DNA-allele inference |
| Assay interpretation — same mission | Registry `inspect_assay`, once per endpoint | Pinned activity/abundance dictionaries | Endpoint, system, direction, scale, controls, source methods | Required | Separate endpoint table. Implemented/tested |
| Comparability — same mission | Registry `assess_comparability`; inspect structured metadata | Shared identities; different experimental endpoints retained | Comparability record and limitations | Required | Side-by-side endpoint/system/scale/direction view. Implemented/tested; no unit merging |
| Coverage — same mission | Registry `summarize_measurement_coverage`; count observed/null values | Exact selected IDs; native observations and reported SE | Denominator, paired count and per-variant values | Required | Missingness matrix/table; unknown remains missing. Implemented/tested |
| Selection — same mission | Registry `filter_measurements` → `ScientificData.preview`; fixed SQL operators and parameterized values | Explicit native-scale rules and selected IDs | Exact matching IDs, excluded reasons and mapping counts | Required | Threshold scatterplot plus exact accessible table; CSV/SVG exports. Implemented/tested |
| Alignment audit — structural team | Registry `align_structure_reference`; **read previously audited sequence-to-construct alignment** | Pinned mapping audit and reference version | Audit, ambiguity and accepted correspondence | Required structural precondition | Mapping coverage strip/table. Implemented/tested read; does not recompute a new protein alignment on every run |
| Mapping — same mission | Registry `map_variant_residues`; audited lookup | Identity-valid IDs and accepted chain correspondence | Mapped/missing/outside-coverage status and coordinates | Required | Sequence strip and linked experimental model; unavailable positions remain visible. Implemented/tested |
| Neighborhood — quantitative mission or selected lead path | Registry `find_spatial_neighbors` → `ScientificData.neighbors`; Euclidean radius query | Accepted reference C-alpha anchor; explicit radius, default 10 Å | Neighbor IDs, distances, radius, coverage limits | Conditional on coordinates and plan | Structured artifact/table and real reference view. Missing-coordinate skip is recorded. Implemented/tested |
| Pair distance — quantitative mission or selected lead path | Registry `calculate_residue_distances` → `ScientificData.distance`; Euclidean norm | Accepted pair; deterministic stable-ID anchor order | Distance in Å, pair IDs, same-residue flag | Conditional on accepted pair | Labelled schematic connector and exact result; not a physical trajectory. Implemented/tested |
| Scenario comparison — declared follow-up | `analysis_execution.py`; recompute typed criteria and set differences; Registry also supports `compare_analysis_scenarios` | Same project, source manifest and dataset; one changed factor initially | Entered, left, unchanged IDs; exact changed input fields; baseline/result references | Explicit follow-up; no invented alternative criterion | Before/after lists and parameter diff. Actual reference case: raising activity ceiling admits Y16T; R172H remains unclassified because abundance is missing. Implemented/tested |
| Source review — explicit paper/guide/investigation action | `papers.py`, `paper_review.py`, public corpus guide and existing provider adapter | Selected original passages, identities, source version; untrusted text remains evidence | Source-linked observations, literal quotations, coverage and limits | Explicit model request or delegated evidence branch | Original-language claim cards and checked citations. Implemented; model interpretation is not experimental reproduction |
| Hypothesis revision — lead action | `ResearchEngine` action `revise_hypothesis` | Actual saved limitation/artifact triggers | Versioned hypothesis and triggering references | Conditional; no confidence number manufactured | Existing hypothesis/evidence view and reproducibility export. Implemented; execution depends on the saved run, not the tool list |
| Reference/number verification — after results | Registry `check_references`, `check_numbers`, worker finalization gates and team verifier | Existing source/artifact IDs; exact numeric paths and matching dataset | Named mechanical pass/fail checks | Required for agent finalization | Check matrix and inspectable failure outputs. Implemented/tested; does not establish scientific truth |
| Supplied-model import — Build 3D experiment | `structure_comparison.py: import_model`; Biopython coordinate parsing | PDB/mmCIF ≤8 MB, ≤150k atoms; first model, observed protein chains; uploader-provided origin | Checksummed original, chain identities, observed sequence and source/method metadata | Explicit file import | Stored model selectors and provenance. Implemented/tested |
| Supplied-model comparison — Align supplied structures | `SuppliedModels.compare` → `align_template`; Kabsch/SVD, identity-matched C-alpha pairs, no reflection | Same project; chosen chains; one-to-one author-residue or explicit correspondence; ≥3 anchors, ≥80% identity, ≥50% observed coverage; reject collinear anchors | Saved rigid transform, aligned display copy, RMSD Å, per-residue displacements, missing masks and provenance | Explicit computation | Superposition, displacement plot and exact table. Identical real 1D5R copies give near-zero displacement. Implemented/tested; differences are not automatically mutation-caused |
| Ideal residue-template exercise — optional details | `structure_lab.py: proposal`; rigid N–CA–C fit of RCSB CCD ideal template, fixed backbone and declared short-distance screen | Mapped PTEN site, actual ideal residue template, reviewed identity | Explicit unrelaxed proposal coordinates, atom changes and geometric checks | Optional, explicitly labelled | Existing reference/proposal overlay and source attribution. Implemented geometry exercise; not rotamer optimization or validated mutant folding |
| Mutant folding / rotamer search / dynamics / docking / ML training | No validated engine integrated for this mission | Unsupported | No fabricated outputs | Unavailable | Level C capability explicitly reports its blocker. No energy, stability, disease or treatment prediction is claimed |
| Inferential statistics | No supported replicate/group inference pipeline in this mission | Full compatible experimental design and suitable replicate data are not declared here | No p-values, bootstrap intervals or predictive scores | Unavailable | Native observations and reported uncertainty are retained. The app does not manufacture Prism-like inference from a list of single-variant summaries |

## What existing runs actually execute

Existing adaptive runs execute the subset of registry tools whose artifacts and events are saved. They do not execute every catalogue entry, and a proposed/parked path is not a completed calculation. Historical runs are preserved as recorded; the upgrade does not retroactively invent agents, messages, results or changed folds.

The new deterministic PTEN mission executes its required checks and records spatial operations as conditional or skipped. The new autonomous-team path executes the lead’s supported checks through independent scoped workers; failed required reviews lead to explicit abstention rather than an unchecked complete brief.

Public literature expeditions perform retrieval, original-text acquisition, literal identifier extraction, structural citation checks and bounded source review. They are evidence-review workflows; their plots of coverage and worker timings are operational summaries, not new biological measurements.

## Scientific boundaries

GraphPad Prism is statistical/graphing software. Here, quantitative graphs bind to saved measurement and calculation schemas. Molecular visualization binds to actual coordinate files. Adding a model to a view does not create binding, simulate a protein complex or perform DNA editing. See [GraphPad’s feature description](https://www.graphpad.com/features) for its distinct statistics/graphing scope.

The project’s reported synonymous-control derivation remains visible for its exploratory default boundaries. A changed selection proves a change in an analytical rule’s output; it does not demonstrate a biological cause. Tests below verify software and numerical contracts, not clinical validity.

## Verification commands

```sh
# Repository root
variant-atlas/backend/.venv/bin/python -m pytest variant-atlas/backend/tests -q
# Frontend directory
npm run build
PW_FRONTEND_PORT=8503 PW_BACKEND_PORT=8003 npx playwright test e2e/analysis-results.spec.ts
```

New numerical/schema regressions are in `backend/tests/test_analysis_network.py`; complete browser journeys are in `frontend/e2e/analysis-results.spec.ts`. The reference run, screenshots and exact counts are recorded separately in the delivery report after execution.
