"""
/api/diff — source and rendered visual diffs between branches.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schema import DiffRequest, RenderedDiff, SourceDiff
from backend.services import diff as diff_svc
from backend.services import git as git_svc
from backend.services.config import get_config

router = APIRouter(prefix="/api/diff", tags=["diff"])


@router.post("/source", summary="Raw markdown (unified) diff between branches")
async def source_diff(body: DiffRequest) -> SourceDiff:
    cfg = get_config()
    repo = git_svc.open_repo(cfg)

    base = body.base_branch or cfg.repository.default_branch
    compare = body.compare_branch or git_svc.current_branch(repo)

    try:
        old_content, _ = git_svc.read_file(repo, body.path, cfg, branch=base)
    except FileNotFoundError:
        old_content = ""
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        new_content, _ = git_svc.read_file(repo, body.path, cfg, branch=compare)
    except FileNotFoundError:
        new_content = ""
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return diff_svc.source_diff(
        old_content, new_content,
        path=body.path,
        base_branch=base,
        compare_branch=compare,
    )


@router.post("/rendered", summary="Visual block+word level rendered HTML diff")
async def rendered_diff(body: DiffRequest) -> RenderedDiff:
    cfg = get_config()
    repo = git_svc.open_repo(cfg)

    base = body.base_branch or cfg.repository.default_branch
    compare = body.compare_branch or git_svc.current_branch(repo)

    try:
        old_content, _ = git_svc.read_file(repo, body.path, cfg, branch=base)
    except FileNotFoundError:
        old_content = ""
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        new_content, _ = git_svc.read_file(repo, body.path, cfg, branch=compare)
    except FileNotFoundError:
        new_content = ""
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        result = diff_svc.rendered_diff_sync(
            old_content, new_content,
            path=body.path,
            base_branch=base,
            compare_branch=compare,
            config=cfg,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return result
