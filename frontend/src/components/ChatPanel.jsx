import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      className="text-[10px] font-mono text-on-surface-variant hover:text-white px-2 py-0.5 rounded bg-[#1e232d] border border-[#2d3545] transition-colors"
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

const mdComponents = {
  h1: ({ children }) => <h1 className="text-primary font-bold text-[18px] mt-4 mb-2 pb-1 border-b border-[#262b35] font-headline-sm">{children}</h1>,
  h2: ({ children }) => <h2 className="text-[#a7c8ff] font-semibold text-[15px] mt-3 mb-1.5 font-headline-sm">{children}</h2>,
  h3: ({ children }) => <h3 className="text-on-surface font-semibold text-[14px] mt-2 mb-1">{children}</h3>,
  p:  ({ children }) => <p className="mb-3 text-[14px] text-on-surface leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 pl-2 space-y-1.5">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 pl-5 space-y-1.5 list-decimal text-on-surface-variant">{children}</ol>,
  li: ({ children }) => (
    <li className="text-[13px] text-on-surface-variant flex gap-2 items-start">
      <span className="text-tertiary mt-[5px] flex-shrink-0 text-[8px]">▸</span>
      <span className="leading-relaxed">{children}</span>
    </li>
  ),
  strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
  em: ({ children }) => <em className="text-secondary-fixed-dim italic">{children}</em>,
  code: ({ inline, children, className }) => {
    if (inline) {
      return <code className="bg-[#0b0d11] text-primary px-1.5 py-0.5 rounded font-mono text-[12px] border border-[#1e232d]">{children}</code>
    }
    const lang = (className || '').replace('language-', '') || 'code'
    const rawText = String(children).replace(/\n$/, '')
    return (
      <div className="my-3 rounded border border-[#262b35] overflow-hidden">
        <div className="flex items-center justify-between bg-[#14171d] px-3 py-1.5 border-b border-[#262b35]">
          <span className="font-mono text-[10px] text-tertiary uppercase tracking-wider">{lang}</span>
          <CopyBtn text={rawText} />
        </div>
        <pre className="bg-[#0b0d11] p-4 overflow-x-auto text-[12px] leading-relaxed font-mono text-[#d6e3ff] m-0">
          <code>{children}</code>
        </pre>
      </div>
    )
  },
  pre: ({ children }) => <>{children}</>,
  blockquote: ({ children }) => <blockquote className="border-l-2 border-primary pl-3 my-2 text-on-surface-variant italic">{children}</blockquote>,
  table: ({ children }) => <div className="overflow-x-auto my-3"><table className="w-full text-[12px] border-collapse border border-[#262b35]">{children}</table></div>,
  th: ({ children }) => <th className="bg-[#1e232d] text-primary font-mono text-[11px] px-3 py-1.5 border border-[#262b35] text-left uppercase tracking-wider">{children}</th>,
  td: ({ children }) => <td className="px-3 py-1.5 border border-[#262b35] text-on-surface-variant text-[12px]">{children}</td>,
  hr: () => <hr className="border-[#262b35] my-4" />,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-primary underline hover:text-[#d6e3ff] transition-colors">{children}</a>,
}

function preprocessMath(content) {
  return content
    .replace(/\\\[([^]*?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\(([^]*?)\\\)/g, (_, m) => `$${m}$`)
}

function MarkdownContent({ content }) {
  return (
    <div className="text-[14px] leading-relaxed katex-dark">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={mdComponents}>
        {preprocessMath(content)}
      </ReactMarkdown>
    </div>
  )
}

const PHASE_ICONS = {
  extract: 'document_scanner',
  retrieve: 'search',
  reason: 'psychology',
  execute: 'terminal',
  artifact: 'description',
}

const PHASE_LABELS = {
  extract: 'Extraction',
  retrieve: 'Knowledge Retrieval',
  reason: 'Reasoning',
  execute: 'Sandbox Execution',
  artifact: 'Document Generation',
}

export default function ChatPanel({ session, onActiveModelChange }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [generating, setGenerating] = useState(false)
  const [routingModel, setRoutingModel] = useState('Phi-3.5 Mini')
  const [routingColor, setRoutingColor] = useState('#a7c8ff')
  const [docType, setDocType] = useState('report')
  const [attachedFile, setAttachedFile] = useState(null)
  const [activePhases, setActivePhases] = useState([])
  const bottomRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handlePaste = (e) => {
    if (e.clipboardData.files.length > 0) handleFile(e.clipboardData.files[0])
  }

  const handleFile = (file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => setAttachedFile({ name: file.name, data: e.target.result, type: file.type })
    reader.readAsDataURL(file)
  }

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || generating) return

    const currentAttachment = attachedFile
    setAttachedFile(null)
    setActivePhases([])

    const userMsg = { id: Date.now(), role: 'user', content: text, attachment: currentAttachment }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setGenerating(true)

    const aiId = Date.now() + 1
    setMessages(prev => [...prev, {
      id: aiId, role: 'ai', content: '', streaming: true,
      model: 'Phi-3.5 Mini', modelColor: '#a7c8ff',
      tokens: 0, latency: 0, phases: [], taskType: '',
      artifacts: [], sandboxResults: [],
    }])

    try {
      const body = { message: text }
      if (currentAttachment?.type?.startsWith('image/')) {
        body.images = [currentAttachment.data.split(',')[1]]
      } else if (currentAttachment?.type === 'application/pdf') {
        body.pdf = currentAttachment.data.split(',')[1]
      }

      // Use agent endpoint
      const resp = await fetch('/api/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let tokens = 0, latency = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'meta' || data.type === 'phase') {
              const display = data.model_display || 'Phi-3.5 Mini'
              const color = data.model_color || '#a7c8ff'
              setRoutingModel(display)
              setRoutingColor(color)
              if (onActiveModelChange) onActiveModelChange(display)

              if (data.type === 'phase') {
                setActivePhases(prev => [...prev, data.phase])
              }

              setMessages(prev => prev.map(m => m.id === aiId ? {
                ...m,
                model: display,
                modelColor: color,
                taskType: data.task_type || m.taskType,
                phases: data.type === 'phase' ? [...m.phases, data.phase] : m.phases,
              } : m))

            } else if (data.type === 'token') {
              setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, content: m.content + data.text }
                : m))

            } else if (data.type === 'artifact') {
              setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, artifacts: [...m.artifacts, data] }
                : m))

            } else if (data.type === 'phase_result' && data.phase === 'execute') {
              setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, sandboxResults: [...m.sandboxResults, data] }
                : m))

            } else if (data.type === 'done') {
              tokens = data.tokens; latency = data.latency_ms

            } else if (data.type === 'error') {
              setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, content: `**Error:** ${data.message}`, streaming: false }
                : m))
            }
          } catch {}
        }
      }
      setMessages(prev => prev.map(m => m.id === aiId
        ? { ...m, streaming: false, tokens, latency }
        : m))
    } catch (e) {
      setMessages(prev => prev.map(m => m.id === aiId
        ? { ...m, content: `**Backend unreachable:** ${e.message}`, streaming: false }
        : m))
    }
    setGenerating(false)
    setActivePhases([])
  }

  const generateDoc = async () => {
    const text = input.trim()
    if (!text || generating) return
    setGenerating(true)
    if (onActiveModelChange) onActiveModelChange('Phi-3.5 Mini')
    setAttachedFile(null)
    const userMsg = { id: Date.now(), role: 'user', content: `📄 Generate ${docType.toUpperCase()}: ${text}` }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    const aiId = Date.now() + 1
    setMessages(prev => [...prev, {
      id: aiId, role: 'ai', content: '', streaming: true,
      model: 'Phi-3.5 Mini', modelColor: '#a7c8ff',
      tokens: 0, latency: 0, phases: [], artifacts: [], sandboxResults: [],
    }])
    try {
      const r = await fetch('/api/documents/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, doc_type: docType, title: 'MRPL Document', equipment_id: 'EQ-001' }),
      })
      const data = await r.json()
      setMessages(prev => prev.map(m => m.id === aiId ? {
        ...m,
        content: `✅ Document generated using **${data.model_used}**. Zero external API calls.`,
        streaming: false,
        artifacts: [{ file: data.file, download_url: data.download_url, doc_type: data.doc_type }],
      } : m))
    } catch (e) {
      setMessages(prev => prev.map(m => m.id === aiId
        ? { ...m, content: `**Error:** ${e.message}`, streaming: false }
        : m))
    }
    setGenerating(false)
  }

  const sessionId = session?.id || '#AC-0000'
  const sessionTitle = session?.title || 'New Session'

  return (
    <section className="flex-1 flex flex-col bg-[#0d0f12] min-w-0 overflow-hidden">
      {/* Session Subheader */}
      <div className="px-6 py-3 border-b border-[#262b35] bg-[#14171d] flex justify-between items-center flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-data-mono text-[13px] text-white font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tertiary"></span>
            SESSION: {sessionId}
          </span>
          <span className="text-[#43474f]">|</span>
          <span className="text-xs text-on-surface-variant font-mono truncate">{sessionTitle}</span>
        </div>
        <div className="flex items-center gap-3">
          {/* Active phase indicators */}
          {activePhases.length > 0 && (
            <div className="flex items-center gap-1.5">
              {activePhases.map((phase, i) => (
                <span key={i} className={`text-[9px] font-label-caps px-1.5 py-0.5 rounded border ${
                  i === activePhases.length - 1
                    ? 'bg-tertiary-container/40 text-tertiary border-tertiary/30 phase-active'
                    : 'bg-[#1e2330] text-on-surface-variant/50 border-outline-variant/30'
                }`}>
                  {PHASE_LABELS[phase] || phase}
                </span>
              ))}
            </div>
          )}
          <div className="font-code-sm text-[11px] text-on-surface-variant bg-[#1a1d24] px-2.5 py-1 border border-[#262b35] rounded">
            Air-Gap: <span className="text-tertiary font-bold">VERIFIED</span>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-4 text-center py-16 min-h-[60vh]">
            <div className="w-12 h-12 rounded bg-[#1c222e] border border-[#2d3545] flex items-center justify-center text-primary mb-2">
              <span className="material-symbols-outlined text-[28px]">hub</span>
            </div>
            <h2 className="font-headline-md text-white">Sovereign AI Workbench</h2>
            <p className="text-on-surface-variant font-body-sm max-w-md">
              Air-gapped agentic AI. All inference on isolated edge hardware.<br />
              Zero telemetry exits the network perimeter.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {[
                'Generate an inspection report for CDU-2 heat exchanger E-201',
                'Write a Python script for LMTD calculation',
                'What does OISD-116 say about fire protection in refineries?',
                'Create a presentation on pressure vessel inspection procedures',
              ].map(label => (
                <button key={label}
                  onClick={() => { setInput(label); inputRef.current?.focus() }}
                  className="px-3 py-1.5 rounded bg-[#1a1e27] border border-[#262b35] hover:border-primary/40 text-on-surface-variant hover:text-white font-code-sm text-[11px] transition-colors max-w-[280px] text-left"
                >{label}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id}>
            {msg.role === 'user' ? (
              <div className="flex justify-end">
                <div className="bg-primary-container text-[#d6e3ff] px-5 py-3 rounded-l-lg rounded-tr-lg max-w-[80%] font-body-lg text-body-lg border border-[#1e487a]/60 shadow-sm flex flex-col gap-2">
                  {msg.attachment?.type?.startsWith('image/') && (
                    <img src={msg.attachment.data} alt="uploaded" className="max-w-[250px] rounded-md border border-[#2d568c]/50 object-contain shadow-sm" />
                  )}
                  {msg.attachment?.type === 'application/pdf' && (
                    <div className="flex items-center gap-2 text-[12px] text-primary bg-[#0d1b2a] rounded px-2 py-1.5 border border-[#2d568c]/50">
                      <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
                      {msg.attachment.name}
                    </div>
                  )}
                  <span>{msg.content}</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3 max-w-[88%]">
                {/* Routing + Phase tags */}
                <div className="flex items-center gap-2 flex-wrap font-code-sm text-[11px] text-on-surface-variant/80">
                  <span className="material-symbols-outlined text-[15px] text-primary">route</span>
                  <span>
                    Agent → <span className="font-mono font-medium" style={{ color: msg.modelColor }}>{msg.model}</span>
                    {msg.taskType && <span className="ml-1 text-on-surface-variant/50">({msg.taskType})</span>}
                  </span>
                  {msg.phases?.map((phase, i) => (
                    <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-[#1e2330] border border-outline-variant/30 text-on-surface-variant/70 flex items-center gap-1">
                      <span className="material-symbols-outlined text-[11px]">{PHASE_ICONS[phase] || 'check'}</span>
                      {PHASE_LABELS[phase] || phase}
                    </span>
                  ))}
                </div>

                {/* AI response card */}
                <div className="bg-[#12151b] p-4 border border-[#222731] rounded">
                  {msg.content
                    ? <MarkdownContent content={msg.content} />
                    : <span className="text-on-surface-variant text-[13px]">Thinking...</span>
                  }
                  {msg.streaming && <span className="cursor-blink" />}
                </div>

                {/* Token stats */}
                {!msg.streaming && msg.tokens > 0 && (
                  <div className="flex items-center gap-3 font-code-sm text-[10px] text-on-surface-variant/60">
                    <span>{msg.tokens} tokens</span>
                    <span>{msg.latency}ms</span>
                    <span className="text-tertiary">✓ 0 external calls</span>
                    {msg.phases?.length > 0 && <span>• {msg.phases.length} agent phases</span>}
                  </div>
                )}

                {/* Artifact downloads */}
                {msg.artifacts?.map((art, i) => (
                  <div key={i} className="bg-[#14171e] border border-[#262b35] p-4 rounded">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded bg-[#1c2331] border border-[#2d3a52] flex items-center justify-center text-primary">
                          <span className="material-symbols-outlined text-[18px]">description</span>
                        </div>
                        <div>
                          <span className="font-data-mono text-data-mono text-white font-medium block leading-none">{art.file}</span>
                          <span className="text-[10px] font-mono text-on-surface-variant">Generated locally · Zero cloud · {art.doc_type?.toUpperCase()}</span>
                        </div>
                      </div>
                      <a
                        href={art.download_url}
                        download={art.file}
                        className="bg-primary-container text-white hover:bg-primary-container/80 border border-[#2d568c] px-3.5 py-1.5 rounded flex items-center gap-2 font-label-caps text-label-caps transition-colors"
                      >
                        <span className="material-symbols-outlined text-[16px]">download</span>
                        DOWNLOAD
                      </a>
                    </div>
                  </div>
                ))}

                {/* Sandbox File downloads */}
                {msg.sandboxResults?.map((res, i) => (
                  <div key={`sb-${i}`} className="bg-[#14171e] border border-[#262b35] p-4 rounded mt-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded bg-[#1c2331] border border-[#2d3a52] flex items-center justify-center text-primary">
                          <span className="material-symbols-outlined text-[18px]">code</span>
                        </div>
                        <div>
                          <span className="font-data-mono text-data-mono text-white font-medium block leading-none">{res.script_file}</span>
                          <span className="text-[10px] font-mono text-on-surface-variant">Generated locally · Executed in Sandbox</span>
                        </div>
                      </div>
                      <a
                        href={`/outputs/${res.script_file}`}
                        download={res.script_file}
                        className="bg-primary-container text-white hover:bg-primary-container/80 border border-[#2d568c] px-3.5 py-1.5 rounded flex items-center gap-2 font-label-caps text-label-caps transition-colors"
                      >
                        <span className="material-symbols-outlined text-[16px]">download</span>
                        DOWNLOAD CODE
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Terminal Input Bar */}
      <div className="p-4 bg-[#14171d] border-t border-[#262b35] flex-shrink-0">
        <div className="font-code-sm text-[11px] text-on-surface-variant mb-2 ml-1 flex items-center gap-2">
          <span className="material-symbols-outlined text-[14px] text-primary">moving</span>
          Routing to <span className="font-mono" style={{ color: routingColor }}>{routingModel}</span>
          {activePhases.length > 0 && <span className="text-tertiary">• Agent executing...</span>}
        </div>
        <div className="bg-[#1a1e27] border border-[#2d3545] rounded p-2 focus-within:border-primary transition-colors flex flex-col shadow-inner">
          {attachedFile && (
            <div className="relative mb-3 p-1 w-fit mt-1 ml-1 group">
              {attachedFile.type.startsWith('image/') ? (
                <img src={attachedFile.data} alt="attached" className="w-16 h-16 object-cover rounded-lg border border-[#2d3545] shadow-sm" />
              ) : (
                <div className="w-16 h-16 bg-[#14171d] rounded-lg border border-[#2d3545] flex flex-col items-center justify-center shadow-sm">
                  <span className="material-symbols-outlined text-[24px] text-primary">description</span>
                  <span className="text-[8px] font-mono mt-1 text-on-surface-variant truncate max-w-[50px]">{attachedFile.name.split('.').pop()}</span>
                </div>
              )}
              <button
                onClick={() => setAttachedFile(null)}
                className="absolute -top-2 -right-2 bg-[#2d3545] text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-error shadow-md"
              >
                <span className="material-symbols-outlined text-[14px] block">close</span>
              </button>
            </div>
          )}
          <textarea
            ref={inputRef}
            onPaste={handlePaste}
            className="w-full bg-transparent border-none focus:ring-0 text-on-surface font-body-lg resize-none min-h-[70px] p-2 placeholder-on-surface-variant/40 outline-none text-[14px]"
            placeholder="Enter industrial directive (e.g., generate inspection report for CDU-2, write LMTD calculator script)..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
            disabled={generating}
          />
          <div className="flex justify-between items-center mt-1 pt-2 border-t border-[#262b35]">
            <div className="flex items-center gap-2">
              <button onClick={() => fileInputRef.current?.click()} className="text-on-surface-variant hover:text-white p-1 rounded hover:bg-[#252c39] transition-colors" title="Attach file">
                <span className="material-symbols-outlined text-[20px]">attach_file</span>
              </button>
              <input type="file" ref={fileInputRef} className="hidden" onChange={(e) => handleFile(e.target.files[0])} accept="image/*,.pdf,.docx,.txt" />
              <select
                value={docType}
                onChange={e => setDocType(e.target.value)}
                className="bg-transparent border border-[#2d3545] text-on-surface-variant font-code-sm text-[11px] rounded px-2 py-1 outline-none"
              >
                <option value="report">Report (.docx)</option>
                <option value="script">Script (.py)</option>
                <option value="sop">SOP (.docx)</option>
                <option value="pptx">Slides (.pptx)</option>
                <option value="xlsx">Spreadsheet (.xlsx)</option>
              </select>
              <button
                onClick={generateDoc}
                disabled={generating || !input.trim()}
                className="text-on-surface-variant hover:text-tertiary p-1 rounded hover:bg-[#252c39] transition-colors disabled:opacity-40"
                title="Generate Document"
              >
                <span className="material-symbols-outlined text-[20px]">description</span>
              </button>
              <span className="text-[11px] font-mono text-on-surface-variant/60">Air-gapped</span>
            </div>
            <button
              onClick={sendMessage}
              disabled={generating || !input.trim()}
              className="bg-secondary-container text-on-secondary-fixed hover:bg-secondary-container/90 px-4 py-1.5 rounded flex items-center gap-2 font-label-caps text-label-caps transition-colors font-bold shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {generating
                ? <span className="w-4 h-4 border-2 border-t-transparent border-[#0d0f12] rounded-full animate-spin inline-block" />
                : <><span>EXECUTE</span><span className="material-symbols-outlined text-[16px]">send</span></>
              }
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
