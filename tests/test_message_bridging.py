from types import SimpleNamespace

from HELPERS.message_bridge import bridge_message_from_existing


def test_bridge_message_from_existing_preserves_transport_context():
    original = SimpleNamespace(
        id=123,
        date=456,
        message_thread_id=789,
        reply_to_message=SimpleNamespace(id=111),
        chat=SimpleNamespace(id=-1001, first_name="Group", type="supergroup"),
        from_user=SimpleNamespace(id=91363026, first_name="Andrey"),
    )

    bridged = bridge_message_from_existing(original, "/audio")

    assert bridged.chat.id == -1001
    assert bridged.chat.first_name == "Group"
    assert bridged.chat.type == "supergroup"
    assert bridged.from_user.id == 91363026
    assert bridged.from_user.first_name == "Andrey"
    assert bridged.id == 123
    assert bridged.date == 456
    assert bridged.message_thread_id == 789
    assert bridged.reply_to_message.id == 111
    assert bridged.text == "/audio"
    assert bridged.command == ["audio"]
    assert bridged._is_fake_message is True
    assert bridged._is_bridged_message is True
    assert bridged._original_message is original


def test_bridge_message_from_existing_preserves_explicit_command_override():
    original = SimpleNamespace(
        id=10,
        date=None,
        message_thread_id=None,
        reply_to_message=None,
        chat=SimpleNamespace(id=91363026, first_name="Andrey", type="private"),
        from_user=SimpleNamespace(id=91363026, first_name="Andrey"),
    )

    bridged = bridge_message_from_existing(original, "🎧", command=["audio"])

    assert bridged.text == "🎧"
    assert bridged.command == ["audio"]
    assert bridged.chat.id == 91363026
