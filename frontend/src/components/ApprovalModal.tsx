import { useEffect } from 'react';
import { CheckCircle2, GitPullRequest, Terminal, X, XCircle } from 'lucide-react';
import type { RemediationRun } from '../types/agent';

interface ApprovalModalProps {
  run: RemediationRun;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onClose: () => void;
}

export default function ApprovalModal({ run, busy, onApprove, onReject, onClose }: ApprovalModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ background: 'rgba(5,8,12,0.8)' }}
      role="dialog"
      aria-modal="true"
      aria-label="Review proposed fix"
    >
      <div
        className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-xl p-6 space-y-5"
        style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--signal)' }}>
              HUMAN REVIEW REQUIRED
            </p>
            <h2 className="text-lg font-bold mt-1">{run.diagnosis_summary ?? 'Proposed fix'}</h2>
            <p className="text-xs mt-1" style={{ color: 'var(--mute)' }}>
              Nothing has been written to GitHub yet. Approving creates a branch, commits the fix and
              its test, and opens a pull request.
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
            className="p-1.5 rounded-md disabled:opacity-40"
            style={{ color: 'var(--mute)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {run.root_cause_analysis && (
          <p className="text-xs leading-relaxed" style={{ color: 'var(--mute)' }}>
            {run.root_cause_analysis}
          </p>
        )}

        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
            PATCH DIFF · {run.target_file}
          </span>
          <pre
            className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-56"
            style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--status-green)' }}
          >
            {run.git_diff_patch}
          </pre>
        </div>

        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
            GENERATED TEST · {run.test_file_name}
          </span>
          <pre
            className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-48"
            style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
          >
            {run.test_code}
          </pre>
        </div>

        <div className="space-y-2">
          <span className="font-mono-ui text-[11px] tracking-widest flex items-center gap-1.5" style={{ color: 'var(--mute)' }}>
            <Terminal className="w-3.5 h-3.5" /> SANDBOX EXECUTION PROOF
            {run.fix_attempts > 1 && ` · fixed on attempt ${run.fix_attempts}`}
          </span>
          <pre
            className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-32"
            style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
          >
            {run.verification_stdout || 'Pytest verification passed in isolated sandbox.'}
          </pre>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={onApprove}
            disabled={busy}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-semibold rounded-lg disabled:opacity-40"
            style={{ background: 'var(--signal)', color: 'var(--void)' }}
          >
            {busy ? <CheckCircle2 className="w-4 h-4 animate-pulse" /> : <GitPullRequest className="w-4 h-4" />}
            {busy ? 'Working…' : 'Approve & open PR'}
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            className="flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-semibold rounded-lg disabled:opacity-40"
            style={{ background: 'var(--panel-raised)', border: '1px solid var(--status-red)', color: 'var(--status-red)' }}
          >
            <XCircle className="w-4 h-4" /> Reject
          </button>
        </div>
      </div>
    </div>
  );
}
