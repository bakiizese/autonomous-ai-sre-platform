import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Issue, IssueOrigin, Repo, RepoType
from app.services.github_client import github_client

logger = logging.getLogger("sre_pipeline")

REPO_FULL_NAME_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


class RepoConnectError(Exception):
    """User-facing failure connecting a repo (bad format, not found, private)."""


def _parse_github_datetime(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _sync_issues(db: Session, repo: Repo, origin: IssueOrigin) -> int:
    """Imports currently-open GitHub issues not already known for this repo.
    Never triggers remediation itself — that's the poller's job for genuinely
    new issues going forward. Used for both the initial baseline scan and the
    dashboard's manual 'refresh issues' action."""
    issues = await github_client.list_open_issues(repo.full_name)
    known_numbers = {n for (n,) in db.query(Issue.issue_number).filter_by(repo_id=repo.id).all()}

    count = 0
    for issue_data in issues:
        if issue_data["number"] in known_numbers:
            continue
        db.add(
            Issue(
                repo_id=repo.id,
                issue_number=issue_data["number"],
                title=issue_data["title"],
                body=issue_data.get("body") or "",
                html_url=issue_data.get("html_url"),
                github_created_at=_parse_github_datetime(issue_data.get("created_at")),
                state="open",
                origin=origin,
            )
        )
        count += 1
    db.flush()
    return count


async def ingest_baseline_issues(db: Session, repo: Repo) -> int:
    count = await _sync_issues(db, repo, IssueOrigin.baseline)
    repo.baseline_ingested_at = datetime.now(timezone.utc)
    db.flush()
    return count


async def refresh_repo_issues(db: Session, repo: Repo) -> int:
    return await _sync_issues(db, repo, IssueOrigin.manual_refresh)


async def connect_repo(db: Session, full_name: str, session_id: str | None = None) -> Repo:
    """Connects an arbitrary public repo for READ-ONLY inspection. repo_type
    is always hardcoded to 'inspected' here — sandbox repos are only ever
    created by seed_sandbox_repos() from server config, never from this
    public-facing entrypoint."""
    full_name = full_name.strip()
    if not REPO_FULL_NAME_RE.match(full_name):
        raise RepoConnectError(f"'{full_name}' doesn't look like a valid owner/repo.")

    existing = db.query(Repo).filter_by(full_name=full_name).one_or_none()
    if existing is not None:
        return existing

    try:
        repo_data = await github_client.get_repo(full_name)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise RepoConnectError(f"GitHub repo '{full_name}' not found.") from e
        raise

    if repo_data.get("private"):
        raise RepoConnectError("Private repositories aren't supported for inspection.")

    owner, name = full_name.split("/", 1)
    repo = Repo(
        owner=owner,
        name=name,
        full_name=full_name,
        repo_type=RepoType.inspected,
        default_branch=repo_data.get("default_branch"),
        created_by_session_id=session_id,
    )
    db.add(repo)
    db.flush()

    await ingest_baseline_issues(db, repo)
    db.commit()
    return repo


async def seed_sandbox_repos(db: Session) -> None:
    """Called once at app startup. Repos listed in settings.SANDBOX_REPOS are
    the only ones ever marked repo_type='sandbox' — the platform can only
    write to (branch/commit/PR) repos that got here, never a repo a visitor
    connected through connect_repo()."""
    for full_name in settings.sandbox_repo_list:
        existing = db.query(Repo).filter_by(full_name=full_name).one_or_none()
        if existing is not None:
            continue
        try:
            repo_data = await github_client.get_repo(full_name)
        except Exception as e:
            logger.warning(f"[STARTUP] Could not seed sandbox repo '{full_name}': {e}")
            continue

        owner, name = full_name.split("/", 1)
        repo = Repo(
            owner=owner,
            name=name,
            full_name=full_name,
            repo_type=RepoType.sandbox,
            default_branch=repo_data.get("default_branch"),
        )
        db.add(repo)
        db.flush()
        await ingest_baseline_issues(db, repo)

    db.commit()
