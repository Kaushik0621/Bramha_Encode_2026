# Variant Atlas — product plan

Draft · 23 October 2026 · Research use · Working name

## The product and its goal

Variant Atlas is an interactive 3D research workspace that connects genetic variants, protein structure, experimental measurements and published evidence. It helps a functional-genomics researcher answer: **Which uncertain variants should we investigate next, why, and what experiment could distinguish the competing explanations?** The product is a web application with saved investigations and an exportable evidence brief. Its long-term goal is to reduce the work between receiving a variant dataset and designing a defensible follow-up experiment.

## The first user and commercial proposition

Start with a researcher in a university functional-genomics laboratory or small biotech team selecting variants for follow-up. Recruit one actual named researcher before claiming user validation. The pitch: **“Turn a table of uncertain mutations into an evidence-backed experimental shortlist, explored directly on the protein.”** Initially test a paid pilot around one real selection task; later consider laboratory/team subscriptions with private datasets and shared reviews. Measure preparation time, mapping errors and expert-rated shortlist usefulness before claiming savings or choosing prices. The buyer, willingness to pay and differentiation remain hypotheses.

## What we will build first

Begin with PTEN, one protein structure, two functional assay datasets and a small compatible variant subset. The researcher selects “preserved abundance, reduced activity,” inspects matching variants on a 3D protein, opens each measurement and its source, and asks an agent to assemble a follow-up shortlist. The agent explains selection criteria, conflicting findings and missing evidence, then drafts experiment questions for researcher review. The initial prototype uses clearly labelled synthetic measurements; real-data integration follows a mapping audit. No patient data is required.

## The experience

A polished React interface centres on an interactive molecular viewer: rotate, zoom, click residues, switch activity/abundance layers and inspect spatial neighbours. A linked table, evidence drawer and investigation timeline explain every highlighted item. Camera transitions guide attention; missing coordinates remain visibly unmapped. Animation is navigation, not simulated biology. The interface must distinguish measured results, calculated geometry and AI-generated hypotheses.

## Technical plan

React + TypeScript + Vite; Mol* for real molecular structures; Python + FastAPI for APIs, analysis and orchestration. Use deterministic tools for identity checks, assay filtering, residue mapping and distances. Start with OpenRouter through a server-side provider adapter; configure the model ID rather than hardcoding it. Support a later R1-family or Gemini adapter after confirming the intended model and its capabilities. For the supplied Google challenge, the final submission must actually use the required Argon model; an OpenRouter-only prototype is not sufficient. Atlas persists core research state: variants, assays, evidence, structures, investigations and reviews. Add Atlas Search, Vector Search and hybrid retrieval for research text; Voyage embeddings are optional. Large assets belong in object storage. No extra database is needed initially.

## Data and scientific boundaries

Candidate sources: [MaveDB PTEN](https://mavedb.org/genes/PTEN) for functional data; [PTEN activity/abundance study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8518224/) for methods; [RCSB 1D5R](https://www.rcsb.org/structure/1D5R) for experimental geometry; [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) for submitted classifications; [UniProt](https://www.uniprot.org/) for reference sequence identity. Before ingestion, check dataset terms, versions, assay scales, sequence/isoform compatibility and resolved residue coverage. Never treat different assay scores as directly interchangeable. Structural proximity is context, not proof of shared function or disease. No cure, treatment recommendation or automatic clinical reclassification.

## Delivery and success

First ship a reproducible dummy-data demo with linked 3D selection, filters, evidence and a saved shortlist. Next audit real PTEN joins and replace fixtures incrementally. Then add bounded tool-using investigations, text retrieval and expert evaluation. A successful demo has correct selection/mapping checks, source-linked findings, explicit abstention and working persistence. Existing MaveDB tools already provide 3D variant views; our proposed advantage is the verified investigation-to-experiment workflow. Do not claim unique biology, validated prioritization or Argon exclusivity without evaluation.
