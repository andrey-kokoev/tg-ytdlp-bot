# Video Concat Staging Manifest Model

## Purpose

This document follows:

- [`21-video-concat-transition-contract.md`](./21-video-concat-transition-contract.md)

Its goal is to define the explicit manifest produced by the staging-acquisition transition for
`video_concat_download`.

This manifest is the missing carrier between:

- selected playlist intent
- staged per-item artifacts
- compatibility determination
- concat execution

## Governing Ambiguity

The live ambiguity is now object-level:

- what explicit structure should carry the selected and staged concat set so that compatibility and
  concat execution do not reconstruct state from scattered locals and temporary files

Without this object, the implementation would likely regress into:

- implicit filesystem scans
- unordered staged-file discovery
- executor-local mismatch reconstruction
- weak or misleading rejection evidence

## Required Role

The staging manifest should answer:

- what exact playlist items were selected
- which of them produced staged artifacts
- what ordered staged artifacts now constitute the concat candidate set
- what media facts are already known for those artifacts

It should not answer:

- whether the set is compatible
- whether Telegram delivery will succeed
- whether the output should be split

Those are later transitions.

## Recommended Shape

The first manifest should carry:

- `playlist_url: str`
- `playlist_id: str | None`
- `playlist_title: str | None`
- `selected_indices: list[int]`
- `ordered_indices: list[int]`
- `requested_count: int`
- `staged_items: list[dict]`
- `missing_indices: list[int]`
- `ordering: str`
- `concat_policy: str`

Where each `staged_item` should minimally carry:

- `playlist_index: int`
- `source_url: str | None`
- `artifact_path: str`
- `container: str | None`
- `video_codec: str | None`
- `audio_codec: str | None`
- `width: int | None`
- `height: int | None`
- `fps: float | None`
- `has_audio: bool | None`

## Why `selected_indices` And `ordered_indices` Are Separate

They are related but not identical in role.

- `selected_indices`
  the chosen playlist membership
- `ordered_indices`
  the ordered concat sequence after applying the requested ordering policy

For ordinary ranges they may coincide.
For reverse concat they differ in meaning:

- the selected set is the same
- the concat order is reversed

Keeping both explicit prevents the task from losing the distinction between:

- what was selected
- how it should be composed

## Staged Item Policy

Every selected index should correspond to either:

- one staged item entry

or:

- one missing index in `missing_indices`

The first implementation should not allow:

- silent omission from both lists
- duplicate staged entries for one selected index
- unordered staged entries that force later rediscovery

## Constitutive vs Derived Fields

Constitutive:

- playlist identity
- selected set
- ordered concat sequence
- staged artifact paths
- per-item media facts used for compatibility
- missing indices
- concat policy

Derived:

- human-readable status text
- terminal rejection messages
- concat list file contents

The manifest should remain a structured account of staged state, not a rendered output object.

## Minimal Production Contract

The staging transition should not return "some downloaded files in a folder."
It should return:

- one manifest

The first implementation should treat manifest construction as part of successful staging.
If the manifest cannot be constructed coherently, staging is not complete.

## Compatibility Consequence

The compatibility predicate should read from the manifest only, not re-scan arbitrary directories.

Why:

- manifest order is authoritative
- selected membership is authoritative
- missing indices are authoritative

This keeps compatibility as a determination over one explicit object.

## Concat Execution Consequence

Concat execution should also read from the manifest only, especially:

- `ordered_indices`
- `staged_items[*].artifact_path`

This prevents concat execution from silently changing sequence order or candidate membership.

## RuntimeTask Consequence

The task should retain the manifest, because the manifest is part of task history.

Recommended write:

- `task_context.video_concat_manifest = manifest`

This lets later logs, rejection rendering, and debugging see the same staged account.

## TerminalOutcomeResult Consequence

If staging fails before a coherent manifest exists, terminalization should be:

- `acquisition_or_transformation_failure`

If a coherent manifest exists but contains missing indices under `direct_concat_only`, the next
transition should usually become:

- `determinate_rejection`

The manifest makes that distinction explicit.

## Minimal Invariants

The first implementation should preserve these invariants:

1. `requested_count == len(selected_indices)`
2. every `ordered_index` belongs to `selected_indices`
3. `selected_indices == sorted(selected_indices)` is allowed, but not required for order
4. every selected index appears exactly once across:
   - `staged_items[*].playlist_index`
   - `missing_indices`
5. `len(staged_items) + len(missing_indices) == requested_count`

These invariants are more important than early convenience.

## Tests Implied By This Model

The first implementation tests should verify:

1. normal range creates coherent `selected_indices` and `ordered_indices`
2. reverse range preserves `selected_indices` but flips `ordered_indices`
3. one missing staged item appears in `missing_indices`
4. staged artifact order is not recovered from directory listing order
5. compatibility reads manifest state rather than re-probing selection intent elsewhere

## Why This Is The Next Correct PDA Move

The previous document defined the transition contract.
This document defines the first missing state carrier inside that contract.

That is the correct next move because without an explicit manifest:

- compatibility would not have one authoritative input object
- concat execution would not have one authoritative ordered artifact set
- rejection evidence would drift back into executor locals
