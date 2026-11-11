// Live SysML v2 diagram: SVG from the server; every node carries data-el="kind:id" so a click opens the record.
import { useEffect, useRef, useState } from 'react'
import { Maximize2, Code2 } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'

export function SysmlDiagram({ path, title, height = 380, showText = true }: { path: string; title?: string; height?: number; showText?: boolean }) {
  const { pid, openTab, project, patches } = useProject()
  const [d, setD] = useState<any>(null); const [err, setErr] = useState(''); const [big, setBig] = useState(false); const [text, setText] = useState(false); const box = useRef<HTMLDivElement>(null)
  useEffect(() => { setD(null); setErr(''); P(pid).get(path).then(async (x: any) => { if (!x.svg && x.dot) { try { x = { ...x, svg: await renderDot(x.dot) } } catch (e: any) { setErr('diagram: ' + e.message); return } } setD(x) }).catch(e => setErr(e.message)) }, [pid, path, patches.length, project?.meta?.rev])
  useEffect(() => { const el = box.current; if (!el) return
    const h = (e: MouseEvent) => { const a = (e.target as HTMLElement).closest('a[data-el]') as HTMLElement | null; if (!a) return; e.preventDefault(); e.stopPropagation(); const [kind, ...rest] = a.dataset.el!.split(':'); const id = rest.join(':'); openTab({ key: `el:${kind}:${id}`, title: id, path: `/p/${pid}/element/${kind}/${encodeURIComponent(id)}`, stage: project?.stage_of?.[kind] || '' }) }
    el.addEventListener('click', h); return () => el.removeEventListener('click', h) }, [pid, d])
  if (err) return <div className="empty">{err}</div>
  if (!d) return <div className="empty" style={{ height }}>Rendering SysML v2 view…</div>
  const body = <div className="diagram" ref={box} style={{ height: big ? 'calc(100vh - 120px)' : height }} dangerouslySetInnerHTML={{ __html: d.svg }} />
  return <div className={'card dgcard' + (big ? ' big' : '')}>
    <div className="row between" style={{ marginBottom: 6 }}><div><h4 style={{ margin: 0 }}>{title || d.title || 'SysML v2'} <span className="pill" style={{ fontSize: 10 }}>{d.view || 'view'}</span></h4><div className="muted small">SysML v2 notation · click any element to open its record</div></div>
      <div className="row">{showText && d.text && <button className="btn ghost sm" onClick={() => setText(t => !t)} title="SysML v2 text"><Code2 size={14} /></button>}<button className="btn ghost sm" onClick={() => setBig(b => !b)} title="expand"><Maximize2 size={14} /></button></div></div>
    {body}
    {text && d.text && <pre className="diff" style={{ marginTop: 8, maxHeight: 260 }}>{d.text}</pre>}
  </div>
}

// Client-side Graphviz (review build / offline): viz.js WASM from jsDelivr, loaded once.
let vizP: Promise<any> | null = null
async function renderDot(dot: string): Promise<string> {
  if (!vizP) vizP = new Promise((res, rej) => { if ((window as any).Viz) return res((window as any).Viz); const s = document.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/@viz-js/viz@3.28.0/lib/viz-standalone.js'; s.onload = () => res((window as any).Viz); s.onerror = () => rej(new Error('could not load viz.js')); document.head.appendChild(s) })
  const Viz = await vizP; const viz = await Viz.instance(); let svg: string = viz.renderString(dot, { format: 'svg' })
  svg = svg.replace(/<\?xml.*?\?>\s*/s, '').replace(/<!DOCTYPE.*?>\s*/s, '').replace(/<svg width="([\d.]+)pt" height="([\d.]+)pt"/, (_m, w, h) => `<svg width="${Math.round(+w * 1.25)}" height="${Math.round(+h * 1.25)}"`)
  return svg.replace(/xlink:href="#el:/g, 'data-el="').replace(/xlink:title/g, 'data-title')
}