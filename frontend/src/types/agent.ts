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

export interface GitHubIssue {
  number: number;
  title: string;
  body: string;
  created_at: string;
  html_url: string;
}

export interface PRAutomationResponse {
  status: string;
  pr_url: string;
  pr_number: number;
  branch: string;
  verification: VerificationResult;
}