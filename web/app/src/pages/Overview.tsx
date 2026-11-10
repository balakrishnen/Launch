import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUp, FileSearch, ListTree, Boxes, ShieldAlert, FlaskConical, Plus } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL, STAGE_COLOR, FORMS, MATRIX_PAIRS } from '../api'
import { Bar, IdLink } from '../components/common'
import { PatchCard } from '../components/Agent'

function greeting() { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }

export function Overview() {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate()
  const [sc, setSc] = useState<any>(null); const [gaps, setGaps] = useState<any[]>([]); const [art, setArt] = useState<any>(null); const [text, setText] = useState(''); const [seg, setSeg] = useState('recent')
  useEffect(() => { const p = P(pid); p.get('/scorecard').then(setSc).catch(() => { }); p.get('/collection/gaps').then(setGaps).catch(() => { }); p.get('/artifacts').then(setArt).catch(() => { }) }, [pid, project?.counts])
  const recent = useMemo(() => { try { return JSON.parse(localStorage.getItem('tabs:' + pid) || '[]') } catch { return [] } }, [pid, patches.length])
  if (!project) return null
  const staged = patches.filter(p => p.status === 'staged'); const name = (project.user || '').split('@')[0]
  const total = Object.values(project.counts).reduce((a, b) => a + b, 0)
  const suggestions = [
    { icon: <FileSearch size={18} />, bg: '#e9f0ff', color: '#2f6fed', t: 'Ingest documents', d: 'Read the PRD, datasheets and standards; set up stakeholders, needs and MoEs.', q: 'Read the documents in docs/ and set up stakeholders, needs and measures of effectiveness' },
    { icon: <ListTree size={18} />, bg: '#fff3e0', color: '#c2410c', t: 'Write requirements', d: 'Derive the regulatory context and write testable system requirements.', q: 'Derive the regulatory context and write the system requirements, each with a measurable attribute and a test' },
    { icon: <Boxes size={18} />, bg: '#e6f7f4', color: '#0f766e', t: 'Design architecture', d: 'Functions, logical components, parts by discipline, interfaces and states.', q: 'Define the logical and physical architecture: functions, logical components, parts by discipline, interfaces, states' },
    { icon: <ShieldAlert size={18} />, bg: '#fdecec', color: '#b91c1c', t: 'Assess risks', d: 'Systematic DFMEA: every function, interface and transition against guide words.', q: 'Assess or screen every failure-mode candidate systematically with causes derived from the architecture' },
    { icon: <FlaskConical size={18} />, bg: '#eefbe7', color: '#15803d', t: 'Plan verification', d: 'Tests with standards and pass/fail, gates, DVP&R and the certification plan.', q: 'Complete the verification plan: every requirement and High-AP failure mode covered by a test with standard, severity and pass/fail; define gates' },
  ]
  const submit = () => { const t = text.trim(); if (!t) return; setText(''); send(t) }
  const items = seg === 'recent' ? recent.slice().reverse().map((t: any) => ({ t: t.title, k: t.stage ? 'Element' : 'Artifact', s: t.stage || '', path: t.path }))
    : seg === 'artifacts' ? [...FORMS.map(f => ({ t: f.title, k: 'Form', s: f.stage, path: `/p/${pid}/form/${f.id}` })), ...MATRIX_PAIRS.map(([a, b]) => ({ t: `${KIND_LABEL[a]} × ${KIND_LABEL[b]}`, k: 'Matrix', s: project.stage_of[b] || '', path: `/p/${pid}/matrix/${a}/${b}` })), ...(art?.views || []).map((v: string) => ({ t: v.replace('.png', '').replace(/^V\d+_/, '').replace(/_/g, ' '), k: 'Diagram', s: '', path: `/p/${pid}/views` }))]
    : staged.map(p => ({ t: p.rationale, k: 'Patch', s: p.author, path: `/p/${pid}/inbox` }))
  return <div>
    <div className="hero">
      <div className="hi">{greeting()}{name ? ` ${name}` : ''},</div><h1>What can we build today?</h1>
      <div className="prompt"><div className="wrap"><textarea value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }} placeholder="Ask anything about this product or describe what you'd like to do…" /><button className="btn primary go" onClick={submit} style={{ padding: 8 }}><ArrowUp size={16} /></button></div>
        <div className="foot">{project.meta.name} · {total} elements · scorecard {sc ? `${sc.grade} · ${sc.overall}` : '…'} · {gaps.length ? `${gaps.length} open gaps` : 'trace clean'}{staged.length ? ` · ${staged.length} patches to review` : ''}</div></div>
    </div>
    <h3 style={{ margin: '0 0 10px' }}>Suggestions</h3>
    <div className="sugg">{suggestions.map(s => <button key={s.t} onClick={() => send(s.q)}><span className="ic" style={{ background: s.bg, color: s.color }}>{s.icon}</span><span className="t">{s.t}</span><span className="d">{s.d}</span></button>)}</div>
    <div className="sechead" style={{ marginTop: 32 }}><div className="seg"><button className={seg === 'recent' ? 'active' : ''} onClick={() => setSeg('recent')}>Recently viewed</button><button className={seg === 'artifacts' ? 'active' : ''} onClick={() => setSeg('artifacts')}>Artifacts</button><button className={seg === 'reviews' ? 'active' : ''} onClick={() => setSeg('reviews')}>Reviews{staged.length ? ` (${staged.length})` : ''}</button></div>
      <button className="btn primary" onClick={() => nav(`/p/${pid}/documents`)}><Plus size={15} />New</button></div>
    <div className="list"><div className="li lh" style={{ cursor: 'default' }}><span>Name</span><span>Type</span><span>Stage</span><span></span></div>
      {items.slice(0, 12).map((it: any, i: number) => <div key={i} className="li" onClick={() => nav(it.path)}><span className="t" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.t}</span><span className="muted">{it.k}</span><span className="row small" style={{ gap: 6 }}>{it.s && STAGE_COLOR[it.s] && <span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: STAGE_COLOR[it.s] }} />}<span className="muted">{it.s}</span></span><span className="muted small">open →</span></div>)}
      {items.length === 0 && <div className="empty">{seg === 'recent' ? 'Nothing viewed yet — open any element or artifact.' : 'Nothing here.'}</div>}</div>
    <div className="grid3" style={{ marginTop: 28 }}>
      <div className="card"><div className="row between"><h4>Scorecard</h4>{sc && <span className={'pill ' + (sc.grade <= 'B' ? 'good' : 'warn')}>{sc.grade} · {sc.overall}</span>}</div>{sc ? <div className="stack" style={{ gap: 8 }}>{Object.entries(sc.dimensions).slice(0, 5).map(([k, v]: any) => <div key={k}><div className="row between small"><span>{k.replace(/_/g, ' ')}</span><b>{v}</b></div><Bar v={v} /></div>)}<a href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/scorecard`) }} className="small">all dimensions →</a></div> : <span className="muted">…</span>}</div>
      <div className="card"><div className="row between"><h4>Open gaps</h4><span className={'pill ' + (gaps.length ? 'warn' : 'good')}>{gaps.length}</span></div>{gaps.length ? <div className="stack" style={{ gap: 3 }}>{gaps.slice(0, 6).map((g, i) => <div key={i} className="small"><span className="muted">{g.gap.replace(/_/g, ' ')}</span> <IdLink id={String(g.item)} /></div>)}<div className="row" style={{ marginTop: 6 }}><button className="btn sm" onClick={() => send('Close the open trace gaps in order of leverage, in reviewable patches; stop when a human decision is needed')}>Ask the agent to close them</button></div></div> : <span className="muted small">Trace is clean.</span>}</div>
      <div className="card"><div className="row between"><h4>Model</h4><span className="pill">{total} elements</span></div><div className="stack" style={{ gap: 4 }}>{['1 Needs', '2 Requirements', '3 Logical architecture', '4 Physical architecture', '5 Analysis', '6 Verification'].map(s => { const ks = Object.entries(project.stage_of).filter(([, st]) => st === s).map(([k]) => k); return <div key={s} className="small" style={{ display: 'grid', gridTemplateColumns: '12px 1fr auto', gap: 6, alignItems: 'baseline' }}><span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: STAGE_COLOR[s] }} /><span style={{ color: STAGE_COLOR[s], fontWeight: 500 }}>{s.replace(/^\d /, '')}</span><span className="muted">{ks.reduce((a, k) => a + project.counts[k], 0)}</span></div> })}<div className="small" style={{ display: 'grid', gridTemplateColumns: '12px 1fr auto', gap: 6 }}><span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: STAGE_COLOR['Risk (derived)'] }} /><span style={{ color: STAGE_COLOR['Risk (derived)'], fontWeight: 500 }}>Risk</span><span className="muted">{project.fmea_counts.assessed} assessed · {project.fmea_counts.high_ap} High AP</span></div></div></div>
    </div>
    {staged.length > 0 && <div style={{ marginTop: 24 }}><h3 style={{ marginBottom: 8 }}>Waiting for your review</h3>{staged.slice(0, 2).map(p => <PatchCard key={p.id} p={p} compact />)}</div>}
  </div>
}
