export interface DiagnosisOutput {
  summary: string;
  root_cause_analysis: string;
  affected_files: string[];
  risk_score: number;
}

export interface RemediationOutput {
  patch_explanation: string;
  target_file: string;
  code_fix: string;
  git_diff_patch: string;
}

export interface TestGenerationOutput {
  test_file_name: string;
  test_code: string;
  test_description: string;
}

export interface PipelineResult {
  diagnosis: DiagnosisOutput;
  remediation: RemediationOutput;
  test_generation: TestGenerationOutput;
}

export interface VerificationResult {
  passed: boolean;
  target_test_passed: boolean;
  stdout: string;
  stderr: string;
}

export interface IssueContextResponse {
  source_code: string;
  resolved_path: string | null;
  method: 'direct_path' | 'code_search' | 'not_found';
}

export type RepoType = 'sandbox' | 'inspected';

export type IssueOrigin =
  | 'baseline'
  | 'poller_detected'
  | 'demo_injected'
  | 'manual_refresh';

export type RunStatus =
  | 'pending'
  | 'running'
  | 'diagnosed'
  | 'verify_failed'
  | 'awaiting_approval'
  | 'rejected'
  | 'pr_opened'
  | 'failed';

export interface Repo {
  id: number;
  owner: string;
  name: string;
  full_name: string;
  repo_type: RepoType;
  is_active: boolean;
  default_branch: string | null;
  connected_at: string;
  last_polled_at: string | null;
  baseline_ingested_at: string | null;
}

export interface IssueRecord {
  id: number;
  repo_id: number;
  issue_number: number;
  title: string;
  body: string | null;
  html_url: string | null;
  state: string;
  origin: IssueOrigin;
  latest_remediation_run_id: number | null;
  latest_run_status: RunStatus | null;
  latest_run_risk_score: number | null;
  first_seen_at: string;
}

export interface RemediationRun {
  id: number;
  issue_id: number;
  repo_id: number;
  trigger_source: 'poller' | 'manual_dashboard' | 'demo_injected';
  status: RunStatus;
  risk_score: number | null;
  diagnosis_summary: string | null;
  root_cause_analysis: string | null;
  affected_files: string[] | null;
  target_file: string | null;
  code_fix: string | null;
  git_diff_patch: string | null;
  test_file_name: string | null;
  test_code: string | null;
  verification_passed: boolean | null;
  verification_stdout: string | null;
  verification_stderr: string | null;
  fix_attempts: number;
  pr_url: string | null;
  pr_number: number | null;
  branch_name: string | null;
  error_message: string | null;
  node_trace: { node: string; duration_ms: number; attempt?: number; passed?: boolean }[] | null;
  started_at: string;
  completed_at: string | null;
}

export interface ProviderRateLimit {
  is_limited: boolean;
  limited_until: string | null;
  remaining_calls: number | null;
}

export interface RateLimitStatus {
  gemini: ProviderRateLimit;
  github: ProviderRateLimit;
}

export interface PollStatus {
  poll_interval_seconds: number;
  last_run: {
    id: number;
    started_at: string;
    completed_at: string | null;
    trigger_type: 'interval' | 'manual';
    repos_polled: number;
    new_issues_found: number;
    error_message: string | null;
  } | null;
}
