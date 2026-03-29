# Task Object Model

## Purpose

This document defines the explicit `Task` object implied by the preceding PDA work.

It follows naturally from:

- [`11-task-state-machine-sketch.md`](./11-task-state-machine-sketch.md)
- [`09-branch-selection-result-model.md`](./09-branch-selection-result-model.md)
- [`10-terminal-outcome-result-model.md`](./10-terminal-outcome-result-model.md)

The goal is to make explicit the primary runtime object that the current system already behaves as if it had.

## Governing Ambiguity

At this layer, the live ambiguity is:

- what object should carry task identity, state, branch commitment, execution evidence, and terminal meaning across the machine

Right now that role is spread across:

- Telegram message objects
- callback queries
- user ID
- files in `users/<user_id>/...`
- cached metadata
- orchestration variables
- flags and counters in large functions

The system behaves as if a `Task` object exists, but does not yet expose it explicitly.

## Definition

A `Task` object is the primary runtime representation of a bounded execution attempt to resolve a user-originated intent into a terminal outcome.

It is the carrier of:

- task identity
- current machine state
- contextual state needed for continuation
- branch-selection result
- execution evidence
- terminal-outcome result

The `Task` object is not merely a wrapper around a Telegram message.
It is the runtime object that persists conceptual continuity across multiple updates, multiple local reads/writes, and multiple execution stages.

## Why This Object Is Needed

Without an explicit `Task` object:

- task identity remains composite and implicit
- branch-selection result has no natural home
- terminal-outcome result has no natural home
- transition boundaries keep leaking into large orchestration functions
- message objects keep being overloaded as pseudo-task containers

An explicit `Task` object would not solve all problems, but it would give the system one coherent primary unit.

## Core Responsibilities

The `Task` object should be responsible for carrying:

- who the task belongs to
- what the task is trying to do
- what state it is currently in
- what branch was selected and by whom
- what evidence has accumulated during execution
- how the task ultimately terminated

It should not itself perform all work.
It should be the authoritative container passed between transition owners.

## Required Fields

At minimum, a `Task` object should contain the following field groups.

### 1. Identity

Fields:

- `task_id`
- `user_id`
- `task_class`
- `initiating_authority`
- `origin_update_ref`

Purpose:

- provide stable task identity that is not reducible to a single message object

### 2. Intent

Fields:

- `intent_kind`
- `original_input`
- `normalized_scope`
- `delivery_intent`

Purpose:

- preserve what the task is fundamentally trying to achieve

### 3. Machine State

Fields:

- `current_state`
- `state_history`

Purpose:

- make the current task-machine location explicit
- preserve transition provenance for reasoning/debugging

### 4. Context State

Fields:

- `user_state_snapshot`
- `callback_context`
- `metadata_context`
- `policy_context`

Purpose:

- hold the context needed for transitions without forcing every module to rebuild it from scratch

### 5. Branch Selection

Fields:

- `branch_selection_result`

Purpose:

- carry the explicit output of `S3 -> S4`

This field should use the model described in [`09-branch-selection-result-model.md`](./09-branch-selection-result-model.md).

### 6. Execution Evidence

Fields:

- `acquisition_attempts`
- `artifact_refs`
- `delivery_attempts`
- `cache_refs`
- `error_evidence`

Purpose:

- store stage-relevant facts gathered during execution
- distinguish constitutive state from side-effect evidence

### 7. Terminal Outcome

Fields:

- `terminal_outcome_result`

Purpose:

- carry the explicit output of `S7 -> S8`

This field should use the model described in [`10-terminal-outcome-result-model.md`](./10-terminal-outcome-result-model.md).

## Minimal Structural Shape

Conceptually, the object can be thought of like this:

```yaml
task_id: ...
user_id: ...
task_class: ...
initiating_authority: ...
origin_update_ref: ...

intent:
  intent_kind: ...
  original_input: ...
  normalized_scope: ...
  delivery_intent: ...

machine:
  current_state: ...
  state_history: [...]

context:
  user_state_snapshot: ...
  callback_context: ...
  metadata_context: ...
  policy_context: ...

branch_selection_result: ...

execution_evidence:
  acquisition_attempts: [...]
  artifact_refs: [...]
  delivery_attempts: [...]
  cache_refs: [...]
  error_evidence: [...]

terminal_outcome_result: ...
```

This is a conceptual shape, not a final implementation schema.

## Constitutive vs Attached Data

An important PDA distinction applies here too.

### Constitutive Task Data

- identity
- intent
- current state
- branch-selection result
- terminal-outcome result

### Attached Execution Evidence

- raw yt-dlp info blobs
- raw ffmpeg outputs
- temporary progress message IDs
- exact cache payloads
- raw exception traces

Attached evidence may be useful, but should not replace constitutive task meaning.

## Relationship To Telegram Objects

A Telegram message or callback should be treated as:

- an event reference
- part of task provenance
- possibly part of callback context

It should not be treated as the task itself.

This is one of the main conceptual corrections the `Task` object enables.

## Relationship To Filesystem State

Filesystem state remains authoritative for many user and artifact facts.

But the `Task` object should hold:

- the task-relevant snapshot or references
- not the claim that filesystem entries are the task itself

In other words:

- filesystem state informs the task
- it should not *become* the only de facto task container

## Relationship To Branch Selection And Terminal Outcome

The `Task` object is the natural owner of both:

- `branch_selection_result`
- `terminal_outcome_result`

This matters because it connects:

- what path the task committed to
- with what outcome that path ultimately achieved

Without a primary object owning both, provenance remains fragmented.

## Transition Contract Sketch

If the task machine were made more explicit, transitions would look conceptually like:

- `route(task) -> task`
- `resolve_context(task) -> task`
- `resolve_metadata(task) -> task`
- `select_branch(task) -> task` with `branch_selection_result` filled
- `execute_branch(task) -> task`
- `terminalize(task) -> task` with `terminal_outcome_result` filled

This does not require immutability or a particular programming style.
It only requires that the task object remain the conceptual carrier.

## What This Object Should Prevent

An explicit `Task` object should reduce:

- handler-local reinference of task meaning
- treating counters and flags as terminal semantics
- treating format strings as branch identity
- treating a single message as the full execution unit
- losing provenance between callback choice and final outcome

## Current Code Approximation

The current code approximates the `Task` object through a combination of:

- message/callback objects
- local files
- in-memory caches
- orchestration locals
- counters
- helper state

That approximation works, but it is why the system feels more interleaved than it should.

## What This Suggests Next

The next natural move after this formulation is one of:

- define explicit transition contracts for a conceptual `Task`
- choose the smallest implementation surface where a real `Task` object could first appear
- audit which current parameters in `down_and_up()`, `down_and_audio()`, and `always_ask_menu.py` would become task fields

The highest-leverage first candidate is probably:

- branch selection returning a real `BranchSelectionResult` attached to a task-like container

before attempting a full task-object rollout.

## Related Documents

- [`Transition Contracts`](./13-transition-contracts.md): explicit read/write/decision boundaries for the task-state-machine transitions

## Recomposition

Recomposed at this layer:

the system's missing primary runtime object is the `Task`.

Once that is explicit, the architecture stops needing to pretend that messages, files, and flags are independently sufficient carriers of execution meaning.
