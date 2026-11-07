"""
Flowchart/graph diagram parser and differ.

Supports mermaid graph/flowchart diagrams (LR, RL, TD, TB, BT).

Strategy:
  1. Parse both old and new mermaid source into a graph model (nodes + edges).
  2. Diff by node ID: identify added, removed, and label-changed nodes.
  3. Diff edges: identify added and removed connections.
  4. Re-emit the NEW graph source with appended `style` directives that
     color-code the changes. Removed nodes/edges are re-inserted as
     dashed/ghost elements so the user can see what disappeared.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.services.mermaid_parsers.base import (
    ADDED_FILL,
    ADDED_STROKE,
    CHANGED_FILL,
    CHANGED_STROKE,
    REMOVED_FILL,
    REMOVED_STROKE,
    DiagramDiffer,
    DiagramModel,
    DiagramParser,
    DiffResult,
)


# ── Graph model ───────────────────────────────────────────────────────────────

@dataclass
class MermaidNode:
    id: str
    label: str  # display label (may differ from id)
    shape: str = "rect"  # rect, round, stadium, etc. (for re-emission)
    raw: str = ""  # original line fragment for re-emission


@dataclass
class MermaidEdge:
    source: str
    target: str
    label: str = ""
    style: str = "-->"  # arrow style
    raw: str = ""


@dataclass
class MermaidGraph(DiagramModel):
    direction: str = "TD"  # TD, LR, etc.
    nodes: dict[str, MermaidNode] = field(default_factory=dict)
    edges: list[MermaidEdge] = field(default_factory=list)
    header: str = ""  # "graph TD" or "flowchart LR" etc.


# ── Parser ────────────────────────────────────────────────────────────────────

# Node shapes: id[label], id(label), id{label}, id([label]), id[[label]], id((label)), id>label]
_SHAPE_PATTERNS = [
    (r'\(\[', r'\]\)', 'stadium'),     # ([label])
    (r'\[\[', r'\]\]', 'subroutine'),  # [[label]]
    (r'\(\(', r'\)\)', 'circle'),      # ((label))
    (r'\[/', r'/\]', 'trap_alt'),      # [/label/]  (alt trapezoid)
    (r'\[\\', r'\\\]', 'trap'),        # [\label\]  (trapezoid)
    (r'\{', r'\}', 'diamond'),         # {label}
    (r'\(', r'\)', 'round'),           # (label)
    (r'\[', r'\]', 'rect'),            # [label]
    (r'>', r'\]', 'asymmetric'),       # >label]
]

# Edge patterns: -->, --->, -.->, -.-, ==>, ===>, -- text -->, -. text .->
_EDGE_RE = re.compile(
    r'(?P<style>'
    r'--+>|'          # -->  --->
    r'==+>|'          # ==>  ===>
    r'-\.+-?>|'       # -.-> -..->
    r'--+\s|'         # -- (open, followed by text)
    r'==+\s|'         # == (open, followed by text)
    r'-\.+\s'         # -. (open, followed by text)
    r')'
)

# Full edge with optional label:  A -->|text| B  or  A -- text --> B
# Also handles inline node defs: A[Start] --> B[Process]
_NODE_ID = r'[A-Za-z_][\w]*'
_NODE_WITH_OPTIONAL_DEF = (
    r'(?P<{name}>' + _NODE_ID + r')'
    r'(?:\s*(?:\(\[.*?\]\)|\[\[.*?\]\]|\(\(.*?\)\)|\[/.*?/\]|\[\\.*?\\\]|\{.*?\}|\(.*?\)|\[.*?\]|>.*?\]))?'
)

def _make_edge_re():
    """Build the edge regex with named groups for src/tgt."""
    # We need different group names for different alternatives, so build manually.
    src = r'(?P<src>' + _NODE_ID + r')' + r'(?:\s*(?:\(\[.*?\]\)|\[\[.*?\]\]|\(\(.*?\)\)|\[/.*?/\]|\[\\.*?\\\]|\{.*?\}|\(.*?\)|\[.*?\]|>.*?\]))?'
    tgt1 = r'(?P<tgt1>' + _NODE_ID + r')' + r'(?:\s*(?:\(\[.*?\]\)|\[\[.*?\]\]|\(\(.*?\)\)|\[/.*?/\]|\[\\.*?\\\]|\{.*?\}|\(.*?\)|\[.*?\]|>.*?\]))?'
    tgt2 = r'(?P<tgt2>' + _NODE_ID + r')' + r'(?:\s*(?:\(\[.*?\]\)|\[\[.*?\]\]|\(\(.*?\)\)|\[/.*?/\]|\[\\.*?\\\]|\{.*?\}|\(.*?\)|\[.*?\]|>.*?\]))?'
    tgt3 = r'(?P<tgt3>' + _NODE_ID + r')' + r'(?:\s*(?:\(\[.*?\]\)|\[\[.*?\]\]|\(\(.*?\)\)|\[/.*?/\]|\[\\.*?\\\]|\{.*?\}|\(.*?\)|\[.*?\]|>.*?\]))?'

    return re.compile(
        r'^\s*' + src + r'\s*'
        r'(?:'
            # Style 1: A -->|label| B  or A[X] -->|label| B[Y]
            r'(?P<arrow1>--+>|==+>|-\.+-?>)'
            r'(?:\|(?P<label1>[^|]*)\|)?'
            r'\s*' + tgt1 +
        r'|'
            # Style 2: A -- label --> B
            r'(?P<open>--+|==+|-\.+)\s+'
            r'(?P<label2>[^-=.]+?)\s*'
            r'(?P<arrow2>--+>|==+>|-\.+-?>)'
            r'\s*' + tgt2 +
        r'|'
            # Style 3: A --- B (no arrow, link)
            r'(?P<link>--+|==+|-\.+-?)'
            r'(?:\|(?P<label3>[^|]*)\|)?'
            r'\s*' + tgt3 +
        r')'
    )

_EDGE_LINE_RE = _make_edge_re()

# Header line: graph TD, flowchart LR, etc.
_HEADER_RE = re.compile(
    r'^\s*(?:graph|flowchart)\s+(TD|TB|BT|LR|RL)\s*$', re.IGNORECASE
)

# Node definition: A[label] or A(label) etc. — standalone or in edge context
_NODE_DEF_RE = re.compile(
    r'(?P<id>[A-Za-z_][\w]*)\s*'
    r'(?P<open>\(\[|\[\[|\(\(|\[/|\[\\|\{|\(|\[|>)'
    r'(?P<label>[^)\]}>]*?)'
    r'(?P<close>\]\)|\]\]|\)\)|/\]|\\?\]|\}|\)|\])'
)

# Style/class lines we should pass through
_DIRECTIVE_RE = re.compile(
    r'^\s*(?:style|classDef|class|linkStyle|click)\s+'
)

# Subgraph
_SUBGRAPH_RE = re.compile(r'^\s*subgraph\s+', re.IGNORECASE)
_END_RE = re.compile(r'^\s*end\s*$', re.IGNORECASE)


def parse_mermaid(source: str) -> MermaidGraph:
    """
    Parse a mermaid flowchart/graph source into a MermaidGraph structure.

    Extracts nodes (with labels and shapes) and edges (with labels and styles).
    Handles the common flowchart syntax; ignores directives, subgraph labels,
    and advanced features gracefully.
    """
    graph = MermaidGraph()
    lines = source.strip().splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('%%'):
            continue

        # Header
        header_m = _HEADER_RE.match(stripped)
        if header_m:
            graph.direction = header_m.group(1).upper()
            graph.header = stripped
            continue

        # Skip directives and subgraph/end markers
        if _DIRECTIVE_RE.match(stripped):
            continue
        if _SUBGRAPH_RE.match(stripped) or _END_RE.match(stripped):
            continue

        # Extract node definitions from anywhere in the line
        for m in _NODE_DEF_RE.finditer(stripped):
            node_id = m.group('id')
            label = m.group('label').strip()
            open_delim = m.group('open')

            # Determine shape from delimiter
            shape = 'rect'
            for open_pat, _, shape_name in _SHAPE_PATTERNS:
                if re.match(open_pat, open_delim):
                    shape = shape_name
                    break

            if node_id not in graph.nodes:
                graph.nodes[node_id] = MermaidNode(
                    id=node_id, label=label, shape=shape, raw=m.group(0)
                )
            elif label and not graph.nodes[node_id].label:
                graph.nodes[node_id].label = label
                graph.nodes[node_id].shape = shape
                graph.nodes[node_id].raw = m.group(0)

        # Extract edges
        # Split on & for parallel edges: A & B --> C
        # For now, handle the simple case
        edge_m = _EDGE_LINE_RE.match(stripped)
        if edge_m:
            src = edge_m.group('src')
            if edge_m.group('tgt1'):
                tgt = edge_m.group('tgt1')
                label = edge_m.group('label1') or ''
                arrow = edge_m.group('arrow1')
            elif edge_m.group('tgt2'):
                tgt = edge_m.group('tgt2')
                label = edge_m.group('label2') or ''
                arrow = edge_m.group('arrow2')
            else:
                tgt = edge_m.group('tgt3')
                label = edge_m.group('label3') or ''
                arrow = edge_m.group('link')

            graph.edges.append(MermaidEdge(
                source=src, target=tgt, label=label.strip(),
                style=arrow, raw=stripped,
            ))

            # Ensure referenced nodes exist (even without explicit definitions)
            if src not in graph.nodes:
                graph.nodes[src] = MermaidNode(id=src, label=src, shape='rect')
            if tgt not in graph.nodes:
                graph.nodes[tgt] = MermaidNode(id=tgt, label=tgt, shape='rect')

        # Standalone node reference (just an ID on a line, no shape)
        elif re.match(r'^\s*[A-Za-z_][\w]*\s*$', stripped):
            node_id = stripped.strip()
            if node_id.lower() not in ('graph', 'flowchart', 'end', 'subgraph'):
                if node_id not in graph.nodes:
                    graph.nodes[node_id] = MermaidNode(
                        id=node_id, label=node_id, shape='rect'
                    )

    return graph


# ── Structural diff ───────────────────────────────────────────────────────────

@dataclass
class MermaidDiff:
    """Result of diffing two mermaid graphs."""
    added_nodes: set[str] = field(default_factory=set)
    removed_nodes: set[str] = field(default_factory=set)
    changed_nodes: set[str] = field(default_factory=set)  # label changed
    added_edges: list[MermaidEdge] = field(default_factory=list)
    removed_edges: list[MermaidEdge] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_nodes or self.removed_nodes or self.changed_nodes
            or self.added_edges or self.removed_edges
        )


def diff_graphs(old: MermaidGraph, new: MermaidGraph) -> MermaidDiff:
    """
    Compare two parsed mermaid graphs and identify structural differences.
    """
    result = MermaidDiff()

    old_ids = set(old.nodes.keys())
    new_ids = set(new.nodes.keys())

    result.added_nodes = new_ids - old_ids
    result.removed_nodes = old_ids - new_ids

    # Check for label changes on nodes present in both
    for node_id in old_ids & new_ids:
        if old.nodes[node_id].label != new.nodes[node_id].label:
            result.changed_nodes.add(node_id)

    # Edge comparison: use (source, target, label) as identity
    # This correctly handles parallel edges with different labels (e.g. Yes/No)
    def edge_key(e: MermaidEdge) -> tuple[str, str, str]:
        return (e.source, e.target, e.label)

    old_edge_keys = [edge_key(e) for e in old.edges]
    new_edge_keys = [edge_key(e) for e in new.edges]

    # Use multiset comparison to handle duplicate edges correctly
    old_edge_counts: dict[tuple, int] = {}
    for k in old_edge_keys:
        old_edge_counts[k] = old_edge_counts.get(k, 0) + 1
    new_edge_counts: dict[tuple, int] = {}
    for k in new_edge_keys:
        new_edge_counts[k] = new_edge_counts.get(k, 0) + 1

    # Removed edges: in old but not (enough) in new
    for e in old.edges:
        k = edge_key(e)
        if new_edge_counts.get(k, 0) < old_edge_counts.get(k, 0):
            if k not in {edge_key(re) for re in result.removed_edges}:
                result.removed_edges.append(e)

    # Added edges: in new but not (enough) in old
    for e in new.edges:
        k = edge_key(e)
        if old_edge_counts.get(k, 0) < new_edge_counts.get(k, 0):
            if k not in {edge_key(ae) for ae in result.added_edges}:
                result.added_edges.append(e)

    return result


# ── Annotated source generation ───────────────────────────────────────────────

def _emit_node(node: MermaidNode) -> str:
    """Emit a node definition with its shape."""
    delimiters = {
        'rect': ('[', ']'),
        'round': ('(', ')'),
        'stadium': ('([', '])'),
        'subroutine': ('[[', ']]'),
        'circle': ('((', '))'),
        'diamond': ('{', '}'),
        'asymmetric': ('>', ']'),
    }
    open_d, close_d = delimiters.get(node.shape, ('[', ']'))
    label = node.label if node.label != node.id else node.label
    return f"    {node.id}{open_d}{label}{close_d}"


def _emit_edge(edge: MermaidEdge) -> str:
    """Emit an edge definition."""
    if edge.label:
        return f"    {edge.source} {edge.style}|{edge.label}| {edge.target}"
    return f"    {edge.source} {edge.style} {edge.target}"


def generate_annotated_source(
    old: MermaidGraph,
    new: MermaidGraph,
    diff: MermaidDiff,
) -> str:
    """
    Generate a mermaid source that represents the new graph with visual
    annotations for structural changes:
      - Added nodes: green fill
      - Removed nodes: red fill, dashed stroke (re-inserted as ghost nodes)
      - Changed labels: yellow fill
      - Added edges: rendered normally (new graph has them)
      - Removed edges: re-inserted with original style, colored red via linkStyle

    Returns the full annotated mermaid source string.
    """
    lines: list[str] = []

    # Header
    header = new.header or old.header or f"graph {new.direction or old.direction or 'TD'}"
    lines.append(header)

    # Emit all nodes from the new graph
    emitted_nodes: set[str] = set()
    for node_id, node in new.nodes.items():
        lines.append(_emit_node(node))
        emitted_nodes.add(node_id)

    # Re-insert removed nodes as ghost nodes
    for node_id in diff.removed_nodes:
        node = old.nodes[node_id]
        lines.append(_emit_node(node))
        emitted_nodes.add(node_id)

    # Emit all edges from the new graph, tracking which are added
    edge_index = 0
    added_edge_indices: list[int] = []
    removed_edge_indices: list[int] = []
    added_edge_keys = {(e.source, e.target, e.label) for e in diff.added_edges}
    for edge in new.edges:
        lines.append(_emit_edge(edge))
        if (edge.source, edge.target, edge.label) in added_edge_keys:
            added_edge_indices.append(edge_index)
        edge_index += 1

    # Re-insert removed edges with their original style (colored red via linkStyle)
    for edge in diff.removed_edges:
        lines.append(_emit_edge(edge))
        removed_edge_indices.append(edge_index)
        edge_index += 1

    # Style directives for highlighting
    lines.append("")

    # Added edges: green color via linkStyle
    for idx in added_edge_indices:
        lines.append(
            f"    linkStyle {idx} stroke:{ADDED_STROKE},stroke-width:2px"
        )

    # Removed edges: red color via linkStyle
    for idx in removed_edge_indices:
        lines.append(
            f"    linkStyle {idx} stroke:{REMOVED_STROKE},stroke-width:2px"
        )

    # Added nodes: green
    for node_id in sorted(diff.added_nodes):
        lines.append(
            f"    style {node_id} fill:{ADDED_FILL},"
            f"stroke:{ADDED_STROKE},stroke-width:2px"
        )

    # Removed nodes: red with dashed border
    for node_id in sorted(diff.removed_nodes):
        lines.append(
            f"    style {node_id} fill:{REMOVED_FILL},"
            f"stroke:{REMOVED_STROKE},stroke-width:2px,stroke-dasharray: 5 5"
        )

    # Changed nodes: yellow
    for node_id in sorted(diff.changed_nodes):
        lines.append(
            f"    style {node_id} fill:{CHANGED_FILL},"
            f"stroke:{CHANGED_STROKE},stroke-width:2px"
        )

    return "\n".join(lines)


# ── Parser/Differ classes implementing the base interfaces ────────────────────

class FlowchartParser(DiagramParser):
    """Parser for mermaid flowchart/graph diagrams."""

    def can_parse(self, source: str) -> bool:
        """Check if a mermaid source is a flowchart/graph diagram."""
        first_line = source.strip().split('\n', 1)[0].strip().lower()
        return first_line.startswith('graph ') or first_line.startswith('flowchart ')

    def parse(self, source: str) -> MermaidGraph:
        """Parse mermaid flowchart source into a MermaidGraph."""
        return parse_mermaid(source.strip())


class FlowchartDiffer(DiagramDiffer):
    """Differ for mermaid flowchart/graph diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        """
        Compute structural diff between two MermaidGraph models.

        Returns annotated mermaid source if there are changes.
        """
        assert isinstance(old, MermaidGraph)
        assert isinstance(new, MermaidGraph)

        result = diff_graphs(old, new)

        if not result.has_changes:
            return DiffResult(has_changes=False)

        annotated = generate_annotated_source(old, new, result)
        return DiffResult(has_changes=True, annotated_source=annotated)
