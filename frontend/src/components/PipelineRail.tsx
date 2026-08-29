import { useEffect, useState } from 'react';

export type StageKey = 'diagnose' | 'patch' | 'verify' | 'ship';
export type StageStatus = 'idle' | 'active' | 'done' | 'error';

const STAGES: { key: StageKey; label: string }[] = [
  { key: 'diagnose', label: 'DIAGNOSE' },
  { key: 'patch', label: 'PATCH' },
  { key: 'verify', label: 'VERIFY' },
  { key: 'ship', label: 'SHIP' },
];

const statusColor: Record<StageStatus, string> = {
  idle: 'var(--line)',
  active: 'var(--signal)',
  done: 'var(--status-green)',
  error: 'var(--status-red)',
};

interface PipelineRailProps {
  /** Real status per stage, e.g. from live app state. Omit to use demo mode. */
  statuses?: Partial<Record<StageKey, StageStatus>>;
  /** If true, auto-cycles through stages on a loop (used on the landing page). */
  autoDemo?: boolean;
}

export default function PipelineRail({ statuses, autoDemo = false }: PipelineRailProps) {
  const [demoIndex, setDemoIndex] = useState(0);

  useEffect(() => {
    if (!autoDemo) return;
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) return;

    const interval = setInterval(() => {
      setDemoIndex((i) => (i + 1) % (STAGES.length + 1));
    }, 1400);
    return () => clearInterval(interval);
  }, [autoDemo]);

  const getStatus = (index: number, key: StageKey): StageStatus => {
    if (statuses?.[key]) return statuses[key]!;
    if (!autoDemo) return 'idle';
    if (index < demoIndex) return 'done';
    if (index === demoIndex) return 'active';
    return 'idle';
  };

  return (
    <div
      className="flex items-center w-full"
      role="list"
      aria-label="Remediation pipeline stages"
    >
      {STAGES.map((stage, i) => {
        const status = getStatus(i, stage.key);
        return (
          <div
            key={stage.key}
            className="flex items-center flex-1 last:flex-none"
            role="listitem"
          >
            <div className="flex flex-col items-center gap-2 shrink-0">
              <div
                className="w-3 h-3 rounded-full transition-colors duration-500"
                style={{
                  background: statusColor[status],
                  boxShadow: status === 'active' ? `0 0 12px ${statusColor[status]}` : 'none',
                }}
              />
              <span
                className="font-mono-ui text-[10px] tracking-widest whitespace-nowrap"
                style={{ color: status === 'idle' ? 'var(--mute)' : 'var(--ink)' }}
              >
                {stage.label}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div
                className="h-px flex-1 mx-2 mb-5 transition-colors duration-500"
                style={{
                  background:
                    status === 'done' || status === 'active'
                      ? 'var(--signal-dim)'
                      : 'var(--line)',
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
