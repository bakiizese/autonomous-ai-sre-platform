import base64
from unittest.mock import patch
import httpx
import pytest
import respx

from app.services.github_client import GitHubClient, github_client


@pytest.fixture
def client():
    """Instantiate a GitHubClient with standard headers for testing."""
    with patch("app.services.github_client.settings") as mock_settings:
        mock_settings.GITHUB_TOKEN = "fake-token"
        mock_settings.GITHUB_REPO = "owner/test-repo"
        yield GitHubClient()


@pytest.mark.asyncio
@respx.mock
async def test_get_issue_success(client):
    """Test successfully fetching an issue from GitHub."""
    issue_number = 42
    url = f"https://api.github.com/repos/owner/test-repo/issues/{issue_number}"

    respx.get(url).respond(
        status_code=200,
        json={
            "number": issue_number,
            "title": "Bug report",
            "body": "Something broken",
        },
    )

    issue = await client.get_issue(issue_number)

    assert issue["number"] == 42
    assert issue["title"] == "Bug report"
    assert respx.calls.last.request.headers["Authorization"] == "Bearer fake-token"


@pytest.mark.asyncio
@respx.mock
async def test_get_default_branch_sha_success(client):
    """Test getting default branch name and fetching its latest commit SHA."""
    repo_url = "https://api.github.com/repos/owner/test-repo"
    ref_url = "https://api.github.com/repos/owner/test-repo/git/ref/heads/main"

    respx.get(repo_url).respond(status_code=200, json={"default_branch": "main"})
    respx.get(ref_url).respond(
        status_code=200, json={"object": {"sha": "abc123def456"}}
    )

    sha = await client.get_default_branch_sha()

    assert sha == "abc123def456"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [201, 422])
@respx.mock
async def test_create_branch(client, status_code):
    """Test creating a new git branch (both new branch and already existing branch)."""
    url = "https://api.github.com/repos/owner/test-repo/git/refs"

    route = respx.post(url).respond(status_code=status_code, json={})

    result = await client.create_branch("fix/bug-1", "base-sha-123")

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
    url = f"https://api.github.com/repos/owner/test-repo/contents/{file_path}"

    # Return 404 for existing file check
    respx.get(f"{url}?ref={branch_name}").respond(status_code=404)
    # Return 201 for file creation
    respx.put(url).respond(status_code=201, json={"commit": {"sha": "new-file-sha"}})

    content = "print('hello world')"
    expected_encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    res = await client.create_or_update_file(
        file_path, content, "add main.py", branch_name
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
    url = f"https://api.github.com/repos/owner/test-repo/contents/{file_path}"

    # Existing file check returns old SHA
    respx.get(f"{url}?ref={branch_name}").respond(
        status_code=200, json={"sha": "old-sha-999"}
    )
    # File update endpoint response
    respx.put(url).respond(status_code=200, json={"commit": {"sha": "updated-sha"}})

    res = await client.create_or_update_file(
        file_path, "updated content", "update file", branch_name
    )

    assert res["commit"]["sha"] == "updated-sha"
    request_json = respx.calls.last.request.content.decode("utf-8")
    assert '"sha":"old-sha-999"' in request_json


@pytest.mark.asyncio
@respx.mock
async def test_create_pull_request(client):
    """Test creating a Pull Request."""
    url = "https://api.github.com/repos/owner/test-repo/pulls"

    respx.post(url).respond(
        status_code=201, json={"number": 10, "html_url": "https://github.com/pr/10"}
    )

    res = await client.create_pull_request(
        title="Fix bug",
        body="PR details",
        head_branch="fix/bug-1",
        base_branch="main",
    )

    assert res["number"] == 10
    assert respx.calls.last.request.headers["X-GitHub-Api-Version"] == "2022-11-28"


@pytest.mark.asyncio
@respx.mock
async def test_list_open_issues_filters_pull_requests(client):
    """Test listing issues and verifying PR items are filtered out."""
    url = "https://api.github.com/repos/owner/test-repo/issues?state=open"

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

    issues = await client.list_open_issues()

    assert len(issues) == 1
    assert issues[0]["number"] == 1
    assert issues[0]["title"] == "Real Issue"


@pytest.mark.asyncio
@respx.mock
async def test_http_error_propagation(client):
    """Test HTTP 404/500 errors throw HTTPStatusError via raise_for_status()."""
    url = "https://api.github.com/repos/owner/test-repo/issues/999"
    respx.get(url).respond(status_code=404)

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_issue(999)
