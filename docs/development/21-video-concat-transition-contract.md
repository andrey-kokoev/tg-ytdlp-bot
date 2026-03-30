# Video Concat Transition Contract

## Purpose

This document follows:

- [`18-video-concat-first-implementation-seam.md`](./18-video-concat-first-implementation-seam.md)
- [`19-video-concat-compatibility-model.md`](./19-video-concat-compatibility-model.md)
- [`20-video-concat-compatibility-result-model.md`](./20-video-concat-compatibility-result-model.md)

Its goal is to define the first explicit transition contract for
`video_concat_download`.

This is the contract that connects:

- branch selection
- staged acquisition
- compatibility determination
- concat execution
- terminalization

## Governing Ambiguity

The live ambiguity is now procedural:

- what transitions are allowed in the first coherent `video_concat_download` path, and what may
  each transition read, write, and decide

Without an explicit transition contract, implementation would likely collapse back into:

- one oversized executor
- hidden policy drift
- executor-local reinterpretation of branch identity and rejection semantics

## First Closed State Skeleton

The first coherent state progression for video concat should be:

1. `VC0 Requested`
2. `VC1 BranchSelected`
3. `VC2 StagingAcquisition`
4. `VC3 CompatibilityDetermined`
5. `VC4 ConcatExecution`
6. `VC5 DeliveryAttempt`
7. `VC6 Terminalized`

This is intentionally narrower than the full system task machine.
It is the local state skeleton for the concat branch family.

## VC0 -> VC1: Request To Branch

### Role

Interpret explicit user intent as:

- `video_concat_download`

### Reads

- command text
- parsed playlist URL
- parsed range
- concat ordering option
- optional name override

### Writes

- `BranchSelectionResult`
- concat-specific `RuntimeTask` fields

### Authority

- user command authority
- command parser authority

### Must Not Do

- inspect media compatibility
- infer fallback to ordinary playlist download
- inspect Telegram delivery constraints

This transition only selects the branch and establishes the task.

## VC1 -> VC2: Branch To Staging Acquisition

### Role

Acquire staged per-item video artifacts for the selected playlist range under concat intent.

### Reads

- selected playlist range
- ordering policy
- concat policy
- user cookies / shared cookies / proxy policy as ordinary acquisition inputs

### Writes

- staged local video artifacts
- per-item acquisition status
- task-local staging manifest

### Authority

- source-platform authority
- acquisition policy authority

### Must Not Do

- decide concat compatibility from raw failures alone
- silently normalize or re-encode
- silently drop selected items to salvage concat

### Required Output

A staging manifest that makes the selected set explicit:

- selected indices
- staged artifact paths
- missing indices if any
- per-item media facts or probe inputs

## VC2 -> VC3: Staging To Compatibility

### Role

Determine whether the staged set is admissible under:

- `direct_concat_only`

### Reads

- staging manifest
- concat policy
- media facts from staged artifacts

### Writes

- explicit compatibility result
- compatibility summary on task state

### Authority

- concat policy authority
- media-fact authority

### Must Not Do

- run concat and infer admissibility from FFmpeg failure
- widen policy to normalized/re-encoded concat
- reinterpret the task as ordinary playlist delivery

### Required Output

- `VideoConcatCompatibilityResult`

If incompatible:

- the next legal transition is terminal rejection, not concat execution

## VC3 -> VC4: Compatibility To Concat Execution

### Precondition

- compatibility result exists
- `compatible=True`

### Role

Run direct concat over the staged set in the fixed selected order.

### Reads

- ordered staged artifact paths
- concat policy
- optional output name override

### Writes

- one composite staged artifact
- concat execution diagnostics

### Authority

- executor authority
- FFmpeg authority

### Must Not Do

- silently re-encode due to concat failure if policy is `direct_concat_only`
- emit final Telegram success before a composite artifact exists
- reinterpret concat failure as incompatibility after the fact

### Required Output

Either:

- one composite artifact

or:

- explicit acquisition/transformation failure

## VC4 -> VC5: Composite Artifact To Delivery Attempt

### Role

Deliver one composite artifact to Telegram.

### Reads

- composite artifact path
- caption/title/name policy
- Telegram upload constraints

### Writes

- Telegram delivery result
- final message identifiers if delivery succeeds

### Authority

- Telegram delivery authority

### Must Not Do

- reinterpret delivery failure as concat incompatibility
- split the artifact into multiple user-facing outputs without an explicit separate policy

### Required Output

Either:

- delivered composite artifact

or:

- artifact-ready delivery failure

## VC5 -> VC6: Delivery To Terminalization

### Role

Produce one terminal outcome that reflects the requested unit:

- one composite artifact

### Reads

- branch identity
- compatibility result
- concat execution result
- Telegram delivery result

### Writes

- `TerminalOutcomeResult`
- task terminal outcome

### Must Not Do

- report playlist-style partial success by default
- count individual staged items as the requested user-facing unit

### Required Terminal Classes

- `artifact_delivery_success`
- `determinate_rejection`
- `acquisition_or_transformation_failure`
- `artifact_ready_delivery_failure`

## Forbidden Collapses

The first video concat implementation must not collapse any of these distinctions:

- incompatibility vs FFmpeg concat failure
- branch rejection vs ordinary playlist fallback
- one requested composite artifact vs many staged items
- delivery failure vs concat failure

If these collapse, the branch loses its coherence immediately.

## Minimal Manifest Requirement

The first implementation needs one explicit staging manifest object or dict-like structure.

Why:

- compatibility depends on the selected set as a set
- concat execution depends on ordered staged paths
- terminal rejection needs selected-set evidence

Without a manifest, state will diffuse back into executor locals.

## Minimal Result Chain

Before any implementation is considered coherent, the path should have at least these explicit
objects:

- `BranchSelectionResult`
- `RuntimeTask`
- staging manifest
- compatibility result
- `TerminalOutcomeResult`

This is the minimum chain that preserves determination through the branch.

## Tests Implied By This Contract

The first implementation tests should verify:

1. explicit `/concat` request creates `video_concat_download`
2. missing staged item leads to rejection before concat execution
3. mixed media shape leads to rejection before concat execution
4. compatible staged set reaches concat execution
5. concat execution failure becomes transformation failure, not rejection
6. delivery failure after composite artifact exists becomes delivery failure, not transformation
   failure

## Why This Is The Next Correct PDA Move

The previous documents localized:

- branch identity
- admissibility
- compatibility result

This document closes the remaining live ambiguity around control flow.

That is the correct next move because the first coherent implementation now has:

- one branch
- one local state machine
- one explicit admissibility gate
- one explicit terminalization path
