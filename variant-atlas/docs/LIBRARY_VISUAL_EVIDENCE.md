# Library: visual evidence and saved results

25 October 2026. The default source detail view now explains the scientific content and the work performed with it, rather than opening on catalogue metadata.

[Open the PTEN reference source](http://localhost:8500/library/source-0203a062c04753d97740e906). Metadata remains under **Overview & provenance**; the original reader, versions and linked work remain available.

## Walkthrough

1. Open a source from Library or project Evidence. **Visual evidence & results** is selected by default.
2. For a supported PTEN source, inspect the experimental reference alongside the amino-acid change inspector. Sequence and structure references are separately linked and versioned.
3. Search a loaded substitution, such as C124S or R172H, or click any reference-sequence position. The amino-acid identities, available measurements and coordinate status update together.
4. Select an unmapped position to see the exact audit reason. The reference remains visible; a coordinate is not invented. Missing assay observations stay marked **Not measured**.
5. Follow **Show completed work** to the saved investigations that pin this exact source version. Choose an investigation to inspect its actual tool results, output changes, observations and failures.
6. A saved one-factor follow-up shows entered, left and unchanged candidates, together with the before/after criterion. Clicking a plotted substitution selects the matching source position when dataset versions are compatible.
7. Inspect the failure ledger and verification history. Tool preconditions, missing coordinates, worker failures, provider attempts and failed numeric/reference checkpoints are distinct. Earlier failed checks are not automatically labelled as unresolved final failures.
8. Open the complete saved result to continue the investigation. If no investigation uses this version, the page explicitly shows that no work is saved and offers linked projects or a new research setup.

The selected residue, substitution, operation and investigation are retained in URL parameters. Opening a source citation preserves its originating investigation instead of switching to a different saved run. Ordinary navigation, clicking positions and inspecting saved evidence do not start a model or new experiment.

## What the visual evidence means

| View | Source of values | Meaning and limitation |
|---|---|---|
| Experimental 3D reference | Actual pinned 1D5R coordinates | Structural context; not a newly generated mutant fold |
| Amino-acid pair | Pinned reference sequence and an actually loaded substitution record | Original → alternative amino-acid identity; not a uniquely determined DNA edit |
| Sequence and coverage map | Audited reference-to-construct mapping | 403 reference positions: 307 accepted mappings, 15 missing coordinates and 81 outside coverage |
| Unresolved construct count | Mapping audit | Two construct positions have no accepted reference assignment; these have a different denominator from reference coverage |
| Measurement coverage bars | Actual non-null values in the 131 loaded workspace profiles | Loaded workspace scope, not the entire public measurement corpus or participant genotypes |
| Saved operation plots | Frozen investigation artifacts | Exact original-scale calculations; no LLM-generated plot values |
| Before/after selection | Saved baseline-comparison record | Analytical set differences and declared input changes; not biological causation |
| Failure and verification history | Actual tool outcomes, task states, provider usage and verification artifacts | Mechanical execution and evidence limitations; not a clinical verdict |

For a paper, the visual source view instead shows original-language extraction coverage, passage navigation, original text and saved work. Generic background evidence uses its recorded passage and coverage. No molecular model is fabricated for unsupported material.

## Version and data integrity

`GET /api/source-visuals/{source_id}` assembles the source-content summary and a bounded list of exact-version investigations. `version` and `project` can restrict the view. Unknown historical versions return an explicit unavailable result; current molecular content is not silently substituted. Current source context and historical run plots stay separate when their dataset versions differ.

The endpoint does not modify scientific run snapshots. The existing catalogue retains its normal metadata reconciliation behavior. No source inspection triggers ingestion, paid inference or new computational analysis.

## Renderer stability

The shared structure viewer now loads its coordinate files once per input set and changes residue selection/focus within that loaded scene. Changing a residue no longer reconstructs the WebGL context or downloads the structure again. Audited author-residue identifiers are normalized to numeric coordinate identifiers, and the browser test requires a nonempty atom selection. Missing positions reset to the whole reference. Sequence, mapping and measurement views remain available if WebGL cannot run.

## Implementation and checks

- `backend/app/source_visuals.py`: source-version matching, coverage derivation, preparation/measurement/model distinctions and saved-work summaries.
- `frontend/src/workspace/SourceVisuals.tsx`: scientific source view, sequence, amino-acid comparison, frozen result adapters and failure ledger.
- `frontend/src/workspace/Sources.tsx`: default visual destination and explicit Library/Evidence links.
- `frontend/src/workspace/StructureViewer.tsx`: stable loaded-scene residue focus.
- `backend/tests/test_source_visuals.py`: exact version filtering, actual coverage/missing values, immutable runs, unavailable historical context and original-language paper behavior.
- `frontend/e2e/source-visuals.spec.ts`: molecule/sequence interactions, missing observations, saved result differences, numeric-check failure, empty states, URL restoration, mobile and no write/model requests. Synthetic failure fixtures are explicitly labelled.

Verification results and screenshots are saved in `artifacts/source-visuals/`. The complete backend suite passes 147 tests. Existing reader/theme/workspace regressions and the new source journeys were exercised; the final renderer check also verifies a single structure download across repeated residue selections.

## Focus-aware Bramha guidance

The Library molecular view now begins with the whole reference. Zoom into it, choose a sequence position, select a measured substitution or click a mapped atom to activate the adjacent Bramha molecular guide. Real camera events drive the transition; programmatic camera resets and layout changes do not select unrelated residues. The nearest accepted C-alpha position to the camera target supplies context for a zoom gesture. Unknown chain/model/object picks retain an unavailable-mapping explanation rather than receiving invented canonical identities. Re-selecting the same residue after **Show whole structure** refocuses the existing renderer without downloading the structure again.

After a short pause at the focus, three public-data tool workers run concurrently:

1. **Measurement analyst** retrieves the actual loaded substitutions at that canonical position, retaining missing activity/abundance values and separate assay scales.
2. **Geometry scout** checks the accepted coordinate mapping and computes nearby mapped reference C-alpha positions within its recorded radius. These distances do not imply a bond or predicted mutant interaction.
3. **Literature scout** retrieves related stored PTEN publications and their exact source-version passages. Only official Europe PMC and J-STAGE public-source URLs are eligible; related work does not establish an effect at the selected residue.

A **Bramha research guide** can interpret those public outputs through Argon with the configured OpenRouter fallback. The tool workers and model interpreter retain distinct engine labels, statuses and timestamps. A failed model interpretation leaves completed tool checks and their usable research actions available. The model receives public reference/assay data and public publication passages, excluding project notes, private paper uploads, patient records and saved investigations. Suggested action IDs and numeric statements are mechanically checked; semantic interpretation still requires researcher review.

The panel offers loaded measured comparisons, a selectable amino-acid replacement for the existing 3D proposal lab, and related published work. Measured activity and abundance plots use their separate original scales; missing values remain explicitly unmeasured. Choose an existing compatible PTEN project or a new project. A geometry handoff preserves the exact selected substitution, reference/dataset identity and target amino acid, then opens the proposal lab with its controls prefilled. **Build 3D proposal** remains an explicit calculation. Its ideal side-chain alignment, atom-distance checks and downloadable coordinates are separate from a prediction of folding, dynamics or biological function.

Background guidance can be paused. A source/version/dataset/position/substitution cache prevents a new model call on every scroll or repeated focus, and a short debounce avoids requests during continuous movement. Concurrent active context checks are bounded. Guidance, worker outputs, interpretation attempts and source-linked handoffs are saved in the configured corpus's `searches` collection (`bramha_searches` in Atlas). Geometry artifacts and project records retain their existing configured project storage. Handoffs reuse the same prepared project on repeated identical submissions and never silently start an investigation.

Implementation: `backend/app/molecular_guidance.py`, `frontend/src/workspace/MolecularGuide.tsx`, camera-event hooks in `StructureViewer.tsx`, and the source-view integration. Routes: `POST /api/molecular-guidance`, `GET /api/molecular-guidance/{id}`, and `POST /api/molecular-guidance/{id}/continue`.

Verification includes actual wheel input in the molecular renderer, parallel tool-worker timestamps, scoped source versions, missing measurements, unsupported action rejection, exact selected-residue handoff, pause/cache behavior and mobile layout. Public-only provenance and live model artifacts are under `artifacts/molecular-guidance/`; isolated browser examples are explicitly tool-backed tests without live model credentials. Live provider metadata states which model actually answered.

The live C124 check completed the three tool specialists and the model interpreter, with OpenRouter fallback explicitly recorded. A source-linked C124A proposal was built and saved from the selected C124S assay context: the reference side-chain heavy atoms were `CB, SG`, while the ideal alanine proposal contained `CB`. This records an ideal-template geometry exercise, not an experimentally changed protein. The comparison renderer now gives small coordinate fragments an atom-detail representation so individual proposed atoms are visible, and switches reference/proposal/overlay using a fresh renderer host. Disposal retains each old canvas's parent until Molstar cleanup completes; this prevents blank views and ResizeObserver exceptions during mode changes. Render-ready flags belong to the current scene rather than the previous canvas.
