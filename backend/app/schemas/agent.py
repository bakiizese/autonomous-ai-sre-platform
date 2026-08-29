#pydantic schemas for multi-agent outputs
from pydantic import BaseModel, Field
from typing import Optional

class DiagnosisOutput(BaseModel):
    summary: str = Field(description="A brief summary of the issue.")
    root_cause_analysis: str = Field(description="Detailed explanation of what went wrong.")
    affected_files: list[str] = Field(description="List of files involved in the failure.")
    risk_score: int = Field(ge=1, le=10, description="Risk level from 1 (low) to 10 (critical).")

class RemediationOutput(BaseModel):
    patch_explanation: str = Field(description="Explanation of how the proposed fix addresses the bug.")
    target_file: str = Field(description="The relative file path targeted for modification.")
    code_fix: str = Field(description="The complete updated Python code for the target file.")
    git_diff_patch: str = Field(description="A unified git diff format representation of the fix.")

class TestGenerationOutput(BaseModel):
    test_file_name: str = Field(description="Suggested filename for the test, e.g., test_fix.py.")
    test_code: str = Field(description="Executable pytest code targeting the fix.")
    test_description: str = Field(description="Explanation of what this test verifies.")

class PipelineResult(BaseModel):
    diagnosis: DiagnosisOutput
    remediation: RemediationOutput
    test_generation: TestGenerationOutput

class VerificationResult(BaseModel):
    passed: bool
    target_test_passed: bool
    stdout: str
    stderr: str