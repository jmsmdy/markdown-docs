"""
Base classes for mermaid diagram parsers and differs.

Each supported diagram type implements DiagramParser and DiagramDiffer
to provide structural diffing with annotated source output.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ── Shared colour constants ───────────────────────────────────────────────────

ADDED_FILL = "#c6efce"
ADDED_STROKE = "#27ae60"
REMOVED_FILL = "#fce4e4"
REMOVED_STROKE = "#e74c3c"
CHANGED_FILL = "#fff3cd"
CHANGED_STROKE = "#f39c12"


# ── Base types ────────────────────────────────────────────────────────────────

@dataclass
class DiffResult:
    """Result of a structural diagram diff."""
    has_changes: bool
    annotated_source: str | None = None


class DiagramModel(ABC):
    """Abstract base for parsed diagram representations."""
    pass


class DiagramParser(ABC):
    """Abstract parser that detects and parses a specific diagram type."""

    @abstractmethod
    def can_parse(self, source: str) -> bool:
        """Return True if this parser can handle the given mermaid source."""
        ...

    @abstractmethod
    def parse(self, source: str) -> DiagramModel:
        """Parse mermaid source into a diagram model."""
        ...


class DiagramDiffer(ABC):
    """Abstract differ that compares two diagram models."""

    @abstractmethod
    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        """
        Compute the structural diff between old and new diagram models.

        Returns a DiffResult with has_changes=True and annotated_source set
        if there are differences, or has_changes=False otherwise.
        """
        ...
