from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import Issue, IssueOrigin, PollTriggerType, Repo, RepoType
from app.services import poller_service


@pytest.mark.asyncio
async def test_run_poll_cycle_only_polls_sandbox_repos(db_session):
    sandbox = Repo(owner="o", name="sandbox", full_name="o/sandbox", repo_type=RepoType.sandbox)
    inspected = Repo(owner="o", name="inspected", full_name="o/inspected", repo_type=RepoType.inspected)
    db_session.add_all([sandbox, inspected])
    db_session.commit()

    with patch.object(
        poller_service.github_client, "list_open_issues", AsyncMock(return_value=[])
    ) as mock_list:
        await poller_service.run_poll_cycle(db_session)

        mock_list.assert_called_once_with("o/sandbox")


@pytest.mark.asyncio
async def test_run_poll_cycle_ignores_inactive_sandbox_repo(db_session):
    inactive = Repo(owner="o", name="off", full_name="o/off", repo_type=RepoType.sandbox, is_active=False)
    db_session.add(inactive)
    db_session.commit()

    with patch.object(poller_service.github_client, "list_open_issues", AsyncMock()) as mock_list:
        await poller_service.run_poll_cycle(db_session)
        mock_list.assert_not_called()


@pytest.mark.asyncio
async def test_run_poll_cycle_skips_already_known_issues(db_session):
    repo = Repo(owner="o", name="known", full_name="o/known", repo_type=RepoType.sandbox)
    db_session.add(repo)
    db_session.flush()
    db_session.add(Issue(repo_id=repo.id, issue_number=1, title="Already seen", origin=IssueOrigin.baseline))
    db_session.commit()

    with patch.object(
        poller_service.github_client, "list_open_issues",
        AsyncMock(return_value=[{"number": 1, "title": "Already seen", "body": "", "html_url": "u", "created_at": None}]),
    ), patch.object(poller_service, "_remediate_in_new_session", AsyncMock()) as mock_remediate:
        poll_run = await poller_service.run_poll_cycle(db_session)

        assert poll_run.new_issues_found == 0
        mock_remediate.assert_not_called()
        assert db_session.query(Issue).filter_by(repo_id=repo.id).count() == 1


@pytest.mark.asyncio
async def test_run_poll_cycle_schedules_remediation_for_new_issue(db_session):
    repo = Repo(owner="o", name="fresh", full_name="o/fresh", repo_type=RepoType.sandbox)
    db_session.add(repo)
    db_session.commit()

    with patch.object(
        poller_service.github_client, "list_open_issues",
        AsyncMock(return_value=[{"number": 9, "title": "New bug", "body": "boom", "html_url": "u", "created_at": None}]),
    ), patch.object(poller_service, "_remediate_in_new_session", AsyncMock()) as mock_remediate:
        poll_run = await poller_service.run_poll_cycle(db_session, PollTriggerType.manual)

        assert poll_run.repos_polled == 1
        assert poll_run.new_issues_found == 1
        assert poll_run.trigger_type == PollTriggerType.manual

        new_issue = db_session.query(Issue).filter_by(repo_id=repo.id, issue_number=9).one()
        assert new_issue.origin == IssueOrigin.poller_detected

        mock_remediate.assert_called_once_with(new_issue.id, repo.id)


@pytest.mark.asyncio
async def test_run_poll_cycle_records_error_without_crashing(db_session):
    repo = Repo(owner="o", name="broken", full_name="o/broken", repo_type=RepoType.sandbox)
    db_session.add(repo)
    db_session.commit()

    with patch.object(
        poller_service.github_client, "list_open_issues", AsyncMock(side_effect=RuntimeError("github is down"))
    ):
        poll_run = await poller_service.run_poll_cycle(db_session)

        assert poll_run.error_message == "github is down"
        assert poll_run.completed_at is not None
