# markdown-docs

A git-native markdown documentation editor with visual diffing.

Edit documents in the browser. Every save is a git commit. When you're done, squash your branch into a single change and review a block+word-level visual diff before merging.

People who prefer other git tools (VS Code, Obsidian, vim) can work directly with the repo — they never need to use this UI.

---

## Features

- **Full in-browser editing** — split-pane editor with live pandoc preview
- **Git-native** — every save commits to a branch; nothing is stored outside git
- **GitLab-Flavored Markdown** — tables, task lists, strikethrough, mermaid diagrams, code blocks with syntax highlighting
- **Visual diff** — block-level highlights (pale) + word-level highlights (darker) in side-by-side or inline view
- **Source diff** — raw unified diff view alongside the rendered diff
- **Branch workflow** — create `docs-` branches from the UI, merge back to `main` with a squash commit
- **Configurable** — `markdown-docs.yaml` for defaults; CLI args override everything
- **No build step** — frontend is plain ES Modules served directly

---

## Prerequisites

- [pixi](https://prefix.dev/) — for environment management
- [pandoc](https://pandoc.org/) ≥ 3.1 (installed automatically by pixi)
- git ≥ 2.40 (installed automatically by pixi)
- A modern browser (Chrome 90+, Firefox 90+, Safari 16+)

---

## Quick Start

```bash
# 1. Install all dependencies
pixi install

# 2. Create the local test repository
pixi run repo-create

# 3. Seed it with sample documents
pixi run repo-seed

# 4. Start the development server
pixi run dev
```

Open [http://localhost:8000](http://localhost:8000).

---

## Configuration

All settings live in `markdown-docs.yaml`. It is safe to check in.

```yaml
repository:
  path: ".test-repo"        # path to the git repo (relative to this file)
  docs_dir: "."             # sub-directory inside the repo
  branch_prefix: "docs-"   # prefix for editor-created branches
  default_branch: "main"
```

### CLI overrides

Any setting can be overridden at startup without touching the config file:

```bash
# Point at a different repo
pixi run dev -- --repo /path/to/my-docs-repo

# Different docs subdirectory within the repo
pixi run dev -- --repo /path/to/repo --docs-dir docs/

# Different branch prefix
pixi run dev -- --branch-prefix "draft/"

# Different port
pixi run dev -- --port 8080
```

Or directly:

```bash
python -m backend.main --repo /path/to/repo --docs-dir docs/ --port 8080
```

Full option list:

```
Options:
  -c, --config PATH          Path to markdown-docs.yaml
  -r, --repo PATH            Override: git repo path
  -d, --docs-dir PATH        Override: docs sub-directory
  -p, --branch-prefix TEXT   Override: branch prefix
  -h, --host TEXT            Override: bind host
  -P, --port INTEGER         Override: bind port
  --reload                   Enable auto-reload (development)
```

---

## Pixi Tasks

| Task | Description |
|------|-------------|
| `pixi run dev` | Start the dev server (auto-reload) |
| `pixi run dev-verbose` | Dev server with debug logging |
| `pixi run test` | Run the test suite |
| `pixi run repo-create` | Create `.test-repo/` with an initial commit |
| `pixi run repo-seed` | Populate with sample markdown documents |
| `pixi run repo-destroy` | Delete `.test-repo/` entirely |
| `pixi run repo-reset` | destroy + create (clean slate) |
| `pixi run lint` | Check Python syntax |

---

## Workflow

### Editing documents

1. Select a document from the left sidebar.
2. The split-pane editor shows raw markdown (left) and live rendered preview (right).
3. Press **Ctrl+S** or click **Save** — this commits your change to the current branch.
4. Autosave runs every 30 seconds (configurable).

### Branching

1. Click **+ New branch** in the branch bar.
2. Type a short name (e.g. `update-api-docs`) — the prefix is prepended automatically.
3. The branch switches immediately.

All saves on a `docs-` branch go to that branch. Other git tools see normal commits.

### Visual diff and merge

1. While on a `docs-` branch, click **Show diff** in the top bar.
2. Toggle between **Rendered** (visual) and **Source** (unified text) diff.
3. The rendered diff shows:
   - Pale block background for changed/added/removed blocks
   - Darker word-level highlights within changed blocks
4. When satisfied, click **Review & merge** in the branch bar.
5. All commits are squashed to one and merged into `main`.

---

## API

The backend exposes a REST API at `/api/`. Interactive docs at `/api/docs`.

### Key endpoints

```
GET  /api/documents                    List all markdown files
GET  /api/documents/{path}             Get raw content (+ optional rendered HTML)
PUT  /api/documents/{path}             Save and commit
POST /api/documents/render             Render markdown to HTML (no commit)

GET  /api/branches                     List branches
POST /api/branches                     Create a doc branch
POST /api/branches/{name}/switch       Switch branch
POST /api/branches/{name}/merge        Squash-merge into target
GET  /api/branches/{name}/changes      List files changed vs default branch

POST /api/diff/source                  Unified markdown diff
POST /api/diff/rendered                Block+word visual diff
```

---

## Project Layout

```
markdown-docs/
├── backend/
│   ├── api/
│   │   ├── branches.py      Branch CRUD and merge
│   │   ├── diff.py          Source and rendered diffs
│   │   └── documents.py     Document read/write/render
│   ├── models/
│   │   └── schema.py        All Pydantic models
│   ├── services/
│   │   ├── config.py        Config loading + CLI overrides
│   │   ├── diff.py          Diff algorithms (block + word)
│   │   ├── git.py           pygit2 wrapper
│   │   └── pandoc.py        Pandoc render + AST
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_diff.py
│   └── main.py              FastAPI app + Click CLI
├── frontend/
│   ├── components/
│   │   ├── md-branch-bar.js Branch selector UI
│   │   ├── md-code-block.js Syntax highlighting + copy
│   │   ├── md-diff-view.js  Visual diff renderer
│   │   ├── md-document.js   Document typography shell
│   │   ├── md-editor.js     Split-pane editor
│   │   └── md-mermaid.js    Mermaid diagram renderer
│   ├── lib/
│   │   └── utils.js         Shared utilities + API client
│   ├── styles/
│   │   └── base.css         Global styles + CSS tokens
│   └── index.html           App shell
├── templates/
│   └── document.html        Pandoc HTML template
├── scripts/
│   └── manage_test_repo.py  Test repo lifecycle
├── markdown-docs.yaml       Configuration
└── pixi.toml                Dependencies and tasks
```

---

## Diff Implementation Notes

The rendered diff is designed to be robust to partial markdown syntax errors.

**Process:**

1. Both versions are rendered independently via pandoc. A syntax error in one version only affects that render — it never crashes the diff.
2. The resulting HTML is split into top-level blocks (`<p>`, `<h1>`–`<h6>`, `<ul>`, `<pre>`, etc.) using a lightweight HTML parser.
3. Blocks are diffed by content hash using Python's `difflib.SequenceMatcher` (LCS-based).
4. For changed blocks, `diff-match-patch` runs a word-level diff on the text content, and changed words are wrapped in `<mark>` spans.
5. The `<md-diff-view>` component renders the result with pale block backgrounds and darker word highlights.

The source diff is a standard unified diff over the raw markdown lines.

---

## Using Your Own Repo

Point markdown-docs at any git repository containing markdown files:

```bash
pixi run dev -- --repo /path/to/your/repo --docs-dir docs/
```

Or set it in `markdown-docs.yaml`:

```yaml
repository:
  path: /path/to/your/repo
  docs_dir: docs/
  branch_prefix: "docs-"
  default_branch: main
```

The tool only reads/writes files under `docs_dir`. It won't touch anything else in the repo.

---

## License

MIT
