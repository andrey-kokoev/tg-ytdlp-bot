# Transition Contracts

## Purpose

This document defines the conceptual contracts for the task-state-machine transitions implied by:

- [`11-task-state-machine-sketch.md`](./11-task-state-machine-sketch.md)
- [`12-task-object-model.md`](./12-task-object-model.md)

The goal is to specify, for each transition:

- what it may read
- what it may decide
- what it may write
- what it must not silently redefine
- what explicit result, if any, it should produce

This is the next natural PDA move because the main remaining ambiguity is not what the states are, but what each transition is allowed to do without collapsing neighboring layers.

## Governing Ambiguity

The current system often lets one transition perform work that conceptually belongs to another.

Examples:

- routing surfaces influence branch identity indirectly
- branch selection leaks execution details
- terminal semantics are inferred from execution side effects

So the live ambiguity is:

- what each transition class is legitimately responsible for, and where its authority should stop

## Contract Style

Each transition contract below is expressed in terms of:

- **Input**
- **Allowed reads**
- **Allowed writes**
- **Decision authority**
- **Required output**
- **Must not do**

The point is not to prescribe code style.
It is to preserve state-boundary clarity.

## T0: Routing Transition

### From / To

- `S0 Inbound Event` -> `S1 Routed Task`

### Input

- inbound Telegram update
- minimal runtime/session context needed for handler classification

### Allowed Reads

- update type and payload
- command syntax
- minimal user/task gating state needed to know whether routing is admissible

### Allowed Writes

- task class
- initial routing provenance
- explicit early rejection reason if routing fails

### Decision Authority

- Telegram update type
- router logic
- explicit command classification

### Required Output

- task moved to `S1`
- or direct terminal rejection path prepared

### Must Not Do

- perform branch selection
- infer final terminal success/failure
- smuggle execution-only policy into routing identity

## T1: Context-Resolution Transition

### From / To

- `S1 Routed Task` -> `S2 Context-Resolved`

### Input

- routed task

### Allowed Reads

- per-user persisted state
- callback context
- in-flight task/session context
- original input scope

### Allowed Writes

- normalized task scope
- resolved user-state snapshot
- context fields needed for admissible-branch reasoning

### Decision Authority

- persisted user state
- task-local context
- callback linkage

### Required Output

- task with enough context to know what branches might be admissible

### Must Not Do

- silently choose a branch
- treat missing context as a branch decision
- infer terminal outcome

## T2: Metadata-Resolution Transition

### From / To

- `S2 Context-Resolved` -> `S3 Metadata-Resolved`

### Input

- context-resolved task

### Allowed Reads

- source-platform metadata
- extractor outputs
- access enablers such as cookies/proxies/PO-token helpers
- user/execution context relevant to extraction

### Allowed Writes

- metadata context
- admissibility pruning facts
- evidence about feasible branch families

### Decision Authority

- source-platform feasibility
- extractor behavior
- access feasibility

### Required Output

- task with enough metadata to select among admissible branches or reject them

### Must Not Do

- silently redefine user intent
- encode branch identity only as raw execution parameters
- assign terminal success/failure

## T3: Branch-Selection Transition

### From / To

- `S3 Metadata-Resolved` -> `S4 Branch-Selected`

### Input

- metadata-resolved task

### Allowed Reads

- explicit current-task user choice
- saved defaults
- task scope
- cache-equivalence facts
- admissibility pruning facts from metadata-resolution

### Allowed Writes

- `branch_selection_result`
- task current state

### Decision Authority

- explicit user choice first
- saved user defaults otherwise
- cache policy where semantically valid
- pruning by inadmissibility

### Required Output

- explicit `BranchSelectionResult`

### Must Not Do

- collapse branch identity into only `format_override` or `quality_key`
- hide who selected the branch
- silently rewrite a pruned branch into a different branch without explicit fallback semantics
- assign final terminal meaning

## T4: Execution / Acquisition Transition

### From / To

- `S4 Branch-Selected` -> `S5 Material Acquisition`

### Input

- task with explicit branch-selection result

### Allowed Reads

- branch-selection result
- context snapshot
- execution constraints
- access requirements

### Allowed Writes

- acquisition attempts
- execution evidence
- intermediate artifacts
- progress evidence

### Decision Authority

- execution feasibility under selected branch
- external source/platform behavior
- local processing feasibility

### Required Output

- task moved into or through active execution

### Must Not Do

- reconstruct branch identity from scratch
- reinterpret saved defaults as if they outranked explicit branch choice
- assign final terminal meaning solely from partial execution evidence

## T5: Artifact-Availability Transition

### From / To

- `S5 Material Acquisition` -> `S6 Local Artifact Available`

### Input

- task with execution evidence

### Allowed Reads

- acquired bytes/artifacts
- post-processing outputs
- cache-equivalent references

### Allowed Writes

- artifact references
- artifact-status evidence

### Decision Authority

- artifact existence and validity
- cache-equivalence validity

### Required Output

- explicit task state showing whether a valid deliverable or equivalent exists

### Must Not Do

- treat artifact availability as terminal success
- confuse cache-equivalent readiness with ordinary fresh artifact creation without preserving provenance

## T6: Delivery Transition

### From / To

- `S6 Local Artifact Available` -> `S7 Delivery Attempt`

### Input

- task with valid deliverable or equivalent

### Allowed Reads

- artifact refs
- delivery intent
- user delivery constraints
- Telegram delivery requirements

### Allowed Writes

- delivery attempts
- delivery evidence

### Decision Authority

- Telegram delivery acceptance
- delivery-mode constraints

### Required Output

- task with explicit delivery evidence

### Must Not Do

- collapse "artifact ready" into "task succeeded"
- let cleanup success/failure stand in for delivery meaning

## T7: Terminalization Transition

### From / To

- `S7 Delivery Attempt` -> `S8 Terminal Outcome`

### Input

- task with branch-selection result
- task with delivery/artifact evidence

### Allowed Reads

- branch-selection result
- task class
- requested scope
- satisfied scope
- artifact status
- delivery status
- failure evidence

### Allowed Writes

- `terminal_outcome_result`
- task current state

### Decision Authority

- delivered-vs-requested scope
- artifact status
- delivery status
- branch family and task class

### Required Output

- explicit `TerminalOutcomeResult`

### Must Not Do

- let cache writes, cleanup, or logging define outcome meaning
- flatten partial success into generic success/failure
- forget branch provenance when assigning terminal class

## Post-Terminal Side Effects

After `S8`, the following may still occur:

- cache writes
- cleanup
- final user-visible string rendering
- logging

These are legitimate side effects, but they should be driven by `terminal_outcome_result`.
They should not redefine it.

## Short-Circuit Contracts

Some transitions legitimately short-circuit the longer machine.

### Routing Rejection Shortcut

- `S1 -> S8`
- allowed output: `TerminalOutcomeResult` with rejection semantics

### Response-Only / State-Mutation Shortcut

- `S4 -> S8`
- allowed output: `TerminalOutcomeResult` with response-only or state-mutation success

### Acquisition Failure Shortcut

- `S5 -> S8`
- allowed output: `TerminalOutcomeResult` with acquisition/transformation failure

These shortcuts are valid only if they still produce explicit terminal outcome meaning.

## Cross-Transition Rule

No transition should be forced to reconstruct a previous transition's constitutive result from derived execution details.

In practice that means:

- terminalization should not infer branch identity from raw format flags
- execution should not infer task identity from a single message object
- routing should not quietly decide later branch semantics

This is the main anti-incoherence rule of the whole formulation.

## What This Suggests Next

The next natural move after transition contracts is no longer mostly conceptual.
It becomes a decision about implementation entry.

The main options are:

- introduce a real `BranchSelectionResult` first
- introduce a real `TerminalOutcomeResult` first
- introduce a lightweight `Task` container first

The most conservative first move is probably:

- implement `BranchSelectionResult` at the `S3 -> S4` boundary

because that is the highest-leverage interleaving surface.

## Recomposition

Recomposed at this layer:

the task machine now has explicit transition contracts.

That means the architecture is no longer only described by states and outcomes, but also by what each transition is allowed to mean.

## Related Documents

- [`First Implementation Seam`](./14-first-implementation-seam.md): justification for starting implementation at `S3 -> S4` with `BranchSelectionResult`
