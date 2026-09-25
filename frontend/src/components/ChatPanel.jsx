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
      className="text-[11px] font-medium text-text-secondary hover:text-text-primary px-2 py-1 rounded-md bg-surface-inset hover:bg-border transition-colors flex items-center gap-1"
    >
      <span className="material-symbols-outlined text-[14px]">{copied ? 'check' : 'content_copy'}</span>
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

const mdComponents = {
  h1: ({ children }) => <h1 className="text-text-primary font-bold text-[20px] mt-5 mb-3 font-headline-md">{children}</h1>,
  h2: ({ children }) => <h2 className="text-text-primary font-semibold text-[17px] mt-4 mb-2 font-headline-sm">{children}</h2>,
  h3: ({ children }) => <h3 className="text-text-primary font-medium text-[15px] mt-3 mb-2">{children}</h3>,
  p:  ({ children }) => <p className="mb-3 text-[15px] text-black leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 pl-5 space-y-1 list-disc text-black">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 pl-5 space-y-1 list-decimal text-black">{children}</ol>,
  li: ({ children }) => <li className="text-[14.5px] leading-relaxed text-black">{children}</li>,
  strong: ({ children }) => <strong className="text-text-primary font-semibold">{children}</strong>,
  em: ({ children }) => <em className="text-text-primary italic">{children}</em>,
  code: ({ inline, children, className }) => {
    if (inline) {
      return <code className="bg-surface-inset text-text-primary px-1.5 py-0.5 rounded-md font-mono text-[13px] border border-border">{children}</code>
    }
    const lang = (className || '').replace('language-', '') || 'code'
    const rawText = String(children).replace(/\n$/, '')
    return (
      <div className="my-4 rounded-xl border border-border overflow-hidden shadow-sm">
        <div className="flex items-center justify-between bg-surface-card px-4 py-2 border-b border-border">
          <span className="font-mono text-[11px] text-text-secondary uppercase tracking-wider">{lang}</span>
          <CopyBtn text={rawText} />
        </div>
        <pre className="bg-surface-inset p-4 overflow-x-auto text-[13px] leading-relaxed font-mono text-text-primary m-0">
          <code>{children}</code>
        </pre>
      </div>
    )
  },
  blockquote: ({ children }) => <blockquote className="border-l-4 border-border pl-4 my-3 text-text-secondary italic">{children}</blockquote>,
  table: ({ children }) => <div className="overflow-x-auto my-4 rounded-xl border border-border shadow-sm"><table className="w-full text-[14px] border-collapse bg-white">{children}</table></div>,
  th: ({ children }) => <th className="bg-surface-inset text-text-primary font-semibold text-[13px] px-4 py-2.5 border-b border-border text-left">{children}</th>,
  td: ({ children }) => <td className="px-4 py-2.5 border-b border-border text-text-secondary text-[14px]">{children}</td>,
  hr: () => <hr className="border-border my-6" />,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-info underline hover:text-blue-600 transition-colors">{children}</a>,
}

function MarkdownContent({ content }) {
  return (
    <div className="text-[15px] leading-relaxed katex-render text-text-primary">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={mdComponents}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

const PRESET_PILLS = [
  'Generate Summary', 'Detailed Analysis', 'Safety Audit', 'Code Generation', 
  'Extract Data', 'Simple', 'Formal', 'Technical', 'Report'
]

export default function ChatPanel({ session, onActiveModelChange }) {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(`chat_messages_${session.id}`)
      if (saved) return JSON.parse(saved)
    } catch (e) {}
    return []
  })

  useEffect(() => {
    localStorage.setItem(`chat_messages_${session.id}`, JSON.stringify(messages))
  }, [messages, session.id])
  const [input, setInput] = useState('')
  const [generating, setGenerating] = useState(false)
  const [docType, setDocType] = useState('report')
  const [attachedFile, setAttachedFile] = useState(null)
  const bottomRef = useRef(null)
  const messagesScrollRef = useRef(null)
  const shouldAutoScrollRef = useRef(true)
  const abortControllerRef = useRef(null)
  const stoppedByUserRef = useRef(false)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    // Do not force the reader back to the newest token while they are
    // reviewing an earlier part of a streaming answer.
    if (shouldAutoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'auto' })
    }
  }, [messages])

  const handleMessagesScroll = (event) => {
    const pane = event.currentTarget
    const distanceFromBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight
    shouldAutoScrollRef.current = distanceFromBottom < 96
  }

  const stopGeneration = () => {
    if (!generating) return
    stoppedByUserRef.current = true
    abortControllerRef.current?.abort()
  }

  const handlePaste = (e) => {
    if (e.clipboardData.files.length > 0) handleFile(e.clipboardData.files[0])
  }

  const handleFile = (file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => setAttachedFile({ name: file.name, data: e.target.result, type: file.type })
    reader.readAsDataURL(file)
  }

  const sendMessage = async (textOverride) => {
    const text = (textOverride || input).trim()
    if (!text || generating) return

    const currentAttachment = attachedFile
    setAttachedFile(null)
    shouldAutoScrollRef.current = true
    stoppedByUserRef.current = false

    const userMsg = { id: Date.now(), role: 'user', content: text, attachment: currentAttachment }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setGenerating(true)

    const aiId = Date.now() + 1
    setMessages(prev => [...prev, {
      id: aiId, role: 'ai', content: '', streaming: true,
      model: 'Phi-3.5 Mini', tokens: 0, latency: 0, phases: [], artifacts: [], sandboxResults: [],
    }])

    const controller = new AbortController()
    abortControllerRef.current = controller
    let idleTimer
    const armIdleTimeout = () => {
      window.clearTimeout(idleTimer)
      // A healthy SSE request immediately emits metadata/progress. If a Vite
      // or backend restart leaves an old browser stream hanging, recover the
      // composer instead of showing "Processing..." forever.
      idleTimer = window.setTimeout(() => controller.abort(), 45000)
    }

    armIdleTimeout()
    try {
      const body = { message: text }
      if (currentAttachment?.type?.startsWith('image/')) {
        body.images = [currentAttachment.data.split(',')[1]]
      } else if (currentAttachment?.type === 'application/pdf') {
        body.pdf = currentAttachment.data.split(',')[1]
      }

      const resp = await fetch('/api/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!resp.ok) {
        throw new Error(`Local service returned HTTP ${resp.status}`)
      }
      if (!resp.body) {
        throw new Error('Local service did not return a response stream')
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let tokens = 0, latency = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        armIdleTimeout()
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'meta' || data.type === 'phase') {
              if (data.model_display) {
                onActiveModelChange?.(data.model_display)
                setMessages(prev => prev.map(m => m.id === aiId ? { ...m, model: data.model_display } : m))
              }
              if (data.type === 'phase') {
                setMessages(prev => prev.map(m => m.id === aiId ? { ...m, phases: [...m.phases, data.phase] } : m))
              }
            } else if (data.type === 'token') {
              setMessages(prev => prev.map(m => m.id === aiId ? { ...m, content: m.content + data.text } : m))
            } else if (data.type === 'artifact') {
              setMessages(prev => prev.map(m => m.id === aiId ? { ...m, artifacts: [...m.artifacts, data] } : m))
            } else if (data.type === 'phase_result' && data.phase === 'execute') {
              setMessages(prev => prev.map(m => m.id === aiId ? { ...m, sandboxResults: [...m.sandboxResults, data] } : m))
            } else if (data.type === 'done') {
              tokens = data.tokens; latency = data.latency_ms
            } else if (data.type === 'error') {
              setMessages(prev => prev.map(m => m.id === aiId ? { ...m, content: `**Error:** ${data.message}`, streaming: false } : m))
            }
          } catch {}
        }
      }
      setMessages(prev => prev.map(m => m.id === aiId ? { ...m, streaming: false, tokens, latency } : m))
    } catch (e) {
      const wasStoppedByUser = e.name === 'AbortError' && stoppedByUserRef.current
      const message = e.name === 'AbortError'
        ? (wasStoppedByUser
          ? 'Generation stopped locally.'
          : 'The local service stopped responding. The server may have restarted; please send the prompt again.')
        : e.message
      setMessages(prev => prev.map(m => m.id === aiId ? {
        ...m,
        // Keep everything already received when the user deliberately stops
        // a stream; replacing it with an error would make Stop destructive.
        content: wasStoppedByUser
          ? `${m.content}${m.content ? '\n\n' : ''}> Generation stopped locally.`
          : `**Error:** ${message}`,
        streaming: false,
      } : m))
    } finally {
      window.clearTimeout(idleTimer)
      if (abortControllerRef.current === controller) abortControllerRef.current = null
      setGenerating(false)
    }
  }

  const generateDoc = () => {
    const text = input.trim()
    if (!text || generating) return
    const requestPrefix = {
      report: 'Create an evidence-grounded inspection report as a Word document. ',
      script: 'Create a Python file. ',
    }[docType] || 'Create an evidence-grounded Word document. '
    // Use the agent workflow so attachments, RAG citations, and the evidence
    // gate are preserved; the legacy direct document endpoint has no context.
    sendMessage(`${requestPrefix}${text}`)
  }

  return (
    <section className="flex-1 flex flex-col bg-surface min-w-0 relative">
      
      {/* Scrollable messages area */}
      <div ref={messagesScrollRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto overscroll-contain px-4 sm:px-12 pt-8 pb-32">
        {messages.length === 0 ? (
          <div className="max-w-4xl mx-auto mt-6 animate-fade-in-up">
            {/* Status Banner */}
            <div className="bg-surface-card border border-border rounded-2xl p-4 flex items-center justify-between shadow-sm mb-8">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-surface-inset flex items-center justify-center border border-border">
                  <span className="material-symbols-outlined text-[20px] text-text-primary">shield_lock</span>
                </div>
                <div>
                  <h3 className="text-[15px] font-semibold text-text-primary">Air-gapped Mode Verified</h3>
                  <p className="text-[13px] text-text-secondary mt-0.5">Connected to local edge cluster. Zero external telemetry.</p>
                </div>
              </div>
              <div className="px-3 py-1.5 bg-accent-container text-accent-text rounded-full text-[12px] font-medium flex items-center gap-1.5 border border-accent/20">
                <span className="material-symbols-outlined text-[14px]">check</span> Node Connected
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Saved Prompts */}
              <div className="bg-surface-card border border-border rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2 text-text-primary font-medium">
                    <span className="material-symbols-outlined text-[18px]">edit_note</span>
                    Your saved prompts
                  </div>
                  <button className="text-[12px] font-medium text-text-secondary hover:text-text-primary flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">add</span> Add prompt
                  </button>
                </div>
                <div className="space-y-3">
                  {['Summarize this long text into a short, professional paragraph that highlights only the key insights.',
                    'Generate an inspection report for CDU-2 heat exchanger E-201',
                    'Write a Python script for LMTD calculation based on process data.'].map((p, i) => (
                    <button key={i} onClick={() => setInput(p)} className="w-full text-left p-4 rounded-xl border border-border hover:border-accent hover:shadow-sm transition-all bg-white text-[13px] text-text-secondary leading-relaxed group">
                      <span className="group-hover:text-text-primary transition-colors">{p}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Output Tags */}
              <div className="bg-surface-card border border-border rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2 text-text-primary font-medium">
                    <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
                    Quick Actions
                  </div>
                  <button className="text-[12px] font-medium text-text-secondary hover:text-text-primary flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">add</span> Add custom
                  </button>
                </div>
                <div className="flex flex-wrap gap-2.5">
                  {PRESET_PILLS.map((pill, i) => (
                    <button key={i} onClick={() => sendMessage(pill)} className={`px-4 py-2 rounded-full text-[13px] font-medium transition-all ${
                      i < 4 ? 'bg-[#f0e6ff] text-[#6b21a8] hover:bg-[#e9d5ff]' : 'bg-surface-inset text-text-secondary hover:bg-border hover:text-text-primary'
                    }`}>
                      {pill}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-8">
            {messages.map(msg => (
              <div key={msg.id} className="animate-fade-in-up">
                {msg.role === 'user' ? (
                  <div className="flex justify-end">
                    <div className="bg-dark text-white px-5 py-3.5 rounded-2xl rounded-tr-sm max-w-[85%] font-body-lg text-[15px] shadow-sm flex flex-col gap-3">
                      {msg.attachment?.type?.startsWith('image/') && (
                        <img src={msg.attachment.data} alt="uploaded" className="max-w-[280px] rounded-lg border border-white/20 object-contain" />
                      )}
                      {msg.attachment?.type === 'application/pdf' && (
                        <div className="flex items-center gap-2 text-[13px] bg-white/10 rounded-lg px-3 py-2">
                          <span className="material-symbols-outlined text-[18px]">picture_as_pdf</span>
                          {msg.attachment.name}
                        </div>
                      )}
                      <span>{msg.content}</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col max-w-[95%]">
                    <div className="flex items-center gap-3 mb-2 px-1">
                      <div className="w-8 h-8 rounded-full bg-surface-card border border-border flex items-center justify-center shadow-sm">
                        <span className="material-symbols-outlined text-[18px] text-accent-text">hub</span>
                      </div>
                      <span className="font-semibold text-text-primary text-[14px]">LocalHost.Ai</span>
                      
                      {msg.phases?.map((phase, i) => (
                         <span key={i} className="ml-2 text-[11px] px-2 py-0.5 rounded-full bg-surface-inset border border-border text-text-secondary flex items-center gap-1">
                           <span className="material-symbols-outlined text-[12px]">check</span> {phase}
                         </span>
                      ))}
                    </div>

                    <div className="bg-surface-card border border-border rounded-2xl rounded-tl-sm p-5 shadow-sm">
                      {msg.content ? <MarkdownContent content={msg.content} /> : <span className="text-text-secondary text-[14px] italic">Processing...</span>}
                      {msg.streaming && <span className="cursor-blink" />}
                    </div>

                    {/* Artifacts / Downloads */}
                    {(msg.artifacts?.length > 0 || msg.sandboxResults?.length > 0) && (
                      <div className="mt-3 flex flex-wrap gap-3 pl-1">
                        {msg.artifacts?.map((art, i) => (
                          <a key={i} href={art.download_url} download={art.file} className="flex items-center gap-3 bg-surface-card border border-border hover:border-accent hover:shadow-sm transition-all px-4 py-2.5 rounded-xl group cursor-pointer">
                            <span className="material-symbols-outlined text-[20px] text-accent-text">description</span>
                            <div>
                              <div className="font-medium text-[13px] text-text-primary">{art.file}</div>
                              <div className="text-[11px] text-text-secondary">Click to download</div>
                            </div>
                            <span className="material-symbols-outlined text-[18px] text-text-tertiary group-hover:text-accent-text ml-2">download</span>
                          </a>
                        ))}
                        {msg.sandboxResults?.map((res, i) => (
                          <a key={`sb-${i}`} href={`/outputs/${res.script_file}`} download={res.script_file} className="flex items-center gap-3 bg-surface-card border border-border hover:border-accent hover:shadow-sm transition-all px-4 py-2.5 rounded-xl group cursor-pointer">
                            <span className="material-symbols-outlined text-[20px] text-info">code</span>
                            <div>
                              <div className="font-medium text-[13px] text-text-primary">{res.script_file}</div>
                              <div className="text-[11px] text-text-secondary">Generated Script</div>
                            </div>
                            <span className="material-symbols-outlined text-[18px] text-text-tertiary group-hover:text-info ml-2">download</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Floating Input Area */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[90%] max-w-3xl z-20">
        <div className="bg-surface-card rounded-full border border-border input-float-shadow flex items-center pr-2 pl-4 py-2 relative">
          
          {/* Attachment Preview (Floats above) */}
          {attachedFile && (
            <div className="absolute -top-16 left-4 bg-surface-card border border-border rounded-xl p-2 shadow-sm flex items-center gap-3 animate-fade-in-up">
              {attachedFile.type.startsWith('image/') ? (
                <img src={attachedFile.data} alt="attached" className="w-10 h-10 object-cover rounded-lg border border-border" />
              ) : (
                <div className="w-10 h-10 bg-surface-inset rounded-lg flex items-center justify-center">
                  <span className="material-symbols-outlined text-[20px] text-text-secondary">description</span>
                </div>
              )}
              <div className="flex flex-col mr-2">
                <span className="text-[12px] font-medium text-text-primary truncate max-w-[120px]">{attachedFile.name}</span>
              </div>
              <button onClick={() => setAttachedFile(null)} className="p-1 hover:bg-surface-inset rounded-full text-text-tertiary hover:text-error transition-colors">
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            </div>
          )}

          <button onClick={() => fileInputRef.current?.click()} className="p-2.5 text-text-secondary hover:text-text-primary hover:bg-surface-inset rounded-full transition-colors flex-shrink-0" title="Attach file">
            <span className="material-symbols-outlined text-[22px]">attach_file</span>
          </button>
          <input type="file" ref={fileInputRef} className="hidden" onChange={(e) => handleFile(e.target.files[0])} accept="image/*,.pdf,.docx,.txt" />
          
          <input
            ref={inputRef}
            onPaste={handlePaste}
            className="flex-1 bg-transparent border-none focus:ring-0 text-text-primary text-[15px] px-3 py-3 outline-none placeholder-text-tertiary"
            placeholder="Type your prompt here..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
            disabled={generating}
          />
          
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {/* Generate Doc Dropdown trigger (simplified for clean UI) */}
            <div className="relative group">
               <button onClick={generateDoc} disabled={generating || !input.trim()} className="p-2.5 text-text-secondary hover:text-text-primary hover:bg-surface-inset rounded-full transition-colors disabled:opacity-50" title="Generate Document">
                 <span className="material-symbols-outlined text-[22px]">auto_stories</span>
               </button>
               {/* Hidden select mapped to docType for functionality preservation */}
               <select value={docType} onChange={e => setDocType(e.target.value)} className="absolute opacity-0 inset-0 cursor-pointer w-full" title="Select Doc Type">
                  <option value="report">Report (.docx)</option>
                  <option value="script">Script (.py)</option>
               </select>
            </div>

            <button className="p-2.5 text-text-secondary hover:text-text-primary hover:bg-surface-inset rounded-full transition-colors flex-shrink-0">
              <span className="material-symbols-outlined text-[22px]">mic</span>
            </button>
            
            {generating ? (
              <button
                onClick={stopGeneration}
                className="ml-1 h-10 px-3 rounded-full bg-error text-white hover:bg-red-700 flex items-center gap-1.5 transition-colors shadow-sm text-[12px] font-semibold"
                title="Stop generating"
              >
                <span className="material-symbols-outlined text-[18px]">stop_circle</span>
                Stop
              </button>
            ) : (
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim()}
                className="ml-1 w-10 h-10 rounded-full bg-accent hover:bg-accent-hover text-accent-text flex items-center justify-center transition-colors disabled:opacity-50 shadow-sm"
                title="Send message"
              >
                <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
