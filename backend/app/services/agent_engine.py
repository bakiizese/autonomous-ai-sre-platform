# this uses the google-genai SDK and enforces JSON schemas via Pydantic for structured multi-agent reasoning.
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.agent import (
    DiagnosisOutput,
    RemediationOutput,
    TestGenerationOutput,
    PipelineResult,
)

client = genai.Client(api_key=settings.GEMINI_API_KEY)
MODEL_ID = "gemini-2.5-flash"


def run_sre_pipeline(error_log: str, source_code_context: str) -> PipelineResult:
    """
    Executes diagnosis, remediation, and test generation in a single
    structured LLM call to optimize speed and stay within API rate limits.
    """
    prompt = f"""
    You are an expert Autonomous SRE Engine. Perform an end-to-end triage:
    1. Diagnose the root cause of the error log and assign a risk score (1-10).
    2. Provide a clean Python code fix and git diff patch.
    3. Generate a standalone executable pytest test file to verify the fix.

    ERROR LOG / STACK TRACE:
    {error_log}

    SOURCE CODE CONTEXT:
    {source_code_context}
    """

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PipelineResult,
            temperature=0.2,
        ),
    )
    return PipelineResult.model_validate_json(response.text)
