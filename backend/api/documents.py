"""
/api/documents — list, read, render, and save markdown documents.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.models.schema import (
    DocumentContent,
    RenderRequest,
    RenderResponse,
    SaveRequest,
    SaveResponse,
)
from backend.services import git as git_svc
from backend.services import pandoc as pandoc_svc
from backend.services.config import get_config

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _repo_and_config(request: Request):
    cfg = get_config()
    repo = git_svc.open_repo(cfg)
    return repo, cfg


@router.get("", summary="List all markdown documents")
async def list_documents(request: Request, branch: str | None = None):
    repo, cfg = _repo_and_config(request)
    try:
        paths = git_svc.list_docs(repo, cfg, branch=branch)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"documents": paths, "branch": branch or git_svc.current_branch(repo)}


@router.get("/{path:path}", summary="Get document content and optional rendered HTML")
async def get_document(
    path: str,
    request: Request,
    branch: str | None = None,
    render: bool = False,
):
    repo, cfg = _repo_and_config(request)
    try:
        content, sha = git_svc.read_file(repo, path, cfg, branch=branch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    rendered_html: str | None = None
    if render:
        try:
            rendered_html = await pandoc_svc.render_markdown(content, cfg, path)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return DocumentContent(
        path=path,
        content=content,
        html=rendered_html,
        branch=branch or git_svc.current_branch(repo),
        commit_sha=sha,
    )


@router.post("/render", summary="Render raw markdown to HTML")
async def render_document(body: RenderRequest):
    cfg = get_config()
    try:
        html = await pandoc_svc.render_markdown(body.content, cfg, body.path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return RenderResponse(html=html, path=body.path)


@router.put("/{path:path}", summary="Save document and commit to branch")
async def save_document(path: str, body: SaveRequest, request: Request):
    repo, cfg = _repo_and_config(request)
    body.path = path  # path from URL takes precedence
    try:
        sha = git_svc.write_file_and_commit(
            repo, path, body.content, cfg,
            branch=body.branch,
            commit_message=body.commit_message,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return SaveResponse(
        path=path,
        branch=body.branch,
        commit_sha=sha,
        commit_message=body.commit_message or f"docs: update {path}",
    )
