"""
Mermaid diagram parser registry.

Provides a dispatcher that selects the appropriate parser and differ
for a given mermaid source string based on diagram type.
"""
from __future__ import annotations

from backend.services.mermaid_parsers.base import (
    DiagramDiffer,
    DiagramParser,
    DiffResult,
)
from backend.services.mermaid_parsers.flowchart import (
    FlowchartDiffer,
    FlowchartParser,
)
from backend.services.mermaid_parsers.class_diagram import (
    ClassDiagramDiffer,
    ClassDiagramParser,
)
from backend.services.mermaid_parsers.er import (
    ERDiagramDiffer,
    ERDiagramParser,
)
from backend.services.mermaid_parsers.gantt import (
    GanttDiagramDiffer,
    GanttDiagramParser,
)
from backend.services.mermaid_parsers.pie import (
    PieDiffer,
    PieParser,
)
from backend.services.mermaid_parsers.sequence import (
    SequenceDiffer,
    SequenceParser,
)
from backend.services.mermaid_parsers.state import (
    StateDiffer,
    StateParser,
)
from backend.services.mermaid_parsers.gitgraph import (
    GitGraphDiffer,
    GitGraphParser,
)
from backend.services.mermaid_parsers.journey import (
    JourneyDiffer,
    JourneyParser,
)
from backend.services.mermaid_parsers.mindmap import (
    MindmapDiffer,
    MindmapParser,
)
from backend.services.mermaid_parsers.timeline import (
    TimelineDiffer,
    TimelineParser,
)

# ── Registry ──────────────────────────────────────────────────────────────────

# Each entry is a (parser, differ) pair. Order matters: first match wins.
_REGISTRY: list[tuple[DiagramParser, DiagramDiffer]] = [
    (FlowchartParser(), FlowchartDiffer()),
    (ClassDiagramParser(), ClassDiagramDiffer()),
    (ERDiagramParser(), ERDiagramDiffer()),
    (GanttDiagramParser(), GanttDiagramDiffer()),
    (PieParser(), PieDiffer()),
    (SequenceParser(), SequenceDiffer()),
    (StateParser(), StateDiffer()),
    (JourneyParser(), JourneyDiffer()),
    (MindmapParser(), MindmapDiffer()),
    (TimelineParser(), TimelineDiffer()),
    (GitGraphParser(), GitGraphDiffer()),
]


def get_parser_and_differ(source: str) -> tuple[DiagramParser, DiagramDiffer] | None:
    """
    Find the appropriate parser and differ for the given mermaid source.

    Returns a (parser, differ) tuple if a matching handler is found,
    or None if no registered parser can handle this diagram type.
    """
    for parser, differ in _REGISTRY:
        if parser.can_parse(source):
            return parser, differ
    return None


__all__ = [
    "get_parser_and_differ",
    "DiffResult",
    "DiagramParser",
    "DiagramDiffer",
]
