# Terminal Outcome Result Model

## Purpose

This document defines the explicit result that should come out of terminalization.

It is the natural pair to [`09-branch-selection-result-model.md`](./09-branch-selection-result-model.md).

If branch selection should yield a first-class result object, terminalization should as well.

The goal is to stop encoding terminal meaning indirectly through:

- upload counters
- ad hoc success messages
- partial/failure text variants
- cache writes
- cleanup branches
- logging side effects

## Governing Ambiguity

The current system frequently knows more than it explicitly states.

For example, it may know that:

- a local artifact exists
- some uploads succeeded
- Telegram did not accept all intended outputs
- cache was written
- cleanup succeeded or failed

But downstream readers still have to infer terminal meaning from those facts.

So the live ambiguity is:

- what information is constitutive of terminal outcome, and what is merely post-outcome side effect or supporting evidence

## Definition

A terminal-outcome result is the minimal explicit object that assigns final outcome meaning to a task and exposes the facts needed for reporting, retry interpretation, cache policy, and cleanup policy without requiring those meanings to be reconstructed from scattered variables.

It is the explicit product of `S7 -> S8`.

## What Problem It Solves

Without an explicit terminal-outcome result:

- "success" may mean local artifact success, Telegram delivery success, or full-scope completion
- "failure" may hide partial success
- cache writes and cleanup may be mistaken for part of outcome meaning
- later code must infer whether the task ended in rejection, response-only success, artifact success, or delivery failure

An explicit result object makes terminal meaning first-class.

## Required Fields

At minimum, the terminal-outcome result should contain the following fields.

### 1. `terminal_class`

The coarse outcome class.

Examples:

- `determinate_rejection`
- `state_mutation_success`
- `response_only_success`
- `artifact_delivery_success`
- `cache_reuse_success`
- `partial_success`
- `artifact_ready_delivery_failure`
- `acquisition_or_transformation_failure`

### 2. `task_class`

The class of task being terminated.

Examples:

- immediate command
- upload-state mutation
- media-acquisition
- callback continuation
- cache-reuse path

This matters because not all task classes share the same success condition.

### 3. `branch_family`

The selected branch family that led to this terminal state.

Examples:

- `audio_download`
- `video_download`
- `direct_link`
- `subtitles_only`
- `cache_reuse`
- `reject`

This should usually come from the branch-selection result rather than be recomputed.

### 4. `scope_requested`

The intended output scope for the task.

Examples:

- one item
- playlist/range of N items
- split output with M parts

### 5. `scope_satisfied`

How much of the requested scope was actually satisfied.

Examples:

- `0/1`
- `1/1`
- `3/5`
- `all`
- `none`

This is one of the main inputs to partial-success semantics.

### 6. `delivery_status`

The actual Telegram-delivery result class.

Examples:

- `not_applicable`
- `all_delivered`
- `partially_delivered`
- `delivery_failed`

### 7. `artifact_status`

Whether the system reached a valid deliverable or equivalent reusable artifact state.

Examples:

- `not_required`
- `no_valid_artifact`
- `local_artifact_ready`
- `cache_equivalent_ready`

### 8. `selected_by`

The authority that selected the branch that is now being terminated.

This should be carried through from branch selection rather than rediscovered.

### 9. `failure_locus`

If the terminal outcome is not full success, the system should name the stage-localized failure locus.

Examples:

- `routing`
- `metadata_extraction`
- `acquisition`
- `transformation`
- `delivery`
- `mixed`
- `none`

### 10. `user_visible_message_kind`

The kind of final user-facing reporting appropriate for this outcome.

Examples:

- rejection message
- success message
- partial-success message
- delivery-failure message
- no final user message

This is not the final string itself. It is the reporting class.

### 11. `cache_effect`

What cache semantics follow from the outcome.

Examples:

- `do_not_cache`
- `cache_reuse_confirmed`
- `cache_new_result`
- `cache_partial_result`
- `cache_unknown`

### 12. `cleanup_policy`

What cleanup meaning follows from the outcome.

Examples:

- `normal_cleanup`
- `preserve_for_retry`
- `preserve_for_debug`
- `no_cleanup_needed`

Cleanup should be driven by outcome meaning, not confused with it.

### 13. `provenance`

Minimal provenance needed to understand how this outcome arose.

Examples:

- task id / user id linkage
- branch family
- whether cache reuse or fresh acquisition was attempted
- whether partial delivery occurred

## Fields That Should Not Substitute For The Object

The following are useful facts, but are not sufficient substitutes for terminal outcome meaning.

- `successful_uploads`
- `error_message_sent`
- whether `safe_edit_message_text()` succeeded
- whether cleanup succeeded
- whether logs were sent
- whether thumbnail generation succeeded

These are inputs, evidence, or side effects.
They are not the terminal-outcome result itself.

## Constitutive vs Derived Fields

### Constitutive

- `terminal_class`
- `task_class`
- `branch_family`
- `scope_requested`
- `scope_satisfied`
- `delivery_status`
- `artifact_status`
- `failure_locus`

### Derived / Side-Effect Oriented

- final human-readable message text
- exact cache write payload
- exact cleanup commands
- exact logging text
- exact progress-message edits

If derived side-effect fields stand in for constitutive fields, terminal meaning becomes opaque again.

## Minimal Example Shapes

### Example 1: Full Audio Success

```yaml
terminal_class: artifact_delivery_success
task_class: media_acquisition
branch_family: audio_download
scope_requested: 1
scope_satisfied: 1
delivery_status: all_delivered
artifact_status: local_artifact_ready
selected_by: explicit_callback
failure_locus: none
user_visible_message_kind: success_message
cache_effect: cache_new_result
cleanup_policy: normal_cleanup
```

### Example 2: Partial Playlist Success

```yaml
terminal_class: partial_success
task_class: media_acquisition
branch_family: video_download
scope_requested: 5
scope_satisfied: 3
delivery_status: partially_delivered
artifact_status: local_artifact_ready
selected_by: saved_user_default
failure_locus: mixed
user_visible_message_kind: partial_success_message
cache_effect: cache_partial_result
cleanup_policy: preserve_for_retry
```

### Example 3: Local Artifact Ready But Delivery Failed

```yaml
terminal_class: artifact_ready_delivery_failure
task_class: media_acquisition
branch_family: video_download
scope_requested: 1
scope_satisfied: 0
delivery_status: delivery_failed
artifact_status: local_artifact_ready
selected_by: explicit_callback
failure_locus: delivery
user_visible_message_kind: delivery_failure_message
cache_effect: cache_unknown
cleanup_policy: preserve_for_debug
```

### Example 4: Cookie Upload Success

```yaml
terminal_class: state_mutation_success
task_class: upload_state_mutation
branch_family: state_mutation
scope_requested: 1
scope_satisfied: 1
delivery_status: all_delivered
artifact_status: not_required
selected_by: router_policy
failure_locus: none
user_visible_message_kind: success_message
cache_effect: do_not_cache
cleanup_policy: no_cleanup_needed
```

## Relationship To Current Code

The current code often implies terminal outcome through combinations like:

- `successful_uploads == len(indices_to_download)`
- partial-success message selection
- success message edits
- cache writes after send success
- cleanup on success vs error

Those are all useful, but they are not a single terminal-outcome object.

So the code smell here is analogous to the branch-selection smell:

- terminal meaning exists conceptually
- but it is represented indirectly through counters, booleans, and side-effect branches

## Interleavings This Object Would Reduce

An explicit terminal-outcome result would reduce interleaving between:

- outcome meaning and progress-message editing
- outcome meaning and cache writes
- outcome meaning and cleanup policy
- local artifact success and user-facing delivery success
- partial-success semantics and generic failure semantics

## Relationship To Branch Selection Result

The two objects are complementary.

- branch-selection result explains **what path the task committed to**
- terminal-outcome result explains **what outcome meaning that path achieved**

Together they would make the middle of the task much easier to reason about.

## What This Suggests Next

The next natural move after this is:

- sketch a task-state machine that takes a branch-selection result and yields a terminal-outcome result

At that point, the main hidden architectural objects would all be explicit enough to support refactoring decisions.

## Recomposition

Recomposed at this layer:

terminalization should return a terminal-outcome result object, not merely success counters plus side effects.

That is the smallest conceptual move that would make outcome meaning explicit and stable across task classes.

## Related Documents

- [`Task State Machine Sketch`](./11-task-state-machine-sketch.md): closed execution skeleton connecting branch selection and terminal outcome
