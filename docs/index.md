# markdown-docs Documentation

A git-native markdown documentation editor with visual diffing — edit documents in the browser, with every save backed by a git commit.

## What is markdown-docs?

markdown-docs gives documentation teams a browser-based editing experience while preserving full git compatibility. Documents are plain markdown files in a git repository. Every save is a commit. When you're ready, squash-merge your edits back to `main` and review a visual diff before merging.

People who prefer other tools (VS Code, Obsidian, vim) can work directly with the repo — they never need to touch this UI.

## Key Features

- **In-browser editing** — split-pane editor with live pandoc preview
- **Git-native** — every save commits to a branch; nothing is stored outside git
- **GitLab-Flavored Markdown** — tables, task lists, strikethrough, mermaid diagrams, syntax-highlighted code blocks
- **Visual diff** — block-level (pale) + word-level (darker) highlights in side-by-side or inline view
- **Source diff** — raw unified diff alongside the rendered diff
- **Mermaid diagram diff** — structural semantic diff for flowchart diagrams, highlighting added/removed/changed nodes and edges
- **Branch workflow** — create `docs-` branches from the UI, merge back to `main` with a squash commit
- **Configurable** — `markdown-docs.yaml` for defaults; CLI args override everything
- **No build step** — frontend is plain ES Modules served directly

## Documentation Guide

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Installation, prerequisites, quick start |
| [Configuration](configuration.md) | Config file reference and CLI options |
| [Editing](editing.md) | Document editing features and workflow |
| [Branching](branching.md) | Branch workflow and merge process |
| [Diffing](diffing.md) | Visual diff and source diff features |
| [API Reference](api-reference.md) | REST API documentation |
| [Architecture](architecture.md) | Project structure and design decisions |
| [Frontend Components](frontend-components.md) | Web component documentation |
| [Using Your Own Repo](using-your-own-repo.md) | Guide for pointing at external repos |

## Planning

| Document | Description |
|----------|-------------|
| [Planning Overview](planning/index.md) | Roadmap and active plans |
| [Mermaid Semantic Diff](planning/mermaid-semantic-diff.md) | Plan for 100% mermaid diagram coverage |

## Quick Links

- **Start the server:** `pixi run dev`
- **API docs (interactive):** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **Run tests:** `pixi run test`
