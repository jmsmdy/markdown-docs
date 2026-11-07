"""
Tests for mermaid pie chart parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.pie import (
    PieChart,
    PieDiffer,
    PieParser,
    PieSlice,
    diff_pies,
    generate_annotated_pie,
)


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestPieCanParse:
    def test_can_parse_positive(self):
        parser = PieParser()
        assert parser.can_parse("pie\n    \"A\" : 30")
        assert parser.can_parse("pie\n    title Chart\n    \"A\" : 30")
        assert parser.can_parse("Pie\n    \"A\" : 30")

    def test_can_parse_negative(self):
        parser = PieParser()
        assert not parser.can_parse("graph TD\n    A --> B")
        assert not parser.can_parse("sequenceDiagram\n    A->>B: msg")
        assert not parser.can_parse("stateDiagram-v2\n    s1 --> s2")


class TestPieParseBasic:
    def test_parse_basic(self):
        source = '''\
pie
    "Dogs" : 45
    "Cats" : 30
    "Birds" : 25
'''
        parser = PieParser()
        chart = parser.parse(source)
        assert isinstance(chart, PieChart)
        assert chart.title is None
        assert len(chart.slices) == 3
        assert chart.slices[0].label == "Dogs"
        assert chart.slices[0].value == 45.0
        assert chart.slices[1].label == "Cats"
        assert chart.slices[1].value == 30.0
        assert chart.slices[2].label == "Birds"
        assert chart.slices[2].value == 25.0

    def test_parse_two_slices(self):
        source = 'pie\n    "Yes" : 70\n    "No" : 30'
        parser = PieParser()
        chart = parser.parse(source)
        assert len(chart.slices) == 2
        assert chart.slices[0].label == "Yes"
        assert chart.slices[1].label == "No"


class TestPieParseWithTitle:
    def test_parse_with_title(self):
        source = '''\
pie
    title Favorite Pets
    "Dogs" : 45
    "Cats" : 30
'''
        parser = PieParser()
        chart = parser.parse(source)
        assert chart.title == "Favorite Pets"
        assert len(chart.slices) == 2


# ── Diff tests ────────────────────────────────────────────────────────────────

class TestPieDiff:
    def test_diff_no_changes(self):
        old = PieChart(slices=[PieSlice("A", 50), PieSlice("B", 50)])
        new = PieChart(slices=[PieSlice("A", 50), PieSlice("B", 50)])
        result = diff_pies(old, new)
        assert not result.has_changes

    def test_diff_added_slice(self):
        old = PieChart(slices=[PieSlice("A", 60)])
        new = PieChart(slices=[PieSlice("A", 60), PieSlice("B", 40)])
        result = diff_pies(old, new)
        assert result.has_changes
        assert len(result.added_slices) == 1
        assert result.added_slices[0].label == "B"
        assert len(result.removed_slices) == 0
        assert len(result.changed_slices) == 0

    def test_diff_removed_slice(self):
        old = PieChart(slices=[PieSlice("A", 60), PieSlice("B", 40)])
        new = PieChart(slices=[PieSlice("A", 60)])
        result = diff_pies(old, new)
        assert result.has_changes
        assert len(result.removed_slices) == 1
        assert result.removed_slices[0].label == "B"

    def test_diff_changed_value(self):
        old = PieChart(slices=[PieSlice("A", 60), PieSlice("B", 40)])
        new = PieChart(slices=[PieSlice("A", 70), PieSlice("B", 30)])
        result = diff_pies(old, new)
        assert result.has_changes
        assert len(result.changed_slices) == 2
        changed_labels = {old_s.label for old_s, _ in result.changed_slices}
        assert "A" in changed_labels
        assert "B" in changed_labels

    def test_diff_multiple_changes(self):
        old = PieChart(slices=[
            PieSlice("A", 50), PieSlice("B", 30), PieSlice("C", 20)
        ])
        new = PieChart(slices=[
            PieSlice("A", 60), PieSlice("D", 40)
        ])
        result = diff_pies(old, new)
        assert result.has_changes
        assert len(result.added_slices) == 1  # D
        assert len(result.removed_slices) == 2  # B, C
        assert len(result.changed_slices) == 1  # A value changed


# ── Annotation tests ──────────────────────────────────────────────────────────

class TestPieAnnotation:
    def test_annotation_valid_syntax(self):
        old_source = '''\
pie
    "Dogs" : 45
    "Cats" : 30
'''
        new_source = '''\
pie
    "Dogs" : 50
    "Cats" : 30
    "Birds" : 20
'''
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert result.startswith("pie")
        # Check markers are present
        assert "[+]" in result
        assert "[~]" in result

    def test_annotation_includes_diff_comments(self):
        old_source = 'pie\n    "A" : 50\n    "B" : 50'
        new_source = 'pie\n    "A" : 50\n    "C" : 50'
        result = mermaid_structural_diff(old_source, new_source)
        assert result is not None
        assert "%% md-diff:" in result


# ── Graceful failure tests ────────────────────────────────────────────────────

class TestPieGracefulFailure:
    def test_graceful_failure(self):
        """Malformed input returns None via mermaid_structural_diff."""
        # Not a pie chart at all
        result = mermaid_structural_diff("not a diagram", "also not a diagram")
        assert result is None

    def test_mismatched_types_returns_none(self):
        """Different diagram types return None."""
        pie_source = 'pie\n    "A" : 50'
        graph_source = 'graph TD\n    A --> B'
        result = mermaid_structural_diff(pie_source, graph_source)
        assert result is None
