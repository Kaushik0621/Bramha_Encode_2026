# Bramha Atlas presentation demo

Use the saved public-data runs as the default. Budget **90 seconds**. The 19-slide pitch is approximately **11 minutes plus the demo**; speaker timings total about 10½ minutes and allow transition time. For a 5-minute slot, use slides 1, 4, 7, 9, 14, 15, 16, 18 and 19, and keep the demo to 45 seconds. The full deck remains available for discussion.

## Before presenting

1. Start the existing backend and frontend using the repository's README. The app is local to this machine. Slide 1 links to `http://localhost:8500/research`.
2. In My Research, find **PTEN: Investigate the unexplained difference**. Its links reopen saved results and do not initiate a model call. The featured card reuses the existing public reference project; opening it creates no duplicate project or run. If that project is absent, it offers the existing setup workflow instead. Creating a project remains an explicit action.
3. Open the baseline and follow-up in separate tabs. Confirm the three substitutions and dataset version below. Do not change source versions, rename records, or portray the two deterministic runs as a single agent run.
4. Keep the PDF and `assets/` frames open as the offline fallback. No model service is required to present those artifacts. Local source navigation does require the app and saved data.

## 90-second talk track

| Time | Action | Say |
| --- | --- | --- |
| 0–15 s | Open the featured baseline. | “Which of these three PTEN substitutions meets our declared assay rules, and what remains unresolved?” |
| 15–35 s | Inspect the selected IDs, native assay criteria and missingness/measurement table. | “Activity and abundance come from different assays. R172H has no abundance observation here; missing is not zero.” |
| 35–50 s | Inspect linked reference structure and executed operation. | “These are accepted positions in the experimental reference. We are not computing a mutant fold.” |
| 50–70 s | Switch to the saved follow-up. Inspect changed inputs and the exact entered/unchanged set. | “Only the activity ceiling changed, from −1.11 to 10. Y16T enters and C124S stays. This is an exploratory rule sensitivity check, not a biological change.” |
| 70–90 s | Open the separate saved agent investigation, if available; otherwise show slide 8. | “The separate recorded model-backed run has a lead, two model reviewers and two deterministic workers. Argon execution is still unverified. A scientist reviews the supported outcome and unknowns.” |

## Exact saved references

- Dataset: `pten-transform-1.0-97b699d687c8`.
- Project: `project-c5786c930ae040d693910c78a4a548eb`.
- [Baseline](http://localhost:8500/research/project-c5786c930ae040d693910c78a4a548eb/workspace?view=analysis&analysis_run=research-4df547659b0949898f8ec40e00ee071c): `research-4df547659b0949898f8ec40e00ee071c`.
- [Follow-up](http://localhost:8500/research/project-c5786c930ae040d693910c78a4a548eb/workspace?view=analysis&analysis_run=research-6be0a905e61a40eda99c4bcce147da1d&selected_id=PTEN%3Ap.Y16T): `research-6be0a905e61a40eda99c4bcce147da1d`.
- [Recorded agent run](http://localhost:8500/research/project-c5786c930ae040d693910c78a4a548eb/investigations/research-00f7ec8b7690404db6f033a509507c8c): `research-00f7ec8b7690404db6f033a509507c8c`; completed with limitations. Actual provider: OpenRouter / x-ai/grok-4.3. Do not attribute it to Argon.
- Activity ceiling: baseline `-1.11`, follow-up `10`.
- Abundance boundary, unchanged: `0.6121866579147568`.
- Three substitutions, unchanged: C124S, R172H, Y16T. All three have accepted reference mappings.
- Entered: Y16T. Left: none. Unchanged: C124S. R172H remains unavailable for the paired rule.

## Optional fresh computation

From the saved baseline, select **Use this result as baseline**, change the activity ceiling to `10`, review the inputs and check the confirmation box, then choose **Run one-factor follow-up**. This creates another deterministic saved run with zero model requests. It is unnecessary for the reliable opening. Starting a model investigation requires its separate explicit confirmation; do not trigger one merely to create motion on screen.

## Provider or app unavailable

If a provider fails, say: “The model provider is unavailable; I will show the saved recorded result and its underlying artifacts.” Do not retry repeatedly during the pitch. If the entire app is unavailable, show slides 4–9 and the real frames in `assets/`. Distinguish recorded playback from a fresh execution. Do not claim an autonomous limitation-driven revision: this evidence establishes a declared criterion change and an unresolved missing observation.
