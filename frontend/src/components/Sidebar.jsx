export default function Sidebar({ sessions, activeId, onSelect, onNew, open }) {
  return (
    <aside
      id="sidebar"
      className={`h-full flex flex-col border-r border-[#262b35] bg-[#14171d] flex-shrink-0 z-40 transition-all duration-200 ${open ? 'w-[280px]' : 'w-0 min-w-0 opacity-0 overflow-hidden pointer-events-none border-r-0'}`}
    >
      {/* New Chat */}
      <div className="p-3 border-b border-[#262b35]">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded bg-[#1e2430] hover:bg-[#252d3d] text-white border border-[#2e3648] hover:border-primary/50 transition-all font-label-caps text-label-caps shadow-sm group"
        >
          <span className="material-symbols-outlined text-[18px] text-primary group-hover:scale-110 transition-transform">add</span>
          <span className="tracking-wider">NEW CHAT</span>
        </button>
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        <div>
          <div className="flex items-center justify-between px-2 mb-2 text-on-surface-variant">
            <span className="font-label-caps text-[10px] tracking-wider uppercase">Active Sessions</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1e232d] text-on-surface-variant">{sessions.length}</span>
          </div>
          <div className="space-y-1.5">
            {sessions.map(sess => {
              const isActive = sess.id === activeId
              return (
                <button
                  key={sess.id}
                  onClick={() => onSelect(sess.id)}
                  className={`w-full text-left p-2.5 rounded border transition-colors block ${
                    isActive
                      ? 'bg-[#1d222c] border-primary/40 text-white'
                      : 'hover:bg-[#191d25] border-transparent hover:border-[#282f3d] text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className={`font-data-mono text-[12px] font-semibold flex items-center gap-1.5 truncate ${isActive ? 'text-primary' : 'text-on-surface'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-tertiary' : 'bg-outline-variant'}`}></span>
                      Session {sess.id}
                    </span>
                    {isActive && (
                      <span className="text-[9px] font-label-caps uppercase px-1 rounded bg-secondary-container/20 text-secondary-fixed-dim border border-secondary-container/40">Active</span>
                    )}
                  </div>
                  <div className="text-[12px] font-body-sm truncate pl-3">{sess.title}</div>
                  <div className="text-[10px] font-code-sm text-on-surface-variant/70 mt-1 pl-3 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px]">schedule</span>
                    {sess.timeAgo} · {sess.model}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </aside>
  )
}
