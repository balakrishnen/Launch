// Department tab — the second navigation axis next to the ISO 15288 life cycle. The top-level departments are fixed by the platform
// (Engineering, Quality, Supply chain, Manufacturing, Service, Program, Go-to-market, Corporate); the organization defines the sub-units
// and teams under each. A department page holds its artifacts, its sub-units and teams, and every gate deliverable its teams owe.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Sparkles, ChevronRight } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { StatusIcon } from './Pdp'

export function Departments() {
  const { pid, project, patches } = useProject(); const nav = useNavigate()
  const [ds, setDs] = useState<any[]>([])
  useEffect(() => { P(pid).get('/departments').then(setDs).catch(() => setDs([])) }, [pid, patches.length, project?.meta?.rev])
  return <div>
    <h2>Departments</h2><div className="muted small" style={{ marginBottom: 12 }}>The fixed departments every product company has; your organization defines the sub-units and teams under each (Organization → Structure).</div>
    <div className="tablewrap"><table className="dt"><thead><tr><th>Department</th><th>Sub-units</th><th>Teams</th><th>Artifacts</th><th>Deliverables open</th></tr></thead><tbody>
      {ds.map(d => <tr key={d.name} className="clickable" onClick={() => nav(`/p/${pid}/dept/${encodeURIComponent(d.name)}`)}><td><b>{d.name}</b></td><td className="small muted">{d.units.filter((u: any) => u.depth === 1).map((u: any) => u.name).join(', ') || '—'}</td><td className="small">{d.teams.map((t: string) => project?.teams?.[t]?.name || t).join(', ') || <span className="muted">no team yet</span>}</td><td className="num">{d.artifacts.length}</td><td className="num" style={{ color: d.open ? 'var(--warn)' : undefined }}>{d.open}</td></tr>)}</tbody></table></div>
  </div>
}

export function DepartmentPage() {
  const { name = '' } = useParams(); const { pid, project, patches, send, openTab } = useProject(); const nav = useNavigate()
  const [d, setD] = useState<any>(null)
  useEffect(() => { P(pid).get('/departments').then((ds: any[]) => { const x = ds.find(z => z.name === name); setD(x || null); if (x) openTab({ key: 'dept:' + name, title: name, path: `/p/${pid}/dept/${encodeURIComponent(name)}`, stage: 'Development' }) }).catch(() => setD(null)) }, [pid, name, patches.length, project?.meta?.rev])
  if (!d) return <div className="empty">Loading…</div>
  const gates: Record<string, any[]> = {}; for (const x of d.deliverables) (gates[x.gate] ??= []).push(x)
  const gateDates: Record<string, string> = {}; for (const x of d.deliverables) if (x.gate_date) gateDates[x.gate] = x.gate_date
  const gateOrder = Object.keys(gates).sort((a, b) => (gateDates[a] || '').localeCompare(gateDates[b] || ''))
  return <div>
    <div className="elhead" style={{ marginBottom: 12 }}><div style={{ flex: 1 }}><div className="row" style={{ marginBottom: 4 }}><span className="pill accent">Department</span><span className="muted small">{d.focuses.map((f: string) => f.replace(/_/g, ' ')).join(' · ')}</span></div><div className="title">{d.name}</div></div>
      <div className="row" style={{ flex: 'none' }}><button className="btn sm" onClick={() => nav(`/p/${pid}/departments`)}>All departments</button><button className="chip" onClick={() => send(`As the ${d.name} department: review our artifacts and gate deliverables and tell me the top 5 things to act on this week, each with element ids and the owning team`)}><Sparkles size={13} />what should we act on</button></div></div>
    <div className="grid2" style={{ gap: 14, alignItems: 'start' }}>
      <div className="card"><h4>Artifacts</h4><div className="muted small" style={{ margin: '2px 0 8px' }}>Derived from the model; every row links to the live artifact.</div>
        <table className="dt"><tbody>{d.artifacts.map((a: any) => <tr key={a.path + a.label} className="clickable" onClick={() => nav(`/p/${pid}/${a.path}`)}><td>{a.label}</td><td className="num muted">{a.count ?? ''}</td><td style={{ width: 20 }}><ChevronRight size={14} /></td></tr>)}</tbody></table></div>
      <div className="stack" style={{ gap: 14 }}>
        <div className="card"><h4>Sub-units & teams</h4><div className="muted small" style={{ margin: '2px 0 8px' }}>As your organization defined them. Teams open their workspace.</div>
          {d.units.length ? d.units.map((u: any) => <div key={u.id} className="row between" style={{ paddingLeft: (u.depth - 1) * 16, padding: '3px 0' }}><span className="small">{u.name}{u.view && <span className="muted"> · view {u.view.replace(/_/g, ' ')}</span>}</span><span className="row" style={{ gap: 4 }}>{d.teams.filter((t: string) => project?.teams?.[t]?.unit === u.id).map((t: string) => <button key={t} className="chip" onClick={() => nav(`/p/${pid}/team/${t}`)}>{project?.teams?.[t]?.name || t}</button>)}</span></div>) : <div className="muted small">No sub-units yet — define them under Organization → Structure.</div>}
          {d.teams.filter((t: string) => !d.units.some((u: any) => project?.teams?.[t]?.unit === u.id)).length > 0 && <div className="row" style={{ gap: 4, marginTop: 8, flexWrap: 'wrap' }}><span className="muted small">Teams in {d.name}:</span>{d.teams.filter((t: string) => !d.units.some((u: any) => project?.teams?.[t]?.unit === u.id)).map((t: string) => <button key={t} className="chip" onClick={() => nav(`/p/${pid}/team/${t}`)}>{project?.teams?.[t]?.name || t}</button>)}</div>}</div>
        <div className="card"><h4>Deliverables by gate</h4>
          {gateOrder.length ? gateOrder.map(g => <div key={g} style={{ marginTop: 8 }}><div className="row" style={{ gap: 6 }}><b className="small">{g}</b><span className="muted small">{(project as any)?.gates?.[g]?.date || gateDates[g] || ''}</span></div>
            {gates[g].map((x: any, i: number) => <div key={i} className="row" style={{ gap: 6, padding: '2px 0', alignItems: 'flex-start' }}><StatusIcon s={x.status} /><span className="small" style={{ flex: 1 }}>{x.name} <span className="muted">· {project?.teams?.[x.team]?.name || x.team}{x.measured ? ' · ' + x.measured : ''}</span></span>{x.link && <a href="#" className="small" onClick={e => { e.preventDefault(); nav(`/p/${pid}${x.link}`) }}>open</a>}</div>)}</div>) : <div className="muted small">No gate deliverables owed by this department's teams in the current process.</div>}</div>
      </div>
    </div>
  </div>
}
