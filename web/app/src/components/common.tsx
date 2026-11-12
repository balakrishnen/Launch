import React from 'react'
import { useNavigate } from 'react-router-dom'
import { ID_RE, KIND_LABEL, stageColor, stageInk } from '../api'
import { useProject } from '../state'

export const esc = (s: unknown) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))

/** Text with element ids turned into links (R-012 → /element). Kind is resolved from the project graph lazily. */
export function Linkified({ text }: { text: string }) {
  const parts: React.ReactNode[] = []; let last = 0; const s = String(text ?? '')
  for (const m of s.matchAll(ID_RE)) { parts.push(s.slice(last, m.index)); parts.push(<IdLink key={m.index} id={m[0]} />); last = m.index! + m[0].length }
  parts.push(s.slice(last)); return <>{parts}</>
}
export function IdLink({ id, kind, children }: { id: string; kind?: string; children?: React.ReactNode }) {
  const nav = useNavigate(); const { pid, openTab } = useProject()
  const go = async (e: React.MouseEvent) => { e.preventDefault(); e.stopPropagation(); let k = kind
    if (!k) { try { const hits = await fetch(`/api/p/${pid}/search?q=${encodeURIComponent(id)}`).then(r => r.json()); k = (hits.find((h: any) => h.id === id) || {}).kind } catch { } }
    if (!k && id.startsWith('FM-')) k = 'fmea'
    if (!k) { nav(`/p/${pid}/search/${encodeURIComponent(id)}`); return }
    openTab({ key: `el:${k}:${id}`, title: id, path: `/p/${pid}/element/${k}/${encodeURIComponent(id)}`, stage: '' }) }
  return <a className="id" href="#" onClick={go}>{children ?? id}</a>
}
export function StagePill({ stage }: { stage?: string }) { if (!stage) return null; return <span className="pill stage" style={{ background: stageColor(stage), color: stageInk(stage) }}>{stage}</span> }
export function KindLabel({ kind }: { kind: string }) { return <>{KIND_LABEL[kind] || kind.replace(/_/g, ' ')}</> }
export function Cell({ v, col }: { v: any; col?: string }) {
  if (col === 'AP' || col === 'DFMEA AP') return <span className={'ap-' + v}>{v}</span>
  if (Array.isArray(v)) return <>{v.map((x, i) => <React.Fragment key={i}>{i > 0 && ', '}{typeof x === 'object' ? JSON.stringify(x) : <Linkified text={String(x)} />}</React.Fragment>)}{v.length === 0 && <span className="muted">—</span>}</>
  if (v && typeof v === 'object') return <span className="small">{Object.entries(v).map(([k, x]) => `${k}=${typeof x === 'object' ? JSON.stringify(x) : x}`).join('; ')}</span>
  if (v === null || v === undefined || v === '') return <span className="muted">—</span>
  return <Linkified text={String(v)} />
}
export function Bar({ v }: { v: number }) { const c = v >= 90 ? 'var(--good)' : v >= 65 ? 'var(--warn)' : 'var(--bad)'; return <div className="bar"><i style={{ width: `${v}%`, background: c }} /></div> }
export function Spinner() { return <span className="spinner" /> }


// The product visual: meta.image (files/product/*.svg|png) served by the project; in the static review build the snapshot inlines it.
export function ProductVisual({ pid, image, size = 120, inline }: { pid: string; image?: string | null; size?: number; inline?: string | null }) {
  const base = (import.meta as any).env?.VITE_REVIEW ? null : ''
  if (inline) return <div className="pv" style={{ width: size, height: size * 0.75 }} dangerouslySetInnerHTML={{ __html: inline }} />
  if (!image) return <div className="pv pv-empty" style={{ width: size, height: size * 0.75 }}><span className="muted small">no visual</span></div>
  const src = image.startsWith('data:') ? image : `${base ?? ''}/p/${pid}/${image}`
  return <div className="pv" style={{ width: size, height: size * 0.75 }}><img src={src} alt="" style={{ maxWidth: '100%', maxHeight: '100%' }} /></div>
}
