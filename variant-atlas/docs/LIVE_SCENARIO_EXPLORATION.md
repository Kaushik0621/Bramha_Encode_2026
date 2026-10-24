# Live scenario exploration

## Product behavior

Start **multi-agent exploration** from the research question panel, or investigate a comparison from the workbench. The configured brain declares up to ten distinct, ranked PTEN scenarios. Ten is a ceiling, not a fabricated target: redundant or unsupported directions should not be added just to fill the board.

The chamber shows:

- The actual brain provider/model and active direction.
- Proposed, exploring, parked, rejected, completed and inconclusive paths.
- Each path's research question, rationale, planned capabilities, assigned specialist agents, actual tool artifacts, public decision history and declared outcome.
- Why directions changed, including evidence-linked model decisions and execution routing based on a selected capability.
- Unvisited and unresolved work when time, step or request budgets stop execution.

Selecting a path opens its outputs; selecting an artifact opens the responsible agent's checkpoint. Replay reconstructs paths from durable path-state artifacts available at that event cursor, rather than displaying later outcomes early. Existing runs without plans retain their task graph and timeline.

## Brain and tools

Argon uses the existing Google adapter when configured. The currently authorized development path is OpenRouter/local; the interface reports that identity explicitly. No OpenRouter run is presented as verified Argon execution.

The catalog currently contains **30 implemented capabilities**, searchable by purpose and inspectable with typed schemas. The agent can call `discover_tools` to find permitted capabilities, then grant a subset to a specialist. There are no hundreds of aliases counted as tools. Reaching hundreds requires integrating distinct, useful data sources and validated scientific operations; the registry can accommodate those additions.

## Actual orchestration

- `ResearchRequest.explore_paths=true` enables the planning loop; the UI enables this on new research starts. API clients can retain the older loop by leaving it false.
- `plan_paths` accepts unique typed proposals, with existing parent references, permitted expected tools and a global ten-path ceiling. The first ranked direction is activated by runtime policy.
- `update_path` records public reasons, evidence references, status and an optional next direction. Resolved paths are immutable. Completed paths require an existing successful tool artifact; this mechanical check does not prove the interpretation scientifically.
- Only the coordinator changes the global plan. Specialists inherit an active path unless the brain explicitly assigns another available path.
- The brain's selected tool is routed to an existing compatible scenario when its scientific scope changes. This deterministic routing policy is recorded as such; it is not invented biological reasoning. An assigned specialist's first tool attempt enters its path.
- Tool results and events carry `path_id`. Path state snapshots, task handoffs and events are persisted before the browser receives updates.
- Existing concurrent workers, scope permissions, depth limits, request/tool/time budgets, cancellation, identity/numeric/evidence gates and review limitations remain enforced.
- Explicit abstention and budget exhaustion are recorded as abstention, rather than claiming successful scientific completion.

## Boundaries and evidence

Path outcomes are public model judgments with artifact links. They do not expose hidden chain-of-thought, prove causal mechanisms or simulate combined mutants. A proposed scenario can remain unvisited, and an explored scenario can remain unresolved. Research measurements retain their native scales and separate assay contexts.

Backend tests exercise ten-path limits, permissions, evidence requirements, immutable outcomes, direction switching, scoped discovery, live-loop delegation, path attribution and execution-based routing. The browser test uses an explicitly scripted execution fixture to check artifact inspection, unvisited-work messaging, tool search and replay without future outcomes.

`artifacts/RESEARCH_EXPLORATION_LIVE.json` preserves an actual OpenRouter development run: eight proposed paths, three agents including the coordinator, eight tool calls, and a stop at the twenty-request ceiling. That run exposed tracking issues subsequently fixed in the tested runtime. It is **not** a complete scientific investigation or a strict autonomous reference pass.
