import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Bell,
  Building2,
  GitPullRequest,
  FlaskConical,
  Gauge,
  KeyRound,
  Radar,
  ScrollText,
  Timer,
  Webhook,
  Workflow,
} from 'lucide-react';
import PipelineRail from '../components/PipelineRail';
import VideoPlaceholder from '../components/VideoPlaceholder';

const WALKTHROUGH_VIDEO_URL: string | undefined = import.meta.env.VITE_WALKTHROUGH_VIDEO_URL;

const FEATURES = [
  {
    icon: Radar,
    title: 'Multi-agent triage',
    body: 'A LangGraph state graph of diagnose, fix, and test-generation agents produces a root-cause analysis, risk score, and remediation plan. A failed verification loops back for one self-corrected retry.',
  },
  {
    icon: FlaskConical,
    title: 'Sandboxed verification',
    body: 'Every generated patch is written to an ephemeral directory alongside a generated pytest suite and executed in isolation before anything is put in front of you.',
  },
  {
    icon: GitPullRequest,
    title: 'Human-approved pull requests',
    body: 'Fixes stop at a review gate. Nothing is written to GitHub until you approve — then a branch is created, the fix and tests are committed, and a pull request opens with the sandbox proof attached.',
  },
  {
    icon: Timer,
    title: 'Continuous polling',
    body: 'A background worker checks the sandbox repos every 30 seconds — or right now, on demand — and diagnoses new issues without anyone opening a dashboard. Existing issues are ingested as a baseline, not fixed in bulk.',
  },
];

const V2_ITEMS = [
  { icon: KeyRound, title: 'Accounts & GitHub OAuth', body: 'Connect your own repos with a GitHub App instead of a shared platform token.' },
  { icon: Building2, title: 'Multi-tenant isolation', body: 'Per-tenant secrets, usage metering, and billing — bring your own Gemini key.' },
  { icon: Webhook, title: 'Signed webhooks', body: 'Instant, signature-verified issue delivery instead of interval polling.' },
  { icon: Workflow, title: 'Scalable workers', body: 'A real job queue and horizontally scaled workers in place of the single in-process loop.' },
  { icon: ScrollText, title: 'Audit trail & policies', body: 'Full audit logging plus configurable approval rules, like auto-merge below a risk threshold.' },
  { icon: Bell, title: 'Chat & paging integrations', body: 'Slack and PagerDuty alerts, plus a live streaming view of the agent graph as it runs.' },
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
    title: 'Approve & ship',
    body: 'A human reviews the diff and sandbox proof. On approval, a branch is created, the fix and tests are committed, and a pull request opens.',
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
            Sentinel watches your repository, diagnoses failures with a multi-agent
            graph, verifies the fix in an isolated sandbox, and — once you approve
            it — opens the pull request with the sandbox proof attached.
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

      {/* Walkthrough video + free-tier expectations */}
      <section className="max-w-7xl mx-auto px-6 py-20 border-t" style={{ borderColor: 'var(--line)' }}>
        <h2 className="font-mono-ui text-xs tracking-widest mb-2" style={{ color: 'var(--signal)' }}>
          SEE IT WORK
        </h2>
        <p className="text-2xl font-bold mb-10" style={{ color: 'var(--ink)' }}>
          The full loop, start to finish.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
          <div className="lg:col-span-3">
            <VideoPlaceholder videoUrl={WALKTHROUGH_VIDEO_URL} />
          </div>

          <div
            className="lg:col-span-2 rounded-xl p-5 space-y-3"
            style={{ background: 'rgba(251,191,36,0.05)', border: '1px solid var(--status-amber)' }}
          >
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--status-amber)' }}>
              <Gauge className="w-4 h-4" /> Running on free-tier API keys
            </div>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--mute)' }}>
              This demo uses free-tier Gemini and GitHub keys. If several people try it at once you
              may hit a rate limit — the two status badges in the header show live availability, and
              a run that can't proceed will say so instead of failing silently.
            </p>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--mute)' }}>
              That's expected, not a bug. V2 moves to dedicated, per-tenant keys.
            </p>
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

      {/* V2 teaser */}
      <section className="max-w-7xl mx-auto px-6 py-20 border-t" style={{ borderColor: 'var(--line)' }}>
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full font-mono-ui text-[11px] tracking-wide mb-6"
          style={{ background: 'var(--signal-wash)', border: '1px solid var(--signal-dim)', color: 'var(--signal)' }}
        >
          V2 IS COMING
        </div>
        <p className="text-2xl font-bold mb-3 max-w-2xl" style={{ color: 'var(--ink)' }}>
          This is a working demo. A production-grade V2 is in development.
        </p>
        <p className="text-sm leading-relaxed max-w-2xl mb-12" style={{ color: 'var(--mute)' }}>
          The engine you see here — the agent graph, the sandbox, the approval gate — carries over.
          V2 wraps it in everything a system you'd trust with your repositories needs, and it will
          be live.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {V2_ITEMS.map((item) => (
            <div
              key={item.title}
              className="p-5 rounded-xl"
              style={{ background: 'var(--panel)', border: '1px dashed var(--line)' }}
            >
              <item.icon className="w-5 h-5 mb-3" style={{ color: 'var(--mute)' }} />
              <h3 className="text-sm font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
                {item.title}
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--mute)' }}>
                {item.body}
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
            Inject a bug. Watch it fix itself.
          </p>
          <p className="text-sm mb-8" style={{ color: 'var(--mute)' }}>
            Try the full loop on a sandbox repo, or point it at any public repo for a read-only
            diagnosis — nothing is written to GitHub until you approve it.
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
