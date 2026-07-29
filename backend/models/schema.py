"""
Pydantic models for markdown-docs.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Config models ─────────────────────────────────────────────────────────────

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    proxy_headers: bool = False


class RepositoryConfig(BaseModel):
    path: str = ".test-repo"
    docs_dir: str = "."
    branch_prefix: str = "docs-"
    default_branch: str = "main"
    max_recent_branches: int = 20


class EditorConfig(BaseModel):
    autosave_interval: int = 30
    tab_size: int = 2
    word_wrap: bool = True


class PandocConfig(BaseModel):
    extra_args: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=lambda: [
        "gfm_auto_identifiers", "pipe_tables", "task_lists", "strikeout",
        "superscript", "subscript", "definition_lists", "fenced_code_blocks",
        "fenced_code_attributes", "backtick_code_blocks", "raw_html", "emoji",
    ])
    highlight_style: str = "kate"


class DiffMode(str, Enum):
    block = "block"
    word = "word"
    both = "both"


class DiffConfig(BaseModel):
    rendered_diff_mode: DiffMode = DiffMode.both
    block_highlight_color: str = "rgba(255, 200, 0, 0.15)"
    word_highlight_color: str = "rgba(255, 140, 0, 0.45)"
    added_color: str = "rgba(0, 200, 80, 0.25)"
    removed_color: str = "rgba(220, 50, 50, 0.25)"


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    repository: RepositoryConfig = Field(default_factory=RepositoryConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    pandoc: PandocConfig = Field(default_factory=PandocConfig)
    diff: DiffConfig = Field(default_factory=DiffConfig)

    # Runtime overrides (set from CLI args, not yaml)
    _repo_path_override: str | None = None
    _docs_dir_override: str | None = None
    _branch_prefix_override: str | None = None

    @property
    def effective_repo_path(self) -> str:
        return self._repo_path_override or self.repository.path

    @property
    def effective_docs_dir(self) -> str:
        return self._docs_dir_override or self.repository.docs_dir

    @property
    def effective_branch_prefix(self) -> str:
        return self._branch_prefix_override or self.repository.branch_prefix


# ── Document models ───────────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    """Metadata for a markdown document in the repo."""
    path: str                  # relative path from docs_dir
    name: str                  # filename without extension
    title: str | None = None   # first H1 heading, if any
    size_bytes: int = 0
    last_modified: str | None = None   # ISO8601 from git log
    last_author: str | None = None


class DocumentContent(BaseModel):
    """Full document content and metadata."""
    path: str
    content: str               # raw markdown
    html: str | None = None    # rendered HTML (optional, on-demand)
    branch: str = "main"
    commit_sha: str | None = None


class RenderRequest(BaseModel):
    content: str
    path: str = "document.md"  # used for relative link resolution


class RenderResponse(BaseModel):
    html: str
    path: str


class SaveRequest(BaseModel):
    path: str
    content: str
    branch: str
    commit_message: str | None = None   # auto-generated if omitted


class SaveResponse(BaseModel):
    path: str
    branch: str
    commit_sha: str
    commit_message: str


# ── Git / Branch models ───────────────────────────────────────────────────────

class BranchInfo(BaseModel):
    name: str
    is_doc_branch: bool
    is_current: bool
    commit_sha: str
    commit_message: str | None = None
    commit_date: str | None = None
    ahead: int = 0       # commits ahead of default branch
    behind: int = 0      # commits behind default branch


class CreateBranchRequest(BaseModel):
    name: str            # without prefix — prefix is prepended automatically
    base_branch: str | None = None   # defaults to config default_branch
    switch_to: bool = True


class CreateBranchResponse(BaseModel):
    branch: str          # full branch name including prefix
    base_commit: str


class MergeRequest(BaseModel):
    source_branch: str
    target_branch: str | None = None   # defaults to default_branch
    squash: bool = True
    commit_message: str | None = None


class MergeResponse(BaseModel):
    merged: bool
    commit_sha: str | None = None
    conflicts: list[str] = Field(default_factory=list)


# ── Diff models ───────────────────────────────────────────────────────────────

class DiffRequest(BaseModel):
    path: str
    base_branch: str | None = None   # defaults to default_branch
    compare_branch: str | None = None


class DiffHunk(BaseModel):
    """A single changed region."""
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str         # unified diff text for this hunk


class SourceDiff(BaseModel):
    """Raw markdown / text diff."""
    path: str
    base_branch: str
    compare_branch: str
    hunks: list[DiffHunk]
    old_content: str
    new_content: str


class RenderedDiffBlock(BaseModel):
    """A block-level diff unit for the visual rendered diff."""
    kind: str            # "unchanged" | "added" | "removed" | "changed"
    old_html: str | None = None
    new_html: str | None = None
    # For "changed" blocks: intra-block word-level diff as HTML
    diff_html: str | None = None


class RenderedDiff(BaseModel):
    path: str
    base_branch: str
    compare_branch: str
    blocks: list[RenderedDiffBlock]
    mode: DiffMode = DiffMode.both
