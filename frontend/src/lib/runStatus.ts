import type { StageKey, StageStatus } from '../components/PipelineRail';
import type { RemediationRun, RunStatus } from '../types/agent';

export function riskColor(score: number) {
  if (score <= 3) return { bg: 'rgba(52,211,153,0.1)', border: 'var(--status-green)', text: 'var(--status-green)' };
  if (score <= 6) return { bg: 'rgba(251,191,36,0.1)', border: 'var(--status-amber)', text: 'var(--status-amber)' };
  return { bg: 'rgba(248,113,113,0.1)', border: 'var(--status-red)', text: 'var(--status-red)' };
}

export const STATUS_DISPLAY: Record<RunStatus, { label: string; color: string }> = {
  pending: { label: 'PENDING', color: 'var(--mute)' },
  running: { label: 'RUNNING', color: 'var(--signal)' },
  diagnosed: { label: 'DIAGNOSED', color: 'var(--signal)' },
  verify_failed: { label: 'VERIFY FAILED', color: 'var(--status-red)' },
  awaiting_approval: { label: 'AWAITING APPROVAL', color: 'var(--status-amber)' },
  rejected: { label: 'REJECTED', color: 'var(--mute)' },
  pr_opened: { label: 'PR OPENED', color: 'var(--status-green)' },
  failed: { label: 'FAILED', color: 'var(--status-red)' },
};

export function extractError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } } | null)?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

/** Maps a run's persisted status onto the four-stage pipeline rail. */
export function railStatusesForRun(
  run: RemediationRun | null,
  busy: boolean
): Partial<Record<StageKey, StageStatus>> {
  if (busy) return { diagnose: 'active' };
  if (!run) return {};

  switch (run.status) {
    case 'diagnosed':
      return { diagnose: 'done' };
    case 'awaiting_approval':
    case 'rejected':
      return { diagnose: 'done', patch: 'done', verify: 'done' };
    case 'verify_failed':
      return { diagnose: 'done', patch: 'done', verify: 'error' };
    case 'pr_opened':
      return { diagnose: 'done', patch: 'done', verify: 'done', ship: 'done' };
    case 'failed':
      return { diagnose: 'error' };
    default:
      return { diagnose: 'active' };
  }
}
