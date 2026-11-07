# Configuration

All settings live in `markdown-docs.yaml` at the project root. This file is safe to check into version control — it contains no secrets.

## Full Configuration Reference

```yaml
# ── Server ────────────────────────────────────────────────────────────────────
server:
  host: "127.0.0.1"       # Bind address
  port: 8000              # Bind port
  proxy_headers: false    # Set true only behind a reverse proxy

# ── Repository ────────────────────────────────────────────────────────────────
repository:
  path: ".test-repo"        # Path to git repo (relative to config file)
  docs_dir: "."             # Sub-directory inside the repo for documents
  branch_prefix: "docs-"   # Prefix for editor-created branches
  default_branch: "main"   # The trunk branch to diff against / merge into
  max_recent_branches: 20  # How many branches to show in the branch bar

# ── Editor ────────────────────────────────────────────────────────────────────
editor:
  autosave_interval: 30    # Autosave every N seconds (0 = disabled)
  tab_size: 2              # Tab size in the raw editor pane
  word_wrap: true          # Wrap long lines in the editor

# ── Pandoc ────────────────────────────────────────────────────────────────────
pandoc:
  extra_args: []           # Extra pandoc CLI arguments for every render
  extensions:              # Markdown extensions (pandoc +extension syntax)
    - gfm_auto_identifiers
    - pipe_tables
    - task_lists
    - strikeout
    - superscript
    - subscript
    - definition_lists
    - fenced_code_blocks
    - fenced_code_attributes
    - backtick_code_blocks
    - raw_html
    - emoji
  highlight_style: "kate"  # Syntax highlight theme (pygments, kate, etc.)

# ── Diff ──────────────────────────────────────────────────────────────────────
diff:
  rendered_diff_mode: "both"              # "block", "word", or "both"
  block_highlight_color: "rgba(255, 200, 0, 0.15)"
  word_highlight_color: "rgba(255, 140, 0, 0.45)"
  added_color: "rgba(0, 200, 80, 0.25)"
  removed_color: "rgba(220, 50, 50, 0.25)"
```

## CLI Overrides

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

Or run directly without pixi:

```bash
python -m backend.main --repo /path/to/repo --docs-dir docs/ --port 8080
```

## Full CLI Options

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

## Config Resolution Order

Configuration values are resolved in this priority (highest first):

1. **CLI arguments** — always win
2. **markdown-docs.yaml** — file-based defaults
3. **Built-in defaults** — hard-coded fallbacks

The config file is searched in this order:

1. Path given via `--config` CLI argument
2. `MARKDOWN_DOCS_CONFIG` environment variable
3. `markdown-docs.yaml` in the current working directory

## Relative Paths

Repository paths in the config file are resolved relative to the directory containing the config file itself, not the working directory. This means the config is portable — moving it alongside the project preserves all paths.

## Diff Modes

The `diff.rendered_diff_mode` setting controls how visual diffs are rendered:

| Mode | Behaviour |
|------|-----------|
| `block` | Highlight entire changed blocks with a pale background. No word-level detail. |
| `word` | Only show word-level highlights within changed blocks. |
| `both` | **(Recommended)** Pale block background + darker word-level highlights. |

## Pandoc Extensions

The `pandoc.extensions` list mirrors GitLab-Flavored Markdown. You can add or remove extensions to match your team's markdown dialect. See the [pandoc manual](https://pandoc.org/MANUAL.html#extensions) for the full list.
