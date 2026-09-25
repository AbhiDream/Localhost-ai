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

export default function App() {
  const [sessions, setSessions] = useState(INITIAL_SESSIONS)
  const [activeId, setActiveId] = useState('#AC-9942')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(true)
  const [activeModel, setActiveModel] = useState('Phi-3.5 Mini')

  const activeSession = sessions.find(s => s.id === activeId) || sessions[0]

  const newChat = () => {
    const id = genId()
    setSessions(prev => [{ id, title: 'New Session', timeAgo: 'now', model: 'phi3.5', active: false }, ...prev])
    setActiveId(id)
  }

  const selectSession = (id) => setActiveId(id)

  return (
    <div className="h-screen flex overflow-hidden bg-surface font-sans">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={selectSession}
        onNew={newChat}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
      />

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-4 sm:px-6 h-14 bg-surface-card border-b border-border flex-shrink-0">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-1.5 rounded-lg hover:bg-surface-inset text-text-secondary hover:text-text-primary transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">menu</span>
              </button>
            )}
            <h1 className="text-[18px] font-semibold text-text-primary tracking-tight">
              LocalHost<span className="text-accent">.Ai</span>
            </h1>
          </div>

          <div className="flex items-center gap-2">
            {/* Active model pill */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-container text-accent-text text-[12px] font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              {activeModel}
            </div>

            <button className="hidden sm:flex items-center gap-1.5 px-4 py-2 rounded-full border border-border bg-surface-card text-text-secondary hover:bg-surface-inset hover:text-text-primary text-[13px] font-medium transition-all">
              <span className="material-symbols-outlined text-[16px]">sync</span>
              Update
            </button>

            <button
              onClick={() => setSettingsOpen(o => !o)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-[13px] font-medium transition-all ${
                settingsOpen
                  ? 'bg-dark text-white shadow-sm'
                  : 'bg-surface-card border border-border text-text-secondary hover:bg-surface-inset'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">settings</span>
              <span className="hidden sm:inline">Settings</span>
            </button>
          </div>
        </header>

        {/* Content + Settings Panel */}
        <div className="flex-1 flex overflow-hidden">
          <ChatPanel key={activeId} session={activeSession} onActiveModelChange={setActiveModel} />
          {settingsOpen && <NetworkMonitor />}
        </div>
      </div>
    </div>
  )
}
