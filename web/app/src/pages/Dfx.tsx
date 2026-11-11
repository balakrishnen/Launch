// Design for X — one app per X (manufacturing, assembly, testability, reliability, safety, maintainability, service,
// transportation, cost, environment, EMC, security, usability, quality, supply chain). Each is a guideline set evaluated
// against the model: automatic checks read the graph; manual items are set by a reviewer or the dfx agent with evidence.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Sparkles, CheckCircle2, CircleDashed, XCircle, HelpCircle, MinusCircle, Bot, User } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { IdLink } from '../components/common'

const Icon = ({ s }: { s: string }) => s === 'pass' ? <CheckCircle2 size={15} color="var(--good)" /> : s === 'partial' ? <CircleDashed size={15} color="var(--warn)" /> : s === 'fail' ? <XCircle size={15} color="var(--bad)" /> : s === 'n/a' ? <MinusCircle size={15} color="var(--line-2)" /> : <HelpCircle size={15} color="var(--ink-3)" />
const scoreColor = (s: number | null) => s === null ? 'var(--ink-3)' : s >= 90 ? 'var(--good)' : s >= 60 ? 'var(--warn)' : 'var(--bad)'

export function DfxList() {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate()
  const [xs, setXs] = useState<any[]>([])
  useEffect(() => { P(pid).get('/dfx').then(setXs).catch(() => setXs([])) }, [pid, patches.length, project?.meta?.rev])
  const groups: Record<string, any[]> = {}; for (const x of xs) (groups[x.focus] ??= []).push(x)
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Design for X</h2><div className="muted small">Guideline sets evaluated against the model. Automatic items read the graph; manual items are reviewed by a person or the dfx agent with evidence. The organization chooses which apply (Tools).</div></div>
      <button className="chip" onClick={() => send('Run the Design-for-X review on every enabled X: decide every unknown item from the model with evidence, propose patches for failed automatic items, and work items for the rest')}><Sparkles size={13} />review all with the agent</button></div>
    {Object.entries(groups).map(([f, list]) => <div key={f} style={{ marginBottom: 18 }}><h4 style={{ textTransform: 'capitalize', marginBottom: 8 }}>{f.replace(/_/g, ' ')}</h4>
      <div className="gallery" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))' }}>{list.map(x => <div key={x.id} className="artcard" onClick={() => nav(`/p/${pid}/dfx/${x.id}`)}>
        <div className="row between"><div className="t">{x.name}</div><b style={{ color: scoreColor(x.score), fontSize: 18 }}>{x.score === null ? '—' : x.score + '%'}</b></div>
        <div className="scorebar"><span style={{ width: `${x.score || 0}%`, background: scoreColor(x.score) }} /></div>
        <div className="d row" style={{ gap: 8 }}><span><CheckCircle2 size={12} color="var(--good)" /> {x.passed}</span><span><CircleDashed size={12} color="var(--warn)" /> {x.partial}</span><span><XCircle size={12} color="var(--bad)" /> {x.failed}</span><span><HelpCircle size={12} color="var(--ink-3)" /> {x.unknown}</span><span className="muted">· {x.applicable} items</span></div>
        {x.reviewed && <div className="d muted">reviewed {x.reviewed} by {x.by}</div>}</div>)}</div></div>)}
    {!xs.length && <div className="empty">No DfX sets enabled — enable them under Organization → Tools.</div>}
  </div>
}

export function DfxPage() {
  const { x = '' } = useParams(); const { pid, project, patches, toast, send, openTab } = useProject(); const nav = useNavigate()
  const [e, setE] = useState<any>(null); const [edit, setEdit] = useState<{ item: string; status: string; evidence: string; note: string } | null>(null)
  useEffect(() => { P(pid).get('/dfx/' + x).then(d => { setE(d); openTab({ key: 'dfx:' + x, title: d.short, path: `/p/${pid}/dfx/${x}`, stage: 'System analysis' }) }).catch(() => setE(null)) }, [pid, x, patches.length, project?.meta?.rev])
  if (!e) return <div className="empty">Loading…</div>
  const save = async () => { if (!edit) return; try { await P(pid).post(`/dfx/${x}/item`, { item: edit.item, status: edit.status, evidence: edit.evidence.split(/[,\s]+/).filter(Boolean), note: edit.note }); toast('Recorded'); setEdit(null) } catch (err: any) { toast(err.message) } }
  return <div>
    <div className="elhead" style={{ marginBottom: 10 }}><div style={{ flex: 1 }}><div className="row" style={{ marginBottom: 4 }}><span className="pill accent">Design for X</span><span className="pill">{e.focus}</span><span className="muted small">{e.standard}</span></div><div className="title">{e.name}</div></div>
      <div className="row" style={{ flex: 'none', alignItems: 'center' }}><b style={{ color: scoreColor(e.score), fontSize: 28 }}>{e.score === null ? '—' : e.score + '%'}</b><button className="btn sm" onClick={() => nav(`/p/${pid}/dfx`)}>All DfX</button><button className="chip" onClick={() => send(`Run the ${e.name} review: decide every unknown item from the model with evidence ids, propose patches for failed automatic items, and work items for the rest`, 'dfx')}><Sparkles size={13} />review with the agent</button></div></div>
    <div className="card"><table className="dt"><thead><tr><th style={{ width: 28 }} /><th>Guideline</th><th>Measured</th><th>Evidence</th><th>Reviewed by</th><th /></tr></thead><tbody>
      {e.items.map((it: any) => <tr key={it.id} style={it.status === 'n/a' ? { opacity: 0.6 } : {}}><td><Icon s={it.status} /></td>
        <td><div><span className="id small">{it.id}</span> {it.text}</div>{it.ref && <div className="muted small">{it.ref}</div>}{it.manual?.note && <div className="small" style={{ marginTop: 2 }}>↳ {it.manual.note}</div>}</td>
        <td className="small">{it.link ? <a href="#" onClick={ev => { ev.preventDefault(); nav(`/p/${pid}${it.link}`) }}>{it.measured}</a> : it.measured}{it.overridden && <div className="muted">auto: {it.auto_status}</div>}</td>
        <td className="small ids">{(it.manual?.evidence || it.ids || []).slice(0, 8).map((i: string) => <IdLink key={i} id={i} />)}</td>
        <td className="small muted">{it.manual?.by ? <span className="row" style={{ gap: 4 }}>{String(it.manual.by).startsWith('agent') ? <Bot size={12} /> : <User size={12} />}{it.manual.by} · {it.manual.date}</span> : it.auto ? 'automatic' : '—'}</td>
        <td><button className="btn ghost sm" onClick={() => setEdit({ item: it.id, status: it.status === 'unknown' ? 'pass' : it.status, evidence: (it.manual?.evidence || []).join(', '), note: it.manual?.note || '' })}>Set</button></td></tr>)}
    </tbody></table></div>
    {edit && <div className="card row" style={{ gap: 8, marginTop: 10, flexWrap: 'wrap', alignItems: 'center', borderColor: 'var(--accent)' }}><b className="small">{edit.item}</b>
      <select className="field" style={{ width: 'auto' }} value={edit.status} onChange={ev => setEdit({ ...edit, status: ev.target.value })}>{['pass', 'partial', 'fail', 'n/a', 'auto'].map(s => <option key={s} value={s}>{s === 'auto' ? 'back to automatic' : s}</option>)}</select>
      <input className="field" style={{ width: 220 }} placeholder="evidence ids (R-04, P-FRAME…)" value={edit.evidence} onChange={ev => setEdit({ ...edit, evidence: ev.target.value })} /><input className="field" style={{ flex: 1, minWidth: 240 }} placeholder="justification" value={edit.note} onChange={ev => setEdit({ ...edit, note: ev.target.value })} />
      <button className="btn sm" onClick={() => setEdit(null)}>Cancel</button><button className="btn sm primary" onClick={save}>Record</button></div>}
    <div className="muted small" style={{ marginTop: 8 }}>Scores count pass as 1 and partial as ½ over applicable items; n/a is excluded. Every recorded status is a patch on <span className="id">DFX-{x}</span> with name and date. Add company guidelines under <code>.sethread/dfx/&lt;x&gt;.yaml</code>.</div>
  </div>
}
