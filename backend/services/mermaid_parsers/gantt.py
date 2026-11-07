"""
Gantt chart parser and differ.

Supports mermaid gantt syntax including title, dateFormat, sections, and tasks.

Strategy:
  1. Parse the gantt header, title, dateFormat, sections, and tasks.
  2. Tasks have names, optional statuses (active, done, crit, milestone),
     start dates or dependencies, and durations.
  3. Diff by section name and task name within sections.
  4. Detect added/removed sections, added/removed tasks, and changed tasks
     (status or timing changes).
  5. Annotate changed tasks with crit status and [+]/[-]/[~] markers.
  6. Re-insert removed sections/tasks.
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


# ── Model ─────────────────────────────────────────────────────────────────────

@dataclass
class GanttTask:
    name: str
    status: str = ""  # active, done, crit, milestone, or combo like "crit, done"
    id: str = ""  # optional task id
    start: str = ""  # date or "after taskId"
    duration: str = ""  # e.g., "3d", "2024-01-05"
    raw: str = ""  # original line for re-emission


@dataclass
class GanttSection:
    name: str
    tasks: list[GanttTask] = field(default_factory=list)


@dataclass
class GanttDiagramModel(DiagramModel):
    title: str = ""
    date_format: str = ""
    sections: list[GanttSection] = field(default_factory=list)


# ── Regex patterns ────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(r'^\s*gantt\s*$', re.IGNORECASE)
_TITLE_RE = re.compile(r'^\s*title\s+(?P<title>.+?)\s*$', re.IGNORECASE)
_DATE_FORMAT_RE = re.compile(r'^\s*dateFormat\s+(?P<format>.+?)\s*$', re.IGNORECASE)
_SECTION_RE = re.compile(r'^\s*section\s+(?P<name>.+?)\s*$', re.IGNORECASE)
_EXCLUDES_RE = re.compile(r'^\s*excludes\s+', re.IGNORECASE)
_AXIS_FORMAT_RE = re.compile(r'^\s*axisFormat\s+', re.IGNORECASE)
_TICK_INTERVAL_RE = re.compile(r'^\s*tickInterval\s+', re.IGNORECASE)

# Task line: TaskName :status, id, start, duration
# Examples:
#   Task A :done, a1, 2024-01-01, 3d
#   Task B :active, after a1, 2d
#   Task C :crit, 2024-01-04, 1d
#   Task D :2024-01-05, 2d
_TASK_RE = re.compile(
    r'^\s*(?P<name>[^:]+?)\s*:\s*(?P<spec>.+?)\s*$'
)

# Known statuses
_STATUSES = {'active', 'done', 'crit', 'milestone'}


def _parse_task_spec(name: str, spec: str) -> GanttTask:
    """Parse the specification part of a task line."""
    task = GanttTask(name=name.strip(), raw=f'{name.strip()} :{spec}')
    parts = [p.strip() for p in spec.split(',')]

    # Extract status tokens from the beginning
    status_parts: list[str] = []
    remaining: list[str] = []
    status_done = False

    for part in parts:
        if not status_done and part.lower() in _STATUSES:
            status_parts.append(part.lower())
        else:
            status_done = True
            remaining.append(part)

    task.status = ', '.join(status_parts)

    # Remaining parts: [id], start, duration
    # If a part looks like an identifier (no spaces, no dates), it might be an id
    if len(remaining) >= 3:
        # Could be: id, start, duration
        task.id = remaining[0]
        task.start = remaining[1]
        task.duration = remaining[2]
    elif len(remaining) == 2:
        # start, duration (or id, start if followed by nothing - less likely)
        task.start = remaining[0]
        task.duration = remaining[1]
    elif len(remaining) == 1:
        # Just duration
        task.duration = remaining[0]

    return task


# ── Parser ────────────────────────────────────────────────────────────────────

class GanttDiagramParser(DiagramParser):
    """Parser for mermaid gantt syntax."""

    def can_parse(self, source: str) -> bool:
        """Return True if the source starts with gantt."""
        for line in source.strip().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue
            return bool(_HEADER_RE.match(stripped))
        return False

    def parse(self, source: str) -> GanttDiagramModel:
        """Parse a gantt source into a GanttDiagramModel."""
        model = GanttDiagramModel()
        lines = source.strip().splitlines()
        current_section: GanttSection | None = None

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue

            # Skip header
            if _HEADER_RE.match(stripped):
                continue

            # Title
            title_m = _TITLE_RE.match(stripped)
            if title_m:
                model.title = title_m.group('title')
                continue

            # Date format
            df_m = _DATE_FORMAT_RE.match(stripped)
            if df_m:
                model.date_format = df_m.group('format')
                continue

            # Skip excludes, axisFormat, tickInterval
            if _EXCLUDES_RE.match(stripped) or _AXIS_FORMAT_RE.match(stripped) or _TICK_INTERVAL_RE.match(stripped):
                continue

            # Section
            section_m = _SECTION_RE.match(stripped)
            if section_m:
                current_section = GanttSection(name=section_m.group('name'))
                model.sections.append(current_section)
                continue

            # Task
            task_m = _TASK_RE.match(stripped)
            if task_m:
                task = _parse_task_spec(task_m.group('name'), task_m.group('spec'))
                if current_section is None:
                    # Tasks before any section go into an unnamed section
                    current_section = GanttSection(name='')
                    model.sections.append(current_section)
                current_section.tasks.append(task)
                continue

        return model


# ── Differ ────────────────────────────────────────────────────────────────────

class GanttDiagramDiffer(DiagramDiffer):
    """Differ for gantt diagram models."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        """Compare two GanttDiagramModel instances and produce annotated source."""
        assert isinstance(old, GanttDiagramModel)
        assert isinstance(new, GanttDiagramModel)

        old_sections = {s.name: s for s in old.sections}
        new_sections = {s.name: s for s in new.sections}

        old_section_names = set(old_sections.keys())
        new_section_names = set(new_sections.keys())

        added_sections = new_section_names - old_section_names
        removed_sections = old_section_names - new_section_names
        common_sections = old_section_names & new_section_names

        # Per-section task diffs
        section_changes: dict[str, dict] = {}
        for sec_name in common_sections:
            old_tasks = {t.name: t for t in old_sections[sec_name].tasks}
            new_tasks = {t.name: t for t in new_sections[sec_name].tasks}

            old_task_names = set(old_tasks.keys())
            new_task_names = set(new_tasks.keys())

            added_tasks = new_task_names - old_task_names
            removed_tasks = old_task_names - new_task_names
            common_tasks = old_task_names & new_task_names

            changed_tasks: set[str] = set()
            for task_name in common_tasks:
                ot = old_tasks[task_name]
                nt = new_tasks[task_name]
                if (ot.status != nt.status or ot.start != nt.start
                        or ot.duration != nt.duration):
                    changed_tasks.add(task_name)

            if added_tasks or removed_tasks or changed_tasks:
                section_changes[sec_name] = {
                    'added_tasks': added_tasks,
                    'removed_tasks': removed_tasks,
                    'changed_tasks': changed_tasks,
                    'old_tasks': old_tasks,
                }

        has_changes = bool(
            added_sections or removed_sections or section_changes
            or old.title != new.title or old.date_format != new.date_format
        )

        # Only flag title/format changes if the main structural stuff is empty
        if not has_changes:
            return DiffResult(has_changes=False)

        annotated = self._generate_annotated(
            new, old, added_sections, removed_sections, section_changes,
            old_sections,
        )
        return DiffResult(has_changes=True, annotated_source=annotated)

    def _generate_annotated(
        self,
        new: GanttDiagramModel,
        old: GanttDiagramModel,
        added_sections: set[str],
        removed_sections: set[str],
        section_changes: dict[str, dict],
        old_sections: dict[str, GanttSection],
    ) -> str:
        """Generate annotated mermaid source highlighting differences."""
        lines: list[str] = []

        lines.append('gantt')
        if new.title:
            lines.append(f'    title {new.title}')
        if new.date_format:
            lines.append(f'    dateFormat {new.date_format}')

        for section in new.sections:
            marker = ''
            if section.name in added_sections:
                marker = ' %% [+] added'

            if section.name:
                lines.append(f'    section {section.name}{marker}')

            changes = section_changes.get(section.name, {})
            added_tasks = changes.get('added_tasks', set())
            changed_tasks = changes.get('changed_tasks', set())
            removed_tasks_set = changes.get('removed_tasks', set())
            old_tasks = changes.get('old_tasks', {})

            for task in section.tasks:
                t_marker = ''
                task_status = task.status
                if task.name in added_tasks:
                    t_marker = ' %% [+]'
                elif task.name in changed_tasks:
                    t_marker = ' %% [~]'
                    # Add crit to status if not already present
                    if 'crit' not in task_status:
                        if task_status:
                            task_status = f'crit, {task_status}'
                        else:
                            task_status = 'crit'

                # Rebuild task line
                spec_parts: list[str] = []
                if task_status:
                    spec_parts.append(task_status)
                if task.id:
                    spec_parts.append(task.id)
                if task.start:
                    spec_parts.append(task.start)
                if task.duration:
                    spec_parts.append(task.duration)
                spec = ', '.join(spec_parts)
                lines.append(f'    {task.name} :{spec}{t_marker}')

            # Re-insert removed tasks
            for task_name in removed_tasks_set:
                old_task = old_tasks[task_name]
                spec_parts: list[str] = []
                if old_task.status:
                    spec_parts.append(old_task.status)
                if old_task.id:
                    spec_parts.append(old_task.id)
                if old_task.start:
                    spec_parts.append(old_task.start)
                if old_task.duration:
                    spec_parts.append(old_task.duration)
                spec = ', '.join(spec_parts)
                lines.append(f'    {task_name} :{spec} %% [-] removed')

        # Re-insert removed sections
        for sec_name in removed_sections:
            old_sec = old_sections[sec_name]
            lines.append(f'    section {sec_name} %% [-] removed')
            for task in old_sec.tasks:
                spec_parts: list[str] = []
                if task.status:
                    spec_parts.append(task.status)
                if task.id:
                    spec_parts.append(task.id)
                if task.start:
                    spec_parts.append(task.start)
                if task.duration:
                    spec_parts.append(task.duration)
                spec = ', '.join(spec_parts)
                lines.append(f'    {task.name} :{spec} %% [-]')

        return '\n'.join(lines)
