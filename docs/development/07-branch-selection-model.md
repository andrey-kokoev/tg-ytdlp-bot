# Branch Selection Model

## Purpose

This document isolates the `S3 -> S4` transition from [`05-task-model.md`](./05-task-model.md):

- **Metadata-Resolved Task** -> **Branch-Selected Task**

This is the highest-leverage live ambiguity in the current system because it is where:

- explicit user choice
- saved defaults
- cache reuse
- direct-link mode
- delivery intent
- access feasibility assumptions

are still too easily flattened together.

The goal is to define what branch selection actually is, what may legitimately influence it, and what should remain downstream rather than contaminating selection.

## Governing Ambiguity

The live ambiguity at this layer is not "how do we download media."
It is:

- what exactly is being selected once metadata is known
- which authorities are allowed to determine that selection
- which inputs are part of branch identity versus merely downstream execution details

If this remains concealed, the system feels arbitrary even when later download logic works.

## Branch Selection Definition

Branch selection is the transition in which the system chooses a concrete admissible continuation class for a task after enough context and metadata are available.

At this layer, the output is not yet a final artifact.
The output is a branch commitment such as:

- immediate direct download with a saved format
- user-selected audio download
- user-selected video download at a particular quality class
- subtitles-only path
- direct-link path
- cached artifact reuse path
- determinate rejection due to inadmissibility

So branch selection chooses the *kind of execution path*, not just a format string.

## Branch Identity

A branch should be understood as the tuple:

- delivery intent
  media delivery, subtitles-only, direct link, state mutation, or rejection
- media class
  audio, video, mixed, or non-media response
- quality/selection intent
  best, explicit quality rung, explicit format, cached equivalent, or saved default
- task scope
  single item, playlist/range, split path, or multi-item path
- execution mode
  fresh acquisition, cache reuse, or other admissible execution source

This means that two branches are not equivalent merely because they may ultimately produce similar user-visible output.

## Admissible Branches

For media tasks in the current system, the main admissible branches appear to be:

### B1. Saved-Format Direct Download

- entered when the user is not in Always Ask mode
- selected before menu display
- usually enters `down_and_up()` directly from [`video_url_extractor()`](./../../URL_PARSERS/video_extractor.py)

### B2. Callback-Selected Audio Download

- explicit user choice, typically `mp3`
- enters `down_and_audio()`

### B3. Callback-Selected Video Download

- explicit user choice, e.g. `best`, `480p`, or equivalent
- enters `down_and_up_with_format()` then `down_and_up()`

### B4. Callback-Selected Subtitles-Only Path

- explicit user choice
- does not intend normal media delivery

### B5. Direct-Link Path

- explicit mode branch
- returns stream URLs rather than Telegram-uploaded artifacts

### B6. Cache-Reuse Path

- selected when cached output is considered semantically valid for the current request
- user-visible result may resemble fresh delivery, but branch identity is distinct

### B7. Determinate Rejection

- selected when no admissible branch remains

## Authorities Allowed To Influence Branch Selection

The following authorities are legitimate at this layer.

### User Authority

Allowed influence:

- explicit callback choice
- explicit direct-link mode choice
- explicit current-task selection among shown options

### Persisted User Policy

Allowed influence:

- saved format when no more specific current-task choice exists
- saved settings that define admissible branch families, such as Always Ask or send-as-file where relevant

### Task Context

Allowed influence:

- original message scope
- playlist/range semantics
- callback-parent linkage
- already-resolved metadata

### Cache/Reuse Policy

Allowed influence:

- whether a semantically equivalent result is already available for reuse

### Source-Platform Feasibility

Allowed influence:

- only to the extent that it rules a branch inadmissible

Source/platform feasibility may prune branches, but it should not silently redefine branch identity.

## Inputs That Should Not Quietly Select Branches

These inputs may matter later, but should not silently decide branch identity without being modeled as such.

- thumbnail-generation feasibility
- exact ffmpeg command shape
- logging destination
- temporary download directory structure
- message-wrapper mechanics
- incidental helper-service implementation details

These are execution details, not branch selectors.

## Precedence Rules For Branch Selection

### 1. Explicit Current-Task User Choice

If the user explicitly chooses a branch through callback/UI for the current task, that choice has the highest precedence.

Examples:

- `mp3`
- `480p`
- subtitles-only
- direct-link branch

### 2. Task-Specific Context Over Ambient Defaults

If task-local context determines a narrower admissible set, it overrides broad saved preference.

Examples:

- callback-selected branch overrides saved format
- current playlist/range scope overrides assumptions of single-item handling

### 3. Saved User Default Over Generic Fallback

If no explicit task-level branch is chosen, saved user policy may determine the branch.

Examples:

- saved format enabling direct download path
- Always Ask mode forcing menu-based branch selection rather than direct acquisition

### 4. Cache Reuse Over Fresh Acquisition, Conditionally

Cache reuse may take precedence over fresh acquisition only if semantic equivalence for the current task is established.

This means:

- same task intent
- same effective branch family
- same relevant quality/delivery semantics

Cache should not win merely because it exists.

### 5. Inadmissibility Prunes, It Does Not Re-Specify

If source-platform or access constraints invalidate a branch, they should prune that branch.
They should not silently redefine the user's chosen branch into a different one without an explicit modeled fallback.

## Branch Equivalence

The current system risks treating unlike branches as equivalent.
The following distinctions should remain explicit:

- fresh acquisition vs cache reuse
- direct link vs Telegram-uploaded artifact
- audio branch vs video branch
- subtitles-only vs media-delivery branch
- saved-default branch vs explicit current-task choice

Equivalence should be claimed only when the system has decided what properties define semantic sameness for the task.

## Branch Selection Outputs

A clean branch-selection output should minimally contain:

- selected branch family
- authority that selected it
- relevant task scope
- quality or format intent
- execution source
  fresh acquisition, cache reuse, or rejection
- downstream constraints that remain to be satisfied

The current system often collapses this into format strings plus scattered flags.
That is workable, but under-modeled.

## Current Code Surfaces

The branch-selection surface is currently split mainly across:

- [`URL_PARSERS/video_extractor.py:video_url_extractor()`](./../../URL_PARSERS/video_extractor.py)
- [`DOWN_AND_UP/always_ask_menu.py:ask_quality_menu()`](./../../DOWN_AND_UP/always_ask_menu.py)
- [`DOWN_AND_UP/always_ask_menu.py:askq_callback_logic()`](./../../DOWN_AND_UP/always_ask_menu.py)
- [`DOWN_AND_UP/always_ask_menu.py:down_and_up_with_format()`](./../../DOWN_AND_UP/always_ask_menu.py)

This split is the current implementation source of branch-selection incoherence.

## Main Interleavings

The strongest interleavings at this layer are:

- explicit callback choice with saved defaults
- cache reuse with quality identity
- direct-link mode with media-delivery mode
- selected branch family with downstream access feasibility

These are not bugs by themselves.
They are the places where a branch-selection object or centralized selector would most reduce concealed arbitrariness.

## What This Suggests Next

If the system is ever refactored, branch selection is a strong candidate for first centralization.

The minimal architectural move would be:

- produce one explicit branch-selection result object before orchestration starts

That object could then be consumed by:

- `down_and_up()`
- `down_and_audio()`
- direct-link delivery
- cache reuse logic
- terminalization logic

## Recomposition

Recomposed at this layer:

branch selection is the system's main decision surface for media tasks.

If it remains implicit, later download and delivery behavior will continue to feel only locally justified.
If it becomes explicit, much of the present incoherence becomes tractable.

## Related Documents

- [`Branch Selection Result Model`](./09-branch-selection-result-model.md): explicit output object for branch selection
- [`Terminal Semantics Model`](./08-terminal-semantics-model.md): explicit formulation of task outcome meaning
