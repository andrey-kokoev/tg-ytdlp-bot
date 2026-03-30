# Video Concat Chapter Policy Model

## Purpose

This document follows:

- [`23-video-concat-terminal-rendering-contract.md`](./23-video-concat-terminal-rendering-contract.md)

Its goal is to make chapter behavior explicit for future `video_concat_download`.

The question is not:

- whether a composite artifact exists

That is already part of the concat task itself.

The question is:

- whether the composite artifact should also preserve playlist-item boundaries as chapters

## Governing Ambiguity

The live ambiguity is an output-policy ambiguity:

- is chapter inclusion constitutive of the requested concat artifact, optional metadata enrichment,
  or out of scope for v1

If this is not made explicit, the implementation is likely to drift into one of two incoherent
states:

- silently dropping boundaries even when the user expects navigability
- silently attempting chapter generation and turning metadata issues into concat failures

## Recommended Policy Separation

Chapter behavior should be treated as a separate policy axis from:

- concat admissibility
- concat execution
- Telegram delivery

Recommended field:

- `chapter_policy = "none" | "playlist_item_boundaries"`

This policy should live on the task or concat-specific provenance, not as an incidental ffmpeg
flag.

## Why Chapters Are Not Core Admissibility

Chapter generation should not affect whether a selected set is admissible for direct concat.

Why:

- direct concat compatibility depends on media shape
- chapter generation depends on metadata and timing bookkeeping

If chapters are treated as part of admissibility, the system would blur:

- media incompatibility
- metadata construction failure

Those are different failure surfaces.

## Recommended V1 Policy

For the first implementation of `video_concat_download`, the coherent default is:

- `chapter_policy = "none"`

Why:

- keeps the first concat branch focused on one composite artifact
- avoids turning chapter timing bugs into apparent concat failure
- keeps terminal semantics cleaner

This does not reject future chapter support.
It simply keeps it out of the first admissibility/execution boundary.

## Future Optional Policy

A later implementation may support:

- `chapter_policy = "playlist_item_boundaries"`

That would mean:

- each selected playlist item contributes one chapter span
- chapter titles are derived from item titles or normalized names
- chapter timing is based on staged/composite durations

But that should remain an explicit policy upgrade, not an accidental side effect.

## Required Separation Of Failure Meaning

If chapters are later supported, failure to generate chapters should not automatically mean:

- concat incompatibility

and should not necessarily mean:

- concat execution failure

Possible future policy choices:

- chapter generation failure downgrades to no chapters
- chapter generation failure fails the task only if chapters were explicitly required

Those are policy decisions and should remain separate from v1.

## RuntimeTask Consequence

If/when chapter policy is added, it should be task-level state:

- `task_context.chapter_policy`

This is because it changes the requested composite artifact semantics, not just local executor
behavior.

## TerminalOutcomeResult Consequence

For v1 with `chapter_policy = "none"`:

- terminal outcomes do not mention chapters

For future chapter support:

- outcomes may include whether chapters were applied
- but only as supporting detail, not as the primary terminal class

## User-Facing Rendering Consequence

For v1:

- do not promise chapters
- do not imply preserved playlist navigation markers

For future explicit chapter support:

- success rendering may mention:
  - `with playlist-item chapters`

only when that policy was selected and satisfied.

## Tests Implied By This Model

When implemented later, tests should verify:

1. v1 video concat defaults to `chapter_policy="none"`
2. chapter policy does not affect direct concat admissibility
3. chapter-generation issues do not become false incompatibility reports
4. future explicit chapter support stays opt-in and task-visible

## Why This Is The Next Correct PDA Move

Video concat is now explicit enough that secondary output semantics become the next likely source
of hidden arbitrariness.

Chapters are the clearest example:

- useful
- non-trivial
- easy to entangle with concat execution if left implicit

So the correct PDA move is to name chapter policy as its own axis now, before implementation
accidentally bakes in one unexamined default.
