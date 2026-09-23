from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_session_id
from app.db.models import Repo
from app.schemas.api import RepoConnectRequest, RepoOut
from app.services import repo_service

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.post("/connect", response_model=RepoOut)
async def connect_repo(
    request: RepoConnectRequest,
    db: Session = Depends(get_db),
    session_id: Optional[str] = Depends(get_session_id),
):
    try:
        return await repo_service.connect_repo(db, request.full_name, session_id)
    except repo_service.RepoConnectError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db)):
    return db.query(Repo).filter_by(is_active=True).order_by(Repo.connected_at.desc()).all()


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.post("/{repo_id}/refresh-issues")
async def refresh_issues(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    added = await repo_service.refresh_repo_issues(db, repo)
    db.commit()
    return {"added": added}
