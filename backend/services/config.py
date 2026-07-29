"""
Config loading: reads markdown-docs.yaml, applies CLI overrides.

Usage:
    from backend.services.config import load_config, get_config

    # At startup (in main.py or CLI entrypoint):
    load_config(path="markdown-docs.yaml", repo_override="/my/repo")

    # Anywhere else:
    cfg = get_config()
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from backend.models.schema import AppConfig

_config: AppConfig | None = None


def load_config(
    path: str | Path | None = None,
    repo_override: str | None = None,
    docs_dir_override: str | None = None,
    branch_prefix_override: str | None = None,
) -> AppConfig:
    """
    Load configuration from a YAML file and apply any CLI overrides.

    Search order for the config file:
      1. ``path`` argument (explicit)
      2. ``MARKDOWN_DOCS_CONFIG`` environment variable
      3. ``markdown-docs.yaml`` in the current working directory
      4. Built-in defaults (no file required)
    """
    global _config

    raw: dict = {}
    resolved_path: Path | None = None

    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    env_path = os.environ.get("MARKDOWN_DOCS_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.cwd() / "markdown-docs.yaml")

    for candidate in candidates:
        if candidate.exists():
            resolved_path = candidate
            with candidate.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            break

    config = AppConfig.model_validate(raw)

    # Apply CLI / runtime overrides
    if repo_override:
        config._repo_path_override = repo_override
    if docs_dir_override:
        config._docs_dir_override = docs_dir_override
    if branch_prefix_override:
        config._branch_prefix_override = branch_prefix_override

    # Resolve relative repo path relative to config file location
    if resolved_path and not Path(config.effective_repo_path).is_absolute():
        abs_path = (resolved_path.parent / config.effective_repo_path).resolve()
        config._repo_path_override = str(abs_path)

    _config = config
    return config


def get_config() -> AppConfig:
    """Return the loaded config, loading defaults if not yet initialised."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
