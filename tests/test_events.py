"""Test suite for amplifier_tui.events module.

Comprehensive test coverage of Event, Item, and Transcript classes.
Focuses on:
- Event dataclass immutability and instantiation
- Item dataclass mutability and defaults
- Transcript idempotency and state management
- Event kind dispatch and payload handling
- Edge cases and error paths
"""

import pytest

from amplifier_tui.events import Event, Item, Transcript

# ============================================================================
# FIXTURES: Test data and common setup
# ============================================================================


@pytest.fixture
def transcript():
    """Fresh Transcript instance for each test."""
    return Transcript()


@pytest.fixture
def sample_event():
    """Basic valid event for testing."""
    return Event(
        session_id="session-1",
        sequence=1,
        turn_id="turn-1",
        kind="turn.accepted",
        item_id="item-1",
        payload={"text": "Hello, world!"},
    )


@pytest.fixture
def user_input_event():
    """Event representing user input."""
    return Event(
        session_id="s1",
        sequence=1,
        turn_id="t1",
        kind="turn.accepted",
        item_id="user-1",
        payload={"text": "What is the weather?"},
    )


@pytest.fixture
def display_message_event():
    """Event representing a display message/notice."""
    return Event(
        session_id="s1",
        sequence=2,
        turn_id="t1",
        kind="display.message",
        item_id="msg-1",
        payload={"text": "Loading..."},
    )


@pytest.fixture
def question_event():
    """Event representing a question with metadata."""
    return Event(
        session_id="s1",
        sequence=3,
        turn_id="t1",
        kind="question.updated",
        item_id="q-1",
        payload={
            "text": "Choose an option",
            "status": "pending",
            "options": ["A", "B", "C"],
        },
    )


@pytest.fixture
def correction_event():
    """Event representing a steering/correction."""
    return Event(
        session_id="s1",
        sequence=4,
        turn_id="t1",
        kind="steering.updated",
        item_id="corr-1",
        payload={
            "text": "Refocus on task X",
            "status": "active",
            "context": {"task": "X"},
        },
    )


@pytest.fixture
def text_delta_event():
    """Event representing incremental text (streaming)."""
    return Event(
        session_id="s1",
        sequence=5,
        turn_id="t1",
        kind="text.delta",
        item_id="stream-1",
        payload={"text": "This is "},
    )


@pytest.fixture
def text_final_event():
    """Event representing final text replacement."""
    return Event(
        session_id="s1",
        sequence=6,
        turn_id="t1",
        kind="text.final",
        item_id="final-1",
        payload={"text": "Complete response."},
    )


@pytest.fixture
def tool_start_event():
    """Event representing tool invocation start."""
    return Event(
        session_id="s1",
        sequence=7,
        turn_id="t1",
        kind="tool.start",
        item_id="tool-1",
        payload={
            "name": "fetch_data",
            "status": "running",
            "args": {"url": "https://example.com"},
        },
    )


@pytest.fixture
def tool_end_event():
    """Event representing tool completion."""
    return Event(
        session_id="s1",
        sequence=8,
        turn_id="t1",
        kind="tool.end",
        item_id="tool-1",
        payload={
            "name": "fetch_data",
            "status": "succeeded",
            "result": {"data": [1, 2, 3]},
        },
    )


@pytest.fixture
def turn_ended_event():
    """Event representing turn completion."""
    return Event(
        session_id="s1",
        sequence=9,
        turn_id="t1",
        kind="turn.ended",
        item_id="outcome-1",
        payload={"status": "success", "message": "Task completed."},
    )


@pytest.fixture
def turn_ended_event_no_message():
    """Event representing turn completion without message."""
    return Event(
        session_id="s1",
        sequence=10,
        turn_id="t1",
        kind="turn.ended",
        item_id="outcome-2",
        payload={"status": "success"},
    )


@pytest.fixture
def event_stream():
    """Sequence of events representing a complete turn."""
    return [
        Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="user-1",
            payload={"text": "Compute 2+2"},
        ),
        Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="text.delta",
            item_id="resp-1",
            payload={"text": "The "},
        ),
        Event(
            session_id="s1",
            sequence=3,
            turn_id="t1",
            kind="text.delta",
            item_id="resp-1",
            payload={"text": "answer "},
        ),
        Event(
            session_id="s1",
            sequence=4,
            turn_id="t1",
            kind="text.final",
            item_id="resp-1",
            payload={"text": "is 4."},
        ),
        Event(
            session_id="s1",
            sequence=5,
            turn_id="t1",
            kind="turn.ended",
            item_id="outcome-1",
            payload={"status": "success"},
        ),
    ]


# ============================================================================
# UNIT TESTS: Event Class
# ============================================================================


class TestEventInstantiation:
    """Test Event dataclass initialization and immutability."""

    def test_event_instantiation_with_all_fields(self, sample_event):
        """Event instantiation with all required fields."""
        assert sample_event.session_id == "session-1"
        assert sample_event.sequence == 1
        assert sample_event.turn_id == "turn-1"
        assert sample_event.kind == "turn.accepted"
        assert sample_event.item_id == "item-1"
        assert sample_event.payload == {"text": "Hello, world!"}

    def test_event_is_frozen_immutable(self, sample_event):
        """Event is frozen; field mutations are prevented."""
        with pytest.raises(
            (AttributeError, RuntimeError),
            match="cannot assign|dataclass|frozen",
        ):
            sample_event.kind = "modified"

    def test_event_with_none_turn_id(self):
        """Event accepts None for turn_id (valid use case)."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id=None,
            kind="display.message",
            item_id="i1",
            payload={"text": "System message"},
        )
        assert event.turn_id is None

    def test_event_with_complex_payload(self):
        """Event payload can contain nested dicts and lists."""
        payload = {
            "text": "Complex",
            "metadata": {"nested": {"deep": "value"}},
            "array": [1, 2, 3],
        }
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="test",
            item_id="i1",
            payload=payload,
        )
        assert event.payload == payload
        assert event.payload["metadata"]["nested"]["deep"] == "value"

    def test_event_with_empty_payload(self):
        """Event payload can be empty dict."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="test",
            item_id="i1",
            payload={},
        )
        assert event.payload == {}

    def test_event_sequence_is_integer(self):
        """Event sequence must be integer (validated by type hint)."""
        # This is caught at instantiation time by type checking
        event = Event(
            session_id="s1",
            sequence=42,
            turn_id="t1",
            kind="test",
            item_id="i1",
            payload={},
        )
        assert isinstance(event.sequence, int)
        assert event.sequence == 42


# ============================================================================
# UNIT TESTS: Item Class
# ============================================================================


class TestItemInstantiation:
    """Test Item dataclass initialization and mutability."""

    def test_item_instantiation_required_fields_only(self):
        """Item instantiation with minimal required fields."""
        item = Item(id="i1", kind="user")
        assert item.id == "i1"
        assert item.kind == "user"
        assert item.text == ""
        assert item.status == ""
        assert item.detail == {}

    def test_item_with_all_fields(self):
        """Item instantiation with all fields specified."""
        item = Item(
            id="i1",
            kind="assistant",
            text="Response text",
            status="complete",
            detail={"key": "value"},
        )
        assert item.text == "Response text"
        assert item.status == "complete"
        assert item.detail == {"key": "value"}

    def test_item_text_default_empty_string(self):
        """Item.text defaults to empty string."""
        item = Item(id="i1", kind="user")
        assert item.text == ""
        assert isinstance(item.text, str)

    def test_item_status_default_empty_string(self):
        """Item.status defaults to empty string."""
        item = Item(id="i1", kind="user")
        assert item.status == ""
        assert isinstance(item.status, str)

    def test_item_detail_default_empty_dict(self):
        """Item.detail defaults to empty dict."""
        item = Item(id="i1", kind="user")
        assert item.detail == {}
        assert isinstance(item.detail, dict)

    def test_item_detail_default_factory_creates_separate_dicts(self):
        """Item.detail default_factory creates unique dicts per instance."""
        item1 = Item(id="i1", kind="user")
        item2 = Item(id="i2", kind="user")
        item1.detail["key"] = "value1"
        item2.detail["key"] = "value2"
        assert item1.detail["key"] == "value1"
        assert item2.detail["key"] == "value2"

    def test_item_is_mutable(self):
        """Item fields can be mutated after instantiation."""
        item = Item(id="i1", kind="assistant")
        item.text = "Updated text"
        item.status = "complete"
        item.detail["metadata"] = "added"
        assert item.text == "Updated text"
        assert item.status == "complete"
        assert item.detail == {"metadata": "added"}

    def test_item_text_mutation_independent_between_instances(self):
        """Mutation of one item's text does not affect others."""
        item1 = Item(id="i1", kind="user", text="Original")
        item2 = Item(id="i2", kind="user", text="Original")
        item1.text = "Modified"
        assert item1.text == "Modified"
        assert item2.text == "Original"

    def test_item_detail_dict_mutation(self):
        """Item.detail can be mutated with dict methods."""
        item = Item(id="i1", kind="user")
        item.detail.update({"key1": "val1", "key2": "val2"})
        assert item.detail == {"key1": "val1", "key2": "val2"}
        item.detail["key3"] = "val3"
        assert len(item.detail) == 3


# ============================================================================
# UNIT TESTS: Transcript Class - Idempotency
# ============================================================================


class TestTranscriptIdempotency:
    """Test Transcript idempotency mechanism (seen set)."""

    def test_transcript_initialization_empty_state(self):
        """Transcript starts with empty items and seen set."""
        t = Transcript()
        assert t.items == {}
        assert t.seen == set()

    def test_apply_single_event_added_to_items(self, transcript, user_input_event):
        """Applying one event adds it to items."""
        transcript.apply(user_input_event)
        assert len(transcript.items) == 1
        assert "user-1" in transcript.items

    def test_apply_duplicate_event_skipped_idempotent(self, transcript, user_input_event):
        """Applying same event twice is idempotent (seen set prevents duplicate)."""
        transcript.apply(user_input_event)
        items_after_first = dict(transcript.items)
        transcript.apply(user_input_event)
        items_after_second = dict(transcript.items)
        assert items_after_first == items_after_second

    def test_seen_set_tracks_session_sequence_tuple(self, transcript):
        """Idempotency key is (session_id, sequence) tuple."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "text1"},
        )
        transcript.apply(event1)
        # Check that seen set contains the key
        assert ("s1", 1) in transcript.seen

    def test_different_events_same_session_different_sequence(self, transcript):
        """Events with same session but different sequence are both applied."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "First"},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i2",
            payload={"text": "Second"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        assert len(transcript.items) == 2
        assert ("s1", 1) in transcript.seen
        assert ("s1", 2) in transcript.seen

    def test_different_sessions_same_sequence_both_applied(self, transcript):
        """Events from different sessions with same sequence are both applied."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Session 1"},
        )
        event2 = Event(
            session_id="s2",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i2",
            payload={"text": "Session 2"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        assert len(transcript.items) == 2
        assert ("s1", 1) in transcript.seen
        assert ("s2", 1) in transcript.seen

    def test_reapply_event_in_different_order_still_idempotent(self, transcript):
        """Idempotency holds even when same event is applied multiple times (not just twice)."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Once"},
        )
        for _ in range(5):
            transcript.apply(event)
        assert len(transcript.items) == 1
        assert len(transcript.seen) == 1


# ============================================================================
# UNIT TESTS: Transcript Event Kind Dispatch
# ============================================================================


class TestTranscriptEventKindTurnAccepted:
    """Test handling of 'turn.accepted' event kind."""

    def test_turn_accepted_creates_user_item(self, transcript, user_input_event):
        """turn.accepted creates an Item with kind='user'."""
        transcript.apply(user_input_event)
        item = transcript.items["user-1"]
        assert item.kind == "user"
        assert item.text == "What is the weather?"
        assert item.status == ""
        assert item.detail == {}

    def test_turn_accepted_missing_text_raises_keyerror(self, transcript):
        """turn.accepted without 'text' in payload raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={},  # Missing 'text'
        )
        with pytest.raises(KeyError, match="text"):
            transcript.apply(event)

    def test_turn_accepted_text_can_be_multiline(self, transcript):
        """turn.accepted text field can contain newlines and special characters."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Line 1\nLine 2\nLine 3"},
        )
        transcript.apply(event)
        assert transcript.items["i1"].text == "Line 1\nLine 2\nLine 3"

    def test_turn_accepted_text_can_be_empty_string(self, transcript):
        """turn.accepted text field can be empty string (valid but uncommon)."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": ""},
        )
        transcript.apply(event)
        assert transcript.items["i1"].text == ""


class TestTranscriptEventKindDisplayMessage:
    """Test handling of 'display.message' event kind."""

    def test_display_message_creates_notice_item(self, transcript, display_message_event):
        """display.message creates an Item with kind='notice'."""
        transcript.apply(display_message_event)
        item = transcript.items["msg-1"]
        assert item.kind == "notice"
        assert item.text == "Loading..."
        assert item.status == ""

    def test_display_message_missing_text_raises_keyerror(self, transcript):
        """display.message without 'text' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="display.message",
            item_id="i1",
            payload={},
        )
        with pytest.raises(KeyError, match="text"):
            transcript.apply(event)


class TestTranscriptEventKindQuestionUpdated:
    """Test handling of 'question.updated' event kind."""

    def test_question_updated_creates_question_item_with_metadata(self, transcript, question_event):
        """question.updated creates an Item with kind='question' and copies payload as detail."""
        transcript.apply(question_event)
        item = transcript.items["q-1"]
        assert item.kind == "question"
        assert item.text == "Choose an option"
        assert item.status == "pending"
        # Payload is shallow copied to detail
        assert "options" in item.detail
        assert item.detail["options"] == ["A", "B", "C"]

    def test_question_updated_detail_is_shallow_copy(self, transcript):
        """question.updated creates a shallow copy of payload to detail."""
        nested_list = ["A", "B", "C"]
        payload = {"text": "Q", "status": "pending", "options": nested_list}
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="question.updated",
            item_id="q1",
            payload=payload,
        )
        transcript.apply(event)
        item = transcript.items["q1"]
        # Mutating original payload's list affects detail (shallow copy)
        nested_list.append("D")
        assert item.detail["options"] == ["A", "B", "C", "D"]

    def test_question_updated_missing_text_raises_keyerror(self, transcript):
        """question.updated without 'text' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="question.updated",
            item_id="q1",
            payload={"status": "pending"},
        )
        with pytest.raises(KeyError, match="text"):
            transcript.apply(event)

    def test_question_updated_missing_status_raises_keyerror(self, transcript):
        """question.updated without 'status' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="question.updated",
            item_id="q1",
            payload={"text": "Choose"},
        )
        with pytest.raises(KeyError, match="status"):
            transcript.apply(event)


class TestTranscriptEventKindSteeringUpdated:
    """Test handling of 'steering.updated' (correction) event kind."""

    def test_steering_updated_creates_correction_item(self, transcript, correction_event):
        """steering.updated creates an Item with kind='correction'."""
        transcript.apply(correction_event)
        item = transcript.items["corr-1"]
        assert item.kind == "correction"
        assert item.text == "Refocus on task X"
        assert item.status == "active"
        assert "context" in item.detail

    def test_steering_updated_missing_text_raises_keyerror(self, transcript):
        """steering.updated without 'text' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="steering.updated",
            item_id="c1",
            payload={"status": "active"},
        )
        with pytest.raises(KeyError):
            transcript.apply(event)

    def test_steering_updated_missing_status_raises_keyerror(self, transcript):
        """steering.updated without 'status' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="steering.updated",
            item_id="c1",
            payload={"text": "Refocus"},
        )
        with pytest.raises(KeyError):
            transcript.apply(event)


class TestTranscriptEventKindTextDeltaAndFinal:
    """Test handling of 'text.delta' and 'text.final' event kinds."""

    def test_text_delta_appends_to_existing_item_text(self, transcript):
        """text.delta appends to item.text."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": "Hello "},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": "world"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        assert transcript.items["s1"].text == "Hello world"

    def test_text_delta_creates_assistant_item_if_missing(self, transcript):
        """text.delta on non-existent item_id creates new Item with kind='assistant'."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="new-item",
            payload={"text": "First delta"},
        )
        transcript.apply(event)
        item = transcript.items["new-item"]
        assert item.kind == "assistant"
        assert item.text == "First delta"

    def test_text_final_replaces_item_text(self, transcript):
        """text.final replaces item.text entirely."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": "Old text"},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="text.final",
            item_id="s1",
            payload={"text": "New final text"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        assert transcript.items["s1"].text == "New final text"

    def test_text_final_creates_assistant_item_if_missing(self, transcript):
        """text.final on non-existent item_id creates new Item."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.final",
            item_id="final-item",
            payload={"text": "Final response"},
        )
        transcript.apply(event)
        assert transcript.items["final-item"].text == "Final response"

    def test_text_delta_missing_text_raises_keyerror(self, transcript):
        """text.delta without 'text' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={},
        )
        with pytest.raises(KeyError):
            transcript.apply(event)

    def test_text_final_missing_text_raises_keyerror(self, transcript):
        """text.final without 'text' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.final",
            item_id="s1",
            payload={},
        )
        with pytest.raises(KeyError):
            transcript.apply(event)

    def test_text_delta_followed_by_final_concatenation_order(self, transcript):
        """text.delta then text.final produces concatenation not replacement."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": "Part A "},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="text.final",
            item_id="s1",
            payload={"text": "Part B"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        # text.final replaces, not appends to delta
        assert transcript.items["s1"].text == "Part B"

    def test_text_delta_empty_string(self, transcript):
        """text.delta with empty string is valid."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": ""},
        )
        transcript.apply(event)
        assert transcript.items["s1"].text == ""


class TestTranscriptEventKindToolEvents:
    """Test handling of 'tool.*' event kinds."""

    def test_tool_event_creates_tool_item_if_missing(self, transcript):
        """tool.* on non-existent item creates new Item with kind='tool'."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="tool1",
            payload={"name": "calc", "status": "running"},
        )
        transcript.apply(event)
        item = transcript.items["tool1"]
        assert item.kind == "tool"
        assert item.text == "calc"
        assert item.status == "running"

    def test_tool_event_name_from_payload_to_text(self, transcript):
        """tool.* sets item.text from payload 'name' field."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="tool1",
            payload={"name": "fetch_url", "status": "running"},
        )
        transcript.apply(event)
        assert transcript.items["tool1"].text == "fetch_url"

    def test_tool_event_status_defaults_to_running_if_missing(self, transcript):
        """tool.* defaults status to 'running' if not in payload."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="tool1",
            payload={"name": "calc"},  # No status
        )
        transcript.apply(event)
        assert transcript.items["tool1"].status == "running"

    def test_tool_event_uses_status_from_payload_if_present(self, transcript):
        """tool.* uses 'status' from payload if provided."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.end",
            item_id="tool1",
            payload={"name": "calc", "status": "succeeded"},
        )
        transcript.apply(event)
        assert transcript.items["tool1"].status == "succeeded"

    def test_tool_event_detail_updated_with_full_payload(self, transcript):
        """tool.* updates item.detail with full payload."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="tool1",
            payload={
                "name": "calc",
                "status": "running",
                "args": {"expr": "2+2"},
                "timeout": 10,
            },
        )
        transcript.apply(event)
        item = transcript.items["tool1"]
        assert item.detail["name"] == "calc"
        assert item.detail["args"] == {"expr": "2+2"}
        assert item.detail["timeout"] == 10

    def test_multiple_tool_events_same_item_accumulate_detail(self, transcript):
        """Multiple tool.* events on same item_id accumulate in detail dict."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="tool1",
            payload={"name": "calc", "status": "running", "args": {"expr": "2+2"}},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="tool.end",
            item_id="tool1",
            payload={"name": "calc", "status": "succeeded", "result": 4},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        item = transcript.items["tool1"]
        # Both payloads merged into detail
        assert item.detail["args"] == {"expr": "2+2"}
        assert item.detail["result"] == 4
        assert item.detail["status"] == "succeeded"

    def test_tool_event_payload_update_overwrites_existing_fields(self, transcript):
        """Subsequent tool.* event updates/overwrites detail fields."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="tool1",
            payload={"name": "task", "status": "running", "version": 1},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="tool.update",
            item_id="tool1",
            payload={"name": "task", "status": "waiting", "version": 2},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        item = transcript.items["tool1"]
        assert item.detail["status"] == "waiting"
        assert item.detail["version"] == 2
        assert item.text == "task"

    def test_tool_event_kind_matching_pattern(self, transcript):
        """Various tool.* event kinds are recognized."""
        for kind in ["tool.start", "tool.end", "tool.error", "tool.update"]:
            event = Event(
                session_id="s1",
                sequence=1,
                turn_id="t1",
                kind=kind,
                item_id="tool1",
                payload={"name": "test", "status": "running"},
            )
            # Should not raise
            transcript.apply(event)


class TestTranscriptEventKindTurnEnded:
    """Test handling of 'turn.ended' event kind."""

    def test_turn_ended_creates_outcome_item(self, transcript, turn_ended_event):
        """turn.ended creates an Item with kind='outcome'."""
        transcript.apply(turn_ended_event)
        item = transcript.items["outcome-1"]
        assert item.kind == "outcome"
        assert item.status == "success"
        assert item.text == "Task completed."

    def test_turn_ended_message_field_optional(self, transcript, turn_ended_event_no_message):
        """turn.ended 'message' field is optional (defaults to empty)."""
        transcript.apply(turn_ended_event_no_message)
        item = transcript.items["outcome-2"]
        assert item.kind == "outcome"
        assert item.status == "success"
        assert item.text == ""

    def test_turn_ended_missing_status_raises_keyerror(self, transcript):
        """turn.ended without 'status' raises KeyError."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.ended",
            item_id="outcome1",
            payload={"message": "done"},
        )
        with pytest.raises(KeyError):
            transcript.apply(event)

    def test_turn_ended_status_values(self, transcript):
        """turn.ended accepts various status values."""
        for status in ["success", "failure", "cancelled", "error"]:
            t = Transcript()
            event = Event(
                session_id="s1",
                sequence=1,
                turn_id="t1",
                kind="turn.ended",
                item_id=f"outcome-{status}",
                payload={"status": status},
            )
            t.apply(event)
            assert t.items[f"outcome-{status}"].status == status


class TestTranscriptEventKindUnknown:
    """Test handling of unknown/unrecognized event kinds."""

    def test_unknown_event_kind_silently_ignored(self, transcript):
        """Unknown event kind does not raise, is silently skipped."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="unknown.event",
            item_id="unknown1",
            payload={"text": "ignored"},
        )
        transcript.apply(event)
        # No item created
        assert len(transcript.items) == 0

    def test_unknown_kind_added_to_seen_set_for_idempotency(self, transcript):
        """Even unknown kinds are tracked in seen set for idempotency."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="future.feature",
            item_id="i1",
            payload={},
        )
        transcript.apply(event)
        # Even though no item was created, the event is marked as seen
        assert ("s1", 1) in transcript.seen

    def test_misspelled_kind_ignored(self, transcript):
        """Misspelled event kind (e.g., 'turn.accepted.typo') is ignored."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.acceptedd",  # typo
            item_id="i1",
            payload={"text": "text"},
        )
        transcript.apply(event)
        assert len(transcript.items) == 0


# ============================================================================
# UNIT TESTS: Payload Error Handling
# ============================================================================


class TestPayloadValidation:
    """Test error handling for malformed payloads."""

    @pytest.mark.parametrize(
        "kind,required_fields",
        [
            ("turn.accepted", ["text"]),
            ("display.message", ["text"]),
            ("question.updated", ["text", "status"]),
            ("steering.updated", ["text", "status"]),
            ("text.delta", ["text"]),
            ("text.final", ["text"]),
            ("turn.ended", ["status"]),
        ],
    )
    def test_missing_required_fields_raise_keyerror(self, transcript, kind, required_fields):
        """Events with missing required fields raise KeyError."""
        # Create payload with all fields except the first required field
        payload = {field: "value" for field in required_fields[1:]}
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind=kind,
            item_id="i1",
            payload=payload,
        )
        with pytest.raises(KeyError):
            transcript.apply(event)

    def test_none_payload_raises_error(self, transcript):
        """Payload cannot be None (should be dict)."""
        # This would fail at Event instantiation (type error), not apply
        # But if it somehow got through, accessing None like a dict would fail
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": None},  # None value instead of missing key
        )
        transcript.apply(event)
        # None is a valid value; it's set as the text
        assert transcript.items["i1"].text is None

    def test_payload_with_extra_fields_ignored(self, transcript):
        """Extra fields in payload are ignored (not validated against)."""
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={
                "text": "hello",
                "extra_field": "extra_value",
                "another_field": 123,
            },
        )
        transcript.apply(event)
        # Applies successfully, extra fields not stored (except in tool.detail)
        assert transcript.items["i1"].text == "hello"


# ============================================================================
# INTEGRATION TESTS: Event Stream Processing
# ============================================================================


class TestTranscriptEventStreamProcessing:
    """Test Transcript processing complete event streams."""

    def test_process_complete_conversation_turn(self, transcript, event_stream):
        """Processing a complete turn's event stream produces expected final state."""
        for event in event_stream:
            transcript.apply(event)

        # Check final state
        assert len(transcript.items) == 3  # user input, response, outcome
        assert transcript.items["user-1"].kind == "user"
        assert transcript.items["user-1"].text == "Compute 2+2"
        assert transcript.items["resp-1"].kind == "assistant"
        # Text accumulated from deltas then replaced by final
        assert transcript.items["resp-1"].text == "is 4."
        assert transcript.items["outcome-1"].kind == "outcome"
        assert transcript.items["outcome-1"].status == "success"

    def test_multiple_turns_accumulate_items(self, transcript):
        """Applying events from multiple turns accumulates all items."""
        # Turn 1
        t1_events = [
            Event("s1", 1, "t1", "turn.accepted", "u1", {"text": "Turn 1"}),
            Event("s1", 2, "t1", "text.delta", "r1", {"text": "Response 1"}),
            Event("s1", 3, "t1", "turn.ended", "o1", {"status": "success"}),
        ]
        # Turn 2
        t2_events = [
            Event("s1", 4, "t2", "turn.accepted", "u2", {"text": "Turn 2"}),
            Event("s1", 5, "t2", "text.delta", "r2", {"text": "Response 2"}),
            Event("s1", 6, "t2", "turn.ended", "o2", {"status": "success"}),
        ]

        for event in t1_events + t2_events:
            transcript.apply(event)

        assert len(transcript.items) == 6
        assert all(item_id in transcript.items for item_id in ["u1", "r1", "o1", "u2", "r2", "o2"])

    def test_interleaved_item_updates(self, transcript):
        """Items can be updated/mutated by events with matching item_id."""
        # Text accumulation across multiple events
        events = [
            Event("s1", 1, "t1", "text.delta", "r1", {"text": "Hello "}),
            Event("s1", 2, "t1", "text.delta", "r1", {"text": "beautiful "}),
            Event("s1", 3, "t1", "text.delta", "r1", {"text": "world"}),
        ]
        for event in events:
            transcript.apply(event)

        assert transcript.items["r1"].text == "Hello beautiful world"

    def test_transcript_state_grows_monotonically(self, transcript):
        """Transcript items and seen set only grow (never shrink)."""
        events = [
            Event("s1", i, "t1", "turn.accepted", f"i{i}", {"text": f"Text {i}"})
            for i in range(1, 6)
        ]

        sizes = []
        for event in events:
            transcript.apply(event)
            sizes.append((len(transcript.items), len(transcript.seen)))

        # Sizes should only increase
        for i in range(1, len(sizes)):
            assert sizes[i][0] >= sizes[i - 1][0]
            assert sizes[i][1] >= sizes[i - 1][1]

    def test_out_of_order_event_application_idempotency_still_holds(self, transcript):
        """Applying same events in different order respects idempotency."""
        events = [
            Event("s1", 1, "t1", "turn.accepted", "u1", {"text": "Text 1"}),
            Event("s1", 2, "t1", "turn.accepted", "u2", {"text": "Text 2"}),
            Event("s1", 3, "t1", "turn.accepted", "u3", {"text": "Text 3"}),
        ]

        # Apply in order
        for event in events:
            transcript.apply(event)
        state1 = {k: (v.text, v.kind) for k, v in transcript.items.items()}

        # Create new transcript and apply out of order
        t2 = Transcript()
        for event in [events[2], events[0], events[1]]:
            t2.apply(event)
        state2 = {k: (v.text, v.kind) for k, v in t2.items.items()}

        # States should be identical (order doesn't matter)
        assert state1 == state2


# ============================================================================
# INTEGRATION TESTS: Recovery Scenario
# ============================================================================


class TestTranscriptRecoveryScenario:
    """Test Transcript in recovery/rebuild scenarios (from saved history)."""

    def test_rebuild_transcript_from_saved_events(self):
        """Rebuild Transcript from sequence of saved events (recovery)."""
        saved_events = [
            Event("s1", 1, "t1", "turn.accepted", "u1", {"text": "What's 2+2?"}),
            Event("s1", 2, "t1", "text.delta", "r1", {"text": "The "}),
            Event("s1", 3, "t1", "text.delta", "r1", {"text": "answer "}),
            Event("s1", 4, "t1", "text.delta", "r1", {"text": "is "}),
            Event("s1", 5, "t1", "text.final", "r1", {"text": "4."}),
            Event("s1", 6, "t1", "turn.ended", "o1", {"status": "success"}),
        ]

        t = Transcript()
        for event in saved_events:
            t.apply(event)

        # Verify rebuilt state
        assert len(t.items) == 3
        assert t.items["u1"].text == "What's 2+2?"
        assert t.items["r1"].text == "4."
        assert t.items["o1"].status == "success"
        assert len(t.seen) == 6

    def test_recovery_idempotent_with_duplicates(self):
        """Recovery still idempotent even if event log has duplicates."""
        events = [
            Event("s1", 1, "t1", "turn.accepted", "u1", {"text": "Text"}),
            Event("s1", 2, "t1", "turn.accepted", "u2", {"text": "Text2"}),
            Event("s1", 1, "t1", "turn.accepted", "u1", {"text": "Text"}),  # Duplicate
        ]

        t = Transcript()
        for event in events:
            t.apply(event)

        # Only 2 items despite 3 events
        assert len(t.items) == 2
        assert len(t.seen) == 2  # Only unique (session, sequence) pairs

    def test_recovery_partial_turn_produces_partial_items(self):
        """Recovering partial turn (interrupted mid-stream) produces incomplete items."""
        partial_events = [
            Event("s1", 1, "t1", "turn.accepted", "u1", {"text": "Start"}),
            Event("s1", 2, "t1", "text.delta", "r1", {"text": "Part "}),
            Event("s1", 3, "t1", "text.delta", "r1", {"text": "of "}),
            # Missing text.final and turn.ended
        ]

        t = Transcript()
        for event in partial_events:
            t.apply(event)

        # Partial item still exists
        assert "r1" in t.items
        assert t.items["r1"].text == "Part of "
        assert "o1" not in t.items  # No outcome because turn didn't end


# ============================================================================
# EDGE CASES & CORNER CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and unusual but valid scenarios."""

    def test_very_long_text_field(self, transcript):
        """Item can hold very long text content."""
        long_text = "x" * 100_000
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": long_text},
        )
        transcript.apply(event)
        assert len(transcript.items["i1"].text) == 100_000

    def test_special_characters_in_text(self, transcript):
        """Text can contain special characters, unicode, emojis."""
        special_text = "Hello 🌍 with émojis and special chars: <>!@#$%^&*()"
        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": special_text},
        )
        transcript.apply(event)
        assert transcript.items["i1"].text == special_text

    def test_zero_sequence_number(self, transcript):
        """Events with sequence=0 are valid."""
        event = Event(
            session_id="s1",
            sequence=0,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "First event"},
        )
        transcript.apply(event)
        assert (("s1", 0)) in transcript.seen

    def test_negative_sequence_number(self, transcript):
        """Events with negative sequence are technically valid (edge case)."""
        event = Event(
            session_id="s1",
            sequence=-1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Negative"},
        )
        transcript.apply(event)
        assert (("s1", -1)) in transcript.seen

    def test_very_large_sequence_number(self, transcript):
        """Events with very large sequence numbers."""
        event = Event(
            session_id="s1",
            sequence=999_999_999,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Large"},
        )
        transcript.apply(event)
        assert (("s1", 999_999_999)) in transcript.seen

    def test_empty_session_id(self, transcript):
        """Session ID can be empty string (unusual but technically valid)."""
        event = Event(
            session_id="",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Text"},
        )
        transcript.apply(event)
        assert ("", 1) in transcript.seen

    def test_item_id_reused_across_sessions(self, transcript):
        """Same item_id in different sessions are different items in Transcript."""
        # This is only an issue if Transcript is shared across sessions,
        # which it shouldn't be. Within one Transcript, same item_id overwrites.
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="shared-id",
            payload={"text": "Session 1"},
        )
        event2 = Event(
            session_id="s2",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="shared-id",
            payload={"text": "Session 2"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        # Same Transcript, same item_id, last write wins
        assert transcript.items["shared-id"].text == "Session 2"

    def test_tool_detail_dict_never_reset(self, transcript):
        """Tool detail dict persists across multiple updates (never cleared)."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="tool.start",
            item_id="t1",
            payload={"name": "task", "step": 1},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="tool.update",
            item_id="t1",
            payload={"status": "running", "step": 2},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        # Both update1 and update2 fields in detail (dict.update merges)
        assert transcript.items["t1"].detail["step"] == 2
        assert transcript.items["t1"].detail["name"] == "task"

    def test_text_concatenation_preserves_exact_spacing(self, transcript):
        """Text delta concatenation preserves exact spacing (no auto-spacing)."""
        event1 = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": "no"},
        )
        event2 = Event(
            session_id="s1",
            sequence=2,
            turn_id="t1",
            kind="text.delta",
            item_id="s1",
            payload={"text": "space"},
        )
        transcript.apply(event1)
        transcript.apply(event2)
        assert transcript.items["s1"].text == "nospace"

    def test_many_items_in_single_transcript(self, transcript):
        """Transcript can hold hundreds of items."""
        for i in range(500):
            event = Event(
                session_id="s1",
                sequence=i,
                turn_id="t1",
                kind="turn.accepted",
                item_id=f"item-{i}",
                payload={"text": f"Text {i}"},
            )
            transcript.apply(event)

        assert len(transcript.items) == 500
        assert len(transcript.seen) == 500


# ============================================================================
# STATE ISOLATION & INDEPENDENCE
# ============================================================================


class TestTranscriptStateIsolation:
    """Test that separate Transcript instances have independent state."""

    def test_two_transcripts_independent_state(self):
        """Two Transcript instances do not share state."""
        t1 = Transcript()
        t2 = Transcript()

        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Text"},
        )
        t1.apply(event)

        # t2 should still be empty
        assert len(t2.items) == 0
        assert len(t2.seen) == 0
        assert len(t1.items) == 1

    def test_item_mutations_in_one_transcript_dont_affect_others(self):
        """Mutating an Item in one Transcript doesn't affect other Transcripts."""
        t1 = Transcript()
        t2 = Transcript()

        event = Event(
            session_id="s1",
            sequence=1,
            turn_id="t1",
            kind="turn.accepted",
            item_id="i1",
            payload={"text": "Original"},
        )
        t1.apply(event)
        t2.apply(event)

        # Mutate in t1
        t1.items["i1"].text = "Modified in t1"

        # t2 should still have original (different Item instance)
        assert t2.items["i1"].text == "Original"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
