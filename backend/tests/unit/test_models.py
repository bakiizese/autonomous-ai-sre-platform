import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    EmailSubscriber,
    Issue,
    IssueOrigin,
    PollRun,
    PollTriggerType,
    RateLimitState,
    RemediationRun,
    Repo,
    RepoType,
    RunStatus,
    RunTriggerSource,
)


def make_repo(db_session, full_name="octocat/hello-world", repo_type=RepoType.inspected):
    repo = Repo(owner="octocat", name="hello-world", full_name=full_name, repo_type=repo_type)
    db_session.add(repo)
    db_session.flush()
    return repo


def test_create_and_fetch_repo(db_session):
    repo = make_repo(db_session)
    db_session.commit()

    fetched = db_session.query(Repo).filter_by(full_name="octocat/hello-world").one()
    assert fetched.id == repo.id
    assert fetched.repo_type == RepoType.inspected
    assert fetched.is_active is True


def test_repo_full_name_is_unique(db_session):
    make_repo(db_session, full_name="octocat/dupe")
    db_session.commit()

    with pytest.raises(IntegrityError):
        make_repo(db_session, full_name="octocat/dupe")
        db_session.commit()
    db_session.rollback()


def test_issue_unique_per_repo_and_number(db_session):
    repo = make_repo(db_session, full_name="octocat/unique-issue-test")

    db_session.add(
        Issue(repo_id=repo.id, issue_number=1, title="Bug A", origin=IssueOrigin.baseline)
    )
    db_session.commit()

    db_session.add(
        Issue(repo_id=repo.id, issue_number=1, title="Bug B (dup number)", origin=IssueOrigin.baseline)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_remediation_run_and_latest_run_pointer(db_session):
    repo = make_repo(db_session, full_name="octocat/circular-fk-test", repo_type=RepoType.sandbox)
    issue = Issue(repo_id=repo.id, issue_number=42, title="Null deref", origin=IssueOrigin.poller_detected)
    db_session.add(issue)
    db_session.flush()

    run = RemediationRun(
        issue_id=issue.id,
        repo_id=repo.id,
        trigger_source=RunTriggerSource.poller,
        status=RunStatus.awaiting_approval,
        risk_score=9,
    )
    db_session.add(run)
    db_session.flush()

    issue.latest_remediation_run_id = run.id
    db_session.commit()

    fetched_issue = db_session.get(Issue, issue.id)
    assert fetched_issue.latest_remediation_run.id == run.id
    assert fetched_issue.latest_remediation_run.status == RunStatus.awaiting_approval
    assert fetched_issue.remediation_runs[0].id == run.id


def test_email_subscriber_unsubscribe_token_unique(db_session):
    token = str(uuid.uuid4())
    db_session.add(EmailSubscriber(email="a@example.com", unsubscribe_token=token))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(EmailSubscriber(email="b@example.com", unsubscribe_token=token))
        db_session.commit()
    db_session.rollback()


def test_rate_limit_state_provider_unique(db_session):
    db_session.add(RateLimitState(provider="gemini", is_limited=False))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(RateLimitState(provider="gemini", is_limited=True))
        db_session.commit()
    db_session.rollback()


def test_poll_run_defaults(db_session):
    run = PollRun(trigger_type=PollTriggerType.manual)
    db_session.add(run)
    db_session.commit()

    fetched = db_session.get(PollRun, run.id)
    assert fetched.repos_polled == 0
    assert fetched.new_issues_found == 0
    assert fetched.trigger_type == PollTriggerType.manual
