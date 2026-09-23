from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Issue, IssueOrigin, Repo, RepoType, RunTriggerSource
from app.schemas.api import DemoInjectRequest, RemediationRunOut
from app.services.demo_scenarios import get_scenario
from app.services.github_client import github_client
from app.services.remediation_service import start_remediation_run

router = APIRouter(prefix="/api/repos", tags=["demo"])


@router.post("/{repo_id}/demo/inject-bug", response_model=RemediationRunOut)
async def inject_demo_bug(
    repo_id: int, request: DemoInjectRequest = DemoInjectRequest(), db: Session = Depends(get_db)
):
    """Sandbox-only: opens a real issue from a canned scenario on a repo the
    platform actually owns, then immediately runs the full pipeline on it —
    this is how a visitor watches the loop work without needing their own
    GitHub credentials."""
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    if repo.repo_type != RepoType.sandbox:
        raise HTTPException(status_code=403, detail="Demo bug injection is only available on sandbox repos.")

    try:
        scenario = get_scenario(request.scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    issue_data = await github_client.create_issue(repo.full_name, scenario.title, scenario.body)

    issue = Issue(
        repo_id=repo.id,
        issue_number=issue_data["number"],
        title=issue_data.get("title") or scenario.title,
        body=issue_data.get("body") or scenario.body,
        html_url=issue_data.get("html_url"),
        state="open",
        origin=IssueOrigin.demo_injected,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    return await start_remediation_run(db, issue, repo, RunTriggerSource.demo_injected)
