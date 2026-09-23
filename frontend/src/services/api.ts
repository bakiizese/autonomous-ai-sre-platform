import axios from 'axios';
import type {
  IssueContextResponse,
  IssueRecord,
  PipelineResult,
  PollStatus,
  RateLimitStatus,
  RemediationRun,
  Repo,
  RunStatus,
  VerificationResult,
} from '../types/agent';

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// No accounts this round — an opaque per-browser id, recorded server-side
// on repos this visitor connects. Not an auth mechanism.
function getSessionId(): string {
  try {
    const existing = localStorage.getItem('sentinel-session-id');
    if (existing) return existing;
    const fresh = crypto.randomUUID();
    localStorage.setItem('sentinel-session-id', fresh);
    return fresh;
  } catch {
    return 'anonymous';
  }
}

const client = axios.create({
  baseURL: API_BASE_URL,
  // Diagnose -> fix -> test -> verify (+ one retry) is several sequential LLM calls.
  timeout: 120000,
  headers: { 'X-Session-Id': getSessionId() },
});

export const api = {
  // --- repos ---
  listRepos: async (): Promise<Repo[]> => (await client.get('/api/repos')).data,

  connectRepo: async (fullName: string): Promise<Repo> =>
    (await client.post('/api/repos/connect', { full_name: fullName })).data,

  refreshIssues: async (repoId: number): Promise<{ added: number }> =>
    (await client.post(`/api/repos/${repoId}/refresh-issues`)).data,

  // --- issues ---
  listIssues: async (
    repoId: number,
    scope: 'baseline' | 'live' | 'all' = 'all'
  ): Promise<IssueRecord[]> =>
    (await client.get(`/api/repos/${repoId}/issues`, { params: { scope } })).data,

  getIssueContext: async (repoId: number, issueNumber: number): Promise<IssueContextResponse> =>
    (await client.get(`/api/repos/${repoId}/issues/${issueNumber}/context`)).data,

  triageIssue: async (repoId: number, issueNumber: number): Promise<RemediationRun> =>
    (await client.post(`/api/repos/${repoId}/issues/${issueNumber}/triage`)).data,

  // --- remediation runs (human-in-the-loop) ---
  listRuns: async (repoId: number, status?: RunStatus): Promise<RemediationRun[]> =>
    (
      await client.get(`/api/repos/${repoId}/remediation-runs`, {
        params: status ? { status } : undefined,
      })
    ).data,

  approveRun: async (runId: number): Promise<RemediationRun> =>
    (await client.post(`/api/remediation-runs/${runId}/approve`)).data,

  rejectRun: async (runId: number, reason?: string): Promise<RemediationRun> =>
    (await client.post(`/api/remediation-runs/${runId}/reject`, { reason })).data,

  // --- sandbox demo ---
  injectBug: async (repoId: number, scenarioId?: string): Promise<RemediationRun> =>
    (await client.post(`/api/repos/${repoId}/demo/inject-bug`, { scenario_id: scenarioId })).data,

  // --- poller ---
  triggerPollNow: async (): Promise<void> => {
    await client.post('/api/poll/trigger-now');
  },

  getPollStatus: async (): Promise<PollStatus> => (await client.get('/api/poll/status')).data,

  // --- email alerts ---
  subscribe: async (repoId: number, email: string): Promise<{ status: string; email: string }> =>
    (await client.post(`/api/repos/${repoId}/subscribe`, { email })).data,

  // --- status ---
  getRateLimits: async (): Promise<RateLimitStatus> =>
    (await client.get('/api/status/rate-limits')).data,

  // --- scratchpad (unpersisted, no repo) ---
  runTriage: async (errorLog: string, sourceCodeContext: string): Promise<PipelineResult> =>
    (
      await client.post('/api/triage', {
        error_log: errorLog,
        source_code_context: sourceCodeContext,
      })
    ).data,

  verifyPatch: async (
    targetFile: string,
    remediatedCode: string,
    testFileName: string,
    generatedTestCode: string
  ): Promise<VerificationResult> =>
    (
      await client.post('/api/verify', {
        target_file: targetFile,
        remediated_code: remediatedCode,
        test_file_name: testFileName,
        generated_test_code: generatedTestCode,
      })
    ).data,
};
