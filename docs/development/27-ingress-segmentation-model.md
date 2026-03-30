# Ingress Segmentation Model

## Purpose

This document applies the PDA lens to the system's external ingress boundary.

Its goal is to make explicit the correct decomposition of the current handler-first stream into
replaceable stages without collapsing transport mechanics into task semantics.

## Governing Ambiguity

The live ambiguity is:

- what exactly crosses from Telegram into the application as authoritative internal state

At present, the system often behaves as if the incoming object were:

- a command string

That is too low-level and too transport-shaped.

The actual ingress contains heterogeneous objects:

- text commands
- plain URL text
- callback queries
- documents
- replies and source-message context

So the next PDA move is to separate the ingress into stages that answer different questions.

## Recommended Segmentation

The coherent segmentation is:

1. `Transport Event`
2. `Ingress Envelope`
3. `Task Request`
4. `Execution`

Only the first three are ingress-side stages.

## Stage 1: Transport Event

This stage answers:

- what arrived from the outer world through the Telegram transport

Examples:

- message text update
- callback query
- document upload

This stage is Telegram-specific.
Its authority belongs to:

- Pyrogram
- Telegram update structure

It should not define business semantics.

## Stage 2: Ingress Envelope

This stage answers:

- what transport context must be preserved so downstream code does not keep reparsing Telegram
  objects ad hoc

Examples of preserved context:

- user/chat identity
- source message id
- callback provenance
- raw payload
- transport kind

This stage is still partly transport-shaped, but already normalized.

It should not yet decide the full task semantics.

## Stage 3: Task Request

This stage answers:

- what internal work is actually being requested

Examples:

- `SubtitleOnlyRequested`
- `VideoConcatRequested`
- `AudioDownloadRequested`
- `VideoDownloadRequested`

This is the first business-level object.
Downstream execution should prefer this object over raw Telegram structures.

## Stage 4: Execution

This stage answers:

- how the requested task is carried out and terminalized

By this point, transport-specific parsing should be over.

Execution may still produce Telegram-facing outputs later, but it should not keep deriving task
identity from raw Telegram input.

## Why Command String Is The Wrong Unit

`command string` is not a sufficient authoritative ingress object because it collapses live
distinctions:

- command vs plain URL text
- command vs callback payload
- command vs uploaded document
- user/chat identity
- source/reply context
- already-parsed task intent

If the system pretends command string is the single ingress type, downstream logic will keep
rebuilding context differently in different handlers.

That is exactly the incoherence we have seen elsewhere.

## Why Generic Envelope Alone Is Not Enough

A normalized envelope is necessary, but not sufficient.

If the system stops there, then business logic still has to reinterpret transport-shaped state.

That leaves the main ambiguity unresolved:

- what internal task is being requested

So the correct PDA layering is not:

- transport event -> execution

and not merely:

- transport event -> envelope

It is:

- transport event -> envelope -> task request -> execution

## Replaceability Consequence

This segmentation is valuable because each stage can later be replaced independently.

Examples:

- replace Telegram transport with HTTP ingress
- keep envelope normalization + task request formation
- replace in-process execution with queued workers
- keep ingress logic stable

That only works if the stages are explicit.

## Authorities By Stage

### Transport Event

- Telegram/Pyrogram authority

### Ingress Envelope

- normalization authority
- context preservation authority

### Task Request

- application task semantics
- branch/task selection authority

### Execution

- worker/process authority
- branch-specific runtime policy

These authorities should not be merged casually.

## Minimal First Refactor Implication

The first refactor should not try to convert the whole app at once.

It should choose one narrow path and make the stage boundaries explicit there.

Best candidates:

- `/sub`
- `/concat`

Why:

- explicit command-driven tasks
- narrower ingress than the broad text auto-router
- easier to compare current handler-first flow with segmented ingress flow

## Why This Is The Right Abstraction Level

This segmentation is the right abstraction level because:

- it does not confuse transport mechanics with business semantics
- it does not over-abstract into "everything is just messages"
- it preserves the minimum live distinctions needed for coherent replacement and extension

So the correct unit is not:

- command string

and not simply:

- generic message

but:

- transport event
- normalized ingress envelope
- explicit task request

## Next PDA Move

The next correct move is to define:

- the minimal `IngressEnvelope`

and then:

- the first narrow `TaskRequest` types

That will make the segmentation executable rather than merely descriptive.
