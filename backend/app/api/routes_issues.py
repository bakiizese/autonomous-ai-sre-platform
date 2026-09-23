from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Issue, IssueOrigin, Repo, RunTriggerSource
from app.schemas.api import IssueOut, RemediationRunOut
from app.services.context_resolver import (
    extract_candidate_file_paths,
    extract_candidate_function_names,
)
from app.services.github_client import github_client
from app.services.remediation_service import start_remediation_run

router = APIRouter(prefix="/api/repos", tags=["issues"])


def _get_repo_or_404(db: Session, repo_id: int) -> Repo:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


def _issue_to_out(issue: Issue) -> IssueOut:
    latest = issue.latest_remediation_run
    return IssueOut(
        id=issue.id,
        repo_id=issue.repo_id,
        issue_number=issue.issue_number,
        title=issue.title,
        body=issue.body,
        html_url=issue.html_url,
        state=issue.state,
        origin=issue.origin,
        latest_remediation_run_id=issue.latest_remediation_run_id,
        latest_run_status=latest.status if latest else None,
        latest_run_risk_score=latest.risk_score if latest else None,
        first_seen_at=issue.first_seen_at,
    )


@router.get("/{repo_id}/issues", response_model=list[IssueOut])
def list_repo_issues(
    repo_id: int,
    scope: str = Query(default="all", pattern="^(baseline|live|all)$"),
    db: Session = Depends(get_db),
):
    repo = _get_repo_or_404(db, repo_id)
    query = db.query(Issue).filter_by(repo_id=repo.id)
    if scope == "baseline":
        query = query.filter(Issue.origin == IssueOrigin.baseline)
    elif scope == "live":
        query = query.filter(Issue.origin != IssueOrigin.baseline)
    issues = query.order_by(Issue.issue_number.desc()).all()
    return [_issue_to_out(i) for i in issues]


@router.get("/{repo_id}/issues/{issue_number}/context")
async def get_issue_context(repo_id: int, issue_number: int, db: Session = Depends(get_db)):
    """Best-effort auto-resolution of the source file relevant to a GitHub issue."""
    repo = _get_repo_or_404(db, repo_id)
    issue = await github_client.get_issue(repo.full_name, issue_number)
    body = issue.get("body", "") or ""

    for path in extract_candidate_file_paths(body):
        content = await github_client.get_file_content(repo.full_name, path)
        if content:
            return {"source_code": content, "resolved_path": path, "method": "direct_path"}

    for func_name in extract_candidate_function_names(body):
        results = await github_client.search_code(repo.full_name, func_name)
        if results:
            path = results[0]["path"]
            content = await github_client.get_file_content(repo.full_name, path)
            if content:
                return {"source_code": content, "resolved_path": path, "method": "code_search"}

    return {"source_code": "", "resolved_path": None, "method": "not_found"}


@router.post("/{repo_id}/issues/{issue_number}/triage", response_model=RemediationRunOut)
async def trigger_manual_triage(repo_id: int, issue_number: int, db: Session = Depends(get_db)):
    repo = _get_repo_or_404(db, repo_id)
    issue = db.query(Issue).filter_by(repo_id=repo.id, issue_number=issue_number).one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found for this repo")
    return await start_remediation_run(db, issue, repo, RunTriggerSource.manual_dashboard)
