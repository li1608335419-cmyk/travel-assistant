from models.schemas import Message, MessageRole


def test_create_and_read_session(memory_store):
    session = memory_store.create_session("u1")
    loaded = memory_store.get_session(session.session_id)
    assert loaded is not None
    assert loaded.user_id == "u1"


def test_message_history_is_trimmed(memory_store):
    session = memory_store.create_session("u1")
    for index in range(6):
        memory_store.add_message(
            session.session_id,
            Message(role=MessageRole.USER, content=f"msg-{index}"),
        )
    loaded = memory_store.get_session(session.session_id)
    assert loaded is not None
    assert len(loaded.messages) == 4
    assert loaded.messages[0].content == "msg-2"


def test_profile_update(memory_store):
    session = memory_store.create_session("u2")
    memory_store.update_profile(session.session_id, {"destination": "杭州", "days": 2})
    loaded = memory_store.get_session(session.session_id)
    assert loaded.trip_profile.destination == "杭州"
    assert loaded.trip_profile.days == 2
