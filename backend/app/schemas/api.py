from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models import IssueOrigin, RepoType, RunStatus, RunTriggerSource


class RepoConnectRequest(BaseModel):
    full_name: str


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: str
    name: str
    full_name: str
    repo_type: RepoType
    is_active: bool
    default_branch: Optional[str] = None
    connected_at: datetime
    last_polled_at: Optional[datetime] = None
    baseline_ingested_at: Optional[datetime] = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    issue_number: int
    title: str
    body: Optional[str] = None
    html_url: Optional[str] = None
    state: str
    origin: IssueOrigin
    latest_remediation_run_id: Optional[int] = None
    latest_run_status: Optional[RunStatus] = None
    latest_run_risk_score: Optional[int] = None
    first_seen_at: datetime


class RemediationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    repo_id: int
    trigger_source: RunTriggerSource
    status: RunStatus
    risk_score: Optional[int] = None
    diagnosis_summary: Optional[str] = None
    root_cause_analysis: Optional[str] = None
    affected_files: Optional[list] = None
    target_file: Optional[str] = None
    code_fix: Optional[str] = None
    git_diff_patch: Optional[str] = None
    test_file_name: Optional[str] = None
    test_code: Optional[str] = None
    verification_passed: Optional[bool] = None
    verification_stdout: Optional[str] = None
    verification_stderr: Optional[str] = None
    fix_attempts: int
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    branch_name: Optional[str] = None
    error_message: Optional[str] = None
    node_trace: Optional[list] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class DemoInjectRequest(BaseModel):
    scenario_id: Optional[str] = None


class SubscribeRequest(BaseModel):
    email: EmailStr


class RateLimitProviderStatus(BaseModel):
    is_limited: bool
    limited_until: Optional[str] = None
    remaining_calls: Optional[int] = None


class RateLimitStatusOut(BaseModel):
    gemini: RateLimitProviderStatus
    github: RateLimitProviderStatus


class PollStatusOut(BaseModel):
    poll_interval_seconds: int
    last_run: Optional[dict[str, Any]] = None
