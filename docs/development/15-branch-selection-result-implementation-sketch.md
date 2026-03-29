# Branch Selection Result Implementation Sketch

## Purpose

This document sketches the smallest viable implementation move for introducing a real `BranchSelectionResult`.

It follows from:

- [`14-first-implementation-seam.md`](./14-first-implementation-seam.md)
- [`09-branch-selection-result-model.md`](./09-branch-selection-result-model.md)

The goal is not to define the final architecture.
It is to define the smallest patch that:

- makes branch selection explicit
- preserves current behavior as much as possible
- limits blast radius
- creates a stable seam for later work

## Non-Goal

This first move is **not**:

- a full `Task` object rollout
- a full state-machine implementation
- a rewrite of `always_ask_menu.py`
- a full cleanup of terminal semantics

It is a narrow introduction of one explicit result object at the `S3 -> S4` boundary.

## Minimal Implementation Target

Introduce a lightweight `BranchSelectionResult` structure and use it at the first branch-selection points.

The smallest practical first version can be:

- a dataclass
- a typed dict
- or a small immutable plain object

A dataclass is the cleanest likely first move.

## Minimal First Version Fields

The first implementation version does not need every field from the conceptual model.
It should include only the fields needed to stop downstream guesswork at the current seam.

Recommended first fields:

- `branch_family`
- `selected_by`
- `task_scope`
- `delivery_intent`
- `media_intent`
- `quality_intent`
- `execution_source`
- `format_override`
- `quality_key`
- `provenance`

Why include `format_override` and `quality_key` here even though they are not constitutive in the full model:

- because the current downstream code already depends on them
- so carrying them inside the result object lets the first patch preserve behavior while still making branch identity explicit

## Recommended File Placement

The cleanest first home is probably:

- `DOWN_AND_UP/branch_selection_result.py`

Why:

- the seam is currently centered around `always_ask_menu.py` and `video_extractor.py`
- it avoids pretending the object is only a helper concern
- it keeps the object near the orchestration boundary rather than buried in generic utilities

## Minimal Dataclass Shape

Conceptually:

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class BranchSelectionResult:
    branch_family: str
    selected_by: str
    task_scope: str
    delivery_intent: str
    media_intent: str
    quality_intent: str
    execution_source: str
    format_override: str | None = None
    quality_key: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
```

This is intentionally small.

## First Insertion Points

The first insertion points should be the narrowest true `S3 -> S4` decisions:

### 1. Saved-Format Direct Path

In:

- [`URL_PARSERS/video_extractor.py`](./../../URL_PARSERS/video_extractor.py)

When the code decides:

- not `ALWAYS_ASK`
- use saved format directly

that decision should produce a `BranchSelectionResult` before calling `down_and_up()`.

### 2. Callback-Selected Audio Path

In:

- [`DOWN_AND_UP/always_ask_menu.py:askq_callback_logic()`](./../../DOWN_AND_UP/always_ask_menu.py)

When `data == "mp3"`, create a `BranchSelectionResult` before calling `down_and_audio()`.

### 3. Callback-Selected Video Path

In:

- [`DOWN_AND_UP/always_ask_menu.py:askq_callback_logic()`](./../../DOWN_AND_UP/always_ask_menu.py)

When `data == "best"` or a concrete quality rung is selected, create a `BranchSelectionResult` before calling `down_and_up_with_format()`.

### 4. Direct-Link Path

Also in:

- [`DOWN_AND_UP/always_ask_menu.py:askq_callback_logic()`](./../../DOWN_AND_UP/always_ask_menu.py)

When link mode is active, create a `BranchSelectionResult` for the direct-link branch before returning the link response.

## First Integration Strategy

The first integration should be additive, not invasive.

Recommended pattern:

1. create the result object
2. log it or attach it to local flow
3. pass it alongside existing parameters
4. keep existing downstream call signatures mostly intact initially

That means the first move is:

- explicit branch-selection result exists
- but downstream code is only partially migrated to depend on it

This is acceptable for the first seam.

## Minimal Signature Change Strategy

Avoid broad refactors immediately.

Instead:

- add an optional `branch_result=None` parameter to:
  - `down_and_up()`
  - `down_and_audio()`
  - `down_and_up_with_format()`

At first, those functions may do nothing except:

- accept it
- log it
- preserve it for future use

That keeps the first patch behavior-safe.

## What The First Patch Should Achieve

The first patch should make these true:

- branch selection is represented explicitly in code
- branch provenance is no longer purely implicit
- downstream execution can begin consuming `branch_result` incrementally
- the codebase gains a real seam for later terminalization and task-object work

If those are true, the patch succeeded, even if most downstream logic still uses legacy parameters.

## What The First Patch Should Not Try To Solve

Do not try to solve all of these in the same patch:

- cache-reuse equivalence correctness
- terminal-outcome modeling
- full callback/task linking
- all `always_ask_menu.py` cleanup
- all argument normalization

Those are later moves.

## Suggested Order Inside The Patch

1. add `BranchSelectionResult` definition
2. add small factory helpers if useful
3. create result in saved-format direct path
4. create result in callback `mp3` path
5. create result in callback video-quality path
6. create result in direct-link path
7. thread optional `branch_result` through immediate downstream calls
8. add high-signal logging using branch family and selected-by

## Example First Factories

If factories are used, keep them minimal.

Examples:

- `make_saved_format_branch_result(...)`
- `make_callback_audio_branch_result(...)`
- `make_callback_video_branch_result(...)`
- `make_direct_link_branch_result(...)`

This is better than one over-generalized builder in the first patch.

## Why This Is Safe Enough

This first patch is relatively safe because:

- it does not remove the old parameters yet
- it does not force all downstream code to understand the new object immediately
- it introduces explicitness at the point of choice, where meaning is freshest

So the change is semantically strong but structurally incremental.

## Success Criteria

The first implementation seam is successful if:

- the code creates an explicit `BranchSelectionResult` at real branch-selection points
- the object survives into downstream orchestration entrypoints
- logs/debugging can show branch family and selecting authority directly
- no user-visible behavior regresses

## What This Suggests Next

After this first patch, the next best move would likely be:

- begin consuming `branch_result` inside terminalization-related paths

That would naturally lead toward:

- `TerminalOutcomeResult`
- and later the larger `Task` container

## Recomposition

Recomposed:

the smallest viable first implementation is to create a real `BranchSelectionResult` object at branch-selection points and thread it through orchestration without forcing an immediate full refactor.
