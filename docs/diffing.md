# Visual Diff & Source Diff

markdown-docs provides two complementary views for reviewing changes: a **rendered visual diff** and a **source (text) diff**.

## Opening the Diff Panel

1. Open any document while on a doc branch.
2. Click **Show diff** in the app bar.
3. The diff panel opens as a full-height overlay.
4. Toggle between **Rendered** and **Source** views using the radio buttons.
5. Press **Escape** or click **✕ Close** to dismiss.

The diff always compares the current branch against the default branch (`main`).

## Rendered Diff

The rendered diff shows your changes as they appear in the final documentation — not as raw markdown, but as formatted HTML.

### How It Works

1. Both the old (`main`) and new (current branch) versions are rendered independently via pandoc.
2. The resulting HTML is split into top-level blocks (paragraphs, headings, lists, tables, code blocks, etc.).
3. Blocks are compared using content hashing and `difflib.SequenceMatcher` (LCS-based algorithm).
4. For changed blocks, a word-level diff highlights exactly what changed within the block.
5. The `<md-diff-view>` web component renders the result.

### Visual Indicators

| Indicator | Meaning |
|-----------|---------|
| Pale green background | Block was added |
| Pale red background | Block was removed |
| Pale yellow background | Block was changed |
| Darker orange highlight | Specific words that changed (within a changed block) |
| Strikethrough with red | Words that were removed |

### View Modes

Toggle between two layouts in the diff toolbar:

- **Side by side** — old on the left, new on the right (default)
- **Inline** — sequential, with gutter indicators (+, −, ~)

### Block-Level vs Word-Level

The diff operates at two granularities (configurable via `diff.rendered_diff_mode`):

- **Block-level** — identifies which paragraphs/headings/list items changed
- **Word-level** — within changed blocks, highlights the specific words that differ

The recommended mode is `"both"` (the default), which shows pale block backgrounds with darker word-level highlights inside.

### Structural Diff for Complex Blocks

For structured HTML content (tables, lists, blockquotes), the diff engine recurses into children:

- **Tables** — row-level and cell-level diffing
- **Lists** — item-level diffing with word-level detail inside changed items
- **Code blocks** — line-level diff with per-line backgrounds and token-level highlights
- **Mermaid diagrams** — structural semantic diff (see below)

### Mermaid Diagram Diff

When a mermaid diagram block changes, the diff engine performs a **structural comparison** rather than a text diff:

1. Both old and new diagram sources are parsed into a graph model (nodes + edges).
2. Nodes are compared by ID: added, removed, or label-changed.
3. Edges are compared by (source, target, label) tuples.
4. An annotated diagram is generated with:
   - **Green** nodes/edges = added
   - **Red dashed** nodes/edges = removed
   - **Yellow** nodes = label changed

The diff view shows two sub-views for diagram changes:

- **Highlighted** — a single annotated diagram with colour-coded changes (default)
- **Side by side** — old diagram on the left, new on the right

Currently, structural diff is supported for **flowchart/graph** diagrams only. Other diagram types (sequence, state, class, ER, etc.) fall back to side-by-side rendering without structural annotation.

## Source Diff

The source diff shows a standard unified text diff of the raw markdown content:

```
@@ -3,5 +3,5 @@
 Some unchanged text.
 
-Original paragraph content.
+Updated paragraph content.
 
 More unchanged text.
```

This is the same format you'd see from `git diff`. Useful for reviewing exact markdown syntax changes.

## Robustness

The diff engine is designed to be tolerant of errors:

- A syntax error in one version only affects that version's render — it never crashes the diff.
- If pandoc fails on either version, the raw content is escaped and wrapped in a `<p>` tag as a fallback.
- Mermaid diagrams that fail to parse simply fall back to side-by-side rendering.
- The diff always produces a result, even for pathologically different content.
