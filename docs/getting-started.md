# Getting Started

## Prerequisites

- [pixi](https://prefix.dev/) — environment and dependency management
- A modern browser (Chrome 90+, Firefox 90+, Safari 16+)

The following are installed automatically by pixi:

- [pandoc](https://pandoc.org/) ≥ 3.1 — markdown rendering
- git ≥ 2.40 — version control operations
- Python ≥ 3.11 — backend runtime

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd markdown-docs

# Install all dependencies (Python, pandoc, git — everything)
pixi install
```

That's it. No separate `pip install`, no system package installs, no Node.js.

## Quick Start

```bash
# 1. Create the local test repository
pixi run repo-create

# 2. Seed it with sample markdown documents
pixi run repo-seed

# 3. Start the development server
pixi run dev
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

You'll see the editor UI with a sidebar listing the sample documents. Click any document to start editing.

## What Just Happened?

1. `repo-create` initialised a git repository at `.test-repo/` with an initial commit.
2. `repo-seed` added sample markdown files (with various formatting, code blocks, mermaid diagrams) to that repo.
3. `dev` started a FastAPI server on port 8000 serving both the REST API and the frontend.

## Available Tasks

| Task | Description |
|------|-------------|
| `pixi run dev` | Start the dev server (auto-reload on backend changes) |
| `pixi run dev-verbose` | Dev server with debug logging |
| `pixi run test` | Run the test suite |
| `pixi run repo-create` | Create `.test-repo/` with an initial commit |
| `pixi run repo-seed` | Populate with sample markdown documents |
| `pixi run repo-destroy` | Delete `.test-repo/` entirely |
| `pixi run repo-reset` | destroy + create (clean slate) |
| `pixi run lint` | Check Python syntax |

## Next Steps

- [Configuration](configuration.md) — customise the server, repo path, and editor settings
- [Editing](editing.md) — learn the editing workflow
- [Using Your Own Repo](using-your-own-repo.md) — point at an existing documentation repository
