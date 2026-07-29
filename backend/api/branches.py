"""
/api/branches — list, create, switch, and manage doc-edit branches.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.models.schema import (
    BranchInfo,
    CreateBranchRequest,
    CreateBranchResponse,
    MergeRequest,
    MergeResponse,
)
from backend.services import git as git_svc
from backend.services.config import get_config

router = APIRouter(prefix="/api/branches", tags=["branches"])


@router.get("", summary="List all branches")
async def list_branches(request: Request) -> dict:
    cfg = get_config()
    repo = git_svc.open_repo(cfg)
    branches = git_svc.list_branches(repo, cfg)
    return {
        "branches": [b.model_dump() for b in branches],
        "current": git_svc.current_branch(repo),
        "default": cfg.repository.default_branch,
        "prefix": cfg.effective_branch_prefix,
    }


@router.post("", summary="Create a new doc-edit branch")
async def create_branch(body: CreateBranchRequest) -> CreateBranchResponse:
    cfg = get_config()
    repo = git_svc.open_repo(cfg)
    try:
        result = git_svc.create_branch(
            repo, body.name, cfg,
            base_branch=body.base_branch,
            switch_to=body.switch_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/{branch_name}/switch", summary="Switch to a branch")
async def switch_branch(branch_name: str) -> dict:
    cfg = get_config()
    repo = git_svc.open_repo(cfg)
    try:
        git_svc.switch_branch(repo, branch_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"current": branch_name}


@router.post("/{branch_name}/merge", summary="Squash-merge a doc branch into target")
async def merge_branch(branch_name: str, body: MergeRequest) -> MergeResponse:
    """
    Squash all commits on source_branch down to a single diff, then apply
    to target_branch. Returns conflict info if the merge cannot be fast-forwarded.
    """
    cfg = get_config()
    repo = git_svc.open_repo(cfg)
    body.source_branch = branch_name

    target = body.target_branch or cfg.repository.default_branch

    try:
        changes = git_svc.squash_branch_to_diff(repo, branch_name, cfg)
        if not changes:
            return MergeResponse(merged=False, conflicts=["No changes to merge"])

        # Switch to target and apply each changed file as a single commit
        git_svc.switch_branch(repo, target)
        message = body.commit_message or f"docs: merge {branch_name} into {target}"

        for rel_path, (old_content, new_content) in changes.items():
            if new_content is not None:
                git_svc.write_file_and_commit(
                    repo, rel_path, new_content, cfg,
                    branch=target,
                    commit_message=message,
                )
            # TODO: handle deletions (new_content is None)

        final_sha = str(repo.head.target)
        return MergeResponse(merged=True, commit_sha=final_sha)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{branch_name}/changes", summary="List files changed on a doc branch")
async def branch_changes(branch_name: str) -> dict:
    cfg = get_config()
    repo = git_svc.open_repo(cfg)
    try:
        changes = git_svc.squash_branch_to_diff(repo, branch_name, cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "branch": branch_name,
        "base": cfg.repository.default_branch,
        "changed_files": list(changes.keys()),
    }
