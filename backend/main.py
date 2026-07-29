"""
markdown-docs — FastAPI application entrypoint.

Usage via pixi:
    pixi run dev

Usage directly (with overrides):
    python -m backend.main --repo /path/to/repo --docs-dir docs/ --port 8080

All CLI arguments override the markdown-docs.yaml config file.
"""
from __future__ import annotations

from pathlib import Path

import click
import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import branches, diff, documents
from backend.services.config import load_config


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="markdown-docs",
        description="Git-native markdown documentation editor with visual diffing",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Allow the dev frontend to call the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routers ───────────────────────────────────────────────────────────
    app.include_router(documents.router)
    app.include_router(branches.router)
    app.include_router(diff.router)

    # ── Meta endpoints — must be on a router (not app directly) so they
    #    are registered before the catch-all StaticFiles mount ──────────────
    meta = APIRouter(prefix="/api", tags=["meta"])

    @meta.get("/health")
    async def health():
        return {"status": "ok"}

    @meta.get("/config")
    async def config_info():
        from backend.services.config import get_config
        cfg = get_config()
        return {
            "repo_path": cfg.effective_repo_path,
            "docs_dir": cfg.effective_docs_dir,
            "branch_prefix": cfg.effective_branch_prefix,
            "default_branch": cfg.repository.default_branch,
            "diff_mode": cfg.diff.rendered_diff_mode,
        }

    app.include_router(meta)

    # ── Static files (MUST be last — it acts as a catch-all) ─────────────────
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )

    return app


app = create_app()


# ── CLI entrypoint ────────────────────────────────────────────────────────────

@click.command()
@click.option("--config", "-c", default=None, help="Path to markdown-docs.yaml")
@click.option("--repo", "-r", default=None, help="Override: git repo path")
@click.option("--docs-dir", "-d", default=None, help="Override: docs sub-directory")
@click.option("--branch-prefix", "-p", default=None, help="Override: branch prefix")
@click.option("--host", "-h", default=None, help="Override: bind host")
@click.option("--port", "-P", default=None, type=int, help="Override: bind port")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload")
def main(
    config: str | None,
    repo: str | None,
    docs_dir: str | None,
    branch_prefix: str | None,
    host: str | None,
    port: int | None,
    reload: bool,
) -> None:
    """Start the markdown-docs development server."""
    cfg = load_config(
        path=config,
        repo_override=repo,
        docs_dir_override=docs_dir,
        branch_prefix_override=branch_prefix,
    )

    bind_host = host or cfg.server.host
    bind_port = port or cfg.server.port

    click.echo(f"  repo      : {cfg.effective_repo_path}")
    click.echo(f"  docs_dir  : {cfg.effective_docs_dir}")
    click.echo(f"  prefix    : {cfg.effective_branch_prefix}")
    click.echo(f"  listening : http://{bind_host}:{bind_port}")

    uvicorn.run(
        "backend.main:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
