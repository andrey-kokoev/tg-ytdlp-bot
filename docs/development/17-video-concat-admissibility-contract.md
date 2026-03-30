# Video Concat Admissibility Contract

## Purpose

This document descends from:

- [`16-video-concat-formulation.md`](./16-video-concat-formulation.md)
- [`13-transition-contracts.md`](./13-transition-contracts.md)

Its purpose is to make the admissibility boundary for `video_concat_download` explicit.

That boundary is the live PDA layer because the system must decide:

- whether video concat is a valid branch at all for the current task
- whether direct concat is admissible under the chosen policy
- when the system must reject early rather than pretend execution can repair branch incoherence

## Governing Ambiguity

The live ambiguity is not:

- how to invoke FFmpeg

It is:

- what must already be true before the system may legitimately commit to video concat
- which failures count as pre-branch inadmissibility versus post-branch execution failure

If this contract remains implicit, concat will oscillate between:

- premature commitment
- silent fallback to unrelated branches
- overloading "failure" with incompatible meanings

## Contract Position

This contract governs the `S3 -> S4` and `S4 -> S5` boundary for:

- `video_concat_download`

More precisely:

- `T3` may select `video_concat_download` only if branch-level admissibility is satisfied
- `T4` may execute only under the selected concat policy and may not silently redefine that policy

## Required Inputs

Before concat may be selected, the task must have:

- explicit concat intent
- explicit selected playlist scope
- explicit ordering policy
- explicit media class
- explicit concat policy

For a first coherent implementation, concat policy should be fixed to:

- `direct_concat_only`

## Minimal Branch-Level Admissibility

At branch-selection time, the following must already be true.

### A1. Multi-Item Scope

The selected scope must contain at least 2 items.

If not:

- concat is inadmissible
- ordinary single-item delivery must not be silently substituted

### A2. Playlist/Range Identity Must Be Explicit

The request must define an ordered multi-item selection.

Examples:

- items `3..7`
- items `7..3`
- explicit reverse ordering over a selected range

If task scope is still ambiguous or collapsed to a single-item default:

- concat is not yet admissible

### A3. Media Intent Must Be Video

The branch must be explicitly video concat.

Audio concat is not equivalent and should remain a separate admissibility surface.

### A4. Concat Policy Must Be Known

For v1, the chosen policy must be known before execution:

- `direct_concat_only`

If the system has not committed to a policy, the branch is under-specified and should not be selected.

### A5. No Silent Fallback Authority

The branch-selection layer must know in advance that if concat becomes inadmissible later, it should:

- reject with a concat-specific reason

It must not:

- silently degrade into ordinary playlist delivery
- silently route into split-video delivery
- silently route into gallery fallback

## Execution-Stage Admissibility Checks

After branch selection, execution may continue only if staged artifacts satisfy the selected concat policy.

For `direct_concat_only`, the checks are:

### E1. Every Selected Item Must Acquire Successfully

Each selected item must yield a valid local video artifact.

If not:

- this is an `acquisition_failed` path
- not a justification for changing branch family

### E2. Every Artifact Must Match Expected Media Class

Each artifact must be a real video artifact for concat purposes.

Audio-only or malformed artifacts do not satisfy this branch.

### E3. Direct Concat Compatibility Must Hold

Under `direct_concat_only`, staged artifacts must satisfy the compatibility policy required for direct FFmpeg concat.

This means the system must have an explicit compatibility predicate.

At minimum, it should examine:

- container compatibility
- codec compatibility
- key stream parameters relevant to direct concat

If compatibility fails:

- the concat branch remains selected
- execution fails with `selection_inadmissible` or `concat_failed`, depending on where the check is performed
- the system must not silently switch to normalized concat unless that policy was explicitly authorized earlier

### E4. Final Artifact Must Be Deliverable Under Current Delivery Policy

If the final artifact is expected to exceed Telegram delivery constraints under the currently selected delivery mode, the system must:

- reject the branch before expensive transformation, or
- move under an explicitly authorized alternate delivery policy

It must not discover this only after pretending full branch admissibility existed.

## Boundary Between Inadmissibility And Failure

This distinction is critical.

### Inadmissibility

Use inadmissibility when the branch should not have been selected under the known policy.

Examples:

- only one item selected
- concat policy unknown
- staged artifacts provably incompatible with `direct_concat_only`
- final artifact predictably undeliverable under selected delivery mode

### Failure

Use failure when the branch was admissible, but execution did not succeed.

Examples:

- source acquisition failed for one selected item
- FFmpeg concat command failed despite predicted compatibility
- Telegram delivery failed after composite artifact success

## Explicit Rejection Reasons

For coherence, the branch should expose coarse rejection reasons such as:

- `concat_scope_too_small`
- `concat_scope_not_explicit`
- `concat_policy_missing`
- `concat_direct_compatibility_failed`
- `concat_delivery_policy_inadmissible`

These reasons should be first-class, not hidden in free-form logs.

## What Must Not Happen

The concat admissibility contract forbids these silent redefinitions:

- concat request -> ordinary playlist download
- concat request -> first successful item only
- concat request -> split-video branch
- concat request -> audio-only branch
- direct concat request -> normalized concat without explicit policy transition

Any of those may be acceptable user-visible behaviors only if they are modeled as explicit alternative branches and selected by explicit authority.

## Consequences For Terminal Semantics

This contract implies:

- many concat problems should terminate as determinate rejection or explicit concat failure
- "partial success" should be rare
- per-item acquisition success is not itself terminal success
- the requested unit remains one composite artifact

## Minimal V1 Policy

For the first coherent implementation:

- branch family: `video_concat_download`
- concat policy: `direct_concat_only`
- fallback policy: `reject_only`
- normalization policy: `not_authorized`

This is intentionally strict.

Why:

- it sharply localizes the admissibility boundary
- it prevents hidden policy escalation
- it gives clean evidence about what the real failure surface is before introducing more permissive policies

## Transition Contract Implications

### T3 Must Be Allowed To Read

- explicit concat intent
- selected ordered range
- branch policy configuration

### T3 Must Write

- explicit `BranchSelectionResult` with concat branch family
- explicit concat policy provenance

### T3 Must Not Do

- assume normalization is allowed if it was never selected
- hide compatibility assumptions in raw FFmpeg arguments

### T4 Must Be Allowed To Read

- concat policy
- staged artifact metadata
- compatibility evidence

### T4 Must Write

- explicit acquisition evidence
- explicit compatibility decision
- explicit failure locus if concat cannot continue

### T4 Must Not Do

- switch branch family implicitly
- reinterpret compatibility failure as ordinary playlist success

## What This Suggests Next

The next natural PDA move is:

- define the `BranchSelectionResult` shape for `video_concat_download`
- define the first implementation seam that enforces `direct_concat_only` without contaminating ordinary `video_download`

That is the next descent because admissibility is now localized enough to support a concrete branch/result contract.
