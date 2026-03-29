# Branch Selection Result Model

## Purpose

This document defines the explicit result that should come out of branch selection.

It is the next PDA descent after [`07-branch-selection-model.md`](./07-branch-selection-model.md), because the live ambiguity is no longer only:

- how branch selection works

It is now also:

- what the selector must output so downstream execution does not reconstruct task intent from scattered flags

## Governing Ambiguity

The current system often passes branch-selection meaning downstream through a loose mixture of:

- `quality_key`
- `format_override`
- `cookies_already_checked`
- `cached_video_info`
- `playlist_name`
- `video_count`
- `video_start_with`
- `tags_text`
- callback context
- implicit mode flags such as direct-link mode or send-as-file

That is workable, but it means downstream code must re-infer:

- what branch was actually chosen
- who chose it
- what task scope it applies to
- what execution source is intended

The live ambiguity therefore is:

- what information is constitutive of branch selection, and what is merely downstream execution context

## Definition

A branch-selection result is the minimal explicit object that commits a task to one admissible branch and carries the information needed for downstream execution without requiring branch identity to be reconstructed.

It is not the final artifact.
It is not terminal outcome.
It is the explicit product of `S3 -> S4`.

## What Problem It Solves

Without an explicit result object:

- branch identity is distributed across flags and helper state
- downstream code must infer meaning from execution parameters
- equivalent-looking branches may hide different authorities and semantics
- terminalization later receives insufficiently explicit provenance about why this path exists

An explicit result object would make the chosen branch first-class.

## Required Fields

At minimum, the branch-selection result should contain the following fields.

### 1. `branch_family`

The coarse branch class.

Examples:

- `saved_format_download`
- `audio_download`
- `video_download`
- `subtitles_only`
- `direct_link`
- `cache_reuse`
- `reject`

### 2. `selected_by`

The authority that selected the branch.

Examples:

- `explicit_callback`
- `saved_user_default`
- `cache_policy`
- `router_policy`
- `inadmissibility_pruning`

### 3. `task_scope`

The concrete scope the branch applies to.

Examples:

- single item
- playlist/range
- split-capable path
- multi-item request

This should include the relevant range semantics, not just raw URL.

### 4. `delivery_intent`

What user-visible outcome the branch is trying to satisfy.

Examples:

- Telegram media delivery
- direct-link response
- subtitles-only response
- state mutation
- rejection

### 5. `media_intent`

The media class intended by the branch.

Examples:

- audio
- video
- mixed
- non-media

### 6. `quality_intent`

The branch's quality/selection meaning.

Examples:

- `best`
- `mp3`
- `480p`
- explicit format ID
- saved default
- cache-equivalent quality identity

This should represent semantic intent, not only the final engine-specific format string.

### 7. `execution_source`

How the branch expects to be satisfied.

Examples:

- `fresh_acquisition`
- `cache_reuse`
- `response_only`
- `reject`

### 8. `access_requirements`

The access conditions known or assumed at selection time.

Examples:

- cookies required / cookies preferred / no-cookie admissible
- proxy admissible or required by policy
- metadata already validated vs still unresolved

This field should not collapse selection into execution, but it should carry the downstream constraints that branch selection already knows.

### 9. `downstream_constraints`

Execution-relevant constraints that do not themselves define branch identity but do constrain execution.

Examples:

- selected subtitle language
- container preference
- codec preference
- send-as-file policy where relevant

### 10. `provenance`

Minimal provenance needed for terminal semantics and debugging.

Examples:

- original message/callback linkage
- whether the branch came from explicit callback
- whether cached metadata was used
- whether branch selection reused pre-existing task context

## Fields That Should Not Substitute For The Object

The following are useful execution parameters, but they are not sufficient substitutes for branch identity.

- raw `format_override`
- raw `quality_key`
- `proc_msg`
- raw `cached_video_info`
- `cookies_already_checked`
- temporary download directory path

These are parts of execution context, not the branch-selection result itself.

## Derived vs Constitutive Fields

An important PDA distinction here is:

- some fields are **constitutive** of branch meaning
- others are **derived** for execution convenience

### Constitutive

- `branch_family`
- `selected_by`
- `task_scope`
- `delivery_intent`
- `media_intent`
- `quality_intent`
- `execution_source`

### Derived

- exact yt-dlp format string
- exact ffmpeg plan
- exact thumbnail source
- exact temp paths
- exact processing message ID

If derived execution fields are allowed to stand in for constitutive fields, branch meaning becomes opaque again.

## Minimal Example Shapes

### Example 1: Callback-Selected MP3

```yaml
branch_family: audio_download
selected_by: explicit_callback
task_scope: single_item
delivery_intent: telegram_media
media_intent: audio
quality_intent: mp3
execution_source: fresh_acquisition
access_requirements:
  cookies: preferred
  metadata_validated: true
downstream_constraints:
  subtitle_mode: none
provenance:
  origin: callback
```

### Example 2: Saved-Format Direct Download

```yaml
branch_family: saved_format_download
selected_by: saved_user_default
task_scope: playlist_range
delivery_intent: telegram_media
media_intent: video
quality_intent: saved_default
execution_source: fresh_acquisition
access_requirements:
  cookies: unresolved
downstream_constraints:
  format_override: persisted
provenance:
  origin: direct_message
```

### Example 3: Direct-Link Branch

```yaml
branch_family: direct_link
selected_by: explicit_callback
task_scope: single_item
delivery_intent: response_only
media_intent: mixed
quality_intent: best
execution_source: response_only
access_requirements:
  metadata_validated: true
provenance:
  origin: callback
```

## Current Code Smell

The current code smell is that branch-selection result is implicit.

Instead of one object, the system often passes:

- a format string
- a quality key
- a few booleans
- message/callback context
- and then expects downstream code to know what that combination *means*

This is a classic sign that a decision surface exists conceptually but has not yet been made explicit in implementation.

## Interleavings This Object Would Reduce

An explicit branch-selection result would reduce interleaving between:

- branch identity and execution details
- user authority and saved default inference
- task scope and raw format choice
- cache reuse semantics and fresh acquisition semantics
- branch provenance and terminal-outcome interpretation

## Relationship To Terminal Semantics

Terminal semantics should not need to infer branch meaning from raw execution flags.

If terminalization knew:

- what branch family was selected
- who selected it
- whether it was intended as media delivery, direct link, or cache reuse

then outcome assignment would become cleaner.

So this object is upstream of, and complementary to, the terminal-outcome model in [`08-terminal-semantics-model.md`](./08-terminal-semantics-model.md).

## What This Suggests Next

The next natural move after this formulation would be one of:

- define a corresponding explicit terminal-outcome result object
- sketch a task-state machine using both branch-selection result and terminal-outcome result
- audit existing orchestrator call signatures to identify which current parameters are constitutive vs derived

## Recomposition

Recomposed at this layer:

the branch selector should return a branch-selection result object, not merely execution flags.

That is the smallest conceptual move that would let downstream code stop guessing what branch was actually chosen.
