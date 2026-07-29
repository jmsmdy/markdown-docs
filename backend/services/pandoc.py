"""
Pandoc rendering service.

Converts markdown → HTML using a custom pandoc template + Lua filter.
The Lua filter rewrites code blocks into web component elements:
  ```python  →  <md-code-block lang="python">
  ```mermaid →  <md-mermaid>

Two render modes:
  - fragment (default): returns only the body content, suitable for
    injecting into the editor preview pane via innerHTML.
  - full_doc: returns a complete <!DOCTYPE html> page using the template,
    suitable for standalone viewing.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from backend.models.schema import AppConfig, PandocConfig


def _pandoc_input_format(cfg: PandocConfig) -> str:
    """Build the pandoc --from argument: markdown+ext1+ext2+..."""
    base = "markdown"
    if cfg.extensions:
        return base + "+" + "+".join(cfg.extensions)
    return base


def _find_template() -> Path | None:
    candidates = [
        Path(__file__).parent.parent.parent / "templates" / "document.html",
        Path.cwd() / "templates" / "document.html",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_lua_filter() -> Path | None:
    candidates = [
        Path(__file__).parent.parent.parent / "templates" / "filters" / "codeblock.lua",
        Path.cwd() / "templates" / "filters" / "codeblock.lua",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _build_cmd(config: AppConfig, full_doc: bool = False) -> list[str]:
    """Build the pandoc command list."""
    if not shutil.which("pandoc"):
        raise RuntimeError("pandoc not found. Install it with: pixi install")

    pandoc_cfg = config.pandoc
    input_format = _pandoc_input_format(pandoc_cfg)
    lua_filter = _find_lua_filter()

    cmd: list[str] = [
        "pandoc",
        "--from", input_format,
        "--to", "html5",
        "--highlight-style", pandoc_cfg.highlight_style,
    ]

    # Apply Lua filter for web component conversion
    if lua_filter:
        cmd += ["--lua-filter", str(lua_filter)]

    if full_doc:
        template_path = _find_template()
        if template_path:
            cmd += ["--template", str(template_path), "--standalone"]
        else:
            cmd += ["--standalone"]
    # Fragment mode: no --standalone, no --template → bare HTML body content

    cmd += pandoc_cfg.extra_args
    return cmd


def render_markdown_sync(
    content: str,
    config: AppConfig,
    doc_path: str = "document.md",
    full_doc: bool = False,
) -> str:
    """
    Synchronously render markdown to HTML via pandoc.

    Args:
        content:   Raw markdown string.
        config:    App config.
        doc_path:  Used for relative link resolution (passed to pandoc).
        full_doc:  If True, return a complete HTML page with <html>/<head>.
                   If False (default), return only the body fragment — suitable
                   for injection into the editor preview via innerHTML.

    Raises:
        RuntimeError: if pandoc is not found or exits non-zero.
    """
    cmd = _build_cmd(config, full_doc=full_doc)

    try:
        result = subprocess.run(
            cmd,
            input=content,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("pandoc timed out after 30 seconds")

    if result.returncode != 0:
        raise RuntimeError(f"pandoc error: {result.stderr.strip()}")

    return result.stdout


async def render_markdown(
    content: str,
    config: AppConfig,
    doc_path: str = "document.md",
    full_doc: bool = False,
) -> str:
    """Async wrapper around render_markdown_sync."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        render_markdown_sync,
        content,
        config,
        doc_path,
        full_doc,
    )


def render_to_ast_json(content: str, config: AppConfig) -> str:
    """
    Render markdown to pandoc's native JSON AST.
    Used by the diff service for AST-level comparison.
    """
    if not shutil.which("pandoc"):
        raise RuntimeError("pandoc not found")

    input_format = _pandoc_input_format(config.pandoc)
    cmd = ["pandoc", "--from", input_format, "--to", "json"]

    result = subprocess.run(
        cmd,
        input=content,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"pandoc AST error: {result.stderr.strip()}")

    return result.stdout
