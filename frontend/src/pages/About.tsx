const STACK = [
  { layer: 'Triage engine', detail: 'google-genai SDK · gemini-2.5-flash · structured output via Pydantic' },
  { layer: 'Sandbox', detail: 'tempfile.TemporaryDirectory · subprocess pytest · timeout-enforced' },
  { layer: 'GitHub integration', detail: 'httpx · REST API · branch, commit, and pull request automation' },
  { layer: 'API', detail: 'FastAPI · Python 3.12 · single-pass prompt to minimize latency and rate-limit exposure' },
  { layer: 'Frontend', detail: 'React 19 · TypeScript · Vite · Tailwind CSS v4' },
];

const PIPELINE = [
  { name: 'Issue', detail: 'GitHub issue or pasted log' },
  { name: 'Triage engine', detail: 'diagnosis + patch + tests' },
  { name: 'Sandbox', detail: 'isolated pytest run' },
  { name: 'GitHub', detail: 'branch · commit · PR' },
];

export default function About() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-20">
      <h1 className="font-mono-ui text-xs tracking-widest mb-3" style={{ color: 'var(--signal)' }}>
        ARCHITECTURE
      </h1>
      <p className="text-3xl font-bold max-w-2xl leading-tight" style={{ color: 'var(--ink)' }}>
        A closed loop from error log to reviewed pull request.
      </p>
      <p className="mt-5 max-w-2xl text-sm leading-relaxed" style={{ color: 'var(--mute)' }}>
        Sentinel doesn't guess and merge. Every fix it proposes has already run against a
        generated test suite in an isolated environment — the pull request it opens carries
        that proof, so a human reviews the same evidence the system did.
      </p>

      {/* Flow diagram */}
      <div
        className="mt-14 rounded-xl p-8 overflow-x-auto"
        style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
      >
        <div className="flex items-center gap-4 min-w-max">
          {PIPELINE.map((step, i) => (
            <div key={step.name} className="flex items-center gap-4">
              <div
                className="px-5 py-4 rounded-lg text-center min-w-[140px]"
                style={{ background: 'var(--panel-raised)', border: '1px solid var(--line)' }}
              >
                <div className="font-mono-ui text-xs tracking-wide mb-1" style={{ color: 'var(--signal)' }}>
                  {step.name.toUpperCase()}
                </div>
                <div className="text-[11px]" style={{ color: 'var(--mute)' }}>
                  {step.detail}
                </div>
              </div>
              {i < PIPELINE.length - 1 && (
                <div className="w-8 h-px shrink-0" style={{ background: 'var(--line)' }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Stack table */}
      <div className="mt-16">
        <h2 className="font-mono-ui text-xs tracking-widest mb-6" style={{ color: 'var(--signal)' }}>
          STACK
        </h2>
        <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--line)' }}>
          {STACK.map((row, i) => (
            <div
              key={row.layer}
              className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-6 px-5 py-4"
              style={{
                background: i % 2 === 0 ? 'var(--panel)' : 'var(--void)',
                borderTop: i === 0 ? 'none' : '1px solid var(--line)',
              }}
            >
              <span
                className="font-mono-ui text-xs tracking-wide w-44 shrink-0"
                style={{ color: 'var(--ink)' }}
              >
                {row.layer}
              </span>
              <span className="font-mono-ui text-xs" style={{ color: 'var(--mute)' }}>
                {row.detail}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Principle */}
      <div
        className="mt-16 p-8 rounded-xl"
        style={{ background: 'var(--signal-wash)', border: '1px solid var(--signal-dim)' }}
      >
        <p className="text-sm leading-relaxed" style={{ color: 'var(--ink)' }}>
          <span className="font-semibold">Nothing merges unreviewed.</span> Sentinel opens a
          pull request; it does not have permission to approve or merge one. The sandbox log,
          risk score, and root-cause analysis travel with the PR so the reviewing engineer has
          the same context the system used to write the fix.
        </p>
      </div>
    </div>
  );
}
