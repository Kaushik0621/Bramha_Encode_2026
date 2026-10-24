# Variant Atlas — final product, research and data plan

Version 1.0 · 24 October 2026 · Agreed implementation direction

## 1. Decision and relationship to earlier drafts

Build **Variant Atlas: a spatial computational research observatory for investigating uncertain genetic variants**. Its first mission is human PTEN functional-variant investigation. This document and `variant-atlas-final-codex-spec.md` supersede earlier planning drafts for scope and completion criteria. The previous synthetic prototype is reusable scaffolding, not the finished product. Preserve its useful UI, APIs and provenance plumbing where appropriate.

This is a software product for a researcher coordinating computational work. It is not an autonomous wet laboratory, whole-organism simulator, diagnostic system or replacement for clinical trials.

## 2. Product goal and customer problem

**Help a functional-genomics team move from scattered variant evidence to a checked explanation of what is known, what remains unresolved and what follow-up could distinguish competing explanations.**

A team has many variants of interest and limited experimental capacity. It must reconcile identifiers, assay measurements, methods, structures and conflicting observations before choosing its next panel. The product performs and records this computational investigation, rather than merely summarising papers or ranking mutations with an unexplained score.

The first user is a functional-genomics researcher. The potential buyer is the laboratory lead or small biotech research team. The proposed commercial unit is a shared investigation workspace with private datasets, review history and reproducible exports. Validate a pilot task before setting pricing. A target such as halving evidence-preparation time is an evaluation hypothesis; it is not a claim about halving discovery or laboratory timelines.

## 3. Precise first research mission

> Given supported human PTEN protein-altering variants, investigate whether available measurements support distinct activity/abundance patterns; audit identity and assay compatibility; examine reliable structural context; compare competing explanations; and prepare a source-linked follow-up brief.

Start with missense substitutions and a small audited public-data slice. The input is identified variants or supported measurement tables, not raw whole-genome reads. Pin organism, reference sequence, isoform, transcript and genome build wherever applicable. Other genes and animals are future extensions; evidence is never pooled across species or model systems without explicit justification.

There is no universal best-variant ranking. Researchers declare their objective, eligibility criteria, capacity and review priorities. Candidate order uses transparent criteria or explicit researcher curation. An LLM cannot silently replace those rules with an importance score.

## 4. Two investigation scenarios

### A. Reduced abundance and reduced activity

Research question: does the available evidence support abundance-associated loss of measured function, or is an additional functional effect unresolved?

- Branch A1 reviews abundance measurements, their precision and experimental context.
- Branch A2 reviews activity measurements and whether the comparison can address the question.
- A reconciliation task identifies what can and cannot be concluded across the assays.
- The result may be a limited explanation plus a follow-up question, not a causal verdict.

### B. Preserved abundance and reduced activity

Research question: what evidence supports impaired measured function despite relatively preserved abundance, and which alternatives remain plausible?

- Branch B1 checks exact substitution identity and measurement coverage.
- Branch B2 examines structure mapping, annotations and spatial context.
- Branch B3 retrieves methods and independent observations relevant to competing explanations.
- Reconciliation may identify assay-specific effects, functional impairment hypotheses or insufficient evidence.

These are scenarios to locate in real data. No specific variant is claimed to exhibit them until the source records are inspected. A spatial relationship generates a testable question; it does not prove mechanism or disease causation.

## 5. What makes the investigation iterative

| Trigger | Required response |
| --- | --- |
| Reference amino acid mismatch | Resolve sequence identity/version before mapping; reject unresolved mappings |
| Protein-level measurement linked to several possible DNA alleles | Preserve representation ambiguity; do not claim the exact allele was measured |
| Different assay systems or endpoints | Create a comparability task and narrow claims accordingly |
| Missing experimental coordinates | Keep the candidate visible but stop unsupported spatial calculations |
| Alternative predicted model has weak confidence | Show its limitations; do not upgrade a prediction to measured evidence |
| Conflicting source findings | Investigate methods and context; preserve disagreement if unresolved |
| Missing independent evidence | Target retrieval to the missing question, then abstain if it stays missing |
| Time, cost or iteration limit reached | Produce an explicitly partial result with unresolved tasks |

The investigator stops when the declared question is answered to the supported level, no permitted tool can resolve the remaining gap, or its budget is exhausted. It does not continue until it can manufacture certainty.

## 6. Agent organisation

Argon is the lead investigator. It can delegate scoped tasks to identity/data, assay, structure, evidence and verification specialists, plus a reconciliation specialist when needed. Specialist model assignments are configurable; the lead and particularly difficult branches may use Argon, while bounded extraction can use a supported faster Gemini model.

Dynamic creation means starting a task-scoped worker instance with a question, permitted tools, input references, expected outputs, execution budget and stop condition. It does not mean copying credentials, spawning uncontrolled recursive agents or creating new model weights. Workers communicate through structured findings and shared artifacts. The lead can compare branches or request revision. Avoid redundant workers by checking existing task/artifact keys.

Verification combines separate review with deterministic checks. Model agreement alone is not scientific validation. The UI distinguishes model agents, numerical tools, databases and outputs.

## 7. Data sources and acquisition plan

| Stage/source | Data required | Why and when it enters | Initial access and gate |
| --- | --- | --- | --- |
| UniProt | Human PTEN reference accession/sequence and annotations | Identity and protein reference | Start at https://www.uniprot.org/uniprotkb/P60484/entry ; pin sequence version and isoform |
| Ensembl | Transcript/genome relationships and consequences | Only when DNA-level variants require annotation | https://www.ensembl.org/info/docs/tools/vep/index.html ; pin assembly, transcript and tool release |
| MaveDB | PTEN scores, assay descriptions, target sequences and metadata | Functional evidence after identity validation | https://mavedb.org/genes/PTEN ; use documented exports/API, inspect overlap and terms |
| Original PTEN study and supplements | Activity/abundance methods, controls and reported results | Interpret the supported comparison | https://pmc.ncbi.nlm.nih.gov/articles/PMC8518224/ ; verify supplement availability and reuse terms |
| RCSB PDB | Experimental coordinates, chain identity, construct and coverage | Spatial analysis after sequence alignment | https://www.rcsb.org/structure/1D5R ; inspect missing residues and numbering |
| AlphaFold DB, optional | Predicted coordinates and confidence | Alternative structural context when justified | https://alphafold.ebi.ac.uk/ ; keep experimental/predicted provenance distinct |
| ClinVar, optional | Condition-specific submissions, review status and dates | Existing interpretation context | https://www.ncbi.nlm.nih.gov/clinvar/ ; preserve disagreements and accession versions |
| gnomAD, optional | Population observations, coverage and frequency metadata | Population context for a specific question | https://gnomad.broadinstitute.org/ ; no record does not mean zero frequency or pathogenicity |
| PubMed/PMC | Relevant abstracts, methods and available full text | Targeted hypothesis/evidence retrieval | https://pubmed.ncbi.nlm.nih.gov/ and https://pmc.ncbi.nlm.nih.gov/ ; obey access/reuse terms |
| Researcher uploads, later | Private supported variant tables and methods | Extend a workspace with new observations | Explicit workspace isolation and provider/data handling policy |

This is a source plan, not a claim that downloads, joins, licences or complete coverage have already been verified. Do not ingest whole databases for the first mission. Begin with one activity dataset, one abundance dataset, a compatible reference and one structure. Select a small intersection only after inspection. If the data cannot support the intended comparison, report the blocker and a narrower scientifically defensible scope; do not replace real gaps with fictional observations.

### Required acquisition artifacts

- Source manifest: source ID, title, canonical URL, release/accession, retrieval time, licence/terms status, checksum and local asset reference.
- Raw immutable downloads, retained alongside transformed tables.
- Assay dictionary: endpoint, model system, construct, direction, units/scale, controls, replicates/uncertainty when available and limitations.
- Identity/mapping audit: every accepted, rejected and unresolved join, including sequence versions and structure numbering.
- Coverage report: counts for measured, comparable, mapped and excluded records, with reasons.
- Reproduction commands and transformation versions.

## 8. Scientific data model and comparison rules

Preserve distinct genomic, transcript and protein representations. A protein substitution cannot always be uniquely reverse-translated into a DNA change. Every record carries organism, reference identity and representation level.

Measurements remain attached to their assay and original scale. Cross-assay classification uses documented assay-specific interpretation or calibration, reviewed for the intended question. Artificial 0–1 scores and thresholds from the prototype are not carried into real data. Unknown values are null, not zero. Replicates must not be invented. Abundance is not automatically a direct measure of stability, and activity assays do not automatically measure the same biological property.

Residue mapping uses alignment and explicit reference-to-chain lookup, handling missing residues, insertion codes, offsets and alternate isoforms. Unresolved or ambiguous mappings remain unavailable. Define spatial distances explicitly, for example C-alpha Euclidean distances in ångströms. Coordinates from a reference structure do not demonstrate a mutant conformation.

## 9. Storage architecture

| Layer | Responsibility |
| --- | --- |
| MongoDB Atlas | Authoritative workspaces, metadata, variants, assays, evidence, mappings, tasks, findings, events and reviews |
| Atlas Search + Vector Search/hybrid retrieval | Versioned evidence-passage retrieval with gene/assay/source filters |
| Object storage | Original tables, structure files, permitted documents and exported artifacts |
| Parquet + DuckDB | Versioned analytical views and reproducible numerical joins; derived from pinned source snapshots |

This uses multiple data paradigms without duplicating authoritative state. Source databases are external evidence providers, not additional mandatory infrastructure. A separate graph database is deferred unless real relationship queries justify it; typed evidence edges can be stored in Atlas. Embeddings retrieve prose, not DNA identity or biological equivalence. Stream Processing is optional only for a genuine live-ingestion use case.

## 10. Product experience and model responsibilities

Three linked views share selection and run state:

1. **Molecular observatory:** real protein, mapped variants, measurement layers, distance annotations and explicit coverage limitations.
2. **Glass investigation chamber:** real agent branches, tool execution, evidence handoffs, failures and changes of plan.
3. **Evidence workbench:** source passages, measurements, competing hypotheses, checks and saved findings.

A Live-capable Gemini companion handles voice and selected-object references; Argon handles deeper investigation. Argon is not assumed to provide Live audio. Voice commands carry selected residue/variant IDs and active dataset versions, not just screenshots. Camera effects are navigation, not simulated biology. The product must work through text/keyboard when voice is unavailable.

OpenRouter remains a development adapter. The supplied Google challenge requires actual Argon use; an OpenRouter-only alternative is not challenge-complete. Use only verified model IDs/capabilities, and preserve provider/model identity on every run.

## 11. Deliverables and verification

Each completed investigation produces: the declared question and criteria; audited inputs; branch/task history; supported observations; reproducible calculations; competing hypotheses; unresolved issues; a reviewable follow-up panel; source-linked brief; and exportable provenance.

Run states are completed, completed-with-limitations, needs-review, failed or cancelled. Scientific uncertainty can remain in a technically completed run, but must be prominently communicated. Independent checks verify identifiers, calculations, source existence and claims against supplied records. They cannot certify biological truth.

Success requires one real-data investigation, actual Argon planning/tool choice, a genuine branch, a limitation that changes the plan, working spatial interaction, saved provenance and researcher review. Pathway 2 fit comes from substantive scientific/spatial interaction; agent count and visual gloss alone are insufficient. Demonstrate the required Atlas feature with a real successful query.

## 12. Build sequence and evaluation

1. Inspect the existing code and preserve working features.
2. Acquire and audit the minimal real data slice before expanding visual effects.
3. Implement deterministic identity, assay and geometry tools with reference checks.
4. Add bounded Argon orchestration, dynamic delegation and persisted verification.
5. Connect the molecular view and chamber to genuine artifacts/events.
6. Add contextual voice and Atlas hybrid retrieval.
7. Evaluate a frozen reference case and a held-out case; finish failure/reconnect/replay behaviour and polish.

Prepare a researcher-reviewed reference task and rubric. Compare preparation time, evidence-handling errors, unsupported claims and expert-rated usefulness against the researcher's normal workflow. Recruit a real named user rather than inventing one. Do not promise a discovery, mechanism, cure, validated clinical interpretation or Phase 1/2 trial result. Wet experiments and clinical trials remain outside the software.

## 13. Expansion after the first mission

Additional genes, curated species-specific workspaces, independently validated computational methods, private-team collaboration and budget-aware panel selection can extend the platform. Each extension needs its own identity, data and evaluation gate. Whole-genome processing, molecular dynamics and clinical deployment are separate projects, not implicit features of this release.

## Reference documentation

- MaveDB access: https://www.mavedb.org/docs/mavedb/finding-data/index.html
- Existing MaveDB 3D functionality: https://www.mavedb.org/docs/mavedb/finding-data/visualizations.html
- Argon: https://ai.google.dev/gemini-api/docs/models/gemini-4-argon
- Live API: https://ai.google.dev/gemini-api/docs/live
- MongoDB hybrid retrieval: https://www.mongodb.com/docs/vector-search/hybrid-search/vector-search-with-full-text-search/
- OpenRouter: https://openrouter.ai/docs/quickstart

Existing tools already visualise variant effects. Our product hypothesis is the verified, adaptive investigation connecting evidence to follow-up questions. Novelty and commercial advantage must be evaluated rather than asserted.
