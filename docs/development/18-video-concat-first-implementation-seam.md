# Video Concat First Implementation Seam

## Purpose

This document follows:

- [`16-video-concat-formulation.md`](./16-video-concat-formulation.md)
- [`17-video-concat-admissibility-contract.md`](./17-video-concat-admissibility-contract.md)

Its goal is to define the smallest coherent first implementation move for video concat.

This is not a full implementation plan for all future concat variants.
It is the narrowest seam that:

- preserves branch identity
- enforces admissibility explicitly
- avoids contaminating ordinary `video_download`

## Governing Ambiguity

The remaining ambiguity is not conceptual anymore.
It is practical:

- where should the first real `video_concat_download` path enter the codebase so that the new feature is explicit but low-blast-radius

## Recommendation

Do **not** implement video concat by patching ordinary:

- `/vid`
- `always_ask_menu.py`
- `down_and_up()` normal playlist flow

Instead:

- introduce concat as a distinct command/branch entry surface
- give it its own executor module
- make ordinary `video_download` unaware of concat-specific policy except through shared helpers where truly appropriate

## First Command Surface

Use the already-established UX direction:

- `/concat ...`

While audio concat remains:

- `/concat --audio-only ...`

The first video implementation should make plain `/concat ...` mean:

- explicit `video_concat_download`

## First BranchSelectionResult Shape

The first result object for video concat should explicitly carry:

- `branch_family="video_concat_download"`
- `selected_by="explicit_command"`
- `task_scope="playlist_range"`
- `delivery_intent="telegram_media"`
- `media_intent="video"`
- `quality_intent="video_concat"`
- `execution_source="fresh_acquisition"`
- provenance:
  - `command="/concat"`
  - `concat_policy="direct_concat_only"`
  - `ordering="original"` or `ordering="reverse"`

## First RuntimeTask Additions

The minimal additions that likely belong on `RuntimeTask` are:

- concat ordering policy
- concat mode / media type
- concat policy
- optional output name override

These fields should be task-level because they are constitutive of the requested concat task, not incidental executor flags.

## First Executor Boundary

Add a new module, conceptually:

- `DOWN_AND_UP/video_concat.py`

Why:

- keeps concat-specific acquisition/transformation separate from ordinary video delivery
- lets concat have its own terminalization semantics
- avoids pushing policy-specific branches into already-large `down_and_up.py`

## First Shared Reuse Surface

Video concat may reuse only these kinds of existing helpers at first:

- range parsing
- cookie/proxy helpers
- preflight directory handling
- logging and terminal-outcome scaffolding

It should not initially reuse:

- ordinary playlist delivery loops as if concat were just another postprocessor

That would blur task identity again.

## First Admissibility Policy

The first implementation should hard-code:

- `direct_concat_only`

That means:

1. acquire selected staged video artifacts
2. inspect compatibility explicitly
3. if incompatible, reject/fail with concat-specific reason
4. do not normalize/re-encode yet

This is the cleanest first seam because it does not hide a second transformation policy inside the same feature.

## First Compatibility Predicate

The first implementation needs one explicit helper that answers:

- can these staged video artifacts be directly concatenated under current policy

This helper should return:

- boolean admissibility
- compact reason if false

It should not immediately run FFmpeg and infer admissibility from failure text alone.

## First TerminalOutcomeResult Shape

The first concat terminalization should be explicit about the requested unit.

Recommended coarse outcomes:

- `artifact_delivery_success`
  one composite video delivered
- `determinate_rejection`
  concat was not admissible under selected policy
- `acquisition_or_transformation_failure`
  selected branch was valid, but staging or concat failed
- `artifact_ready_delivery_failure`
  composite artifact exists locally, Telegram delivery failed

Avoid:

- treating per-item acquisition counts as if they were the requested unit
- using ordinary playlist "partial completion" semantics as the default

## What To Reuse From Existing Refactor

The current PDA-driven runtime model already gives useful seams:

- `BranchSelectionResult`
- `RuntimeTask`
- `TerminalOutcomeResult`

The first video concat implementation should plug into those rather than inventing parallel ad hoc state.

## What Not To Solve In First Patch

Do not solve these in v1:

- normalized/re-encoded concat
- subtitle merging across items
- mixed container/codec recovery
- composite thumbnail synthesis
- final composite cache reuse
- concat via Always Ask callback menu

Those are later moves.

## Suggested Implementation Order

1. extend command parsing for plain `/concat ...` into explicit video-concat task
2. add `video_concat_download` branch factory
3. extend `RuntimeTask` with minimal concat-specific fields
4. add `video_concat.py`
5. implement staged acquisition under explicit concat policy
6. implement explicit compatibility check
7. implement direct concat execution
8. emit explicit terminal outcome

## Why This Is The Right Seam

It is the smallest move that keeps the feature coherent because:

- branch identity stays explicit
- admissibility stays explicit
- terminal semantics stay explicit
- ordinary video-download code is not forced to impersonate a fundamentally different task class

That is the correct PDA-preserving first implementation boundary.
