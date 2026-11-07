# Plan: 100% Mermaid Diagram Coverage for Semantic Diff

## Goal

Extend the mermaid structural diff engine to support **all** mermaid diagram types, so that every diagram change produces a meaningful semantic annotation — not just a side-by-side render.

## Current State

The existing implementation (`backend/services/mermaid_diff.py`) supports **flowchart/graph** diagrams only. It:

1. Parses mermaid source into a graph model (nodes + edges)
2. Diffs two graphs by node ID and edge identity
3. Generates annotated mermaid source with `style` and `linkStyle` directives

All other diagram types fall through to `None` (triggering a side-by-side fallback in the diff view).

## Diagram Types Requiring Support

| # | Type | Keyword(s) | Structural Elements |
|---|------|-----------|---------------------|
| 1 | ✅ Flowchart | `graph`, `flowchart` | Nodes, edges, subgraphs |
| 2 | Sequence | `sequenceDiagram` | Participants, messages, activations, notes, loops/alt/par |
| 3 | State | `stateDiagram-v2` | States, transitions, forks/joins, notes, composite states |
| 4 | Class | `classDiagram` | Classes (fields + methods), relationships |
| 5 | ER | `erDiagram` | Entities (attributes), relationships |
| 6 | Gantt | `gantt` | Sections, tasks (dates, durations, dependencies) |
| 7 | Pie | `pie` | Slices (label + value) |
| 8 | Journey | `journey` | Sections, tasks (rating, actors) |
| 9 | Quadrant | `quadrantChart` | Axes, points |
| 10 | Mindmap | `mindmap` | Tree nodes (parent-child hierarchy) |
| 11 | Timeline | `timeline` | Periods, events |
| 12 | C4 | `C4Context`, `C4Container`, etc. | People, systems, containers, relationships |
| 13 | Git Graph | `gitGraph` | Commits, branches, merges, checkouts |

## Architecture

### Design Constraints

1. **Independent of CSS/DOM** — the diff engine must be a pure Python function: `(old_source: str, new_source: str) → str | None`. No coupling to frontend styles, web components, or browser APIs.
2. **Annotation via mermaid syntax only** — output must be valid mermaid source that renders correctly in any mermaid renderer. Use only mermaid's own styling mechanisms (`style`, `linkStyle`, `classDef`, class assignments, and `%%` comments for metadata).
3. **Consistent colour convention** — all diagram types use the same palette:
   - Added: `#c6efce` fill / `#27ae60` stroke (green)
   - Removed: `#fce4e4` fill / `#e74c3c` stroke (red, dashed)
   - Changed: `#fff3cd` fill / `#f39c12` stroke (yellow/amber)
4. **Same public interface** — every diagram type plugs into `mermaid_structural_diff(old_source, new_source) → str | None`.
5. **Graceful fallback** — if parsing fails for any reason, return `None`. The caller already handles this by falling back to side-by-side.

### Module Structure

```
backend/services/
├── mermaid_diff.py              # Public API + dispatcher + base classes
└── mermaid_parsers/
    ├── __init__.py              # Registry of diagram parsers
    ├── base.py                  # Abstract base classes (DiagramModel, DiagramParser, DiagramDiffer)
    ├── flowchart.py             # Existing flowchart parser (refactored from mermaid_diff.py)
    ├── sequence.py              # Sequence diagram parser + differ
    ├── state.py                 # State diagram parser + differ
    ├── class_diagram.py         # Class diagram parser + differ
    ├── er.py                    # ER diagram parser + differ
    ├── gantt.py                 # Gantt chart parser + differ
    ├── pie.py                   # Pie chart parser + differ
    ├── journey.py               # Journey map parser + differ
    ├── quadrant.py              # Quadrant chart parser + differ
    ├── mindmap.py               # Mindmap parser + differ
    ├── timeline.py              # Timeline parser + differ
    ├── c4.py                    # C4 diagram parser + differ
    └── gitgraph.py              # Git graph parser + differ
```

### Base Classes

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class DiffResult:
    """Uniform result from any diagram differ."""
    has_changes: bool
    annotated_source: str | None  # Valid mermaid source with style annotations

class DiagramModel(ABC):
    """Abstract parsed representation of a mermaid diagram."""
    pass

class DiagramParser(ABC):
    """Parses raw mermaid source into a DiagramModel."""

    @abstractmethod
    def can_parse(self, source: str) -> bool:
        """Return True if this parser handles the given source."""
        ...

    @abstractmethod
    def parse(self, source: str) -> DiagramModel:
        """Parse source into a diagram model. Raises ValueError on failure."""
        ...

class DiagramDiffer(ABC):
    """Diffs two DiagramModels and produces annotated source."""

    @abstractmethod
    def diff(self, old: DiagramModel, new: DiagramModel) -> DiffResult:
        """Compare two models and return annotated mermaid source."""
        ...
```

### Dispatcher

```python
# In mermaid_diff.py (updated public API)

_PARSERS: list[tuple[DiagramParser, DiagramDiffer]] = []

def register_diagram_type(parser: DiagramParser, differ: DiagramDiffer):
    """Register a parser/differ pair. Called at module import time."""
    _PARSERS.append((parser, differ))

def mermaid_structural_diff(old_source: str, new_source: str) -> str | None:
    """
    Public API — unchanged signature.
    Dispatches to the appropriate parser/differ based on diagram type detection.
    """
    for parser, differ in _PARSERS:
        if parser.can_parse(old_source) and parser.can_parse(new_source):
            try:
                old_model = parser.parse(old_source)
                new_model = parser.parse(new_source)
                result = differ.diff(old_model, new_model)
                return result.annotated_source if result.has_changes else None
            except (ValueError, Exception):
                return None  # Graceful fallback
    return None
```

### Annotation Strategies Per Diagram Type

Each diagram type has different styling mechanisms available in mermaid. The annotation strategy adapts to what the syntax supports:

| Diagram | Styling Mechanism |
|---------|-------------------|
| Flowchart | `style NodeID fill:...,stroke:...` + `linkStyle N stroke:...` |
| Sequence | `participant` notes + `%%` comments + message text markup |
| State | `classDef` + `class` + state notes |
| Class | `style` + `cssClass` + notes |
| ER | Limited — use entity comments/annotations |
| Gantt | `crit` keyword + section markers |
| Pie | Limited — annotate title/slice labels |
| Journey | Task annotations |
| Quadrant | Point styling |
| Mindmap | `::icon` + node classes |
| Timeline | Section annotations |
| C4 | `Rel` descriptions + boundary labels |
| Git Graph | Branch options + commit highlighting |

For diagram types with limited native styling (ER, Pie, Journey), the annotated source will:
1. Include `%%` comments marking changes (machine-readable)
2. Append text markers to labels (e.g. `[+]` for added, `[-]` for removed, `[~]` for changed)
3. When rendered, the frontend can read the comments and apply CSS overlays

This keeps the output as valid mermaid source that degrades gracefully in any renderer.

## Implementation Plan

### Phase 1: Refactor (Foundation)

**Goal:** Extract the existing flowchart implementation into the new modular structure without changing behaviour.

1. Create `backend/services/mermaid_parsers/` package
2. Create `base.py` with abstract classes
3. Move existing flowchart logic to `flowchart.py`, implementing the new interfaces
4. Update `mermaid_diff.py` to use the dispatcher pattern
5. Ensure all existing tests still pass
6. Add integration test confirming the refactor is behaviour-preserving

**Deliverable:** Same functionality, new structure. Zero behaviour change.

### Phase 2: Simple Diagrams (Quick Wins)

**Goal:** Implement parsers for diagram types with straightforward structure.

#### 2a: Pie Chart
- Model: list of `(label, value)` slices
- Diff: compare by label; detect added/removed/value-changed slices
- Annotation: modify labels with markers (`[+]`, `[-]`, `[~]`)

#### 2b: Journey Map
- Model: list of sections, each with tasks `(name, rating, actors)`
- Diff: compare sections by name, tasks by name within sections
- Annotation: append markers to task names

#### 2c: Timeline
- Model: list of periods, each with events
- Diff: compare periods and events by text content
- Annotation: append markers to event descriptions

#### 2d: Quadrant Chart
- Model: axis labels + list of points `(label, x, y)`
- Diff: compare points by label; detect position changes
- Annotation: modify point labels

**Tests for each:** parser round-trip test + diff test for added/removed/changed elements.

### Phase 3: Graph-Like Diagrams

**Goal:** Implement parsers for diagram types that have nodes and relationships (similar to flowchart but with different syntax).

#### 3a: State Diagram
- Model: states (with sub-states), transitions `(from, to, label)`
- Diff: compare states by name, transitions by (from, to) pair
- Annotation: `classDef` + `class` assignments for state highlighting; re-insert removed transitions as annotated paths

#### 3b: Class Diagram
- Model: classes (name, fields, methods), relationships (type, from, to, label)
- Diff: compare classes by name; within classes, compare members by signature
- Annotation: `style` for class highlighting; annotate added/removed members in the class definition

#### 3c: ER Diagram
- Model: entities (with attributes), relationships (cardinality, from, to, label)
- Diff: compare entities by name, attributes by name within entity, relationships by (from, to)
- Annotation: label markers + `%%` comments

#### 3d: C4 Diagrams
- Model: people, systems, containers, components, relationships
- Diff: compare elements by ID/name, relationships by (from, to)
- Annotation: description text markers + boundary labels

### Phase 4: Sequence-Based Diagrams

**Goal:** Handle ordered/sequential diagram types where the meaningful diff is about message/event ordering and participants.

#### 4a: Sequence Diagram
- Model: participants (ordered list), messages `(from, to, type, text)`, groups (loop/alt/par with conditions)
- Diff: compare participant lists (order matters); compare message sequences using LCS; compare group structure
- Annotation strategy:
  - New participants: append `(NEW)` to participant alias
  - Removed participants: re-insert with `(REMOVED)` marker
  - Changed messages: mark with text annotation
  - Added/removed messages: insert with `Note` annotations marking the change
  - Group changes: annotate group labels

#### 4b: Git Graph
- Model: ordered list of operations (commit, branch, checkout, merge)
- Diff: LCS on operation sequences
- Annotation: commit message markers for added/removed operations

### Phase 5: Tree/Hierarchy Diagrams

#### 5a: Mindmap
- Model: tree of nodes (parent-child relationships, with optional icons/classes)
- Diff: tree diff algorithm — match nodes by label, detect moves/adds/removes
- Annotation: node class assignments for highlighting

### Phase 6: Time-Based Diagrams

#### 6a: Gantt Chart
- Model: sections with tasks `(name, status, start, end, dependencies)`
- Diff: compare sections by name, tasks by name within sections; detect schedule changes
- Annotation: `crit` keyword for changed tasks, section-level markers

## Consistency Requirements

### Colour Palette (Hard-coded constants, not CSS)

```python
ADDED_FILL = "#c6efce"
ADDED_STROKE = "#27ae60"
REMOVED_FILL = "#fce4e4"
REMOVED_STROKE = "#e74c3c"
CHANGED_FILL = "#fff3cd"
CHANGED_STROKE = "#f39c12"
```

These are embedded directly in the mermaid `style` directives. They are **not** CSS custom properties — they work identically regardless of what CSS is loaded, what theme is active, or whether the diagram is rendered in markdown-docs, GitHub, GitLab, or any other mermaid viewer.

### Text Markers (for diagrams without styling support)

```
[+] = added
[-] = removed
[~] = changed
```

These appear in element labels/descriptions and are human-readable in any context.

### Machine-Readable Comments

```mermaid
%% md-diff: added participant Alice
%% md-diff: removed message 3
%% md-diff: changed task "Deploy" rating 3->5
```

These `%%` comments are ignored by the mermaid renderer but can be parsed by the frontend for additional highlighting (CSS overlays, tooltips, etc.) when available.

## Testing Strategy

### Unit Tests (per diagram type)

Each parser/differ gets its own test file:

```
backend/tests/
├── test_mermaid_flowchart.py      # Existing (rename from test_diff.py mermaid section)
├── test_mermaid_sequence.py
├── test_mermaid_state.py
├── test_mermaid_class.py
├── test_mermaid_er.py
├── test_mermaid_gantt.py
├── test_mermaid_pie.py
├── test_mermaid_journey.py
├── test_mermaid_quadrant.py
├── test_mermaid_mindmap.py
├── test_mermaid_timeline.py
├── test_mermaid_c4.py
└── test_mermaid_gitgraph.py
```

Each test file covers:
1. **Parser correctness** — known input → expected model
2. **Round-trip** — parse → emit → parse produces equivalent model
3. **Diff detection** — added/removed/changed elements are correctly identified
4. **Annotation validity** — output is valid mermaid syntax (parseable by mermaid.js)
5. **No-change case** — identical inputs produce `has_changes=False`
6. **Graceful failure** — malformed input returns `None` (never raises)

### Integration Tests

- End-to-end test: markdown with diagram → rendered diff API → response contains `kind="mermaid"` with `diff_html`
- Test that unsupported/malformed diagrams still produce a valid response (fallback to side-by-side)

### Validation Script

A script that feeds annotated mermaid output to mermaid.js (via Node or puppeteer) and confirms it renders without errors. Run as a CI check.

## Maintainability

### Adding a New Diagram Type

To add support for a new mermaid diagram type:

1. Create `backend/services/mermaid_parsers/<type>.py`
2. Implement `<Type>Parser(DiagramParser)` with `can_parse()` and `parse()`
3. Implement `<Type>Differ(DiagramDiffer)` with `diff()`
4. Register in `mermaid_parsers/__init__.py`
5. Add tests in `backend/tests/test_mermaid_<type>.py`

No changes needed to `mermaid_diff.py`, the API layer, or the frontend.

### Parser Robustness Guidelines

- Use regex for line-by-line parsing (mermaid syntax is not context-free in general)
- Skip lines that don't match expected patterns (don't fail on unknown syntax)
- Handle optional elements (labels, styles, annotations) as truly optional
- Set a recursion/depth limit for nested structures (composite states, subgraphs)
- Test against real-world diagrams from mermaid documentation and GitHub repos

### Versioning Considerations

Mermaid's syntax evolves. To handle this:

- Pin to a known mermaid syntax version in documentation
- Parsers should be tolerant of unknown keywords (skip, don't crash)
- The `can_parse()` check should be based on the header keyword only (e.g. `sequenceDiagram`), not deep syntax validation
- When mermaid adds new syntax, parsers can be updated independently

## Independence Guarantee

The mermaid diff engine is designed to be used **outside** markdown-docs:

```python
from backend.services.mermaid_diff import mermaid_structural_diff

# Pure function: string in, string out
annotated = mermaid_structural_diff(old_source, new_source)
if annotated:
    print(annotated)  # Valid mermaid source, renders anywhere
```

No imports from:
- Frontend code
- FastAPI / web framework
- Configuration system (colours are hard-coded constants)
- Database or file I/O

The only dependencies are:
- Python standard library (`re`, `dataclasses`, `abc`)
- The internal `mermaid_parsers` package

This means the diff engine can be:
- Extracted into a standalone Python package
- Used in CI pipelines to annotate diagram changes in PRs
- Integrated into other documentation tools
- Called from CLI scripts

## Timeline Estimate

| Phase | Scope | Effort |
|-------|-------|--------|
| Phase 1 | Refactor | 1–2 days |
| Phase 2 | Pie, Journey, Timeline, Quadrant | 3–4 days |
| Phase 3 | State, Class, ER, C4 | 5–7 days |
| Phase 4 | Sequence, Git Graph | 4–5 days |
| Phase 5 | Mindmap | 2–3 days |
| Phase 6 | Gantt | 2–3 days |
| **Total** | | **~3–4 weeks** |

## Success Criteria

- [ ] All 13 mermaid diagram types produce meaningful structural diffs
- [ ] `mermaid_structural_diff()` signature unchanged — fully backward compatible
- [ ] All annotated output is valid mermaid syntax (renders without error)
- [ ] Zero coupling to CSS, DOM, or frontend code
- [ ] Each diagram type can be added/modified independently
- [ ] Test coverage ≥ 90% for all parsers and differs
- [ ] Graceful fallback for every failure mode (never crash, always return `None` on error)
