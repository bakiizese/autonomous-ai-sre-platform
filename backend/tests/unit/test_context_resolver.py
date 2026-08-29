import pytest

from app.services.context_resolver import (
    _EXCLUDED_NAMES,
    extract_candidate_file_paths,
    extract_candidate_function_names,
)


class TestExtractCandidateFilePaths:
    """Tests for extract_candidate_file_paths."""

    def test_extract_standard_python_file_paths(self):
        """Extracts standard relative and root python file paths."""
        body = "There is an error in app/core/config.py and main.py during setup."
        result = extract_candidate_file_paths(body)
        assert result == ["app/core/config.py", "main.py"]

    def test_deduplicates_and_preserves_order(self):
        """Deduplicates paths while preserving first-appearance order."""
        body = "Check utils.py first, then app/services/client.py and back to utils.py."
        result = extract_candidate_file_paths(body)
        assert result == ["utils.py", "app/services/client.py"]

    def test_strips_punctuation_and_markdown_formatting(self):
        """Strips surrounding quotes, backticks, brackets, and punctuation from file paths."""
        body = (
            "Review `app/models.py`, 'services/auth.py': "
            '["db/session.py"]. Check (app/schemas/agent.py).'
        )
        result = extract_candidate_file_paths(body)
        assert result == [
            "app/models.py",
            "services/auth.py",
            "db/session.py",
            "app/schemas/agent.py",
        ]

    def test_ignores_non_python_files(self):
        """Ignores non-python extensions like .js, .json, .md, or .txt."""
        body = "Configuration in settings.json, script in index.js, and logic in runner.py."
        result = extract_candidate_file_paths(body)
        assert result == ["runner.py"]

    def test_empty_string_and_no_matches(self):
        """Returns empty list when no python files are found."""
        assert extract_candidate_file_paths("") == []
        assert extract_candidate_file_paths("The application crashed abruptly.") == []


class TestExtractCandidateFunctionNames:
    """Tests for extract_candidate_function_names."""

    def test_extract_function_calls(self):
        """Extracts custom function identifiers followed by an opening parenthesis."""
        body = (
            "The crash happens in process_data(data) after calling calculate_score()."
        )
        result = extract_candidate_function_names(body)
        assert result == ["process_data", "calculate_score"]

    def test_handles_whitespace_before_parenthesis(self):
        """Matches function names even when spaces exist before the opening parenthesis."""
        body = "Call trigger_pipeline   (payload) or run_sre_pipeline\n(log)."
        result = extract_candidate_function_names(body)
        assert result == ["trigger_pipeline", "run_sre_pipeline"]

    def test_filters_excluded_builtins_and_keywords(self):
        """Filters out Python builtins and control keywords defined in _EXCLUDED_NAMES."""
        body = "if (x > 0): print(str(x)) for item in list(data): custom_func(item)"
        result = extract_candidate_function_names(body)
        assert result == ["custom_func"]

    def test_deduplicates_and_preserves_order(self):
        """Ensures function names are deduplicated while maintaining order of appearance."""
        body = "run_job() then process_queue() and finally run_job() again."
        result = extract_candidate_function_names(body)
        assert result == ["run_job", "process_queue"]

    def test_ignores_identifiers_without_parentheses(self):
        """Ignores bare function or variable references without trailing parentheses."""
        body = "Look at the process_data and calculate_score functions."
        result = extract_candidate_function_names(body)
        assert result == []

    def test_excluded_names_set_integrity(self):
        """Sanity test verifying key Python builtins and keywords are present in exclusions."""
        essential_exclusions = {"if", "for", "print", "len", "open", "def", "class"}
        assert essential_exclusions.issubset(_EXCLUDED_NAMES)


class TestRealWorldIssueBodyExtraction:
    """Integration style tests against realistic GitHub issue bodies."""

    def test_github_issue_body_extraction(self):
        """Extracts both file paths and functions from a complex Markdown issue body."""
        body = """
        ### Bug Report: Pipeline Failure in `app/sre_pipeline.py`
        
        When processing logs in `run_sre_pipeline()`, an unhandled exception is raised:
        ```python
        File "app/core/engine.py", line 42, in execute
            result = parse_error_log ( raw_log )
        ```
        Steps to reproduce:
        1. Open `app/sre_pipeline.py`.
        2. Run `execute_task(payload)` after calling `format_response()`.
        3. Check `print(result)`.
        """
        paths = extract_candidate_file_paths(body)
        functions = extract_candidate_function_names(body)

        assert paths == ["app/sre_pipeline.py", "app/core/engine.py"]
        assert functions == [
            "run_sre_pipeline",
            "parse_error_log",
            "execute_task",
            "format_response",
        ]
