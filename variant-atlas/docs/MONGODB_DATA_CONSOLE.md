# MongoDB & Data console

Open [MongoDB & data](http://localhost:8500/data) from the sidebar, or follow **Settings & Connections → Inspect MongoDB & stored data**.

## What is stored where

The current configuration uses **MongoDB Atlas for the public research corpus** and **local storage for project investigations and the paper workspace**. The database is `variant_atlas`. This feature does not migrate or duplicate existing research.

- Atlas holds publication metadata, versioned original-language passages, molecular mentions, structural references, public measurement records, semantic vectors and public expedition activity.
- GridFS (`bramha_assets.files` and `bramha_assets.chunks`) holds checksummed original file bytes, structure files and the specifically approved historical backups.
- `bramha_workspace_snapshots` stores backup paths, hashes and asset pointers. The 223 approved file backups are snapshots; later local changes are not automatically synchronized.
- Project questions, notebooks, PTEN investigations, tool artifacts and operation results still follow `DATA_BACKEND=local`. The screen lists their relative file locations and counts separately.
- Local paper uploads remain in the local paper archive. Supplied-model comparisons and assistant/discovery records use the existing local SQLite archive in this configuration.

MongoDB uses collections of documents rather than SQL tables. A published study links to passages by study ID and source version. Passages can link to molecular mentions and locally generated vectors; acquired structure records point to checksummed original files. Expedition records, tasks and events preserve actual execution history.

## Browse the data

1. Inspect the current database connection, project storage and record counts at the top.
2. Follow the source-to-storage diagrams to understand the acquisition, embedding, execution and backup paths.
3. Choose **Browse records**, then select a collection. Its physical collection name and purpose appear above the records.
4. Search stored titles, IDs, genes, source text or status. Searches are literal, bounded and paginated; they do not invoke an LLM or ingestion.
5. Select a document to see saved fields, source versions, original text and related-study links beside the records. A bounded JSON preview is available under details.
6. Refresh to re-read counts and records. Collection, search, page and selected record are kept in the URL and restore after reload.
7. Review vector metadata, recorded index verification, approved-backup status, local inventory and saved ingestion jobs.

The console is read-only. It does not provision an index, upload files, start agents, generate embeddings or modify records. Binary contents and vector arrays are omitted from previews; credential fields are redacted, and long lists/text are explicitly truncated. The displayed archived-file byte total describes original bytes, not MongoDB compressed disk usage.

## Actual Atlas check

Checked at **2026-10-25T05:47:09.471345+00:00**. These are observed counts, not seeded display values; refresh the page for current counts.

| Physical collection / file group | Stored records |
|---|---:|
| `bramha_studies` | 480 |
| `bramha_passages` | 4,784 |
| `bramha_entities` | 2,394 |
| `bramha_structures` | 21 |
| `bramha_relations` | 40 |
| `bramha_scenarios` | 240 |
| `bramha_ingestion_jobs` | 1 |
| `bramha_expeditions` | 3 |
| `bramha_events` | 78 |
| `bramha_tasks` | 25 |
| `bramha_searches` | 1 |
| `bramha_metadata` | 2 |
| `bramha_workspace_snapshots` | 223 |
| `bramha_measurements` | 7,657 |
| `bramha_assets.files / bramha_assets.chunks` | 350 |

There are **4,533 stored passage vectors**. Embeddings use the configured local pretrained multilingual model. The screen labels the saved vector-index status as **last recorded verification**; simply opening this page does not re-verify/provision the Atlas index.

## Implementation and verification

- Backend: `backend/app/data_inspector.py`, `GET /api/data/overview` and `GET /api/data/collections/{name}`. Only known collection names and bounded query parameters are accepted. No arbitrary MongoDB query operator or file path is accepted.
- Frontend: `frontend/src/workspace/DataConsole.tsx` with a dedicated `/data` route and sidebar/settings entry points.
- Tests: `backend/tests/test_data_inspector.py` covers pagination, literal multilingual search, redaction, preserved original bytes, unknown collections, bounds, no mutation and corpus outages. `frontend/e2e/data-console.spec.ts` covers search, pagination, document inspection, reload, refresh, mobile layout and zero POST requests.
- Full backend suite: **145 passed**. Production build: passed. Data-console browser test: passed.
- Actual Atlas read checks: studies, passages, backup pointers and GridFS metadata were read through the new endpoints. See [credential-free storage summary](../artifacts/data-console/actual-storage-summary.json).

Screenshots and actual browser checks are in `artifacts/data-console/`. Existing scientific records and provider configuration are preserved.
