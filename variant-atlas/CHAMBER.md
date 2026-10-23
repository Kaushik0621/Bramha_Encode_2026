# Investigation chamber

Implemented from `../variant-atlas-investigation-chamber.md`. The existing scientific workspace and its shortlist rules remain intact. Frontend and backend remain separate applications.

## Use it

Start the backend and frontend with the commands in README, then open `http://localhost:8500`.

1. Enter the research question, criteria, candidate capacity and explanation mode.
2. Press **Start investigation**. The chamber opens immediately while the asynchronous run is accepted.
3. Inspect a worker instrument, its timeline button, a data dock, a recorded handoff or an output artifact. The drawer exposes timestamps, task summaries, permitted references, completed results and warnings. It does not expose hidden model reasoning or prompts.
4. Use **Workflow / Protein / Split view**. Split is desktop-only. Selecting a variant reference in an artifact focuses that variant in the linked protein view. The protein geometry remains explicitly illustrative.
5. Open the saved review brief from the output tray. Existing decision notes, source snapshots and Markdown export remain available.
6. At completion, select **Replay recorded events**. Replay has its own play, pause, restart, seek and speed controls and never invokes tools. Playback advances at a readable event-paced cadence; timestamps retain their recorded values, so playback speed is not a claim of wall-clock execution duration. **Pause visual motion** only pauses visual effects. Neither control pauses backend execution.
7. **Preview simulated chamber (no model call)** loads the tracked deterministic recording. Its execution label is simulated, separately from synthetic scientific inputs.

The independent accessible worker buttons and 2D event timeline remain usable when WebGL is unavailable. Reduced-motion mode disables packet/pulse effects and uses immediate state updates. Motion effects do not drive business logic.

## Execution truthfulness

- **Data mode:** synthetic throughout this milestone.
- **Execution mode:** live for actual backend tasks, simulated for the bundled fixture.
- **Playback mode:** live stream, saved provenance or explicitly recorded replay.
- The coordinator is a deterministic workflow controller. Retrieval, filtering, mapping, evidence assembly and verification are deterministic tools. Brief synthesis is a single optional model-backed explanation call, or a clearly labelled deterministic fixture explanation. The provider adapter can make one repair call; it is not a separate autonomous worker.
- The chamber does not claim independent multi-agent execution. OpenRouter is a provider dock; local files/Atlas are store docks. Neither is labelled an agent.
- Tools execute sequentially according to the declared dependency graph. The coordinator remains active while coordinating them. No independent worker parallelism is simulated.
- The source records, assay counts, matches and coverage come from actual tool results. Unmapped candidates are retained. Geometry checks calculate real Euclidean distances in **demo** units, at radius 12 for the recorded workflow.
- An explanation failure produces a saved partial deterministic result with terminal state `needs_review`. It is never converted into a green full-success result. Hard failures and cancellation remain visible.

## API and compatibility

The existing synchronous API remains compatible:

```text
POST /api/investigations                    → 201 Investigation
```

The chamber opts into asynchronous execution:

```text
POST /api/investigations?execution=live      → 202 RunSnapshot (queued)
GET  /api/investigations/{run_id}            → RunSnapshot
GET  /api/investigations/{run_id}/events     → SSE, saved + live events
POST /api/investigations/{run_id}/cancel     → cancellation acknowledgement
GET  /api/chamber/fixture                   → simulated RunSnapshot
GET  /api/chamber/fixture/export            → labelled simulated Markdown brief
```

Saved investigation IDs retain their original GET/export behavior. Run snapshots point to an independently persisted investigation result. Each run stores its original question, criteria, selection, capacity, dataset version, store, provider, model, artifacts and event history.

SSE sends `event: run-event`, a stable `id: {run_id}:{sequence}` and a typed JSON payload. Reconnect with `Last-Event-ID` or `?after=<sequence>`; the higher valid cursor wins. Heartbeats are SSE comments, not progress events. Unknown runs return 404. The client sorts/de-duplicates recorded events and rebuilds task state independently of rendering or replay animation. A final snapshot supplies authoritative results.

## Persistence, restart and cancellation

Local files use atomic per-run JSON snapshots under `var/runs/`. Atlas mode uses a `runs` collection, provisioned by the seed command. Persisted events have monotonically increasing per-run sequence numbers. Existing saved investigations and exports are unchanged.

Execution runs in a background asyncio task in the **single backend process**, not inside the SSE generator. Closing a tab or losing the stream does not cancel a job. No production queue or distributed lease is implemented. Do not run multiple worker processes against this development manager.

On a backend restart, any persisted nonterminal job is marked **failed / interrupted** with a recovery event. It is not silently resumed, rerun or billed again. Start a new investigation explicitly. Completed provenance remains available. The browser restores the last live run ID after refresh.

**Cancel run** first records `cancellation_requested`; the worker then confirms `cancelled`. Cancellation interrupts the local task and its in-flight HTTP client request. The remote provider may still process or charge for a request already submitted; provider-side compute cancellation is not guaranteed. Queued/active tasks are visibly cancelled and no later model result is accepted. If the brief has already been committed, completion wins and the event log explains that cancellation arrived after commit. Cancelling an already terminal run is idempotent.

## Fixture and verification

Regenerate the tracked, deterministic simulated recording without any API key or model invocation:

```sh
backend/.venv/bin/python scripts/chamber_fixture.py
```

Backend tests cover sequence/dependency order, SSE cursor reconnection, saved run persistence, model-error partial results, cancellation of an in-flight asynchronous test call, unknown IDs, hard failure and interrupted-job recovery. Frontend reducer checks cover replay reconstruction, out-of-order/repeated delivery, terminal authority and absence of future artifacts. Browser checks cover live start → inspect worker → open saved output, refresh reconstruction, fixture replay, linked protein selection, reduced motion and WebGL fallback.

No extra paid provider calls are required to run these tests: Playwright explicitly overrides the provider/key to an isolated mock configuration.
