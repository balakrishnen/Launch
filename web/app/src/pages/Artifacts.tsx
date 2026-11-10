// Artifact library: every generated artifact of the project as a filterable catalogue — forms, matrices, diagrams, documents,
// SysML packages — with type, stage and freshness. This is the page that scales to hundreds of artifacts.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProject } from '../state'
import { P, FORMS, MATRIX_PAIRS, KIND_LABEL, STAGE_COLOR, type Form } from '../api'
import { Grid } from '../components/Grid'
import { marked } from 'marked'

type Art = { id: string; title: string; type: string; stage: string; sub: string; path: string; fresh?: string }

export function Artifacts() {
  const { pid, project } = useProject(); const nav = useNavigate()
  const [art, setArt] = useState<any>(null); const [q, setQ] = useState(''); const [type, setType] = useState(''); const [stage, setStage] = useState('')
  useEffect(() => { P(pid).get('/artifacts').then(setArt).catch(() => { }) }, [pid, project?.meta?.rev])
  const items = useMemo<Art[]>(() => {
    const out: Art[] = []
    for (const f of FORMS) out.push({ id: 'form:' + f.id, title: f.title, type: 'Form', stage: f.stage, sub: f.std, path: `/p/${pid}/form/${f.id}`, fresh: 'live' })
    for (const [a, b] of MATRIX_PAIRS) out.push({ id: `mx:${a}:${b}`, title: `${KIND_LABEL[a]} × ${KIND_LABEL[b]}`, type: 'Matrix', stage: project?.stage_of[b] || '', sub: 'dependency matrix', path: `/p/${pid}/matrix/${a}/${b}`, fresh: 'live' })
    for (const v of art?.views || []) out.push({ id: 'view:' + v, title: v.replace('.png', '').replace(/^V\d+_/, '').replace(/_/g, ' '), type: 'Diagram', stage: viewStage(v), sub: v, path: `/p/${pid}/views#${v}`, fresh: 'built' })
    for (const s of art?.sysml || []) out.push({ id: 'sysml:' + s, title: s.replace('.sysml', '').replace(/^\d+_/, '').replace(/_/g, ' '), type: 'SysML v2', stage: '', sub: s, path: `/p/${pid}/sysml#${s}`, fresh: 'built' })
    if (art?.docs?.length) out.push({ id: 'docs', title: 'System design documentation', type: 'Document', stage: '', sub: 'OOSEM-ordered, every table with provenance', path: `/p/${pid}/docs`, fresh: 'built' })
    for (const d of art?.docx || []) out.push({ id: 'docx:' + d, title: d, type: 'Document', stage: '', sub: 'Word export', path: `/p/${pid}/out/${d}`, fresh: 'built' })
    for (const d of art?.documents || []) out.push({ id: 'src:' + d, title: d, type: 'Source document', stage: '1 Needs', sub: 'uploaded input', path: `/api/p/${pid}/file?path=docs/${encodeURIComponent(d)}` })
    for (const [k, s] of Object.entries(project?.stage_of || {})) if (k !== 'fm_assessments') out.push({ id: 'col:' + k, title: KIND_LABEL[k], type: 'Collection', stage: s, sub: `${project?.counts[k]} elements`, path: `/p/${pid}/collection/${k}`, fresh: 'live' })
    return out
  }, [art, project, pid])
  const types = [...new Set(items.map(i => i.type))]; const stages = [...new Set(items.map(i => i.stage).filter(Boolean))].sort()
  const view = items.filter(i => (!type || i.type === type) && (!stage || i.stage === stage) && (!q || (i.title + ' ' + i.sub + ' ' + i.type).toLowerCase().includes(q.toLowerCase())))
  const go = (a: Art) => { if (a.path.startsWith('/api') || a.path.endsWith('.docx')) window.open(a.path, '_blank'); else nav(a.path) }
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Artifact library <span className="pill">{view.length}</span></h2><div className="muted small">Every artifact of this project, generated from one model. Forms and matrices are live; diagrams and documents are rebuilt by <b>Build artifacts</b>.</div></div>
      <input className="field" style={{ width: 280 }} placeholder="search artifacts…" value={q} onChange={e => setQ(e.target.value)} /></div>
    <div className="row" style={{ marginBottom: 14 }}>
      <button className="chip" style={!type ? sel : {}} onClick={() => setType('')}>All types</button>{types.map(t => <button key={t} className="chip" style={type === t ? sel : {}} onClick={() => setType(t)}>{t}</button>)}
      <span style={{ width: 12 }} />{stages.map(s => <button key={s} className="chip" style={stage === s ? sel : {}} onClick={() => setStage(stage === s ? '' : s)}><span className="sw" style={{ width: 7, height: 7, borderRadius: 2, background: STAGE_COLOR[s] }} />{s}</button>)}</div>
    <div className="gallery" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))' }}>{view.map(a => <div key={a.id} className="artcard" onClick={() => go(a)}>
      <div className="row between"><span className="pill">{a.type}</span>{a.fresh && <span className={'pill ' + (a.fresh === 'live' ? 'good' : '')}>{a.fresh}</span>}</div>
      <div className="t">{a.title}</div><div className="d">{a.sub}</div>{a.stage && <div className="row small" style={{ gap: 6, marginTop: 'auto' }}><span className="sw" style={{ width: 7, height: 7, borderRadius: 2, background: STAGE_COLOR[a.stage] }} /><span className="muted">{a.stage}</span></div>}</div>)}</div>
  </div>
}
const sel = { borderColor: 'var(--accent)', color: 'var(--accent-ink)', background: 'var(--accent-soft)' }
function viewStage(v: string) { const n = parseInt(v.slice(1, 3)); return n <= 2 ? '1 Needs' : n <= 4 ? '2 Requirements' : n <= 6 ? '3 Logical architecture' : n <= 11 ? '4 Physical architecture' : n === 12 ? '5 Analysis' : n === 13 ? 'Risk (derived)' : '6 Verification' }

export function FormPage() {
  const { name = '' } = useParams(); const { pid, send, patches, project, openTab } = useProject(); const [form, setForm] = useState<Form | null>(null); const [showRatings, setShowRatings] = useState(false)
  const load = () => P(pid).get('/form/' + name).then(setForm).catch(() => setForm(null))
  useEffect(() => { load() }, [pid, name, patches.length, project?.meta?.rev])
  useEffect(() => { const f = FORMS.find(f => f.id === name); if (f) openTab({ key: 'form:' + name, title: f.title, path: `/p/${pid}/form/${name}`, stage: f.stage }) }, [name])
  const ask: Record<string, string> = { dfmea: 'Assess or screen every remaining failure-mode candidate (fmea_candidates), causes derived from the architecture, S/O/D with AP, prevention controls and verifying tests', dvpr: 'Complete every test: method with standard and severity, sample size, gate, numeric pass/fail', vcrm: 'Close every requirement without a verifying test', reqspec: 'Make every requirement testable: a measurable attribute, a verification method and a test', hazards: 'Review the hazard register: every S≥9 mode needs a prevention control and a test', n2: 'Review the N² matrix: every pair of parts that touch or exchange energy/data needs an interface; propose the missing ones', icd: 'Complete the ICD characteristics for every interface from datasheets; mark assumptions', pugh: 'Fill weights, scores and a datum for every trade study from the requirements each criterion traces to', fta: 'Review the fault trees: every top event needs two independent barriers; propose missing controls and tests', drbfm: 'Run a DRBFM on each architecture decision: concerns from the change, affected functions, tests to re-run' }
  if (!form) return <div className="empty">Loading…</div>
  return <div>
    <div className="row between" style={{ marginBottom: 4 }}><div><h2>{form.title} <span className="pill">{form.rows.length}</span></h2><div className="muted small">{form.standard} · generated from the model · {form.editable ? 'click a cell to edit; edits become a logged patch' : 'read-only view'}</div></div>
      <div className="row">{form.rating_tables && <button className="btn sm" onClick={() => setShowRatings(v => !v)}>Rating tables</button>}<button className="btn sm" onClick={() => send(ask[name] || `Improve the ${form.title}`)}>▶ Ask the agent</button></div></div>
    {showRatings && form.rating_tables && <div className="card" style={{ margin: '8px 0' }}><div className="row" style={{ gap: 28, alignItems: 'flex-start' }}>{Object.entries(form.rating_tables).map(([t, rows]) => <div key={t}><h4>{t}</h4>{rows.map(([n, d]) => <div key={n} className="small"><b style={{ display: 'inline-block', width: 22 }}>{n}</b>{d}</div>)}</div>)}</div></div>}
    {form.rows.length ? <Grid form={form} onSaved={load} /> : <div className="empty">Nothing to show yet. <button className="chip" onClick={() => send(ask[name] || '')}>ask the agent</button></div>}
  </div>
}

export function MatrixPage() {
  const { a = '', b = '' } = useParams(); const nav = useNavigate(); const { pid, project, patches } = useProject(); const [form, setForm] = useState<Form | null>(null)
  useEffect(() => { P(pid).get(`/matrix/${a}/${b}`).then(setForm).catch(() => setForm(null)) }, [pid, a, b, patches.length, project?.meta?.rev])
  if (!form) return <div className="empty">Loading…</div>
  return <div>
    <div className="row between" style={{ marginBottom: 4 }}><div><h2>Dependency matrix</h2><div className="muted small">rows × columns; cells are relations from the trace graph</div></div>
      <select className="field" style={{ width: 'auto' }} value={`${a}/${b}`} onChange={e => nav(`/p/${pid}/matrix/${e.target.value}`)}>{MATRIX_PAIRS.map(([x, y]) => <option key={x + y} value={`${x}/${y}`}>{KIND_LABEL[x]} × {KIND_LABEL[y]}</option>)}</select></div>
    <Grid form={form} />
  </div>
}

export function Views() {
  const { pid, project } = useProject(); const [art, setArt] = useState<any>(null)
  useEffect(() => { P(pid).get('/artifacts').then(setArt) }, [pid, project?.meta?.rev])
  if (!art) return null
  if (!art.views.length) return <div className="empty">No diagrams yet — click <b>Build artifacts</b>.</div>
  return <div><h2 style={{ marginBottom: 10 }}>Diagrams — rendered from the model</h2><div className="gallery">{art.views.map((v: string) => <div key={v} id={v}><div className="muted small" style={{ marginBottom: 4 }}>{v.replace('.png', '').replace(/_/g, ' ')}</div><img src={P(pid).out(`views/${v}`) + `?t=${project?.meta?.rev || 0}`} onClick={e => window.open((e.target as HTMLImageElement).src)} /></div>)}</div></div>
}
export function Docs() {
  const { pid, project } = useProject(); const [html, setHtml] = useState(''); const [art, setArt] = useState<any>(null)
  useEffect(() => { P(pid).get('/artifacts').then(setArt); fetch(P(pid).out('docs/design_documentation.md')).then(r => r.ok ? r.text() : '').then(md => setHtml(md ? (marked.parse(md.replace(/^---[\s\S]*?---/, '').replaceAll('](../views/', `](${P(pid).out('views/')}`).replace(/\{width=[^}]*\}/g, '')) as string) : '')) }, [pid, project?.meta?.rev])
  if (!html) return <div className="empty">Not built yet — click <b>Build artifacts</b>.</div>
  return <div><div className="row" style={{ marginBottom: 10 }}>{art?.docx?.map((f: string) => <a key={f} className="btn sm" href={`/p/${pid}/out/${f}`}>⬇ {f}</a>)}<button className="btn sm" onClick={() => fetch(`/api/p/${pid}/build?docx=true`, { method: 'POST' })}>Rebuild with Word export</button></div><div className="mdoc" dangerouslySetInnerHTML={{ __html: html }} /></div>
}
export function Sysml() {
  const { pid, project } = useProject(); const [files, setFiles] = useState<[string, string][]>([])
  useEffect(() => { P(pid).get('/artifacts').then(async (a: any) => setFiles(await Promise.all(a.sysml.map(async (f: string) => [f, await fetch(P(pid).out(`sysml/${f}`)).then(r => r.text())])))) }, [pid, project?.meta?.rev])
  if (!files.length) return <div className="empty">Not built yet — click <b>Build artifacts</b>.</div>
  return <div><h2 style={{ marginBottom: 10 }}>SysML v2 — textual notation</h2>{files.map(([f, t]) => <div key={f} id={f} className="card" style={{ marginBottom: 10 }}><h4>{f}</h4><pre className="diff" style={{ maxHeight: 420 }}>{t}</pre></div>)}</div>
}
