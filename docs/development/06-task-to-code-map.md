# Task-to-Code Map

## Purpose

This document maps the task model in [`05-task-model.md`](./05-task-model.md) onto the current codebase.

The goal is not to repeat runtime flow.
It is to identify:

- which modules/functions currently govern each task state transition
- which authorities are represented in code at that transition
- what state is read or written there
- where authority or precedence is split across multiple code surfaces
- where incoherence is therefore most likely to appear

## Mapping Principle

The unit being mapped is not "feature" and not "module."
It is:

- task state transition class

Each transition below names the primary code owners, the key reads/writes, and the main interleavings.

## S0 -> S1: Inbound Event to Routed Task

### Primary Code Owners

- [`URL_PARSERS/url_extractor.py:url_distractor()`](./../../URL_PARSERS/url_extractor.py)
- message/callback decorators and wrappers in [`HELPERS/decorators.py`](./../../HELPERS/decorators.py)
- command-specific handlers registered in `COMMANDS/*`
- document upload handler in [`COMMANDS/cookies_cmd.py:save_my_cookie()`](./../../COMMANDS/cookies_cmd.py)

### Authorities Represented

- Telegram update type
- handler registration/filter matching
- router logic
- explicit command syntax

### State Reads

- current Telegram update fields
- limited per-user state in early routing, such as command limiter behavior

### State Writes

- mostly none at this stage, aside from logs and possible reply messages

### Known Interleavings

- filter-level routing and in-function routing both participate
- command routing is split between explicit `@app.on_message(filters.command(...))` handlers and the catch-all/private-text router
- callback routing is distributed across several modules rather than centralized

### Likely Incoherence

- one conceptual routing transition is implemented by multiple overlapping registration surfaces
- routing authority is partially in decorators/filters and partially in handler internals

## S1 -> S2: Routed Task to Context-Resolved Task

### Primary Code Owners

- [`URL_PARSERS/url_extractor.py:url_distractor()`](./../../URL_PARSERS/url_extractor.py)
- [`URL_PARSERS/video_extractor.py:video_url_extractor()`](./../../URL_PARSERS/video_extractor.py)
- cookie/state helpers in [`COMMANDS/cookies_cmd.py`](./../../COMMANDS/cookies_cmd.py)
- argument/setting helpers in `COMMANDS/args_cmd.py`, `COMMANDS/format_cmd.py`, `COMMANDS/settings_cmd.py`

### Authorities Represented

- persisted per-user state
- explicit callback context where present
- router-local policy defaults

### State Reads

- `users/<user_id>/format.txt`
- `users/<user_id>/cookie.txt`
- `users/<user_id>/args.txt`
- tags, keyboard, language, and other user files
- in-memory session/cache state

### State Writes

- creation of user directory when needed
- possible intermediate state flags and logs

### Known Interleavings

- the same transition mixes user preference resolution, cookie-state resolution, and command interpretation
- context is partly file-backed and partly carried through Telegram message/reply/callback objects

### Likely Incoherence

- context resolution is real but not centrally modeled; it is assembled ad hoc across several helpers

## S2 -> S3: Context-Resolved Task to Metadata-Resolved Task

### Primary Code Owners

- [`DOWN_AND_UP/yt_dlp_hook.py:get_video_formats()`](./../../DOWN_AND_UP/yt_dlp_hook.py)
- [`DOWN_AND_UP/always_ask_menu.py:ask_quality_menu()`](./../../DOWN_AND_UP/always_ask_menu.py)
- extractor-related helpers in `URL_PARSERS/*` and `HELPERS/*`

### Authorities Represented

- source-platform feasibility
- extractor behavior
- cookie/proxy/PO-token access enablement

### State Reads

- user cookie file
- user args and format-related options
- ask-menu/session caches
- helper-service configuration

### State Writes

- cached metadata / ask-menu information
- copied cookie into task/download scope when needed
- logs about extraction outcomes and fallbacks

### Known Interleavings

- metadata extraction and access-strategy selection are intertwined
- cookie/proxy/fallback decisions are made during extraction rather than before it as a separately modeled phase

### Likely Incoherence

- source feasibility and local policy are entangled in the same operational layer

## S3 -> S4: Metadata-Resolved Task to Branch-Selected Task

### Primary Code Owners

- [`DOWN_AND_UP/always_ask_menu.py:ask_quality_menu()`](./../../DOWN_AND_UP/always_ask_menu.py)
- [`DOWN_AND_UP/always_ask_menu.py:askq_callback()`](./../../DOWN_AND_UP/always_ask_menu.py)
- [`DOWN_AND_UP/always_ask_menu.py:askq_callback_logic()`](./../../DOWN_AND_UP/always_ask_menu.py)
- direct-path logic in [`URL_PARSERS/video_extractor.py:video_url_extractor()`](./../../URL_PARSERS/video_extractor.py)

### Authorities Represented

- explicit user callback choice
- saved user format preference
- cache availability
- direct-link mode and related branch policy

### State Reads

- callback data
- reply-to/original message context
- saved format
- cached qualities and cached metadata
- filter/subtitle selections

### State Writes

- session cache for quality/filter/subtitle state
- processing messages and inline menu state

### Known Interleavings

- callback specificity, saved defaults, and cache reuse all compete here
- this is the main branch-selection surface for media tasks

### Likely Incoherence

- branch-selection authority is distributed between callback handlers, saved preferences, and cache helpers without one explicit decision object

## S4 -> S5: Branch-Selected Task to Material Acquisition

### Primary Code Owners

- [`DOWN_AND_UP/down_and_up.py:down_and_up()`](./../../DOWN_AND_UP/down_and_up.py)
- [`DOWN_AND_UP/down_and_audio.py:down_and_audio()`](./../../DOWN_AND_UP/down_and_audio.py)
- alternative engine paths such as gallery-dl-related logic in `DOWN_AND_UP/*`

### Authorities Represented

- selected task branch
- access strategy
- source-platform feasibility under concrete chosen options

### State Reads

- user cookie and args
- chosen format/quality info
- subtitle and split settings
- cache entries and retry flags

### State Writes

- active-download tracking
- task download directories under `users/<user_id>/downloads/...`
- status/progress messages
- intermediate files

### Known Interleavings

- acquisition, retry, proxy/cookie fallback, and progress reporting all co-exist in these large orchestration functions
- terminal semantics are not yet separated from acquisition logic

### Likely Incoherence

- too much authority is concentrated in orchestration functions that mix policy, state mutation, remote access, and user messaging

## S5 -> S6: Material Acquisition to Local Artifact Available

### Primary Code Owners

- [`DOWN_AND_UP/down_and_up.py`](./../../DOWN_AND_UP/down_and_up.py)
- [`DOWN_AND_UP/down_and_audio.py`](./../../DOWN_AND_UP/down_and_audio.py)
- [`DOWN_AND_UP/ffmpeg.py`](./../../DOWN_AND_UP/ffmpeg.py)
- cache helpers in [`DATABASE/cache_db.py`](./../../DATABASE/cache_db.py)

### Authorities Represented

- success/failure of download engines
- post-processing feasibility
- cache validity for reuse

### State Reads

- downloaded source files
- thumbnails
- subtitle files
- cached message IDs

### State Writes

- converted/merged/tagged output files
- split outputs
- thumbnail artifacts
- cache updates

### Known Interleavings

- fresh artifact creation and cache reuse both influence whether the system considers a deliverable available
- local artifact existence and semantic validity are not always modeled separately

### Likely Incoherence

- artifact availability, artifact suitability, and cache validity are close but not identical concepts, yet often handled together

## S6 -> S7: Local Artifact Available to Delivery Attempt

### Primary Code Owners

- [`DOWN_AND_UP/sender.py:send_videos()`](./../../DOWN_AND_UP/sender.py)
- `app.send_audio(...)` call sites in [`DOWN_AND_UP/down_and_audio.py`](./../../DOWN_AND_UP/down_and_audio.py)
- helper messaging in [`HELPERS/safe_messeger.py:safe_send_message()`](./../../HELPERS/safe_messeger.py)

### Authorities Represented

- chosen artifact
- Telegram upload semantics
- user delivery-mode settings such as send-as-file

### State Reads

- final artifact path
- thumbnails and captions
- user args such as `send_as_file`

### State Writes

- Telegram outbound messages/media
- cached message IDs after success
- logs and success/progress text

### Known Interleavings

- upload mode policy and Telegram constraints interleave here
- success semantics often depend on what Telegram accepted, not just what was locally available

### Likely Incoherence

- some delivery logic is centralized in `sender.py`, some remains embedded in orchestrator functions

## S7 -> S8: Delivery Attempt to Terminal Outcome

### Primary Code Owners

- terminal branches spread across:
  - [`DOWN_AND_UP/down_and_up.py`](./../../DOWN_AND_UP/down_and_up.py)
  - [`DOWN_AND_UP/down_and_audio.py`](./../../DOWN_AND_UP/down_and_audio.py)
  - [`HELPERS/logger.py`](./../../HELPERS/logger.py)
  - [`HELPERS/safe_messeger.py`](./../../HELPERS/safe_messeger.py)

### Authorities Represented

- Telegram upload result
- counts of delivered vs requested outputs
- local exception handling
- current task/reporting policy

### State Reads

- successful upload counters
- task counts and selected indices
- final exception states

### State Writes

- completion/failure messages
- cache saves
- cleanup of task directories
- terminal logs

### Known Interleavings

- terminalization is not one centralized layer
- success reporting, cleanup, caching, and failure reporting are intertwined

### Likely Incoherence

- terminal semantics are distributed, which makes partial success and stage-local failure harder to keep uniform

## Cross-Cutting Ownership Surfaces

These code surfaces cut across multiple transition classes and therefore deserve special attention.

### `HELPERS/safe_messeger.py`

- mediates many user-visible state changes
- normalizes reply behavior and thread routing
- influences perceived task continuity even though it is not the task owner

### `COMMANDS/cookies_cmd.py`

- owns both state mutation tasks and parts of access-strategy resolution
- therefore spans more than one task class

### `DOWN_AND_UP/always_ask_menu.py`

- spans metadata display, branch selection, callback continuation, cache participation, and some task-state persistence
- it is one of the highest interleaving modules in the codebase

### `DOWN_AND_UP/down_and_up.py` and `DOWN_AND_UP/down_and_audio.py`

- act as de facto workflow engines
- currently combine transition ownership that might eventually deserve stronger separation

## Most Likely Incoherence Hotspots

If the goal is to inspect the code for system-design incoherence, the highest-yield hotspots are:

1. routing overlap between handler registration and in-function branching
2. context resolution assembled from scattered file reads and implicit task context
3. branch selection inside `always_ask_menu.py`
4. access-strategy decisions mixed into extraction/download code
5. terminal semantics distributed across orchestration, sender, logging, and cleanup code

## Recomposition

Recomposed at this layer:

- the current codebase already contains an implicit task engine
- but ownership of task transitions is distributed rather than explicit
- therefore the main architectural work ahead is not discovering whether a task model exists
- it is deciding whether to make the existing implicit task engine explicit

## What This Enables Next

The next natural move after this map is one of:

- define a single explicit task-state machine artifact
- annotate current modules/functions with owned transition classes
- identify one transition class to centralize first, most likely branch selection or terminalization

## Related Documents

- [`Branch Selection Model`](./07-branch-selection-model.md): explicit formulation of the `S3 -> S4` decision surface
