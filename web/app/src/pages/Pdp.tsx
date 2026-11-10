// Product development process — the company's own phases and gates, and what every team owes at each gate, with status
// computed from the model. Adopt a template (stage-gate, EVT/DVT/PVT, APQP, ISO 15288) and tailor it; the matrix is the
// "what do we owe at CDR" view that program managers and teams both read.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, CheckCircle2, CircleDashed, Circle, Diamond } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'

export const StatusIcon = ({ s }: { s: string }) => s === 'done' ? <CheckCircle2 size={14} color="var(--good)" /> : s === 'partial' ? <CircleDashed size={14} color="var(--warn)" /> : s === 'n/a' ? <Circle size={14} color="var(--line-2)" /> : <Circle size={14} color="var(--bad)" />

export function Pdp() {
  const { pid, project, patches, toast, send } = useProject(); const nav = useNavigate()
  const [x, setX] = useState<any>(null); const [tpl, setTpl] = useState(''); const [start, setStart] = useState(new Date().toISOString().slice(0, 10)); const [busy, setBusy] = useState(false)
  useEffect(() => { P(pid).get('/pdp').then(setX).catch(() => { }) }, [pid, patches.length, project?.meta?.rev])
  if (!x) return <div className="empty">Loading…</div>
  const adopt = async () => { if (!tpl) return; setBusy(true); try { const r = await P(pid).post('/pdp/apply', { template: tpl, start, apply: true }); toast(`Adopted — ${r.patch_id}`) } catch (e: any) { toast(e.message) } setBusy(false) }
  const mg = x.gates.filter((g: any) => x.per_gate[g.id]?.total)
  const teams = Object.entries(x.teams) as [string, any][]; const subs = teams.filter(([, t]) => t.kind === 'subsystem'), funs = teams.filter(([, t]) => t.kind !== 'subsystem')
  const Roll = ({ r }: { r: any }) => r && r.total ? <span className="small" style={{ color: r.done === r.total ? 'var(--good)' : r.missing ? 'var(--bad)' : 'var(--warn)' }}>{r.done}/{r.total}</span> : <span className="muted small">—</span>
  const Cell = ({ ds }: { ds: any[] }) => <td style={{ verticalAlign: 'top', minWidth: 150 }}>{(ds || []).map(d => <div key={d.id} className="dchip" title={`${d.name} — ${d.measured}`} onClick={() => d.link && nav(`/p/${pid}${d.link}`)}><StatusIcon s={d.status} /><span>{d.name}</span></div>)}</td>
  return <div>
    <div className="row between" style={{ marginBottom: 10 }}><div><h2>Product development process{x.name ? <span className="muted" style={{ fontWeight: 400, fontSize: 15 }}> · {x.name}</span> : ''}</h2><div className="muted small">Phases closed by gates; the deliverables each team owes at each gate, with status read from the model.</div></div>
      <div className="row"><button className="chip" onClick={() => send('Tailor our product development process: review the phases, gates and deliverables against how this company actually works, and propose deliverables per team that are missing or not applicable')}><Sparkles size={13} />tailor with the agent</button></div></div>
    {x.phases.length === 0 && <div className="card" style={{ marginBottom: 14 }}><h4>Adopt a process template to start</h4><div className="row" style={{ gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>{x.templates.map((t: any) => <button key={t.id} className="artcard" style={{ width: 260, textAlign: 'left', cursor: 'pointer', borderColor: tpl === t.id ? 'var(--accent)' : undefined }} onClick={() => setTpl(t.id)}><div className="t">{t.name}</div><div className="d">{t.description}</div><div className="d">{t.phases} phases · {t.gates} gates · {t.deliverables} deliverables</div></button>)}</div>
      <div className="row" style={{ marginTop: 10, gap: 8 }}><span className="small">first gate on</span><input className="field" style={{ width: 160 }} type="date" value={start} onChange={e => setStart(e.target.value)} /><button className="btn primary" disabled={!tpl || busy} onClick={adopt}>{busy ? 'Applying…' : 'Adopt'}</button><span className="muted small">Existing gates keep their dates; everything lands as one reviewable patch.</span></div></div>}
    {x.phases.length > 0 && <div className="card" style={{ marginBottom: 14 }}><div className="phases">{x.phases.map((p: any, i: number) => { const g = x.gates.find((g: any) => g.id === p.gate); const r = x.per_gate[p.gate]; const cur = project?.stage === p.stage
      return <div key={p.id} className={'phase' + (g?.status === 'passed' ? ' passed' : '') + (x.next_gate === p.gate ? ' next' : '')}><div className="ph">{i + 1}. {p.name}<div className="muted small">{p.stage}{cur ? ' · now' : ''}</div></div><div className="gate" onClick={() => g && nav(`/p/${pid}/element/gates/${g.id}`)}><Diamond size={14} /> <b>{p.gate}</b> <span className="muted small">{g?.date}</span> <Roll r={r} /></div></div> })}</div></div>}
    {x.gates.length > 0 && <div className="card"><h4>Gate × team — what each team owes</h4><div className="tablewrap" style={{ maxHeight: 'none', overflowX: 'auto' }}><table className="dt matrix"><thead><tr><th style={{ minWidth: 140 }}>Team</th>{mg.map((g: any) => <th key={g.id} style={{ textAlign: 'center' }}>{g.id}<div className="muted" style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>{g.date}</div><Roll r={x.per_gate[g.id]} /></th>)}<th>All</th></tr></thead><tbody>
      {[['Subsystem teams', subs], ['Functional teams', funs]].map(([label, list]: any) => <>
        <tr key={label} className="grp"><td colSpan={mg.length + 2}><b>{label}</b></td></tr>
        {list.map(([t, tv]: any) => <tr key={t}><td><a href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/team/${t}`) }}><b>{tv.name}</b></a><div className="muted small">{tv.kind === 'subsystem' ? 'subsystem' : tv.focus || 'functional'}</div></td>{mg.map((g: any) => <Cell key={g.id} ds={x.cells[g.id]?.[t]} />)}<td><Roll r={x.per_team[t]} /></td></tr>)}</>)}
      {x.unowned.length > 0 && <tr><td><b>Unowned</b><div className="muted small">no team matches</div></td>{mg.map((g: any) => <Cell key={g.id} ds={x.unowned.filter((d: any) => d.gate === g.id)} />)}<td /></tr>}
    </tbody></table></div><div className="muted small" style={{ marginTop: 6 }}>Deliverables target a team, a team kind (every subsystem team) or a focus (reliability, quality…). Gates without deliverables ({x.gates.filter((g: any) => !x.per_gate[g.id]?.total).map((g: any) => g.id).join(', ') || 'none'}) are not shown. Edit them in <a href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/collection/deliverables`) }}>Deliverables</a>; phases in <a href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/collection/phases`) }}>Phases</a>.</div></div>}
  </div>
}

// a team's own deliverables, for the team workspace
export function TeamDeliverables({ tid }: { tid: string }) {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate()
  const [ds, setDs] = useState<any[]>([])
  useEffect(() => { P(pid).get(`/team/${tid}/deliverables`).then(setDs).catch(() => setDs([])) }, [pid, tid, patches.length, project?.meta?.rev])
  if (!ds.length) return <div className="card"><h4>Our deliverables</h4><span className="muted small">No PDP deliverables target this team yet — <a href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/pdp`) }}>set up the process</a>.</span></div>
  const byGate: Record<string, any[]> = {}; for (const d of ds) (byGate[d.gate] ??= []).push(d)
  return <div className="card"><div className="row between"><h4>Our deliverables by gate</h4><button className="chip" onClick={() => send(`For this team: for every deliverable that is missing or partial at the next gate, propose the work items (owner, due before the gate) and, where the model can produce it, draft the deliverable itself`)}><Sparkles size={13} />plan the gaps</button></div>
    {Object.entries(byGate).map(([g, xs]) => <div key={g} style={{ marginBottom: 8 }}><div className="small" style={{ fontWeight: 600 }}>{g} <span className="muted" style={{ fontWeight: 400 }}>{xs[0].gate_date}{xs[0].gate_status === 'passed' ? ' · passed' : ''}</span></div>
      {xs.map(d => <div key={d.id} className="row small" style={{ gap: 6, padding: '3px 0', cursor: d.link ? 'pointer' : 'default' }} onClick={() => d.link && nav(`/p/${pid}${d.link}`)}><StatusIcon s={d.status} /><span>{d.name}</span><span className="muted">{d.measured}</span></div>)}</div>)}</div>
}
