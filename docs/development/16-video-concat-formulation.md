# Video Concat Formulation

## Purpose

This document applies the existing PDA framework to the proposed video-concat feature.

It treats video concat as a distinct task/branch family, not as a minor extension of audio concat.

The goal is to localize the live ambiguity before implementation so that:

- branch identity remains explicit
- admissibility is not confused with execution convenience
- terminal semantics remain coherent
- the system does not silently collapse into "download N videos, then do something with ffmpeg"

## Governing Ambiguity

The live ambiguity is not:

- whether FFmpeg can concatenate files

The live ambiguity is:

- what exactly counts as the same requested output when multiple playlist items become one artifact
- when concat is admissible versus when normalization/re-encode is required
- whether failure to concatenate is a branch failure, a transformation failure, or an inadmissible branch selection
- how a multi-item playlist request becomes a single delivered artifact without losing task meaning

If this is not made explicit, video concat will feel like an accidental side path rather than a coherent task family.

## Task Class

Video concat should be treated as its own media-acquisition task class:

- `playlist_concat_video`

It is not equivalent to:

- ordinary playlist video download
- split-video delivery
- cache replay of individual items
- audio concat with a different media extension

Its requested output is:

- one ordered composite artifact derived from multiple playlist items

## Branch Family

The branch family should be explicit:

- `video_concat_download`

This branch family differs from ordinary `video_download` because:

- scope requested is multi-item
- scope satisfied is one composite artifact, not N delivered artifacts
- transformation is constitutive, not incidental
- admissibility depends on cross-item compatibility, not only per-item download feasibility

## Branch Identity

A video-concat branch should minimally be understood as:

- delivery intent
  single Telegram video/document artifact
- media intent
  video
- task scope
  playlist range or selected ordered subset
- transformation intent
  concatenate selected items into one composite result
- ordering policy
  original range order or explicit reverse order
- normalization policy
  direct concat if compatible, else normalization/re-encode if allowed
- execution source
  fresh acquisition, partially cached staged inputs, or inadmissible

## Authorities

### User Authority

Legitimate user inputs:

- explicit concat command
- selected playlist range
- explicit reverse ordering
- explicit naming intent
- possibly future normalization policy flags

### Persisted User Policy

Should have limited influence at first.

Allowed:

- send-as-file preference if it only affects Telegram delivery mode

Should not silently decide branch identity:

- saved `/format`
- ambient concat-unrelated download defaults

Video concat is a specialized task and should remain task-led.

### Source/Transformation Authority

Source-platform and FFmpeg constraints may:

- prune inadmissible executions
- force normalization policy choice if that policy was pre-authorized

They should not silently redefine the branch into ordinary playlist download.

## Forced Structure

These are structurally required for a coherent first implementation:

- multiple playlist items must be selected explicitly
- selected items must be materialized locally before concat
- order of the selected items must be explicit
- concat must produce one final composite artifact
- terminal outcome must reflect one requested composite result, not N independent deliveries

## Contingent Policy

These are implementation choices, not necessities:

- YouTube-only initial scope
- maximum selected item count
- whether re-encode is allowed in v1
- whether concat output is always MP4
- whether delivery is `send_video` or `send_document` in some edge cases
- whether staging reuses partial cache or always redownloads

These should remain explicit policy, not hidden assumptions.

## Main Distinction: Direct Concat vs Normalized Concat

This is the central branch-internal ambiguity.

### Direct Concat

Admissible when staged items are already compatible enough for FFmpeg concat without prior normalization.

Advantages:

- faster
- lower CPU cost
- less generational loss

Risk:

- fragile
- compatibility failures may be common across playlist items from heterogeneous sources

### Normalized Concat

Admissible when the system is authorized to re-encode staged items into a shared intermediate format before concat.

Advantages:

- more robust
- clearer artifact semantics

Costs:

- much slower
- larger CPU/memory burden
- more complex failure surface

## PDA Recommendation For V1

V1 should not silently oscillate between these.

Choose one explicit initial policy:

- either `direct_concat_only`
- or `normalize_then_concat`

The more coherent first choice is:

- `direct_concat_only`

Why:

- it localizes the first admissibility boundary clearly
- it avoids hiding expensive transformation policy inside a "simple" feature
- it gives a clean failure class when the selected range is incompatible

If later needed, normalized concat can be introduced as a second explicit policy branch.

## Admissibility Rules

For a first coherent implementation, a video-concat task should be admissible only when:

- selected range contains at least 2 items
- each selected item can be acquired
- each selected item resolves to a local artifact of the expected media class
- all artifacts satisfy the chosen concat policy
- final expected size/delivery mode remains within acceptable Telegram constraints or explicit fallback policy

If any of these fail, the branch should become:

- determinate rejection before transformation, or
- acquisition/transformation failure after branch selection

What should not happen:

- silently degrade into ordinary playlist download
- silently deliver only the first successful item as if concat succeeded

## Precedence Rules

### 1. Explicit Concat Intent

If the user selected concat, concat remains the branch family unless it becomes inadmissible.

### 2. Explicit Ordering Over Ambient Ordering

If the user requested reverse order, that ordering governs concat input order.

### 3. Admissibility Prunes, It Does Not Re-Specify

If direct concat is inadmissible, the system must either:

- fail with a clear concat-specific reason, or
- move to an explicitly authorized normalization policy

It should not silently become ordinary multi-item delivery.

### 4. Naming Is Downstream, Not Branch-Defining

Output naming affects reporting and final artifact naming, but not branch identity.

## Terminal Semantics

A coherent video-concat terminal outcome should be framed around one requested composite artifact.

### Full Success

- one composite artifact requested
- one composite artifact delivered

### Partial Success

This should be rare and carefully defined.

Examples:

- composite artifact built, but Telegram delivery failed after local artifact success
- some staged items acquired, but composite artifact was not valid

For V1, most concat failures should probably be plain failure, not partial success.

### Failure Classes

Useful distinct failure loci:

- `selection_inadmissible`
- `acquisition_failed`
- `normalization_failed`
- `concat_failed`
- `delivery_failed`

## Cache Semantics

Video concat should not inherit ordinary per-item playlist cache semantics by default.

Two distinct cache questions exist:

- staged item cache
- final composite artifact cache

These should remain separate.

For V1, the coherent policy is:

- do not promise final composite cache reuse yet
- if staging reuses cache, treat that as internal execution support, not as branch identity change

## Cleanup Policy

Cleanup should follow outcome meaning.

Suggested initial policy:

- on full success: normal cleanup of staged intermediates, optionally preserve final artifact if rename/reuse is supported
- on concat failure: preserve staged artifacts only if they materially help debug/retry
- on delivery failure after final artifact success: preserve final artifact for resend/rename/retry

## Non-Goals For V1

V1 should not try to solve all of these at once:

- subtitles across concatenated items
- heterogeneous codecs/containers with silent normalization
- rich final composite metadata synthesis
- cross-platform/source generalized concat
- aggressive final-artifact caching
- live stream concat

## Most Coherent First Command Surface

The cleaner long-term UX is:

- `/concat` = concat family
- `/concat --audio-only` = audio concat
- `/concat` with no media-type override = video concat

While video concat is not implemented, the command surface can still be coherent if:

- `/concat --audio-only ...` is live
- plain `/concat ...` returns a clear "video concat not implemented yet" response

That preserves future branch identity without forcing misleading temporary commands like `/vconcat`.

## Suggested Implementation Order

1. define `video_concat_download` branch family explicitly
2. define a narrow admissibility policy such as `direct_concat_only`
3. stage selected playlist items to local compatible artifacts
4. attempt concat under that explicit policy
5. emit concat-specific terminal outcomes
6. only then consider normalized concat as a second policy branch

## Why This Matters

Without this formulation, video concat will likely inherit the wrong semantics from:

- ordinary playlist video download
- split-video logic
- audio concat

Those similarities are real but not decisive.

Video concat is its own branch family because:

- one requested result is synthesized from many inputs
- transformation is constitutive of success
- admissibility depends on cross-item relations rather than independent item success

That is the real PDA center of gravity for the feature.
