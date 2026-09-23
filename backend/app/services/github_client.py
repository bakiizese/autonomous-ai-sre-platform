import asyncio
import base64
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services import rate_limit_service

GITHUB_API_ROOT = "https://api.github.com"


class GitHubClient:
    """One client, one platform token (settings.GITHUB_TOKEN), used against
    every repo — sandbox or read-only inspected. Every public method takes an
    explicit repo_full_name; nothing is bound to a single repo at construction
    time anymore, so the same client instance can act against multiple repos."""

    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._http = httpx.AsyncClient()

    def _base_url(self, repo_full_name: str) -> str:
        return f"{GITHUB_API_ROOT}/repos/{repo_full_name}"

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Every GitHub call routes through here so rate-limit headers get
        recorded exactly once per call, success or failure, before the
        caller decides whether to raise_for_status() or inspect the code."""
        response = await self._http.request(method, url, headers=self.headers, **kwargs)
        await asyncio.to_thread(rate_limit_service.record_github_response, response)
        return response

    async def get_issue(self, repo_full_name: str, issue_number: int) -> Dict[str, Any]:
        """Fetch details of a specific issue from the target repository."""
        response = await self._request(
            "GET", f"{self._base_url(repo_full_name)}/issues/{issue_number}"
        )
        response.raise_for_status()
        return response.json()

    async def close_issue(
        self, repo_full_name: str, issue_number: int, comment: str | None = None
    ) -> Dict[str, Any]:
        """Closes a GitHub issue, optionally posting a comment first (e.g. linking the fix PR)."""
        base_url = self._base_url(repo_full_name)
        if comment:
            comment_res = await self._request(
                "POST", f"{base_url}/issues/{issue_number}/comments", json={"body": comment}
            )
            comment_res.raise_for_status()

        response = await self._request(
            "PATCH", f"{base_url}/issues/{issue_number}", json={"state": "closed"}
        )
        response.raise_for_status()
        return response.json()

    async def get_repo(self, repo_full_name: str) -> Dict[str, Any]:
        """Fetch repo metadata (default_branch, private, etc.) — used both by
        get_default_branch_sha and by repo_service when connecting a repo."""
        response = await self._request("GET", self._base_url(repo_full_name))
        response.raise_for_status()
        return response.json()

    async def get_default_branch_sha(self, repo_full_name: str) -> str:
        """Get the latest commit SHA from the repo's default branch."""
        repo_data = await self.get_repo(repo_full_name)
        default_branch = repo_data.get("default_branch", "main")

        ref_res = await self._request(
            "GET", f"{self._base_url(repo_full_name)}/git/ref/heads/{default_branch}"
        )
        ref_res.raise_for_status()
        return ref_res.json()["object"]["sha"]

    async def create_branch(self, repo_full_name: str, branch_name: str, base_sha: str) -> bool:
        """Create a new git branch from base SHA."""
        url = f"{self._base_url(repo_full_name)}/git/refs"
        payload = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
        response = await self._request("POST", url, json=payload)
        if response.status_code in (201, 422):  # 422 if branch already exists
            return True
        response.raise_for_status()
        return True

    async def create_or_update_file(
        self, repo_full_name: str, file_path: str, content: str, commit_message: str, branch_name: str
    ) -> Dict[str, Any]:
        """Commit a file fix or new test file to the target branch."""
        url = f"{self._base_url(repo_full_name)}/contents/{file_path}"

        sha: Optional[str] = None
        existing_res = await self._request("GET", f"{url}?ref={branch_name}")
        if existing_res.status_code == 200:
            sha = existing_res.json().get("sha")

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch_name,
        }
        if sha:
            payload["sha"] = sha

        response = await self._request("PUT", url, json=payload)
        response.raise_for_status()
        return response.json()

    async def create_pull_request(
        self, repo_full_name: str, title: str, body: str, head_branch: str, base_branch: str = "main"
    ) -> Dict[str, Any]:
        """Open a Pull Request with AI remediation details and verification badges."""
        url = f"{self._base_url(repo_full_name)}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }
        response = await self._request("POST", url, json=payload)
        response.raise_for_status()
        return response.json()

    async def create_issue(self, repo_full_name: str, title: str, body: str) -> Dict[str, Any]:
        """Opens a new issue — used by the sandbox 'inject a bug' demo flow."""
        url = f"{self._base_url(repo_full_name)}/issues"
        response = await self._request("POST", url, json={"title": title, "body": body})
        response.raise_for_status()
        return response.json()

    async def list_open_issues(self, repo_full_name: str) -> list[Dict[str, Any]]:
        """Fetch open issues from the GitHub repository, excluding pull requests."""
        url = f"{self._base_url(repo_full_name)}/issues?state=open"
        response = await self._request("GET", url)
        response.raise_for_status()
        issues = response.json()

        # GitHub's /issues endpoint returns both issues and PRs.
        # Filter out PRs (PR items contain a 'pull_request' key).
        return [
            {
                "number": issue["number"],
                "title": issue["title"],
                "body": issue.get("body", ""),
                "created_at": issue["created_at"],
                "html_url": issue["html_url"],
            }
            for issue in issues
            if "pull_request" not in issue
        ]

    async def get_file_content(self, repo_full_name: str, file_path: str) -> str | None:
        """Fetches and decodes a file's content from the repo's default branch. None if not found."""
        response = await self._request(
            "GET", f"{self._base_url(repo_full_name)}/contents/{file_path}"
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if data.get("encoding") != "base64":
            return None
        return base64.b64decode(data["content"]).decode("utf-8")

    async def search_code(self, repo_full_name: str, query: str) -> list[dict]:
        """Searches the repo's code for a query string (e.g. a function name). Returns [] on any failure."""
        response = await self._request(
            "GET",
            f"{GITHUB_API_ROOT}/search/code",
            params={"q": f"{query} repo:{repo_full_name}"},
        )
        if response.status_code != 200:
            return []
        return response.json().get("items", [])


github_client = GitHubClient()
