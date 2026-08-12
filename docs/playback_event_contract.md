# Playback Event Contract

**Scope**: Frontend diagnosis dashboard (`frontend/src/components/StageTimeline.tsx`, `EvidenceGraphView.tsx`).

**Status**: Current implementation uses pseudo-playback derived from `DiagnosisResult.metadata.phases_completed`. This document defines the internal contract so a future backend SSE stream can replace the generator without changing UI components.

---

## Event source boundary

The UI consumes a **stage progression** abstraction, not raw backend messages.

```
Backend SSE / WebSocket messages
  -> Adapter (translates backend events into PlaybackEvent[])
  -> PlaybackController (manages current stage + play/pause/seek)
  -> StageTimeline + EvidenceGraphView (render)
```

Today the adapter is `useStagePlayback`: it reads `phases_completed` and `degradation_reason` and emits a discrete stage sequence.
Tomorrow the adapter can be replaced with one that receives SSE messages and pushes the same stage progression.

---

## PlaybackEvent schema

```typescript
type PlaybackEvent =
  | { type: "stage.start"; stage: StageId; timestamp: string }
  | { type: "stage.complete"; stage: StageId; timestamp: string }
  | { type: "highlight"; target: "root-cause" | "propagation-chain"; ids: string[]; timestamp: string }
  | { type: "complete"; timestamp: string }
  | { type: "error"; stage: StageId; reason: string; timestamp: string };

type StageId = "perception" | "topology" | "judge" | "rank" | "critic" | "assemble";
```

## Stage semantics

| Stage | Meaning | Canvas effect |
|---|---|---|
| `perception` | Alarm parsing complete | Nothing visible yet |
| `topology` | Topology + evidence graph built | Reveal `TOPOLOGY` edges |
| `judge` | Candidate propagation chains generated | Reveal `BELONGS_TO` + `PROPAGATES` edges dimly |
| `rank` | Candidates scored and ranked | Brighten propagation chain for top candidate |
| `critic` | Critic verdict produced | Reveal critic challenge markers |
| `assemble` | Final dossier assembled | Pulse root-cause node, lock final state |

## Ordering guarantees

1. Events for a given stage arrive in order: `stage.start` → zero or more `highlight` → `stage.complete`.
2. Stages are monotonic unless the user seeks backward via the timeline UI.
3. `complete` is emitted once after `assemble.complete`.
4. `error` can interrupt any stage; the timeline shows the stage in `error` state and stops playback.

## Seek behavior

When the user clicks a stage button, the controller must:

1. Pause playback.
2. Set `currentStage` to the selected stage.
3. Recompute visible graph elements as if all events up to and including `selectedStage.complete` have occurred.

This implies the UI treats `currentStage` as a **cursor** over the cumulative event stream, not just the latest event.

## Replacing pseudo-playback with SSE

Steps:

1. Create `useSSEPlayback(eventSourceUrl)` that returns the same shape as `useStagePlayback`:
   - `currentStage: StageId | null`
   - `playing: boolean`
   - `seek(stage)`, `play()`, `pause()`, `replay()`
2. Inside the hook, buffer SSE events into a `PlaybackEvent[]` and advance `currentStage` based on `stage.complete` events.
3. Pass the same `currentStage` into `StageTimeline` and `EvidenceGraphView`.
4. No changes to `StageTimeline` or `EvidenceGraphView` should be required.

## Current pseudo-playback mapping

`useStagePlayback` derives the cursor from `DiagnosisResult.metadata.phases_completed`:

- On new result: reset cursor, start playing.
- Every 900ms advance cursor to the next stage.
- A stage is "done" if it appears in `phases_completed` or the cursor has passed it.
- The current cursor stage is shown as `running`.

`EvidenceGraphView` maps the cursor to visible edge types via `revealedEdgeTypesForStage(stage)`.

---

## Notes

- This contract is intentionally small. It does not include per-agent log lines, token counts, or raw LLM outputs — those belong in a separate "raw trace" panel if needed.
- Highlight targets use node/edge `id` values from the evidence graph, so the backend must emit IDs consistent with the graph returned by `/api/v1/diagnose`.
