"""Best-effort extraction of likely file paths and function names from a GitHub issue body,
used to auto-resolve source code context without requiring the user to paste it manually."""
import re

# Matches path-like tokens ending in .py, e.g. "app/utils.py" or "utils.py"
_FILE_PATH_PATTERN = re.compile(r"[\w\-./]*[\w\-]+\.py\b")

# Matches identifier-followed-by-open-paren, e.g. "export_logs_to_file(" or "calculate_rate("
_FUNCTION_CALL_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")

# Common builtins/keywords that look like function calls but aren't useful search targets
_EXCLUDED_NAMES = {
    "if", "for", "while", "print", "str", "int", "float", "list", "dict",
    "set", "tuple", "len", "range", "open", "type", "isinstance", "super",
    "return", "raise", "except", "def", "class", "with", "lambda", "format",
    "join", "split", "get", "getattr", "setattr", "hasattr", "repr", "input",
}


def extract_candidate_file_paths(body: str) -> list[str]:
    """Finds likely .py file paths mentioned in an issue body, deduplicated, in order of appearance."""
    matches = _FILE_PATH_PATTERN.findall(body)
    seen: list[str] = []
    for m in matches:
        cleaned = m.strip("`'\",.:()[]")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def extract_candidate_function_names(body: str) -> list[str]:
    """Finds likely function names referenced via a call-like pattern, e.g. `foo()`, ranked by first appearance."""
    matches = _FUNCTION_CALL_PATTERN.findall(body)
    seen: list[str] = []
    for m in matches:
        if m in _EXCLUDED_NAMES or m in seen:
            continue
        seen.append(m)
    return seen
