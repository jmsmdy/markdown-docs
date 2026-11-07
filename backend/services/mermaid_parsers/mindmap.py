"""
Mindmap diagram parser and differ.

Supports mermaid mindmap diagrams with indentation-based hierarchy.

Syntax:
    mindmap
        root((Central idea))
            Child 1
                Grandchild
            [Square child]
            ))Cloud child((
            {{Hexagon child}}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.services.mermaid_parsers.base import (
    DiagramDiffer,
    DiagramModel,
    DiagramParser,
    DiffResult,
)


# ── Mindmap model ─────────────────────────────────────────────────────────────

@dataclass
class MindmapNode:
    text: str
    shape: str = "plain"  # plain, round, square, cloud, hexagon
    children: list["MindmapNode"] = field(default_factory=list)
    raw: str = ""  # original line content for re-emission


@dataclass
class MindmapModel(DiagramModel):
    root: MindmapNode | None = None


# ── Shape parsing ─────────────────────────────────────────────────────────────

# Shape patterns: order matters (check longer delimiters first)
_SHAPE_PATTERNS: list[tuple[str, str, str, str]] = [
    # (open, close, shape_name, regex-safe open, regex-safe close)
    ("))","((", "cloud", r"\)\)", r"\(\("),
    ("{{","}}", "hexagon", r"\{\{", r"\}\}"),
    ("((","))", "round", r"\(\(", r"\)\)"),
    ("([","])", "stadium", r"\(\[", r"\]\)"),
    ("(",")", "round", r"\(", r"\)"),
    ("[","]", "square", r"\[", r"\]"),
]


def _parse_node_content(text: str) -> tuple[str, str]:
    """Parse node text and determine shape. Returns (text, shape)."""
    text = text.strip()

    # root(...) special case
    if text.lower().startswith("root(") and text.endswith(")"):
        inner = text[5:-1].strip()
        # Check if it's root((text))
        if inner.startswith("(") and inner.endswith(")"):
            return inner[1:-1].strip(), "round"
        return inner, "round"

    # Check shape patterns
    for open_d, close_d, shape, _, _ in _SHAPE_PATTERNS:
        if text.startswith(open_d) and text.endswith(close_d):
            inner = text[len(open_d):-len(close_d)].strip()
            return inner, shape

    return text, "plain"


# ── Parser ────────────────────────────────────────────────────────────────────

class MindmapParser(DiagramParser):
    """Parser for mermaid mindmap diagrams."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split("\n", 1)[0].strip().lower()
        return first_line == "mindmap"

    def parse(self, source: str) -> MindmapModel:
        lines = source.strip().splitlines()
        model = MindmapModel()

        if len(lines) < 2:
            return model

        # Build tree from indentation
        # Stack: list of (indent_level, node)
        stack: list[tuple[int, MindmapNode]] = []

        for line in lines[1:]:  # skip 'mindmap' header
            if not line.strip() or line.strip().startswith("%%"):
                continue

            # Determine indentation level
            indent = len(line) - len(line.lstrip())
            content = line.strip()

            # Handle ::icon(...) annotations - strip them
            icon_match = re.search(r"::icon\([^)]*\)", content)
            if icon_match:
                content = content[: icon_match.start()].strip()

            if not content:
                continue

            text, shape = _parse_node_content(content)
            node = MindmapNode(text=text, shape=shape, raw=line.rstrip())

            if not stack:
                # First node is root
                model.root = node
                stack.append((indent, node))
            else:
                # Find parent: go up stack until we find a node with less indentation
                while len(stack) > 1 and stack[-1][0] >= indent:
                    stack.pop()

                parent = stack[-1][1]
                parent.children.append(node)
                stack.append((indent, node))

        return model


# ── Differ ────────────────────────────────────────────────────────────────────

class MindmapDiffer(DiagramDiffer):
    """Differ for mermaid mindmap diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, MindmapModel)
        assert isinstance(new, MindmapModel)

        if old.root is None and new.root is None:
            return DiffResult(has_changes=False)

        changes: list[str] = []
        annotated_lines: list[str] = ["mindmap"]

        if new.root is None and old.root is not None:
            # Everything removed
            self._emit_node(old.root, 1, annotated_lines, "[-]")
            changes.append("root_removed")
        elif old.root is None and new.root is not None:
            # Everything added
            self._emit_node(new.root, 1, annotated_lines, "[+]")
            changes.append("root_added")
        else:
            assert old.root is not None and new.root is not None
            self._diff_nodes(old.root, new.root, 1, annotated_lines, changes)

        if not changes:
            return DiffResult(has_changes=False)

        return DiffResult(
            has_changes=True, annotated_source="\n".join(annotated_lines)
        )

    def _diff_nodes(
        self,
        old_node: MindmapNode,
        new_node: MindmapNode,
        depth: int,
        lines: list[str],
        changes: list[str],
    ) -> None:
        """Recursively diff two nodes and their children."""
        indent = "    " * depth
        node_text = self._format_node(new_node)

        # Root text changed
        if old_node.text != new_node.text:
            lines.append(f"{indent}{node_text} [~]")
            changes.append(f"changed:{new_node.text}")
        else:
            lines.append(f"{indent}{node_text}")

        # Diff children by text matching
        old_children = {c.text: c for c in old_node.children}
        new_children = {c.text: c for c in new_node.children}

        # Process new children in order
        for child in new_node.children:
            if child.text in old_children:
                # Recurse
                self._diff_nodes(
                    old_children[child.text], child, depth + 1, lines, changes
                )
            else:
                # Added
                self._emit_node(child, depth + 1, lines, "[+]")
                changes.append(f"added:{child.text}")

        # Removed children
        for child in old_node.children:
            if child.text not in new_children:
                self._emit_node(child, depth + 1, lines, "[-]")
                changes.append(f"removed:{child.text}")

    def _emit_node(
        self,
        node: MindmapNode,
        depth: int,
        lines: list[str],
        marker: str,
    ) -> None:
        """Emit a node and all its children with a marker."""
        indent = "    " * depth
        node_text = self._format_node(node)
        lines.append(f"{indent}{node_text} {marker}")
        for child in node.children:
            self._emit_node(child, depth + 1, lines, marker)

    def _format_node(self, node: MindmapNode) -> str:
        """Format a node with its shape delimiters."""
        shape_delims = {
            "plain": ("", ""),
            "round": ("(", ")"),
            "square": ("[", "]"),
            "cloud": ("))", "(("),
            "hexagon": ("{{", "}}"),
            "stadium": ("([", "])"),
        }
        open_d, close_d = shape_delims.get(node.shape, ("", ""))
        if open_d:
            return f"{open_d}{node.text}{close_d}"
        return node.text
