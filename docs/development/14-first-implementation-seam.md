# First Implementation Seam

## Purpose

This document identifies the first implementation seam that best converts the current PDA work into low-risk architectural change.

The question is no longer primarily conceptual.
It is:

- where should explicit implementation begin so that coherence improves materially without requiring a full rewrite

## Decision

The best first implementation seam is:

- introduce a real `BranchSelectionResult` at the `S3 -> S4` boundary

This means making branch selection return an explicit object before orchestration continues into download/direct-link/cache-reuse execution.

## Why This Seam Wins

Among the major candidates:

- real `Task` object
- real `BranchSelectionResult`
- real `TerminalOutcomeResult`

the branch-selection seam is the strongest first move because it is:

- high leverage
- relatively localizable
- upstream of most downstream ambiguity
- less invasive than a full `Task` rollout
- more semantics-critical than terminalization alone

## Why Not Start With `Task`

A real `Task` object is probably the right long-term center of gravity.
But it is not the best first move because:

- it touches nearly every layer
- it forces broad signature and context changes
- it risks becoming a large refactor before branch and terminal semantics are operationally stabilized

So `Task` is the right primary runtime object, but not the safest first implementation seam.

## Why Not Start With `TerminalOutcomeResult`

Terminal outcome explicitness is important, but as a first implementation seam it is slightly downstream of the highest incoherence source.

If branch identity is still implicit, then terminalization still has to interpret:

- raw flags
- reconstructed branch provenance
- ambiguous execution intent

That means terminalization improves most after branch-selection explicitness exists.

So terminal outcome should likely be second, not first.

## Why Branch Selection Is The Highest-Leverage Surface

Branch selection is where the following currently collide:

- explicit callback choice
- saved defaults
- cache reuse
- direct-link mode
- task scope
- execution-source meaning
- access-feasibility pruning

This is the main place where:

- user intent becomes execution commitment

If this surface stays implicit, later layers continue to inherit ambiguity even when they are internally correct.

## What The Seam Should Produce

The first implementation seam should produce a real object conforming conceptually to:

- [`09-branch-selection-result-model.md`](./09-branch-selection-result-model.md)

At minimum, the first implementation version should carry:

- `branch_family`
- `selected_by`
- `task_scope`
- `delivery_intent`
- `media_intent`
- `quality_intent`
- `execution_source`
- `downstream_constraints`
- `provenance`

It does not need the final ideal shape on day one.
It needs enough explicitness to stop downstream code from guessing what branch was chosen.

## Where It Should Be Introduced

The most natural code surface is the current `S3 -> S4` area:

- [`URL_PARSERS/video_extractor.py`](./../../URL_PARSERS/video_extractor.py)
- [`DOWN_AND_UP/always_ask_menu.py`](./../../DOWN_AND_UP/always_ask_menu.py)

Concretely, the first seam should likely sit where the system currently decides between:

- saved-format direct download
- callback-selected audio path
- callback-selected video path
- subtitles-only path
- direct-link path
- cache-reuse path

That is the point where one explicit object can replace several implicit combinations of:

- `quality_key`
- `format_override`
- callback data
- saved defaults
- mode flags

## What Should Not Happen In The First Move

The first move should not attempt all of the following at once:

- introduce a full `Task` object
- refactor all orchestrators
- centralize all terminal semantics
- rewrite the entire menu system

That would raise risk and blur the seam.

The first move should be deliberately narrow:

- make branch selection explicit
- keep downstream call structure mostly intact
- adapt downstream consumers incrementally

## Transition Contract For The Seam

The first implementation seam should preserve this contract:

- input: metadata-resolved context plus current-task authority inputs
- output: explicit `BranchSelectionResult`
- no silent collapse of branch meaning into raw format strings
- no hidden precedence between callback choice and saved default

That is the minimum anti-incoherence contract.

## Immediate Benefits

If this seam is implemented first, the likely immediate benefits are:

- downstream code stops inferring branch meaning from loose flags
- callback-selected intent becomes explicit and portable
- saved-default behavior becomes explicit rather than ambient
- cache-reuse semantics become easier to distinguish from fresh acquisition
- terminalization later becomes easier to model because branch provenance is preserved

## Risk Profile

This seam has moderate conceptual leverage with relatively bounded implementation blast radius.

Risk is lower because:

- it can be introduced at one transition boundary
- it can coexist temporarily with legacy parameters
- it improves meaning before forcing broad object-model adoption

Risk is not zero because:

- `always_ask_menu.py` is dense and highly interleaved
- some branch logic is also split into `video_extractor.py`

But relative to the other candidates, this is still the best ratio of leverage to disruption.

## Suggested Order After This Seam

If the branch-selection seam is implemented successfully, the likely next order is:

1. implement `BranchSelectionResult`
2. implement `TerminalOutcomeResult`
3. introduce a lightweight `Task` container that owns both

That order respects the current interleaving structure better than starting with a large `Task` abstraction.

## Recomposition

Recomposed:

the first implementation seam should be the point where branch selection becomes an explicit returned object.

That is the smallest real code move that most directly attacks the system's current incoherence.

## Related Documents

- [`Branch Selection Result Implementation Sketch`](./15-branch-selection-result-implementation-sketch.md): smallest viable first patch for introducing `BranchSelectionResult`
