# Variant Atlas · Encode 2026

A research decision-support prototype for preparing an evidence-linked variant shortlist. It combines a linked 3D protein-like viewer, explicit assay criteria, per-variant decision notes and an inspectable investigation chamber.

**All current scientific inputs are synthetic. Geometry is illustrative, not a biological structure.** The prototype does not establish actual variant effects, clinical conclusions or validated experimental priorities.

## Application

The frontend and backend are separate applications under [`variant-atlas/`](variant-atlas/):

- **Frontend:** React, TypeScript, Vite, React Three Fiber and Drei.
- **Backend:** Python, FastAPI, deterministic analysis, persisted workflow events and optional OpenRouter explanations.
- **Storage:** durable local development files; an optional Atlas repository adapter is included but has not been verified with live credentials. Atlas Search and real PTEN integration are deferred.

See the [full setup, seed and test instructions](variant-atlas/README.md) and the [investigation chamber guide](variant-atlas/CHAMBER.md).

## Run locally

From this repository root:

```sh
cd variant-atlas
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp .env.example backend/.env
backend/.venv/bin/python scripts/seed.py
```

Backend terminal:

```sh
cd variant-atlas/backend
.venv/bin/python -m app.server
```

Frontend terminal:

```sh
cd variant-atlas/frontend
npm ci
npm run dev
```

Open **http://localhost:8500**. The default fixture explanation runs without external keys. Optional provider credentials belong exclusively in the ignored `variant-atlas/backend/.env`; they are not included in this repository.

## Features

- Editable activity/abundance criteria, explicit missing-value handling and researcher-curated candidate capacity.
- Synchronized table/3D selection, coverage inspection and calculated spatial neighbours.
- Research question, per-variant inclusion reasons, uncertainty and proposed follow-up approaches.
- Live asynchronous investigation chamber with SSE events, worker/artifact inspection, cancellation and persisted provenance.
- Clearly labelled simulated recording, recorded replay, linked protein view and accessible 2D fallback.
- Saved evidence snapshots and Markdown decision-brief export.

## Verification

The latest local verification passed **33 backend checks** and **nine browser/reducer checks**, plus the frontend production build. A bounded live OpenRouter run using synthetic inputs also completed successfully. See [verification notes](variant-atlas/artifacts/VERIFICATION.md).

## Planning documents

- [Product plan](variant-atlas-product-plan.md)
- [Business goal](variant-atlas-business-goal.md)
- [Build brief](variant-atlas-codex-build-brief.md)
- [Investigation chamber addendum](variant-atlas-investigation-chamber.md)
- [Implementation/plan review](variant-atlas/PLAN_REVIEW.md)
- [Earlier idea atlas](idea-map.html)

This is a single-process local development prototype. Real data mapping, production job infrastructure and research-user validation remain subsequent milestones. Competition eligibility must be checked against the actual build timing and rules.
