import { Code, ExternalLink, Eye, GitPullRequest, Terminal, XCircle } from 'lucide-react';
import { riskColor, STATUS_DISPLAY } from '../lib/runStatus';
import type { RemediationRun } from '../types/agent';

interface RunResultPanelProps {
  run: RemediationRun;
  onReview: () => void;
}

export default function RunResultPanel({ run, onReview }: RunResultPanelProps) {
  const status = STATUS_DISPLAY[run.status];
  const rc = run.risk_score !== null ? riskColor(run.risk_score) : null;

  return (
    <div className="rounded-xl p-5 space-y-5" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
      <div className="flex justify-between items-center pb-3 border-b" style={{ borderColor: 'var(--line)' }}>
        <span className="font-mono-ui text-[11px] tracking-widest flex items-center gap-1.5" style={{ color: status.color }}>
          <Code className="w-4 h-4" /> RUN #{run.id} · {status.label}
        </span>
        {rc && (
          <span
            className="px-2.5 py-1 text-xs font-bold rounded-full font-mono-ui"
            style={{ background: rc.bg, border: `1px solid ${rc.border}`, color: rc.text }}
          >
            RISK {run.risk_score}/10
          </span>
        )}
      </div>

      {run.status === 'failed' && (
        <div
          className="p-3 rounded-lg text-xs flex items-start gap-2"
          style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid var(--status-red)', color: 'var(--status-red)' }}
        >
          <XCircle className="w-4 h-4 shrink-0 mt-px" />
          <span>{run.error_message ?? 'The pipeline failed before producing a result.'}</span>
        </div>
      )}

      {run.diagnosis_summary && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">{run.diagnosis_summary}</h3>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--mute)' }}>
            {run.root_cause_analysis}
          </p>
        </div>
      )}

      {run.status === 'diagnosed' && (
        <div
          className="p-3 rounded-lg text-xs flex items-start gap-2"
          style={{ background: 'var(--signal-wash)', border: '1px solid var(--signal-dim)', color: 'var(--signal)' }}
        >
          <Eye className="w-4 h-4 shrink-0 mt-px" />
          <span>
            Read-only inspection — the pipeline stopped after diagnosis. No fix was generated and
            nothing was written to this repository.
          </span>
        </div>
      )}

      {run.git_diff_patch && (
        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
            GENERATED PATCH DIFF{run.fix_attempts > 1 ? ` · attempt ${run.fix_attempts}` : ''}
          </span>
          <pre
            className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-56"
            style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--status-green)' }}
          >
            {run.git_diff_patch}
          </pre>
        </div>
      )}

      {run.test_code && (
        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
            GENERATED TEST SUITE ({run.test_file_name})
          </span>
          <pre
            className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-48"
            style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
          >
            {run.test_code}
          </pre>
        </div>
      )}

      {run.verification_passed === false && run.verification_stderr && (
        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest flex items-center gap-1.5" style={{ color: 'var(--status-red)' }}>
            <Terminal className="w-3.5 h-3.5" /> SANDBOX VERIFICATION FAILED
          </span>
          <pre
            className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-40"
            style={{ background: 'var(--void)', border: '1px solid var(--status-red)', color: 'var(--ink)' }}
          >
            {run.verification_stderr}
          </pre>
        </div>
      )}

      {run.node_trace && run.node_trace.length > 0 && (
        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
            AGENT GRAPH TRACE
          </span>
          <div className="flex flex-wrap items-center gap-1.5 font-mono-ui text-[10px]">
            {run.node_trace.map((step, i) => (
              <span
                key={`${step.node}-${i}`}
                className="px-2 py-1 rounded-md"
                style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--mute)' }}
              >
                {step.node}
                {step.attempt && step.attempt > 1 ? ` #${step.attempt}` : ''} · {step.duration_ms}ms
              </span>
            ))}
          </div>
        </div>
      )}

      {run.status === 'awaiting_approval' && (
        <button
          onClick={onReview}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-semibold rounded-lg"
          style={{ background: 'var(--signal)', color: 'var(--void)' }}
        >
          <GitPullRequest className="w-4 h-4" /> Review &amp; approve fix
        </button>
      )}

      {run.status === 'pr_opened' && run.pr_url && (
        <a
          href={run.pr_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center gap-1.5 py-2.5 text-xs font-semibold rounded-lg underline"
          style={{ background: 'rgba(52,211,153,0.06)', border: '1px solid var(--status-green)', color: 'var(--status-green)' }}
        >
          Pull request opened — view on GitHub <ExternalLink className="w-3.5 h-3.5" />
        </a>
      )}
    </div>
  );
}
