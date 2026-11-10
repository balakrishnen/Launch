// ⌘K command palette: elements (server search), artifacts, pages and agent actions.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '../state'
import { FORMS, KIND_LABEL, MATRIX_PAIRS, STAGE_COLOR } from '../api'

type Hit = { section: string; label: string; sub?: string; color?: string; run: () => void }

export function Palette() {
  const { pid, palette, setPalette, project, send, openTab } = useProject(); const nav = useNavigate()
  const [q, setQ] = useState(''); const [hits, setHits] = useState<Hit[]>([]); const [sel, setSel] = useState(0); const inp = useRef<HTMLInputElement>(null)
  useEffect(() => { if (palette) { setQ(''); setSel(0); setTimeout(() => inp.current?.focus(), 20) } }, [palette])
  const go = (path: string) => { setPalette(false); nav(path) }
  const statics = useMemo<Hit[]>(() => {
    if (!project) return []
    const out: Hit[] = []
    out.push({ section: 'Pages', label: 'Overview', run: () => go(`/p/${pid}`) }, { section: 'Pages', label: 'Artifact library', run: () => go(`/p/${pid}/artifacts`) }, { section: 'Pages', label: 'Graph', run: () => go(`/p/${pid}/graph`) }, { section: 'Pages', label: 'Scorecard', run: () => go(`/p/${pid}/scorecard`) }, { section: 'Pages', label: 'Open gaps', run: () => go(`/p/${pid}/gaps`) }, { section: 'Pages', label: 'Review inbox', run: () => go(`/p/${pid}/inbox`) }, { section: 'Pages', label: 'Integrations (OSLC, tools)', run: () => go(`/p/${pid}/integrations`) }, { section: 'Pages', label: 'History & baselines', run: () => go(`/p/${pid}/history`) })
    for (const [k, s] of Object.entries(project.stage_of)) out.push({ section: 'Collections', label: KIND_LABEL[k] || k, sub: `${project.counts[k]} · ${s}`, color: STAGE_COLOR[s], run: () => go(`/p/${pid}/collection/${k}`) })
    for (const f of FORMS) out.push({ section: 'Artifacts', label: f.title, sub: f.std, color: STAGE_COLOR[f.stage], run: () => go(`/p/${pid}/form/${f.id}`) })
    for (const [a, b] of MATRIX_PAIRS) out.push({ section: 'Artifacts', label: `Matrix ${KIND_LABEL[a]} × ${KIND_LABEL[b]}`, run: () => go(`/p/${pid}/matrix/${a}/${b}`) })
    out.push({ section: 'Artifacts', label: 'Diagrams', run: () => go(`/p/${pid}/views`) }, { section: 'Artifacts', label: 'Design documentation', run: () => go(`/p/${pid}/docs`) }, { section: 'Artifacts', label: 'SysML v2 text', run: () => go(`/p/${pid}/sysml`) })
    for (const r of project.role_order) out.push({ section: 'Agent', label: `Run ${project.roles[r]}`, run: () => { setPalette(false); send('', r) } })
    out.push({ section: 'Agent', label: 'Close the open trace gaps', run: () => { setPalette(false); send('Close the open trace gaps in order of leverage, in reviewable patches') } })
    out.push({ section: 'Agent', label: 'Assess all unassessed failure modes', run: () => { setPalette(false); send('Assess or screen every unassessed failure-mode candidate with causes derived from the architecture, S/O/D with AP, controls and tests') } })
    return out
  }, [project, pid])
  useEffect(() => {
    const ql = q.trim().toLowerCase(); let alive = true
    const local = statics.filter(h => !ql || (h.label + ' ' + (h.sub || '')).toLowerCase().includes(ql)).slice(0, ql ? 12 : 40)
    if (!ql) { setHits(local); return }
    fetch(`/api/p/${pid}/search?q=${encodeURIComponent(ql)}`).then(r => r.json()).then((rows: any[]) => { if (!alive) return
      const el: Hit[] = rows.slice(0, 30).map(h => ({ section: 'Elements', label: `${h.id}  ${h.name || ''}`, sub: KIND_LABEL[h.kind] || h.kind, color: STAGE_COLOR[project?.stage_of[h.kind] || ''], run: () => { setPalette(false); openTab({ key: `el:${h.kind}:${h.id}`, title: h.id, path: `/p/${pid}/element/${h.kind}/${encodeURIComponent(h.id)}`, stage: project?.stage_of[h.kind] }) } }))
      const ask: Hit = { section: 'Agent', label: `Ask the agent: “${q}”`, run: () => { setPalette(false); send(q) } }
      setHits([...el, ...local, ask]); setSel(0) }).catch(() => setHits(local))
    return () => { alive = false }
  }, [q, statics, pid])
  if (!palette) return null
  const onKey = (e: React.KeyboardEvent) => { if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(s + 1, hits.length - 1)) } if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(s - 1, 0)) } if (e.key === 'Enter') { hits[sel]?.run() } if (e.key === 'Escape') setPalette(false) }
  let lastSection = ''
  return <div className="overlay" onMouseDown={() => setPalette(false)}>
    <div className="palette" onMouseDown={e => e.stopPropagation()}>
      <input ref={inp} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} placeholder="Search elements, artifacts, pages… or type a request for the agent" />
      <div className="list">{hits.map((h, i) => { const sect = h.section !== lastSection ? h.section : ''; lastSection = h.section
        return <div key={i}>{sect && <div className="sect">{sect}</div>}<div className={'hit' + (i === sel ? ' sel' : '')} onMouseEnter={() => setSel(i)} onClick={h.run}>{h.color && <span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: h.color, flex: 'none' }} />}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.label}</span>{h.sub && <span className="k">{h.sub}</span>}</div></div> })}
        {hits.length === 0 && <div className="empty">No matches</div>}</div>
    </div>
  </div>
}
