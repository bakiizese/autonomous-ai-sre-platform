import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { ProviderRateLimit } from '../types/agent';

const POLL_MS = 15000;

interface BadgeState {
  limited: boolean;
  detail: string | null;
}

const UNKNOWN: BadgeState = { limited: false, detail: null };

function toBadgeState(status: ProviderRateLimit): BadgeState {
  if (!status.is_limited) {
    return {
      limited: false,
      detail: status.remaining_calls !== null ? `${status.remaining_calls} left` : null,
    };
  }
  if (!status.limited_until) return { limited: true, detail: null };
  const minutes = Math.max(1, Math.ceil((new Date(status.limited_until).getTime() - Date.now()) / 60000));
  return { limited: true, detail: `resets in ${minutes}m` };
}

function Badge({ label, state }: { label: string; state: BadgeState }) {
  const color = state.limited ? 'var(--status-red)' : 'var(--status-green)';
  return (
    <div
      className="flex items-center gap-2 px-2.5 py-1.5 rounded-md font-mono-ui text-[10px] tracking-wide"
      style={{
        background: 'var(--panel)',
        border: `1px solid ${state.limited ? 'var(--status-red)' : 'var(--line)'}`,
      }}
      title={
        state.limited
          ? `${label} API is rate limited — this demo runs on free-tier keys`
          : `${label} API is available`
      }
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${state.limited ? '' : 'animate-pulse-dot'}`}
        style={{ background: color }}
      />
      <span style={{ color: state.limited ? 'var(--status-red)' : 'var(--mute)' }}>
        {label.toUpperCase()} · {state.limited ? 'RATE LIMITED' : 'OK'}
        {state.detail ? ` · ${state.detail}` : ''}
      </span>
    </div>
  );
}

export default function RateLimitBadges() {
  const [gemini, setGemini] = useState<BadgeState>(UNKNOWN);
  const [github, setGithub] = useState<BadgeState>(UNKNOWN);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const status = await api.getRateLimits();
        if (cancelled) return;
        setGemini(toBadgeState(status.gemini));
        setGithub(toBadgeState(status.github));
      } catch {
        // backend unreachable — leave the last known state rather than flashing an error
      }
    };

    load();
    const interval = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="hidden lg:flex items-center gap-2">
      <Badge label="Gemini" state={gemini} />
      <Badge label="GitHub" state={github} />
    </div>
  );
}
