# Architecture

## Design Principles

1. **Git is the source of truth** — no database, no external state. Everything lives in the git repository.
2. **No build step** — the frontend is plain ES Modules served directly by the backend. No webpack, no bundler, no transpiler.
3. **Graceful degradation** — a broken mermaid diagram doesn't crash the editor; a pandoc failure doesn't break the diff.
4. **External tool compatibility** — any git tool can read/write the same repo. The UI is optional.
5. **Minimal dependencies** — the backend has a focused dependency set; the frontend uses zero npm packages.

## Project Layout

```
markdown-docs/
├── backend/
│   ├── api/
│   │   ├── branches.py          # Branch CRUD and merge endpoints
│   │   ├── diff.py              # Source and rendered diff endpoints
│   │   └── documents.py         # Document read/write/render endpoints
│   ├── models/
│   │   └── schema.py            # All Pydantic models (config, API, domain)
│   ├── services/
│   │   ├── config.py            # Config loading + CLI overrides
│   │   ├── diff.py              # Diff algorithms (block, word, structural)
│   │   ├── git.py               # pygit2 wrapper (all git operations)
│   │   ├── mermaid_diff.py      # Mermaid structural diff (flowchart only)
│   │   └── pandoc.py            # Pandoc render + AST extraction
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_diff.py
│   └── main.py                  # FastAPI app factory + Click CLI
├── frontend/
│   ├── components/
│   │   ├── md-branch-bar.js     # Branch selector and status strip
│   │   ├── md-code-block.js     # Syntax highlighting + copy button
│   │   ├── md-diff-view.js      # Visual diff renderer
│   │   ├── md-document.js       # Document typography shell
│   │   ├── md-editor.js         # Split-pane editor with live preview
│   │   └── md-mermaid.js        # Mermaid diagram renderer (lazy CDN load)
│   ├── lib/
│   │   └── utils.js             # API client, debounce, URL helpers
│   ├── styles/
│   │   └── base.css             # Global styles, CSS tokens, app layout
│   └── index.html               # App shell + orchestration script
├── templates/
│   ├── document.html            # Pandoc HTML template
│   └── filters/
│       └── codeblock.lua        # Pandoc Lua filter (code → web components)
├── scripts/
│   └── manage_test_repo.py      # Test repo lifecycle (create/seed/destroy)
├── markdown-docs.yaml           # Configuration
└── pixi.toml                    # Dependencies and tasks
```

## Backend Architecture

### FastAPI Application

The backend is a FastAPI application created via a factory function in `main.py`. It mounts:

- Three API routers (`/api/documents`, `/api/branches`, `/api/diff`)
- A meta router (`/api/health`, `/api/config`)
- A static file mount for the frontend (`/` catch-all, must be last)

### Service Layer

All business logic lives in the `services/` package:

| Service | Responsibility |
|---------|---------------|
| `config.py` | Load and resolve `markdown-docs.yaml` + CLI overrides |
| `git.py` | All pygit2 operations (read, write, branch, merge) |
| `pandoc.py` | Subprocess calls to pandoc for rendering |
| `diff.py` | Block splitting, LCS diff, word diff, structural HTML diff |
| `mermaid_diff.py` | Flowchart parsing, graph diffing, annotated source generation |

API route handlers are thin — they validate input, call services, and return Pydantic models.

### Git Operations

All git operations go through `services/git.py`. The design:

- Uses `pygit2` (libgit2 bindings) for performance — no shelling out to `git`.
- Reads from the git object store for branch content (no checkout required for reads).
- Writes to the working tree only when committing (write → stage → commit in one operation).
- Branch names are always sanitised and prefixed.

### Diff Pipeline

The rendered diff pipeline processes content through multiple stages:

```
Old markdown ──→ pandoc ──→ HTML ──→ Block split ──→┐
                                                     ├──→ LCS diff ──→ Word diff ──→ Result
New markdown ──→ pandoc ──→ HTML ──→ Block split ──→┘
```

For mermaid blocks, a parallel path handles structural diffing:

```
Old mermaid source ──→ Parse graph ──→┐
                                       ├──→ Diff nodes/edges ──→ Annotated source
New mermaid source ──→ Parse graph ──→┘
```

### Configuration

Configuration uses a singleton pattern — loaded once at startup, accessible everywhere via `get_config()`. CLI arguments override YAML file values, which override built-in defaults.

## Frontend Architecture

### No Build, No Bundle

The frontend is entirely browser-native:

- ES Modules loaded via `<script type="module">`
- Custom elements (web components) with Shadow DOM
- CSS custom properties for theming
- No npm, no node_modules, no transpilation

### Web Components

Each UI element is a self-contained custom element:

| Component | Purpose |
|-----------|---------|
| `<md-editor>` | Split-pane editor with live preview |
| `<md-diff-view>` | Visual diff renderer (side-by-side / inline) |
| `<md-branch-bar>` | Branch selector, create, merge UI |
| `<md-mermaid>` | Mermaid diagram renderer (lazy load from CDN) |
| `<md-code-block>` | Syntax-highlighted code with copy button |
| `<md-document>` | Typography wrapper for rendered content |

Components communicate via:

- **Properties** — parent sets data (e.g. `editor.content = "..."`)
- **Custom events** — child notifies parent (e.g. `save-request`, `branch-switch`)
- **Attributes** — declarative configuration (e.g. `mode="side-by-side"`)

### App Shell

`index.html` contains the app shell — layout structure, component wiring, and a `<script type="module">` block that orchestrates:

- Bootstrap (fetch config, load branches, load doc list)
- Event handlers for branch operations, editor saves, diff loading
- URL state management (query params for path/branch)
- Toast notifications

### Theming

CSS custom properties defined in `base.css` provide design tokens:

- Light mode by default
- Dark mode via `@media (prefers-color-scheme: dark)`
- Components use `var(--md-*)` tokens from their shadow DOM

## Key Design Decisions

### Why pygit2 instead of subprocess git?

Performance and reliability. pygit2 (libgit2) operates directly on the git object store without spawning processes. This matters when the editor makes many rapid saves.

### Why pandoc for rendering?

Pandoc handles the full GitLab-Flavored Markdown spec correctly, including edge cases in table alignment, nested lists, and definition lists. A JavaScript markdown parser would be faster but less correct.

### Why web components instead of React/Vue?

- Zero build step — no bundler configuration to maintain
- Self-contained — each component is one file with its own styles
- Standard — no framework lock-in, works in any browser
- Simple — the app is small enough that a framework adds complexity without proportional benefit

### Why not a SPA router?

The app uses simple query parameters (`?path=...&branch=...`) and `history.replaceState`. There's only one page — no navigation between distinct views that would benefit from a router.
