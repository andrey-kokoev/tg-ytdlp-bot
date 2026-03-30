# Ingress Implementation Status

## Purpose

This note records what parts of the PDA ingress segmentation are already implemented in code, what still bypasses the new boundary, and what the next migration targets should be.

The intended ingress shape is:

1. transport event
2. ingress envelope
3. task request
4. execution

This document is intentionally narrower than the earlier ingress formulation docs. It is about implementation status, not the general model.

## Implemented Seams

The following paths now cross an explicit ingress boundary before entering their existing runtime logic:

- `/sub` and `/subtitle`
- `/concat`
- `/rename`
- `/audio`
- plain URL download requests routed through `url_distractor`
- `askq` callback selections in the Always Ask menu
- `askf` callback filter selections in the Always Ask menu
- `img_range` callback selections in the image/gallery flow
- cookie menu callback selections handled by `download_cookie_callback`
- subtitle settings callbacks in `subtitles_cmd.py`
- format settings callbacks in `format_cmd.py`
- cookie document uploads handled by `save_my_cookie`

The current implementation boundary is:

- `IngressEnvelope` and request dataclasses in [`HELPERS/ingress_models.py`](../../HELPERS/ingress_models.py)
- Telegram-message envelope builders in [`HELPERS/ingress_models.py`](../../HELPERS/ingress_models.py)
- request construction adapters in [`HELPERS/ingress_requests.py`](../../HELPERS/ingress_requests.py)
- transport-context bridging helpers in [`HELPERS/message_bridge.py`](../../HELPERS/message_bridge.py)

The corresponding request objects currently in use are:

- `SubtitleOnlyRequested`
- `ConcatRequested`
- `RenameRequested`
- `AudioDownloadRequested`
- `UrlDownloadRequested`
- `AskQualitySelectionRequested`
- `AskFilterSelectionRequested`
- `ImageRangeSelectionRequested`
- `CookieMenuSelectionRequested`
- `SubtitleSettingsSelectionRequested`
- `FormatMenuSelectionRequested`
- `CookieUploadRequested`

## Implemented Flow Shape

For the migrated message paths, the code now has this shape:

1. Pyrogram handler or router receives a Telegram message
2. the message is normalized into `IngressEnvelope`
3. the envelope is converted into a task request
4. the existing execution path runs using that request-derived state

For the migrated callback paths, the code now has this shape:

1. Pyrogram handler receives a callback query
2. the callback is normalized into `CallbackIngressEnvelope`
3. the callback envelope is converted into a callback request
4. the existing menu or execution logic runs using that request-derived state

For the migrated document-upload paths, the code now has this shape:

1. Pyrogram handler receives a document message
2. the document is normalized into `DocumentIngressEnvelope`
3. the document envelope is converted into a document request
4. the existing validation and save logic runs using that request-derived state

This means those paths no longer depend solely on raw Telegram messages or raw callback payload strings as the first authoritative business input.

## Current Boundary Modules

### Envelope Creation

[`HELPERS/ingress_models.py`](../../HELPERS/ingress_models.py)

- `build_telegram_message_envelope(...)`
- `build_telegram_command_envelope(...)`
- `build_telegram_callback_envelope(...)`
- `build_telegram_document_envelope(...)`

### Request Formation

[`HELPERS/ingress_requests.py`](../../HELPERS/ingress_requests.py)

- `build_subtitle_only_request(...)`
- `build_concat_request(...)`
- `build_rename_request(...)`
- `build_audio_download_request(...)`
- `build_url_download_request(...)`
- `build_ask_quality_selection_request(...)`
- `build_ask_filter_selection_request(...)`
- `build_image_range_selection_request(...)`
- `build_cookie_menu_selection_request(...)`
- `build_subtitle_settings_selection_request(...)`
- `build_format_menu_selection_request(...)`
- `build_cookie_upload_request(...)`

## Remaining Bypasses

The following ingress areas still bypass the new envelope-request boundary, or only partially participate in it:

- most callback-query ingress outside `askq`, `askf`, `img_range`, cookie menu selection, subtitle settings selection, and format settings selection
- most image/gallery command ingress outside `img_range`
- settings and admin command surfaces
- remaining fake-message reentry paths used by some commands and menu flows

These areas still depend more directly on raw Telegram update objects or on message-shaped internal reentry.

## Current Coherence Gains

The current implementation improves coherence in these ways:

- raw Telegram text is no longer treated as the only meaningful ingress object on the migrated paths
- transport-specific context is localized in `IngressEnvelope`
- business-level intent is made explicit in request objects
- handlers no longer have to jump directly from raw Telegram messages into execution without an intermediate request layer
- some command reentry paths now preserve real Telegram context through `bridge_message_from_existing(...)` instead of fabricating blank synthetic messages
- at least one former fake-callback loop has been replaced by a shared internal selection handler in the cookie menu flow

## Current Limits

The ingress refactor is still partial.

Important limits:

- callback ingress is only partially migrated
- request objects do not yet cover the full command surface
- many execution paths still accept Telegram message objects directly alongside request-derived state
- fake-message recursion is still present in several places

So the system is not yet uniformly ingress-segmented. It has a real ingress boundary on several important paths, but not a complete one.

## Next Migration Targets

The highest-value remaining ingress targets are:

1. remaining callback-query families outside `askq`, `askf`, and `img_range`
2. broader image/gallery command ingress
3. settings and admin command surfaces
4. remaining fake-message reentry paths

Why this order:

- callback ingress still has many transport-shaped branches outside the migrated seams
- image/gallery paths are a major alternate execution family beyond the one migrated callback
- settings/admin flows still carry a lot of direct Telegram-shaped control
- remaining fake-message reentry still keeps parts of internal control flow too close to Telegram message mechanics

## Practical Stopping Point

At the current checkpoint, the ingress refactor is already meaningful enough to keep:

- the envelope boundary is real
- request formation is real
- the broad URL path now participates
- callback ingress is established across multiple subsystems
- document ingress has started in at least one real upload path
- some message-shaped reentry has already been reduced through context-preserving bridging
- at least one callback/command loop has already been normalized into a shared internal selection path

That makes this a genuine architectural seam rather than a documentation-only framing.
