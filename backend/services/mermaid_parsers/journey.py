"""
User Journey diagram parser and differ.

Supports mermaid journey diagrams with sections and tasks.

Syntax:
    journey
        title My Journey
        section Section Name
            Task name: rating: actor1, actor2
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


# ── Journey model ─────────────────────────────────────────────────────────────

@dataclass
class JourneyTask:
    name: str
    rating: int  # 1-5
    actors: list[str] = field(default_factory=list)


@dataclass
class JourneySection:
    name: str
    tasks: list[JourneyTask] = field(default_factory=list)


@dataclass
class JourneyModel(DiagramModel):
    title: str | None = None
    sections: list[JourneySection] = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────────────

_TASK_RE = re.compile(
    r"^\s*(.+?)\s*:\s*(\d+)\s*(?::\s*(.+))?\s*$"
)


class JourneyParser(DiagramParser):
    """Parser for mermaid user journey diagrams."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split("\n", 1)[0].strip().lower()
        return first_line == "journey"

    def parse(self, source: str) -> JourneyModel:
        lines = source.strip().splitlines()
        model = JourneyModel()
        current_section: JourneySection | None = None

        for line in lines[1:]:  # skip 'journey' header
            stripped = line.strip()
            if not stripped or stripped.startswith("%%"):
                continue

            # Title
            if stripped.lower().startswith("title "):
                model.title = stripped[6:].strip()
                continue

            # Section
            if stripped.lower().startswith("section "):
                current_section = JourneySection(name=stripped[8:].strip())
                model.sections.append(current_section)
                continue

            # Task line: "Task name: rating: actor1, actor2"
            m = _TASK_RE.match(stripped)
            if m:
                task_name = m.group(1)
                rating = int(m.group(2))
                rating = max(1, min(5, rating))
                actors_str = m.group(3)
                actors = (
                    [a.strip() for a in actors_str.split(",") if a.strip()]
                    if actors_str
                    else []
                )
                task = JourneyTask(name=task_name, rating=rating, actors=actors)
                if current_section is None:
                    # Create an implicit section
                    current_section = JourneySection(name="")
                    model.sections.append(current_section)
                current_section.tasks.append(task)

        return model


# ── Differ ────────────────────────────────────────────────────────────────────

class JourneyDiffer(DiagramDiffer):
    """Differ for mermaid user journey diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, JourneyModel)
        assert isinstance(new, JourneyModel)

        changes: list[str] = []
        annotated_lines: list[str] = ["journey"]

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

        # Build section maps
        old_sections = {s.name: s for s in old.sections}
        new_sections = {s.name: s for s in new.sections}

        old_names = [s.name for s in old.sections]
        new_names = [s.name for s in new.sections]

        # Process new sections in order
        for section_name in new_names:
            section = new_sections[section_name]
            if section_name not in old_sections:
                # Added section
                annotated_lines.append(f"    section {section_name} [+]")
                changes.append(f"section_added:{section_name}")
                for task in section.tasks:
                    actors_str = (
                        ": " + ", ".join(task.actors) if task.actors else ""
                    )
                    annotated_lines.append(
                        f"        {task.name} [+]: {task.rating}{actors_str}"
                    )
            else:
                # Existing section - diff tasks
                old_section = old_sections[section_name]
                section_changes = self._diff_tasks(old_section, section)
                if section_changes["has_changes"]:
                    annotated_lines.append(f"    section {section_name} [~]")
                    changes.append(f"section_changed:{section_name}")
                else:
                    annotated_lines.append(f"    section {section_name}")
                annotated_lines.extend(section_changes["lines"])

        # Removed sections (in old but not in new)
        for section_name in old_names:
            if section_name not in new_sections:
                section = old_sections[section_name]
                annotated_lines.append(f"    section {section_name} [-]")
                changes.append(f"section_removed:{section_name}")
                for task in section.tasks:
                    actors_str = (
                        ": " + ", ".join(task.actors) if task.actors else ""
                    )
                    annotated_lines.append(
                        f"        {task.name} [-]: {task.rating}{actors_str}"
                    )

        if not changes:
            return DiffResult(has_changes=False)

        return DiffResult(
            has_changes=True, annotated_source="\n".join(annotated_lines)
        )

    def _diff_tasks(
        self, old_section: JourneySection, new_section: JourneySection
    ) -> dict:
        """Diff tasks within a section. Returns dict with 'has_changes' and 'lines'."""
        old_tasks = {t.name: t for t in old_section.tasks}
        new_tasks = {t.name: t for t in new_section.tasks}
        lines: list[str] = []
        has_changes = False

        # Process tasks in new section order
        for task in new_section.tasks:
            actors_str = (
                ": " + ", ".join(task.actors) if task.actors else ""
            )
            if task.name not in old_tasks:
                # Added task
                lines.append(
                    f"        {task.name} [+]: {task.rating}{actors_str}"
                )
                has_changes = True
            else:
                old_task = old_tasks[task.name]
                task_markers: list[str] = []
                if old_task.rating != task.rating:
                    task_markers.append(
                        f"~ {old_task.rating}->{task.rating}"
                    )
                if old_task.actors != task.actors:
                    task_markers.append("~ actors")
                if task_markers:
                    marker = " [" + ", ".join(task_markers) + "]"
                    lines.append(
                        f"        {task.name}{marker}: {task.rating}{actors_str}"
                    )
                    has_changes = True
                else:
                    lines.append(
                        f"        {task.name}: {task.rating}{actors_str}"
                    )

        # Removed tasks (in old but not in new)
        for task in old_section.tasks:
            if task.name not in new_tasks:
                actors_str = (
                    ": " + ", ".join(task.actors) if task.actors else ""
                )
                lines.append(
                    f"        {task.name} [-]: {task.rating}{actors_str}"
                )
                has_changes = True

        return {"has_changes": has_changes, "lines": lines}
