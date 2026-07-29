#!/usr/bin/env python3
"""
scripts/manage_test_repo.py

Create, destroy, reset, or seed the local test git repository used for
development and testing. Called by pixi tasks:

    pixi run repo-create    # Create .test-repo/ with initial commit
    pixi run repo-destroy   # Remove .test-repo/ entirely
    pixi run repo-reset     # destroy + create
    pixi run repo-seed      # Populate with sample documents

The repo is intentionally placed at .test-repo/ (gitignored) so it
lives inside this project directory but is never committed.
"""
from __future__ import annotations

import shutil
import sys
import textwrap
from pathlib import Path

import pygit2

# ── Config ─────────────────────────────────────────────────────────────────────

REPO_DIR = Path(__file__).parent.parent / ".test-repo"
AUTHOR   = pygit2.Signature("markdown-docs test", "test@markdown-docs.local")

SAMPLE_DOCS: dict[str, str] = {
    "README.md": textwrap.dedent("""\
        # markdown-docs Test Repo

        This is the test repository used for local development.
        It demonstrates the markdown-docs editor features.

        ## Features

        - **Git-native editing** — every save is a commit
        - **Branch-based workflow** — create a `docs-` branch to start editing
        - **Visual diffing** — see block and word-level changes side by side

        ## Quick Start

        ```bash
        pixi run dev
        ```

        Then open [http://localhost:8000](http://localhost:8000).
    """),
    "guide/getting-started.md": textwrap.dedent("""\
        # Getting Started

        Welcome to markdown-docs!

        ## Installation

        Install [pixi](https://prefix.dev/) if you haven't already:

        ```bash
        curl -fsSL https://pixi.sh/install.sh | bash
        ```

        Then run:

        ```bash
        pixi install
        pixi run repo-create
        pixi run dev
        ```

        ## Creating Your First Branch

        Use the branch bar at the top of the editor to create a new `docs-` branch.
        All your edits will be committed to that branch.

        When you're done, click **Review & merge** to see a visual diff and merge
        your changes back to `main`.
    """),
    "guide/markdown-reference.md": textwrap.dedent("""\
        # Markdown Reference

        This page demonstrates GitLab-Flavored Markdown features.

        ## Text Formatting

        **Bold**, *italic*, ~~strikethrough~~, `inline code`.

        ## Tables

        | Feature       | Supported |
        |---------------|-----------|
        | Tables        | ✅        |
        | Task lists    | ✅        |
        | Mermaid       | ✅        |
        | Code blocks   | ✅        |
        | Math (KaTeX)  | planned   |

        ## Task List

        - [x] Scaffold project
        - [x] FastAPI backend
        - [x] Web components
        - [ ] Write more docs

        ## Code Block

        ```python
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        print(greet("world"))
        ```

        ## Mermaid Diagram

        ```mermaid
        graph TD
            A[User edits doc] --> B[Autosave commit]
            B --> C{Done editing?}
            C -->|No| A
            C -->|Yes| D[Review diff]
            D --> E[Merge to main]
        ```

        ## Blockquote

        > The best documentation is the one that gets written.

        ## Definition List

        Pandoc
        :   A universal document converter used to render this markdown.

        pygit2
        :   Python bindings for libgit2, used for all git operations.
    """),
    "api/overview.md": textwrap.dedent("""\
        # API Overview

        The markdown-docs backend exposes a JSON REST API at `/api/`.

        ## Endpoints

        ### Documents

        | Method | Path | Description |
        |--------|------|-------------|
        | GET    | `/api/documents` | List all docs |
        | GET    | `/api/documents/{path}` | Get doc content |
        | PUT    | `/api/documents/{path}` | Save doc and commit |
        | POST   | `/api/documents/render` | Render markdown to HTML |

        ### Branches

        | Method | Path | Description |
        |--------|------|-------------|
        | GET    | `/api/branches` | List branches |
        | POST   | `/api/branches` | Create doc branch |
        | POST   | `/api/branches/{name}/switch` | Switch branch |
        | POST   | `/api/branches/{name}/merge` | Squash-merge |

        ### Diff

        | Method | Path | Description |
        |--------|------|-------------|
        | POST   | `/api/diff/source` | Unified text diff |
        | POST   | `/api/diff/rendered` | Visual block+word diff |

        See `/api/docs` for the interactive Swagger UI.
    """),
}


# ── Commands ────────────────────────────────────────────────────────────────────

def cmd_create() -> None:
    if REPO_DIR.exists():
        print(f"[repo-create] Already exists: {REPO_DIR}")
        print("  Use 'pixi run repo-reset' to start fresh.")
        return

    print(f"[repo-create] Initialising git repo at {REPO_DIR}")
    repo = pygit2.init_repository(str(REPO_DIR))

    # Create initial empty commit so 'main' branch exists
    tree_id = repo.TreeBuilder().write()
    commit_id = repo.create_commit(
        "refs/heads/main", AUTHOR, AUTHOR,
        "chore: init test repo",
        tree_id, [],
    )
    print(f"[repo-create] Created initial commit: {str(commit_id)[:8]}")
    print(f"[repo-create] Done. Run 'pixi run repo-seed' to add sample docs.")


def cmd_seed() -> None:
    if not REPO_DIR.exists():
        print("[repo-seed] Repo not found. Run 'pixi run repo-create' first.")
        sys.exit(1)

    repo = pygit2.Repository(str(REPO_DIR))
    index = repo.index
    index.read()

    created = []
    for rel_path, content in SAMPLE_DOCS.items():
        abs_path = REPO_DIR / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        index.add(rel_path)
        created.append(rel_path)

    index.write()
    tree_id = index.write_tree()

    try:
        parents = [repo.head.target]
    except pygit2.GitError:
        parents = []

    commit_id = repo.create_commit(
        "refs/heads/main", AUTHOR, AUTHOR,
        "docs: seed sample documents",
        tree_id, parents,
    )
    print(f"[repo-seed] Committed {len(created)} sample docs: {str(commit_id)[:8]}")
    for p in created:
        print(f"  + {p}")


def cmd_destroy() -> None:
    if not REPO_DIR.exists():
        print(f"[repo-destroy] Nothing to remove: {REPO_DIR}")
        return
    shutil.rmtree(REPO_DIR)
    print(f"[repo-destroy] Removed {REPO_DIR}")


def cmd_reset() -> None:
    cmd_destroy()
    cmd_create()


# ── Entry point ─────────────────────────────────────────────────────────────────

COMMANDS = {
    "create":  cmd_create,
    "destroy": cmd_destroy,
    "reset":   cmd_reset,
    "seed":    cmd_seed,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} <{'|'.join(COMMANDS)}>")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
