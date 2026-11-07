"""
Mermaid structural diff — public API.

This module delegates to the mermaid_parsers package for diagram-type-specific
parsing and diffing. It maintains backward compatibility by re-exporting the
flowchart parser's types and functions.
"""
from __future__ import annotations

from backend.services.mermaid_parsers import get_parser_and_differ

# Re-export for backward compatibility — existing code imports these from here.
from backend.services.mermaid_parsers.flowchart import (  # noqa: F401
    MermaidDiff,
    MermaidEdge,
    MermaidGraph,
    MermaidNode,
    diff_graphs,
    generate_annotated_source,
    parse_mermaid,
)


# ── Public API ────────────────────────────────────────────────────────────────

def mermaid_structural_diff(old_source: str, new_source: str) -> str | None:
    """
    Produce an annotated mermaid source highlighting structural differences
    between old_source and new_source.

    Returns the annotated source string, or None if:
      - Either source is not a supported diagram type
      - There are no structural changes detected
    """
    old_stripped = old_source.strip()
    new_stripped = new_source.strip()

    # Both sources must be parseable by the same diagram type
    old_handler = get_parser_and_differ(old_stripped)
    new_handler = get_parser_and_differ(new_stripped)

    if old_handler is None or new_handler is None:
        return None

    # Use the new source's handler (they should be the same type for now)
    parser, differ = new_handler

    # Verify the old source is also parseable by this parser
    if not parser.can_parse(old_stripped):
        return None

    old_model = parser.parse(old_stripped)
    new_model = parser.parse(new_stripped)

    result = differ.diff(old_model, new_model)

    if not result.has_changes:
        return None

    return result.annotated_source
