# Task Request Ingress Model

## Purpose

This document follows:

- [`27-ingress-segmentation-model.md`](./27-ingress-segmentation-model.md)
- [`28-ingress-envelope-model.md`](./28-ingress-envelope-model.md)

Its goal is to define the first business-level objects that should be formed from ingress
envelopes.

This is the point where transport normalization stops and actual application work begins.

## Governing Ambiguity

The live ambiguity is:

- what is the first internal object that should carry requested work without remaining transport-
  shaped

If we stop at envelope level, downstream code still has to reinterpret transport fields.

If we jump straight to execution without an explicit task request, then task identity remains
distributed across handlers.

So the correct next layer is:

- explicit task request

## First Recommended Request Types

The first migration should define only a small set of request types.

Best initial candidates:

- `SubtitleOnlyRequested`
- `VideoConcatRequested`

Why:

- explicit command-driven tasks
- already have clearer branch/task semantics than the general text auto-router
- good fit for proving the ingress segmentation without refactoring the whole app

## Minimal Shared Shape

Each task request should minimally carry:

- `request_kind: str`
- `user_id: int`
- `chat_id: int`
- `source_message_id: int | None`
- `source_transport: str`
- `raw_input: str | None`
- `provenance: dict`

This is the shared task-request substrate.

Then each concrete request type adds its constitutive fields.

## `SubtitleOnlyRequested`

Minimal constitutive fields:

- `url: str`
- `subtitle_mode: str`
- `text_only: bool`
- `tags: list[str]`

Optional policy fields:

- subtitle language preference
- auto/translated mode preference

This request should already mean:

- subtitle-only artifact requested

It should not still require downstream code to infer whether the user wanted:

- settings change
- video download with subtitles
- subtitle-only file

## `VideoConcatRequested`

Minimal constitutive fields:

- `url: str`
- `range_start: int`
- `range_end: int`
- `ordering: str`
- `concat_policy: str`
- `chapter_policy: str`
- `output_name_override: str | None`

This request should already mean:

- one composite video artifact requested from a playlist range

It should not still require downstream code to infer branch identity from raw command tokens.

## Envelope -> Task Formation Responsibility

The task-formation layer may:

- parse command arguments
- normalize URL identity
- choose task-request type
- attach explicit task policy fields

It must not:

- perform download staging
- perform compatibility checks
- do Telegram delivery work

Those belong to execution.

## No Generic "CommandRequest" End State

It is acceptable to have a transient internal helper like:

- `CommandRequest`

but that should not be the final business-level object if it still merely wraps:

- command name
- argument tokens

That would remain too transport-shaped.

The first real business object should already answer:

- what work is requested

not merely:

- which command tokens arrived

## Relationship To Existing Runtime Objects

These ingress task requests are upstream of the existing runtime objects:

- `BranchSelectionResult`
- `RuntimeTask`
- `TerminalOutcomeResult`

A coherent next architecture would be:

- `IngressEnvelope`
-> `TaskRequest`
-> `BranchSelectionResult`
-> `RuntimeTask`
-> execution
-> `TerminalOutcomeResult`

This keeps task-request formation distinct from branch-selection and execution.

## Replaceability Consequence

If task requests are explicit, then later:

- Telegram commands
- HTTP endpoints
- dashboard actions

can all produce the same internal request types.

That is the real architectural benefit.

## First Migration Implication

The first implementation should not try to replace every handler.

It should:

1. choose one narrow command path
2. build envelope
3. build request
4. hand off to the current branch/task runtime

So the first useful experiments are:

- `/sub` path
- `/concat` path

## Why This Is The Next Correct PDA Move

We now have:

- ingress stages
- an envelope

The next missing business-level object is:

- task request

That is the correct next move because it is the first object whose authority is:

- requested work

rather than:

- transport mechanics
