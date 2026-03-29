# System Formulation

## Purpose

This document describes `tg-ytdlp-bot` as a system rather than as a code walkthrough.

The aim is to make the active determination structure explicit:

- what the system is
- where its boundary is
- what is structurally necessary
- what is implementation policy
- which choices take precedence over others
- what state exists and who owns it
- where failures occur and how they propagate

This is intended to be a more PDA-aligned formulation than a pure runtime flow description.

## Governing Ambiguity

The governing ambiguity for this system is not "how does the code run" in the generic sense.
It is:

- what is structurally required for a Telegram-mediated media acquisition task to be determinately executable
- what is merely contingent implementation policy in this repository
- where authority over continuation changes hands during the task
- which residual policy choices still materially change admissible continuation or user-visible outcome

This matters because a smooth operational description can still hide decisive arbitrariness.
For this system, the live ambiguity sits mainly in:

- authority boundaries
- state ownership
- precedence among competing continuation paths
- stage-local failure meaning

The goal of this formulation is therefore not to narrate execution, but to expose the determination structure of execution.

## System Boundary

`tg-ytdlp-bot` is a Telegram-mediated media acquisition and delivery system.

Its boundary includes:

- the Telegram bot session
- the Python process and its handler/orchestration logic
- local per-user state under `users/<user_id>/...`
- local temp download and post-processing artifacts
- helper services used by the deployment, such as the PO token provider and internal cookie server
- optional cache/database services used for reuse, stats, and policy enforcement

Its boundary does not include:

- Telegram itself as a platform
- source media platforms such as YouTube, X/Twitter, TikTok, Instagram, or Facebook
- the user’s browser or desktop environment
- the intrinsic correctness or availability of third-party extractor targets

## Primary Function

The primary function of the system is:

- accept a Telegram-originated user intent to obtain media or metadata from a supported source
- resolve that intent into a concrete acquisition path
- acquire or derive the requested artifact
- deliver the resulting artifact or a determinate failure back through Telegram

The system is therefore not merely a downloader and not merely a Telegram interface.
It is an intent-to-artifact mediation system with local state, extraction policy, and upload policy.

## Actors

The system contains or depends on the following actors:

- **User**: initiates commands, URLs, uploads, and callbacks
- **Telegram**: external message transport and delivery platform
- **Pyrogram Client**: active Telegram session endpoint
- **Router/Handlers**: transform inbound updates into admissible execution paths
- **Extraction Layer**: obtains metadata, formats, and direct acquisition paths via `yt-dlp` or other engines
- **Download Orchestrator**: executes the chosen acquisition path
- **Post-Processing Layer**: merges, converts, tags, thumbnails, splits, and normalizes artifacts
- **Upload Layer**: sends text, audio, video, or documents back to Telegram
- **Filesystem State Store**: per-user settings, cookie files, temporary downloads, converted outputs
- **Cache/Database Layer**: optional persistence for cached results, stats, and enforcement
- **Helper Services**: PO token provider, internal cookie source server, proxy infrastructure
- **External Source Platforms**: actual origin of metadata and media bytes

## Authorities

The system is multi-authority. These authorities must remain distinct.

- **User authority**: supplies intent, uploads cookies, chooses qualities, and sets preferences where the interface allows it.
- **Router authority**: decides which internal execution class an inbound update belongs to.
- **Policy authority**: determines defaults and fallback behavior when the user has not selected a concrete path.
- **Source-platform authority**: determines whether metadata/media can actually be extracted or downloaded.
- **Telegram authority**: determines delivery semantics for inbound updates, callbacks, and outbound media acceptance.
- **Local-state authority**: constrains continuation through persisted settings, cookies, cache entries, and task artifacts.

The system is easiest to misdescribe when these are collapsed into one "bot decides" story.
It does not. Continuation is co-determined by multiple authorities.

## External Interface

The system exposes its behavior primarily through Telegram interactions:

- text commands
- plain URL messages
- document uploads such as `cookie.txt`
- callback queries from inline buttons
- final outbound text, menus, audio, video, and file messages

The web dashboard is a secondary interface for monitoring and administration, not the primary media acquisition interface.

## Core Invariants

These invariants characterize the current system.

- A user task begins from a Telegram update.
- A media delivery task must resolve to a concrete local or cached artifact before final Telegram media upload.
- Per-user settings and task context are materially stateful, not purely derived from the current message.
- A task may branch through metadata discovery before the system knows the concrete download path.
- The system may fail after partial success, for example after download but before upload.
- A user-visible success or failure must ultimately be expressed back through Telegram, unless the process crashes or connectivity is lost before response.

## State Transitions

At the system level, a task moves through a small number of state classes.

1. **Inbound intent**
   A Telegram update has arrived, but no concrete continuation has yet been selected.
2. **Routed intent**
   The update has been classified as command, upload, URL/media task, callback continuation, or rejection.
3. **Resolved acquisition path**
   The system has enough metadata and policy/context to know which branch is admissible.
4. **Material acquisition**
   The system is attempting to obtain bytes or reusable cached artifacts.
5. **Local artifact state**
   A concrete local or cached artifact exists for possible delivery.
6. **Delivery attempt**
   The artifact or result message is being sent back through Telegram.
7. **Terminal state**
   The task ends in success, determinate rejection, partial failure, or unrecoverable failure.

These states are more important than individual function names because they identify where the system actually changes determination class.

## Forced Structure

These are structural facts of the current system rather than optional preferences.

- Telegram-originated updates are the entry condition for normal user tasks.
- The router must classify an inbound update before execution can proceed.
- URL/media tasks require source inspection or direct extraction before a final artifact can be delivered.
- User-selected quality in “Always Ask” mode requires a callback round trip through Telegram.
- Final Telegram media delivery operates on a completed local or cached artifact in the current design.
- Post-processing, when needed, operates on local files and yields local files.
- The system is dependent on third-party source platform behavior for successful extraction and download.
- Authority crosses system boundaries multiple times during one task: Telegram inbound, source-platform extraction/download, Telegram outbound.

## Contingent Policy

These are implementation choices, not unavoidable truths of the problem class.

- Per-user persistent state is file-backed under `users/<user_id>/...`.
- User cookies are stored as `users/<user_id>/cookie.txt`.
- Format preference, args, keyboard mode, language, and similar settings are stored in simple local files.
- Quality selection is mainly implemented through Telegram inline menus.
- The system prefers local orchestration with Python, `yt-dlp`, and `ffmpeg` rather than delegating work to an external job system.
- Shared fallback cookies may exist alongside user-provided cookies.
- The deployment may use helper services such as a PO token provider and internal cookie webserver.
- Caching may be backed by Firebase-derived local cache or local JSON-backed state depending on deployment mode.

## Residual Policy

These are live choices that still materially determine behavior and therefore must remain explicit.

- whether to ask the user for quality or use a saved format directly
- whether to use user cookies, shared cookies, or no cookies
- whether to use proxy or direct access
- whether to send as media or as file where both are admissible
- whether to use cached media/message IDs or perform a fresh acquisition
- whether subtitles, metadata, thumbnails, or split behavior are applied for a given task

These are not inert stylistic differences. They alter admissible continuation and user-visible outcome.

## Localized Ambiguities Still Live

The following ambiguities are still live in the current system formulation and should be treated as explicit decision surfaces rather than hidden assumptions.

- exact cache-validity criteria for reusing prior Telegram message IDs
- exact retry ordering when cookie, proxy, and source-platform failures interact
- when a fallback path should be considered equivalent to the primary path versus merely acceptable
- what counts as the correct terminal semantics for partial success in multi-item tasks
- which user preferences should be treated as hard constraints versus soft preferences

These are localized ambiguities, not reasons to discard the whole formulation.
They identify where further descent would still change execution-relevant determination.

## Precedence Rules

The following precedence relations are part of the current operational determination structure.

There is an important interleaving in this system:

- **authority interleaving**
  User intent, router classification, persisted user state, source-platform constraints, and Telegram delivery constraints all participate in continuation
- **state interleaving**
  Routing-state precedence, acquisition-state precedence, and delivery-state precedence are not the same thing

If these are flattened into one undifferentiated "precedence" list, concealed arbitrariness re-enters the formulation.
So precedence is separated below by transition class.

### Routing-State Precedence

These rules determine what the inbound update becomes before acquisition starts.

- Bot/outgoing messages are ignored before normal private-text routing.
- Explicit command interpretation takes precedence over generic URL handling.
- Cookie/document upload classification takes precedence over treating the same update as generic text or URL input.
- Callback-originated continuation takes precedence over saved general defaults for the current in-flight task because the callback is the more specific user act.

### Acquisition-Path Precedence

These rules determine which admissible media-acquisition path is chosen once the task is routed.

- If the user is in “Always Ask” mode, metadata discovery and callback selection take precedence over immediate direct download.
- If a concrete callback-selected format exists for the current task, it overrides a saved general format preference for that task.
- A task-specific explicit format override takes precedence over ambient user preference.
- Cached artifact reuse, when valid and semantically compatible with the current task, can take precedence over fresh acquisition.

### Access-Strategy Precedence

These rules determine how the system tries to make the chosen acquisition path executable.

- For actual downloads, a user-provided cookie is preferred over shared fallback cookie sources.
- Shared cookie sources are fallback mechanisms rather than the primary user-state source.
- No-cookie operation remains admissible only where the selected content and source platform allow it.
- Proxy use is conditional and subordinate to the need to make acquisition executable; it is not a universal first step.
- Source-platform refusal or extractor refusal can override local preference entirely by making a nominal path inadmissible.

### Artifact-Selection Precedence

These rules determine which local artifact counts as the deliverable once acquisition has succeeded enough to produce bytes.

- If post-processing generates the final deliverable, that post-processed artifact takes precedence over the raw downloaded artifact for upload.
- If cached Telegram message reuse is valid for the current task semantics, cached reuse can take precedence over re-uploading a locally available artifact.
- The upload layer sends the concrete artifact selected by orchestration, not the remote source stream itself.

### Delivery-State Precedence

These rules determine how terminal semantics are assigned after artifact selection.

- Successful Telegram upload takes precedence over merely having obtained local media bytes when determining task success.
- Partial completion takes precedence over simple failure when some requested items were delivered and some were not.
- Stage-localized failure reporting takes precedence over generic "download failed" narration when the failure locus is known.

## State Model

The active system state can be described in the following classes.

### User State

Per-user persistent state includes:

- cookie file
- saved format
- saved yt-dlp args
- tags
- keyboard mode
- language
- settings affecting subtitles, proxy, format selection, and delivery behavior

### Task State

Per-task transient state includes:

- original input URL or command payload
- extracted metadata
- selected quality/mode
- active temp directory
- intermediate downloaded files
- thumbnails and transformed outputs
- progress/status messages

### Cache State

Reusable state may include:

- cached Telegram message IDs for prior uploads
- cached playlist/video resolution
- Firebase-derived local cache or local JSON persistence
- remembered outcomes for cookie success on some domains/tasks

### Session State

Process/session state includes:

- active downloads
- callback handling context
- live client session to Telegram
- helper service connectivity

## Failure Domains

The major failure domains are:

- Telegram inbound/update delivery
- handler routing and internal control flow
- local state corruption or missing files
- cookie invalidity or cookie precedence mistakes
- extractor failure on source platforms
- anti-bot or login requirements on source platforms
- proxy or helper-service failure
- local download/storage/post-processing failure
- Telegram upload failure after successful local acquisition

## Failure Propagation

The system does not have a single failure mode. Failures propagate according to stage.

- A routing failure prevents task initiation.
- A metadata extraction failure prevents menu formation or direct acquisition.
- A callback-stage failure prevents the selected branch from starting.
- A download failure may occur after the system has already emitted progress or menu messages.
- A post-processing failure may occur after successful remote acquisition.
- An upload failure may occur after successful local artifact creation.

Therefore, “task failed” does not identify the failure locus by itself. A determinate formulation must preserve stage locality.

## Recomposition

Recomposed at the current level, the system can be stated compactly as follows.

`tg-ytdlp-bot` is a multi-authority Telegram-mediated intent-to-artifact system that:

- receives user intent through Telegram updates
- resolves that intent into an admissible continuation under local state and policy
- depends on external source platforms for extraction and media availability
- materializes or reuses a concrete artifact locally or from cache
- returns either that artifact or a stage-localized failure back through Telegram

What is forced is now separated from what is contingent.
What remains policy-sensitive is named.
What still needs deeper descent is localized rather than diffused.

## Decision-Inert Distinctions

The following distinctions are usually inert at the system-description level unless the current decision context is specifically about them.

- exact module file where a handler is defined
- internal naming differences between helper wrappers that do not alter continuation
- whether a log line originates in router or wrapper, if routing semantics are unchanged
- exact thumbnail-generation command details, when the question is only about artifact flow

These distinctions matter for debugging, but not always for system formulation.

## Admissible Continuations

From the current formulation, the admissible continuations are structurally visible.

- inbound text may terminate in command response, quality menu, direct link, download path, or determinate rejection
- callback input may terminate in audio pipeline, video pipeline, subtitles path, direct-link path, or determinate rejection
- cookie upload may terminate in persisted cookie state or explicit rejection
- a download path may terminate in cached reuse, fresh artifact delivery, partial failure, or explicit final failure

This means the formulation can guide action without requiring hidden supplementation by the author.

## Closure Criteria for This Formulation

This document is sufficiently closed for the current engineering context if it allows a reader to answer:

- what the system fundamentally does
- where the system boundary is
- which actors own which parts of behavior
- which parts are structural and which are policy
- what precedence relations govern branching behavior
- what kinds of state materially determine continuation
- where failures can happen and how they differ

If a future decision depends on finer distinctions, such as exact cookie validation precedence or cache invalidation semantics, that is a sign to refine the relevant section rather than to abandon this formulation.

For PDA purposes, closure here is relative rather than absolute.
This formulation is closed enough for system-level reasoning if further descent would mostly refine localized policy surfaces rather than change the system's admissible continuations at the architectural level.

## Related Documents

- [`Data Flow Sequence`](./02-data-flow-sequence.md): runtime actor/request flow and sequence diagrams
- [`Incoherence Memo`](./03-incoherence-memo.md): short statement of the main architectural mismatch
- [`Contributing`](./04-contributing.md): development workflow and contribution guidance
