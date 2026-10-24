# Blood-group comparative investigations

Create a blood-group comparative evidence project from Home or `/projects/new?method=blood`. Blood and PTEN work share project navigation, the source library and canonical investigation detail while retaining separate scientific engines and inputs. The old `/?page=blood` link redirects to project creation. See [the current route and migration guide](RESEARCH_WORKFLOW_ROUTES.md). The standalone development surface is retained at `/developer/blood`.

## What is implemented

1. Enter a question mentioning two blood groups, or supply both structured scenario fields. Interpret before execution. ABO and RhD are parsed separately; contradictory question/field labels are rejected. The supported context is severe *P. falciparum* malaria. No participant identifiers are requested.
2. Review the self-reported scenarios and whether one or both factors differ. **Separate the factors** prepares ABO comparisons with RhD fixed, or RhD comparisons with ABO fixed. These are analytical scenarios; nothing is experimentally controlled by the software.
3. Start an actual configured-provider investigation. The lead receives shared cached evidence once and selects scoped reviewer tasks. Scenario A/B, mechanism, applicability, verification and reconciliation reports are required before finalization. Verification and reconciliation cannot precede their inputs. Optional additional searches operate on the bounded inspected corpus; they are not a web-wide literature search. Invalid worker outputs get at most one bounded correction. No model weights are copied.
4. Follow persisted events, real source handoffs and task outputs in the existing glass chamber. Inspect a node or replay actual events. The UI uses the configured provider/model. Deterministic retrieval is a tool, not a fabricated model agent.
5. Inspect synchronized illustrative cell environments, reference surface markers, evidence-supported rosetting topology and source metadata. Both scenarios use identical clustering; neither RhD status nor animation determines a disease difference. Counts, dimensions and placement are not biological measurements. There are no patient probabilities, adhesion constants or invented molecular coordinates.
6. Read the four-section comparison, presenter summary, limitations and source references. Export Markdown; the complete reproducibility checkpoint is available through the snapshot API. Partial and failed runs retain their actual outputs instead of receiving a fallback conclusion.

## Scientific source scope

The corpus contains inspected, explicitly labelled curator paraphrases of these sources, with source locations, retrieval dates, design, population, endpoints and limitations:

- [ABO reference biology, NCBI Bookshelf](https://www.ncbi.nlm.nih.gov/books/NBK2267/)
- [Rh reference biology, NCBI Bookshelf](https://www.ncbi.nlm.nih.gov/books/NBK2269/)
- [Rowe et al., Malian children and rosetting](https://pmc.ncbi.nlm.nih.gov/articles/PMC2077280/)
- [Kenyan genotype-specific study and adhesion assays](https://pmc.ncbi.nlm.nih.gov/articles/PMC10522014/)
- [Adult Indian case-control study and meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC3215225/)

The additional studies constrain generalization across non-O groups, genotypes, populations and parasite preferences. Reported B does not establish a BO or BB genotype. The corpus contains RhD reference biology but no applicable RhD-specific malaria effect study. That is a retrieval limitation, not proof of no effect.

The existing structured Rowe statistic retains its pooled O/non-O contrast, severe-versus-uncomplicated endpoint, Malian study population and confidence interval. It is never converted to a personal risk percentage. Generated findings are qualitative; numeric assertions belong in structured source metadata. Final supported differences cannot turn the corpus's pooled or context-specific malaria observations into an encoded pairwise effect for the entered phenotypes. Reference phenotype differences and unsupported disease distinctions are kept separate. Mechanical checks and model review do not establish scientific truth; independent review remains pending.

## Architecture and persistence

- Typed contracts: `backend/app/blood/schemas.py`.
- Orchestration: `BloodEngine` reuses `ResearchEngine` lifecycle, leases, event/artifact/task persistence and the configured action provider, with a domain-specific bounded comparative scheduler. Limits reuse model requests, tools, concurrency, depth, spawned tasks, time and optional cost settings. Remote cancellation is best effort; an in-flight request may still bill.
- Canonical local records: `var/research/research-*.json`, segregated by `workspace_id`. List, get and claim operations isolate blood investigations from PTEN; legacy PTEN records without a workspace ID remain PTEN.
- Atlas: existing revision-controlled investigation snapshots and normalized task/event/artifact projections; an additional `blood_evidence` text index supports filtered catalogue retrieval. Scenarios, source manifests and final results remain embedded in the authoritative checkpoint. No live Atlas verification was possible with the current local credentials.
- Runtime investigation retrieval uses pinned source copies for reproducibility. Local search is lexical. Atlas vector/hybrid retrieval and embeddings for this corpus are not implemented or claimed.
- Original-asset acquisition: `scripts/acquire_blood_evidence.py`. CAPTCHA pages are rejected. Content-addressed local XML snapshots were acquired for the Kenyan and Indian papers. The book chapters and Rowe full-text archive were blocked during direct acquisition; their inspected paraphrases and original links remain available. Raw archive availability is recorded per source. No remote object-storage integration is claimed.
- External workers: `scripts/research_worker.py` launches both isolated queues.

## API

- `POST /api/blood/interpret`: typed request suitable for text input now, future voice transcription using the same contract.
- `GET /api/blood/sources?q=...&system=ABO|RhD|all&context=reference|malaria|all&study=source-id|all`.
- `POST /api/blood/investigations`, `GET /api/blood/investigations`.
- `GET /api/blood/investigations/{id}`: complete snapshot.
- `GET /api/blood/investigations/{id}/events`: persisted SSE, with `after` cursor.
- `POST /api/blood/investigations/{id}/cancel`.
- `GET /api/blood/investigations/{id}/export`: Markdown brief with provenance.

## Verification and remaining gates

`tests/test_blood.py` covers interpretation, factor separation, identical groups, unsupported scope, conflicting input, real persisted handoffs with a scripted test provider, shared retrieval, queue isolation, budgets, invalid references/numerical assertions, unsupported RhD/pairwise malaria claims, provider failure and export. Scripted fixtures are test-only and explicitly labelled.

Browser checks cover interpretation, factor separation, missing-provider rejection, identical-group display, synchronized cameras, responsive sources, chamber inspection/replay and return to PTEN. Existing PTEN scene and chamber checks also pass.

`artifacts/BLOOD_COMPARISON_LIVE.json` records the latest explicit live-provider check. Earlier invalid/partial trials remain in the local investigation archive. Google/Argon credentials, Atlas/hybrid retrieval, remote object storage and independent scientific endorsement remain unverified or unavailable. This is evidence review plus schematic explanation, not infection simulation, diagnosis, genotype discovery or a laboratory experiment.
