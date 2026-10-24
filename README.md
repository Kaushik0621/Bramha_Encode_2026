# Bramha Atlas · Encode 2026

A local research workspace that keeps a question, its evidence, exploration and computational investigations together. The React/TypeScript frontend and Python/FastAPI backend remain separate applications under [`variant-atlas/`](variant-atlas/).

Supported project methods are **PTEN variant investigation** using audited public assays and experimental reference geometry, and **blood-group comparative evidence review** using reported ABO/RhD scenarios and an inspected malaria literature corpus. Neither establishes clinical conclusions, personal risk or a mutant protein fold.

Open **http://localhost:8500** after starting the servers. Home opens a molecular overview with immediate workspace/resume actions, followed by the project dashboard. Create a supported project, link sources, explore evidence, review exact investigation inputs, then inspect actual workflow events and findings or abstention. Blood-group work uses this same project journey.

See the [molecular overview and asset provenance](variant-atlas/docs/MOLECULAR_OVERVIEW.md), [route map, feature migration, storage and screenshots](variant-atlas/docs/RESEARCH_WORKFLOW_ROUTES.md), [setup instructions](variant-atlas/README.md), [real-data build](variant-atlas/docs/REAL_DATA_BUILD.md) and [scientific acceptance gates](variant-atlas/docs/IMPLEMENTATION_STATUS.md).

## Run locally

From `variant-atlas/`, install dependencies and prepare supported assets if needed:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp .env.example backend/.env  # Only for a new setup; preserve existing credentials.
backend/.venv/bin/python scripts/acquire_pten.py
backend/.venv/bin/python scripts/seed_research.py
npm ci --prefix frontend
```

Start the backend with `cd backend && .venv/bin/python -m app.server` and the frontend in another terminal with `cd frontend && npm run dev`. Credentials belong only in the ignored backend `.env`. Provider execution requires configured access; navigation and deterministic exploration do not.

Local project metadata references existing assets and saved runs. Migration preserves original snapshots, backs up existing metadata and leaves historical work explicitly Unassigned until linked. Atlas integration and successful Google generation remain unverified. Search in this local workspace is lexical. This is a single-user research prototype without public hosting or authentication.

The original synthetic regression demonstration remains explicitly available at `/developer/demo`; it is outside the primary research journey.
