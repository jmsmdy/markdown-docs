"""
Sequence diagram parser and differ.

Supports mermaid sequence diagrams.

Strategy:
  1. Parse both old and new mermaid source into a sequence model
     (participants, messages, notes, groups).
  2. Diff participants by id, messages by index position.
  3. Re-emit annotated diagram with markers:
     - Added participants: alias gets " [+]"
     - Removed participants: re-inserted with " [-]"
     - Added messages: text gets " [+]"
     - Removed messages: re-inserted with " [-]"
     - Changed messages: text gets " [~]"
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


# ── Sequence model ────────────────────────────────────────────────────────────

@dataclass
class Participant:
    id: str
    alias: str | None = None  # display name


@dataclass
class Message:
    sender: str
    receiver: str
    arrow_type: str  # ->, -->, ->>, ->>>, -x, --x, -), --)
    text: str


@dataclass
class Note:
    position: str  # "over", "left of", "right of"
    participants: list[str]  # which participants the note is over
    text: str


@dataclass
class Group:
    kind: str  # loop, alt, par, opt, critical, break
    label: str
    messages: list[Message | Note | "Group"] = field(default_factory=list)


@dataclass
class SequenceDiagram(DiagramModel):
    participants: list[Participant] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    # Raw lines preserved for elements we don't diff (activations etc.)
    raw_lines: list[str] = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────────────

# Arrow types ordered longest-first for matching
_ARROW_TYPES = ['-->>', '-->',  '--x', '--)', '->>', '->', '-x', '-)']
_ARROW_RE = re.compile(
    r'^\s*([\w]+)\s*'
    r'(-->>|--\)|--x|-->|->>|-\)|-x|->)'
    r'\s*([\w]+)\s*:\s*(.+)$'
)
_PARTICIPANT_RE = re.compile(
    r'^\s*participant\s+(\S+)(?:\s+as\s+(.+))?\s*$', re.IGNORECASE
)
_ACTOR_RE = re.compile(
    r'^\s*actor\s+(\S+)(?:\s+as\s+(.+))?\s*$', re.IGNORECASE
)
_NOTE_RE = re.compile(
    r'^\s*Note\s+(over|left of|right of)\s+([^:]+):\s*(.+)$', re.IGNORECASE
)
_GROUP_START_RE = re.compile(
    r'^\s*(loop|alt|else|par|opt|critical|break|rect)\s*(.*)$', re.IGNORECASE
)
_GROUP_END_RE = re.compile(r'^\s*end\s*$', re.IGNORECASE)
_ACTIVATE_RE = re.compile(r'^\s*(activate|deactivate)\s+(\S+)\s*$', re.IGNORECASE)


class SequenceParser(DiagramParser):
    """Parser for mermaid sequence diagrams."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split('\n', 1)[0].strip().lower()
        return first_line.startswith('sequencediagram')

    def parse(self, source: str) -> SequenceDiagram:
        """Parse mermaid sequence diagram source."""
        lines = source.strip().splitlines()
        diagram = SequenceDiagram()
        diagram.raw_lines = lines

        # Track participants discovered from messages (implicit)
        seen_participants: set[str] = set()

        for line in lines[1:]:  # skip header
            stripped = line.strip()
            if not stripped or stripped.startswith('%%'):
                continue

            # Participant declaration
            p_match = _PARTICIPANT_RE.match(stripped)
            if p_match:
                pid = p_match.group(1)
                alias = p_match.group(2)
                if alias:
                    alias = alias.strip()
                diagram.participants.append(Participant(id=pid, alias=alias))
                seen_participants.add(pid)
                continue

            # Actor declaration (treated same as participant)
            a_match = _ACTOR_RE.match(stripped)
            if a_match:
                pid = a_match.group(1)
                alias = a_match.group(2)
                if alias:
                    alias = alias.strip()
                diagram.participants.append(Participant(id=pid, alias=alias))
                seen_participants.add(pid)
                continue

            # Note
            n_match = _NOTE_RE.match(stripped)
            if n_match:
                position = n_match.group(1).lower()
                participants_str = n_match.group(2).strip()
                text = n_match.group(3).strip()
                parts = [p.strip() for p in participants_str.split(',')]
                diagram.notes.append(Note(position=position, participants=parts, text=text))
                continue

            # Group start (loop, alt, par, etc.)
            g_match = _GROUP_START_RE.match(stripped)
            if g_match:
                kind = g_match.group(1).lower()
                label = g_match.group(2).strip() if g_match.group(2) else ""
                diagram.groups.append(Group(kind=kind, label=label))
                continue

            # Group end / activate / deactivate — skip for diffing
            if _GROUP_END_RE.match(stripped) or _ACTIVATE_RE.match(stripped):
                continue

            # Message
            m_match = _ARROW_RE.match(stripped)
            if m_match:
                sender = m_match.group(1)
                arrow = m_match.group(2)
                receiver = m_match.group(3)
                text = m_match.group(4).strip()
                diagram.messages.append(Message(
                    sender=sender, receiver=receiver,
                    arrow_type=arrow, text=text
                ))
                # Auto-register implicit participants
                for pid in (sender, receiver):
                    if pid not in seen_participants:
                        diagram.participants.append(Participant(id=pid, alias=None))
                        seen_participants.add(pid)
                continue

        return diagram


# ── Differ ────────────────────────────────────────────────────────────────────

@dataclass
class SequenceDiff:
    added_participants: list[Participant] = field(default_factory=list)
    removed_participants: list[Participant] = field(default_factory=list)
    added_messages: list[Message] = field(default_factory=list)
    removed_messages: list[Message] = field(default_factory=list)
    changed_messages: list[tuple[Message, Message]] = field(default_factory=list)  # (old, new)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_participants or self.removed_participants
            or self.added_messages or self.removed_messages
            or self.changed_messages
        )


def diff_sequences(old: SequenceDiagram, new: SequenceDiagram) -> SequenceDiff:
    """Compare two sequence diagrams."""
    result = SequenceDiff()

    # Compare participants by id
    old_ids = {p.id for p in old.participants}
    new_ids = {p.id for p in new.participants}

    old_by_id = {p.id: p for p in old.participants}
    new_by_id = {p.id: p for p in new.participants}

    for pid in new_ids - old_ids:
        result.added_participants.append(new_by_id[pid])

    for pid in old_ids - new_ids:
        result.removed_participants.append(old_by_id[pid])

    # Compare messages by index (simple positional matching)
    max_len = max(len(old.messages), len(new.messages))
    for i in range(max_len):
        if i >= len(old.messages):
            # Added message
            result.added_messages.append(new.messages[i])
        elif i >= len(new.messages):
            # Removed message
            result.removed_messages.append(old.messages[i])
        else:
            old_msg = old.messages[i]
            new_msg = new.messages[i]
            if (old_msg.sender != new_msg.sender
                    or old_msg.receiver != new_msg.receiver
                    or old_msg.arrow_type != new_msg.arrow_type
                    or old_msg.text != new_msg.text):
                result.changed_messages.append((old_msg, new_msg))

    return result


def generate_annotated_sequence(
    old: SequenceDiagram,
    new: SequenceDiagram,
    diff: SequenceDiff,
) -> str:
    """Generate annotated sequence diagram source with diff markers."""
    lines: list[str] = []
    lines.append("sequenceDiagram")

    # Emit participants from new diagram
    added_ids = {p.id for p in diff.added_participants}
    removed_ids = {p.id for p in diff.removed_participants}

    for p in new.participants:
        alias_display = p.alias or p.id
        if p.id in added_ids:
            lines.append(f"    participant {p.id} as {alias_display} [+]")
        else:
            if p.alias:
                lines.append(f"    participant {p.id} as {p.alias}")
            else:
                lines.append(f"    participant {p.id}")

    # Re-insert removed participants
    for p in diff.removed_participants:
        alias_display = p.alias or p.id
        lines.append(f"    participant {p.id} as {alias_display} [-]")

    # Emit messages from new diagram with annotations
    added_msgs = set(id(m) for m in diff.added_messages)
    changed_new_msgs = set(id(new_m) for _, new_m in diff.changed_messages)

    for msg in new.messages:
        msg_line = f"    {msg.sender}{msg.arrow_type}{msg.receiver}: {msg.text}"
        if id(msg) in added_msgs:
            msg_line = f"    {msg.sender}{msg.arrow_type}{msg.receiver}: {msg.text} [+]"
        elif id(msg) in changed_new_msgs:
            msg_line = f"    {msg.sender}{msg.arrow_type}{msg.receiver}: {msg.text} [~]"
        lines.append(msg_line)

    # Re-insert removed messages
    for msg in diff.removed_messages:
        lines.append(f"    {msg.sender}{msg.arrow_type}{msg.receiver}: {msg.text} [-]")

    return "\n".join(lines)


class SequenceDiffer(DiagramDiffer):
    """Differ for mermaid sequence diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, SequenceDiagram)
        assert isinstance(new, SequenceDiagram)

        result = diff_sequences(old, new)

        if not result.has_changes:
            return DiffResult(has_changes=False)

        annotated = generate_annotated_sequence(old, new, result)
        return DiffResult(has_changes=True, annotated_source=annotated)
