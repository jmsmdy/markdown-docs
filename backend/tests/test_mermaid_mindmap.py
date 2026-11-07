"""
Tests for mermaid Mindmap diagram parser and differ.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import mermaid_structural_diff
from backend.services.mermaid_parsers.mindmap import (
    MindmapDiffer,
    MindmapModel,
    MindmapNode,
    MindmapParser,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_MINDMAP = """\
mindmap
    root((Central))
        Child 1
        Child 2
"""

NESTED_MINDMAP = """\
mindmap
    root((Central))
        Branch A
            Leaf A1
            Leaf A2
        Branch B
            Leaf B1
"""

SHAPES_MINDMAP = """\
mindmap
    root((Round Root))
        [Square Node]
        ))Cloud Node((
        {{Hexagon Node}}
        (Round Node)
"""


@pytest.fixture
def parser():
    return MindmapParser()


@pytest.fixture
def differ():
    return MindmapDiffer()


# ── Parser tests ──────────────────────────────────────────────────────────────


class TestMindmapCanParse:
    def test_can_parse(self, parser):
        assert parser.can_parse("mindmap\n    root((Test))") is True

    def test_cannot_parse_flowchart(self, parser):
        assert parser.can_parse("graph TD\n    A --> B") is False

    def test_cannot_parse_journey(self, parser):
        assert parser.can_parse("journey\n    title Test") is False


class TestMindmapParse:
    def test_parse_simple_tree(self, parser):
        model = parser.parse(SIMPLE_MINDMAP)
        assert isinstance(model, MindmapModel)
        assert model.root is not None
        assert model.root.text == "Central"
        assert model.root.shape == "round"
        assert len(model.root.children) == 2
        assert model.root.children[0].text == "Child 1"
        assert model.root.children[1].text == "Child 2"

    def test_parse_nested_tree(self, parser):
        model = parser.parse(NESTED_MINDMAP)
        assert model.root is not None
        assert model.root.text == "Central"
        assert len(model.root.children) == 2

        branch_a = model.root.children[0]
        assert branch_a.text == "Branch A"
        assert len(branch_a.children) == 2
        assert branch_a.children[0].text == "Leaf A1"
        assert branch_a.children[1].text == "Leaf A2"

        branch_b = model.root.children[1]
        assert branch_b.text == "Branch B"
        assert len(branch_b.children) == 1
        assert branch_b.children[0].text == "Leaf B1"

    def test_parse_shapes(self, parser):
        model = parser.parse(SHAPES_MINDMAP)
        assert model.root is not None
        assert model.root.text == "Round Root"
        assert model.root.shape == "round"

        children = model.root.children
        assert len(children) == 4
        assert children[0].text == "Square Node"
        assert children[0].shape == "square"
        assert children[1].text == "Cloud Node"
        assert children[1].shape == "cloud"
        assert children[2].text == "Hexagon Node"
        assert children[2].shape == "hexagon"
        assert children[3].text == "Round Node"
        assert children[3].shape == "round"

    def test_parse_empty_mindmap(self, parser):
        model = parser.parse("mindmap\n")
        assert isinstance(model, MindmapModel)
        assert model.root is None


# ── Differ tests ──────────────────────────────────────────────────────────────


class TestMindmapDiff:
    def test_diff_no_changes(self, parser, differ):
        model1 = parser.parse(SIMPLE_MINDMAP)
        model2 = parser.parse(SIMPLE_MINDMAP)
        result = differ.diff(model1, model2)
        assert result.has_changes is False

    def test_diff_added_node(self, parser, differ):
        old = SIMPLE_MINDMAP
        new = """\
mindmap
    root((Central))
        Child 1
        Child 2
        Child 3
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[+]" in result.annotated_source
        assert "Child 3" in result.annotated_source

    def test_diff_removed_node(self, parser, differ):
        old = SIMPLE_MINDMAP
        new = """\
mindmap
    root((Central))
        Child 1
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[-]" in result.annotated_source
        assert "Child 2" in result.annotated_source

    def test_diff_added_subtree(self, parser, differ):
        old = SIMPLE_MINDMAP
        new = """\
mindmap
    root((Central))
        Child 1
            Grandchild 1
            Grandchild 2
        Child 2
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.has_changes is True
        assert "[+]" in result.annotated_source
        assert "Grandchild 1" in result.annotated_source
        assert "Grandchild 2" in result.annotated_source


# ── Integration tests ─────────────────────────────────────────────────────────


class TestMindmapAnnotation:
    def test_annotation_valid_syntax(self, parser, differ):
        """Annotated source should still start with 'mindmap' header."""
        old = SIMPLE_MINDMAP
        new = """\
mindmap
    root((Central))
        Child 1
        Child 2
        Child 3
"""
        model_old = parser.parse(old)
        model_new = parser.parse(new)
        result = differ.diff(model_old, model_new)
        assert result.annotated_source is not None
        lines = result.annotated_source.strip().splitlines()
        assert lines[0].strip() == "mindmap"

    def test_mermaid_structural_diff_integration(self):
        """Test that mindmap diffs work through the mermaid_structural_diff API."""
        old = SIMPLE_MINDMAP
        new = """\
mindmap
    root((Central))
        Child 1
        Child 2
        Child 3
"""
        result = mermaid_structural_diff(old, new)
        assert result is not None
        assert "mindmap" in result
        assert "[+]" in result


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestMindmapGracefulFailure:
    def test_graceful_failure(self, parser):
        """Parser should handle unusual input gracefully."""
        source = """\
mindmap
    root((Test))
        
        Valid Child
"""
        model = parser.parse(source)
        assert isinstance(model, MindmapModel)
        assert model.root is not None
        assert model.root.text == "Test"
        # Blank lines are skipped
        assert len(model.root.children) == 1
        assert model.root.children[0].text == "Valid Child"

    def test_empty_source(self, parser):
        model = parser.parse("mindmap")
        assert isinstance(model, MindmapModel)
        assert model.root is None
