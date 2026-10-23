# Variant Atlas — live 3D investigation chamber

UI and implementation addendum · 24 October 2026

## The requested experience

When the researcher starts an investigation, reveal a transparent, three-dimensional glass chamber containing the investigation's active workers, connected data sources and results. The researcher should feel able to look inside the research workflow: see what is running, what it is inspecting, what it has produced and what is waiting on another result.

This replaces the screenshot's passive “Running & saving…” experience with an inspectable live workspace. Keep the existing question, title, candidate capacity and explanation settings in a compact context header. The chamber becomes the main investigation view; the question and selected criteria remain visible.

**Design statement:** A scientific investigation unfolding inside a glass instrument, with visible handoffs between workers and evidence flowing into a reviewable result.

## What the user sees

On pressing “Start investigation,” the view expands smoothly into a dark, translucent glass chamber. A coordinator node sits above a group of specialist nodes arranged at different depths. Labelled data-source docks sit around the chamber's edge. The output tray sits below the workers. Keep labels readable from the default camera angle; avoid an orbit that hides the workflow.

The chamber has subtle glass edges, gentle reflections, restrained lighting and a faint depth grid. Nodes look like compact luminous instruments with readable labels, rather than humanoid avatars. Connections carry small moving packets only while actual work or a handoff is occurring. A selected node is brought into focus and opens a concrete activity panel.

The protein viewer and investigation chamber are two linked views of the same run. Do not mix the worker network with the protein structure so thoroughly that neither can be understood. Provide “Workflow” and “Protein” tabs, plus an optional desktop split view. A structure-related tool result can focus the relevant variants in the protein view.

## Example visible sequence

1. **Coordinator:** “Starting investigation with your declared criteria.”
2. **Data retrieval worker:** “Loaded 8 variant records and 2 assay datasets.”
3. **Assay analysis tool:** “5 variants meet the filters; 1 has missing activity data.”
4. **Structure mapping worker/tool:** “3 matching variants mapped; 2 lack coordinates.”
5. **Evidence review worker:** “Checking source records and assay context.”
6. **Verification tool:** “Checking identifiers, measurements and evidence references.”
7. **Coordinator:** “Review brief ready.”
8. **Output tray:** shortlist, evidence gaps, follow-up questions and export.

These counts describe the previously specified synthetic fixture only. Real runs must display their actual counts. The sequence is illustrative; independent work may overlap only if the backend really runs it concurrently.

## Worker roles and truthful labels

| Node | Responsibility | Typical visible output |
| --- | --- | --- |
| Coordinator | Manage run state and delegate bounded work | Task started, dependency ready, brief ready |
| Data retrieval | Load variants, assay metadata and evidence | Records retrieved, source/version, retrieval failure |
| Assay analysis | Apply explicit selection criteria | Matching IDs, missing measurements, filter reasons |
| Structure mapping | Validate residue mapping and calculate neighbours | Mapping coverage, rejected mappings, distances |
| Evidence review | Compare supplied evidence and identify limitations | Referenced findings and unresolved questions |
| Verification | Validate identifiers, values and citations | Checks passed, failed or unavailable |
| Brief synthesis | Summarize verified outputs for review | Review brief and proposed follow-up questions |

Use node badges to distinguish **LLM agent**, **deterministic tool**, **database** and **output**. These roles are not a requirement to create seven separate LLM calls. The initial workflow may use one model call plus several tools. Label that accurately. Only call the system multi-agent when independent model-backed workers are implemented; show real delegation and handoff events then.

OpenRouter is a model provider, not a worker. Atlas is a data store, not an agent. Show the actual configured store/provider; do not show a successful Atlas retrieval when the application used local fixtures.

## Visual language

- Background: deep navy, consistent with the supplied screenshot.
- Chamber: transparent smoked glass, thin cyan edges and understated depth cues.
- Queued: muted slate and a readable waiting label.
- Running: cyan outline with a gentle pulse.
- Completed: teal check and static illumination.
- Needs review: amber marker and explanation.
- Failed: restrained red marker and actionable error details.
- Cancelled: grey stop marker.
- Handoffs: short labelled arcs such as “variant records,” “mapping results” and “verified evidence.”

Never rely on colour alone. Use icons, labels and state text. Avoid a screen full of glowing wires. Hover or selection can reveal detailed edges; keep the default view focused on current work and immediate dependencies. Provide reset view, zoom, pause visual motion and an accessible 2D timeline fallback.

Motion is tied to events: illuminate a node on task start, animate a packet on handoff, settle the node on completion and draw attention to an error only once. Do not animate continuous database traffic while nothing is happening. Waiting on a remote response can show elapsed time and “Awaiting response”; do not fabricate intermediate progress or percentages.

## Interaction details

Click a worker to open a drawer containing:

- Worker name, type and current status.
- Current task, expressed in plain language.
- Start/end times and elapsed duration.
- Input summary with links to permitted source records.
- Completed tool calls, result summaries and evidence IDs.
- Check outcomes, missing information and errors.
- Output links and downstream consumers.

Show observable execution events and concise task summaries, not hidden model chain-of-thought, raw system prompts or private reasoning. Avoid logging credentials or sensitive payloads.

Click a handoff to see which records or artifact were passed. Click a data dock to inspect the actual source/version and record counts. Click an output card to open the saved shortlist or brief. Each result retains the investigation's dataset version, filters and model identity.

At completion, keep the chamber available as a static provenance view. Offer replay of recorded events with an explicit “Recorded replay” label and playback controls. Pausing replay or visual motion does not pause backend execution. A separate “Cancel run” control requests real cancellation; display “Cancellation requested” until the backend confirms it. Define whether an in-flight model request can actually be interrupted.

## Backend event contract

Use Python/FastAPI to publish structured run events, consumed by React. Server-Sent Events are sufficient for the first version; use HTTP POST for start/cancel. Do not poll model prose to infer worker state.

Suggested routes:

- `POST /api/investigations`: create a run and return `run_id` promptly.
- `GET /api/investigations/{run_id}/events`: stream saved and live events.
- `GET /api/investigations/{run_id}`: current run snapshot and outputs.
- `POST /api/investigations/{run_id}/cancel`: request cancellation.

If the existing start endpoint currently returns only after completion, preserve compatibility or version the response contract. Keep worker execution outside the request stream so disconnecting the viewer does not destroy run state. A durable job queue is a later production requirement; a local development worker is acceptable if restart limitations are documented.

Example event:

```json
{
  "event_id": "run-demo-001:12",
  "run_id": "run-demo-001",
  "sequence": 12,
  "timestamp": "2026-10-24T10:00:03Z",
  "type": "tool.completed",
  "worker_id": "assay-analysis",
  "worker_kind": "deterministic_tool",
  "task_id": "filter-variants",
  "parent_task_id": "investigate",
  "status": "completed",
  "summary": "5 variants meet the declared criteria.",
  "input_refs": ["assay-activity-demo", "assay-abundance-demo"],
  "output_refs": ["artifact-filter-results"],
  "metrics": {"matching_variants": 5},
  "mode": "fixture"
}
```

Support run/task started, completed, failed and cancelled events; task queued; handoff; warning; tool start/completion; artifact created; run needs-review. Persist events with a monotonically increasing sequence per run and stable task IDs. De-duplicate on the client, support reconnection using the last event ID and rebuild the view from persisted events plus a snapshot. Use heartbeat messages for connectivity, not fictional progress.

Agent handoffs must include sender, recipient and artifact references. Dependency edges come from the actual task graph; a node cannot complete before its required tools complete. Terminal states are authoritative. A failed step can lead to a clearly labelled partial result or failed run, never a green success animation by default.

## React and 3D implementation

Use React Three Fiber and Drei for the chamber, with accessible HTML overlays for labels and controls. Use a small fixed layout initially; an automatic force layout is unnecessary. Prefer lightweight translucent panels and a few lines over expensive refraction effects. Keep camera movement bounded and ensure text does not become illegible behind glass.

Suggested components:

```text
InvestigationWorkspace
  InvestigationContextHeader
  InvestigationViewTabs
  InvestigationChamberCanvas
    GlassChamber
    WorkerNode
    DataSourceDock
    HandoffEdge
    OutputTray
  WorkerDetailDrawer
  ExecutionTimeline
  RunControls
```

Create a typed event reducer separate from animation code. The reducer builds task status, dependencies and artifact references; the renderer visualizes that state. Business logic must not depend on animation completion. Honour prefers-reduced-motion, clean up WebGL resources and streams, and retain keyboard operation. In reduced-motion mode show static edges and immediate state changes.

## Dummy-data milestone

First implement a deterministic recorded fixture event sequence and label it **“Simulated workflow — synthetic data.”** This makes visual development possible without model/API keys. Next connect the same event contract to real backend tasks and OpenRouter calls. Show “Live execution” only for actual backend execution; synthetic scientific inputs can still be used, but remain labelled separately.

Support distinct labels for data mode, execution mode and playback mode. For example: “Synthetic data · Live execution” is different from “Synthetic data · Recorded replay.” An animation alone does not prove multi-agent execution.

## Acceptance criteria

1. Starting an investigation opens the chamber with the original objective and criteria retained.
2. Nodes and handoffs reflect real events or an explicitly labelled fixture replay.
3. Selecting a node reveals its actual inputs, outputs, status and evidence references.
4. Database and deterministic-tool nodes are distinguishable from LLM agents.
5. Parallel activity appears only when tasks genuinely overlap in the event history.
6. Errors, partial results, missing mappings and cancellation stay visible.
7. Refresh/reconnect reconstructs the run without duplicating nodes or events.
8. Completed outputs open the existing shortlist, evidence and export views.
9. The protein view and chamber share run/variant selection but retain distinct scientific and execution meanings.
10. Keyboard navigation, reduced motion and the 2D fallback remain functional.
11. Tests cover event order/de-duplication, reconnect, failure and cancellation; one browser flow covers start -> inspect worker -> open output.

## Instruction to Codex

Implement this as an extension of the existing investigation UI shown in the supplied screenshot. Preserve its criteria-based selection and saved investigation behaviour. The principal upgrade is an interactive, transparent 3D execution view that makes the workflow inspectable. Begin with fixture events, then wire genuine execution events through the same interface. Deliver a polished working experience with honest execution labels, not a decorative loading animation.
