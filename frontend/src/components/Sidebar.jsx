import { useState } from 'react'

export default function Sidebar({ sessions, activeId, onSelect, onNew, open, onToggle }) {
  const [folders] = useState(['General', 'Design', 'Management'])
  
  // Group sessions by simple heuristic for UI
  const todaySessions = sessions.filter(s => s.timeAgo.includes('m') || s.timeAgo.includes('h'))
  const yesterdaySessions = sessions.filter(s => s.timeAgo.includes('Yesterday') || (!s.timeAgo.includes('m') && !s.timeAgo.includes('h')))

  return (
    <aside
      className={`h-full flex flex-col bg-sidebar text-sidebar-text flex-shrink-0 z-40 transition-all duration-300 dark-scroll ${
        open ? 'w-[260px] lg:w-[280px]' : 'w-0 min-w-0 opacity-0 overflow-hidden pointer-events-none'
      }`}
    >
      {/* Header / Brand */}
      <div className="h-14 px-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2 text-white">
          <div className="w-6 h-6 rounded flex items-center justify-center bg-white text-black font-bold text-[14px]">
            <span className="material-symbols-outlined text-[16px]">hub</span>
          </div>
          <span className="font-semibold tracking-wide">MRPL.ai</span>
        </div>
        <div className="flex gap-1">
          <button onClick={onToggle} className="p-1 rounded-md hover:bg-sidebar-hover text-sidebar-text hover:text-white transition-colors lg:hidden">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
          <button className="p-1 rounded-md hover:bg-sidebar-hover text-sidebar-text hover:text-white transition-colors">
            <span className="material-symbols-outlined text-[18px]">more_horiz</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-5">
        
        {/* Actions */}
        <div className="space-y-2">
          <button
            onClick={onNew}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sidebar-text-bright hover:text-white hover:bg-sidebar-hover transition-colors group"
          >
            <span className="material-symbols-outlined text-[18px] group-hover:scale-110 transition-transform">add</span>
            <span className="text-[14px] font-medium">New Chat</span>
          </button>
          
          <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover transition-colors">
            <span className="material-symbols-outlined text-[18px]">search</span>
            <span className="text-[14px] font-medium">Search</span>
          </button>
        </div>

        <div className="border-t border-sidebar-border" />

        {/* Main Nav */}
        <div className="space-y-1">
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover transition-colors">
            <span className="material-symbols-outlined text-[18px]">home</span>
            <span className="text-[14px]">Home</span>
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-white bg-sidebar-active transition-colors">
            <span className="material-symbols-outlined text-[18px]">chat</span>
            <span className="text-[14px]">Chats</span>
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover transition-colors">
            <span className="material-symbols-outlined text-[18px]">tune</span>
            <span className="text-[14px]">Prompt Settings</span>
          </button>
        </div>

        <div className="border-t border-sidebar-border" />

        {/* Folders */}
        <div>
          <div className="flex items-center justify-between px-3 py-1 mb-1 group cursor-pointer">
            <span className="text-[11px] font-semibold tracking-wider text-sidebar-text group-hover:text-sidebar-text-bright transition-colors uppercase">Pinned Folders</span>
            <div className="flex items-center text-sidebar-text opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="material-symbols-outlined text-[16px] hover:text-white">add</span>
              <span className="material-symbols-outlined text-[16px] hover:text-white">expand_more</span>
            </div>
          </div>
          <div className="space-y-1">
            {folders.map(f => (
              <button key={f} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover transition-colors group">
                <span className="material-symbols-outlined text-[18px]">folder</span>
                <span className="text-[14px]">{f}</span>
                <span className="material-symbols-outlined text-[16px] ml-auto opacity-0 group-hover:opacity-100 hover:text-white">more_horiz</span>
              </button>
            ))}
          </div>
          <button className="w-full flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-sidebar-text hover:text-sidebar-text-bright transition-colors text-[13px]">
            <span className="material-symbols-outlined text-[16px]">add</span>
            Show 4 more
          </button>
        </div>

        <div className="border-t border-sidebar-border" />

        {/* Chat History */}
        <div>
          <div className="flex items-center justify-between px-3 py-1 mb-1 group cursor-pointer">
            <span className="text-[11px] font-semibold tracking-wider text-sidebar-text group-hover:text-sidebar-text-bright transition-colors uppercase">Chats</span>
            <div className="flex items-center text-sidebar-text opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="material-symbols-outlined text-[16px] hover:text-white">add</span>
              <span className="material-symbols-outlined text-[16px] hover:text-white">expand_more</span>
            </div>
          </div>
          
          <div className="mt-2 mb-3">
            <div className="px-3 text-[11px] font-medium text-sidebar-text mb-1">Today</div>
            <div className="space-y-0.5">
              {todaySessions.map(sess => (
                <button
                  key={sess.id}
                  onClick={() => onSelect(sess.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group ${
                    sess.id === activeId ? 'text-white bg-sidebar-active' : 'text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover'
                  }`}
                >
                  <span className="material-symbols-outlined text-[16px]">chat_bubble_outline</span>
                  <span className="text-[13px] truncate flex-1 text-left">{sess.title}</span>
                  <span className="material-symbols-outlined text-[16px] ml-auto opacity-0 group-hover:opacity-100 hover:text-white">more_horiz</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="px-3 text-[11px] font-medium text-sidebar-text mb-1">Yesterday</div>
            <div className="space-y-0.5">
              {yesterdaySessions.map(sess => (
                <button
                  key={sess.id}
                  onClick={() => onSelect(sess.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group ${
                    sess.id === activeId ? 'text-white bg-sidebar-active' : 'text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover'
                  }`}
                >
                  <span className="material-symbols-outlined text-[16px]">chat_bubble_outline</span>
                  <span className="text-[13px] truncate flex-1 text-left">{sess.title}</span>
                  <span className="material-symbols-outlined text-[16px] ml-auto opacity-0 group-hover:opacity-100 hover:text-white">more_horiz</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
