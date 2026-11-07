"""
Tests for mermaid Journey diagram parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.journey import (
    JourneyDiffer,
    JourneyModel,
    JourneyParser,
    JourneySection,
    JourneyTask,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

BASIC_JOURNEY = """\
journey
    title My Working Day
    section Go to work
        Make tea: 5: Me
        Go upstairs: 3: Me, Cat
    section Go home
        Go downstairs: 5: Me
        Sit down: 5: Me
"""

JOURNEY_NO_TITLE = """\
journey
    section Morning
        Wake up: 3: Me
        Breakfast: 4: Me, Partner
"""


@pytest.fixture
def parser():
    return JourneyParser()


@pytest.fixture
def differ():
    return JourneyDiffer()


# ── Parser tests ──────────────────────────────────────────────────────────────


class TestJourneyCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("journey\n    title Test") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_mindmap(self, parser):
        assert parser.can_parse("mindmap\n    root") is False


class TestJourneyParse:
    def test_parse_sections_and_tasks(self, parser):
        model = parser.parse(BASIC_JOURNEY)
        assert isinstance(model, JourneyModel)
        assert model.title == "My Working Day"
        assert len(model.sections) == 2
        assert model.sections[0].name == "Go to work"
        assert model.sections[1].name == "Go home"
        assert len(model.sections[0].tasks) == 2
        assert len(model.sections[1].tasks) == 2

    def test_parse_ratings_and_actors(self, parser):
        model = parser.parse(BASIC_JOURNEY)
        task1 = model.sections[0].tasks[0]
        assert task1.name == "Make tea"
        assert task1.rating == 5
        assert task1.actors == ["Me"]

        task2 = model.sections[0].tasks[1]
        assert task2.name == "Go upstairs"
        assert task2.rating == 3
        assert task2.actors == ["Me", "Cat"]

    def test_parse_no_title(self, parser):
        model = parser.parse(JOURNEY_NO_TITLE)
        assert model.title is None
        assert len(model.sections) == 1

    def test_parse_empty_journey(self, parser):
        model = parser.parse("journey\n")
        assert model.title is None
        assert model.sections == []


# ── Differ tests ──────────────────────────────────────────────────────────────


class TestJourneyDiff:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(BASIC_JOURNEY)
        model2 = parser.parse(BASIC_JOURNEY)
        result = differ.diff(model1, model2)
        assert result.has_changes is False

    def test_diff_added_section(self, parser, differ):
        old = BASIC_JOURNEY
        new = BASIC_JOURNEY + "    section Evening\n        Relax: 5: Me\n"
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[+]" in result.annotated_source
        assert "Evening" in result.annotated_source

    def test_diff_removed_section(self, parser, differ):
        old = BASIC_JOURNEY
        # Remove "Go home" section
        new = """\
journey
    title My Working Day
    section Go to work
        Make tea: 5: Me
        Go upstairs: 3: Me, Cat
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[-]" in result.annotated_source
        assert "Go home" in result.annotated_source

    def test_diff_added_task(self, parser, differ):
        old = BASIC_JOURNEY
        new = """\
journey
    title My Working Day
    section Go to work
        Make tea: 5: Me
        Go upstairs: 3: Me, Cat
        Check email: 4: Me
    section Go home
        Go downstairs: 5: Me
        Sit down: 5: Me
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[+]" in result.annotated_source
        assert "Check email" in result.annotated_source

    def test_diff_removed_task(self, parser, differ):
        old = BASIC_JOURNEY
        new = """\
journey
    title My Working Day
    section Go to work
        Make tea: 5: Me
    section Go home
        Go downstairs: 5: Me
        Sit down: 5: Me
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[-]" in result.annotated_source
        assert "Go upstairs" in result.annotated_source

    def test_diff_changed_rating(self, parser, differ):
        old = BASIC_JOURNEY
        new = """\
journey
    title My Working Day
    section Go to work
        Make tea: 3: Me
        Go upstairs: 3: Me, Cat
    section Go home
        Go downstairs: 5: Me
        Sit down: 5: Me
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "5->3" in result.annotated_source
        assert "Make tea" in result.annotated_source


# ── Integration tests ─────────────────────────────────────────────────────────


class TestJourneyAnnotation:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated source should still start with 'journey' header."""
        old = BASIC_JOURNEY
        new = BASIC_JOURNEY + "    section Evening\n        Relax: 5: Me\n"
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.annotated_source is not None
        lines = result.annotated_source.strip().splitlines()
        assert lines[0].strip() == "journey"

    def test_mermaid_structural_diff_integration(self):
        """Test that journey diffs work through the mermaid_structural_diff API."""
        old = BASIC_JOURNEY
        new = BASIC_JOURNEY + "    section Evening\n        Relax: 5: Me\n"
        result = mermaid_structural_diff(old, new)
        assert result is not None
        assert "journey" in result
        assert "[+]" in result


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestJourneyGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle malformed input gracefully."""
        # Invalid rating (non-numeric parts are skipped)
        source = """\
journey
    section Test
        Bad task: not_a_number: actor
        Good task: 3: Me
"""
        model = parser.parse(source)
        # Should parse what it can, skip what it can't
        assert isinstance(model, JourneyModel)
        # The bad task line won't match the regex, so only good task parsed
        assert len(model.sections) == 1
        assert len(model.sections[0].tasks) == 1
        assert model.sections[0].tasks[0].name == "Good task"

    def test_empty_source(self, parser):
        model = parser.parse("journey")
        assert isinstance(model, JourneyModel)
        assert model.sections == []
