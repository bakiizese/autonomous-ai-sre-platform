import { NavLink, Outlet } from 'react-router-dom';
import { ShieldHalf } from 'lucide-react';

const navItems: { to: string; label: string; end?: boolean }[] = [
  { to: '/', label: 'Home', end: true },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/about', label: 'About' },
];

export default function Layout() {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--void)', color: 'var(--ink)' }}
    >
      <header
        className="sticky top-0 z-50 border-b backdrop-blur"
        style={{ borderColor: 'var(--line)', background: 'rgba(10,14,19,0.85)' }}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <NavLink to="/" className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-md flex items-center justify-center"
              style={{ background: 'var(--panel-raised)', border: '1px solid var(--line)' }}
            >
              <ShieldHalf className="w-4 h-4" style={{ color: 'var(--signal)' }} />
            </div>
            <span className="font-mono-ui text-sm tracking-widest">
              SENTINEL<span style={{ color: 'var(--signal)' }}>.SRE</span>
            </span>
          </NavLink>

          <nav className="hidden md:flex items-center gap-1 font-mono-ui text-xs">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className="px-3.5 py-2 rounded-md transition-colors tracking-wide"
                style={({ isActive }) => ({
                  color: isActive ? 'var(--ink)' : 'var(--mute)',
                  background: isActive ? 'var(--panel-raised)' : 'transparent',
                })}
              >
                {item.label.toUpperCase()}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <div
              className="hidden sm:flex items-center gap-2 px-2.5 py-1.5 rounded-md font-mono-ui text-[10px] tracking-wide"
              style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
                style={{ background: 'var(--status-green)' }}
              />
              <span style={{ color: 'var(--mute)' }}>POLLER ACTIVE · 30S</span>
            </div>
            <NavLink
              to="/dashboard"
              className="px-4 py-2 rounded-md text-xs font-semibold transition-opacity hover:opacity-90"
              style={{ background: 'var(--signal)', color: 'var(--void)' }}
            >
              Open Dashboard
            </NavLink>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t" style={{ borderColor: 'var(--line)' }}>
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span className="font-mono-ui text-[11px]" style={{ color: 'var(--mute)' }}>
            © {new Date().getFullYear()} Sentinel SRE · Autonomous remediation engine
          </span>
          <span className="font-mono-ui text-[11px]" style={{ color: 'var(--mute)' }}>
            gemini-2.5-flash · sandboxed pytest · github rest api
          </span>
        </div>
      </footer>
    </div>
  );
}
