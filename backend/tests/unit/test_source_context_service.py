from unittest.mock import AsyncMock, patch

import pytest

from app.services import source_context_service


@pytest.mark.asyncio
async def test_resolves_via_direct_file_path():
    with patch.object(source_context_service.github_client, "get_file_content", AsyncMock(return_value="code")) as mock_get:
        result = await source_context_service.resolve_source_context(
            "o/r", "`calculate_running_total()` in `demo/off_by_one.py` is wrong"
        )

    assert result == {"source_code": "code", "resolved_path": "demo/off_by_one.py", "method": "direct_path"}
    mock_get.assert_called_once_with("o/r", "demo/off_by_one.py")


@pytest.mark.asyncio
async def test_falls_back_to_code_search_for_function_name():
    with patch.object(source_context_service.github_client, "search_code", AsyncMock(return_value=[{"path": "pkg/mod.py"}])), \
         patch.object(source_context_service.github_client, "get_file_content", AsyncMock(return_value="found it")):
        result = await source_context_service.resolve_source_context("o/r", "crash when calling apply_discount() twice")

    assert result["method"] == "code_search"
    assert result["resolved_path"] == "pkg/mod.py"
    assert result["source_code"] == "found it"


@pytest.mark.asyncio
async def test_not_found_when_nothing_resolves():
    with patch.object(source_context_service.github_client, "get_file_content", AsyncMock(return_value=None)), \
         patch.object(source_context_service.github_client, "search_code", AsyncMock(return_value=[])):
        result = await source_context_service.resolve_source_context("o/r", "something is broken in demo/gone.py, see do_thing()")

    assert result == {"source_code": "", "resolved_path": None, "method": "not_found"}
