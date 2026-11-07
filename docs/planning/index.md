# Planning

This section contains design plans and roadmap items for markdown-docs.

## Active Plans

| Plan | Status | Description |
|------|--------|-------------|
| [Mermaid Semantic Diff](mermaid-semantic-diff.md) | 🟡 In progress | Extend structural diffing to all mermaid diagram types |

## Current State

markdown-docs is functional and stable for its core use case: editing markdown documents with git-backed branching and visual diffing.

### What works well

- Full document editing lifecycle (create → edit → save → branch → merge)
- Block-level and word-level rendered diffs
- Structural diff for tables, lists, and code blocks
- Mermaid flowchart/graph semantic diff with node/edge highlighting
- Source (unified text) diff
- Branch management UI

### Known gaps

- **Mermaid diagram coverage** — only flowchart/graph diagrams get structural diffs. All other diagram types (sequence, state, class, ER, gantt, pie, journey, quadrant, mindmap, timeline, C4, gitGraph) fall back to side-by-side rendering with no semantic annotation.
- **No conflict resolution UI** — merge conflicts require the git CLI.
- **No remote sync** — push/pull must be done outside the tool.
- **No file deletion UI** — files can only be deleted via git CLI.

## Design Principles for New Features

1. **Independence** — new subsystems should be usable independently of the full UI. The mermaid diff engine, for example, should work as a pure function with no coupling to CSS, DOM, or the rest of the application.
2. **Consistency** — all diagram types should produce diffs in the same output format with the same annotation conventions.
3. **Maintainability** — parser/differ pairs for new diagram types should follow a common interface pattern so contributors can add support for new types without understanding the full system.
4. **Graceful degradation** — if a parser fails, the system falls back to side-by-side rendering. Never crash on unexpected input.
