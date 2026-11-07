"""
Pie chart diagram parser and differ.

Supports mermaid pie chart diagrams.

Strategy:
  1. Parse both old and new mermaid source into a pie model (title + slices).
  2. Diff by slice label: identify added, removed, and value-changed slices.
  3. Re-emit the diagram with annotated labels:
     - Added slices get " [+]" appended to label
     - Removed slices get " [-]" appended to label
     - Changed slices get " [~]" appended to label
     - %% md-diff: comments explain each change
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


# ── Pie model ─────────────────────────────────────────────────────────────────

@dataclass
class PieSlice:
    label: str
    value: float


@dataclass
class PieChart(DiagramModel):
    title: str | None = None
    slices: list[PieSlice] = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────────────

# Match "Label" : value
_SLICE_RE = re.compile(r'^\s*"([^"]+)"\s*:\s*([0-9]*\.?[0-9]+)\s*$')
_TITLE_RE = re.compile(r'^\s*title\s+(.+)$', re.IGNORECASE)


class PieParser(DiagramParser):
    """Parser for mermaid pie chart diagrams."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split('\n', 1)[0].strip().lower()
        return first_line.startswith('pie')

    def parse(self, source: str) -> PieChart:
        """Parse mermaid pie source into a PieChart model."""
        lines = source.strip().splitlines()
        chart = PieChart()

        for line in lines[1:]:  # skip 'pie' header
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue

            title_match = _TITLE_RE.match(stripped)
            if title_match:
                chart.title = title_match.group(1).strip()
                continue

            slice_match = _SLICE_RE.match(stripped)
            if slice_match:
                label = slice_match.group(1)
                value = float(slice_match.group(2))
                chart.slices.append(PieSlice(label=label, value=value))

        return chart


# ── Differ ────────────────────────────────────────────────────────────────────

@dataclass
class PieDiff:
    added_slices: list[PieSlice] = field(default_factory=list)
    removed_slices: list[PieSlice] = field(default_factory=list)
    changed_slices: list[tuple[PieSlice, PieSlice]] = field(default_factory=list)  # (old, new)

    @property
    def has_changes(self) -> bool:
        return bool(self.added_slices or self.removed_slices or self.changed_slices)


def diff_pies(old: PieChart, new: PieChart) -> PieDiff:
    """Compare two pie charts by slice label."""
    result = PieDiff()

    old_by_label = {s.label: s for s in old.slices}
    new_by_label = {s.label: s for s in new.slices}

    old_labels = set(old_by_label.keys())
    new_labels = set(new_by_label.keys())

    for label in new_labels - old_labels:
        result.added_slices.append(new_by_label[label])

    for label in old_labels - new_labels:
        result.removed_slices.append(old_by_label[label])

    for label in old_labels & new_labels:
        if old_by_label[label].value != new_by_label[label].value:
            result.changed_slices.append((old_by_label[label], new_by_label[label]))

    return result


def generate_annotated_pie(old: PieChart, new: PieChart, diff: PieDiff) -> str:
    """
    Generate annotated pie chart source with diff markers.

    - Added slices: "Label [+]" with %% md-diff: added comment
    - Removed slices: "Label [-]" with %% md-diff: removed comment
    - Changed slices: "Label [~]" with %% md-diff: changed comment
    """
    lines: list[str] = []
    lines.append("pie")

    # Title from new chart (or old if removed)
    title = new.title or old.title
    if title:
        lines.append(f"    title {title}")

    # Track which labels have been emitted
    added_labels = {s.label for s in diff.added_slices}
    removed_labels = {s.label for s in diff.removed_slices}
    changed_labels = {new_s.label for _, new_s in diff.changed_slices}

    # Emit slices from the new chart with annotations
    for s in new.slices:
        if s.label in added_labels:
            lines.append(f'    %% md-diff: added slice "{s.label}"')
            lines.append(f'    "{s.label} [+]" : {s.value}')
        elif s.label in changed_labels:
            old_slice = next(o for o, _ in diff.changed_slices if o.label == s.label)
            lines.append(f'    %% md-diff: changed "{s.label}" value {old_slice.value} -> {s.value}')
            lines.append(f'    "{s.label} [~]" : {s.value}')
        else:
            lines.append(f'    "{s.label}" : {s.value}')

    # Re-insert removed slices
    for s in diff.removed_slices:
        lines.append(f'    %% md-diff: removed slice "{s.label}"')
        lines.append(f'    "{s.label} [-]" : {s.value}')

    return "\n".join(lines)


class PieDiffer(DiagramDiffer):
    """Differ for mermaid pie chart diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, PieChart)
        assert isinstance(new, PieChart)

        result = diff_pies(old, new)

        if not result.has_changes:
            return DiffResult(has_changes=False)

        annotated = generate_annotated_pie(old, new, result)
        return DiffResult(has_changes=True, annotated_source=annotated)
