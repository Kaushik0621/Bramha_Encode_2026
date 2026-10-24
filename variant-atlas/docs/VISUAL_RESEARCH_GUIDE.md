# Visual research companion

## Explore a real residue

Select a substitution in the linked table or molecular viewer, click **Explore this residue**, or zoom into the molecular region. A contextual panel opens without changing the reference protein backbone.

- **Understand** shows the sequence neighborhood, an activity/abundance profile plot, native measurements, filter boundaries, exclusion reasons and coordinate availability.
- **Explore paths** offers executable, data-grounded research comparisons and independently labels whether each alternative has both assay measurements and accepted reference coordinates. Selecting an alternative changes the inspected scientific object. Applying a comparison uses the existing versioned, stale-context-checked scenario API. Launching an investigation runs the existing bounded multi-agent workflow.
- **Prior research** shows saved investigations whose selected IDs include that exact substitution. Status, dataset version and saved findings are retained; missing checked findings are displayed as a gap, not converted into a conclusion.

Data-derived guidance loads first. With a configured provider, **Focus-aware brain suggestions** can automatically prioritize plans for a newly inspected context. Automatic requests are bounded to four per mounted companion session, at least thirty seconds apart, and once per context; the checkbox disables this behavior. Manual prioritization remains available. Camera motion does not continuously submit model requests. Old asynchronous responses cannot overwrite a newly focused context.

Only audited substitutions are offered. Missing coordinates prevent a spatial calculation, not inspection of the assay evidence. No unmeasured replacement receives a fabricated score or mutant shape.

## Understand investigation evidence

Tool outputs now default to readable experiment explanations, numeric summaries, coverage bars, paired-measurement plots, reference-distance diagrams and observation cards. Technical JSON remains under **Technical record & reproducibility data**. Evidence rows can open their real residue in split molecular/research view.

The scenario map visualizes the ranked research directions and their actual states. Clicking a direction opens a side inspector with its question, rationale, capability steps, actual artifacts and outcome. Runtime identifiers are translated into readable labels in explanatory text. Agent judgments remain distinct from verified calculations.

## Replay a run

Use **Replay**, **Pause**, previous/next controls, the event slider or named milestones to revisit actual saved work. A caption explains the current checkpoint. Evidence and path states remain scoped to the selected event; **Return to live state** restores the newest snapshot. Playback never starts research or changes a saved result.

## Explore the synthetic workspace

The synthetic workspace retains its fabricated data and illustrative geometry. Brighter excluded markers and direct substitution buttons make all eight records discoverable. Selecting a marker/table row or zooming opens a synthetic companion with fictional measurement comparisons, filter explanations, coverage limits and linked fictional evidence. **Broaden filters** explicitly adjusts the current criteria to include a measured excluded profile. Missing assay values cannot be manufactured to include it.

The synthetic companion's guidance is data-derived and labeled accordingly. Launching an investigation uses the existing selected explanation mode. Workspace-level prior investigation counts are not presented as residue-specific findings.

The real workspace header links back to Variant Atlas's synthetic workspace, and the synthetic header/companion link back to authentic PTEN research.

## Verification

The backend context endpoint is tested against actual pinned PTEN data, same-position alternatives, separate assay/geometry readiness, prior abstention records and stale-dataset refusal. Browser tests cover residue selection, zoom focus, alternative inspection, visual evidence, replay, synthetic comparisons and navigation. An explicitly scripted provider test verifies focus-aware request bounding without spending API credits in the suite.
