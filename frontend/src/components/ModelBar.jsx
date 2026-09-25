const MODELS = [
  { key: 'reasoning', label: 'Phi-3.5 Mini',      color: '#6366f1', vram: '2.2 GB', role: 'Reasoning / Reports' },
  { key: 'code',      label: 'Qwen2.5-Coder 3B',  color: '#10b981', vram: '1.9 GB', role: 'Code / Calculations' },
  { key: 'vision',    label: 'Moondream 2',         color: '#f59e0b', vram: '1.1 GB', role: 'Vision / OCR' },
  { key: 'embed',     label: 'Nomic Embed',         color: '#8b5cf6', vram: 'CPU',    role: 'Embeddings / RAG' },
]

export default function ModelBar() {
  return (
    <div className="model-bar">
      <span className="model-bar-label">Models:</span>
      {MODELS.map(m => (
        <div className="model-chip" key={m.key} data-tip={m.role}>
          <span className="model-chip-dot" style={{ background: m.color, boxShadow: `0 0 6px ${m.color}88` }} />
          <span>{m.label}</span>
          <span className="model-chip-vram">{m.vram}</span>
        </div>
      ))}
      <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
        Total VRAM ≤ 4 GB (one model at a time)
      </span>
    </div>
  )
}
