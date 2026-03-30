from __future__ import annotations

from types import SimpleNamespace


def bridge_message_from_existing(
    original_message,
    text,
    *,
    command=None,
    runtime_task=None,
    default_user_name="User",
):
    """
    Create a lightweight message-like object for internal reentry while preserving
    the original Telegram transport context instead of fabricating a blank one.
    """
    original_chat = getattr(original_message, "chat", None)
    original_user = getattr(original_message, "from_user", None)
    user_id = getattr(original_user, "id", None) or getattr(original_chat, "id", None)
    if user_id is None:
        user_id = -1

    m = SimpleNamespace()
    m.chat = SimpleNamespace()
    m.chat.id = getattr(original_chat, "id", user_id)
    m.chat.first_name = getattr(original_chat, "first_name", default_user_name)
    m.chat.type = getattr(original_chat, "type", "private")
    m.text = text
    m.caption = None
    m.first_name = getattr(original_user, "first_name", m.chat.first_name)
    m.reply_to_message = getattr(original_message, "reply_to_message", None)
    m.id = getattr(original_message, "id", 0)
    m.date = getattr(original_message, "date", None)
    m.from_user = SimpleNamespace()
    m.from_user.id = user_id
    m.from_user.first_name = getattr(original_user, "first_name", m.chat.first_name)
    m._is_fake_message = True
    m._is_bridged_message = True
    m._original_chat_id = getattr(original_chat, "id", user_id)
    m.message_thread_id = getattr(original_message, "message_thread_id", None)
    m._original_message = original_message
    m._runtime_task = runtime_task
    if command is not None:
        m.command = command
    else:
        try:
            if isinstance(text, str) and text.startswith('/'):
                parts = text.strip().split()
                if parts:
                    cmd = parts[0][1:] if len(parts[0]) > 1 else ''
                    args = parts[1:]
                    m.command = [cmd] + args
        except Exception:
            pass
    return m
