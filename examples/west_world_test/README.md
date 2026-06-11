# West World Recorder MVE

This experiment compares two independent dynamic-environment recorders against
the same fixed event sequence and Oracle truth.

## Evaluation Protocol

- Every event explicitly declares `affected_probe_ids`; event relevance is not
  guessed from the event target.
- `pour_whiskey` increases `glasses_filled` and does not consume or destroy an
  intact glass.
- Probes are split into `visual_physical` and `hidden_knowledge`.
- `visual_physical` is the primary Text-vs-Image comparison score.
- `hidden_knowledge` is reported separately because private ownership and
  witness knowledge are not representable by a pure image state.

## Recorder Methods

### Text Recorder

```text
previous text state + event
  -> qwen3.5-flash
  -> next text state
  -> qwen3.5-flash answers probes from text
```

### Image Recorder

```text
initial scene description
  -> Image 2 images.generate
  -> initial world-state image

previous world-state image + event
  -> Image 2 images.edit
  -> next world-state image
  -> qwen3.5-flash answers probes from the current image
```

The Image Recorder does not keep `scene_text` or use a text LLM to update its
state. Its only persistent dynamic state is the current image handle.

This comparison intentionally changes both the storage medium and the update
mechanism. Errors can therefore come from image generation/editing, accumulated
visual drift, or visual question answering.

## Important Limitation

An image can represent visible physical state, but it cannot naturally encode
private knowledge such as "Dolores did not witness a hidden event." Visibility
probes expose this limitation rather than solving it. A production Recorder
still needs structured access-control or witness metadata for non-visual facts.

## Model Configuration

The local credential file is ignored by Git:

```bash
cp examples/west_world_test/configs/models_config.example.yaml \
   examples/west_world_test/configs/models_config.yaml
```

The configured Image 2 endpoint must provide OpenAI-compatible `images.generate`
and `images.edit` methods. If its API differs, adapt
`adapters/model_clients.py` without changing the experiment core.

## Run

Phase A, without Ray or Redis:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.core.compare --method both
```

Phase B, through the distributed kernel:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.run_test
```

Plot results:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.eval.plot
```

Run a fully archived comparison:

```bash
PYTHONPATH=packages/agentkernel-distributed:. \
python -m examples.west_world_test.eval.run_archived_comparison
```

Each archived run contains every model request and response in
`model_traces/all_calls.jsonl`, every image state, raw scored results,
event-by-event statistics, a global report, provenance, and checksums.
