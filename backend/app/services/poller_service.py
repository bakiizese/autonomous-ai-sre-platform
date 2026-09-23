import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Issue, IssueOrigin, PollRun, PollTriggerType, Repo, RepoType, RunTriggerSource
from app.db.session import SessionLocal
from app.services.github_client import github_client
from app.services.remediation_service import start_remediation_run

logger = logging.getLogger("sre_pipeline")

# Set externally (e.g. by POST /api/poll/trigger-now) to force an immediate
# poll cycle instead of waiting out the rest of the sleep interval.
poll_trigger_event = asyncio.Event()


async def run_poll_cycle(db: Session, trigger_type: PollTriggerType = PollTriggerType.interval) -> PollRun:
    """Auto-polling only ever looks at sandbox repos — inspected (read-only)
    repos are refresh-on-demand only via the dashboard's manual button, to
    keep the free-tier Gemini budget from being spent on repos the platform
    doesn't control anyway. Poller state lives in Postgres (the `issues`
    table), not an in-memory set, so it survives a restart."""
    poll_run = PollRun(trigger_type=trigger_type, started_at=datetime.now(timezone.utc))
    db.add(poll_run)
    db.flush()

    repos_polled = 0
    new_issues_found = 0
    try:
        sandbox_repos = db.query(Repo).filter_by(repo_type=RepoType.sandbox, is_active=True).all()
        for repo in sandbox_repos:
            repos_polled += 1
            issues = await github_client.list_open_issues(repo.full_name)
            known_numbers = {n for (n,) in db.query(Issue.issue_number).filter_by(repo_id=repo.id).all()}

            for issue_data in issues:
                if issue_data["number"] in known_numbers:
                    continue

                issue = Issue(
                    repo_id=repo.id,
                    issue_number=issue_data["number"],
                    title=issue_data["title"],
                    body=issue_data.get("body") or "",
                    html_url=issue_data.get("html_url"),
                    state="open",
                    origin=IssueOrigin.poller_detected,
                )
                db.add(issue)
                db.flush()
                new_issues_found += 1
                logger.info(f"[POLLER] 🆕 New issue detected: #{issue.issue_number} - {issue.title}")
                asyncio.create_task(_remediate_in_new_session(issue.id, repo.id))

            repo.last_polled_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"[POLLER] ⚠️ Polling error: {e}")
        poll_run.error_message = str(e)
    finally:
        poll_run.repos_polled = repos_polled
        poll_run.new_issues_found = new_issues_found
        poll_run.completed_at = datetime.now(timezone.utc)
        db.commit()

    return poll_run


async def _remediate_in_new_session(issue_id: int, repo_id: int) -> None:
    """Fire-and-forget background task — runs in its own DB session since it
    outlives the poll cycle's session that discovered the issue."""
    with SessionLocal() as db:
        issue = db.get(Issue, issue_id)
        repo = db.get(Repo, repo_id)
        if issue is None or repo is None:
            return
        try:
            await start_remediation_run(db, issue, repo, RunTriggerSource.poller)
        except Exception as e:
            logger.error(f"[POLLER] ⚠️ Auto-remediation failed for issue #{issue.issue_number}: {e}")


async def poll_loop() -> None:
    while True:
        trigger_type = PollTriggerType.manual if poll_trigger_event.is_set() else PollTriggerType.interval
        poll_trigger_event.clear()
        with SessionLocal() as db:
            await run_poll_cycle(db, trigger_type)
        try:
            await asyncio.wait_for(poll_trigger_event.wait(), timeout=settings.POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
