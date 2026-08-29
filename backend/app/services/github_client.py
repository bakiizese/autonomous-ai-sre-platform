import base64
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings

class GitHubClient:
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.repo = settings.GITHUB_REPO
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_issue(self, issue_number: int) -> Dict[str, Any]:
        """Fetch details of a specific issue from the target repository."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/issues/{issue_number}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def get_default_branch_sha(self) -> str:
        """Get the latest commit SHA from the main/master branch."""
        async with httpx.AsyncClient() as client:
            # First fetch repository info to get default branch name
            repo_res = await client.get(self.base_url, headers=self.headers)
            repo_res.raise_for_status()
            default_branch = repo_res.json().get("default_branch", "main")

            # Get reference SHA for default branch
            ref_res = await client.get(
                f"{self.base_url}/git/ref/heads/{default_branch}",
                headers=self.headers
            )
            ref_res.raise_for_status()
            return ref_res.json()["object"]["sha"]

    async def create_branch(self, branch_name: str, base_sha: str) -> bool:
        """Create a new git branch from base SHA."""
        url = f"{self.base_url}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            if response.status_code in (201, 422):  # 422 if branch already exists
                return True
            response.raise_for_status()
            return True

    async def create_or_update_file(
        self,
        file_path: str,
        content: str,
        commit_message: str,
        branch_name: str
    ) -> Dict[str, Any]:
        """Commit a file fix or new test file to the target branch."""
        url = f"{self.base_url}/contents/{file_path}"
        
        # Check if file already exists on target branch to get its SHA
        async with httpx.AsyncClient() as client:
            sha: Optional[str] = None
            existing_res = await client.get(
                f"{url}?ref={branch_name}",
                headers=self.headers
            )
            if existing_res.status_code == 200:
                sha = existing_res.json().get("sha")

            # Base64 encode file content
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            
            payload = {
                "message": commit_message,
                "content": encoded_content,
                "branch": branch_name
            }
            if sha:
                payload["sha"] = sha

            response = await client.put(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main"
    ) -> Dict[str, Any]:
        """Open a Pull Request with AI remediation details and verification badges."""
        url = f"{self.base_url}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()

github_client = GitHubClient()