"""
Class diagram parser and differ.

Supports mermaid classDiagram syntax including class definitions with
members/methods, and relationships between classes.

Strategy:
  1. Parse class definitions (both block and inline syntax).
  2. Parse relationships with their types and labels.
  3. Diff by class name: identify added, removed, and changed classes.
  4. Within changed classes, diff members and methods.
  5. Diff relationships by (from, to, type) tuple.
  6. Re-emit annotated source with style directives and markers.
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
class ClassInfo:
    name: str
    members: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class ClassRelationship:
    from_class: str
    to_class: str
    rel_type: str
    label: str = ""


@dataclass
class ClassDiagramModel(DiagramModel):
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    relationships: list[ClassRelationship] = field(default_factory=list)


# ── Regex patterns ────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(r'^\s*classDiagram\s*$', re.IGNORECASE)

# Relationship patterns: ClassA <|-- ClassB : label
_REL_TYPES = [
    '<|--', '*--', 'o--', '-->', '--', '..>', '..|>',
    '--|>', '--*', '--o',
    '<|..', '..',
]

# Build a regex that matches relationships
# Pattern: ClassA rel ClassB : optional label
_REL_TYPE_PATTERN = '|'.join(re.escape(r) for r in sorted(_REL_TYPES, key=len, reverse=True))
_REL_RE = re.compile(
    r'^\s*(?P<from>[A-Za-z_][\w]*)\s+'
    r'(?P<rel>' + _REL_TYPE_PATTERN + r')\s+'
    r'(?P<to>[A-Za-z_][\w]*)'
    r'(?:\s*:\s*(?P<label>.+?))?\s*$'
)

# Class block start: class ClassName {
_CLASS_BLOCK_RE = re.compile(r'^\s*class\s+(?P<name>[A-Za-z_][\w]*)\s*\{\s*$')

# Class block end
_CLASS_BLOCK_END_RE = re.compile(r'^\s*\}\s*$')

# Inline member/method: ClassName : +member or ClassName : +method()
_INLINE_MEMBER_RE = re.compile(
    r'^\s*(?P<name>[A-Za-z_][\w]*)\s*:\s*(?P<content>.+?)\s*$'
)

# Member vs method detection: methods end with ()
_METHOD_RE = re.compile(r'.*\(.*\)\s*$')

# Annotation line inside class block: <<interface>> etc.
_ANNOTATION_RE = re.compile(r'^\s*<<.+>>\s*$')


# ── Parser ────────────────────────────────────────────────────────────────────

class ClassDiagramParser(DiagramParser):
    """Parser for mermaid classDiagram syntax."""

    def can_parse(self, source: str) -> bool:
        """Return True if the source starts with classDiagram."""
        for line in source.strip().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue
            return bool(_HEADER_RE.match(stripped))
        return False

    def parse(self, source: str) -> ClassDiagramModel:
        """Parse a classDiagram source into a ClassDiagramModel."""
        model = ClassDiagramModel()
        lines = source.strip().splitlines()
        in_class_block = False
        current_class: str | None = None

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue

            # Skip header
            if _HEADER_RE.match(stripped):
                continue

            # Skip style/directive lines
            if stripped.startswith('style ') or stripped.startswith('classDef '):
                continue

            # Class block end
            if in_class_block and _CLASS_BLOCK_END_RE.match(stripped):
                in_class_block = False
                current_class = None
                continue

            # Inside a class block
            if in_class_block and current_class:
                # Skip annotations
                if _ANNOTATION_RE.match(stripped):
                    continue
                # Determine if member or method
                if _METHOD_RE.match(stripped):
                    model.classes[current_class].methods.append(stripped)
                else:
                    model.classes[current_class].members.append(stripped)
                continue

            # Class block start
            block_m = _CLASS_BLOCK_RE.match(stripped)
            if block_m:
                name = block_m.group('name')
                if name not in model.classes:
                    model.classes[name] = ClassInfo(name=name)
                in_class_block = True
                current_class = name
                continue

            # Relationship
            rel_m = _REL_RE.match(stripped)
            if rel_m:
                from_cls = rel_m.group('from')
                to_cls = rel_m.group('to')
                rel_type = rel_m.group('rel')
                label = rel_m.group('label') or ''
                model.relationships.append(ClassRelationship(
                    from_class=from_cls,
                    to_class=to_cls,
                    rel_type=rel_type,
                    label=label.strip(),
                ))
                # Ensure classes exist
                if from_cls not in model.classes:
                    model.classes[from_cls] = ClassInfo(name=from_cls)
                if to_cls not in model.classes:
                    model.classes[to_cls] = ClassInfo(name=to_cls)
                continue

            # Inline member: ClassName : +content
            inline_m = _INLINE_MEMBER_RE.match(stripped)
            if inline_m:
                name = inline_m.group('name')
                content = inline_m.group('content')
                if name not in model.classes:
                    model.classes[name] = ClassInfo(name=name)
                if _METHOD_RE.match(content):
                    model.classes[name].methods.append(content)
                else:
                    model.classes[name].members.append(content)
                continue

        return model


# ── Differ ────────────────────────────────────────────────────────────────────

class ClassDiagramDiffer(DiagramDiffer):
    """Differ for classDiagram models."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        """Compare two ClassDiagramModel instances and produce annotated source."""
        assert isinstance(old, ClassDiagramModel)
        assert isinstance(new, ClassDiagramModel)

        old_names = set(old.classes.keys())
        new_names = set(new.classes.keys())

        added_classes = new_names - old_names
        removed_classes = old_names - new_names
        common_classes = old_names & new_names

        # Track per-class changes
        changed_classes: dict[str, dict] = {}  # name -> {added_members, removed_members, ...}
        for name in common_classes:
            old_cls = old.classes[name]
            new_cls = new.classes[name]
            old_members = set(old_cls.members)
            new_members = set(new_cls.members)
            old_methods = set(old_cls.methods)
            new_methods = set(new_cls.methods)

            changes = {
                'added_members': new_members - old_members,
                'removed_members': old_members - new_members,
                'added_methods': new_methods - old_methods,
                'removed_methods': old_methods - new_methods,
            }
            if any(changes.values()):
                changed_classes[name] = changes

        # Diff relationships by (from, to, type) key
        def rel_key(r: ClassRelationship) -> tuple:
            return (r.from_class, r.to_class, r.rel_type)

        old_rel_keys = {rel_key(r) for r in old.relationships}
        new_rel_keys = {rel_key(r) for r in new.relationships}
        added_rels = new_rel_keys - old_rel_keys
        removed_rels = old_rel_keys - new_rel_keys

        # Check if anything changed
        has_changes = bool(
            added_classes or removed_classes or changed_classes
            or added_rels or removed_rels
        )

        if not has_changes:
            return DiffResult(has_changes=False)

        # Generate annotated source
        annotated = self._generate_annotated(
            new, old, added_classes, removed_classes, changed_classes,
            added_rels, removed_rels,
        )
        return DiffResult(has_changes=True, annotated_source=annotated)

    def _generate_annotated(
        self,
        new: ClassDiagramModel,
        old: ClassDiagramModel,
        added_classes: set[str],
        removed_classes: set[str],
        changed_classes: dict[str, dict],
        added_rels: set[tuple],
        removed_rels: set[tuple],
    ) -> str:
        """Generate annotated mermaid source highlighting differences."""
        lines: list[str] = []
        styles: list[str] = []

        lines.append('classDiagram')

        # Emit new classes
        for name, cls_info in new.classes.items():
            marker = ''
            if name in added_classes:
                marker = ' %% [+] added'
                styles.append(
                    f'style {name} fill:{ADDED_FILL},stroke:{ADDED_STROKE}'
                )
            elif name in changed_classes:
                marker = ' %% [~] changed'
                styles.append(
                    f'style {name} fill:{CHANGED_FILL},stroke:{CHANGED_STROKE}'
                )

            if cls_info.members or cls_info.methods:
                lines.append(f'    class {name} {{{marker}')
                changes = changed_classes.get(name, {})
                for member in cls_info.members:
                    m_marker = ''
                    if member in changes.get('added_members', set()):
                        m_marker = ' %% [+]'
                    lines.append(f'        {member}{m_marker}')
                # Re-insert removed members
                for member in changes.get('removed_members', set()):
                    lines.append(f'        {member} %% [-]')
                for method in cls_info.methods:
                    m_marker = ''
                    if method in changes.get('added_methods', set()):
                        m_marker = ' %% [+]'
                    lines.append(f'        {method}{m_marker}')
                # Re-insert removed methods
                for method in changes.get('removed_methods', set()):
                    lines.append(f'        {method} %% [-]')
                lines.append('    }')
            else:
                if marker:
                    lines.append(f'    class {name}{marker}')
                else:
                    lines.append(f'    class {name}')

        # Re-insert removed classes
        for name in removed_classes:
            cls_info = old.classes[name]
            styles.append(
                f'style {name} fill:{REMOVED_FILL},stroke:{REMOVED_STROKE}'
            )
            if cls_info.members or cls_info.methods:
                lines.append(f'    class {name} {{ %% [-] removed')
                for member in cls_info.members:
                    lines.append(f'        {member}')
                for method in cls_info.methods:
                    lines.append(f'        {method}')
                lines.append('    }')
            else:
                lines.append(f'    class {name} %% [-] removed')

        # Emit relationships from new
        for rel in new.relationships:
            key = (rel.from_class, rel.to_class, rel.rel_type)
            marker = ''
            if key in added_rels:
                marker = ' %% [+] added'
            label_part = f' : {rel.label}' if rel.label else ''
            lines.append(f'    {rel.from_class} {rel.rel_type} {rel.to_class}{label_part}{marker}')

        # Re-insert removed relationships
        for rel in old.relationships:
            key = (rel.from_class, rel.to_class, rel.rel_type)
            if key in removed_rels:
                label_part = f' : {rel.label}' if rel.label else ''
                lines.append(
                    f'    {rel.from_class} {rel.rel_type} {rel.to_class}{label_part} %% [-] removed'
                )

        # Append style directives
        for style in styles:
            lines.append(f'    {style}')

        return '\n'.join(lines)
