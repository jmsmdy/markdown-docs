"""
Tests for mermaid Timeline diagram parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.timeline import (
    TimelineDiffer,
    TimelineModel,
    TimelineParser,
    TimelinePeriod,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

BASIC_TIMELINE = """\
timeline
    title History of Social Media
    2002 : LinkedIn
    2004 : Facebook
         : Google
    2005 : YouTube
"""

TIMELINE_NO_TITLE = """\
timeline
    2020 : Event A
    2021 : Event B
"""


@pytest.fixture
def parser():
    return TimelineParser()


@pytest.fixture
def differ():
    return TimelineDiffer()


# ── Parser tests ──────────────────────────────────────────────────────────────


class TestTimelineCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("timeline\n    title Test") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_mindmap(self, parser):
        assert parser.can_parse("mindmap\n    root") is False


class TestTimelineParse:
    def test_parse_periods_and_events(self, parser):
        model = parser.parse(BASIC_TIMELINE)
        assert isinstance(model, TimelineModel)
        assert len(model.periods) == 3
        assert model.periods[0].label == "2002"
        assert model.periods[0].events == ["LinkedIn"]
        assert model.periods[1].label == "2004"
        assert model.periods[1].events == ["Facebook", "Google"]
        assert model.periods[2].label == "2005"
        assert model.periods[2].events == ["YouTube"]

    def test_parse_with_title(self, parser):
        model = parser.parse(BASIC_TIMELINE)
        assert model.title == "History of Social Media"

    def test_parse_no_title(self, parser):
        model = parser.parse(TIMELINE_NO_TITLE)
        assert model.title is None
        assert len(model.periods) == 2

    def test_parse_empty_timeline(self, parser):
        model = parser.parse("timeline\n")
        assert isinstance(model, TimelineModel)
        assert model.title is None
        assert model.periods == []


# ── Differ tests ──────────────────────────────────────────────────────────────


class TestTimelineDiff:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(BASIC_TIMELINE)
        model2 = parser.parse(BASIC_TIMELINE)
        result = differ.diff(model1, model2)
        assert result.has_changes is False

    def test_diff_added_period(self, parser, differ):
        old = BASIC_TIMELINE
        new = BASIC_TIMELINE.rstrip() + "\n    2006 : Twitter\n"
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[+]" in result.annotated_source
        assert "2006" in result.annotated_source
        assert "Twitter" in result.annotated_source

    def test_diff_removed_period(self, parser, differ):
        old = BASIC_TIMELINE
        new = """\
timeline
    title History of Social Media
    2002 : LinkedIn
    2004 : Facebook
         : Google
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[-]" in result.annotated_source
        assert "2005" in result.annotated_source

    def test_diff_added_event(self, parser, differ):
        old = BASIC_TIMELINE
        new = """\
timeline
    title History of Social Media
    2002 : LinkedIn
         : MySpace
    2004 : Facebook
         : Google
    2005 : YouTube
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[+]" in result.annotated_source
        assert "MySpace" in result.annotated_source

    def test_diff_removed_event(self, parser, differ):
        old = BASIC_TIMELINE
        new = """\
timeline
    title History of Social Media
    2002 : LinkedIn
    2004 : Facebook
    2005 : YouTube
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[-]" in result.annotated_source
        assert "Google" in result.annotated_source


# ── Integration tests ─────────────────────────────────────────────────────────


class TestTimelineAnnotation:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated source should still start with 'timeline' header."""
        old = BASIC_TIMELINE
        new = BASIC_TIMELINE.rstrip() + "\n    2006 : Twitter\n"
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.annotated_source is not None
        lines = result.annotated_source.strip().splitlines()
        assert lines[0].strip() == "timeline"

    def test_mermaid_structural_diff_integration(self):
        """Test that timeline diffs work through the mermaid_structural_diff API."""
        old = BASIC_TIMELINE
        new = BASIC_TIMELINE.rstrip() + "\n    2006 : Twitter\n"
        result = mermaid_structural_diff(old, new)
        assert result is not None
        assert "timeline" in result
        assert "[+]" in result


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestTimelineGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle minimal/unusual input gracefully."""
        source = """\
timeline
    title Just a Title
"""
        model = parser.parse(source)
        assert isinstance(model, TimelineModel)
        assert model.title == "Just a Title"
        assert model.periods == []

    def test_empty_source(self, parser):
        model = parser.parse("timeline")
        assert isinstance(model, TimelineModel)
        assert model.periods == []
