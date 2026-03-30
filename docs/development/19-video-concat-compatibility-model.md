# Video Concat Compatibility Model

## Purpose

This document follows:

- [`16-video-concat-formulation.md`](./16-video-concat-formulation.md)
- [`17-video-concat-admissibility-contract.md`](./17-video-concat-admissibility-contract.md)
- [`18-video-concat-first-implementation-seam.md`](./18-video-concat-first-implementation-seam.md)

Its goal is to make one specific live ambiguity explicit:

- when does a selected playlist range count as directly concat-compatible under the initial
  `direct_concat_only` policy

This is not yet the full executor design.
It is the compatibility determination layer that stands between:

- staged acquisition
- concat execution

## Governing Ambiguity

The live ambiguity is not:

- whether concat was requested
- whether the selected range exists

Those are already upstream.

The live ambiguity is:

- whether the staged video artifacts may be treated as one admissible direct-concat set without
  silently introducing a second policy such as normalization or re-encoding

## Why This Layer Must Be Explicit

Without an explicit compatibility model, the system would drift back into incoherence:

- concat admissibility would be inferred from FFmpeg failure text
- normalization would creep in implicitly as "best effort"
- the requested unit would blur from one composite artifact into a sequence of per-item recovery
  attempts

Under PDA, this layer must stay explicit because it decides whether the selected branch remains:

- admissible
- rejected
- or has crossed into a different unrequested transformation regime

## Authority

At this layer, the relevant authorities are:

- user authority
  the user requested composite video concat over a chosen playlist range
- platform authority
  the acquired artifacts have concrete codecs, containers, frame rates, stream layouts, and
  durations
- concat policy authority
  v1 policy is `direct_concat_only`, so compatibility must be judged against direct concat rules,
  not broader "could maybe be re-encoded" feasibility

The executor does **not** have authority to silently broaden policy from:

- `direct_concat_only`

to:

- `normalized_concat`
- `reencoded_concat`

## Constitutive Inputs

The compatibility predicate may inspect only information constitutive of direct concat
compatibility, such as:

- selected item ordering
- final staged container
- video codec
- audio codec
- width and height
- frame rate
- presence/absence of audio stream
- time base / stream layout details if needed

It may also inspect:

- whether every selected item produced a staged artifact at all

It must not use:

- Telegram delivery constraints as a compatibility criterion
- caption/title metadata
- thumbnail availability
- cache policy

Those belong to later transitions.

## Required Predicate Shape

The first compatibility helper should return a structured result, not only a boolean.

Recommended shape:

- `compatible: bool`
- `reason_code: str | None`
- `reason_text: str | None`
- `evidence: dict`

Where:

- `reason_code` is stable enough for terminalization and tests
- `reason_text` is compact user/log language
- `evidence` records the concrete mismatch surface

Example reason codes:

- `missing_staged_artifact`
- `mixed_container`
- `mixed_video_codec`
- `mixed_audio_codec`
- `mixed_resolution`
- `mixed_framerate`
- `mixed_stream_layout`

## Compatibility Standard For V1

Under `direct_concat_only`, the selected set should count as compatible only if all staged items
share the same direct-concat-relevant media shape.

That means at minimum:

- every selected item staged successfully
- same output container
- same video codec
- same audio codec, or all have no audio
- same resolution
- same effective frame rate
- same stream layout category

The standard should be intentionally strict in v1.

Why:

- strict explicit rejection is more coherent than silent partial normalization
- it preserves the meaning of `direct_concat_only`
- it keeps failure meaning distinct from inadmissibility

## Inadmissibility vs Failure

This layer must distinguish:

- inadmissibility
- execution failure

Inadmissibility means:

- the selected/staged set does not satisfy direct concat rules

Failure means:

- the set was admissible, but acquisition, concat execution, or delivery failed

This distinction matters because:

- inadmissibility should become `determinate_rejection`
- failure should become `acquisition_or_transformation_failure` or
  `artifact_ready_delivery_failure`

## No Silent Downshift

If compatibility fails, the system must not silently:

- send items separately
- send only the compatible subset
- re-encode the set
- fall back to audio-only
- fall back to ordinary playlist video delivery

All of those would be different tasks.

The correct v1 response is:

- reject the requested concat task explicitly

## Ordering As Part Of Compatibility Context

Compatibility is checked after ordering is fixed.

Why:

- the selected set is not only which items, but in what order they are meant to form one artifact

However, ordering itself should not change media compatibility.
It changes:

- concat input order

It does not change:

- whether the staged set is technically direct-concat-compatible

So ordering is constitutive context, but not usually the mismatch cause.

## RuntimeTask Consequence

If the task is `video_concat_download`, then compatibility determination should write back:

- concat compatibility result
- concat policy used
- ordering used

onto the task or its branch provenance.

This keeps admissibility visible at the task level instead of leaving it buried inside executor
locals.

## TerminalOutcomeResult Consequence

If incompatibility is found, the terminal outcome should carry:

- `outcome_kind="determinate_rejection"`
- `reason_code` from the compatibility predicate
- optional compact mismatch evidence

That is more coherent than treating incompatibility as generic FFmpeg failure.

## Tests Implied By This Model

Once implemented, the first tests should verify:

1. identical staged media shape => compatible
2. mixed container => determinate rejection
3. mixed resolution => determinate rejection
4. mixed audio-stream presence => determinate rejection
5. missing artifact in selected range => determinate rejection
6. compatibility failure does not trigger silent fallback to ordinary playlist delivery

## Why This Is The Next Correct PDA Move

The current live ambiguity for video concat is not the command surface anymore.
It is:

- what exactly counts as admissible concat under the chosen v1 policy

This document localizes that ambiguity so the first implementation can stay coherent:

- explicit branch
- explicit admissibility
- explicit rejection
- no hidden normalization policy
