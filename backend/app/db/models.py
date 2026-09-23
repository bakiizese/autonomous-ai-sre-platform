import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RepoType(str, enum.Enum):
    sandbox = "sandbox"
    inspected = "inspected"


class IssueOrigin(str, enum.Enum):
    baseline = "baseline"
    poller_detected = "poller_detected"
    demo_injected = "demo_injected"
    manual_refresh = "manual_refresh"


class RunTriggerSource(str, enum.Enum):
    poller = "poller"
    manual_dashboard = "manual_dashboard"
    demo_injected = "demo_injected"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    diagnosed = "diagnosed"
    verify_failed = "verify_failed"
    awaiting_approval = "awaiting_approval"
    rejected = "rejected"
    pr_opened = "pr_opened"
    failed = "failed"


class PollTriggerType(str, enum.Enum):
    interval = "interval"
    manual = "manual"


class Repo(Base):
    """A GitHub repo the platform knows about — either one of our own writable
    sandbox/demo repos, or a repo a visitor connected for read-only inspection.
    `repo_type` is only ever set server-side (see repo_service), never from
    client input, so this column is the enforcement point for the read-only
    guarantee on arbitrary connected repos."""

    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(511), unique=True, index=True)
    repo_type: Mapped[RepoType] = mapped_column(SAEnum(RepoType, name="repo_type"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issues: Mapped[list["Issue"]] = relationship(back_populates="repo")


class Issue(Base):
    """A GitHub issue we know about for a repo — either pre-existing at connect
    time (`origin='baseline'`) or detected afterwards. Replaces the old
    in-memory `seen_issue_numbers` set so poller state survives a restart."""

    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("repo_id", "issue_number", name="uq_issue_repo_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    issue_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(1024))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    github_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(10), default="open")
    origin: Mapped[IssueOrigin] = mapped_column(SAEnum(IssueOrigin, name="issue_origin"))
    # Circular FK with remediation_runs — see alembic/versions/0001_initial_schema.py
    # for how this column is added after both tables exist.
    latest_remediation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("remediation_runs.id", use_alter=True, name="fk_issue_latest_run"),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    repo: Mapped["Repo"] = relationship(back_populates="issues")
    remediation_runs: Mapped[list["RemediationRun"]] = relationship(
        back_populates="issue", foreign_keys="RemediationRun.issue_id"
    )
    latest_remediation_run: Mapped["RemediationRun | None"] = relationship(
        foreign_keys=[latest_remediation_run_id], post_update=True
    )


class RemediationRun(Base):
    """One triage/remediation attempt for one issue — the persisted audit
    trail and risk-score history. `status` never reaches `pr_opened` without
    passing through `awaiting_approval` first (the human-in-the-loop gate)."""

    __tablename__ = "remediation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"))
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    trigger_source: Mapped[RunTriggerSource] = mapped_column(SAEnum(RunTriggerSource, name="run_trigger_source"))
    status: Mapped[RunStatus] = mapped_column(SAEnum(RunStatus, name="run_status"), default=RunStatus.pending)

    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diagnosis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_files: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    target_file: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    code_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    git_diff_patch: Mapped[str | None] = mapped_column(Text, nullable=True)

    test_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    test_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    verification_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verification_stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_attempts: Mapped[int] = mapped_column(Integer, default=0)

    pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-node timing/attempt/error record, populated once at completion —
    # the graph runs via .invoke(), not streamed, so this is post-hoc, not live.
    node_trace: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    issue: Mapped["Issue"] = relationship(back_populates="remediation_runs", foreign_keys=[issue_id])
    repo: Mapped["Repo"] = relationship()


class EmailSubscriber(Base):
    """A visitor-submitted email watching a repo (or, when repo_id is NULL,
    every repo — used for the admin fallback seeded from ADMIN_ALERT_EMAIL).
    No per-subscriber threshold: everyone alerts off the single global
    settings.CRITICAL_RISK_THRESHOLD."""

    __tablename__ = "email_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(320))
    is_admin_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RateLimitState(Base):
    """One row per provider ('gemini' or 'github') tracking whether we're
    currently known to be rate-limited, so agent_engine/github_client can
    fail fast instead of burning a free-tier call."""

    __tablename__ = "rate_limit_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), unique=True)
    is_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    limited_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remaining_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class PollRun(Base):
    """Log of each poll cycle — backs GET /api/poll/status."""

    __tablename__ = "poll_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_type: Mapped[PollTriggerType] = mapped_column(SAEnum(PollTriggerType, name="poll_trigger_type"))
    repos_polled: Mapped[int] = mapped_column(Integer, default=0)
    new_issues_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
