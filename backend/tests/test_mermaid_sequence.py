"""
Tests for mermaid sequence diagram parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.sequence import (
    Message,
    Note,
    Participant,
    SequenceDiagram,
    SequenceDiffer,
    SequenceParser,
    diff_sequences,
    generate_annotated_sequence,
)


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestSequenceCanParse:
    def test_can_parse_positive(self):
        parser = SequenceParser()
        assert parser.can_parse("sequenceDiagram\n    A->>B: Hello")
        assert parser.can_parse("sequenceDiagram\n    participant A")
        assert parser.can_parse("SequenceDiagram\n    A->>B: msg")

    def test_can_parse_negative(self):
        parser = SequenceParser()
        assert not parser.can_parse("graph TD\n    A --> B")
        assert not parser.can_parse("pie\n    \"A\" : 50")
        assert not parser.can_parse("stateDiagram-v2\n    s1 --> s2")


class TestSequenceParseParticipants:
    def test_parse_participants(self):
        source = '''\
sequenceDiagram
    participant A as Alice
    participant B as Bob
    A->>B: Hello
'''
        parser = SequenceParser()
        diagram = parser.parse(source)
        assert len(diagram.participants) == 2
        assert diagram.participants[0].id == "A"
        assert diagram.participants[0].alias == "Alice"
        assert diagram.participants[1].id == "B"
        assert diagram.participants[1].alias == "Bob"

    def test_parse_implicit_participants(self):
        source = '''\
sequenceDiagram
    Alice->>Bob: Hello
'''
        parser = SequenceParser()
        diagram = parser.parse(source)
        # Implicit participants discovered from messages
        ids = {p.id for p in diagram.participants}
        assert "Alice" in ids
        assert "Bob" in ids


class TestSequenceParseMessages:
    def test_parse_messages(self):
        source = '''\
sequenceDiagram
    participant A
    participant B
    A->>B: Hello
    B-->>A: Reply
    A->B: Sync
'''
        parser = SequenceParser()
        diagram = parser.parse(source)
        assert len(diagram.messages) == 3
        assert diagram.messages[0].sender == "A"
        assert diagram.messages[0].receiver == "B"
        assert diagram.messages[0].arrow_type == "->>"
        assert diagram.messages[0].text == "Hello"
        assert diagram.messages[1].arrow_type == "-->>"
        assert diagram.messages[1].text == "Reply"
        assert diagram.messages[2].arrow_type == "->"

    def test_parse_various_arrows(self):
        source = '''\
sequenceDiagram
    A->>B: async
    A-->>B: async dashed
    A->B: sync
    A-->B: sync dashed
    A-xB: cross
    A--xB: cross dashed
    A-)B: open
    A--)B: open dashed
'''
        parser = SequenceParser()
        diagram = parser.parse(source)
        arrows = [m.arrow_type for m in diagram.messages]
        assert "->>" in arrows
        assert "-->>" in arrows
        assert "->" in arrows
        assert "-->" in arrows
        assert "-x" in arrows
        assert "--x" in arrows
        assert "-)" in arrows
        assert "--)" in arrows


class TestSequenceParseNotesAndLoops:
    def test_parse_notes_and_loops(self):
        source = '''\
sequenceDiagram
    participant A
    participant B
    Note over A: This is a note
    loop Every minute
        A->>B: ping
    end
'''
        parser = SequenceParser()
        diagram = parser.parse(source)
        assert len(diagram.notes) == 1
        assert diagram.notes[0].position == "over"
        assert diagram.notes[0].participants == ["A"]
        assert diagram.notes[0].text == "This is a note"
        assert len(diagram.groups) == 1
        assert diagram.groups[0].kind == "loop"
        assert diagram.groups[0].label == "Every minute"


# ── Diff tests ────────────────────────────────────────────────────────────────

class TestSequenceDiff:
    def test_diff_no_changes(self):
        old = SequenceDiagram(
            participants=[Participant("A", "Alice"), Participant("B", "Bob")],
            messages=[Message("A", "B", "->>", "Hello")],
        )
        new = SequenceDiagram(
            participants=[Participant("A", "Alice"), Participant("B", "Bob")],
            messages=[Message("A", "B", "->>", "Hello")],
        )
        result = diff_sequences(old, new)
        assert not result.has_changes

    def test_diff_added_participant(self):
        old = SequenceDiagram(
            participants=[Participant("A", "Alice")],
            messages=[],
        )
        new = SequenceDiagram(
            participants=[Participant("A", "Alice"), Participant("B", "Bob")],
            messages=[],
        )
        result = diff_sequences(old, new)
        assert result.has_changes
        assert len(result.added_participants) == 1
        assert result.added_participants[0].id == "B"

    def test_diff_removed_participant(self):
        old = SequenceDiagram(
            participants=[Participant("A", "Alice"), Participant("B", "Bob")],
            messages=[],
        )
        new = SequenceDiagram(
            participants=[Participant("A", "Alice")],
            messages=[],
        )
        result = diff_sequences(old, new)
        assert result.has_changes
        assert len(result.removed_participants) == 1
        assert result.removed_participants[0].id == "B"

    def test_diff_added_message(self):
        old = SequenceDiagram(
            participants=[Participant("A"), Participant("B")],
            messages=[Message("A", "B", "->>", "Hello")],
        )
        new = SequenceDiagram(
            participants=[Participant("A"), Participant("B")],
            messages=[
                Message("A", "B", "->>", "Hello"),
                Message("B", "A", "-->>", "Reply"),
            ],
        )
        result = diff_sequences(old, new)
        assert result.has_changes
        assert len(result.added_messages) == 1
        assert result.added_messages[0].text == "Reply"

    def test_diff_removed_message(self):
        old = SequenceDiagram(
            participants=[Participant("A"), Participant("B")],
            messages=[
                Message("A", "B", "->>", "Hello"),
                Message("B", "A", "-->>", "Reply"),
            ],
        )
        new = SequenceDiagram(
            participants=[Participant("A"), Participant("B")],
            messages=[Message("A", "B", "->>", "Hello")],
        )
        result = diff_sequences(old, new)
        assert result.has_changes
        assert len(result.removed_messages) == 1
        assert result.removed_messages[0].text == "Reply"

    def test_diff_changed_message(self):
        old = SequenceDiagram(
            participants=[Participant("A"), Participant("B")],
            messages=[Message("A", "B", "->>", "Hello")],
        )
        new = SequenceDiagram(
            participants=[Participant("A"), Participant("B")],
            messages=[Message("A", "B", "->>", "Hi there")],
        )
        result = diff_sequences(old, new)
        assert result.has_changes
        assert len(result.changed_messages) == 1
        assert result.changed_messages[0][0].text == "Hello"
        assert result.changed_messages[0][1].text == "Hi there"


# ── Annotation tests ──────────────────────────────────────────────────────────

class TestSequenceAnnotation:
    def test_annotation_valid_syntax(self):
        old_source = '''\
sequenceDiagram
    participant A as Alice
    participant B as Bob
    A->>B: Hello
'''
        new_source = '''\
sequenceDiagram
    participant A as Alice
    participant B as Bob
    participant C as Charlie
    A->>B: Hello
    B->>C: Forward
'''
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert result.startswith("sequenceDiagram")
        assert "[+]" in result

    def test_annotation_removed_participant(self):
        old_source = '''\
sequenceDiagram
    participant A as Alice
    participant B as Bob
    A->>B: Hello
'''
        new_source = '''\
sequenceDiagram
    participant A as Alice
    A->>A: Self
'''
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert "[-]" in result


# ── Graceful failure tests ────────────────────────────────────────────────────

class TestSequenceGracefulFailure:
    def test_graceful_failure(self):
        """Malformed input returns None via mermaid_structural_diff."""
        result = mermaid_structural_diff("not a diagram", "also not")
        assert result is None

    def test_mismatched_types_returns_none(self):
        """Different diagram types return None."""
        seq_source = "sequenceDiagram\n    A->>B: Hello"
        pie_source = 'pie\n    "A" : 50'
        result = mermaid_structural_diff(seq_source, pie_source)
        assert result is None
