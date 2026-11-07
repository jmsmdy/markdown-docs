"""
Tests for mermaid state diagram parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.state import (
    StateDiagram,
    StateDiffer,
    StateParser,
    StateTransition,
    diff_states,
    generate_annotated_state,
)
from backend.services.mermaid_parsers.base import (
    ADDED_FILL,
    ADDED_STROKE,
    REMOVED_FILL,
    REMOVED_STROKE,
    CHANGED_FILL,
    CHANGED_STROKE,
)


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestStateCanParse:
    def test_can_parse_positive(self):
        parser = StateParser()
        assert parser.can_parse("stateDiagram-v2\n    s1 --> s2")
        assert parser.can_parse("stateDiagram\n    s1 --> s2")
        assert parser.can_parse("StateDiagram-v2\n    s1 --> s2")

    def test_can_parse_negative(self):
        parser = StateParser()
        assert not parser.can_parse("graph TD\n    A --> B")
        assert not parser.can_parse("pie\n    \"A\" : 50")
        assert not parser.can_parse("sequenceDiagram\n    A->>B: msg")


class TestStateParseStates:
    def test_parse_states(self):
        source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Processing
    s3 : Done
    s1 --> s2
    s2 --> s3
'''
        parser = StateParser()
        diagram = parser.parse(source)
        assert "s1" in diagram.states
        assert diagram.states["s1"] == "Idle"
        assert diagram.states["s2"] == "Processing"
        assert diagram.states["s3"] == "Done"

    def test_parse_implicit_states(self):
        source = '''\
stateDiagram-v2
    s1 --> s2
'''
        parser = StateParser()
        diagram = parser.parse(source)
        # States implicitly created from transitions
        assert "s1" in diagram.states
        assert "s2" in diagram.states

    def test_parse_start_end_states(self):
        source = '''\
stateDiagram-v2
    [*] --> s1
    s1 --> [*]
'''
        parser = StateParser()
        diagram = parser.parse(source)
        assert len(diagram.transitions) == 2
        assert diagram.transitions[0].source == "[*]"
        assert diagram.transitions[1].target == "[*]"


class TestStateParseTransitions:
    def test_parse_transitions(self):
        source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Active
    s1 --> s2 : activate
    s2 --> s1 : deactivate
'''
        parser = StateParser()
        diagram = parser.parse(source)
        assert len(diagram.transitions) == 2
        assert diagram.transitions[0].source == "s1"
        assert diagram.transitions[0].target == "s2"
        assert diagram.transitions[0].label == "activate"
        assert diagram.transitions[1].label == "deactivate"

    def test_parse_transition_no_label(self):
        source = '''\
stateDiagram-v2
    s1 --> s2
'''
        parser = StateParser()
        diagram = parser.parse(source)
        assert diagram.transitions[0].label == ""

    def test_parse_composite_state(self):
        source = '''\
stateDiagram-v2
    state s1 {
        a1 : Sub A
        a2 : Sub B
        a1 --> a2
    }
    s1 --> s2
'''
        parser = StateParser()
        diagram = parser.parse(source)
        assert "s1" in diagram.composite_states
        assert "a1" in diagram.composite_states["s1"]
        assert "a2" in diagram.composite_states["s1"]


# ── Diff tests ────────────────────────────────────────────────────────────────

class TestStateDiff:
    def test_diff_no_changes(self):
        old = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[StateTransition("s1", "s2", "go")],
        )
        new = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[StateTransition("s1", "s2", "go")],
        )
        result = diff_states(old, new)
        assert not result.has_changes

    def test_diff_added_state(self):
        old = StateDiagram(
            states={"s1": "Idle"},
            transitions=[],
        )
        new = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[],
        )
        result = diff_states(old, new)
        assert result.has_changes
        assert "s2" in result.added_states
        assert len(result.removed_states) == 0

    def test_diff_removed_state(self):
        old = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[],
        )
        new = StateDiagram(
            states={"s1": "Idle"},
            transitions=[],
        )
        result = diff_states(old, new)
        assert result.has_changes
        assert "s2" in result.removed_states

    def test_diff_changed_label(self):
        old = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[],
        )
        new = StateDiagram(
            states={"s1": "Idle", "s2": "Running"},
            transitions=[],
        )
        result = diff_states(old, new)
        assert result.has_changes
        assert "s2" in result.changed_states

    def test_diff_added_transition(self):
        old = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[StateTransition("s1", "s2", "go")],
        )
        new = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[
                StateTransition("s1", "s2", "go"),
                StateTransition("s2", "s1", "back"),
            ],
        )
        result = diff_states(old, new)
        assert result.has_changes
        assert len(result.added_transitions) == 1
        assert result.added_transitions[0].source == "s2"
        assert result.added_transitions[0].target == "s1"

    def test_diff_removed_transition(self):
        old = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[
                StateTransition("s1", "s2", "go"),
                StateTransition("s2", "s1", "back"),
            ],
        )
        new = StateDiagram(
            states={"s1": "Idle", "s2": "Active"},
            transitions=[StateTransition("s1", "s2", "go")],
        )
        result = diff_states(old, new)
        assert result.has_changes
        assert len(result.removed_transitions) == 1
        assert result.removed_transitions[0].source == "s2"


# ── Annotation tests ──────────────────────────────────────────────────────────

class TestStateAnnotation:
    def test_annotation_valid_syntax(self):
        old_source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Active
    s1 --> s2 : go
'''
        new_source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Active
    s3 : Done
    s1 --> s2 : go
    s2 --> s3 : finish
'''
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert result.startswith("stateDiagram-v2")
        # Should contain classDef for styling
        assert "classDef added" in result
        assert ADDED_FILL in result
        assert "class s3 added" in result

    def test_annotation_removed_state(self):
        old_source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Active
    s1 --> s2
'''
        new_source = '''\
stateDiagram-v2
    s1 : Idle
    s1 --> s1
'''
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert "classDef removed" in result
        assert "class s2 removed" in result

    def test_annotation_changed_label(self):
        old_source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Active
    s1 --> s2
'''
        new_source = '''\
stateDiagram-v2
    s1 : Idle
    s2 : Running
    s1 --> s2
'''
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert "classDef changed" in result
        assert "class s2 changed" in result


# ── Graceful failure tests ────────────────────────────────────────────────────

class TestStateGracefulFailure:
    def test_graceful_failure(self):
        """Malformed input returns None via mermaid_structural_diff."""
        result = mermaid_structural_diff("not a diagram", "also not")
        assert result is None

    def test_mismatched_types_returns_none(self):
        """Different diagram types return None."""
        state_source = "stateDiagram-v2\n    s1 --> s2"
        pie_source = 'pie\n    "A" : 50'
        result = mermaid_structural_diff(state_source, pie_source)
        assert result is None
