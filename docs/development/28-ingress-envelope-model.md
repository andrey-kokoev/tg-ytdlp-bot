# Ingress Envelope Model

## Purpose

This document follows:

- [`27-ingress-segmentation-model.md`](./27-ingress-segmentation-model.md)

Its goal is to define the minimal normalized envelope that should sit between:

- Telegram transport events
- internal task-request formation

## Governing Ambiguity

The live ambiguity is:

- what is the minimal non-arbitrary object that preserves the active distinctions at ingress
  without dragging raw Telegram objects deep into the system

Too small:

- command string

Too large:

- full Telegram message/callback/document object treated as the runtime carrier

So the envelope must be:

- transport-aware
- context-preserving
- not yet business-semantic

## Recommended Shape

Minimal fields:

- `transport: str`
- `event_kind: str`
- `user_id: int`
- `chat_id: int`
- `source_message_id: int | None`
- `raw_text: str | None`
- `raw_payload: dict`
- `reply_context: dict`
- `attachments: list[dict]`

## Field Meaning

### `transport`

The ingress source.

For the first implementation:

- `telegram`

### `event_kind`

Coarse event family, such as:

- `command_message`
- `plain_text_message`
- `callback_query`
- `document_upload`

This is still transport-side categorization, not task meaning.

### `user_id`, `chat_id`, `source_message_id`

These preserve the identity and reply origin needed for:

- access control
- rate limiting
- response routing
- task provenance

### `raw_text`

The raw text when the event has text.

This is preserved for parsing, auditing, and debugging.

It should not be the sole authoritative input after task formation.

### `raw_payload`

Compact normalized transport payload beyond plain text.

Examples:

- callback data
- document filename
- mime type
- command tokens

### `reply_context`

Any transport context that materially affects meaning or response routing.

Examples:

- reply-to message id
- originating callback message id
- topic/thread id if applicable

### `attachments`

A normalized list of attached document/media artifacts when present.

This keeps document-driven commands from becoming a special ad hoc path.

## What The Envelope Must Not Do

The envelope must not directly decide:

- branch family
- task request type
- concat policy
- subtitle mode

Those belong to the task-request stage.

If the envelope starts accumulating business semantics, the transport/business distinction collapses
again.

## Why `raw_payload` Is Needed

Even if `raw_text` exists, it is not enough.

Examples:

- callback query carries data that is not a command string
- document upload carries filename and file identity
- some command flows depend on source message id or attachment type

So the envelope needs one structured payload field even in the first minimal version.

## Why `raw_payload` Must Stay Compact

The envelope should not become a full Telegram shadow object.

That would defeat the point of normalization.

The correct standard is:

- preserve what later stages still need
- drop what later stages should not depend on

## Replaceability Consequence

If this envelope is shaped correctly, then:

- Telegram transport can later be replaced by another transport
- task-request formation can stay mostly stable

That is the whole architectural payoff.

## First Narrow Examples

### `/sub URL`

- `transport="telegram"`
- `event_kind="command_message"`
- `raw_text="/sub https://..."`
- `raw_payload={"command": "sub", "args": ["https://..."]}`

### `/concat reverse 1-11 URL`

- `transport="telegram"`
- `event_kind="command_message"`
- `raw_text="/concat reverse 1-11 https://..."`
- `raw_payload={"command": "concat", "args": ["reverse", "1-11", "https://..."]}`

### cookie.txt upload

- `transport="telegram"`
- `event_kind="document_upload"`
- `attachments=[{"file_name": "cookie.txt", ...}]`

## First Invariants

1. every ingress event produces exactly one envelope
2. every envelope has transport + event kind + user/chat identity
3. task formation reads the envelope, not raw Telegram objects directly
4. the envelope preserves enough context for reply routing, but not arbitrary Telegram internals

## Why This Is The Next Correct PDA Move

The previous document localized the ingress stages.
This document defines the first explicit object at the stage boundary.

That is the correct next move because the system now needs:

- one ingress carrier

before it can cleanly define:

- one task-request carrier
