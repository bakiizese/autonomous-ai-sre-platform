import { Link } from 'react-router-dom';
import {
  ArrowRight,
  GitPullRequest,
  FlaskConical,
  Radar,
  Timer,
} from 'lucide-react';
import PipelineRail from '../components/PipelineRail';

const FEATURES = [
  {
    icon: Radar,
    title: 'Multi-agent triage',
    body: 'A single structured pass over your error log and source context produces a root-cause analysis, risk score, and remediation plan — no chained calls, no rate-limit churn.',
  },
  {
    icon: FlaskConical,
    title: 'Sandboxed verification',
    body: 'Every generated patch is written to an ephemeral directory alongside a generated pytest suite and executed in isolation before anything touches your repository.',
  },
  {
    icon: GitPullRequest,
    title: 'Automated pull requests',
    body: 'Verified fixes are committed to a new branch with the generated tests, and a pull request is opened with the diagnosis and sandbox proof attached.',
  },
  {
    icon: Timer,
    title: 'Continuous polling',
    body: 'A background worker checks your repository for new issues on an interval and can trigger the full remediation loop without anyone opening a dashboard.',
  },
];

const STEPS = [
  {
    n: '01',
    title: 'Detect',
    body: 'An issue is opened on GitHub, or a log is pasted directly into the dashboard.',
  },
  {
    n: '02',
    title: 'Diagnose',
    body: 'The triage engine reads the error and source context and identifies the root cause.',
  },
  {
    n: '03',
    title: 'Verify',
    body: 'The generated fix and its test suite run inside an isolated sandbox before anything is trusted.',
  },
  {
    n: '04',
    title: 'Ship',
    body: 'A branch is created, the fix and tests are committed, and a pull request is opened with proof attached.',
  },
];

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid pointer-events-none" />
        <div className="relative max-w-7xl mx-auto px-6 pt-20 pb-24">
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full font-mono-ui text-[11px] tracking-wide mb-8"
            style={{
              background: 'var(--signal-wash)',
              border: '1px solid var(--signal-dim)',
              color: 'var(--signal)',
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full animate-pulse-dot" style={{ background: 'var(--signal)' }} />
            AUTONOMOUS REMEDIATION ENGINE
          </div>

          <h1
            className="text-5xl sm:text-6xl font-extrabold tracking-tight max-w-3xl leading-[1.05]"
            style={{ color: 'var(--ink)' }}
          >
            Issues Get Diagnosed, Patched, And Shipped {' '}
            <span style={{ color: 'var(--signal)' }}>before you finish your coffee.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed" style={{ color: 'var(--mute)' }}>
            Sentinel watches your repository, diagnoses failures with a structured
            multi-agent pass, verifies the fix in an isolated sandbox, and opens the
            pull request — with the sandbox proof attached.
          </p>

          <div className="mt-9 flex items-center gap-4">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-sm font-semibold transition-transform hover:-translate-y-0.5"
              style={{ background: 'var(--signal)', color: 'var(--void)' }}
            >
              Open Dashboard <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/about"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-sm font-medium transition-colors"
              style={{ border: '1px solid var(--line)', color: 'var(--ink)' }}
            >
              How it works
            </Link>
          </div>

          {/* Signature element */}
          <div
            className="mt-16 max-w-2xl rounded-xl p-6"
            style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
          >
            <div className="flex items-center justify-between mb-6">
              <span className="font-mono-ui text-[11px] tracking-widest" style={{ color: 'var(--mute)' }}>
                LIVE PIPELINE
              </span>
              <span className="font-mono-ui text-[11px]" style={{ color: 'var(--mute-dim)' }}>
                #482 · math_helpers.py
              </span>
            </div>
            <PipelineRail autoDemo />
          </div>
        </div>
      </section>

      {/* How it works — a real sequence, numbering earns its place */}
      <section className="max-w-7xl mx-auto px-6 py-20 border-t" style={{ borderColor: 'var(--line)' }}>
        <h2 className="font-mono-ui text-xs tracking-widest mb-2" style={{ color: 'var(--signal)' }}>
          THE LOOP
        </h2>
        <p className="text-2xl font-bold mb-12" style={{ color: 'var(--ink)' }}>
          One fixed sequence, every time.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {STEPS.map((step, i) => (
            <div key={step.n} className="relative">
              <div
                className="font-mono-ui text-3xl font-bold mb-4"
                style={{ color: 'var(--panel-raised)', WebkitTextStroke: '1px var(--line)' }}
              >
                {step.n}
              </div>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--ink)' }}>
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--mute)' }}>
                {step.body}
              </p>
              {i < STEPS.length - 1 && (
                <div
                  className="hidden md:block absolute top-3 -right-3 w-6 h-px"
                  style={{ background: 'var(--line)' }}
                />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Feature grid */}
      <section className="max-w-7xl mx-auto px-6 py-20 border-t" style={{ borderColor: 'var(--line)' }}>
        <h2 className="font-mono-ui text-xs tracking-widest mb-2" style={{ color: 'var(--signal)' }}>
          CAPABILITIES
        </h2>
        <p className="text-2xl font-bold mb-12" style={{ color: 'var(--ink)' }}>
          Built to be trusted with write access.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="p-6 rounded-xl transition-colors hover:border-[var(--signal-dim)]"
              style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
            >
              <f.icon className="w-5 h-5 mb-4" style={{ color: 'var(--signal)' }} />
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--ink)' }}>
                {f.title}
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--mute)' }}>
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div
          className="rounded-2xl p-12 text-center"
          style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
        >
          <p className="text-2xl font-bold mb-3" style={{ color: 'var(--ink)' }}>
            Connect a repository. Watch it fix itself.
          </p>
          <p className="text-sm mb-8" style={{ color: 'var(--mute)' }}>
            Every run leaves a sandbox log and a pull request — nothing merges unreviewed.
          </p>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-sm font-semibold"
            style={{ background: 'var(--signal)', color: 'var(--void)' }}
          >
            Open Dashboard <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
