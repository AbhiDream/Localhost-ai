export default function Header({ health }) {
  const ok = health?.ollama === 'connected'
  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo">⚗️</div>
        <div>
          <div className="header-title">MRPL AI Workbench</div>
          <div className="header-sub">Air-gapped · Self-hosted · On-premises</div>
        </div>
      </div>
      <div className="header-right">
        <span className="badge badge-indigo">PS 26117</span>
        <span className="badge badge-violet">SIH 2026</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <div className={`health-dot ${ok ? 'ok' : 'err'}`} />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {ok ? 'Ollama connected' : health?.status === 'unreachable' ? 'Backend offline' : 'Checking…'}
          </span>
        </div>
      </div>
    </header>
  )
}
