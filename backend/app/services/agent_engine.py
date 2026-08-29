#this uses the google-genai SDK and enforces JSON schemas via Pydantic for structured multi-agent reasoning.
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

def run_diagnosis_agent(error_log: str, source_code_context: str) -> DiagnosisOutput:
    prompt = f"""
    You are an expert SRE Diagnosis Agent. Analyze the following stack trace and source code context.
    
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
            response_schema=DiagnosisOutput,
            temperature=0.2,
        ),
    )
    return DiagnosisOutput.model_validate_json(response.text)


def run_remediation_agent(diagnosis: DiagnosisOutput, source_code_context: str) -> RemediationOutput:
    prompt = f"""
    You are an expert Remediation Agent. Based on the diagnosis, provide a clean code fix and git diff patch.
    
    ROOT CAUSE:
    {diagnosis.root_cause_analysis}
    
    SOURCE CODE CONTEXT:
    {source_code_context}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RemediationOutput,
            temperature=0.2,
        ),
    )
    return RemediationOutput.model_validate_json(response.text)


def run_test_generation_agent(diagnosis: DiagnosisOutput, remediation: RemediationOutput) -> TestGenerationOutput:
    prompt = f"""
    You are a Test Generation Agent. Generate a standalone, executable `pytest` unit test that validates the proposed fix.
    
    DIAGNOSIS:
    {diagnosis.root_cause_analysis}
    
    CODE FIX:
    {remediation.code_fix}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TestGenerationOutput,
            temperature=0.2,
        ),
    )
    return TestGenerationOutput.model_validate_json(response.text)


def run_sre_pipeline(error_log: str, source_code_context: str) -> PipelineResult:
    """Orchestrates the 3-stage agent pipeline sequentially."""
    diagnosis = run_diagnosis_agent(error_log, source_code_context)
    remediation = run_remediation_agent(diagnosis, source_code_context)
    test_gen = run_test_generation_agent(diagnosis, remediation)
    
    return PipelineResult(
        diagnosis=diagnosis,
        remediation=remediation,
        test_generation=test_gen
    )