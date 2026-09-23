import { useState } from 'react';
import type { FormEvent } from 'react';
import { Bell, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';

interface EmailSubscribeFormProps {
  repoId: number;
}

export default function EmailSubscribeForm({ repoId }: EmailSubscribeFormProps) {
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setState('loading');
    setMessage('');
    try {
      await api.subscribe(repoId, email.trim());
      setState('done');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      setMessage(typeof detail === 'string' ? detail : 'Could not subscribe — check the address and try again.');
      setState('error');
    }
  };

  return (
    <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}>
      <label htmlFor="alert-email" className="flex items-center gap-2 text-sm font-semibold">
        <Bell className="w-4 h-4" style={{ color: 'var(--signal)' }} /> Critical-risk email alerts
      </label>
      <p className="text-[11px] leading-relaxed" style={{ color: 'var(--mute)' }}>
        Get an email right away whenever a diagnosis for this repo scores above 8/10. No account
        needed — unsubscribe with one click from any alert.
      </p>

      {state === 'done' ? (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--status-green)' }}>
          <CheckCircle2 className="w-4 h-4" /> Subscribed — alerts will go to {email}.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            id="alert-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="flex-1 min-w-0 rounded-lg p-2.5 text-xs focus:outline-none"
            style={{ background: 'var(--void)', border: '1px solid var(--line)', color: 'var(--ink)' }}
          />
          <button
            type="submit"
            disabled={state === 'loading' || email.trim().length === 0}
            className="px-4 py-2 text-xs font-semibold rounded-lg transition-opacity disabled:opacity-40"
            style={{ background: 'var(--signal)', color: 'var(--void)' }}
          >
            {state === 'loading' ? 'Subscribing…' : 'Subscribe'}
          </button>
        </form>
      )}

      {state === 'error' && (
        <p className="text-[11px]" style={{ color: 'var(--status-red)' }}>
          {message}
        </p>
      )}
    </div>
  );
}
