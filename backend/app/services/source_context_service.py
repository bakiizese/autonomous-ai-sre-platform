from typing import TypedDict

from app.services.context_resolver import (
    extract_candidate_file_paths,
    extract_candidate_function_names,
)
from app.services.github_client import github_client


class ResolvedContext(TypedDict):
    source_code: str
    resolved_path: str | None
    method: str  # 'direct_path' | 'code_search' | 'not_found'


async def resolve_source_context(repo_full_name: str, issue_body: str) -> ResolvedContext:
    """Best-effort: find the source file an issue is talking about.
    Tier 1: the body names a file path. Tier 2: it names a function, so search
    the repo for it. Raises on GitHub errors — callers decide whether that's fatal."""
    for path in extract_candidate_file_paths(issue_body):
        content = await github_client.get_file_content(repo_full_name, path)
        if content:
            return {"source_code": content, "resolved_path": path, "method": "direct_path"}

    for func_name in extract_candidate_function_names(issue_body):
        results = await github_client.search_code(repo_full_name, func_name)
        if results:
            path = results[0]["path"]
            content = await github_client.get_file_content(repo_full_name, path)
            if content:
                return {"source_code": content, "resolved_path": path, "method": "code_search"}

    return {"source_code": "", "resolved_path": None, "method": "not_found"}
