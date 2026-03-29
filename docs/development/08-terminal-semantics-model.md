# Terminal Semantics Model

## Purpose

This document isolates the `S7 -> S8` layer from [`05-task-model.md`](./05-task-model.md):

- **Delivery Attempt** -> **Terminal Outcome**

The goal is to make explicit what the current system means by:

- success
- partial success
- failure
- rejection
- locally successful but externally unsuccessful completion

This is the next natural PDA descent after branch selection because the remaining live ambiguity is not mainly "which branch did we choose," but:

- what exactly counts as completion once acquisition, artifact creation, and Telegram delivery can diverge

## Governing Ambiguity

The live ambiguity at this layer is:

- what event actually closes a task
- what conditions are necessary for success
- when partial completion is a distinct terminal state rather than a weakened failure label
- which downstream side effects belong to terminal semantics and which are merely cleanup or logging

If this remains concealed, the system will continue to report outcomes inconsistently even when branch selection is clear.

## Terminalization Definition

Terminalization is the transition in which the system assigns final outcome meaning to a task.

That meaning is not identical to:

- successful extraction
- successful download
- successful post-processing
- successful local artifact creation

Those are upstream achievements.
Terminal semantics begin when the system decides whether the task, as a user-facing execution attempt, has ended in a determinate outcome class.

## What Terminal Semantics Must Distinguish

The system must distinguish at least the following axes:

- did routing admit the task at all
- did the system obtain a valid deliverable or equivalent cached result
- did Telegram actually accept the intended outbound result
- were all requested outputs delivered or only some
- was the task satisfied through fresh acquisition or cached reuse

If these distinctions collapse, outcome meaning becomes muddy.

## Terminal Outcome Classes

The following terminal outcome classes are the minimal explicit set suggested by the current system.

### T1. Determinate Rejection

The task is closed as inadmissible before meaningful acquisition or delivery.

Examples:

- malformed input
- policy-based rejection
- unsupported or blocked path
- explicit early constraint violation

### T2. State-Mutation Success

The task was not a media-delivery task and successfully completed its intended local/user-state mutation.

Examples:

- cookie upload saved
- settings successfully changed
- keyboard mode updated

### T3. Response-Only Success

The task succeeded by returning a text/menu/help/direct-link response rather than by delivering media artifacts.

Examples:

- help/settings response
- direct-link branch success
- successful menu creation

### T4. Artifact Delivery Success

The system successfully delivered all requested artifacts for the task through Telegram.

This is the main success class for normal media delivery.

### T5. Cache-Reuse Success

The system successfully satisfied the task through semantically valid reuse rather than fresh acquisition.

This may be user-visible as ordinary success, but it is terminally distinct in system terms.

### T6. Partial Success

The system delivered some but not all intended outputs.

Examples:

- playlist task where only part of the requested range reached Telegram
- split output where only some parts were sent
- mixed cached/fresh path where not all required outputs finalized successfully

### T7. Artifact-Ready Delivery Failure

The system created or located a valid deliverable, but Telegram delivery did not fully succeed.

This is not acquisition failure.
It is delivery failure after upstream success.

### T8. Acquisition/Transformation Failure

The system never reached a valid deliverable or equivalent cached outcome.

Examples:

- extractor failure
- download failure
- post-processing failure
- invalid fallback path

## Terminal Authority

At this layer, the main authorities are:

- local task counters and task scope
- existence or absence of valid deliverables
- Telegram upload acceptance
- current task policy for interpreting partial delivery

Source-platform authority matters less here than earlier.
By terminalization time, the key question is no longer "can we fetch" but "what outcome meaning has been achieved."

## Success Is Not A Single Event

The current system implicitly uses several upstream success notions that should not be confused.

### Upstream Successes

- metadata extraction succeeded
- download succeeded
- post-processing succeeded
- local artifact exists
- cache lookup succeeded

### Terminal Successes

- intended response delivered
- intended artifact(s) delivered
- semantically valid cache reuse satisfied the task

The system should not collapse upstream success into task success.

## Failure Is Also Layered

Similarly, failure is layered.

### Routing Failure

- no admissible task continuation

### Acquisition Failure

- media or metadata could not be obtained

### Transformation Failure

- local post-processing failed after some upstream success

### Delivery Failure

- valid deliverable existed but Telegram delivery failed or was incomplete

### Mixed Outcome Failure

- some outputs succeeded, some failed

This layered structure is why generic "download failed" messaging is often semantically inadequate.

## Partial Success

Partial success should remain a first-class terminal class.

It should not be flattened into either:

- success
- failure

because it materially changes:

- retry meaning
- cache meaning
- user expectation
- logging interpretation
- whether the task should be considered closed or resumable

The current code already hints at this through `successful_uploads`, playlist counts, split counts, and "Partially completed" messages.
The semantics should therefore be modeled explicitly rather than treated as ad hoc reporting.

## Preconditions For Artifact Delivery Success

For a media-delivery task to terminate in full success, all of the following should hold:

- a valid deliverable or valid reusable cached result exists
- task scope has been satisfied
- Telegram accepted the intended outbound media/result
- the system has no remaining undelivered required outputs for the task

If any of these fail, the terminal class should change.

## Delivery Does Not Equal Cleanup

Cleanup, cache write, and logging are not themselves terminal semantics.

They are downstream side effects of terminalization.

This distinction matters because the current code often interleaves:

- success assignment
- cache saving
- cleanup
- final user message editing
- terminal logging

Those actions should not be confused with the meaning of the terminal outcome itself.

## Terminalization Inputs

The inputs that legitimately determine terminal outcome include:

- task class
- task scope
- count of requested vs delivered outputs
- existence of valid local deliverables
- existence of valid cache reuse path
- Telegram send/upload result
- whether the task intended media delivery or only response/state mutation

Inputs that should not by themselves determine terminal class include:

- incidental logging success/failure
- cleanup success/failure
- exact temp-directory shape
- thumbnail-generation details once the required delivery succeeded

## Precedence Rules For Terminal Semantics

### 1. User-Facing Delivery Meaning Over Upstream Local Success

For media tasks, successful Telegram delivery takes precedence over mere local artifact existence in determining terminal success.

### 2. Complete Scope Satisfaction Over Single-Artifact Success

For multi-item tasks, all required outputs must be accounted for before the task is classified as full success.

### 3. Partial Delivery Over Flat Failure

If some intended outputs were delivered, partial success should take precedence over undifferentiated failure labeling.

### 4. Terminal Class Over Side Effects

Outcome meaning should be assigned before cache/logging/cleanup side effects are interpreted.

### 5. Branch Family Matters

A direct-link branch, response-only branch, state-mutation branch, and media-delivery branch should not share one undifferentiated success condition.

## Current Code Surfaces

The terminal-semantics surface is currently distributed mainly across:

- [`DOWN_AND_UP/down_and_up.py`](./../../DOWN_AND_UP/down_and_up.py)
- [`DOWN_AND_UP/down_and_audio.py`](./../../DOWN_AND_UP/down_and_audio.py)
- [`DOWN_AND_UP/sender.py`](./../../DOWN_AND_UP/sender.py)
- [`HELPERS/safe_messeger.py`](./../../HELPERS/safe_messeger.py)
- [`HELPERS/logger.py`](./../../HELPERS/logger.py)

This distribution is one reason terminal meaning currently feels less crisp than branch selection or acquisition logic.

## Main Interleavings

The strongest interleavings at this layer are:

- local artifact success with Telegram delivery success
- cache save with task success assignment
- cleanup with terminal closure
- partial counts with binary success/failure language
- task-class differences hidden behind shared success messaging patterns

These are the main places where concealed arbitrariness can re-enter.

## What This Suggests Next

The likely next architectural move after this formulation is:

- define an explicit terminal-outcome object or enum for the task engine

That object would separate:

- outcome meaning
- user-facing reporting
- cache side effects
- cleanup side effects

At the moment, these are too intertwined.

## Recomposition

Recomposed at this layer:

`tg-ytdlp-bot` does not have one success and one failure.
It has multiple terminal outcome classes whose distinction matters operationally.

If those classes are made explicit, partial completion, delivery failure after local success, and cache-reuse success stop looking like edge cases and start looking like normal task semantics.

## Related Documents

- [`Terminal Outcome Result Model`](./10-terminal-outcome-result-model.md): explicit output object for terminalization
