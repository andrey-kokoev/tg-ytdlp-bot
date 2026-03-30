# Video Concat Compatibility Result Model

## Purpose

This document follows:

- [`19-video-concat-compatibility-model.md`](./19-video-concat-compatibility-model.md)

Its goal is to define the explicit result object produced by the first
`video_concat_download` compatibility check.

The compatibility layer should not return:

- raw FFmpeg stderr
- a bare boolean
- ad hoc tuples interpreted differently by callers

It should return one explicit result shape.

## Governing Ambiguity

The live ambiguity is now narrower:

- what exact object should represent concat compatibility so that branch execution, rejection, and
  terminalization remain coherent

Without this object, the implementation would likely regress into:

- `if not ok: send error`
- implicit branch mutation
- executor-local mismatch handling

## Required Role

The compatibility result object exists to answer one question:

- may this selected and staged set proceed into direct concat under the current policy

It should not answer:

- how Telegram delivery will work
- whether the output is too large
- whether captions/thumbnails are available

Those are later transition concerns.

## Recommended Shape

The first object should carry:

- `compatible: bool`
- `policy: str`
- `reason_code: str | None`
- `reason_text: str | None`
- `mismatch_surface: str | None`
- `evidence: dict`

Recommended semantics:

- `compatible`
  whether the staged set is admissible for direct concat
- `policy`
  normally `direct_concat_only` in v1
- `reason_code`
  stable identifier for rejection/testing/logging
- `reason_text`
  compact human-readable explanation
- `mismatch_surface`
  the highest-level dimension of incompatibility
- `evidence`
  compact structured mismatch details

## Why `mismatch_surface` Matters

`reason_code` alone is too fine-grained for all downstream decisions.

The higher-level `mismatch_surface` helps preserve coherent grouping, for example:

- `artifact_presence`
- `container_shape`
- `video_stream_shape`
- `audio_stream_shape`
- `stream_layout`

This lets logs and terminal rendering stay compact without losing specificity.

## Example Result Shapes

Compatible:

```text
compatible=True
policy="direct_concat_only"
reason_code=None
reason_text=None
mismatch_surface=None
evidence={
  "container": "mp4",
  "video_codec": "h264",
  "audio_codec": "aac",
  "width": 1280,
  "height": 720,
  "fps": 30.0,
  "count": 4
}
```

Incompatible due to mixed resolution:

```text
compatible=False
policy="direct_concat_only"
reason_code="mixed_resolution"
reason_text="Selected videos do not share one resolution."
mismatch_surface="video_stream_shape"
evidence={
  "heights": [720, 1080],
  "widths": [1280, 1920]
}
```

Incompatible due to missing staged item:

```text
compatible=False
policy="direct_concat_only"
reason_code="missing_staged_artifact"
reason_text="One or more selected items did not produce a staged video file."
mismatch_surface="artifact_presence"
evidence={
  "missing_indices": [4]
}
```

## Constitutive vs Derived Fields

Constitutive:

- `compatible`
- `policy`
- `reason_code`
- `mismatch_surface`
- enough `evidence` to justify the determination

Derived:

- display formatting
- terminal message suffixes
- log rendering

The object should stay close to the determination itself, not pre-rendered UI.

## Precedence

If more than one incompatibility exists, the result should report one primary incompatibility,
not an unordered bag.

Suggested precedence:

1. `artifact_presence`
2. `container_shape`
3. `video_stream_shape`
4. `audio_stream_shape`
5. `stream_layout`

Why:

- missing staged artifacts means concat cannot even be meaningfully evaluated yet
- container and stream incompatibilities are more constitutive than layout refinements

The goal is not to report every defect.
The goal is to return one coherent primary reason.

## RuntimeTask Consequence

The task should retain the compatibility result, because concat admissibility is part of task
history, not only executor-local state.

Recommended task write:

- `task_context.video_concat_compatibility = compatibility_result`

That makes later outcome rendering and debugging more coherent.

## TerminalOutcomeResult Consequence

If compatibility fails, terminalization should derive from this result rather than rebuilding
reasoning from scratch.

Recommended mapping:

- `compatible=False`
  -> `outcome_kind="determinate_rejection"`
  -> carry `reason_code`
  -> optionally carry `evidence`

This prevents incompatibility from mutating into generic transformation failure.

## Logging Consequence

Logs should record:

- policy
- compatibility verdict
- reason code
- mismatch surface

Logs should not dump huge raw probe payloads by default.

That keeps the compatibility layer inspectable without diffusing it into debugging noise.

## Tests Implied By This Model

The first tests should assert:

1. compatible set returns `compatible=True` and no rejection fields
2. mixed container returns:
   - `compatible=False`
   - `reason_code="mixed_container"`
   - `mismatch_surface="container_shape"`
3. missing artifact outranks codec mismatch
4. terminal rejection derives from compatibility result rather than generic exception formatting
5. task retains the compatibility result after evaluation

## Why This Is The Next Correct PDA Move

The previous document localized the compatibility decision surface.
This document gives that surface one explicit result object.

That is the next correct descent because implementation coherence now depends on having:

- one branch
- one policy
- one compatibility predicate
- one compatibility result

before any FFmpeg concat execution is introduced.
