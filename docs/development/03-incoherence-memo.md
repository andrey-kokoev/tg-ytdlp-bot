# Incoherence Memo

## Claim

There is a real design incoherence in `tg-ytdlp-bot`.

It is not that the system lacks functionality.
It is that the system's operative unit is a **stateful task**, while large parts of the implementation are still organized as if the operative unit were an isolated **Telegram message handler**.

This mismatch creates avoidable ambiguity, edge-case fragility, and recurring control-flow surprises.

## Core Incoherence

The system behaves like workflow software but is still substantially structured like handler-first bot code.

That means:

- continuation is really determined by task state, not by the current update alone
- but much of the code is written as if each handler can decide locally from the current message/callback

This is the architectural tension behind many of the system's recurring problems.

## Symptoms

### 1. Message Object Overloading

The system overloads the meaning of a Telegram message.

A message may function as:

- a command
- a URL-bearing intent
- a state transition trigger
- a reply anchor
- a callback parent
- a file transport container
- a reusable cache reference

These are not the same kind of object.
Treating them as one object class hides important distinctions about authority, state, and continuation.

### 2. State Is Real but Weakly Modeled

The system already has a real per-user state store under `users/<user_id>/...`.

That state influences:

- cookies
- saved format
- args
- tags
- keyboard mode
- language
- download directories
- partial task artifacts
- some cache and retry behavior

So state is not optional or secondary.
But it is mostly represented as scattered files with implicit contracts rather than as an explicit state model.

This creates a mismatch:

- state has high authority
- state structure has low explicitness

### 3. Continuation Authority Is Distributed

The winner at each branch point is not always the same authority.

Depending on the stage, continuation may be determined by:

- explicit user callback
- explicit command
- saved user preference
- existing cookie state
- cache availability
- source-platform feasibility
- proxy/cookie fallback policy
- Telegram upload constraints

That distribution is normal for this kind of system.
What is incoherent is that the precedence among these authorities is spread across handlers and helper functions rather than expressed as one shared model.

### 4. Terminal Semantics Are Under-Modeled

The system has multiple materially distinct terminal states:

- success with fresh acquisition
- success with cache reuse
- partial success
- failure before acquisition
- failure after acquisition but before upload
- failure after upload attempt begins

Those are not cosmetic differences.
They affect user-visible behavior, retry semantics, logging meaning, and future continuation.

But the system does not yet have a single explicit task-state model that makes these terminal states first-class.

### 5. Flow Logic and Policy Logic Interleave

Routing logic, fallback policy, state lookup, extraction feasibility, and delivery semantics frequently interleave in the same operational surfaces.

This makes it harder to answer simple architectural questions like:

- why did this path win
- who had authority to choose it
- was this a failure of policy, state, source platform, or delivery

The result is code that often works but is harder to reason about than it should be.

## What The System Actually Is

The system is not best described as "a Telegram bot with download handlers."

It is better described as:

- a multi-authority intent-to-artifact workflow system
- mediated through Telegram
- with persistent per-user state
- external extractor dependency
- local artifact materialization
- and multiple terminal outcome classes

Once stated that way, many current implementation choices look less coherent because they were shaped around handler locality rather than workflow locality.

## Consequence

The main consequence is not abstract elegance loss.
It is practical debugging and change-cost inflation.

When the system is handler-first in structure but workflow-first in reality:

- bugs appear as local oddities but originate in cross-stage state interactions
- fixes tend to patch symptoms at the handler level
- precedence mistakes recur
- partial-success semantics remain muddy
- duplicated or contradictory behavior becomes easier to introduce

## Non-Claim

This memo does not claim the system is unusable or unsalvageable.

It claims something narrower:

- the current implementation center of gravity does not match the system's real determination structure

That is a design incoherence, not a total failure.

## Most Likely Corrective Direction

The most likely corrective direction is not an immediate rewrite.

It is to make the workflow/task model explicit first:

- define the task as the primary unit
- define task states and transition classes
- define authority precedence at each transition class
- define terminal outcomes explicitly
- define which per-user state is authoritative and when

Only after that should larger refactoring decisions be made.

## Short Form

The shortest accurate statement is:

`tg-ytdlp-bot` behaves like stateful workflow software but is still too organized like message-local bot code.

That mismatch is the main architectural incoherence.
