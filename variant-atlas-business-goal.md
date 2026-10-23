# Variant Atlas — the problem, product and business goal

Draft · 23 October 2026 · Product hypothesis for research use

## What are we building?

**Variant Atlas is a research decision-support workspace that helps a genetics team decide which mutations to investigate next, why those mutations deserve attention, and what uncertainty a follow-up experiment could resolve.**

Its main deliverable is a reviewable experimental shortlist with supporting evidence, unresolved questions and proposed follow-up approaches. An interactive 3D protein view helps researchers inspect structural context. The researcher remains responsible for the scientific decision.

## The business situation

Imagine a research organisation studying a gene associated with disease. The team has 200 mutations of interest but can investigate only 10 in its next laboratory experiment. These numbers are illustrative, not observed customer data.

The team needs to answer:

> Which 10 should we investigate, what question will each experiment answer, and why choose these rather than the others?

The difficulty is not simply finding a mutation or reading a paper. It is combining evidence from different experiments, checking whether it applies to the same variant, understanding the remaining uncertainty and making a defensible selection within a limited budget.

## What makes the decision difficult?

| Information the researcher has | Question they still need to answer |
| --- | --- |
| A list of mutations | Which already have relevant experimental measurements? |
| Published measurements | What did each experiment measure, and under which conditions? |
| A protein structure | Can this mutation be mapped reliably, and where does it occur? |
| Findings from different studies | Do they genuinely disagree, or measure different properties? |
| Several possible experiments | Which approach addresses the team's specific unanswered question? |

An experienced researcher can investigate these questions manually. Our product hypothesis is that evidence assembly, compatibility checking and review can be made faster and more traceable. We must validate that hypothesis with real users.

## One concrete example

Suppose two mutations both show reduced protein activity in published experiments.

- **Mutation A:** measurements also show reduced protein abundance.
- **Mutation B:** measured abundance appears relatively normal.

These patterns lead to different follow-up questions. For A, could reduced activity be associated with less protein being present? For B, could the protein be present but impaired in its measured function?

These are possible explanations, not conclusions. Assay conditions, model systems and other differences could also explain the observations. The platform must preserve those limitations rather than silently combine incompatible measurements.

Variant Atlas would assemble the records, explain what each assay measured, identify evidence gaps, display available structural context and draft follow-up questions for researcher review. It must not claim to establish the mechanism from those observations alone.

## What insight does the platform provide?

The useful insight is an explicit connection between **an observed pattern, an unresolved scientific question and a reason to consider follow-up**.

For example:

> This variant meets your selected activity/abundance criteria. The available measurements leave its mechanism unresolved. Here are the source records, an alternative explanation and a follow-up approach to discuss.

The platform should distinguish three things throughout:

1. **Observed evidence:** what a supplied experimental source reports.
2. **Calculated results:** what a reproducible filter, mapping or geometry calculation returns.
3. **Hypotheses:** possible explanations and follow-up suggestions that need expert review.

It should not present a universal ranking of the most important mutations. A shortlist depends on the research objective, available evidence and declared selection criteria. Mechanism discovery and assay evaluation may require different selections.

## What does the researcher receive?

| Deliverable | Purpose |
| --- | --- |
| A shortlist of variants | Defines candidates for the team's next investigation |
| Selection criteria and reasons | Makes inclusion and exclusion understandable |
| Source-linked evidence | Lets colleagues inspect and challenge the basis of a decision |
| Unresolved questions | Explains what further work could clarify |
| Proposed follow-up approaches | Provides a starting point for experimental planning, not an executable laboratory protocol |
| Missing or conflicting information | Makes uncertainty visible |
| Linked 3D protein view | Provides structural context where reliable mapping is available |
| Saved review history and export | Supports research meetings, collaboration and reproducibility |

## Why the 3D representation matters

Positions far apart in a protein's linear sequence can lie close together in its folded structure. A linked 3D view helps researchers inspect spatial relationships alongside functional measurements and ask whether a structural neighbourhood deserves follow-up.

Selecting a variant should highlight its mapped position and open its evidence. Switching between activity and abundance should change the displayed measurement layer. Unmapped positions and uncertain structural regions should remain explicit.

Structural proximity does not establish a common biological mechanism or disease effect. A reference structure is not a validated mutant structure. Camera movement is interface animation, not simulated molecular behaviour. The evidence workflow must remain useful when structural mapping is unavailable.

## Why an agent helps

The agent coordinates a bounded investigation: understand the research question, retrieve relevant records, run explicit analysis tools, compare evidence, identify missing information and draft a review brief.

Numerical tools establish filters, mappings and distances. Sources establish reported measurements. The language model helps connect and explain them; its prose is not independent scientific evidence. The first prototype can use a deterministic workflow with optional AI explanation before adding genuine tool-selecting agent behaviour.

## What is the organisation buying?

**A faster, more traceable process for preparing experimental decisions.**

The initial commercial hypothesis is a workspace for functional-genomics laboratories and small biotech research teams. The first user is the researcher preparing a shortlist; the potential buyer is the laboratory lead or research team responsible for that workflow and its budget.

Potential value includes less manual evidence assembly, easier review between colleagues and fewer mistakes caused by mismatched identifiers, overlooked limitations or incompatible measurements. These are benefits to test, not proven savings.

Start with a pilot around one real selection task. Consider team subscriptions or private workspaces only after demonstrating recurring value. Do not invent pricing, customer demand or return on investment.

## The first product promise

> Give us variants for one supported gene and your selection criteria. We will assemble the supported evidence, identify relevant patterns and gaps, and produce a source-linked shortlist for your review.

Begin with PTEN and selected activity/abundance datasets after verifying that the records can be mapped and interpreted together. A clearly labelled synthetic-data prototype demonstrates the interaction first; it does not demonstrate biological validity.

The first release supports explicit criteria and evidence review. It does not claim to calculate which experiment has the greatest scientific information gain. Validating that more ambitious prioritisation capability would require expert objectives, suitable evaluation data and a separately tested method.

## How we know whether it is useful

Recruit one actual researcher and compare the same shortlist task using their existing workflow and the prototype. Define the evaluation rubric before the comparison.

- Time required to prepare a reviewable shortlist.
- Accuracy of variant identity, assay interpretation and evidence mapping.
- Missing limitations or unsupported statements in the brief.
- Expert-rated usefulness of the shortlist and follow-up questions.
- Ability of another researcher to reconstruct the reasons for each selection.

Success means a useful, defensible research decision is prepared more efficiently without increasing evidence-handling errors. Attractive graphics alone do not establish product value. Avoid claiming improved discovery rates or experimental outcomes until those are studied.

## Boundaries and differentiation

Variant Atlas does not promise a cure, recommend treatment, diagnose a patient or automatically reclassify clinical variants. Existing resources already provide variant evidence and 3D visualisation. Our proposed contribution is the connected, verified workflow from a research question to a follow-up shortlist and review brief. Its advantage over existing workflows remains to be demonstrated.

## Product pitch

**Variant Atlas helps genetics researchers turn scattered mutation evidence into an evidence-backed plan for what to investigate next, with uncertainty and structural context visible throughout.**
