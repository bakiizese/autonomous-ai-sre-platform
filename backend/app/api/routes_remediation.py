from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import RemediationRun, RunStatus
from app.schemas.api import RejectRequest, RemediationRunOut
from app.services.remediation_service import ApprovalError, approve_remediation_run, reject_remediation_run

router = APIRouter(tags=["remediation"])


def _get_run_or_404(db: Session, run_id: int) -> RemediationRun:
    run = db.get(RemediationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Remediation run not found")
    return run


@router.get("/api/remediation-runs/{run_id}", response_model=RemediationRunOut)
def get_remediation_run(run_id: int, db: Session = Depends(get_db)):
    return _get_run_or_404(db, run_id)


@router.get("/api/repos/{repo_id}/remediation-runs", response_model=list[RemediationRunOut])
def list_remediation_runs(
    repo_id: int, status: Optional[str] = Query(default=None), db: Session = Depends(get_db)
):
    query = db.query(RemediationRun).filter_by(repo_id=repo_id)
    if status:
        try:
            status_enum = RunStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status '{status}'")
        query = query.filter_by(status=status_enum)
    return query.order_by(RemediationRun.started_at.desc()).all()


@router.post("/api/remediation-runs/{run_id}/approve", response_model=RemediationRunOut)
async def approve_run(run_id: int, db: Session = Depends(get_db)):
    """The only route in the system that actually opens a branch/commit/PR
    on GitHub — every sandbox-repo run stops here waiting for this call."""
    run = _get_run_or_404(db, run_id)
    try:
        return await approve_remediation_run(db, run)
    except ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/api/remediation-runs/{run_id}/reject", response_model=RemediationRunOut)
def reject_run(run_id: int, request: RejectRequest = RejectRequest(), db: Session = Depends(get_db)):
    run = _get_run_or_404(db, run_id)
    try:
        return reject_remediation_run(db, run, request.reason)
    except ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))
