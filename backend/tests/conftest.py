"""
Shared pytest fixtures for markdown-docs tests.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pygit2
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.services.config import load_config


@pytest.fixture(scope="session")
def test_repo_path(tmp_path_factory) -> Path:
    """Create a minimal git repo for use in tests."""
    repo_dir = tmp_path_factory.mktemp("test_repo")
    repo = pygit2.init_repository(str(repo_dir))

    # Initial commit with a sample doc
    (repo_dir / "README.md").write_text("# Test Repo\n\nHello world.\n")
    index = repo.index
    index.read()
    index.add("README.md")
    index.write()
    tree_id = index.write_tree()
    sig = pygit2.Signature("Test", "test@test.com")
    repo.create_commit("refs/heads/main", sig, sig, "Initial commit", tree_id, [])

    return repo_dir


@pytest.fixture(scope="session")
def test_config(test_repo_path) -> object:
    return load_config(
        repo_override=str(test_repo_path),
        docs_dir_override=".",
        branch_prefix_override="test-",
    )


@pytest.fixture
async def client(test_config) -> AsyncClient:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
