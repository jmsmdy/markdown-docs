# Using Your Own Repository

markdown-docs can point at any git repository containing markdown files. You're not limited to the built-in test repo.

## Quick Setup

### Via CLI

```bash
pixi run dev -- --repo /path/to/your/repo --docs-dir docs/
```

### Via Config File

Edit `markdown-docs.yaml`:

```yaml
repository:
  path: /path/to/your/repo
  docs_dir: docs/
  branch_prefix: "docs-"
  default_branch: main
```

Then start normally:

```bash
pixi run dev
```

## Requirements

Your repository must:

1. **Be a valid git repository** — initialised with at least one commit.
2. **Have the specified default branch** — the branch named in `default_branch` (default: `main`) must exist.
3. **Contain the docs directory** — the `docs_dir` path must exist within the repo (use `"."` for the repo root).

## What markdown-docs Will Do

- **Read** markdown files from `docs_dir` on any branch
- **Write** to files under `docs_dir` only
- **Create commits** on doc branches (`docs-*`)
- **Create branches** from the default branch
- **Merge branches** back into the default branch (squash merge)

## What markdown-docs Will NOT Do

- Touch any files outside `docs_dir`
- Push to or pull from remotes
- Modify git configuration
- Access or modify `.git/hooks`
- Create tags
- Force-push or rewrite history

## Path Resolution

- **Absolute paths** are used as-is: `path: /home/user/my-repo`
- **Relative paths** resolve from the directory containing `markdown-docs.yaml`: `path: ../my-repo`

## Common Setups

### Monorepo with a docs/ directory

```yaml
repository:
  path: /path/to/monorepo
  docs_dir: docs/
```

Only files under `monorepo/docs/` are visible and editable.

### Dedicated docs repository

```yaml
repository:
  path: /path/to/docs-repo
  docs_dir: "."
```

All markdown files in the repo root are documents.

### Nested documentation structure

```yaml
repository:
  path: /path/to/project
  docs_dir: documentation/user-guide/
```

Only files under `project/documentation/user-guide/` are managed.

## Branch Prefix Considerations

The default prefix `docs-` works well for most setups. Choose a different prefix if:

- Your repo already uses `docs-` branches for other purposes
- You want to namespace by team: `team-docs/`
- You prefer a different convention: `draft/`, `edit/`

```yaml
repository:
  branch_prefix: "draft/"
```

Resulting branches: `draft/my-feature`, `draft/api-update`, etc.

## Working Alongside Other Tools

Since markdown-docs operates on standard git branches and commits:

- VS Code, Obsidian, vim users can edit the same files on the same branches
- CI/CD pipelines can build documentation from `main`
- PRs can be opened on GitHub/GitLab for the same branches
- `git log` shows all edits with author "markdown-docs" and email "markdown-docs@localhost"

## Tips

- **Back up first** — test on a copy of your repo before pointing at production docs.
- **Use SSH or credential helpers** for remote repos — markdown-docs doesn't handle authentication.
- **Commit any local changes** before starting — markdown-docs expects a clean working tree on branch switches.
- **Set `max_recent_branches`** appropriately if your repo has many branches.
