"""
Git service — wraps pygit2 for all repository operations.

Design principles:
  - All mutations go through this module; callers never touch pygit2 directly.
  - Operations that modify the working tree or index are always explicit.
  - Branch names managed by this tool always carry the configured prefix.
  - The working tree is left clean after every operation (no dangling index state).
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pygit2

from backend.models.schema import AppConfig, BranchInfo, CreateBranchResponse


# ── Repo access ───────────────────────────────────────────────────────────────

def open_repo(config: AppConfig) -> pygit2.Repository:
    """Open (and validate) the configured git repository."""
    repo_path = config.effective_repo_path
    try:
        return pygit2.Repository(repo_path)
    except pygit2.GitError as exc:
        raise RuntimeError(
            f"Cannot open git repository at '{repo_path}': {exc}"
        ) from exc


def get_docs_root(repo: pygit2.Repository, config: AppConfig) -> Path:
    """Return the absolute path to the docs sub-directory inside the repo."""
    return Path(repo.workdir) / config.effective_docs_dir


# ── Branch helpers ────────────────────────────────────────────────────────────

def is_doc_branch(name: str, prefix: str) -> bool:
    """Return True if *name* was created by this tool (has the prefix)."""
    return name.startswith(prefix)


def full_branch_name(short_name: str, prefix: str) -> str:
    """
    Given a user-supplied short name, return the full prefixed branch name.
    Idempotent — won't double-prefix.
    """
    if short_name.startswith(prefix):
        return short_name
    # Sanitise: replace spaces/illegal chars with hyphens
    safe = re.sub(r"[^a-zA-Z0-9._/-]", "-", short_name).strip("-")
    return f"{prefix}{safe}"


def list_branches(repo: pygit2.Repository, config: AppConfig) -> list[BranchInfo]:
    """Return all local branches, annotated with doc-branch metadata."""
    prefix = config.effective_branch_prefix
    default = config.repository.default_branch
    results: list[BranchInfo] = []

    try:
        head_name = repo.head.shorthand
    except pygit2.GitError:
        head_name = ""

    # Compute ahead/behind relative to default branch
    try:
        default_ref = repo.lookup_branch(default)
        default_commit = default_ref.peel(pygit2.Commit) if default_ref else None
    except pygit2.GitError:
        default_commit = None

    for branch_name in repo.branches.local:
        branch_ref = repo.lookup_branch(branch_name)
        if branch_ref is None:
            continue
        try:
            commit = branch_ref.peel(pygit2.Commit)
        except pygit2.GitError:
            continue

        ahead = behind = 0
        if default_commit and commit.id != default_commit.id:
            try:
                ahead, behind = repo.ahead_behind(commit.id, default_commit.id)
            except pygit2.GitError:
                pass

        ts = commit.commit_time
        commit_date = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        results.append(BranchInfo(
            name=branch_name,
            is_doc_branch=is_doc_branch(branch_name, prefix),
            is_current=(branch_name == head_name),
            commit_sha=str(commit.id),
            commit_message=commit.message.strip().splitlines()[0],
            commit_date=commit_date,
            ahead=ahead,
            behind=behind,
        ))

    # Sort: current first, then doc branches, then others; all alphabetical
    results.sort(key=lambda b: (not b.is_current, not b.is_doc_branch, b.name))
    return results[: config.repository.max_recent_branches + 10]


def create_branch(
    repo: pygit2.Repository,
    short_name: str,
    config: AppConfig,
    base_branch: str | None = None,
    switch_to: bool = True,
) -> CreateBranchResponse:
    """
    Create a new doc-edit branch from *base_branch* (defaults to default_branch).
    Optionally check it out immediately.
    """
    prefix = config.effective_branch_prefix
    name = full_branch_name(short_name, prefix)
    base = base_branch or config.repository.default_branch

    try:
        base_ref = repo.lookup_branch(base)
        if base_ref is None:
            raise RuntimeError(f"Base branch '{base}' not found")
        base_commit = base_ref.peel(pygit2.Commit)
    except pygit2.GitError as exc:
        raise RuntimeError(f"Cannot resolve base branch '{base}': {exc}") from exc

    if repo.lookup_branch(name):
        raise ValueError(f"Branch '{name}' already exists")

    new_branch = repo.create_branch(name, base_commit, False)

    if switch_to:
        repo.checkout(new_branch)

    return CreateBranchResponse(
        branch=name,
        base_commit=str(base_commit.id),
    )


def switch_branch(repo: pygit2.Repository, branch_name: str) -> None:
    """Check out an existing branch. Raises if working tree is dirty."""
    branch_ref = repo.lookup_branch(branch_name)
    if branch_ref is None:
        raise RuntimeError(f"Branch '{branch_name}' not found")
    repo.checkout(branch_ref)


def current_branch(repo: pygit2.Repository) -> str:
    """Return the current branch short name, or 'HEAD' if detached."""
    try:
        return repo.head.shorthand
    except pygit2.GitError:
        return "HEAD"


# ── File operations ───────────────────────────────────────────────────────────

def read_file(
    repo: pygit2.Repository,
    rel_path: str,
    config: AppConfig,
    branch: str | None = None,
) -> tuple[str, str]:
    """
    Read a file's content from the working tree (default) or a specific branch.

    Returns:
        (content, commit_sha) — commit_sha is the HEAD of the branch.
    """
    docs_root = get_docs_root(repo, config)

    if branch:
        # Read from the git object store (no checkout needed)
        branch_ref = repo.lookup_branch(branch)
        if branch_ref is None:
            raise FileNotFoundError(f"Branch '{branch}' not found")
        commit = branch_ref.peel(pygit2.Commit)
        tree = commit.tree

        # Walk the tree path
        docs_dir = config.effective_docs_dir
        lookup_path = (
            f"{docs_dir}/{rel_path}".lstrip("./")
            if docs_dir not in (".", "")
            else rel_path
        )
        try:
            blob = repo.get(tree[lookup_path].id)
            return blob.data.decode("utf-8"), str(commit.id)
        except KeyError:
            raise FileNotFoundError(
                f"'{rel_path}' not found in branch '{branch}'"
            )

    # Working tree read
    abs_path = docs_root / rel_path
    if not abs_path.exists():
        raise FileNotFoundError(f"'{rel_path}' not found in working tree")
    return abs_path.read_text(encoding="utf-8"), str(repo.head.target)


def write_file_and_commit(
    repo: pygit2.Repository,
    rel_path: str,
    content: str,
    config: AppConfig,
    branch: str,
    commit_message: str | None = None,
) -> str:
    """
    Write *content* to *rel_path* in the docs dir and create a commit on *branch*.

    Returns the new commit SHA.
    """
    # Ensure we're on the right branch
    cur = current_branch(repo)
    if cur != branch:
        switch_branch(repo, branch)

    docs_root = get_docs_root(repo, config)
    abs_path = docs_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")

    # Stage the file
    repo_rel = str(Path(config.effective_docs_dir) / rel_path).lstrip("./")
    index = repo.index
    index.read()
    index.add(repo_rel)
    index.write()

    # Build commit
    tree_id = index.write_tree()
    sig = _make_signature()
    message = commit_message or f"docs: update {rel_path}"

    parent_commits = []
    try:
        parent_commits = [repo.head.target]
    except pygit2.GitError:
        pass  # Initial commit

    commit_id = repo.create_commit(
        f"refs/heads/{branch}",
        sig, sig,
        message,
        tree_id,
        parent_commits,
    )
    return str(commit_id)


def list_docs(
    repo: pygit2.Repository,
    config: AppConfig,
    branch: str | None = None,
) -> list[str]:
    """
    Return a list of relative markdown file paths in docs_dir.
    Reads from working tree if no branch given, otherwise from git tree.
    """
    if branch:
        branch_ref = repo.lookup_branch(branch)
        if branch_ref is None:
            return []
        commit = branch_ref.peel(pygit2.Commit)
        tree = commit.tree
        docs_dir = config.effective_docs_dir.lstrip("./")
        results = []
        _walk_tree(repo, tree, docs_dir, "", results)
        return results

    docs_root = get_docs_root(repo, config)
    if not docs_root.exists():
        return []
    return [
        str(p.relative_to(docs_root))
        for p in sorted(docs_root.rglob("*.md"))
    ]


def _walk_tree(
    repo: pygit2.Repository,
    tree: pygit2.Tree,
    base_prefix: str,
    current_path: str,
    results: list[str],
) -> None:
    for entry in tree:
        entry_path = f"{current_path}/{entry.name}" if current_path else entry.name
        full = f"{base_prefix}/{entry_path}" if base_prefix else entry_path
        obj = repo.get(entry.id)
        if isinstance(obj, pygit2.Tree):
            _walk_tree(repo, obj, base_prefix, entry_path, results)
        elif isinstance(obj, pygit2.Blob) and entry.name.endswith(".md"):
            results.append(entry_path)


# ── Squash / merge helpers ─────────────────────────────────────────────────────

def squash_branch_to_diff(
    repo: pygit2.Repository,
    source_branch: str,
    config: AppConfig,
) -> dict[str, tuple[str | None, str | None]]:
    """
    Compute the net file-level changes introduced by *source_branch* relative
    to the default branch, WITHOUT modifying the repo.

    Returns:
        dict mapping rel_path → (old_content | None, new_content | None)
        A None old_content means the file was added; None new_content means deleted.
    """
    default = config.repository.default_branch
    changes: dict[str, tuple[str | None, str | None]] = {}

    try:
        old_ref = repo.lookup_branch(default)
        new_ref = repo.lookup_branch(source_branch)
        if old_ref is None or new_ref is None:
            return {}
        old_commit = old_ref.peel(pygit2.Commit)
        new_commit = new_ref.peel(pygit2.Commit)
        diff = repo.diff(old_commit, new_commit)
    except pygit2.GitError:
        return {}

    for patch in diff:
        old_path = patch.delta.old_file.path
        new_path = patch.delta.new_file.path
        status = patch.delta.status

        old_content = _blob_content(repo, old_commit.tree, old_path)
        new_content = _blob_content(repo, new_commit.tree, new_path)

        key = new_path if new_path else old_path
        changes[key] = (old_content, new_content)

    return changes


def _blob_content(
    repo: pygit2.Repository,
    tree: pygit2.Tree,
    path: str,
) -> str | None:
    try:
        entry = tree[path]
        blob = repo.get(entry.id)
        return blob.data.decode("utf-8", errors="replace")
    except (KeyError, AttributeError):
        return None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_signature() -> pygit2.Signature:
    return pygit2.Signature(
        name="markdown-docs",
        email="markdown-docs@localhost",
        time=int(time.time()),
        offset=0,
    )
