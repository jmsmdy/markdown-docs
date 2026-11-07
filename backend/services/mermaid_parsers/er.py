"""
ER (Entity-Relationship) diagram parser and differ.

Supports mermaid erDiagram syntax including entity definitions with
attributes, and relationships with cardinality.

Strategy:
  1. Parse entity definitions with their attributes (name, type, keys).
  2. Parse relationships with cardinality markers and labels.
  3. Diff entities by name: identify added, removed, changed.
  4. Within changed entities, diff attributes.
  5. Diff relationships by (entity1, entity2) pair.
  6. Re-emit annotated source with markers and comments.
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
class ERAttribute:
    type: str
    name: str
    keys: str = ""  # PK, FK, UK, etc.


@dataclass
class EREntity:
    name: str
    attributes: list[ERAttribute] = field(default_factory=list)


@dataclass
class ERRelationship:
    entity1: str
    entity2: str
    cardinality1: str
    cardinality2: str
    label: str = ""


@dataclass
class ERDiagramModel(DiagramModel):
    entities: dict[str, EREntity] = field(default_factory=dict)
    relationships: list[ERRelationship] = field(default_factory=list)


# ── Regex patterns ────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(r'^\s*erDiagram\s*$', re.IGNORECASE)

# Entity block start: ENTITY_NAME {
_ENTITY_BLOCK_RE = re.compile(r'^\s*(?P<name>[A-Za-z_][\w]*)\s*\{\s*$')

# Entity block end
_ENTITY_BLOCK_END_RE = re.compile(r'^\s*\}\s*$')

# Attribute line inside entity block: type name [PK|FK|UK]
_ATTR_RE = re.compile(
    r'^\s*(?P<type>[A-Za-z_][\w]*)\s+(?P<name>[A-Za-z_][\w]*)'
    r'(?:\s+(?P<keys>[A-Z,\s]+?))?\s*$'
)

# Cardinality markers
_CARDINALITY_LEFT = r'(?P<card1>\|\||\|o|o\||o\{|\{o|\|\{|\{\||\}\||\|}|\}o|o\})'
_CARDINALITY_RIGHT = r'(?P<card2>\|\||o\||\|o|\{o|o\{|\{\||\|\{|\}\||\|\}|o\}|\}o)'

# Relationship: ENTITY1 ||--o{ ENTITY2 : label
_REL_RE = re.compile(
    r'^\s*(?P<entity1>[A-Za-z_][\w]*)\s+'
    r'(?P<card1>[|o}{]+)'
    r'--'
    r'(?P<card2>[|o}{]+)'
    r'\s+(?P<entity2>[A-Za-z_][\w]*)'
    r'(?:\s*:\s*(?P<label>.+?))?\s*$'
)


# ── Parser ────────────────────────────────────────────────────────────────────

class ERDiagramParser(DiagramParser):
    """Parser for mermaid erDiagram syntax."""

    def can_parse(self, source: str) -> bool:
        """Return True if the source starts with erDiagram."""
        for line in source.strip().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue
            return bool(_HEADER_RE.match(stripped))
        return False

    def parse(self, source: str) -> ERDiagramModel:
        """Parse an erDiagram source into an ERDiagramModel."""
        model = ERDiagramModel()
        lines = source.strip().splitlines()
        in_entity_block = False
        current_entity: str | None = None

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue

            # Skip header
            if _HEADER_RE.match(stripped):
                continue

            # Entity block end
            if in_entity_block and _ENTITY_BLOCK_END_RE.match(stripped):
                in_entity_block = False
                current_entity = None
                continue

            # Inside entity block - parse attributes
            if in_entity_block and current_entity:
                attr_m = _ATTR_RE.match(stripped)
                if attr_m:
                    attr = ERAttribute(
                        type=attr_m.group('type'),
                        name=attr_m.group('name'),
                        keys=attr_m.group('keys').strip() if attr_m.group('keys') else '',
                    )
                    model.entities[current_entity].attributes.append(attr)
                continue

            # Entity block start
            entity_m = _ENTITY_BLOCK_RE.match(stripped)
            if entity_m:
                name = entity_m.group('name')
                if name not in model.entities:
                    model.entities[name] = EREntity(name=name)
                in_entity_block = True
                current_entity = name
                continue

            # Relationship
            rel_m = _REL_RE.match(stripped)
            if rel_m:
                entity1 = rel_m.group('entity1')
                entity2 = rel_m.group('entity2')
                card1 = rel_m.group('card1')
                card2 = rel_m.group('card2')
                label = rel_m.group('label') or ''

                model.relationships.append(ERRelationship(
                    entity1=entity1,
                    entity2=entity2,
                    cardinality1=card1,
                    cardinality2=card2,
                    label=label.strip(),
                ))
                # Ensure entities exist
                if entity1 not in model.entities:
                    model.entities[entity1] = EREntity(name=entity1)
                if entity2 not in model.entities:
                    model.entities[entity2] = EREntity(name=entity2)
                continue

        return model


# ── Differ ────────────────────────────────────────────────────────────────────

class ERDiagramDiffer(DiagramDiffer):
    """Differ for erDiagram models."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        """Compare two ERDiagramModel instances and produce annotated source."""
        assert isinstance(old, ERDiagramModel)
        assert isinstance(new, ERDiagramModel)

        old_names = set(old.entities.keys())
        new_names = set(new.entities.keys())

        added_entities = new_names - old_names
        removed_entities = old_names - new_names
        common_entities = old_names & new_names

        # Track per-entity attribute changes
        changed_entities: dict[str, dict] = {}
        for name in common_entities:
            old_attrs = {(a.type, a.name, a.keys) for a in old.entities[name].attributes}
            new_attrs = {(a.type, a.name, a.keys) for a in new.entities[name].attributes}

            added_attrs = new_attrs - old_attrs
            removed_attrs = old_attrs - new_attrs

            if added_attrs or removed_attrs:
                changed_entities[name] = {
                    'added_attrs': added_attrs,
                    'removed_attrs': removed_attrs,
                }

        # Diff relationships by (entity1, entity2) key
        def rel_key(r: ERRelationship) -> tuple:
            return (r.entity1, r.entity2)

        old_rel_keys = {rel_key(r) for r in old.relationships}
        new_rel_keys = {rel_key(r) for r in new.relationships}
        added_rels = new_rel_keys - old_rel_keys
        removed_rels = old_rel_keys - new_rel_keys

        has_changes = bool(
            added_entities or removed_entities or changed_entities
            or added_rels or removed_rels
        )

        if not has_changes:
            return DiffResult(has_changes=False)

        annotated = self._generate_annotated(
            new, old, added_entities, removed_entities, changed_entities,
            added_rels, removed_rels,
        )
        return DiffResult(has_changes=True, annotated_source=annotated)

    def _generate_annotated(
        self,
        new: ERDiagramModel,
        old: ERDiagramModel,
        added_entities: set[str],
        removed_entities: set[str],
        changed_entities: dict[str, dict],
        added_rels: set[tuple],
        removed_rels: set[tuple],
    ) -> str:
        """Generate annotated mermaid source highlighting differences."""
        lines: list[str] = []

        lines.append('erDiagram')

        # Emit entities
        for name, entity in new.entities.items():
            marker = ''
            if name in added_entities:
                marker = ' [+]'
            elif name in changed_entities:
                marker = ' [~]'

            if entity.attributes:
                lines.append(f'    {name}{marker} {{')
                changes = changed_entities.get(name, {})
                added_attrs = changes.get('added_attrs', set())
                removed_attrs = changes.get('removed_attrs', set())

                for attr in entity.attributes:
                    attr_key = (attr.type, attr.name, attr.keys)
                    a_marker = ''
                    if attr_key in added_attrs:
                        a_marker = ' %% [+]'
                    keys_part = f' {attr.keys}' if attr.keys else ''
                    lines.append(f'        {attr.type} {attr.name}{keys_part}{a_marker}')

                # Re-insert removed attributes
                for attr_tuple in removed_attrs:
                    keys_part = f' {attr_tuple[2]}' if attr_tuple[2] else ''
                    lines.append(f'        {attr_tuple[0]} {attr_tuple[1]}{keys_part} %% [-]')

                lines.append('    }')
            else:
                if marker:
                    lines.append(f'    %% md-diff: entity {name}{marker}')
                # Entity with no attributes doesn't need a block
                # It will appear in relationships

        # Re-insert removed entities
        for name in removed_entities:
            entity = old.entities[name]
            if entity.attributes:
                lines.append(f'    %% md-diff: removed entity {name} [-]')
                lines.append(f'    {name} {{')
                for attr in entity.attributes:
                    keys_part = f' {attr.keys}' if attr.keys else ''
                    lines.append(f'        {attr.type} {attr.name}{keys_part} %% [-]')
                lines.append('    }')
            else:
                lines.append(f'    %% md-diff: removed entity {name} [-]')

        # Emit relationships
        for rel in new.relationships:
            key = (rel.entity1, rel.entity2)
            marker = ''
            if key in added_rels:
                marker = ' [+]'
            label_part = f' : {rel.label}{marker}' if rel.label else f' : {marker}' if marker else ''
            if not rel.label and marker:
                label_part = f' : relates{marker}'
            lines.append(
                f'    {rel.entity1} {rel.cardinality1}--{rel.cardinality2} {rel.entity2}{label_part}'
            )

        # Re-insert removed relationships
        for rel in old.relationships:
            key = (rel.entity1, rel.entity2)
            if key in removed_rels:
                label = rel.label or 'relates'
                lines.append(
                    f'    {rel.entity1} {rel.cardinality1}--{rel.cardinality2} {rel.entity2} : {label} [-]'
                )

        return '\n'.join(lines)
