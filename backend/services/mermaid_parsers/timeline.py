"""
Timeline diagram parser and differ.

Supports mermaid timeline diagrams with periods and events.

Syntax:
    timeline
        title My Timeline
        2023 : Event 1
             : Event 2
        2024 : Event 3
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.mermaid_parsers.base import (
    DiagramDiffer,
    DiagramModel,
    DiagramParser,
    DiffResult,
)


# ── Timeline model ────────────────────────────────────────────────────────────

@dataclass
class TimelinePeriod:
    label: str
    events: list[str] = field(default_factory=list)


@dataclass
class TimelineModel(DiagramModel):
    title: str | None = None
    periods: list[TimelinePeriod] = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────────────

class TimelineParser(DiagramParser):
    """Parser for mermaid timeline diagrams."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split("\n", 1)[0].strip().lower()
        return first_line == "timeline"

    def parse(self, source: str) -> TimelineModel:
        lines = source.strip().splitlines()
        model = TimelineModel()
        current_period: TimelinePeriod | None = None

        for line in lines[1:]:  # skip 'timeline' header
            stripped = line.strip()
            if not stripped or stripped.startswith("%%"):
                continue

            # Title
            if stripped.lower().startswith("title "):
                model.title = stripped[6:].strip()
                continue

            # Determine if this is a period or event based on indentation
            # and colon separator
            indent = len(line) - len(line.lstrip())

            # Check for "label : event" or just "label" pattern
            if ":" in stripped:
                parts = stripped.split(":", 1)
                label_part = parts[0].strip()
                event_part = parts[1].strip() if len(parts) > 1 else ""

                if indent > 0 and current_period is not None and not label_part:
                    # Continuation event: "    : Event text"
                    if event_part:
                        current_period.events.append(event_part)
                elif label_part:
                    if indent > 0 and current_period is not None:
                        # Indented line with colon could be an event
                        # If it starts with something that looks like a continuation
                        # treat it as a new period with event
                        current_period = TimelinePeriod(label=label_part)
                        model.periods.append(current_period)
                        if event_part:
                            current_period.events.append(event_part)
                    else:
                        # New period with optional first event
                        current_period = TimelinePeriod(label=label_part)
                        model.periods.append(current_period)
                        if event_part:
                            current_period.events.append(event_part)
            else:
                # No colon - could be a period label or indented event
                if indent > 0 and current_period is not None:
                    # Indented line without colon = event
                    current_period.events.append(stripped)
                else:
                    # Non-indented line = new period
                    current_period = TimelinePeriod(label=stripped)
                    model.periods.append(current_period)

        return model


# ── Differ ────────────────────────────────────────────────────────────────────

class TimelineDiffer(DiagramDiffer):
    """Differ for mermaid timeline diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, TimelineModel)
        assert isinstance(new, TimelineModel)

        changes: list[str] = []
        annotated_lines: list[str] = ["timeline"]

        # Title
        if new.title:
            if old.title != new.title:
                annotated_lines.append(f"    title {new.title} [~]")
                changes.append("title_changed")
            else:
                annotated_lines.append(f"    title {new.title}")
        elif old.title and not new.title:
            annotated_lines.append(f"    title {old.title} [-]")
            changes.append("title_removed")

        # Build period maps
        old_periods = {p.label: p for p in old.periods}
        new_periods = {p.label: p for p in new.periods}

        # Process periods in new order
        for period in new.periods:
            if period.label not in old_periods:
                # Added period
                annotated_lines.append(f"    {period.label} [+]")
                changes.append(f"period_added:{period.label}")
                for event in period.events:
                    annotated_lines.append(f"        : {event} [+]")
            else:
                # Existing period - diff events
                old_period = old_periods[period.label]
                event_changes = self._diff_events(old_period, period)
                if event_changes["has_changes"]:
                    annotated_lines.append(f"    {period.label} [~]")
                    changes.append(f"period_changed:{period.label}")
                else:
                    annotated_lines.append(f"    {period.label}")
                annotated_lines.extend(event_changes["lines"])

        # Removed periods
        for period in old.periods:
            if period.label not in new_periods:
                annotated_lines.append(f"    {period.label} [-]")
                changes.append(f"period_removed:{period.label}")
                for event in period.events:
                    annotated_lines.append(f"        : {event} [-]")

        if not changes:
            return DiffResult(has_changes=False)

        return DiffResult(
            has_changes=True, annotated_source="\n".join(annotated_lines)
        )

    def _diff_events(
        self, old_period: TimelinePeriod, new_period: TimelinePeriod
    ) -> dict:
        """Diff events within a period."""
        old_events = set(old_period.events)
        new_events = set(new_period.events)
        lines: list[str] = []
        has_changes = False

        # Events in new period
        for event in new_period.events:
            if event not in old_events:
                lines.append(f"        : {event} [+]")
                has_changes = True
            else:
                lines.append(f"        : {event}")

        # Removed events
        for event in old_period.events:
            if event not in new_events:
                lines.append(f"        : {event} [-]")
                has_changes = True

        return {"has_changes": has_changes, "lines": lines}
