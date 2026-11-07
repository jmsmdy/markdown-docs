"""
Tests for the diff service — the most critical and complex piece.
"""
from __future__ import annotations

import pytest

from backend.models.schema import AppConfig, DiffMode
from backend.services.diff import (
    rendered_diff_sync,
    source_diff,
    split_html_blocks,
    word_diff_html,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def config() -> AppConfig:
    return AppConfig()


# ── split_html_blocks ─────────────────────────────────────────────────────────

def test_split_blocks_basic():
    html = "<p>Hello world</p><p>Second paragraph</p>"
    blocks = split_html_blocks(html)
    assert len(blocks) == 2
    assert "Hello world" in blocks[0]
    assert "Second paragraph" in blocks[1]


def test_split_blocks_headings():
    html = "<h1>Title</h1><p>Body</p><h2>Section</h2>"
    blocks = split_html_blocks(html)
    assert len(blocks) == 3


def test_split_blocks_nested_list():
    html = "<ul><li>Item 1</li><li>Item 2</li></ul><p>After</p>"
    blocks = split_html_blocks(html)
    # The whole <ul> should be one block
    assert len(blocks) == 2
    assert "<ul>" in blocks[0]


def test_split_blocks_empty():
    assert split_html_blocks("") == []
    assert split_html_blocks("   ") == []


def test_split_blocks_pre():
    html = "<pre><code>def foo(): pass</code></pre><p>Text</p>"
    blocks = split_html_blocks(html)
    assert len(blocks) == 2


# ── source_diff ───────────────────────────────────────────────────────────────

def test_source_diff_no_changes():
    content = "# Hello\n\nSame content.\n"
    result = source_diff(content, content, "doc.md", "main", "branch")
    assert result.hunks == []
    assert result.old_content == content
    assert result.new_content == content


def test_source_diff_single_line_change():
    old = "# Hello\n\nOriginal paragraph.\n"
    new = "# Hello\n\nUpdated paragraph.\n"
    result = source_diff(old, new, "doc.md", "main", "branch")
    assert len(result.hunks) == 1
    assert "Original paragraph" in result.hunks[0].content
    assert "Updated paragraph" in result.hunks[0].content


def test_source_diff_addition():
    old = "# Hello\n"
    new = "# Hello\n\nNew section added.\n"
    result = source_diff(old, new, "doc.md", "main", "branch")
    assert len(result.hunks) >= 1
    combined = "".join(h.content for h in result.hunks)
    assert "New section" in combined


def test_source_diff_empty_to_content():
    result = source_diff("", "# New doc\n", "doc.md", "main", "branch")
    assert len(result.hunks) >= 1


# ── word_diff_html ────────────────────────────────────────────────────────────

def test_word_diff_insertion(config):
    old = "<p>The quick brown fox</p>"
    new = "<p>The quick brown lazy fox</p>"
    result = word_diff_html(old, new, config)
    assert "lazy" in result
    assert "md-diff-added" in result


def test_word_diff_deletion(config):
    old = "<p>The quick brown fox</p>"
    new = "<p>The brown fox</p>"
    result = word_diff_html(old, new, config)
    assert "md-diff-removed" in result
    assert "quick" in result


def test_word_diff_no_change(config):
    block = "<p>Unchanged content here</p>"
    result = word_diff_html(block, block, config)
    assert "md-diff-added" not in result
    assert "md-diff-removed" not in result


def test_word_diff_broken_markdown_safe(config):
    """Broken markdown in one block must not crash the diff."""
    old = "<p>**broken bold</p>"
    new = "<p>**fixed bold**</p>"
    # Should not raise
    result = word_diff_html(old, new, config)
    assert isinstance(result, str)


# ── rendered_diff_sync ────────────────────────────────────────────────────────

def test_rendered_diff_unchanged(config):
    content = "# Title\n\nParagraph.\n"
    result = rendered_diff_sync(content, content, "doc.md", "main", "branch", config)
    assert all(b.kind == "unchanged" for b in result.blocks)


def test_rendered_diff_has_changed_block(config):
    old = "# Title\n\nOriginal paragraph.\n"
    new = "# Title\n\nModified paragraph.\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    kinds = [b.kind for b in result.blocks]
    assert "changed" in kinds or "added" in kinds or "removed" in kinds


def test_rendered_diff_addition(config):
    old = "# Title\n"
    new = "# Title\n\nA brand new paragraph.\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    kinds = [b.kind for b in result.blocks]
    assert "added" in kinds


def test_rendered_diff_removal(config):
    old = "# Title\n\nA paragraph to remove.\n"
    new = "# Title\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    kinds = [b.kind for b in result.blocks]
    assert "removed" in kinds


def test_rendered_diff_mode_block_only(config):
    """With block-only mode, diff_html should be None on changed blocks."""
    config.diff.rendered_diff_mode = DiffMode.block
    old = "# Title\n\nOriginal text.\n"
    new = "# Title\n\nChanged text.\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    changed = [b for b in result.blocks if b.kind == "changed"]
    # In block mode, no word-level diff_html
    for b in changed:
        assert b.diff_html is None


def test_rendered_diff_mode_both(config):
    """With 'both' mode, changed blocks should have diff_html with word highlights."""
    config.diff.rendered_diff_mode = DiffMode.both
    old = "# Title\n\nThe quick brown fox jumps.\n"
    new = "# Title\n\nThe quick red fox leaps.\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    changed = [b for b in result.blocks if b.kind == "changed"]
    if changed:
        assert changed[0].diff_html is not None
        assert "mark" in changed[0].diff_html


def test_rendered_diff_empty_old(config):
    result = rendered_diff_sync("", "# New\n\nContent.\n", "doc.md", "main", "branch", config)
    kinds = [b.kind for b in result.blocks]
    assert any(k in kinds for k in ("added", "changed"))


def test_rendered_diff_empty_new(config):
    result = rendered_diff_sync("# Old\n\nContent.\n", "", "doc.md", "main", "branch", config)
    kinds = [b.kind for b in result.blocks]
    assert any(k in kinds for k in ("removed", "changed"))


# ── Mermaid diagram diff ──────────────────────────────────────────────────────

def test_mermaid_block_changed(config):
    """Changed mermaid blocks get kind='mermaid' with raw old/new html and annotated diff."""
    old = "# Title\n\n```mermaid\ngraph TD\n    A-->B\n```\n"
    new = "# Title\n\n```mermaid\ngraph TD\n    A-->B\n    A-->C\n```\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    mermaid_blocks = [b for b in result.blocks if b.kind == "mermaid"]
    assert len(mermaid_blocks) == 1
    block = mermaid_blocks[0]
    # Both old and new HTML should contain md-mermaid elements (not wrapped in diff divs)
    assert "md-mermaid" in block.old_html
    assert "md-mermaid" in block.new_html
    assert "md-diff-block" not in block.old_html
    assert "md-diff-block" not in block.new_html
    # diff_html contains the annotated diagram (structural diff)
    assert block.diff_html is not None
    assert "md-mermaid" in block.diff_html
    assert "style C" in block.diff_html  # new node C is highlighted


def test_mermaid_block_added(config):
    """A newly added mermaid block gets kind='mermaid' with only new_html."""
    old = "# Title\n\nJust text.\n"
    new = "# Title\n\nJust text.\n\n```mermaid\ngraph LR\n    X-->Y\n```\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    mermaid_blocks = [b for b in result.blocks if b.kind == "mermaid"]
    assert len(mermaid_blocks) == 1
    block = mermaid_blocks[0]
    assert block.new_html is not None
    assert "md-mermaid" in block.new_html
    assert block.old_html is None


def test_mermaid_block_removed(config):
    """A removed mermaid block gets kind='mermaid' with only old_html."""
    old = "# Title\n\n```mermaid\nsequenceDiagram\n    A->>B: Hello\n```\n"
    new = "# Title\n"
    result = rendered_diff_sync(old, new, "doc.md", "main", "branch", config)
    mermaid_blocks = [b for b in result.blocks if b.kind == "mermaid"]
    assert len(mermaid_blocks) == 1
    block = mermaid_blocks[0]
    assert block.old_html is not None
    assert "md-mermaid" in block.old_html
    assert block.new_html is None


def test_mermaid_block_unchanged(config):
    """Unchanged mermaid blocks still get kind='unchanged'."""
    content = "# Title\n\n```mermaid\ngraph TD\n    A-->B\n```\n"
    result = rendered_diff_sync(content, content, "doc.md", "main", "branch", config)
    assert all(b.kind == "unchanged" for b in result.blocks)
    mermaid_blocks = [b for b in result.blocks if b.kind == "mermaid"]
    assert len(mermaid_blocks) == 0


def test_is_mermaid_block():
    """The _is_mermaid_block helper correctly identifies mermaid elements."""
    from backend.services.diff import _is_mermaid_block

    assert _is_mermaid_block("<md-mermaid>graph TD; A-->B</md-mermaid>")
    assert _is_mermaid_block("  <md-mermaid>content</md-mermaid>  ")
    assert not _is_mermaid_block("<p>Not mermaid</p>")
    assert not _is_mermaid_block("<pre><code>md-mermaid</code></pre>")
    assert not _is_mermaid_block("")
