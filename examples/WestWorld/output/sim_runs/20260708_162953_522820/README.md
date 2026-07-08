# West World Simulation Run

- `timeline.jsonl`: initial and tick-end aggregate snapshots.
- `agent_states.jsonl`: query-safe state rows without private feedback, messages, memory, or full plan traces.
- `internal/agent_states.jsonl`: full state rows for private diagnostics.
- `scene_snapshots_public.jsonl`: replay-safe scene state without hidden notes.
- `scene_snapshots_internal.jsonl`: private diagnostics with hidden notes and pending actions.
- `world_objects_snapshots.jsonl`: world-level object registry snapshots (objects + ledger) per tick.
- `model_traces.jsonl`: query-safe request summaries without prompts or model output.
- `internal/model_traces.jsonl`: full prompts, model output, parsed output, and available usage.
- `events.jsonl`: ordered lifecycle and phase events.
- `raw/llm_attempts.jsonl`: one row per provider attempt, including failures, retries, latency, and exact usage.
- `views/`: query-oriented tick, agent, location, slow-request, and failure views.
- `summary.json` and `report/report.md`: aggregate run diagnostics.
- `inputs/`: archived inputs; model credentials are redacted.

Do not expose `scene_snapshots_internal.jsonl` or `internal/` to agents or a public frontend.
