from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.db.models import Issue, IssueOrigin, Repo, RepoType
from app.services import repo_service


def _http_404():
    request = httpx.Request("GET", "https://api.github.com/repos/owner/missing")
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("not found", request=request, response=response)


@pytest.mark.asyncio
async def test_connect_repo_rejects_bad_format(db_session):
    with pytest.raises(repo_service.RepoConnectError):
        await repo_service.connect_repo(db_session, "not-a-valid-repo-name")


@pytest.mark.asyncio
async def test_connect_repo_rejects_private_repo(db_session):
    with patch.object(repo_service.github_client, "get_repo", AsyncMock(return_value={"private": True})):
        with pytest.raises(repo_service.RepoConnectError, match="Private"):
            await repo_service.connect_repo(db_session, "owner/private-repo")


@pytest.mark.asyncio
async def test_connect_repo_not_found_raises(db_session):
    with patch.object(repo_service.github_client, "get_repo", AsyncMock(side_effect=_http_404())):
        with pytest.raises(repo_service.RepoConnectError, match="not found"):
            await repo_service.connect_repo(db_session, "owner/missing")


@pytest.mark.asyncio
async def test_connect_repo_success_ingests_baseline_issues(db_session):
    open_issues = [
        {"number": 1, "title": "Bug A", "body": "oops", "html_url": "http://x/1", "created_at": "2026-01-01T00:00:00Z"},
        {"number": 2, "title": "Bug B", "body": "oops2", "html_url": "http://x/2", "created_at": "2026-01-02T00:00:00Z"},
    ]
    with patch.object(
        repo_service.github_client, "get_repo", AsyncMock(return_value={"private": False, "default_branch": "main"})
    ), patch.object(repo_service.github_client, "list_open_issues", AsyncMock(return_value=open_issues)):
        repo = await repo_service.connect_repo(db_session, "octocat/hello-world", session_id="sess-1")

        assert repo.repo_type == RepoType.inspected
        assert repo.default_branch == "main"
        assert repo.created_by_session_id == "sess-1"
        assert repo.baseline_ingested_at is not None

        issues = db_session.query(Issue).filter_by(repo_id=repo.id).all()
        assert len(issues) == 2
        assert all(i.origin == IssueOrigin.baseline for i in issues)


@pytest.mark.asyncio
async def test_connect_repo_is_idempotent(db_session):
    with patch.object(
        repo_service.github_client, "get_repo", AsyncMock(return_value={"private": False, "default_branch": "main"})
    ), patch.object(repo_service.github_client, "list_open_issues", AsyncMock(return_value=[])):
        first = await repo_service.connect_repo(db_session, "octocat/idempotent-test")
        second = await repo_service.connect_repo(db_session, "octocat/idempotent-test")

        assert first.id == second.id
        assert db_session.query(Repo).filter_by(full_name="octocat/idempotent-test").count() == 1


@pytest.mark.asyncio
async def test_refresh_repo_issues_only_adds_new_ones(db_session):
    with patch.object(
        repo_service.github_client, "get_repo", AsyncMock(return_value={"private": False, "default_branch": "main"})
    ), patch.object(
        repo_service.github_client, "list_open_issues",
        AsyncMock(return_value=[{"number": 1, "title": "A", "body": "", "html_url": "u", "created_at": None}]),
    ):
        repo = await repo_service.connect_repo(db_session, "octocat/refresh-test")

    with patch.object(
        repo_service.github_client, "list_open_issues",
        AsyncMock(return_value=[
            {"number": 1, "title": "A", "body": "", "html_url": "u", "created_at": None},
            {"number": 2, "title": "B (new)", "body": "", "html_url": "u2", "created_at": None},
        ]),
    ):
        added = await repo_service.refresh_repo_issues(db_session, repo)

        assert added == 1
        issues = db_session.query(Issue).filter_by(repo_id=repo.id).order_by(Issue.issue_number).all()
        assert [i.issue_number for i in issues] == [1, 2]
        assert issues[0].origin == IssueOrigin.baseline
        assert issues[1].origin == IssueOrigin.manual_refresh


@pytest.mark.asyncio
async def test_seed_sandbox_repos_creates_sandbox_type(db_session):
    with patch("app.services.repo_service.settings") as mock_settings, patch.object(
        repo_service.github_client, "get_repo", AsyncMock(return_value={"private": False, "default_branch": "main"})
    ), patch.object(repo_service.github_client, "list_open_issues", AsyncMock(return_value=[])):
        mock_settings.sandbox_repo_list = ["octocat/sandbox-demo"]

        await repo_service.seed_sandbox_repos(db_session)

        repo = db_session.query(Repo).filter_by(full_name="octocat/sandbox-demo").one()
        assert repo.repo_type == RepoType.sandbox


@pytest.mark.asyncio
async def test_seed_sandbox_repos_skips_repo_already_seeded(db_session):
    db_session.add(Repo(owner="octocat", name="sandbox-demo", full_name="octocat/sandbox-demo", repo_type=RepoType.sandbox))
    db_session.commit()

    with patch("app.services.repo_service.settings") as mock_settings, patch.object(
        repo_service.github_client, "get_repo", AsyncMock()
    ) as mock_get_repo:
        mock_settings.sandbox_repo_list = ["octocat/sandbox-demo"]

        await repo_service.seed_sandbox_repos(db_session)

        mock_get_repo.assert_not_called()
        assert db_session.query(Repo).filter_by(full_name="octocat/sandbox-demo").count() == 1
