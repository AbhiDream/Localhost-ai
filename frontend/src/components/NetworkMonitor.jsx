import { useState, useEffect, useRef } from 'react'

const INIT_LOG = [
  { type: 'INFO', color: 'text-text-secondary', time: '[--:--]', msg: 'System initialized' },
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
        const mapped = d.recent_log.slice(-5).map(e => ({
          type: e.external ? 'WARN' : 'CALL',
          color: e.external ? 'text-error' : 'text-success',
          time: `[${new Date(e.ts * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}]`,
          msg: `${e.destination}`,
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
      setArtifacts((d.files || []).slice(0, 3))
    } catch {}
  }

  useEffect(() => {
    fetchStats()
    fetchArtifacts()
    const id = setInterval(() => { fetchStats(); fetchArtifacts() }, 5000)
    return () => clearInterval(id)
  }, [])

  const extCalls = stats?.external_calls ?? 0

  return (
    <aside className="w-[300px] h-full border-l border-border bg-surface-card flex flex-col flex-shrink-0 z-30 overflow-y-auto">
      <div className="p-5 space-y-6">
        
        <section>
           <h3 className="text-[13px] font-medium text-text-primary mb-3">Sovereignty Status</h3>
           <div className={`p-4 rounded-xl border ${extCalls === 0 ? 'bg-accent-container border-accent/30' : 'bg-red-50 border-error/30'}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`material-symbols-outlined text-[18px] ${extCalls === 0 ? 'text-accent-text' : 'text-error'}`}>
                  {extCalls === 0 ? 'verified_user' : 'gpp_bad'}
                </span>
                <span className={`font-semibold text-[13px] ${extCalls === 0 ? 'text-accent-text' : 'text-error'}`}>
                  {extCalls === 0 ? 'Air-gapped Mode' : 'Sovereignty Breach'}
                </span>
              </div>
              <div className="text-[11px] text-text-secondary">
                External API calls: <strong className={extCalls === 0 ? 'text-accent-text' : 'text-error'}>{extCalls}</strong>
              </div>
           </div>

           {/* Mini Action Log */}
           <div className="mt-3">
             <div className="text-[11px] font-medium text-text-tertiary mb-1.5 uppercase tracking-wide">Network Log</div>
             <div className="bg-surface-inset rounded-lg p-2.5 font-mono text-[10px] space-y-1">
               {log.map((entry, i) => (
                 <div key={i} className="flex gap-2 truncate">
                   <span className="text-text-tertiary flex-shrink-0">{entry.time}</span>
                   <span className={entry.color}>{entry.type}</span>
                   <span className="text-text-secondary truncate">{entry.msg}</span>
                 </div>
               ))}
             </div>
           </div>
        </section>

      </div>
    </aside>
  )
}
