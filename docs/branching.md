# Branch Workflow

markdown-docs uses git branches to isolate edits until they're ready to merge. This keeps `main` clean and allows review before changes go live.

## Concepts

- **Default branch** (`main`) — the trunk. This is what readers see as the current documentation.
- **Doc branches** (`docs-*`) — editing branches created by the UI. All saves on a doc branch produce commits on that branch.
- **Branch prefix** — configurable (default: `docs-`). Any branch whose name starts with this prefix is treated as a doc branch.

## Creating a Branch

1. Click **+ New branch** in the branch bar at the top of the page.
2. Enter a short descriptive name (e.g. `update-api-docs`).
3. The prefix is prepended automatically → `docs-update-api-docs`.
4. The branch is created from the current HEAD of `main` and switched to immediately.

Branch names are sanitised: spaces and special characters are replaced with hyphens.

## Switching Branches

Use the dropdown in the branch bar to switch between branches. The document list and editor content update to reflect the selected branch's state.

The branch bar shows:

- A badge indicating whether you're on a doc branch or `main`
- Ahead/behind counts relative to `main` (e.g. `↑3 ↓0` = 3 commits ahead)

## The Editing Flow

1. Create a doc branch (or switch to an existing one).
2. Edit documents — each save creates a commit on that branch.
3. When finished, click **Review & merge** to squash-merge into `main`.

## Reviewing & Merging

When you click **Review & merge** from a doc branch:

1. A confirmation dialog shows the source and target branches.
2. On confirmation, all commits on the doc branch are **squashed** into a single diff relative to `main`.
3. Each changed file is applied as a commit on `main` with the message `docs: merge <branch> into main`.
4. You're switched back to `main`.

This means the commit history on `main` stays clean — one commit per merged branch, regardless of how many individual saves happened during editing.

## Branch Visibility

The branch bar shows up to `max_recent_branches` (default: 20) branches, sorted:

1. Current branch first
2. Doc branches next (alphabetical)
3. Other branches last

Use the ↺ refresh button to reload the branch list after external changes.

## External Branch Operations

Since branches are standard git refs, you can also:

```bash
# Create a branch from the command line
git checkout -b docs-my-feature main

# Push to a remote
git push -u origin docs-my-feature

# Merge manually
git checkout main
git merge --squash docs-my-feature
git commit -m "docs: merge my-feature"
```

The UI will see these branches on the next refresh.

## Limitations

- **No conflict resolution UI** — if `main` has diverged, the merge may fail. Resolve conflicts with git CLI and retry.
- **File deletions** — deleting files from a branch is not yet exposed in the UI (use git CLI).
- **No remote sync** — the tool operates on the local repo only. Use `git push`/`git pull` separately.
