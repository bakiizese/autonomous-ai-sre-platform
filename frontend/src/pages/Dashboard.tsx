import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../services/api';
import PipelineRail from '../components/PipelineRail';
import ApprovalModal from '../components/ApprovalModal';
import EmailSubscribeForm from '../components/EmailSubscribeForm';
import RunResultPanel from '../components/RunResultPanel';
import { extractError, railStatusesForRun, riskColor, STATUS_DISPLAY } from '../lib/runStatus';
import type { IssueRecord, PipelineResult, RemediationRun, Repo } from '../types/agent';

import {
  Bug,
  Eye,
  Link2,
  Play,
  RefreshCw,
  Radar,
  Sparkles,
  Timer,
  Wrench,
  XCircle,
} from 'lucide-react';

const AUTO_REFRESH_MS = 10000;
const CHECK_NOW_SETTLE_MS = 3000;

type IssueScope = 'all' | 'baseline' | 'live';

export default function Dashboard() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(null);
  const [connectInput, setConnectInput] = useState('');
  const [connecting, setConnecting] = useState(false);

  const [issues, setIssues] = useState<IssueRecord[]>([]);
  const [scope, setScope] = useState<IssueScope>('all');
  const [pendingRuns, setPendingRuns] = useState<RemediationRun[]>([]);
  const [reloadTick, setReloadTick] = useState(0);

  const [activeRun, setActiveRun] = useState<RemediationRun | null>(null);
  const [triagingIssue, setTriagingIssue] = useState<number | null>(null);
  const [injecting, setInjecting] = useState(false);
  const [checkingNow, setCheckingNow] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [reviewRun, setReviewRun] = useState<RemediationRun | null>(null);
  const [approvalBusy, setApprovalBusy] = useState(false);

  const [errorMessage, setErrorMessage] = useState('');

  const [scratchLog, setScratchLog] = useState('');
  const [scratchSource, setScratchSource] = useState('');
  const [scratchLoading, setScratchLoading] = useState(false);
  const [scratchResult, setScratchResult] = useState<PipelineResult | null>(null);

  const selectedRepo = repos.find((r) => r.id === selectedRepoId) ?? null;
  const isReadOnly = selectedRepo?.repo_type === 'inspected';
  const reload = () => setReloadTick((t) => t + 1);

  useEffect(() => {
    let cancelled = false;
    const loadRepos = async () => {
      try {
        const list = await api.listRepos();
        if (cancelled) return;
        setRepos(list);
        setSelectedRepoId((current) => current ?? (list.find((r) => r.repo_type === 'sandbox') ?? list[0])?.id ?? null);
      } catch (err) {
        if (!cancelled) setErrorMessage(extractError(err, 'Could not reach the backend.'));
      }
    };
    loadRepos();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedRepoId === null) return;
    let cancelled = false;
    const load = async () => {
      try {
        const [issueList, pending] = await Promise.all([
          api.listIssues(selectedRepoId),
          api.listRuns(selectedRepoId, 'awaiting_approval'),
        ]);
        if (cancelled) return;
        setIssues(issueList);
        setPendingRuns(pending);
      } catch (err) {
        if (!cancelled) setErrorMessage(extractError(err, 'Could not load issues for this repo.'));
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [selectedRepoId, reloadTick]);

  // The backend poller runs on its own interval — refresh so new issues and
  // runs it picks up show without anyone clicking anything.
  useEffect(() => {
    const id = setInterval(() => setReloadTick((t) => t + 1), AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  const handleSelectRepo = (id: number) => {
    setSelectedRepoId(id);
    setActiveRun(null);
    setIssues([]);
    setPendingRuns([]);
    setErrorMessage('');
  };

  const handleConnect = async (e: FormEvent) => {
    e.preventDefault();
    setConnecting(true);
    setErrorMessage('');
    try {
      const repo = await api.connectRepo(connectInput.trim());
      setRepos(await api.listRepos());
      setConnectInput('');
      handleSelectRepo(repo.id);
    } catch (err) {
      setErrorMessage(extractError(err, 'Could not connect that repository.'));
    } finally {
      setConnecting(false);
    }
  };

  const handleTriage = async (issue: IssueRecord) => {
    if (selectedRepoId === null) return;
    setTriagingIssue(issue.issue_number);
    setErrorMessage('');
    try {
      setActiveRun(await api.triageIssue(selectedRepoId, issue.issue_number));
      reload();
    } catch (err) {
      setErrorMessage(extractError(err, 'Triage failed.'));
    } finally {
      setTriagingIssue(null);
    }
  };

  const handleInjectBug = async () => {
    if (selectedRepoId === null) return;
    setInjecting(true);
    setErrorMessage('');
    try {
      setActiveRun(await api.injectBug(selectedRepoId));
      reload();
    } catch (err) {
      setErrorMessage(extractError(err, 'Could not inject a demo bug.'));
    } finally {
      setInjecting(false);
    }
  };

  const handleCheckNow = async () => {
    setCheckingNow(true);
    setErrorMessage('');
    try {
      await api.triggerPollNow();
      setTimeout(() => {
        reload();
        setCheckingNow(false);
      }, CHECK_NOW_SETTLE_MS);
    } catch (err) {
      setErrorMessage(extractError(err, 'Could not trigger a poll.'));
      setCheckingNow(false);
    }
  };

  const handleRefreshIssues = async () => {
    if (selectedRepoId === null) return;
    setRefreshing(true);
    setErrorMessage('');
    try {
      await api.refreshIssues(selectedRepoId);
      reload();
    } catch (err) {
      setErrorMessage(extractError(err, 'Could not refresh issues from GitHub.'));
    } finally {
      setRefreshing(false);
    }
  };

  const handleApprove = async () => {
    if (!reviewRun) return;
    setApprovalBusy(true);
    setErrorMessage('');
    try {
      setActiveRun(await api.approveRun(reviewRun.id));
      setReviewRun(null);
      reload();
    } catch (err) {
      setErrorMessage(extractError(err, 'Approval failed.'));
    } finally {
      setApprovalBusy(false);
    }
  };

  const handleReject = async () => {
    if (!reviewRun) return;
    setApprovalBusy(true);
    setErrorMessage('');
    try {
      setActiveRun(await api.rejectRun(reviewRun.id));
      setReviewRun(null);
      reload();
    } catch (err) {
      setErrorMessage(extractError(err, 'Reject failed.'));
    } finally {
      setApprovalBusy(false);
    }
  };

  const handleScratchTriage = async () => {
    setScratchLoading(true);
    setErrorMessage('');
    setScratchResult(null);
    try {
      setScratchResult(await api.runTriage(scratchLog, scratchSource));
    } catch (err) {
      setErrorMessage(extractError(err, 'Triage engine failure.'));
    } finally {
      setScratchLoading(false);
    }
  };

  const visibleIssues = issues.filter((i) => {
    if (scope === 'baseline') return i.origin === 'baseline';
    if (scope === 'live') return i.origin !== 'baseline';
    return true;
  });

  const busy = triagingIssue !== null || injecting;
  const railStatuses = railStatusesForRun(activeRun, busy);

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" style={{ color: 'var(--ink)' }}>
      {/* Header */}
      <div
        className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-8 mb-6 border-b"
        style={{ borderColor: 'var(--line)' }}
      >
        <div>
          <h1 className="text-xl font-bold tracking-tight">Remediation Console</h1>
          <p className="text-xs mt-1" style={{ color: 'var(--mute)' }}>
            Watch issues get diagnosed and fixed, then approve what ships.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="w-64 hidden md:block">
            <PipelineRail statuses={railStatuses} />
          </div>
          <button
            onClick={handleCheckNow}
            disabled={checkingNow}
            className="flex items-center gap-2 px-3 py-2 text-xs rounded-md font-mono-ui disabled:opacity-50"
            style={{ background: 'var(--panel)', border: '1px solid var(--signal-dim)', color: 'var(--signal)' }}
            title="Ask the poller to check the sandbox repos for new issues right now instead of waiting for its next interval"
          >
            <Timer className={`w-3.5 h-3.5 ${checkingNow ? 'animate-pulse' : ''}`} />
            {checkingNow ? 'CHECKING…' : 'CHECK NOW'}
          </button>
        </div>
      </div>

      {/* Repo selector + connect */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="rounded-xl p-4" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
          <label htmlFor="repo-select" className="flex items-center gap-2 text-sm font-semibold mb-3">
            <Radar className="w-4 h-4" style={{ color: 'var(--signal)' }} /> Repository
          </label>
          {repos.length > 0 ? (
            <select
              id="repo-select"
              value={selectedRepoId ?? ''}
              onChange={(e) => handleSelectRepo(Number(e.target.value))}
              className="w-full rounded-lg p-2.5 text-xs focus:outline-none"
              style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
            >
              <optgroup label="Sandbox — full loop, writable">
                {repos
                  .filter((r) => r.repo_type === 'sandbox')
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.full_name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Inspecting — read-only">
                {repos
                  .filter((r) => r.repo_type === 'inspected')
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.full_name}
                    </option>
                  ))}
              </optgroup>
            </select>
          ) : (
            <p className="text-xs" style={{ color: 'var(--mute-dim)' }}>
              No repositories yet — connect one to the right.
            </p>
          )}
        </div>

        <form
          onSubmit={handleConnect}
          className="rounded-xl p-4 space-y-3"
          style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
        >
          <label htmlFor="connect-repo" className="flex items-center gap-2 text-sm font-semibold">
            <Link2 className="w-4 h-4" style={{ color: 'var(--signal)' }} /> Inspect a public repo
          </label>
          <div className="flex gap-2">
            <input
              id="connect-repo"
              value={connectInput}
              onChange={(e) => setConnectInput(e.target.value)}
              placeholder="owner/repo"
              className="flex-1 min-w-0 rounded-lg p-2.5 text-xs font-mono-ui focus:outline-none"
              style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
            />
            <button
              type="submit"
              disabled={connecting || connectInput.trim().length === 0}
              className="px-4 py-2 text-xs font-semibold rounded-lg disabled:opacity-40"
              style={{ background: 'var(--signal)', color: 'var(--void)' }}
            >
              {connecting ? 'Connecting…' : 'Connect'}
            </button>
          </div>
          <p className="text-[11px]" style={{ color: 'var(--mute-dim)' }}>
            Read-only: existing open issues are imported as a baseline and can be diagnosed, but
            nothing is ever written to a repo you connect.
          </p>
        </form>
      </div>

      {isReadOnly && (
        <div
          className="mb-6 p-3 rounded-lg text-xs flex items-center gap-2"
          style={{ background: 'var(--signal-wash)', border: '1px solid var(--signal-dim)', color: 'var(--signal)' }}
        >
          <Eye className="w-4 h-4 shrink-0" />
          READ-ONLY INSPECTION — this repo can be diagnosed and risk-scored, but no fixes are
          generated and no pull requests will be opened.
        </div>
      )}

      {errorMessage && (
        <div
          className="mb-6 p-3 rounded-lg text-xs flex items-center gap-2"
          style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid var(--status-red)', color: 'var(--status-red)' }}
        >
          <XCircle className="w-4 h-4 shrink-0" /> {errorMessage}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left column: issues */}
        <div className="lg:col-span-5 space-y-6">
          <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-semibold">
                <Bug className="w-4 h-4" style={{ color: 'var(--signal)' }} /> Issues
              </span>
              <div className="flex items-center gap-1 font-mono-ui text-[10px]">
                {(['all', 'baseline', 'live'] as IssueScope[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    className="px-2 py-1 rounded-md"
                    style={{
                      background: scope === s ? 'var(--panel-raised)' : 'transparent',
                      color: scope === s ? 'var(--ink)' : 'var(--mute)',
                    }}
                  >
                    {s.toUpperCase()}
                  </button>
                ))}
                <button
                  onClick={handleRefreshIssues}
                  disabled={refreshing || selectedRepoId === null}
                  aria-label="Re-scan open issues on GitHub"
                  title="Re-scan open issues on GitHub (never triggers a fix)"
                  className="p-1.5 rounded-md disabled:opacity-40"
                  style={{ color: 'var(--mute)' }}
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>

            {visibleIssues.length === 0 ? (
              <p className="text-xs p-2" style={{ color: 'var(--mute-dim)' }}>
                {selectedRepoId === null
                  ? 'Select or connect a repository to see its issues.'
                  : 'No issues in this view.'}
              </p>
            ) : (
              <ul className="space-y-2 max-h-105 overflow-y-auto pr-1">
                {visibleIssues.map((issue) => {
                  const status = issue.latest_run_status ? STATUS_DISPLAY[issue.latest_run_status] : null;
                  const rc = issue.latest_run_risk_score !== null ? riskColor(issue.latest_run_risk_score) : null;
                  return (
                    <li
                      key={issue.id}
                      className="rounded-lg p-3 space-y-2"
                      style={{ background: 'var(--void)', border: '1px solid var(--line)' }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-medium leading-snug">
                          #{issue.issue_number} {issue.title}
                        </span>
                        <span className="font-mono-ui text-[9px] tracking-widest shrink-0" style={{ color: 'var(--mute-dim)' }}>
                          {issue.origin === 'baseline' ? 'BASELINE' : issue.origin === 'demo_injected' ? 'DEMO' : 'LIVE'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 font-mono-ui text-[10px]">
                          {status ? (
                            <span style={{ color: status.color }}>{status.label}</span>
                          ) : (
                            <span style={{ color: 'var(--mute-dim)' }}>NOT TRIAGED</span>
                          )}
                          {rc && (
                            <span style={{ color: rc.text }}>RISK {issue.latest_run_risk_score}/10</span>
                          )}
                        </div>
                        <button
                          onClick={() => handleTriage(issue)}
                          disabled={busy}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-semibold rounded-md disabled:opacity-40"
                          style={{ background: 'var(--panel-raised)', border: '1px solid var(--signal-dim)', color: 'var(--ink)' }}
                        >
                          {triagingIssue === issue.issue_number ? (
                            <RefreshCw className="w-3 h-3 animate-spin" />
                          ) : (
                            <Play className="w-3 h-3" />
                          )}
                          {issue.latest_remediation_run_id ? 'Re-run' : 'Run triage'}
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            {selectedRepo?.repo_type === 'sandbox' && (
              <button
                onClick={handleInjectBug}
                disabled={busy}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-semibold rounded-lg disabled:opacity-40"
                style={{ background: 'var(--signal)', color: 'var(--void)' }}
                title="Opens a real bug report on the sandbox repo and runs the full loop on it"
              >
                {injecting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {injecting ? 'Injecting & diagnosing…' : 'Inject a bug & watch it get fixed'}
              </button>
            )}
          </div>

          {selectedRepoId !== null && <EmailSubscribeForm repoId={selectedRepoId} />}

          <details className="rounded-xl p-4" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
            <summary className="flex items-center gap-2 text-sm font-semibold cursor-pointer">
              <Wrench className="w-4 h-4" style={{ color: 'var(--signal)' }} /> Advanced · scratchpad
            </summary>
            <div className="mt-4 space-y-3">
              <p className="text-[11px]" style={{ color: 'var(--mute)' }}>
                Paste an error and some source directly — runs the agent graph without touching any
                repository or saving anything.
              </p>
              <textarea
                rows={4}
                value={scratchLog}
                onChange={(e) => setScratchLog(e.target.value)}
                placeholder="Error log / stack trace…"
                className="w-full rounded-lg p-3 font-mono-ui text-xs focus:outline-none"
                style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
              />
              <textarea
                rows={4}
                value={scratchSource}
                onChange={(e) => setScratchSource(e.target.value)}
                placeholder="Relevant source code…"
                className="w-full rounded-lg p-3 font-mono-ui text-xs focus:outline-none"
                style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
              />
              <button
                onClick={handleScratchTriage}
                disabled={scratchLoading || scratchLog.trim().length === 0 || scratchSource.trim().length === 0}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-semibold rounded-lg disabled:opacity-40"
                style={{ background: 'var(--panel-raised)', border: '1px solid var(--signal-dim)', color: 'var(--ink)' }}
              >
                {scratchLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                Run scratchpad triage
              </button>
              {scratchResult && (
                <div className="space-y-2 pt-2">
                  <p className="text-xs font-semibold">
                    {scratchResult.diagnosis.summary}{' '}
                    <span className="font-mono-ui" style={{ color: riskColor(scratchResult.diagnosis.risk_score).text }}>
                      · RISK {scratchResult.diagnosis.risk_score}/10
                    </span>
                  </p>
                  <pre
                    className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-48"
                    style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--status-green)' }}
                  >
                    {scratchResult.remediation.git_diff_patch}
                  </pre>
                </div>
              )}
            </div>
          </details>
        </div>

        {/* Right column: approval queue + result */}
        <div className="lg:col-span-7 space-y-6">
          {pendingRuns.length > 0 && (
            <div
              className="rounded-xl p-4 space-y-3"
              style={{ background: 'rgba(251,191,36,0.05)', border: '1px solid var(--status-amber)' }}
            >
              <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--status-amber)' }}>
                AWAITING YOUR APPROVAL · {pendingRuns.length}
              </span>
              <ul className="space-y-2">
                {pendingRuns.map((run) => {
                  const rc = run.risk_score !== null ? riskColor(run.risk_score) : null;
                  return (
                    <li
                      key={run.id}
                      className="flex items-center justify-between gap-3 rounded-lg p-3"
                      style={{ background: 'var(--void)', border: '1px solid var(--line)' }}
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-medium truncate">{run.diagnosis_summary ?? `Run #${run.id}`}</p>
                        <p className="font-mono-ui text-[10px] mt-0.5" style={{ color: rc?.text ?? 'var(--mute)' }}>
                          {run.target_file} · RISK {run.risk_score}/10
                        </p>
                      </div>
                      <button
                        onClick={() => setReviewRun(run)}
                        className="shrink-0 px-3 py-1.5 text-[11px] font-semibold rounded-md"
                        style={{ background: 'var(--signal)', color: 'var(--void)' }}
                      >
                        Review fix
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {activeRun ? (
            <RunResultPanel run={activeRun} onReview={() => setReviewRun(activeRun)} />
          ) : (
            <div
              className="rounded-xl p-12 text-center text-xs"
              style={{ background: 'var(--panel)', border: '1px dashed var(--line)', color: 'var(--mute-dim)' }}
            >
              {selectedRepo?.repo_type === 'sandbox'
                ? 'Run triage on an issue — or inject a demo bug — to watch the agent graph work. Fixes wait here for your approval before anything is written to GitHub.'
                : 'Run triage on any issue to see its diagnosis and risk score.'}
            </div>
          )}
        </div>
      </div>

      {reviewRun && (
        <ApprovalModal
          run={reviewRun}
          busy={approvalBusy}
          onApprove={handleApprove}
          onReject={handleReject}
          onClose={() => setReviewRun(null)}
        />
      )}
    </div>
  );
}
