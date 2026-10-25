# Bramha Atlas: evidence-led pitch presentation brief for Codex

**Deliverable:** an editable 16:9 PowerPoint with a story-led slide count (suggested starting point: 16 slides), speaker notes, a PDF preview and a repeatable opening demo. Audience: hackathon judges and potential laboratory partners. Inspect the repository, applicable AGENTS.md, latest reports, screenshots, source manifests and actual run artifacts before creating the deck. Use the installed presentation skill if available. Build the deck, render every slide, inspect desktop-sized previews and fix clipping, illegibility and inconsistent composition.

The `10-slide` filename is retained for existing references; it is not a slide-count constraint. Add, merge or remove slides to improve the story. Keep one clear message per slide and preserve time for the opening demo. State the expected presentation duration and distinguish the core pitch from optional technical backup slides.

## Repository evidence to inspect first

The following are starting points, not substitutes for checking the underlying artifacts and current application:

- `docs/EXPERIMENT_ANALYSIS_DELIVERY.md` and `docs/EXPERIMENT_EXECUTION_AUDIT.md`: executed operations, real PTEN case and capability boundaries.
- `artifacts/experiment-analysis/real-reference-check.json`: pinned dataset `pten-transform-1.0-97b699d687c8`, baseline/follow-up IDs, actual measurements and selection differences.
- `artifacts/experiment-analysis/live-team-verified-report.json`: saved successful agent run `research-00f7ec8b7690404db6f033a509507c8c`, completed with limitations. It records 5 model requests, 10 deterministic tool calls and four delegated workers: two deterministic workers and two model reviewers. This run used a fallback provider; it does **not** verify Argon. Do not relabel its screenshot as Argon execution.
- `artifacts/ARGON_CONNECTIVITY.json`: the recorded Argon connectivity check was unverified after a timeout. Inspect newer evidence if available; otherwise present Argon as the intended integration.
- `docs/MONGODB_DATA_CONSOLE.md`, `artifacts/data-console/actual-storage-summary.json` and `artifacts/research-observatory/atlas-verification-report.json`: distinguish public-corpus Atlas persistence, recorded vector-index verification and local project storage. A ready vector index alone does not demonstrate a successful end-to-end retrieval query.
- `docs/BRAND_AND_THEME.md` and production branding assets: inspect the actual current brand before choosing the lockup.

Do not expose credentials, private source material or private backup manifests in slides, notes or the asset handoff. Date snapshot counts and identify their exact report.

## Story and positioning

Bramha Atlas helps small life-science teams connect scattered evidence to a research decision they can inspect and reproduce. Start with human PTEN variant evidence. Show the actual research question, calculations, evidence, changing investigation and useful outcome. Position Argon as the intended lead investigator, coordinating scoped specialists and deterministic tools; upgrade this to a demonstrated capability only after a verified Argon run. MongoDB Atlas provides public-corpus persistence and retrieval where verified. Project investigation state currently remains local; do not imply it has been migrated to Atlas. Human scientists review the interpretation. No claims of cures, clinical validation, biological experiments or measured efficiency gains without supporting evidence.

## Opening demonstration

Create a prominently featured **“PTEN: Investigate the unexplained difference”** example at the top of the existing research section. Preserve the approved homepage. Reuse supported project/template mechanisms and make seeding idempotent. Select actual audited variants with relevant activity/abundance measurements. Prefer contrasting mapping coverage only when supported by the selected records; do not manufacture a missing-coordinate case. Do not invent the variants or force an unsupported pattern. If the intended example is unavailable, choose and explain a supported alternative.

Question: “Which selected variants meet our assay-specific criteria, what structural context is available, and what remains unresolved?” Preload the question, evidence and selections. Starting model execution requires an explicit click. Demonstrate identity/comparability checks, a missing/incompatible evidence condition and a source-linked result. Show a genuine agent branch and limitation-driven revision only if their saved events establish that behavior. Separate the deterministic baseline/follow-up from the model-backed investigation; do not splice separate runs into a fictional continuous execution. Reuse a saved verified run for reliability, clearly labelled recorded replay. Include a concise live-demo script in the notes and a graceful unavailable-provider fallback.

Supported opening case: C124S, R172H and Y16T. The saved baseline selects C124S; changing only the activity ceiling from -1.11 to 10 adds Y16T. R172H remains unavailable for the paired rule because abundance is missing. All three records have accepted reference mappings in this report. The changed threshold is an exploratory sensitivity demonstration, not an experimentally justified new cutoff, biological change or agent-generated hypothesis revision. The two deterministic runs made zero model requests.

Capture real frames for workspace/selection, measured-data comparison, saved agent branches, declared input change and final evidence/uncertainty. Use distinct frames where they support the slide story. A completed-network screenshot is evidence of a saved run, not an active live execution. If a genuine limitation-driven revision cannot be verified, show the actual unresolved condition and state that adaptive revision remains unverified. Do not fabricate runtime activity for visual impact.

## Suggested narrative: 16 slides, adjustable

The sequence below is a starting structure, not a fixed count. Split dense material, combine short transitions, and move implementation depth to notes or explicitly marked backup slides. Make the central question and useful outcome understandable before explaining the architecture.

| # | Title and content | Main visual |
| --- | --- | --- |
| 1 | **Bramha Atlas**. “Which mutation should we investigate next, and why?” Brief product description and demo entry. | Approved logo and a real molecular workspace frame |
| 2 | **One research decision, scattered evidence**. One researcher, competing explanations and limited experimental capacity. Introduce the initial customer. | Focused research scenario; label any illustrative quantities |
| 3 | **A connected, reviewable investigation**. Ask, inspect evidence, investigate, review and continue. Output: a checked research brief with unresolved questions. | Editable workflow with human review and artifact handoffs |
| 4 | **Start with real PTEN evidence**. Introduce the actual substitutions, pinned records and the question. | Selection frame and compact source/measurement table |
| 5 | **Activity and abundance answer different questions**. Explain native scales, assay systems and missingness. | Editable measurement chart and explicit missing-value row |
| 6 | **Structural context has boundaries**. Show accepted reference mapping and explain what coordinates can establish. | Real linked selection and reference structure; no mutant-fold claim |
| 7 | **Change one criterion; inspect the difference**. Show baseline/follow-up inputs and entered/left/unchanged sets. Explain why the threshold change is exploratory. | Editable before/after comparison from saved artifacts |
| 8 | **A lead coordinates scoped reviews**. Show actual dependencies, independent assay/structure review, deterministic checks and artifact transfers. Argon status must be explicit. | Saved chamber frame plus a readable editable task diagram |
| 9 | **The result includes what remains unresolved**. What ran, what was unavailable, what the evidence supports and the next research question. Show an actual revision only when verified. | Source-linked result and concise limitation panel |
| 10 | **Evidence, computation and persistence**. Distinguish deterministic Python, model review, contextual assistant, retrieval and storage. | Editable architecture with public Atlas corpus and local project state separately labelled |
| 11 | **What is demonstrated today**. Distinguish verified reference analyses, saved model run, recorded replay and pending integrations. | Compact capability/evidence matrix; date the evidence |
| 12 | **Who starts using it**. Academic genomics labs and small biotech teams. Define the initial job and proposed design-partner pilot. | Focused customer/workflow composition |
| 13 | **Where it fits**. Carefully sourced competitor context: Benchling, Galaxy, MaveDB and literature tools. State the proposed investigation-level distinction. | Fair comparison by supported workflow; optionally one sourced market-context number |
| 14 | **Business model: a hypothesis to test**. Bounded individual/lab subscriptions and a labelled illustrative revenue calculation. | Editable pricing hypothesis and transparent arithmetic |
| 15 | **Pilot, measure, expand**. Expert review, task success, time/error evaluation and validated expansion. No measured gains without data. | Adoption sequence with proposed acceptance criteria |
| 16 | **The next research milestone**. Verify Argon integration, evaluate with researchers and expand gene coverage. Ask for pilot labs and scientific advisers. | Approved logo, concrete milestones and one clear ask |

Keep prospective permissioned collaboration, persistent identifiers and portable research packages in the roadmap or notes. Optional blockchain is not needed to explain the core product. Avoid filling extra slides with speculative features.

## Design, accuracy and handoff

- Use a premium editorial software aesthetic: one dominant visual per slide, generous whitespace, strong hierarchy and restrained colour. Derive the palette from the approved product/brand assets. Use the existing approved logo in its original proportions; do not regenerate it or assume the newest experiment is approved.
- Titles around 32–44 pt, body preferably 20–24 pt. Keep visible copy brief; put technical depth and citations in speaker notes. Use varied compositions, cropped legible app frames and editable charts/diagrams. Avoid stock scientists, generic DNA wallpaper and repetitive bullet slides.
- Make roles precise: one orchestrator, dynamically instantiated scoped specialists, numerical tools and data stores. Read counts from the featured run. Separate available roles from actual workers. “Replication” means bounded task delegation, not new model training. Never depict private chain-of-thought.
- Discuss Argon and relevant Gemini companions only; omit alternative-provider branding. Confirm actual Argon execution before using a screenshot as proof. If showing a provider-neutral saved run, label it “recorded model-backed run; Argon unverified” and disclose its actual provider/model in notes and the evidence manifest without promotional alternative-provider branding. If unverified, label the architecture “planned” or “integration pending” and use honestly labelled available evidence. Apply the same rule to Atlas persistence, hybrid retrieval and voice. Credentials or adapters alone do not establish working execution.
- Validate external numbers and cite source URL/date in notes. Market context is not company valuation or our addressable market. Do not add overlapping market categories. Pricing, revenue scenarios and efficiency targets are assumptions until tested. Source starting points: https://www.grandviewresearch.com/horizon/outlook/drug-discovery-informatics-market-size/global and the latest official competitor pages.
- Current capability statements come from inspected code/run artifacts. Include compact limitations where material. Use notes for source details, demo steps and backup behaviour. Optional blockchain is future exploration, not a core claim.
- Deliver the editable deck, PDF preview, source/asset manifest, slide thumbnails and presentation-generation source. Report blocked/unverified claims accurately. Choose the final slide count based on clarity and pitch duration. Optional backup slides are allowed, clearly separated from the core presentation. Report the final count and timing. Include a claim-to-source ledger, a repeatable demo script with saved run IDs, and any remaining blockers. A revised brief alone is not the presentation deliverable when executing this prompt.
