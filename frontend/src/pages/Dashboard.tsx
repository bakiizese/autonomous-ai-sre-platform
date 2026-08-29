import { useState, useEffect } from 'react';
import { api, getIssueContext } from '../services/api';
import PipelineRail, { type StageKey, type StageStatus } from '../components/PipelineRail';

import type {
  GitHubIssue,
  PipelineResult,
  PRAutomationResponse,
} from '../types/agent';

import {
  Bug,
  Code,
  ExternalLink,
  GitPullRequest,
  Play,
  RefreshCw,
  Terminal,
  XCircle,
  CheckCircle2,
} from 'lucide-react';

function riskColor(score: number) {
  if (score <= 3) return { bg: 'rgba(52,211,153,0.1)', border: 'var(--status-green)', text: 'var(--status-green)' };
  if (score <= 6) return { bg: 'rgba(251,191,36,0.1)', border: 'var(--status-amber)', text: 'var(--status-amber)' };
  return { bg: 'rgba(248,113,113,0.1)', border: 'var(--status-red)', text: 'var(--status-red)' };
}

export default function Dashboard() {
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<number | null>(null);
  const [errorLog, setErrorLog] = useState('');
  const [sourceCode, setSourceCode] = useState('');

  const [loading, setLoading] = useState(false);
  const [prLoading, setPrLoading] = useState(false);
  const [triageResult, setTriageResult] = useState<PipelineResult | null>(null);
  const [prResult, setPrResult] = useState<PRAutomationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [contextLoading, setContextLoading] = useState(false);
  const [contextMethod, setContextMethod] = useState<
    'direct_path' | 'code_search' | 'not_found' | null
  >(null);
  const [resolvedPath, setResolvedPath] = useState<string | null>(null);



  useEffect(() => {
    loadIssues();
  }, []);

  const loadIssues = async () => {
    try {
      const data = await api.fetchIssues();
      setIssues(data.issues);
      if (data.issues.length > 0) {
        handleSelectIssue(data.issues[0]);
      }
    } catch (err: any) {
      console.error('Failed to load GitHub issues:', err);
      setErrorMessage(err.response?.data?.detail || 'Could not load GitHub issues.');
    }
  };

  const handleSelectIssue = async (issue: GitHubIssue) => {
    setSelectedIssue(issue.number);
    setErrorLog(`Issue #${issue.number}: ${issue.title}\n\n${issue.body}`);
    setSourceCode('');
    setTriageResult(null);
    setPrResult(null);
    setContextMethod(null);
    setResolvedPath(null);

    setContextLoading(true);
    try {
      const context = await getIssueContext(issue.number);
      setContextMethod(context.method);
      setResolvedPath(context.resolved_path);
      if (context.source_code) {
        setSourceCode(context.source_code);
      }
    } catch (err) {
      console.error('Failed to auto-resolve source context:', err);
      setContextMethod('not_found');
    } finally {
      setContextLoading(false);
    }
  };

  const handleRunTriage = async () => {
    setLoading(true);
    setErrorMessage('');
    setTriageResult(null);
    setPrResult(null);
    try {
      const result = await api.runTriage(errorLog, sourceCode);
      setTriageResult(result);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Triage engine failure.');
    } finally {
      setLoading(false);
    }
  };

  const handleRemediateAndPR = async () => {
    if (!selectedIssue) return;
    setPrLoading(true);
    setErrorMessage('');
    try {
      const result = await api.remediateAndPR(selectedIssue, errorLog, sourceCode);
      setPrResult(result);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Automated PR creation failed.');
    } finally {
      setPrLoading(false);
    }
  };

  const canRun = errorLog.trim().length > 0 && sourceCode.trim().length > 0;

  // Map local loading state onto the pipeline rail for visual feedback
  const stageStatuses: Partial<Record<StageKey, StageStatus>> = (() => {
    if (loading) return { diagnose: 'active' };
    if (prLoading) {
      if (triageResult) return { diagnose: 'done', patch: 'done', verify: 'active' };
      return { diagnose: 'active' };
    }
    if (prResult) return { diagnose: 'done', patch: 'done', verify: 'done', ship: 'done' };
    if (triageResult) return { diagnose: 'done', patch: 'done' };
    return {};
  })();

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" style={{ color: 'var(--ink)' }}>
      {/* Page header + pipeline rail */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-8 mb-8 border-b" style={{ borderColor: 'var(--line)' }}>
        <div>
          <h1 className="text-xl font-bold tracking-tight">Remediation Console</h1>
          <p className="text-xs mt-1" style={{ color: 'var(--mute)' }}>
            Diagnose, verify, and ship fixes for a selected issue.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="w-64 hidden md:block">
            <PipelineRail statuses={stageStatuses} />
          </div>
          <button
            onClick={loadIssues}
            className="flex items-center gap-2 px-3 py-2 text-xs rounded-md transition-colors font-mono-ui"
            style={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--mute)' }}
          >
            <RefreshCw className="w-3.5 h-3.5" /> RELOAD ISSUES
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left panel */}
        <div className="lg:col-span-5 space-y-6">
          <div className="rounded-xl p-4" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
            <label className="flex items-center gap-2 text-sm font-semibold mb-3">
              <Bug className="w-4 h-4" style={{ color: 'var(--signal)' }} /> GitHub Repository Issues
            </label>
            {issues.length > 0 ? (
              <select
                value={selectedIssue || ''}
                onChange={(e) => {
                  const issue = issues.find((i) => i.number === Number(e.target.value));
                  if (issue) handleSelectIssue(issue);
                }}
                className="w-full rounded-lg p-2.5 text-xs focus:outline-none"
                style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
              >
                {issues.map((issue) => (
                  <option key={issue.number} value={issue.number}>
                    #{issue.number}: {issue.title}
                  </option>
                ))}
              </select>
            ) : (
              <div className="text-xs p-2" style={{ color: 'var(--mute-dim)' }}>
                No open issues found. Open one on GitHub, then reload.
              </div>
            )}
          </div>

          <div className="rounded-xl p-4 space-y-2" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
            <label className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
              ERROR LOG / STACK TRACE
            </label>
            <textarea
              rows={5}
              value={errorLog}
              onChange={(e) => setErrorLog(e.target.value)}
              placeholder="Paste a traceback or error message..."
              className="w-full rounded-lg p-3 font-mono-ui text-xs focus:outline-none"
              style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
            />
          </div>

          <div className="rounded-xl p-4 space-y-2" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
            <div className="flex items-center justify-between">
              <label className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
                SOURCE CODE CONTEXT
              </label>
              {contextLoading && (
                <span className="font-mono-ui text-[10px]" style={{ color: 'var(--mute-dim)' }}>
                  resolving from repo…
                </span>
              )}
              {!contextLoading && contextMethod === 'direct_path' && (
                <span className="font-mono-ui text-[10px]" style={{ color: 'var(--status-green)' }}>
                  auto-resolved · {resolvedPath}
                </span>
              )}
              {!contextLoading && contextMethod === 'code_search' && (
                <span className="font-mono-ui text-[10px]" style={{ color: 'var(--status-green)' }}>
                  found via code search · {resolvedPath}
                </span>
              )}
              {!contextLoading && contextMethod === 'not_found' && (
                <span className="font-mono-ui text-[10px]" style={{ color: 'var(--status-amber)' }}>
                  no match found — paste manually
                </span>
              )}
            </div>
            <textarea
              rows={5}
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
              placeholder="Paste the relevant function or file..."
              className="w-full rounded-lg p-3 font-mono-ui text-xs focus:outline-none"
              style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleRunTriage}
              disabled={loading || prLoading || !canRun}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 font-medium text-xs rounded-lg transition-opacity disabled:opacity-40"
              style={{ background: 'var(--signal)', color: 'var(--void)' }}
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run Multi-Agent Triage
            </button>

            <button
              onClick={handleRemediateAndPR}
              disabled={loading || prLoading || !selectedIssue || !canRun}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 font-medium text-xs rounded-lg transition-opacity disabled:opacity-40"
              style={{ background: 'var(--panel-raised)', border: '1px solid var(--signal-dim)', color: 'var(--ink)' }}
            >
              {prLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <GitPullRequest className="w-4 h-4" />}
              Full Loop &amp; Open PR
            </button>
          </div>

          {!canRun && (
            <p className="text-[11px] font-mono-ui" style={{ color: 'var(--mute-dim)' }}>
              Both fields are required to run triage.
            </p>
          )}

          {errorMessage && (
            <div
              className="p-3 rounded-lg text-xs flex items-center gap-2"
              style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid var(--status-red)', color: 'var(--status-red)' }}
            >
              <XCircle className="w-4 h-4 shrink-0" /> {errorMessage}
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="lg:col-span-7 space-y-6">
          {triageResult ? (
            <div className="rounded-xl p-5 space-y-5" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
              <div className="flex justify-between items-center pb-3 border-b" style={{ borderColor: 'var(--line)' }}>
                <span className="font-mono-ui text-[11px] tracking-widest flex items-center gap-1.5" style={{ color: 'var(--signal)' }}>
                  <Code className="w-4 h-4" /> DIAGNOSIS &amp; REMEDIATION
                </span>
                {(() => {
                  const rc = riskColor(triageResult.diagnosis.risk_score);
                  return (
                    <span
                      className="px-2.5 py-1 text-xs font-bold rounded-full font-mono-ui"
                      style={{ background: rc.bg, border: `1px solid ${rc.border}`, color: rc.text }}
                    >
                      RISK {triageResult.diagnosis.risk_score}/10
                    </span>
                  );
                })()}
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-semibold">{triageResult.diagnosis.summary}</h3>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--mute)' }}>
                  {triageResult.diagnosis.root_cause_analysis}
                </p>
              </div>

              <div className="space-y-2">
                <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
                  GENERATED PATCH DIFF
                </span>
                <pre
                  className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto"
                  style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--status-green)' }}
                >
                  {triageResult.remediation.git_diff_patch}
                </pre>
              </div>

              <div className="space-y-2">
                <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
                  GENERATED TEST SUITE ({triageResult.test_generation.test_file_name})
                </span>
                <pre
                  className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto max-h-48"
                  style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
                >
                  {triageResult.test_generation.test_code}
                </pre>
              </div>
            </div>
          ) : (
            <div
              className="rounded-xl p-12 text-center text-xs"
              style={{ background: 'var(--panel)', border: '1px dashed var(--line)', color: 'var(--mute-dim)' }}
            >
              Select an issue and run triage to see the diagnosis and generated patch here.
            </div>
          )}

          {prResult && (
            <div
              className="rounded-xl p-5 space-y-4"
              style={{ background: 'rgba(52,211,153,0.06)', border: '1px solid var(--status-green)' }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-sm" style={{ color: 'var(--status-green)' }}>
                  <CheckCircle2 className="w-5 h-5" /> Pull request created
                </div>
                <a
                  href={prResult.pr_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-xs font-semibold underline"
                  style={{ color: 'var(--status-green)' }}
                >
                  View on GitHub <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>

              <div className="space-y-2">
                <span className="font-mono-ui text-[11px] tracking-widest flex items-center gap-1.5" style={{ color: 'var(--mute)' }}>
                  <Terminal className="w-3.5 h-3.5" /> SANDBOX EXECUTION PROOF
                </span>
                <pre
                  className="p-3 rounded-lg font-mono-ui text-xs overflow-x-auto"
                  style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
                >
                  {prResult.verification.stdout || 'Pytest verification passed in isolated sandbox.'}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
