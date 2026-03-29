# Task Model

## Purpose

This document defines the task as the primary unit of execution in `tg-ytdlp-bot`.

The goal is to replace the implicit handler-first picture with an explicit task-level formulation that makes the following visible:

- what a task is
- what identifies a task
- which states a task can occupy
- which authorities can move it
- which precedence rules apply at each transition class
- which terminal outcomes exist

This is the next PDA descent layer after system formulation because the live ambiguity is no longer mainly about system boundary. It is about task determination.

## Governing Ambiguity

The governing ambiguity at this layer is:

- is the operative unit of continuation a Telegram update, or a stateful task that may span multiple updates and local artifacts?

For this system, the answer is:

- the operative unit is the task

A single task may involve:

- an inbound message
- one or more callback queries
- one or more local state reads
- one or more extraction attempts
- optional retries or fallbacks
- local artifact creation
- final Telegram delivery or failure

So a Telegram update is an event in task evolution, not necessarily the task itself.

## Task Definition

A task is a bounded execution attempt to resolve a user-originated intent into one of the system's admissible terminal outcomes.

A task begins when an inbound update is classified into an execution class that implies continuation rather than immediate inert rejection.

A task ends when the system reaches a terminal outcome for that execution attempt.

## Task Identity

At the conceptual level, a task is identified by the combination of:

- initiating authority
  usually a specific user via Telegram
- initiating intent
  command, URL/media request, cookie upload, callback continuation, or direct-link request
- task scope
  the concrete object of work such as a URL, playlist range, uploaded document, or callback-selected branch
- continuation context
  relevant per-user state and in-flight task state needed to determine admissible next steps

In implementation, this identity is distributed across:

- Telegram message/callback objects
- user ID
- local files under `users/<user_id>/...`
- cached metadata and artifacts
- in-memory active-download/task context

So task identity is real, but currently composite rather than centrally modeled.

## What Is Not A Task

The following are not sufficient by themselves to count as the primary unit:

- a single Telegram message
- a single handler invocation
- a single local file
- a single yt-dlp call
- a single upload call

Each of those may be part of a task, but none is the full unit of continuation.

## Task Classes

The current system appears to have at least these task classes.

### 1. Immediate Command Task

Examples:

- `/clean`
- `/settings`
- `/help`
- keyboard-mode commands

These may terminate without remote acquisition.

### 2. Upload-State Mutation Task

Examples:

- upload `cookie.txt`
- save settings-like user artifacts

These mutate local user state and terminate without source-platform acquisition.

### 3. Media-Acquisition Task

Examples:

- send a YouTube URL
- send an X/Twitter URL
- send a TikTok URL

These usually require extraction, optional menu selection, download, post-processing, and delivery.

### 4. Callback-Continuation Task

Examples:

- choose `mp3`
- choose `480p`
- choose subtitles-only
- choose a direct-link branch

These are best understood as continuations of media tasks rather than isolated tasks, unless the system intentionally reifies them as new tasks.

### 5. Cache-Reuse Task

A task may resolve primarily through cached Telegram message reuse rather than fresh acquisition.

This is operationally distinct from fresh download even if user-visible output looks similar.

## Task States

The task state model below is the current best closed formulation at this layer.

### S0. Inbound Event

A Telegram update exists, but no execution class has yet been assigned.

### S1. Routed Task

The system has determined the execution class:

- immediate command
- state mutation
- media task
- callback continuation
- rejection

### S2. Context-Resolved Task

The system has enough user state and task context to know the admissible branches.

Examples:

- saved format found or not
- cookie state found or not
- callback branch decoded
- cache availability known or not

### S3. Metadata-Resolved Task

The system has enough source-platform information to know the concrete acquisition options or to reject/redirect the task.

Examples:

- format list known
- playlist range resolved
- direct-link path available
- extraction impossible

### S4. Branch-Selected Task

One concrete execution branch has been selected.

Examples:

- immediate command response
- upload-state mutation
- direct download with saved format
- callback-selected `mp3`
- callback-selected `480p`
- cached artifact reuse

### S5. Material Acquisition

The system is acquiring or reusing bytes/artifacts.

Examples:

- yt-dlp download
- gallery-dl fetch
- cached Telegram message reuse lookup

### S6. Local Artifact Available

A concrete deliverable or reusable artifact exists.

Examples:

- downloaded media file
- converted mp3
- split video parts
- cached Telegram message IDs judged valid

### S7. Delivery Attempt

The system is attempting to send the result back through Telegram.

### S8. Terminal Outcome

The task has ended in one of the terminal classes defined below.

## State Transition Classes

The important transition classes are:

- routing transition
- context-resolution transition
- metadata-resolution transition
- branch-selection transition
- acquisition transition
- artifact-selection transition
- delivery transition
- terminalization transition

These transition classes matter more than individual functions because precedence and authority differ by class.

## Authorities By Transition Class

### Routing Transition

Primary authorities:

- Telegram update type
- router logic
- explicit command syntax

### Context-Resolution Transition

Primary authorities:

- per-user persisted state
- active task/session state
- explicit callback data if present

### Metadata-Resolution Transition

Primary authorities:

- source-platform responses
- extractor behavior
- access enablers such as cookies, proxies, PO tokens

### Branch-Selection Transition

Primary authorities:

- explicit user callback if present
- saved user preference if no more specific task-level choice exists
- cache availability if semantically admissible

### Delivery Transition

Primary authorities:

- existence of a concrete local or cached deliverable
- Telegram upload/delivery acceptance

## Precedence By Transition Class

### Routing Transition Precedence

- bot/outgoing-message suppression precedes normal user-text routing
- explicit command classification precedes generic URL interpretation
- upload/document classification precedes generic text treatment when the update is a file-bearing update

### Context-Resolution Precedence

- explicit in-flight callback choice precedes ambient saved preference for the current task
- task-specific context precedes broad per-user defaults
- relevant persisted state precedes fallback assumptions of absence

### Metadata-Resolution Precedence

- source-platform feasibility precedes local preference when the preferred path is infeasible
- valid user cookie precedes shared fallback cookie source for the current task
- shared fallback cookie source precedes no-cookie attempt only where fallback policy allows it
- no-cookie operation is admissible only when the source platform/content permits it

### Branch-Selection Precedence

- explicit task-level user choice precedes saved default
- semantically valid cache reuse may precede fresh acquisition
- a direct-link branch and a media-delivery branch are distinct branches; neither should silently collapse into the other

### Delivery Precedence

- successful Telegram delivery precedes mere local acquisition in determining success
- partial delivery precedes total-failure classification when some requested outputs were delivered

## Terminal Outcomes

The current system needs the following terminal distinctions.

### T1. Determinate Rejection

The task is rejected before successful acquisition because the path is inadmissible.

Examples:

- malformed input
- blocked content/user
- unsupported path
- explicit policy rejection

### T2. Immediate Success

The task completes without remote acquisition.

Examples:

- settings/help/clean response
- cookie upload saved successfully

### T3. Acquisition Success With Delivery Success

The system acquired or reused what it needed and successfully delivered the result via Telegram.

### T4. Acquisition Success With Delivery Failure

The system produced a valid local or cached deliverable but failed to deliver it through Telegram.

This is not the same as download failure.

### T5. Partial Success

Some but not all requested outputs were successfully delivered.

This is especially relevant for:

- playlist/range tasks
- split outputs
- multi-item downloads

### T6. Acquisition Failure

The system never produced a valid deliverable because extraction, access strategy, download, or post-processing failed.

## Non-Inert Distinctions At This Layer

The following distinctions remain decision-relevant at the task layer:

- whether a callback continues an existing task or implicitly creates a new one
- whether cache reuse is terminally equivalent to fresh acquisition
- whether local artifact creation without upload counts as success, partial success, or failure
- whether user preference is a hard constraint or defeasible default
- whether a retry remains inside the same task or constitutes a new task attempt

These should remain explicit until the system chooses them.

## Interleaving Notice

The main interleaving at the task layer is:

- update-level events
- persistent user state
- source-platform feasibility
- task-specific explicit user choice
- delivery semantics

These do not all speak at once or with equal authority.
They speak at different transition classes.

So the right formulation is not "many things matter."
It is:

- different authorities govern different transitions, and incoherence appears when those transitions are collapsed.

## Recomposition

Recomposed at the task layer:

`tg-ytdlp-bot` should be understood as executing stateful user tasks that evolve across multiple updates, state reads, acquisition steps, and delivery attempts, rather than as merely reacting to isolated messages.

That is the primary formulation needed to reason coherently about:

- cookies
- callbacks
- cache reuse
- partial completion
- retries
- delivery success

## What This Enables Next

Once this task model is accepted, the next natural move is either:

- define an explicit task-state machine for the current implementation, or
- audit current handlers/modules by asking which task state and transition class each one actually governs

That would convert the present architectural tension into a concrete refactoring map instead of a vague concern.
