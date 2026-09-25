import { useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import NetworkMonitor from './components/NetworkMonitor'
import './index.css'

const INITIAL_SESSIONS = [
  { id: '#AC-9942', title: 'CDU-2 Inspection Report', timeAgo: '2m ago', model: 'phi3.5', active: true },
  { id: '#AC-9938', title: 'Heat Exchanger LMTD Calculation', timeAgo: '1h ago', model: 'qwen2.5', active: false },
  { id: '#AC-9925', title: 'P&ID Tag Extraction', timeAgo: '3h ago', model: 'moondream2', active: false },
  { id: '#AC-9910', title: 'SOP Emergency Shutdown', timeAgo: 'Yesterday', model: 'phi3.5', active: false },
]

function genId() { return '#AC-' + Math.floor(1000 + Math.random() * 9000) }

function ModelBadge({ name, desc, vram, pct, active, activeColorClass, activeShadowClass, activeBadgeBg, activeBadgeText, activeBorder, activeBar }) {
  if (active) {
    return (
      <div className={`flex items-center gap-3 px-3 py-1.5 rounded bg-[#1a1e27] border-l-2 ${activeBorder} border border-[#29303d] shadow-sm transition-all`}>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="font-data-mono text-[11px] font-semibold text-white tracking-tight leading-none">{name}</span>
            <span className={`w-1.5 h-1.5 rounded-full ${activeColorClass} ${activeShadowClass} animate-pulse`}></span>
            <span className={`text-[9px] font-label-caps px-1 rounded ${activeBadgeBg} ${activeBadgeText} border border-current`}>ACTIVE</span>
          </div>
          <div className="text-[10px] font-code-sm text-on-surface-variant/80 mt-0.5">{desc}</div>
        </div>
        <div className="w-20 pl-1">
          <div className="flex justify-between font-code-sm text-[9px] text-on-surface-variant mb-1 leading-none">
            <span className="text-white font-mono">{vram}</span><span className="opacity-60">{pct}</span>
          </div>
          <div className="w-full h-1 bg-[#0d0f12] rounded-none overflow-hidden">
            <div className={`h-full ${activeBar}`} style={{width: pct}}></div>
          </div>
        </div>
      </div>
    )
  }
  
  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded bg-[#161922] border border-[#232936] hover:border-[#323b4e] transition-colors">
      <div className="flex flex-col">
        <div className="flex items-center gap-1.5">
          <span className="font-data-mono text-[11px] font-medium text-on-surface leading-none">{name}</span>
          <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
          <span className="text-[9px] font-label-caps px-1 rounded bg-[#1e2330] text-on-surface-variant/70 border border-outline-variant/30">STANDBY</span>
        </div>
        <div className="text-[10px] font-code-sm text-on-surface-variant/70 mt-0.5">{desc}</div>
      </div>
      <div className="w-20 pl-1">
        <div className="flex justify-between font-code-sm text-[9px] text-on-surface-variant mb-1 leading-none">
          <span className="text-on-surface font-mono">{vram}</span><span className="opacity-60">{pct}</span>
        </div>
        <div className="w-full h-1 bg-[#0d0f12] rounded-none overflow-hidden">
          <div className="h-full bg-primary/30" style={{width: pct}}></div>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [sessions, setSessions] = useState(INITIAL_SESSIONS)
  const [activeId, setActiveId] = useState('#AC-9942')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeModel, setActiveModel] = useState('Phi-3.5 Mini')

  const activeSession = sessions.find(s => s.id === activeId) || sessions[0]

  const newChat = () => {
    const id = genId()
    setSessions(prev => [{ id, title: 'New Session', timeAgo: 'now', model: 'phi3.5', active: false }, ...prev])
    setActiveId(id)
  }

  const selectSession = (id) => setActiveId(id)

  return (
    <div className="bg-[#0d0f12] text-[#d8dde6] h-screen overflow-hidden flex flex-col font-body-sm">
      {/* TOP HEADER */}
      <header className="flex items-center justify-between w-full px-5 h-16 z-50 bg-[#14171d] border-b border-[#262b35] flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            className="p-1.5 text-on-surface-variant hover:text-white hover:bg-[#1f242d] rounded transition-colors flex items-center justify-center"
            onClick={() => setSidebarOpen(o => !o)}
            title="Toggle Sidebar"
          >
            <span className="material-symbols-outlined text-[22px]">menu</span>
          </button>
          <div className="flex items-center gap-2.5 select-none">
            <div className="w-7 h-7 rounded bg-[#1c222e] border border-[#2d3545] flex items-center justify-center text-primary shadow-inner">
              <span className="material-symbols-outlined text-[18px]">hub</span>
            </div>
            <h1 className="font-headline-sm text-[17px] font-bold text-white tracking-tight flex items-baseline">
              LocalHost<span className="text-primary font-mono">.Ai</span>
            </h1>
          </div>
        </div>

        {/* Model Status Badges */}
        <div className="flex items-center gap-2.5">
          <ModelBadge
            name="Phi-3.5 Mini"
            desc="3.8B · Reasoning"
            vram="2.2G"
            pct="55%"
            active={activeModel.startsWith('Phi-3.5 Mini')}
            activeColorClass="bg-tertiary"
            activeShadowClass="shadow-[0_0_6px_rgba(56,222,187,0.8)]"
            activeBadgeBg="bg-tertiary-container/40"
            activeBadgeText="text-tertiary"
            activeBorder="border-l-secondary-container"
            activeBar="bg-secondary-container"
          />
          <ModelBadge
            name="Qwen2.5-Coder"
            desc="3B · Code/Logic"
            vram="1.9G"
            pct="47%"
            active={activeModel.startsWith('Qwen2.5-Coder')}
            activeColorClass="bg-[#10b981]"
            activeShadowClass="shadow-[0_0_6px_rgba(16,185,129,0.8)]"
            activeBadgeBg="bg-[#10b981]/20"
            activeBadgeText="text-[#10b981]"
            activeBorder="border-l-[#10b981]"
            activeBar="bg-[#10b981]"
          />
          <ModelBadge
            name="Llava-Phi3"
            desc="4.2B · Vision/OCR"
            vram="2.9G"
            pct="72%"
            active={activeModel.startsWith('Llava')}
            activeColorClass="bg-[#f59e0b]"
            activeShadowClass="shadow-[0_0_6px_rgba(245,158,11,0.8)]"
            activeBadgeBg="bg-[#f59e0b]/20"
            activeBadgeText="text-[#f59e0b]"
            activeBorder="border-l-[#f59e0b]"
            activeBar="bg-[#f59e0b]"
          />
        </div>
      </header>

      {/* MAIN WORKSPACE */}
      <main className="flex-1 flex overflow-hidden">
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onSelect={selectSession}
          onNew={newChat}
          open={sidebarOpen}
        />
        <ChatPanel key={activeId} session={activeSession} onActiveModelChange={setActiveModel} />
        <NetworkMonitor />
      </main>
    </div>
  )
}
