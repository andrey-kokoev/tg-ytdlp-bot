# Video Concat Policy Partition

## Purpose

This document follows:

- [`17-video-concat-admissibility-contract.md`](./17-video-concat-admissibility-contract.md)
- [`21-video-concat-transition-contract.md`](./21-video-concat-transition-contract.md)
- [`25-video-concat-object-chain-implementation-sketch.md`](./25-video-concat-object-chain-implementation-sketch.md)

Its goal is to remove the last obvious policy interleaving before implementation.

The policies most likely to blur together are:

- concat admissibility policy
- delivery admissibility policy
- rendering policy

They interact, but they are not the same layer.

## Governing Ambiguity

The live ambiguity is:

- which decisions belong to concat-policy determination
- which belong to delivery policy
- which belong only to terminal rendering

If these are not partitioned explicitly, the implementation will likely:

- report delivery constraints as if they were concat incompatibility
- report concat incompatibility as if it were Telegram upload failure
- render one layer's policy using another layer's vocabulary

## Policy Layers

## 1. Concat Admissibility Policy

This policy governs whether the selected and staged set may proceed into concat execution at all.

For v1:

- `concat_policy = "direct_concat_only"`

This layer may decide:

- compatible vs incompatible
- rejection reason for incompatible staged sets

This layer must not decide:

- Telegram upload strategy
- whether a success/failure message should be verbose

## 2. Delivery Admissibility Policy

This policy governs whether the requested composite artifact is deliverable under current Telegram
delivery rules.

This layer may decide:

- whether the composite artifact can be uploaded as selected
- whether delivery mode is already under-specified or invalid

This layer must not decide:

- whether the staged set is direct-concat-compatible
- whether a concat failure should be called incompatibility

In other words:

- concat admissibility answers "may we build one composite artifact"
- delivery admissibility answers "may we deliver that artifact under current delivery policy"

## 3. Terminal Rendering Policy

This policy governs how already-determined terminal states are presented.

This layer may decide:

- wording
- compactness
- whether supporting detail is included

This layer must not redefine:

- branch family
- rejection class
- failure class

Rendering should consume terminal meaning, not author it.

## Required Order

These layers must be applied in this order:

1. concat admissibility
2. concat execution
3. delivery admissibility / delivery result
4. terminal rendering

Why:

- rendering cannot determine whether concat was admissible
- delivery policy cannot determine whether staged media were concat-compatible
- concat admissibility cannot determine how terminal text should be phrased

## Explicit Non-Equivalences

The implementation should preserve these non-equivalences:

- `mixed_resolution`
  is not a delivery policy problem
- `telegram_upload_too_large`
  is not a concat incompatibility
- `concat succeeded, upload failed`
  is not a concat failure
- `warning-style user text`
  is not a distinct terminal outcome class

These seem obvious, but they are exactly where systems often drift back into incoherence.

## Recommended Field Ownership

### Concat Admissibility Layer

Owns fields like:

- `concat_policy`
- `video_concat_manifest`
- `video_concat_compatibility`

### Delivery Layer

Owns fields like:

- delivery mode
- artifact path
- artifact size
- Telegram delivery result

### Rendering Layer

Owns fields like:

- user-facing text
- log summary text
- compact reason formatting

## Terminal Outcome Mapping Discipline

`TerminalOutcomeResult` should be authored before rendering.

That means:

- concat incompatibility -> terminal rejection
- concat execution failure -> transformation failure
- artifact created but upload failed -> delivery failure

Only after that should rendering decide:

- whether to say `⚠️` or `❌`
- whether to include one supporting line

## V1 Delivery Policy Recommendation

For the first `video_concat_download` implementation, delivery policy should stay simple:

- one composite artifact
- one Telegram delivery attempt
- no automatic split or multi-part fallback

This keeps delivery policy from quietly becoming a second transformation branch.

## Why This Matters Before Code

Without this partition, the first implementation may still appear structured while hiding the old
interleaving in different names.

This document prevents that by making explicit:

- which layer decides admissibility
- which layer decides deliverability
- which layer only renders meaning already decided elsewhere

## Tests Implied By This Partition

The first implementation should test:

1. concat incompatibility does not become delivery failure
2. upload failure after composite creation does not become concat failure
3. rendering helpers do not invent new terminal classes
4. delivery-size rejection uses delivery-policy wording, not compatibility wording

## Why This Is The Next Correct PDA Move

The object chain is now explicit enough that the remaining risk is not missing objects, but
policy-layer confusion.

So the correct next PDA move is to partition those policy layers before implementation starts.
