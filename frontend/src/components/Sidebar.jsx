import { useState } from 'react'

export default function Sidebar({ sessions, activeId, onSelect, onNew, open, onToggle, onDelete, onClearAll }) {
  const [folders] = useState(['General', 'Design', 'Management'])
  const [isSearching, setIsSearching] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showMenu, setShowMenu] = useState(false)
  
  // Filter sessions
  const filteredSessions = sessions.filter(s => s.title.toLowerCase().includes(searchQuery.toLowerCase()))
  const todaySessions = filteredSessions.filter(s => s.timeAgo.includes('m') || s.timeAgo.includes('h') || s.timeAgo === 'now')
  const yesterdaySessions = filteredSessions.filter(s => s.timeAgo.includes('Yesterday') || (!s.timeAgo.includes('m') && !s.timeAgo.includes('h') && s.timeAgo !== 'now'))

  return (
    <aside
      className={`h-full flex flex-col bg-black text-sidebar-text flex-shrink-0 z-40 transition-all duration-300 dark-scroll ${
        open ? 'w-[260px] lg:w-[280px]' : 'w-0 min-w-0 opacity-0 overflow-hidden pointer-events-none'
      }`}
    >
      {/* Header / Brand */}
      <div className="h-14 px-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2 text-white">
          <div className="w-6 h-6 rounded flex items-center justify-center bg-white text-black font-bold text-[14px]">
            <span className="material-symbols-outlined text-[16px]">hub</span>
          </div>
          <span className="font-semibold tracking-wide">LocalHost.Ai</span>
        </div>
        <div className="flex gap-1 items-center">
          <button onClick={onToggle} className="p-1 rounded-md hover:bg-sidebar-hover text-sidebar-text hover:text-white transition-colors lg:hidden">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
          
          <div className="relative">
            <button onClick={() => setShowMenu(!showMenu)} className="p-1 rounded-md hover:bg-sidebar-hover text-sidebar-text hover:text-white transition-colors">
              <span className="material-symbols-outlined text-[18px]">more_horiz</span>
            </button>
            {showMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)}></div>
                <div className="absolute top-full mt-2 right-0 w-40 bg-[#1a1a24] border border-[#2a2a35] rounded-xl shadow-lg overflow-hidden z-50 py-1">
                  <button onClick={() => { if(window.confirm('Delete all chats?')) onClearAll(); setShowMenu(false) }} className="w-full text-left px-4 py-2 text-[13px] text-red-400 hover:bg-[#2a2a35] flex items-center gap-2 transition-colors">
                    <span className="material-symbols-outlined text-[16px]">delete_sweep</span>
                    Clear all
                  </button>
                  <button onClick={() => setShowMenu(false)} className="w-full text-left px-4 py-2 text-[13px] text-gray-300 hover:bg-[#2a2a35] flex items-center gap-2 transition-colors">
                    <span className="material-symbols-outlined text-[16px]">settings</span>
                    Preferences
                  </button>
                </div>
              </>
            )}
          </div>
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
          
          {isSearching ? (
            <div className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-sidebar-hover text-white transition-colors border border-border">
              <span className="material-symbols-outlined text-[18px] text-sidebar-text">search</span>
              <input
                autoFocus
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onBlur={() => { if(!searchQuery) setIsSearching(false) }}
                placeholder="Search chats..."
                className="bg-transparent border-none outline-none text-[14px] w-full placeholder-sidebar-text"
              />
            </div>
          ) : (
            <button onClick={() => setIsSearching(true)} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sidebar-text hover:text-sidebar-text-bright hover:bg-sidebar-hover transition-colors">
              <span className="material-symbols-outlined text-[18px]">search</span>
              <span className="text-[14px] font-medium">Search</span>
            </button>
          )}
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
          
          {todaySessions.length > 0 && (
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
                    <div onClick={(e) => onDelete(sess.id, e)} className="ml-auto opacity-0 group-hover:opacity-100 hover:text-error transition-colors p-1">
                      <span className="material-symbols-outlined text-[16px]">delete</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {yesterdaySessions.length > 0 && (
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
                    <div onClick={(e) => onDelete(sess.id, e)} className="ml-auto opacity-0 group-hover:opacity-100 hover:text-error transition-colors p-1">
                      <span className="material-symbols-outlined text-[16px]">delete</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {todaySessions.length === 0 && yesterdaySessions.length === 0 && (
            <div className="text-[12px] text-sidebar-text text-center mt-4">
              No chats found
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
