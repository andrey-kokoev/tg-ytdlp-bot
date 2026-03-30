# Video Concat Terminal Rendering Contract

## Purpose

This document follows:

- [`20-video-concat-compatibility-result-model.md`](./20-video-concat-compatibility-result-model.md)
- [`21-video-concat-transition-contract.md`](./21-video-concat-transition-contract.md)
- [`22-video-concat-staging-manifest-model.md`](./22-video-concat-staging-manifest-model.md)

Its goal is to define how `video_concat_download` terminal outcomes should be rendered to:

- the user
- logs

This is not the same thing as terminal outcome determination.
That has already been localized.

This document addresses the next live ambiguity:

- how the explicit concat branch should speak about its own terminal states without collapsing back
  into ordinary playlist-download wording

## Governing Ambiguity

The live ambiguity is representational:

- once `video_concat_download` reaches a terminal state, what text should express that state so the
  requested unit remains one composite artifact rather than many playlist items

Without an explicit rendering contract, the system would likely regress into:

- playlist-style "sent X/Y videos"
- generic FFmpeg failure text
- ordinary download failure wording
- logs that obscure whether rejection happened before concat execution

## Requested Unit Must Remain Visible

For video concat, the requested unit is:

- one composite video artifact

Rendering must preserve that.

It must not default to language whose primary unit is:

- individual playlist items
- separate delivered videos
- partially delivered playlist members

That language belongs to ordinary playlist delivery, not concat.

## Required Terminal Classes

Rendering should distinguish at least these classes:

- `artifact_delivery_success`
- `determinate_rejection`
- `acquisition_or_transformation_failure`
- `artifact_ready_delivery_failure`

These classes should not share one generic fallback message.

## User-Facing Rendering Contract

### Success

Success should render as:

- one composite result completed and delivered

The message should refer to:

- concat success
- composite output identity
- optional output name if provided

It should not emphasize:

- how many playlist items were staged, except optionally as supporting detail

Example shape:

- `✅ Concat complete: 5 playlist items merged into one video.`

### Determinate Rejection

Rejection should render as:

- the requested concat task was understood but is not admissible under current policy

It should mention:

- that direct concat is not possible
- one compact reason

It should not sound like:

- a transient download error
- a generic FFmpeg crash

Example shape:

- `⚠️ Video concat is not possible under direct concat mode: selected videos do not share one resolution.`

### Acquisition Or Transformation Failure

This should render as:

- concat was a valid task, but staging or concat execution failed

It may mention:

- whether failure happened during staging
- whether failure happened during concat execution

It should not be described as rejection.

Example shape:

- `❌ Video concat failed while building the composite video.`

### Artifact-Ready Delivery Failure

This should render as:

- the composite artifact exists, but Telegram delivery failed

It must not sound like:

- concat incompatibility
- yt-dlp acquisition failure

Example shape:

- `⚠️ Composite video created, but Telegram could not receive it.`

## Logging Contract

Logs should be more specific than user text.

Each terminal log line should include:

- branch family
- outcome kind
- concat policy
- ordering
- requested item count
- rejection/failure reason code if any

Recommended examples:

- `[video_concat] success policy=direct_concat_only ordering=reverse requested=5 delivered=1`
- `[video_concat] rejected policy=direct_concat_only reason=mixed_resolution`
- `[video_concat] failed phase=concat_execution reason=ffmpeg_concat_failed`
- `[video_concat] delivery_failed artifact_ready=true`

Logs should avoid:

- replaying large FFmpeg stderr by default in the summary line
- using playlist-style sent counts as the primary interpretation

## Rendering Inputs

User/log rendering may read:

- `BranchSelectionResult`
- `RuntimeTask`
- staging manifest summary
- compatibility result
- `TerminalOutcomeResult`

It should not need to rediscover:

- selected range from raw command text
- compatibility reason from raw FFmpeg output
- branch family from handler path guesses

## Required Compact Supporting Detail

The first rendering contract may include compact supporting detail when it materially clarifies the
terminal state:

- requested item count
- ordering
- output name
- primary rejection reason

It should not include:

- full per-item artifact breakdown
- verbose probe evidence
- full exception traces

Those belong in deeper logs or debug tooling.

## No Playlist-Partial Default

The first video concat rendering contract should not use ordinary playlist partial-completion
language by default.

Why:

- the requested unit is one composite artifact
- a concat task with one incompatible item is not "partially successful" in the ordinary playlist
  sense

If future policy introduces normalized or subset concat, that is a different task contract.

For v1:

- incompatibility => rejection
- concat failure => failure
- delivery failure => delivery failure

## Name Override Consequence

If the user supplied a concat output name override, rendering should prefer that as the artifact
identity for:

- success
- delivery failure

It should not override:

- rejection reason
- compatibility diagnosis

## Tests Implied By This Contract

The first implementation tests should verify:

1. success rendering refers to one composite video, not playlist member counts as primary unit
2. mixed-resolution rejection renders as inadmissibility, not generic failure
3. concat-execution failure renders as failure, not rejection
4. delivery failure renders as artifact-ready delivery failure
5. log summary contains branch family and reason code
6. user-facing rejection does not mention ordinary playlist partial completion

## Why This Is The Next Correct PDA Move

The previous documents made branch, compatibility, manifest, and terminal classes explicit.
The next coherent step is to make rendering explicit too.

Otherwise, the feature would remain formally coherent internally but still present itself through:

- legacy playlist semantics
- generic executor failure wording

That would reintroduce confusion at the user-facing boundary.
