"""
Diff service — produces source (text) diffs and visual rendered HTML diffs.

Rendered diff strategy:
  1. Render both old and new markdown to HTML via pandoc.
  2. Split each HTML into "blocks" (paragraphs, headings, list items, etc.)
     using a lightweight HTML parser — no DOM dependency.
  3. Diff the block sequences with difflib (LCS-based, robust to partial
     markdown syntax errors).
  4. For changed blocks, run a word-level diff using diff-match-patch and
     annotate with <mark> spans.
  5. Return structured RenderedDiffBlock list that the <md-diff-view>
     component consumes.

This is intentionally NOT fragile: a broken markdown syntax in one block
affects only that block's rendering, never the diff logic.
"""
from __future__ import annotations

import difflib
import hashlib
import html
import re
from html.parser import HTMLParser

from diff_match_patch import diff_match_patch

from backend.models.schema import (
    AppConfig,
    DiffHunk,
    DiffMode,
    RenderedDiff,
    RenderedDiffBlock,
    SourceDiff,
)
from backend.services import pandoc as pandoc_svc
from backend.services.mermaid_diff import mermaid_structural_diff


# ── Source (text) diff ────────────────────────────────────────────────────────

def source_diff(
    old_content: str,
    new_content: str,
    path: str,
    base_branch: str,
    compare_branch: str,
) -> SourceDiff:
    """Produce a unified-diff representation of two markdown strings."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    hunks: list[DiffHunk] = []
    diff_text = ""

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for group in matcher.get_grouped_opcodes(n=3):
        i1 = group[0][1]
        i2 = group[-1][2]
        j1 = group[0][3]
        j2 = group[-1][4]

        hunk_lines = []
        for tag, i1_, i2_, j1_, j2_ in group:
            if tag == "equal":
                hunk_lines.extend(" " + line for line in old_lines[i1_:i2_])
            elif tag in ("replace", "delete"):
                hunk_lines.extend("-" + line for line in old_lines[i1_:i2_])
                if tag == "replace":
                    hunk_lines.extend("+" + line for line in new_lines[j1_:j2_])
            elif tag == "insert":
                hunk_lines.extend("+" + line for line in new_lines[j1_:j2_])

        content = "".join(hunk_lines)
        hunks.append(DiffHunk(
            old_start=i1 + 1,
            old_lines=i2 - i1,
            new_start=j1 + 1,
            new_lines=j2 - j1,
            content=content,
        ))

    return SourceDiff(
        path=path,
        base_branch=base_branch,
        compare_branch=compare_branch,
        hunks=hunks,
        old_content=old_content,
        new_content=new_content,
    )


# ── HTML block splitter ───────────────────────────────────────────────────────

# Tags that constitute "top-level blocks" for diffing purposes.
_BLOCK_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre",
    "table", "thead", "tbody", "tr",
    "hr", "details", "summary",
    "md-code-block", "md-mermaid",   # our custom elements
})


class _BlockSplitter(HTMLParser):
    """
    Splits an HTML fragment into a flat list of top-level block strings.
    Nested blocks (e.g. <li> inside <ul>) are kept together as one unit
    at the outermost block tag level.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._depth = 0
        self._current: list[str] = []
        self._blocks: list[str] = []
        self._stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_str = ""
        for name, value in attrs:
            if value is None:
                attr_str += f" {name}"
            else:
                attr_str += f' {name}="{html.escape(value, quote=True)}"'
        token = f"<{tag}{attr_str}>"
        if tag in _BLOCK_TAGS and self._depth == 0:
            self._depth = 1
            self._stack = [tag]
            self._current = [token]
        elif self._depth > 0:
            self._depth += 1
            self._stack.append(tag)
            self._current.append(token)

    def handle_endtag(self, tag: str) -> None:
        token = f"</{tag}>"
        if self._depth > 0:
            self._current.append(token)
            if self._stack:
                self._stack.pop()
            self._depth -= 1
            if self._depth == 0:
                block = "".join(self._current).strip()
                if block:
                    self._blocks.append(block)
                self._current = []

    def handle_data(self, data: str) -> None:
        if self._depth > 0:
            self._current.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._depth > 0:
            self._current.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._depth > 0:
            self._current.append(f"&#{name};")

    @property
    def blocks(self) -> list[str]:
        return self._blocks


def split_html_blocks(html_fragment: str) -> list[str]:
    """Split an HTML fragment into a list of top-level block strings."""
    parser = _BlockSplitter()
    parser.feed(html_fragment)
    return [b for b in parser.blocks if b.strip()]


# ── Word-level intra-block diff ───────────────────────────────────────────────

def _strip_tags(text: str) -> str:
    """Remove HTML tags, keeping inner text."""
    return re.sub(r"<[^>]+>", "", text)


def _text_of(html_str: str) -> str:
    """Plain text content of an HTML snippet (for hashing / comparison)."""
    return _strip_tags(html_str).strip()


# ── Prose word-level diff ─────────────────────────────────────────────────────

def _prose_word_diff(old_html: str, new_html: str, diff_cfg) -> str:
    """
    Word-level diff for prose blocks (paragraphs, headings, blockquotes).
    Splits on word boundaries and diffs the word sequence — avoids the
    single-character noise of raw character diffing.
    """
    # Split into words + surrounding whitespace/punctuation as separate tokens
    WORD_RE = re.compile(r'\w+|\W+')
    old_words = WORD_RE.findall(_text_of(old_html))
    new_words = WORD_RE.findall(_text_of(new_html))

    sm = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
    parts: list[str] = []

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = html.escape("".join(old_words[i1:i2]))
        new_chunk = html.escape("".join(new_words[j1:j2]))

        if op == "equal":
            parts.append(new_chunk)
        elif op == "delete":
            parts.append(
                f'<mark class="md-diff-removed" style="background:{diff_cfg.removed_color};'
                f'text-decoration:line-through">{old_chunk}</mark>'
            )
        elif op == "insert":
            parts.append(
                f'<mark class="md-diff-added" style="background:{diff_cfg.added_color}">'
                f'{new_chunk}</mark>'
            )
        elif op == "replace":
            parts.append(
                f'<mark class="md-diff-removed" style="background:{diff_cfg.removed_color};'
                f'text-decoration:line-through">{old_chunk}</mark>'
                f'<mark class="md-diff-added" style="background:{diff_cfg.added_color}">'
                f'{new_chunk}</mark>'
            )

    return "".join(parts)


# ── Structural HTML extraction ────────────────────────────────────────────────

class _ChildExtractor(HTMLParser):
    """
    Extract immediate children of a single HTML element.
    e.g. given "<ul><li>A</li><li>B</li></ul>" returns ["<li>A</li>", "<li>B</li>"]
    along with the outer tag and its attributes string.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.outer_tag: str = ""
        self.outer_attrs: str = ""
        self.children: list[str] = []
        self._depth = 0
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_str = "".join(
            f' {n}' if v is None else f' {n}="{html.escape(v, quote=True)}"'
            for n, v in attrs
        )
        token = f"<{tag}{attr_str}>"
        if self._depth == 0:
            self.outer_tag = tag
            self.outer_attrs = attr_str
        elif self._depth == 1:
            self._current = [token]
        else:
            self._current.append(token)
        self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        token = f"</{tag}>"
        self._depth -= 1
        if self._depth == 1:
            self._current.append(token)
            self.children.append("".join(self._current))
            self._current = []
        elif self._depth > 1:
            self._current.append(token)

    def handle_data(self, data: str) -> None:
        if self._depth == 1:
            # Text directly inside the outer element (not in a child tag)
            stripped = data.strip()
            if stripped:
                self.children.append(html.escape(stripped))
        elif self._depth > 1:
            self._current.append(data)

    def handle_entityref(self, name: str) -> None:
        t = f"&{name};"
        if self._depth > 1:
            self._current.append(t)

    def handle_charref(self, name: str) -> None:
        t = f"&#{name};"
        if self._depth > 1:
            self._current.append(t)


def _extract_children(html_str: str) -> tuple[str, str, list[str]]:
    """
    Parse an HTML element and return (outer_tag, outer_attrs, [child_html, ...]).
    Falls back to (None, None, []) if parsing fails.
    """
    p = _ChildExtractor()
    try:
        p.feed(html_str.strip())
    except Exception:
        return "", "", []
    return p.outer_tag, p.outer_attrs, p.children


# Tags whose children we diff recursively
_DIFF_CHILDREN_OF = frozenset({
    "ul", "ol", "dl",           # list items
    "table", "tbody", "thead",  # table rows
    "tr",                       # table cells
    "blockquote",               # blockquote paragraphs
})

# Leaf tags — diff their text content word-by-word
_PROSE_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "td", "th", "dt", "dd",
})


def _structural_diff(old_html: str, new_html: str, diff_cfg, depth: int = 0) -> str:
    """
    Recursively diff two HTML snippets, preserving structure.

    Strategy:
      - If both are the same: return new_html unchanged.
      - If both are a container tag (ul, table, etc.): diff their children
        using LCS, annotating added/removed/changed children, then reassemble.
      - If both are a leaf/prose tag: apply word-level diff on text content,
        wrapped in the original tag.
      - Otherwise: fall back to prose word diff on plain text.
    """
    if depth > 8:
        # Safety: avoid infinite recursion on pathological input
        return new_html

    old_html = old_html.strip()
    new_html = new_html.strip()

    if old_html == new_html:
        return new_html

    old_tag, old_attrs, old_children = _extract_children(old_html)
    new_tag, new_attrs, new_children = _extract_children(new_html)

    # If tags don't match or extraction failed, fall back to prose word diff
    if not old_tag or not new_tag or old_tag != new_tag:
        return _prose_word_diff(old_html, new_html, diff_cfg)

    tag = new_tag

    # Leaf tags: word diff the text content, re-wrap in the tag
    if tag in _PROSE_TAGS:
        diffed_text = _prose_word_diff(old_html, new_html, diff_cfg)
        return f"<{tag}{new_attrs}>{diffed_text}</{tag}>"

    # Container tags: LCS-diff the children
    if tag in _DIFF_CHILDREN_OF and (old_children or new_children):
        diffed_children = _diff_children(old_children, new_children, diff_cfg, depth)
        return f"<{tag}{new_attrs}>\n{chr(10).join(diffed_children)}\n</{tag}>"

    # Code blocks: line-level diff rendered as an annotated <pre>
    if tag in ("pre", "code", "md-code-block"):
        return _code_block_diff(old_html, new_html, new_tag, new_attrs, diff_cfg)

    # md-mermaid: just show new version (can't meaningfully diff diagrams)
    if tag == "md-mermaid":
        return new_html

    # Everything else: highlight the whole block as changed
    if old_html != new_html:
        return (
            f'<div class="md-diff-changed-block" '
            f'style="outline:2px solid {diff_cfg.word_highlight_color};border-radius:3px;">'
            f'{new_html}</div>'
        )
    return new_html


def _code_block_diff(
    old_html: str,
    new_html: str,
    tag: str,
    attrs: str,
    diff_cfg,
) -> str:
    """
    Line-level diff for code blocks (pre, code, md-code-block).

    Extracts the raw text from each block, splits into lines, LCS-diffs them,
    and renders as a <pre> block with per-line background highlights.
    Lines that changed also get word-level marks within the line.
    """
    old_text = html.unescape(_strip_tags(old_html))
    new_text = html.unescape(_strip_tags(new_html))

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    rendered_lines: list[str] = []

    # Extract lang attribute for the badge
    lang_match = re.search(r'lang=["\']([^"\']+)["\']', attrs)
    lang = lang_match.group(1) if lang_match else ""

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for line in new_lines[j1:j2]:
                rendered_lines.append(
                    f'<span style="display:block">{html.escape(line)}</span>'
                )
        elif op == "insert":
            for line in new_lines[j1:j2]:
                rendered_lines.append(
                    f'<span style="display:block;background:{diff_cfg.added_color}">'
                    f'<span style="opacity:0.6;user-select:none;margin-right:0.5em">+</span>'
                    f'{html.escape(line)}</span>'
                )
        elif op == "delete":
            for line in old_lines[i1:i2]:
                rendered_lines.append(
                    f'<span style="display:block;background:{diff_cfg.removed_color};'
                    f'text-decoration:line-through;opacity:0.7">'
                    f'<span style="opacity:0.6;user-select:none;margin-right:0.5em">−</span>'
                    f'{html.escape(line)}</span>'
                )
        elif op == "replace":
            # For each matched pair: show old line (−) then new line (+)
            # with token-level marks for what changed within the line.
            old_chunk = old_lines[i1:i2]
            new_chunk = new_lines[j1:j2]
            pairs = min(len(old_chunk), len(new_chunk))

            for idx in range(pairs):
                old_marked, new_marked = _token_diff(
                    old_chunk[idx], new_chunk[idx], diff_cfg
                )
                rendered_lines.append(
                    f'<span style="display:block;background:{diff_cfg.removed_color};opacity:0.85">'
                    f'<span style="opacity:0.5;user-select:none;margin-right:0.5em">−</span>'
                    f'{old_marked}</span>'
                )
                rendered_lines.append(
                    f'<span style="display:block;background:{diff_cfg.added_color}">'
                    f'<span style="opacity:0.5;user-select:none;margin-right:0.5em">+</span>'
                    f'{new_marked}</span>'
                )

            # Remaining unmatched lines (pure deletes / inserts)
            for line in old_chunk[pairs:]:
                rendered_lines.append(
                    f'<span style="display:block;background:{diff_cfg.removed_color};opacity:0.85">'
                    f'<span style="opacity:0.5;user-select:none;margin-right:0.5em">−</span>'
                    f'{html.escape(line)}</span>'
                )
            for line in new_chunk[pairs:]:
                rendered_lines.append(
                    f'<span style="display:block;background:{diff_cfg.added_color}">'
                    f'<span style="opacity:0.5;user-select:none;margin-right:0.5em">+</span>'
                    f'{html.escape(line)}</span>'
                )

    lang_badge = (
        f'<span style="display:block;font-size:0.7em;opacity:0.6;'
        f'font-family:monospace;padding:0.2em 0.5em;'
        f'border-bottom:1px solid rgba(0,0,0,0.1)">{html.escape(lang)}</span>'
        if lang else ""
    )

    body = "".join(rendered_lines)
    return (
        f'<div style="font-family:monospace;font-size:0.85em;line-height:1.5;'
        f'border:1px solid #d0d7de;border-radius:6px;overflow:hidden;margin:0.25em 0">'
        f'{lang_badge}'
        f'<pre style="margin:0;padding:0.5em;overflow-x:auto;background:transparent">'
        f'<code style="white-space:pre;line-height:1.5;font-family:inherit">{body}</code></pre>'
        f'</div>'
    )


def _token_diff(old_line: str, new_line: str, diff_cfg) -> tuple[str, str]:
    """
    Diff two lines at the token level rather than character level.

    Tokenises each line into meaningful chunks (identifiers, numbers, strings,
    operators, whitespace runs) then diffs the token sequence using
    diff-match-patch's line-mode trick. This avoids spurious single-character
    matches between unrelated tokens.

    Returns (old_annotated_html, new_annotated_html).
    """
    # Tokenise: identifiers/numbers, quoted strings, whitespace, any other char
    TOKEN_RE = re.compile(
        r'[A-Za-z_]\w*'        # identifier
        r'|\d[\d.]*'           # number
        r'|"(?:[^"\\]|\\.)*"'  # double-quoted string
        r"|'(?:[^'\\]|\\.)*'"  # single-quoted string
        r'|[ \t]+'             # whitespace run
        r'|.'                  # any single char (operator, punct, etc.)
    )

    old_tokens = TOKEN_RE.findall(old_line)
    new_tokens = TOKEN_RE.findall(new_line)

    # Use SequenceMatcher on token lists — simpler and more predictable than
    # the dmp line-mode hack, and gives clean token-boundary results.
    sm = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)

    old_parts: list[str] = []
    new_parts: list[str] = []

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = html.escape("".join(old_tokens[i1:i2]))
        new_chunk = html.escape("".join(new_tokens[j1:j2]))

        if op == "equal":
            old_parts.append(old_chunk)
            new_parts.append(new_chunk)
        elif op == "delete":
            old_parts.append(
                f'<mark style="background:{diff_cfg.removed_color};'
                f'text-decoration:line-through;border-radius:2px">{old_chunk}</mark>'
            )
        elif op == "insert":
            new_parts.append(
                f'<mark style="background:{diff_cfg.word_highlight_color};'
                f'border-radius:2px">{new_chunk}</mark>'
            )
        elif op == "replace":
            old_parts.append(
                f'<mark style="background:{diff_cfg.removed_color};'
                f'text-decoration:line-through;border-radius:2px">{old_chunk}</mark>'
            )
            new_parts.append(
                f'<mark style="background:{diff_cfg.word_highlight_color};'
                f'border-radius:2px">{new_chunk}</mark>'
            )

    return "".join(old_parts), "".join(new_parts)


    """
    Inject a style attribute and class onto the outermost tag of child_html.
    e.g. "<li>foo</li>" → "<li class="md-diff-added" style="background:...">foo</li>"
    Falls back to wrapping in a <div> if the tag can't be parsed.
    """
    child_html = child_html.strip()
    # Match the opening tag
    m = re.match(r'^(<(\w[\w-]*)([^>]*)>)', child_html)
    if not m:
        return f'<div class="{extra_class}" style="{style}">{child_html}</div>'

    full_open, tag, existing_attrs = m.group(1), m.group(2), m.group(3)

    # Build new opening tag with added class and style
    new_open = f'<{tag} class="{extra_class}" style="{style}"{existing_attrs}>'
    return new_open + child_html[len(full_open):]


def _inject_style(child_html: str, style: str, extra_class: str) -> str:
    """
    Inject a style attribute and class onto the outermost tag of child_html.
    e.g. "<li>foo</li>" → "<li class="md-diff-added" style="...">foo</li>"
    Falls back to a <div> wrapper if the tag can't be parsed.
    """
    child_html = child_html.strip()
    m = re.match(r'^(<(\w[\w-]*)([^>]*)>)', child_html)
    if not m:
        return f'<div class="{extra_class}" style="{style}">{child_html}</div>'
    full_open, tag, existing_attrs = m.group(1), m.group(2), m.group(3)
    new_open = f'<{tag} class="{extra_class}" style="{style}"{existing_attrs}>'
    return new_open + child_html[len(full_open):]


def _diff_children(
    old_children: list[str],
    new_children: list[str],
    diff_cfg,
    depth: int,
) -> list[str]:
    """
    LCS-diff two lists of child HTML snippets.
    Uses text content as the comparison key (robust to attribute changes).
    Injects diff styling directly onto child elements (not wrapper spans)
    so the result is always valid HTML regardless of parent context.
    """
    old_keys = [_text_of(c) for c in old_children]
    new_keys = [_text_of(c) for c in new_children]

    sm = difflib.SequenceMatcher(None, old_keys, new_keys, autojunk=False)
    result: list[str] = []

    added_style   = f"background:{diff_cfg.added_color}"
    removed_style = f"background:{diff_cfg.removed_color};text-decoration:line-through;opacity:0.8"
    changed_style = f"background:{diff_cfg.block_highlight_color}"

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            result.extend(new_children[j1:j2])

        elif op == "insert":
            for child in new_children[j1:j2]:
                result.append(_inject_style(child, added_style, "md-diff-added"))

        elif op == "delete":
            for child in old_children[i1:i2]:
                result.append(_inject_style(child, removed_style, "md-diff-removed"))

        elif op == "replace":
            old_chunk = old_children[i1:i2]
            new_chunk = new_children[j1:j2]
            pairs = max(len(old_chunk), len(new_chunk))
            for idx in range(pairs):
                if idx >= len(old_chunk):
                    result.append(_inject_style(new_chunk[idx], added_style, "md-diff-added"))
                elif idx >= len(new_chunk):
                    result.append(_inject_style(old_chunk[idx], removed_style, "md-diff-removed"))
                else:
                    # Recurse into the changed child pair
                    diffed = _structural_diff(
                        old_chunk[idx], new_chunk[idx], diff_cfg, depth + 1
                    )
                    result.append(_inject_style(diffed, changed_style, "md-diff-changed"))

    return result


def word_diff_html(
    old_html: str,
    new_html: str,
    config: AppConfig,
) -> str:
    """
    Public entry point for intra-block diffing.

    Dispatches to structural diff (tables, lists, etc.) or prose word diff
    depending on the block type. Always returns valid HTML.
    """
    return _structural_diff(old_html, new_html, config.diff)


# ── Rendered diff ─────────────────────────────────────────────────────────────

def _is_mermaid_block(block_html: str) -> bool:
    """Check if an HTML block is a mermaid diagram element."""
    stripped = block_html.strip()
    return stripped.startswith("<md-mermaid") and stripped.endswith("</md-mermaid>")


def _extract_mermaid_source(block_html: str) -> str:
    """Extract the raw mermaid source text from an <md-mermaid> element."""
    stripped = block_html.strip()
    # Remove opening tag (may have attributes)
    start = stripped.index('>') + 1
    # Remove closing tag
    end = stripped.rindex('</md-mermaid>')
    return html.unescape(stripped[start:end]).strip()


def rendered_diff_sync(
    old_content: str,
    new_content: str,
    path: str,
    base_branch: str,
    compare_branch: str,
    config: AppConfig,
) -> RenderedDiff:
    """
    Produce a block-level rendered diff between two markdown strings.

    Steps:
      1. Render both to HTML via pandoc.
      2. Split each HTML into blocks.
      3. Diff the block sequences.
      4. For "changed" blocks, apply word-level diff.
    """
    mode = config.diff.rendered_diff_mode
    diff_cfg = config.diff

    # Render both versions. If pandoc fails on one, we still diff the other.
    try:
        old_html = pandoc_svc.render_markdown_sync(old_content, config, path)
    except RuntimeError:
        old_html = f"<p>{html.escape(old_content)}</p>"

    try:
        new_html = pandoc_svc.render_markdown_sync(new_content, config, path)
    except RuntimeError:
        new_html = f"<p>{html.escape(new_content)}</p>"

    old_blocks = split_html_blocks(old_html)
    new_blocks = split_html_blocks(new_html)

    # Use hashes as the sequence for difflib so it compares blocks semantically
    def _hash(block: str) -> str:
        return hashlib.md5(block.encode()).hexdigest()

    old_hashes = [_hash(b) for b in old_blocks]
    new_hashes = [_hash(b) for b in new_blocks]

    sm = difflib.SequenceMatcher(None, old_hashes, new_hashes, autojunk=False)
    result_blocks: list[RenderedDiffBlock] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for idx in range(i2 - i1):
                result_blocks.append(RenderedDiffBlock(
                    kind="unchanged",
                    old_html=old_blocks[i1 + idx],
                    new_html=new_blocks[j1 + idx],
                ))

        elif tag == "delete":
            for idx in range(i2 - i1):
                block = old_blocks[i1 + idx]
                if _is_mermaid_block(block):
                    result_blocks.append(RenderedDiffBlock(
                        kind="mermaid",
                        old_html=block,
                    ))
                else:
                    result_blocks.append(RenderedDiffBlock(
                        kind="removed",
                        old_html=_wrap_block(block, "removed", diff_cfg),
                    ))

        elif tag == "insert":
            for idx in range(j2 - j1):
                block = new_blocks[j1 + idx]
                if _is_mermaid_block(block):
                    result_blocks.append(RenderedDiffBlock(
                        kind="mermaid",
                        new_html=block,
                    ))
                else:
                    result_blocks.append(RenderedDiffBlock(
                        kind="added",
                        new_html=_wrap_block(block, "added", diff_cfg),
                    ))

        elif tag == "replace":
            # Pair up old/new blocks; extras treated as pure add/remove
            old_chunk = old_blocks[i1:i2]
            new_chunk = new_blocks[j1:j2]
            pairs = max(len(old_chunk), len(new_chunk))
            for idx in range(pairs):
                old_b = old_chunk[idx] if idx < len(old_chunk) else None
                new_b = new_chunk[idx] if idx < len(new_chunk) else None

                if old_b is None:
                    result_blocks.append(RenderedDiffBlock(
                        kind="added",
                        new_html=_wrap_block(new_b, "added", diff_cfg),
                    ))
                elif new_b is None:
                    result_blocks.append(RenderedDiffBlock(
                        kind="removed",
                        old_html=_wrap_block(old_b, "removed", diff_cfg),
                    ))
                elif _is_mermaid_block(old_b) or _is_mermaid_block(new_b):
                    # Mermaid diagrams: attempt structural diff to produce
                    # an annotated diagram with highlighted changes
                    diff_html = None
                    if _is_mermaid_block(old_b) and _is_mermaid_block(new_b):
                        old_src = _extract_mermaid_source(old_b)
                        new_src = _extract_mermaid_source(new_b)
                        annotated = mermaid_structural_diff(old_src, new_src)
                        if annotated:
                            diff_html = (
                                f"<md-mermaid>{html.escape(annotated)}</md-mermaid>"
                            )
                    result_blocks.append(RenderedDiffBlock(
                        kind="mermaid",
                        old_html=old_b,
                        new_html=new_b,
                        diff_html=diff_html,
                    ))
                else:
                    # Changed block — apply word diff
                    diff_html = (
                        word_diff_html(old_b, new_b, config)
                        if mode in (DiffMode.word, DiffMode.both)
                        else None
                    )
                    result_blocks.append(RenderedDiffBlock(
                        kind="changed",
                        old_html=_wrap_block(old_b, "changed-old", diff_cfg),
                        new_html=_wrap_block(new_b, "changed-new", diff_cfg),
                        diff_html=diff_html,
                    ))

    return RenderedDiff(
        path=path,
        base_branch=base_branch,
        compare_branch=compare_branch,
        blocks=result_blocks,
        mode=mode,
    )


def _wrap_block(block_html: str, kind: str, diff_cfg) -> str:
    """Wrap a block in a <div> with diff styling data attributes."""
    return (
        f'<div class="md-diff-block md-diff-{kind}" '
        f'data-diff="{kind}">'
        f'{block_html}'
        f'</div>'
    )
