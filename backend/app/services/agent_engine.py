# Real multi-node LangGraph pipeline (diagnose -> fix -> test -> verify),
# with a genuine cyclic retry edge back to `fix` on a failed sandbox
# verification. Each node still makes exactly one raw google-genai call with
# a narrow structured-output schema, so there's no new dependency on
# langchain's model wrapper — just a real, inspectable graph around it.
from datetime import datetime, timezone
from typing import Optional, TypedDict

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy

from app.core.config import settings
from app.schemas.agent import (
    DiagnosisOutput,
    PipelineResult,
    RemediationOutput,
    TestGenerationOutput,
    VerificationResult,
)
from app.services import rate_limit_service
from app.services.sandbox_runner import run_preflight_verification

client = genai.Client(api_key=settings.GEMINI_API_KEY)


class GeminiStillRateLimitedError(Exception):
    """Raised when we already know Gemini is rate-limited and skip the
    network call entirely — not retried, since an immediate retry can't
    possibly succeed any faster than waiting out the known limit window."""


class PipelineState(TypedDict, total=False):
    error_log: str
    source_code_context: str
    diagnosis: DiagnosisOutput
    remediation: RemediationOutput
    test_generation: TestGenerationOutput
    verification: VerificationResult
    fix_attempt: int
    max_fix_attempts: int
    stop_after_diagnosis: bool
    node_trace: list[dict]


# ---------------------------------------------------------------------------
# Gemini call helper — every LLM node routes through this single choke point.
# ---------------------------------------------------------------------------


def _extract_retry_after(exc: errors.ClientError) -> Optional[int]:
    response = getattr(exc, "response", None)
    header = getattr(response, "headers", {}).get("Retry-After") if response is not None else None
    try:
        return int(header) if header is not None else None
    except (TypeError, ValueError):
        return None


DEFAULT_GEMINI_RETRY_AFTER_SECONDS = 30


def _call_gemini(prompt: str, response_schema: type[BaseModel]) -> BaseModel:
    # No is_gemini_limited() check here deliberately: this function is also
    # what LangGraph's own RetryPolicy calls again on each backoff attempt
    # within a single node, and a fail-fast guard here would immediately
    # block that in-flight retry from ever reaching the network again,
    # permanently defeating the backoff it's in the middle of. The
    # known-limited check instead lives once at run_sre_pipeline()'s entry,
    # where it belongs: deciding whether to start a *new* pipeline run at all.
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.2,
            ),
        )
    except errors.ClientError as e:
        if e.code == 429:
            retry_after = _extract_retry_after(e) or DEFAULT_GEMINI_RETRY_AFTER_SECONDS
            rate_limit_service.record_gemini_rate_limit(retry_after_seconds=retry_after, message=str(e))
        raise

    rate_limit_service.record_gemini_success()
    return response_schema.model_validate_json(response.text)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ValidationError):
        return True
    if isinstance(exc, errors.ClientError):
        return exc.code == 429
    return False


LLM_RETRY_POLICY = RetryPolicy(max_attempts=4, retry_on=_is_retryable)


def _trace_entry(node: str, started_at: datetime, **extra) -> dict:
    ended_at = datetime.now(timezone.utc)
    return {
        "node": node,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
        **extra,
    }


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def diagnose_node(state: PipelineState) -> dict:
    started = datetime.now(timezone.utc)
    prompt = f"""
    You are an expert Autonomous SRE Engine. Diagnose the root cause of the
    following error and assign a risk score (1-10, where 10 is a critical
    production-impacting issue).

    ERROR LOG / STACK TRACE:
    {state["error_log"]}

    SOURCE CODE CONTEXT:
    {state.get("source_code_context", "")}
    """
    diagnosis = _call_gemini(prompt, DiagnosisOutput)
    return {
        "diagnosis": diagnosis,
        "node_trace": state.get("node_trace", []) + [_trace_entry("diagnose", started)],
    }


def fix_node(state: PipelineState) -> dict:
    started = datetime.now(timezone.utc)
    fix_attempt = state.get("fix_attempt", 0) + 1

    prior_failure = ""
    verification = state.get("verification")
    if verification is not None and not verification.passed:
        prior_failure = f"""

    A PREVIOUS FIX ATTEMPT FAILED SANDBOX VERIFICATION:
    {verification.stderr}
    Diagnose why that fix didn't work and correct the underlying issue —
    don't just patch the test to pass.
    """

    prompt = f"""
    You are an expert Autonomous SRE Engine. Provide a clean Python code fix
    and a unified git diff patch for the following diagnosed issue.

    ERROR LOG / STACK TRACE:
    {state["error_log"]}

    SOURCE CODE CONTEXT:
    {state.get("source_code_context", "")}

    ROOT CAUSE ANALYSIS:
    {state["diagnosis"].root_cause_analysis}
    {prior_failure}
    """
    remediation = _call_gemini(prompt, RemediationOutput)
    return {
        "remediation": remediation,
        "fix_attempt": fix_attempt,
        "node_trace": state.get("node_trace", []) + [_trace_entry("fix", started, attempt=fix_attempt)],
    }


def test_gen_node(state: PipelineState) -> dict:
    started = datetime.now(timezone.utc)
    prompt = f"""
    You are an expert Autonomous SRE Engine. Generate a standalone,
    executable pytest test file that verifies the following fix actually
    resolves the original error.

    ORIGINAL ERROR LOG:
    {state["error_log"]}

    THE FIX:
    {state["remediation"].code_fix}
    """
    test_generation = _call_gemini(prompt, TestGenerationOutput)
    return {
        "test_generation": test_generation,
        "node_trace": state.get("node_trace", []) + [_trace_entry("test_gen", started)],
    }


def verify_node(state: PipelineState) -> dict:
    started = datetime.now(timezone.utc)
    verification = run_preflight_verification(
        target_file_rel_path=state["remediation"].target_file,
        remediated_code=state["remediation"].code_fix,
        test_file_name=state["test_generation"].test_file_name,
        generated_test_code=state["test_generation"].test_code,
    )
    return {
        "verification": verification,
        "node_trace": state.get("node_trace", [])
        + [_trace_entry("verify", started, passed=verification.passed)],
    }


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


def _after_diagnose(state: PipelineState) -> str:
    return "end" if state.get("stop_after_diagnosis") else "fix"


def _after_verify(state: PipelineState) -> str:
    verification = state["verification"]
    # fix_attempt counts attempts already made (1 after the first fix_node
    # call), so "<=" here means max_fix_attempts is the number of *extra*
    # retries allowed beyond that first attempt.
    if not verification.passed and state.get("fix_attempt", 0) <= state.get("max_fix_attempts", 0):
        return "retry"
    return "end"


def _build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("diagnose", diagnose_node, retry_policy=LLM_RETRY_POLICY)
    graph.add_node("fix", fix_node, retry_policy=LLM_RETRY_POLICY)
    graph.add_node("test_gen", test_gen_node, retry_policy=LLM_RETRY_POLICY)
    graph.add_node("verify", verify_node)

    graph.set_entry_point("diagnose")
    graph.add_conditional_edges("diagnose", _after_diagnose, {"fix": "fix", "end": END})
    graph.add_edge("fix", "test_gen")
    graph.add_edge("test_gen", "verify")
    graph.add_conditional_edges("verify", _after_verify, {"retry": "fix", "end": END})

    return graph.compile()


_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def run_sre_pipeline(
    error_log: str,
    source_code_context: str,
    stop_after_diagnosis: bool = False,
    max_fix_attempts: Optional[int] = None,
) -> PipelineState:
    if rate_limit_service.is_gemini_limited():
        raise GeminiStillRateLimitedError(
            "Gemini is currently rate-limited; skipping this run to avoid burning free-tier quota."
        )

    initial_state: PipelineState = {
        "error_log": error_log,
        "source_code_context": source_code_context,
        "fix_attempt": 0,
        "max_fix_attempts": (
            max_fix_attempts if max_fix_attempts is not None else settings.AGENT_MAX_FIX_RETRIES
        ),
        "stop_after_diagnosis": stop_after_diagnosis,
        "node_trace": [],
    }
    return _graph.invoke(initial_state)


def to_pipeline_result(state: PipelineState) -> PipelineResult:
    """Reassembles the old single-call response shape, for the ad hoc
    /api/triage scratchpad route that predates per-repo persistence."""
    return PipelineResult(
        diagnosis=state["diagnosis"],
        remediation=state["remediation"],
        test_generation=state["test_generation"],
    )
