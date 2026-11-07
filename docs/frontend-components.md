# Frontend Components

The frontend is built entirely with native web components (custom elements with Shadow DOM). Each component is a single ES Module file with no dependencies beyond the shared `lib/utils.js`.

## Component Overview

| Component | Element | File |
|-----------|---------|------|
| Editor | `<md-editor>` | `components/md-editor.js` |
| Diff View | `<md-diff-view>` | `components/md-diff-view.js` |
| Branch Bar | `<md-branch-bar>` | `components/md-branch-bar.js` |
| Mermaid | `<md-mermaid>` | `components/md-mermaid.js` |
| Code Block | `<md-code-block>` | `components/md-code-block.js` |
| Document | `<md-document>` | `components/md-document.js` |

---

## `<md-editor>`

Split-pane markdown editor with live pandoc preview.

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | `""` | Document path (for display and API calls) |
| `branch` | string | `""` | Current branch name |
| `autosave` | number | `30` | Autosave interval in seconds (0 = off) |
| `readonly` | flag | — | If present, hides the editor pane |
| `layout` | string | `"split"` | `"editor"` / `"split"` / `"preview"` |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `content` | string | Get/set the raw markdown content |

### Events

| Event | Detail | Description |
|-------|--------|-------------|
| `content-change` | `{ content, path, branch }` | Fired on every keystroke |
| `save-request` | `{ content, path, branch }` | Fired on Ctrl+S or Save click |
| `autosave` | `{ content, path, branch }` | Fired on autosave timer |

### Methods

| Method | Description |
|--------|-------------|
| `markSaved()` | Call after a successful save to update status |
| `markSaveError(message)` | Call after a failed save to show error |

---

## `<md-diff-view>`

Block+word level visual diff viewer. Consumes the `RenderedDiff` JSON from the API.

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"side-by-side"` | `"side-by-side"` or `"inline"` |
| `base-label` | string | `"Before"` | Label for the old/left side |
| `new-label` | string | `"After"` | Label for the new/right side |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `diff` | object | Set to a `RenderedDiff` response object |

### Usage

```javascript
const view = document.querySelector("md-diff-view");
view.setAttribute("mode", "side-by-side");
view.diff = await api.post("/api/diff/rendered", { path, base_branch, compare_branch });
```

### Block Rendering

The component handles five block kinds:

- `unchanged` — rendered normally, no highlight
- `added` — green background
- `removed` — red background
- `changed` — yellow background with word-level marks in the diff_html
- `mermaid` — special diagram diff with annotated/side-by-side toggle

---

## `<md-branch-bar>`

Branch selector strip with create, switch, and merge controls.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `branches` | array | Array of `BranchInfo` objects from the API |
| `current` | string | Current branch name |
| `prefix` | string | Branch prefix (e.g. `"docs-"`) |
| `default` | string | Default/trunk branch name |

### Events

| Event | Detail | Description |
|-------|--------|-------------|
| `branch-switch` | `{ branch }` | User selected a different branch |
| `branch-create` | `{ name }` | User wants to create a branch (name without prefix) |
| `branch-merge` | `{ source, target }` | User clicked Review & merge |
| `branch-refresh` | — | User clicked the refresh button |

---

## `<md-mermaid>`

Renders mermaid diagrams. Mermaid.js is loaded lazily from CDN only when this element appears on the page.

### Usage

The element's text content is the mermaid source:

```html
<md-mermaid>graph TD
    A-->B
    B-->C</md-mermaid>
```

This is emitted by pandoc via a Lua filter that converts ` ```mermaid ` code blocks into `<md-mermaid>` elements.

### Behaviour

- Mermaid.js is loaded from jsDelivr CDN on first use
- If loading fails, the raw source is displayed in a `<pre>` block as fallback
- If the diagram source has a syntax error, the error message is shown alongside the raw source
- Uses `securityLevel: "loose"` to allow click handlers and links in diagrams

---

## `<md-code-block>`

Syntax-highlighted code block with a copy-to-clipboard button.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `lang` | string | Language identifier (e.g. `"python"`, `"javascript"`) |

### Usage

```html
<md-code-block lang="python">def hello():
    print("world")</md-code-block>
```

### Behaviour

- Highlight.js loaded lazily from CDN on first use
- CSS injected into Shadow DOM for colour isolation
- Copy button appears on hover (top-right corner)
- Falls back to plain monospace text if highlight.js fails

---

## `<md-document>`

Typography wrapper for rendered markdown content. Provides consistent heading sizes, paragraph spacing, link styles, etc.

### Usage

Used as a container around pandoc-rendered HTML in contexts where document-style typography is needed.

---

## Shared Utilities (`lib/utils.js`)

The `lib/utils.js` module exports:

| Export | Description |
|--------|-------------|
| `debounce(fn, wait)` | Returns a debounced version of `fn` |
| `escapeHtml(str)` | Escapes HTML special characters |
| `api` | Fetch wrapper with `get`, `post`, `put`, `delete` methods |
| `sanitizeBranchName(name)` | Sanitises user input for branch names |
| `docUrl(path, branch, mode)` | Builds a URL for a document |
| `parseLocation()` | Parses current URL into `{ path, branch, mode }` |
| `relativeTime(isoDate)` | Formats ISO date as "3h ago" etc. |

### API Client

```javascript
import { api } from "/lib/utils.js";

// GET with query params
const data = await api.get("/api/documents", { branch: "main" });

// POST with JSON body
const diff = await api.post("/api/diff/rendered", { path: "doc.md" });

// PUT
await api.put("/api/documents/doc.md", { content, branch });
```

The client automatically:
- Sets `Content-Type: application/json` for POST/PUT
- Throws descriptive errors on non-2xx responses
- Handles 204 No Content gracefully

## Theming

All components use CSS custom properties (design tokens) defined in `styles/base.css`:

```css
--md-text         /* Body text colour */
--md-bg           /* Page background */
--md-code-bg      /* Code/toolbar background */
--md-border       /* Border colour */
--md-muted        /* Secondary text */
--md-heading      /* Heading colour */
--md-link         /* Link colour */
--md-error        /* Error/danger colour */
--md-bar-bg       /* App bar background */
--md-diff-added   /* Diff: added block background */
--md-diff-removed /* Diff: removed block background */
--md-diff-block   /* Diff: changed block background */
--md-diff-word    /* Diff: word-level highlight */
```

Dark mode is handled automatically via `@media (prefers-color-scheme: dark)` in `base.css`.
