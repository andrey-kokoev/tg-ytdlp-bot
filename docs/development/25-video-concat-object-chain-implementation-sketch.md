# Video Concat Object Chain Implementation Sketch

## Purpose

This document follows:

- [`21-video-concat-transition-contract.md`](./21-video-concat-transition-contract.md)
- [`22-video-concat-staging-manifest-model.md`](./22-video-concat-staging-manifest-model.md)
- [`23-video-concat-terminal-rendering-contract.md`](./23-video-concat-terminal-rendering-contract.md)
- [`24-video-concat-chapter-policy-model.md`](./24-video-concat-chapter-policy-model.md)

Its goal is to define the smallest coherent first implementation of the full
`video_concat_download` object chain.

This is the point where the PDA descent stops being mainly conceptual and becomes an executable
architecture sketch.

## Governing Ambiguity

The live ambiguity is now practical:

- what exact first patch shape would introduce video concat without diffusing its state across
  existing playlist/video code

The key is to preserve one explicit chain:

- branch selection
- task materialization
- staging manifest
- compatibility result
- concat execution result
- terminal outcome

## First-Patch Scope

The first implementation should be intentionally narrow.

### Included

- explicit `/concat ...` video path
- playlist range selection
- optional reverse ordering
- optional output name override
- explicit `chapter_policy="none"`
- direct concat only
- explicit incompatibility rejection
- one composite Telegram video output

### Excluded

- always-ask menu integration
- normalized/re-encoded concat
- chapter generation
- concat cache reuse
- subtitle merging
- mixed-media recovery
- partial multi-output fallback

## First Command Surface

The first implementation should extend the current unified command UX:

- `/concat ...`

with this rule:

- `/concat --audio-only ...`
  routes to existing audio concat
- plain `/concat ...`
  routes to new `video_concat_download`

This keeps the UX coherent while keeping execution distinct.

## First Branch Factory

Add a branch factory conceptually like:

- `video_concat_branch(...)`

Expected output:

- `branch_family="video_concat_download"`
- `selected_by="explicit_command"`
- `task_scope="playlist_range"`
- `delivery_intent="telegram_media"`
- `media_intent="video"`
- `quality_intent="video_concat"`
- `execution_source="fresh_acquisition"`

Provenance should include:

- `command="/concat"`
- `concat_policy="direct_concat_only"`
- `ordering="original" | "reverse"`
- `chapter_policy="none"`

## First RuntimeTask Additions

The minimal additional task fields should be:

- `concat_policy`
- `concat_ordering`
- `chapter_policy`
- `output_name_override`
- `video_concat_manifest`
- `video_concat_compatibility`
- `video_concat_execution`

These are task-level because they govern the requested composite artifact, not incidental executor
flags.

## First New Module Boundary

Add a dedicated module:

- `DOWN_AND_UP/video_concat.py`

This module should own the concat-local orchestration, not `down_and_up.py`.

Why:

- ordinary video delivery remains a different task class
- concat has different admissibility and terminal semantics
- a separate module keeps the first patch low-blast-radius

## First Internal Object Chain

The first implementation should make these objects explicit in order:

1. `BranchSelectionResult`
2. `RuntimeTask`
3. `VideoConcatStagingManifest`
4. `VideoConcatCompatibilityResult`
5. `VideoConcatExecutionResult`
6. `TerminalOutcomeResult`

The first patch does not need all of these as dataclasses immediately, but each must exist as one
explicit object boundary.

## First Staging Strategy

The first staging strategy should be:

1. resolve playlist range into ordered selected items
2. download each item as a staged video artifact into a concat-specific working directory
3. build the explicit staging manifest
4. stop if manifest is incoherent

The staging strategy must not:

- silently skip failed items
- silently continue with a smaller compatible subset

Under `direct_concat_only`, selected-set integrity matters.

## First Compatibility Strategy

The first compatibility strategy should:

1. inspect the manifest only
2. compare direct-concat-relevant media fields
3. return one explicit compatibility result
4. reject before FFmpeg concat if incompatible

This should happen before any concat list file is executed.

## First Concat Execution Result

The first implementation needs one explicit execution result object or dict-like carrier.

Minimal fields:

- `succeeded: bool`
- `artifact_path: str | None`
- `reason_code: str | None`
- `phase: str`
- `evidence: dict`

Why:

- concat execution failure must stay distinct from incompatibility
- artifact-ready delivery failure must stay distinct from concat execution failure

## First Terminal Mapping

Map the chain like this:

- incompatible manifest
  -> `determinate_rejection`
- compatible manifest + concat failure
  -> `acquisition_or_transformation_failure`
- composite artifact exists + Telegram delivery fails
  -> `artifact_ready_delivery_failure`
- composite artifact delivered
  -> `artifact_delivery_success`

The requested unit remains:

- one composite video

not:

- `N/M` playlist items

## First Rendering Contract Usage

The first implementation should use concat-specific rendering from the beginning.

That means:

- success says concat completed
- rejection says direct concat is not possible under current policy
- failure says composite creation failed
- delivery failure says composite exists but Telegram delivery failed

It should not inherit ordinary playlist status text.

## First Filesystem Boundary

The working directory should be concat-specific, for example under:

- `users/<id>/downloads/.../video_concat_*`

The composite output and the staged artifacts should live inside one task-local directory until
terminalization and cleanup.

This preserves task-local evidence and simplifies cleanup.

## First Logging Boundary

The first implementation should log one summary line at each major step:

- branch selected
- staging complete
- compatibility result
- concat execution result
- terminal outcome

This is enough to make the branch inspectable without making it noisy.

## First Tests

The first implementation tests should focus on the object chain, not on Telegram live behavior.

Recommended first tests:

1. `/concat` without `--audio-only` creates `video_concat_download`
2. reverse option is preserved on task and manifest ordering
3. mixed media shape yields explicit `determinate_rejection`
4. compatible set yields explicit concat execution attempt
5. concat execution failure maps to transformation failure
6. successful composite delivery maps to artifact success
7. rendering uses concat-specific wording, not playlist partial wording

## What Must Not Be Smuggled Into V1

Do not silently add:

- re-encode fallback
- chapter generation
- partial subset concat
- ordinary playlist delivery fallback
- implicit cache reuse semantics

Those are separate future policy moves.

## Why This Is The Correct PDA Stop Point

At this point, the branch has:

- explicit formulation
- explicit admissibility
- explicit compatibility result
- explicit local transition contract
- explicit manifest
- explicit rendering contract
- explicit chapter-policy separation
- explicit first implementation chain

That is enough structure to begin real implementation without immediately collapsing back into
hidden arbitrariness.
