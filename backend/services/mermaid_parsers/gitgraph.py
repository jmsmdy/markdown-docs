"""
Git Graph diagram parser and differ.

Supports mermaid gitGraph diagrams with commits, branches, merges, etc.

Syntax:
    gitGraph
        commit
        commit id: "abc"
        commit tag: "v1.0"
        branch develop
        checkout develop
        commit
        merge main
        cherry-pick id: "abc"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from backend.services.mermaid_parsers.base import (
    DiagramDiffer,
    DiagramModel,
    DiagramParser,
    DiffResult,
)


# ── GitGraph model ────────────────────────────────────────────────────────────

@dataclass
class GitOperation:
    type: str  # commit, branch, checkout, merge, cherry-pick
    branch_name: str = ""
    id: str = ""
    tag: str = ""
    raw: str = ""  # original line for re-emission

    @property
    def key(self) -> str:
        """Identity key for comparison."""
        parts = [self.type]
        if self.branch_name:
            parts.append(self.branch_name)
        if self.id:
            parts.append(f"id:{self.id}")
        if self.tag:
            parts.append(f"tag:{self.tag}")
        return "|".join(parts)


@dataclass
class GitGraphModel(DiagramModel):
    operations: list[GitOperation] = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────────────

_COMMIT_ID_RE = re.compile(r'id:\s*"([^"]*)"')
_COMMIT_TAG_RE = re.compile(r'tag:\s*"([^"]*)"')


class GitGraphParser(DiagramParser):
    """Parser for mermaid gitGraph diagrams."""

    def can_parse(self, source: str) -> bool:
        first_line = source.strip().split("\n", 1)[0].strip().lower()
        return first_line in ("gitgraph", "gitgraph:")

    def parse(self, source: str) -> GitGraphModel:
        lines = source.strip().splitlines()
        model = GitGraphModel()

        for line in lines[1:]:  # skip 'gitGraph' header
            stripped = line.strip()
            if not stripped or stripped.startswith("%%"):
                continue

            op = self._parse_operation(stripped)
            if op:
                op.raw = stripped
                model.operations.append(op)

        return model

    def _parse_operation(self, line: str) -> GitOperation | None:
        """Parse a single git graph operation line."""
        lower = line.lower()

        # commit [id: "..."] [tag: "..."]
        if lower.startswith("commit"):
            op = GitOperation(type="commit")
            id_match = _COMMIT_ID_RE.search(line)
            if id_match:
                op.id = id_match.group(1)
            tag_match = _COMMIT_TAG_RE.search(line)
            if tag_match:
                op.tag = tag_match.group(1)
            return op

        # branch <name>
        if lower.startswith("branch "):
            name = line[7:].strip()
            return GitOperation(type="branch", branch_name=name)

        # checkout <name>
        if lower.startswith("checkout "):
            name = line[9:].strip()
            return GitOperation(type="checkout", branch_name=name)

        # merge <name>
        if lower.startswith("merge "):
            name = line[6:].strip()
            # Handle merge with id/tag
            parts = name.split()
            branch = parts[0] if parts else name
            op = GitOperation(type="merge", branch_name=branch)
            id_match = _COMMIT_ID_RE.search(line)
            if id_match:
                op.id = id_match.group(1)
            tag_match = _COMMIT_TAG_RE.search(line)
            if tag_match:
                op.tag = tag_match.group(1)
            return op

        # cherry-pick id: "..."
        if lower.startswith("cherry-pick"):
            op = GitOperation(type="cherry-pick")
            id_match = _COMMIT_ID_RE.search(line)
            if id_match:
                op.id = id_match.group(1)
            return op

        return None


# ── Differ ────────────────────────────────────────────────────────────────────

class GitGraphDiffer(DiagramDiffer):
    """Differ for mermaid gitGraph diagrams."""

    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        assert isinstance(old, GitGraphModel)
        assert isinstance(new, GitGraphModel)

        old_keys = [op.key for op in old.operations]
        new_keys = [op.key for op in new.operations]

        # Use SequenceMatcher for LCS-based comparison
        matcher = SequenceMatcher(None, old_keys, new_keys)
        opcodes = matcher.get_opcodes()

        # Check if there are any changes
        has_changes = any(tag != "equal" for tag, _, _, _, _ in opcodes)
        if not has_changes:
            return DiffResult(has_changes=False)

        # Build annotated source
        annotated_lines: list[str] = ["gitGraph"]

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                for op in new.operations[j1:j2]:
                    annotated_lines.append(f"    {self._emit_op(op)}")
            elif tag == "replace":
                # Removed operations
                for op in old.operations[i1:i2]:
                    annotated_lines.append(
                        f"    {self._emit_op(op)} %% [-]"
                    )
                # Added operations
                for op in new.operations[j1:j2]:
                    annotated_lines.append(
                        f"    {self._emit_op(op)} %% [+]"
                    )
            elif tag == "delete":
                for op in old.operations[i1:i2]:
                    annotated_lines.append(
                        f"    {self._emit_op(op)} %% [-]"
                    )
            elif tag == "insert":
                for op in new.operations[j1:j2]:
                    annotated_lines.append(
                        f"    {self._emit_op(op)} %% [+]"
                    )

        return DiffResult(
            has_changes=True, annotated_source="\n".join(annotated_lines)
        )

    def _emit_op(self, op: GitOperation) -> str:
        """Emit a git operation as a mermaid line."""
        if op.type == "commit":
            parts = ["commit"]
            if op.id:
                parts.append(f'id: "{op.id}"')
            if op.tag:
                parts.append(f'tag: "{op.tag}"')
            return " ".join(parts)
        elif op.type == "branch":
            return f"branch {op.branch_name}"
        elif op.type == "checkout":
            return f"checkout {op.branch_name}"
        elif op.type == "merge":
            parts = [f"merge {op.branch_name}"]
            if op.id:
                parts.append(f'id: "{op.id}"')
            if op.tag:
                parts.append(f'tag: "{op.tag}"')
            return " ".join(parts)
        elif op.type == "cherry-pick":
            if op.id:
                return f'cherry-pick id: "{op.id}"'
            return "cherry-pick"
        return op.raw or op.type
