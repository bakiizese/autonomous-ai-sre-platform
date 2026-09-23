import base64
from unittest.mock import patch
import httpx
import pytest
import respx

from app.services.github_client import GitHubClient, github_client

REPO = "owner/test-repo"


@pytest.fixture
def client():
    """Instantiate a GitHubClient with a fake token for testing."""
    with patch("app.services.github_client.settings") as mock_settings:
        mock_settings.GITHUB_TOKEN = "fake-token"
        yield GitHubClient()


@pytest.mark.asyncio
@respx.mock
async def test_get_issue_success(client):
    """Test successfully fetching an issue from GitHub."""
    issue_number = 42
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_number}"

    respx.get(url).respond(
        status_code=200,
        json={
            "number": issue_number,
            "title": "Bug report",
            "body": "Something broken",
        },
    )

    issue = await client.get_issue(REPO, issue_number)

    assert issue["number"] == 42
    assert issue["title"] == "Bug report"
    assert respx.calls.last.request.headers["Authorization"] == "Bearer fake-token"


@pytest.mark.asyncio
@respx.mock
async def test_get_default_branch_sha_success(client):
    """Test getting default branch name and fetching its latest commit SHA."""
    repo_url = f"https://api.github.com/repos/{REPO}"
    ref_url = f"https://api.github.com/repos/{REPO}/git/ref/heads/main"

    respx.get(repo_url).respond(status_code=200, json={"default_branch": "main"})
    respx.get(ref_url).respond(
        status_code=200, json={"object": {"sha": "abc123def456"}}
    )

    sha = await client.get_default_branch_sha(REPO)

    assert sha == "abc123def456"


@pytest.mark.asyncio
@respx.mock
async def test_get_repo_returns_metadata(client):
    """Test fetching repo metadata (used by repo_service to check private/default_branch)."""
    url = f"https://api.github.com/repos/{REPO}"
    respx.get(url).respond(
        status_code=200, json={"default_branch": "main", "private": False}
    )

    repo_data = await client.get_repo(REPO)

    assert repo_data["default_branch"] == "main"
    assert repo_data["private"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [201, 422])
@respx.mock
async def test_create_branch(client, status_code):
    """Test creating a new git branch (both new branch and already existing branch)."""
    url = f"https://api.github.com/repos/{REPO}/git/refs"

    route = respx.post(url).respond(status_code=status_code, json={})

    result = await client.create_branch(REPO, "fix/bug-1", "base-sha-123")

    assert result is True
    assert route.called
    request_data = route.calls.last.request.read().decode("utf-8")
    assert '"ref":"refs/heads/fix/bug-1"' in request_data
    assert '"sha":"base-sha-123"' in request_data


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_file_new_file(client):
    """Test creating a brand new file (no existing SHA)."""
    file_path = "src/main.py"
    branch_name = "fix/bug-1"
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"

    # Return 404 for existing file check
    respx.get(f"{url}?ref={branch_name}").respond(status_code=404)
    # Return 201 for file creation
    respx.put(url).respond(status_code=201, json={"commit": {"sha": "new-file-sha"}})

    content = "print('hello world')"
    expected_encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    res = await client.create_or_update_file(
        REPO, file_path, content, "add main.py", branch_name
    )

    assert res["commit"]["sha"] == "new-file-sha"
    put_request = respx.calls.last.request
    request_json = put_request.content.decode("utf-8")
    assert expected_encoded in request_json
    assert '"sha":' not in request_json  # Ensure no SHA payload sent for new file


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_file_existing_file(client):
    """Test updating an existing file (provides old SHA in payload)."""
    file_path = "src/main.py"
    branch_name = "fix/bug-1"
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"

    # Existing file check returns old SHA
    respx.get(f"{url}?ref={branch_name}").respond(
        status_code=200, json={"sha": "old-sha-999"}
    )
    # File update endpoint response
    respx.put(url).respond(status_code=200, json={"commit": {"sha": "updated-sha"}})

    res = await client.create_or_update_file(
        REPO, file_path, "updated content", "update file", branch_name
    )

    assert res["commit"]["sha"] == "updated-sha"
    request_json = respx.calls.last.request.content.decode("utf-8")
    assert '"sha":"old-sha-999"' in request_json


@pytest.mark.asyncio
@respx.mock
async def test_create_pull_request(client):
    """Test creating a Pull Request."""
    url = f"https://api.github.com/repos/{REPO}/pulls"

    respx.post(url).respond(
        status_code=201, json={"number": 10, "html_url": "https://github.com/pr/10"}
    )

    res = await client.create_pull_request(
        REPO,
        title="Fix bug",
        body="PR details",
        head_branch="fix/bug-1",
        base_branch="main",
    )

    assert res["number"] == 10
    assert respx.calls.last.request.headers["X-GitHub-Api-Version"] == "2022-11-28"


@pytest.mark.asyncio
@respx.mock
async def test_create_issue(client):
    """Test opening a new issue (used by the sandbox 'inject a bug' demo flow)."""
    url = f"https://api.github.com/repos/{REPO}/issues"

    respx.post(url).respond(
        status_code=201, json={"number": 99, "html_url": "https://github.com/issue/99"}
    )

    res = await client.create_issue(REPO, "Demo bug: off-by-one", "Injected for the demo.")

    assert res["number"] == 99
    request_json = respx.calls.last.request.content.decode("utf-8")
    assert '"title":"Demo bug: off-by-one"' in request_json


@pytest.mark.asyncio
@respx.mock
async def test_list_open_issues_filters_pull_requests(client):
    """Test listing issues and verifying PR items are filtered out."""
    url = f"https://api.github.com/repos/{REPO}/issues?state=open"

    raw_response = [
        {
            "number": 1,
            "title": "Real Issue",
            "body": "Issue details",
            "created_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/issue/1",
        },
        {
            "number": 2,
            "title": "Pull Request disguised as issue",
            "body": "PR details",
            "created_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/pull/2",
            "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/2"},
        },
    ]

    respx.get(url).respond(status_code=200, json=raw_response)

    issues = await client.list_open_issues(REPO)

    assert len(issues) == 1
    assert issues[0]["number"] == 1
    assert issues[0]["title"] == "Real Issue"


@pytest.mark.asyncio
@respx.mock
async def test_http_error_propagation(client):
    """Test HTTP 404/500 errors throw HTTPStatusError via raise_for_status()."""
    url = f"https://api.github.com/repos/{REPO}/issues/999"
    respx.get(url).respond(status_code=404)

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_issue(REPO, 999)


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_recorded_on_every_call(client):
    """_request() records GitHub's rate-limit headers on every call, so the
    status endpoint reflects reality even for a plain successful request."""
    from app.services import rate_limit_service

    url = f"https://api.github.com/repos/{REPO}/issues/1"
    respx.get(url).respond(
        status_code=200,
        json={"number": 1, "title": "x", "body": ""},
        headers={"X-RateLimit-Remaining": "37", "X-RateLimit-Reset": "9999999999"},
    )

    await client.get_issue(REPO, 1)

    status = rate_limit_service.get_status()
    assert status["github"]["remaining_calls"] == 37
    assert status["github"]["is_limited"] is False


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_flagged_when_exhausted(client):
    """A 403 with X-RateLimit-Remaining: 0 marks GitHub as limited."""
    from app.services import rate_limit_service

    url = f"https://api.github.com/repos/{REPO}/issues/2"
    respx.get(url).respond(
        status_code=403,
        json={"message": "rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"},
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_issue(REPO, 2)

    status = rate_limit_service.get_status()
    assert status["github"]["is_limited"] is True
    assert status["github"]["limited_until"] is not None
