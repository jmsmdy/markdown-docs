"""
State diagram parser and differ.

Supports mermaid stateDiagram-v2 diagrams.

Strategy:
  1. Parse both old and new mermaid source into a state model
     (states, transitions, composite states).
  2. Diff states by id (detect added/removed/label-changed).
     Diff transitions by (from, to) pairs.
  3. Re-emit annotated diagram with:
     - classDef directives for added/removed/changed styling
     - class statements to apply styles to affected states
     - Removed states/transitions re-inserted
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


# ── State model ───────────────────────────────────────────────────────────────

@dataclass
class StateTransition:
    source: str
    target: str
    label: str = ""


@dataclass
class StateDiagram(DiagramModel):
    states: dict[str, str] = field(default_factory=dict)  # id -> label
    transitions: list[StateTransition] = field(default_factory=list)
    composite_states: dict[str, list[str]] = field(default_factory=dict)  # id -> child state ids


# ── Parser ────────────────────────────────────────────────────────────────────

# s1 : State Name
_STATE_DEF_RE = re.compile(r'^\s*(\w+)\s*:\s*(.+)$')
# s1 --> s2 : label   OR   s1 --> s2
_TRANSITION_RE = re.compile(r'^\s*(\[?\*?\]?[\w\[\]\*]+)\s*-->\s*(\[?\*?\]?[\w\[\]\*]+)(?:\s*:\s*(.+))?\s*$')
# state s1 {  (composite state start)
_COMPOSITE_START_RE = re.compile(r'^\s*state\s+(\w+)\s*\{\s*$')
# state "Label" as s1
_STATE_ALIAS_RE = re.compile(r'^\s*state\s+"([^"]+)"\s+as\s+(\w+)\s*$')
# end of composite state
_COMPOSITE_END_RE = re.compile(r'^\s*\}\s*$')


class StateParser(DiagramParser):
    """Parser for mermaid state diagrams (stateDiagram-v2)."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split('\n', 1)[0].strip().lower()
        return first_line.startswith('statediagram')

    def parse(self, source: str) -> StateDiagram:
        """Parse mermaid state diagram source."""
        lines = source.strip().splitlines()
        diagram = StateDiagram()

        # Stack for composite state parsing
        composite_stack: list[str] = []

        for line in lines[1:]:  # skip header
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue

            # State alias: state "Label" as id
            alias_match = _STATE_ALIAS_RE.match(stripped)
            if alias_match:
                label = alias_match.group(1)
                state_id = alias_match.group(2)
                diagram.states[state_id] = label
                if composite_stack:
                    parent = composite_stack[-1]
                    if parent not in diagram.composite_states:
                        diagram.composite_states[parent] = []
                    diagram.composite_states[parent].append(state_id)
                continue

            # Composite state start
            comp_match = _COMPOSITE_START_RE.match(stripped)
            if comp_match:
                state_id = comp_match.group(1)
                composite_stack.append(state_id)
                if state_id not in diagram.states:
                    diagram.states[state_id] = state_id
                if state_id not in diagram.composite_states:
                    diagram.composite_states[state_id] = []
                continue

            # Composite state end
            if _COMPOSITE_END_RE.match(stripped):
                if composite_stack:
                    composite_stack.pop()
                continue

            # Transition: s1 --> s2 : label
            trans_match = _TRANSITION_RE.match(stripped)
            if trans_match:
                src = trans_match.group(1)
                tgt = trans_match.group(2)
                label = trans_match.group(3).strip() if trans_match.group(3) else ""
                diagram.transitions.append(StateTransition(
                    source=src, target=tgt, label=label
                ))
                # Register states implicitly
                for sid in (src, tgt):
                    if sid not in diagram.states and sid != '[*]':
                        diagram.states[sid] = sid
                    if composite_stack and sid != '[*]':
                        parent = composite_stack[-1]
                        if sid not in diagram.composite_states.get(parent, []):
                            diagram.composite_states.setdefault(parent, []).append(sid)
                continue

            # State definition: s1 : Label
            state_match = _STATE_DEF_RE.match(stripped)
            if state_match:
                state_id = state_match.group(1)
                label = state_match.group(2).strip()
                # Avoid matching things like 'classDef' or 'class' or 'direction'
                if state_id.lower() in ('classdef', 'class', 'direction', 'state'):
                    continue
                diagram.states[state_id] = label
                if composite_stack:
                    parent = composite_stack[-1]
                    if parent not in diagram.composite_states:
                        diagram.composite_states[parent] = []
                    if state_id not in diagram.composite_states[parent]:
                        diagram.composite_states[parent].append(state_id)
                continue

        return diagram


# ── Differ ────────────────────────────────────────────────────────────────────

@dataclass
class StateDiff:
    added_states: set[str] = field(default_factory=set)
    removed_states: set[str] = field(default_factory=set)
    changed_states: set[str] = field(default_factory=set)  # label changed
    added_transitions: list[StateTransition] = field(default_factory=list)
    removed_transitions: list[StateTransition] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_states or self.removed_states or self.changed_states
            or self.added_transitions or self.removed_transitions
        )


def diff_states(old: StateDiagram, new: StateDiagram) -> StateDiff:
    """Compare two state diagrams."""
    result = StateDiff()

    old_ids = set(old.states.keys())
    new_ids = set(new.states.keys())

    result.added_states = new_ids - old_ids
    result.removed_states = old_ids - new_ids

    # Check for label changes
    for state_id in old_ids & new_ids:
        if old.states[state_id] != new.states[state_id]:
            result.changed_states.add(state_id)

    # Compare transitions by (source, target) pair
    def trans_key(t: StateTransition) -> tuple[str, str]:
        return (t.source, t.target)

    old_trans_keys = {trans_key(t) for t in old.transitions}
    new_trans_keys = {trans_key(t) for t in new.transitions}

    for t in new.transitions:
        if trans_key(t) not in old_trans_keys:
            result.added_transitions.append(t)

    for t in old.transitions:
        if trans_key(t) not in new_trans_keys:
            result.removed_transitions.append(t)

    return result


def generate_annotated_state(
    old: StateDiagram,
    new: StateDiagram,
    diff: StateDiff,
) -> str:
    """
    Generate annotated state diagram with diff styling.

    Uses classDef to define added/removed/changed classes and
    class statements to apply them to affected states.
    Re-inserts removed states and transitions.
    """
    lines: list[str] = []
    lines.append("stateDiagram-v2")

    # Emit state definitions from new diagram
    for state_id, label in new.states.items():
        if label != state_id:
            lines.append(f"    {state_id} : {label}")
        else:
            # Only emit explicit definitions for states that have labels
            pass

    # Re-insert removed states
    for state_id in sorted(diff.removed_states):
        label = old.states[state_id]
        if label != state_id:
            lines.append(f"    {state_id} : {label}")
        else:
            lines.append(f"    {state_id}")

    # Emit transitions from new diagram
    for t in new.transitions:
        if t.label:
            lines.append(f"    {t.source} --> {t.target} : {t.label}")
        else:
            lines.append(f"    {t.source} --> {t.target}")

    # Re-insert removed transitions
    for t in diff.removed_transitions:
        if t.label:
            lines.append(f"    {t.source} --> {t.target} : {t.label}")
        else:
            lines.append(f"    {t.source} --> {t.target}")

    # Add classDef directives for styling
    lines.append("")
    lines.append(f"    classDef added fill:{ADDED_FILL},stroke:{ADDED_STROKE},stroke-width:2px")
    lines.append(f"    classDef removed fill:{REMOVED_FILL},stroke:{REMOVED_STROKE},stroke-width:2px,stroke-dasharray:5 5")
    lines.append(f"    classDef changed fill:{CHANGED_FILL},stroke:{CHANGED_STROKE},stroke-width:2px")

    # Apply classes to affected states
    if diff.added_states:
        for state_id in sorted(diff.added_states):
            lines.append(f"    class {state_id} added")

    if diff.removed_states:
        for state_id in sorted(diff.removed_states):
            lines.append(f"    class {state_id} removed")

    if diff.changed_states:
        for state_id in sorted(diff.changed_states):
            lines.append(f"    class {state_id} changed")

    return "\n".join(lines)


class StateDiffer(DiagramDiffer):
    """Differ for mermaid state diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, StateDiagram)
        assert isinstance(new, StateDiagram)

        result = diff_states(old, new)

        if not result.has_changes:
            return DiffResult(has_changes=False)

        annotated = generate_annotated_state(old, new, result)
        return DiffResult(has_changes=True, annotated_source=annotated)
