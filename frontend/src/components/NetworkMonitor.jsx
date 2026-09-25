import { useState, useEffect, useRef } from 'react'

function timeAgo(ts) {
  const s = Math.round((Date.now() / 1000) - ts)
  if (s < 60) return `${s}s ago`
  return `${Math.round(s / 60)}m ago`
}

const INIT_LOG = [
  { type: 'INFO', color: 'text-tertiary', time: '[--:--:--]', msg: 'System initialized — awaiting first task' },
]

export default function NetworkMonitor() {
  const [stats, setStats] = useState(null)
  const [log, setLog] = useState(INIT_LOG)
  const [artifacts, setArtifacts] = useState([])
  const fetchingRef = useRef(false)

  const fetchStats = async () => {
    if (fetchingRef.current) return
    fetchingRef.current = true
    try {
      const r = await fetch('/api/network/stats')
      const d = await r.json()
      setStats(d)
      if (d.recent_log?.length) {
        const mapped = d.recent_log.slice(-8).map(e => ({
          type: e.external ? 'WARN' : 'CALL',
          color: e.external ? 'text-error' : 'text-secondary-container',
          time: `[${new Date(e.ts * 1000).toLocaleTimeString('en-GB', { hour12: false })}]`,
          msg: `${e.destination} — ${e.preview || ''}`,
        }))
        setLog(mapped.length ? mapped : INIT_LOG)
      }
    } catch {}
    finally { fetchingRef.current = false }
  }

  const fetchArtifacts = async () => {
    try {
      const r = await fetch('/api/documents/list')
      const d = await r.json()
      setArtifacts((d.files || []).slice(0, 5))
    } catch {}
  }

  useEffect(() => {
    fetchStats()
    fetchArtifacts()
    const id = setInterval(() => { fetchStats(); fetchArtifacts() }, 5000)
    return () => clearInterval(id)
  }, [])

  const extCalls = stats?.external_calls ?? 0
  const intCalls = stats?.internal_calls ?? 0

  return (
    <aside className="w-80 h-full border-l border-[#262b35] bg-[#101318] flex flex-col flex-shrink-0 z-30">
      {/* Header */}
      <div className="p-4 border-b border-[#262b35] bg-[#14171d] flex items-center gap-2 flex-shrink-0">
        <span className="material-symbols-outlined text-primary text-[18px]">monitor_heart</span>
        <h2 className="font-label-caps text-label-caps text-white font-bold tracking-wider">SYSTEM TELEMETRY</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Sovereignty Status */}
        <section>
          <h3 className="font-label-caps text-[10px] text-on-surface-variant mb-2.5 border-b border-[#262b35] pb-1 uppercase tracking-wider">
            Data Sovereignty
          </h3>
          <div className={`border p-3 text-center mb-3 rounded ${extCalls === 0 ? 'bg-[#0a1a15] border-tertiary/30' : 'bg-[#1a0a0a] border-error/30'}`}>
            <div className="font-code-sm text-[10px] text-on-surface-variant uppercase tracking-wide mb-0.5">EXTERNAL CALLS</div>
            <div className={`font-display-lg text-[36px] font-mono leading-none ${extCalls === 0 ? 'text-tertiary' : 'text-error'}`}>{extCalls}</div>
            <div className={`font-code-sm text-[10px] mt-1 ${extCalls === 0 ? 'text-tertiary' : 'text-error'}`}>
              {extCalls === 0 ? '✓ SOVEREIGN — VERIFIED' : '✗ SOVEREIGNTY COMPROMISED'}
            </div>
          </div>
          <table className="w-full font-code-sm text-code-sm text-left border-collapse">
            <tbody>
              <tr className="border-b border-[#212631]">
                <td className="py-1.5 text-on-surface-variant font-mono">inference</td>
                <td className="py-1.5 text-on-surface-variant font-mono">→</td>
                <td className="py-1.5 text-white font-mono">ollama</td>
                <td className="py-1.5 text-right"><span className="material-symbols-outlined text-[15px] text-tertiary">link</span></td>
              </tr>
              <tr className="border-b border-[#212631]">
                <td className="py-1.5 text-on-surface-variant font-mono">embeddings</td>
                <td className="py-1.5 text-on-surface-variant font-mono">→</td>
                <td className="py-1.5 text-white font-mono">chroma</td>
                <td className="py-1.5 text-right"><span className="material-symbols-outlined text-[15px] text-tertiary">link</span></td>
              </tr>
              <tr className="border-b border-[#212631]">
                <td className="py-1.5 text-on-surface-variant font-mono">internet</td>
                <td className="py-1.5 text-on-surface-variant font-mono">→</td>
                <td className="py-1.5 text-error font-mono">blocked</td>
                <td className="py-1.5 text-right"><span className="material-symbols-outlined text-[15px] text-error">block</span></td>
              </tr>
              <tr>
                <td className="py-1.5 text-on-surface-variant font-mono">cloud API</td>
                <td className="py-1.5 text-on-surface-variant font-mono">→</td>
                <td className="py-1.5 text-error font-mono">blocked</td>
                <td className="py-1.5 text-right"><span className="material-symbols-outlined text-[15px] text-error">block</span></td>
              </tr>
            </tbody>
          </table>
          {intCalls > 0 && (
            <div className="mt-2 font-code-sm text-[10px] text-on-surface-variant/60">
              Local calls processed: <span className="text-white font-mono">{intCalls}</span>
            </div>
          )}
        </section>

        {/* Action Log */}
        <section>
          <h3 className="font-label-caps text-[10px] text-on-surface-variant mb-2.5 border-b border-[#262b35] pb-1 uppercase tracking-wider">
            Action Log (Local Only)
          </h3>
          <div className="bg-[#0b0d11] border border-[#212631] p-3 font-code-sm text-[11px] font-mono h-44 overflow-y-auto space-y-1.5 rounded">
            {log.map((entry, i) => (
              <div key={i} className="text-on-surface-variant">
                <span className="text-gray-500">{entry.time}</span>{' '}
                <span className={entry.color}>{entry.type}</span>{' '}
                <span className="break-all">{entry.msg}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Output Artifacts */}
        <section>
          <h3 className="font-label-caps text-[10px] text-on-surface-variant mb-2.5 border-b border-[#262b35] pb-1 uppercase tracking-wider">
            Output Artifacts
          </h3>
          <ul className="space-y-2 font-code-sm text-[11px]">
            {artifacts.length === 0 && (
              <li className="text-on-surface-variant/50 text-center py-3 italic">No artifacts generated yet</li>
            )}
            {artifacts.map((f, i) => (
              <li key={i} className="bg-[#141820] border border-[#232936] p-2 rounded flex items-center justify-between hover:border-primary/40 transition-colors">
                <div className="truncate text-on-surface font-mono flex items-center gap-2">
                  <span className="material-symbols-outlined text-[14px] text-primary">
                    {f.name.endsWith('.py') ? 'code' : f.name.endsWith('.pptx') ? 'slideshow' : f.name.endsWith('.xlsx') ? 'table_chart' : 'description'}
                  </span>
                  {f.name}
                </div>
                <a href={f.url} download={f.name} className="text-primary hover:text-white transition-colors">
                  <span className="material-symbols-outlined text-[15px]">download</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </aside>
  )
}
