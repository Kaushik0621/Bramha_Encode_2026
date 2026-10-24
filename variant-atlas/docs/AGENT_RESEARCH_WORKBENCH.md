# Agent research workbench

The molecular hero now supports **suggest → apply → verify → investigate** using the real PTEN workspace. Frontend and backend remain separate. OpenRouter/local is the active development path.

## What to try

1. Open http://localhost:8500 and find **What should we try next?**
2. Click **Ask the model to prioritize**. The configured live model ranks a bounded set of applicable plans using actual assay observations, selection, exploratory thresholds and coordinate coverage. The default cards use deterministic data tools and are labeled accordingly.
3. Click **Apply & verify** on a plan. This changes the selected cohort, recolors its mapped reference residues, focuses the structure, and changes the assay layer when appropriate. Grey residues are outside the cohort or have no measurement.
4. Inspect the before/after counts, native scores and reported standard errors, criteria results, coordinate coverage, and reference C-alpha distance. Different substitutions at the same residue share the reference coordinate; no zero-length molecular distance annotation is drawn.
5. Use **Investigate this comparison with tools & specialists** to start the existing bounded agent on the exact resulting cohort and research question. This runs real provider/tool/delegation work; it can abstain when its checks do not pass.
6. Undo the selection change or export the scenario. A changed selection, anchor, layer, criteria or dataset invalidates old proposals.

## Available research moves

| Move | Actual change | Research purpose |
|---|---|---|
| Same-position comparison | Replace cohort with two measured substitutions at one residue | Compare substitution-specific assay differences while holding reference position fixed |
| Assay contrast | Replace cohort with the closest activity-matched pair across the current abundance boundary | Distinguish descriptive measurement patterns; confounding remains |
| Add discordant measurement | Add a measured low-activity/preserved-abundance substitution | Broaden the follow-up candidate cohort |
| Remove unsupported spatial claims | Remove unmapped variants from the spatial cohort | Make coordinate coverage explicit and report exclusion bias |
| Spatial neighbor | Add an independently measured substitution at a different residue within 10 Å | Plan a reference-space comparison without asserting an interaction |

Only currently applicable moves appear. Pair plans intentionally replace the cohort; addition/removal chips disclose the exact changes before execution. A contrast need not satisfy the current shortlist criteria.

## Execution and persistence

- `POST /api/research/scenarios/suggest`: typed context; deterministic candidate generation; optional one-call model prioritization. Only an exact permutation of permitted plan IDs is accepted. Model prose is displayed as unverified interpretation.
- `POST /api/research/scenarios/apply`: proposal lookup; context fingerprint and dataset checks; regenerate permitted edits from authoritative data; recompute criteria from pinned Parquet; check mappings; calculate reference distances; persist result; return verified scene command.
- The browser checks context again before applying an asynchronous response. Model or network failures do not cause silent fallback or selection changes.
- Proposals and results are atomically saved under ignored `var/scenario-lab/`. The UI history is per session; exports are portable JSON. This feature currently uses local persistence even if another backend mode is configured.
- Numeric observations, cohort membership and scene commands come from deterministic data tools. The model ranks plans; it cannot invent measurements, execute arbitrary code, change assay thresholds, or modify the molecular backbone.

## Scientific scope

These are independently measured single amino-acid substitutions, not an experimentally measured combined mutant. Adding/removing a variant edits the research comparison, not a protein in a living system. No mutant folding simulation, rescue experiment, clinical classification, treatment effect or causal mechanism is produced. Activity and abundance scores retain separate native scales and systems; standard errors are displayed without inventing significance tests.

A successful bounded scenario does not establish that the full autonomous reference investigation has passed. Google Argon, Atlas hybrid retrieval and Live audio remain unverified without their credentials.

## Verification

`tests/test_scenarios.py` exercises actual pinned measurements, same-residue distance, coverage exclusions, persistence, stale-context/forged-action rejection, assay contrasts and bounded model output validation. The browser workbench test exercises selection changes, molecular cohort state, before/after checks, stale-plan disabling, undo and abundance view switching. `artifacts/RESEARCH_SCENARIO_LIVE.json` records one real OpenRouter planning call and execution; scripted test providers are separately labeled.
