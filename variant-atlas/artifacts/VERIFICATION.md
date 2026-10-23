# Verification — investigation chamber (24 October 2026)

- Read the investigation-chamber addendum and implemented it as an extension of the existing separate frontend/backend application.
- Production TypeScript/Vite build: passed.
- Backend suite: **33 passed**, including original scientific/business contracts plus event/dependency order, SSE reconnect cursor, persistence, cancellation, partial results, hard failure and interrupted-run recovery.
- Playwright suite: **9 passed**: seven browser flows and two event-reducer checks. Includes live start → inspect tool → open output → refresh reconstruction, simulated replay, linked protein selection, source/artifact inspection, existing filter/export workflow, reduced motion and WebGL fallback.
- Desktop chamber screenshot captured and visually inspected: `investigation-chamber.png`.
- A real configured OpenRouter run completed using `x-ai/grok-4.3`: asynchronous POST returned 202/queued; **40 live SSE events arrived in sequence**; result mode was `openrouter`; the review brief was saved. Only synthetic scientific inputs were used.
- Live verification run: `run-70250db194f649f5b612ab3ba20ab571`.
- Saved review brief: `inv-172eaa0661c84ac784ba9863a8d637cb` (visible in saved investigations as “Chamber live integration check”).
- Credential audit: 74 project/build/artifact/state files scanned; the key was absent outside the private backend `.env` (`0600`).
- Servers left running at backend `0.0.0.0:8000` and frontend `http://localhost:8500`.

The chamber's coordinator and tools are deterministic. One optional model-backed explanation is not independent multi-agent execution. Live backend execution and recorded simulation have distinct labels. Playback does not run tools or pause the backend.

Development limitations: jobs run in one local backend process, without a production queue. Restart-interrupted jobs are marked failed and need an explicit new run. Cancellation interrupts the local HTTP request, but cannot guarantee cancellation of provider-side compute/billing. Atlas mode has not been exercised with live credentials. Real PTEN data and scientific validation remain deferred.

Non-blocking dependency notices remain: Three.Clock deprecation, Vite's 3D bundle-size advisory and Starlette's test-transport migration warning. The completed browser flows had no page errors.
