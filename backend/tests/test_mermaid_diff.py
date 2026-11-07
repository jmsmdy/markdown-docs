"""
Tests for mermaid structural diff — parser, diff logic, and annotated source.
"""
from __future__ import annotations

import pytest

from backend.services.mermaid_diff import (
    MermaidEdge,
    MermaidGraph,
    MermaidNode,
    diff_graphs,
    generate_annotated_source,
    mermaid_structural_diff,
    parse_mermaid,
)


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestParseMermaid:
    def test_basic_graph(self):
        source = """\
graph TD
    A[Start] --> B[Process]
    B --> C[End]
"""
        g = parse_mermaid(source)
        assert g.direction == "TD"
        assert "A" in g.nodes
        assert "B" in g.nodes
        assert "C" in g.nodes
        assert g.nodes["A"].label == "Start"
        assert g.nodes["B"].label == "Process"
        assert g.nodes["C"].label == "End"
        assert len(g.edges) == 2

    def test_flowchart_keyword(self):
        source = "flowchart LR\n    X --> Y\n"
        g = parse_mermaid(source)
        assert g.direction == "LR"
        assert "X" in g.nodes
        assert "Y" in g.nodes

    def test_node_shapes(self):
        source = """\
graph TD
    A[Rectangle]
    B(Round)
    C{Diamond}
    D([Stadium])
    E((Circle))
"""
        g = parse_mermaid(source)
        assert g.nodes["A"].shape == "rect"
        assert g.nodes["B"].shape == "round"
        assert g.nodes["C"].shape == "diamond"
        assert g.nodes["D"].shape == "stadium"
        assert g.nodes["E"].shape == "circle"

    def test_edge_with_label(self):
        source = """\
graph LR
    A -->|yes| B
    A -->|no| C
"""
        g = parse_mermaid(source)
        assert len(g.edges) == 2
        edge_labels = {(e.source, e.target): e.label for e in g.edges}
        assert edge_labels[("A", "B")] == "yes"
        assert edge_labels[("A", "C")] == "no"

    def test_edge_label_style2(self):
        source = """\
graph TD
    A -- text --> B
"""
        g = parse_mermaid(source)
        assert len(g.edges) == 1
        assert g.edges[0].label == "text"
        assert g.edges[0].source == "A"
        assert g.edges[0].target == "B"

    def test_implicit_nodes_from_edges(self):
        """Nodes referenced only in edges should still appear in the graph."""
        source = "graph TD\n    A --> B\n"
        g = parse_mermaid(source)
        assert "A" in g.nodes
        assert "B" in g.nodes

    def test_ignores_style_directives(self):
        source = """\
graph TD
    A --> B
    style A fill:#f00
"""
        g = parse_mermaid(source)
        assert len(g.edges) == 1
        assert "A" in g.nodes

    def test_ignores_comments(self):
        source = """\
graph TD
    %% This is a comment
    A --> B
"""
        g = parse_mermaid(source)
        assert len(g.edges) == 1

    def test_empty_source(self):
        g = parse_mermaid("")
        assert g.nodes == {}
        assert g.edges == []

    def test_node_with_spaces_in_label(self):
        source = 'graph TD\n    A[Long Label Here]\n'
        g = parse_mermaid(source)
        assert g.nodes["A"].label == "Long Label Here"


# ── Diff tests ────────────────────────────────────────────────────────────────

class TestDiffGraphs:
    def test_no_changes(self):
        source = "graph TD\n    A[Start] --> B[End]\n"
        old = parse_mermaid(source)
        new = parse_mermaid(source)
        diff = diff_graphs(old, new)
        assert not diff.has_changes
        assert diff.added_nodes == set()
        assert diff.removed_nodes == set()
        assert diff.changed_nodes == set()
        assert diff.added_edges == []
        assert diff.removed_edges == []

    def test_added_node(self):
        old_source = "graph TD\n    A --> B\n"
        new_source = "graph TD\n    A --> B\n    A --> C[New]\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        assert "C" in diff.added_nodes
        assert diff.has_changes

    def test_removed_node(self):
        old_source = "graph TD\n    A --> B\n    A --> C\n"
        new_source = "graph TD\n    A --> B\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        assert "C" in diff.removed_nodes

    def test_changed_label(self):
        old_source = "graph TD\n    A[Old Label] --> B\n"
        new_source = "graph TD\n    A[New Label] --> B\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        assert "A" in diff.changed_nodes
        assert diff.added_nodes == set()
        assert diff.removed_nodes == set()

    def test_added_edge(self):
        old_source = "graph TD\n    A --> B\n"
        new_source = "graph TD\n    A --> B\n    B --> C\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        assert len(diff.added_edges) == 1
        assert diff.added_edges[0].source == "B"
        assert diff.added_edges[0].target == "C"

    def test_removed_edge(self):
        old_source = "graph TD\n    A --> B\n    B --> C\n"
        new_source = "graph TD\n    A --> B\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0].source == "B"
        assert diff.removed_edges[0].target == "C"

    def test_removed_labeled_edge_parallel(self):
        """Removing one of two parallel edges (e.g. Yes/No) should detect it."""
        old_source = "graph TD\n    A -->|Yes| B\n    A -->|No| C\n"
        new_source = "graph TD\n    A -->|Yes| B\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0].source == "A"
        assert diff.removed_edges[0].target == "C"
        assert diff.removed_edges[0].label == "No"

    def test_multiple_changes(self):
        old_source = """\
graph TD
    A[Start] --> B[Middle]
    B --> C[End]
"""
        new_source = """\
graph TD
    A[Start] --> B[Modified]
    B --> D[New End]
"""
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)

        assert "D" in diff.added_nodes
        assert "C" in diff.removed_nodes
        assert "B" in diff.changed_nodes  # label changed


# ── Annotated source generation tests ─────────────────────────────────────────

class TestAnnotatedSource:
    def test_added_node_gets_green_style(self):
        old_source = "graph TD\n    A[Start] --> B[End]\n"
        new_source = "graph TD\n    A[Start] --> B[End]\n    A --> C[New]\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        annotated = generate_annotated_source(old, new, diff)

        assert "style C fill:#c6efce" in annotated
        assert "C" in annotated

    def test_added_edge_gets_green_linkstyle(self):
        old_source = "graph TD\n    A --> B\n"
        new_source = "graph TD\n    A --> B\n    B --> C\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        annotated = generate_annotated_source(old, new, diff)

        # Added edge should get green linkStyle
        assert "linkStyle" in annotated
        assert "#27ae60" in annotated

    def test_removed_node_appears_as_ghost(self):
        old_source = "graph TD\n    A --> B\n    A --> C[Removed]\n"
        new_source = "graph TD\n    A --> B\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        annotated = generate_annotated_source(old, new, diff)

        # Removed node should be re-inserted with red styling
        assert "style C fill:#fce4e4" in annotated
        assert "stroke-dasharray" in annotated
        # Removed edge should be re-inserted with red linkStyle
        assert "linkStyle" in annotated
        assert "#e74c3c" in annotated

    def test_changed_label_gets_yellow_style(self):
        old_source = "graph TD\n    A[Old] --> B\n"
        new_source = "graph TD\n    A[New] --> B\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        annotated = generate_annotated_source(old, new, diff)

        assert "style A fill:#fff3cd" in annotated

    def test_header_preserved(self):
        old_source = "flowchart LR\n    A --> B\n"
        new_source = "flowchart LR\n    A --> B\n    B --> C\n"
        old = parse_mermaid(old_source)
        new = parse_mermaid(new_source)
        diff = diff_graphs(old, new)
        annotated = generate_annotated_source(old, new, diff)

        assert annotated.startswith("flowchart LR")


# ── Integration: mermaid_structural_diff ──────────────────────────────────────

class TestMermaidStructuralDiff:
    def test_returns_annotated_for_flowchart(self):
        old = "graph TD\n    A[Start] --> B[End]\n"
        new = "graph TD\n    A[Start] --> B[End]\n    A --> C[New]\n"
        result = mermaid_structural_diff(old, new)
        assert result is not None
        assert "style C" in result
        assert "graph TD" in result

    def test_returns_none_for_no_changes(self):
        source = "graph TD\n    A --> B\n"
        result = mermaid_structural_diff(source, source)
        assert result is None

    def test_returns_none_for_non_flowchart(self):
        """Non-supported diagram types return None; sequence is now supported."""
        old = "not a diagram\n    something\n"
        new = "not a diagram\n    something else\n"
        result = mermaid_structural_diff(old, new)
        assert result is None

    def test_removed_node_scenario(self):
        """The original bug report: one removed node should show up."""
        old = """\
graph TD
    A[Input] --> B[Process]
    B --> C[Output]
    B --> D[Log]
"""
        new = """\
graph TD
    A[Input] --> B[Process]
    B --> C[Output]
"""
        result = mermaid_structural_diff(old, new)
        assert result is not None
        # D should be shown as removed (red, dashed)
        assert "style D fill:#fce4e4" in result
        assert "stroke-dasharray" in result
        # The removed edge B-->D should be re-inserted and colored red
        assert "linkStyle" in result
        assert "#e74c3c" in result
