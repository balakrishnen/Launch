// Project overview driven by the lifecycle: convergence state, evidence readiness for the next gate, alerts, concurrent workflows (handoffs),
// plus Teams page, Notifications page and the Comments panel used on element pages.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowRight, CheckCircle2, Circle, MessageSquare, Send } from 'lucide-react'
import { useProject } from '../state'
import { P, api } from '../api'
import { IdLink, Linkified } from '../components/common'

export function useLifecycle() {
  const { pid, project, patches } = useProject(); const [lc, setLc] = useState<any>(null)
  useEffect(() => { P(pid).get('/lifecycle').then(setLc).catch(() => setLc(null)) }, [pid, patches.length, project?.meta?.rev, project?.counts])
  return lc
}

function Meter({ label, v, n, color }: { label: string; v: number; n: number; color: string }) {
  const pct = n ? Math.round(100 * v / n) : 0
  return <div style={{ minWidth: 180 }}><div className="row between small" style={{ marginBottom: 4 }}><span className="muted" style={{ textTransform: 'uppercase', letterSpacing: '.05em', fontSize: 11 }}>{label}</span><b className="mono">{v}/{n}</b></div><div className="bar"><i style={{ width: `${pct}%`, background: color }} /></div></div>
}

export function ProjectLifecycle() {
  const { pid, send } = useProject(); const nav = useNavigate(); const lc = useLifecycle()
  if (!lc) return <div className="empty">Loading lifecycle…</div>
  const g = lc.next_gate; const v = lc.verification
  const alertTo: Record<string, string> = { stale: `/p/${pid}/teams`, findings: `/p/${pid}/form/findings`, handoffs: `/p/${pid}/teams`, dfmea: `/p/${pid}/form/dfmea`, pfmea: `/p/${pid}/form/pfmea`, suppliers: `/p/${pid}/form/avl`, fracas: `/p/${pid}/form/fracas` }
  return <div className="stack" style={{ gap: 18 }}>
    <div className="grid2" style={{ gridTemplateColumns: 'minmax(300px,1fr) minmax(420px,1.6fr)' }}>
      <div className="card"><h4>Convergence state</h4><h2 style={{ fontSize: 22, margin: '4px 0 2px' }}>{lc.stage}</h2><div className="muted small" style={{ marginBottom: 14 }}>converging on <b>{lc.phase}</b> · INCOSE / ISO 15288 life cycle</div>
        <div className="stack" style={{ gap: 6 }}>{lc.stages.map((s: string, i: number) => <div key={s} className="row small" style={{ gap: 8, color: i === lc.stage_index ? 'var(--ink)' : 'var(--ink-3)' }}>{i < lc.stage_index ? <CheckCircle2 size={15} color="var(--good)" /> : i === lc.stage_index ? <Circle size={15} color="var(--accent)" fill="var(--accent)" /> : <Circle size={15} />}<span style={{ fontWeight: i === lc.stage_index ? 600 : 400 }}>{s}</span></div>)}</div>
        <div className="row between" style={{ marginTop: 14 }}><span className="muted small">Gates passed</span><b className="mono">{lc.gates.filter((x: any) => x.status === 'passed').length} / {lc.gates.length}</b></div><div className="bar" style={{ marginTop: 4 }}><i style={{ width: `${100 * lc.gates.filter((x: any) => x.status === 'passed').length / Math.max(1, lc.gates.length)}%`, background: 'var(--accent)' }} /></div></div>
      <div className="card"><div className="row between"><h4>Evidence readiness</h4><span className="pill accent">live</span></div>
        {g ? <>
          <div className="row between"><h2 style={{ fontSize: 22, margin: '4px 0 12px' }}>{g.gate} <span className="muted" style={{ fontSize: 14, fontWeight: 400 }}>· {g.date} · {g.stage}</span></h2><span className={'pill ' + (g.ready ? 'good' : 'warn')}>{g.ready ? 'ready' : `${g.score}% of criteria met`}</span></div>
          <div className="row" style={{ gap: 20, marginBottom: 14 }}><Meter label="Verification coverage" v={v.coverage[0]} n={v.coverage[1]} color="var(--good)" /><Meter label="Verification freshness" v={v.fresh[0]} n={v.fresh[1]} color="var(--warn)" /><Meter label="Tests passed" v={v.passed[0]} n={v.passed[1]} color="var(--accent)" />{g.deliverables?.total ? <Meter label="Team deliverables" v={g.deliverables.done} n={g.deliverables.total} color="#6d28d9" /> : null}<Meter label="Exit criteria" v={g.criteria.filter((c: any) => c.ok).length} n={g.criteria.length} color="var(--s4)" /></div>
          <div className="row" style={{ gap: 6 }}>{lc.alerts.map((a: any, i: number) => <button key={i} className="chip" style={{ borderColor: a.level === 'bad' ? '#f3b4b4' : '#f5d78e', background: a.level === 'bad' ? 'var(--bad-soft)' : 'var(--warn-soft)', color: a.level === 'bad' ? 'var(--bad)' : 'var(--warn)' }} onClick={() => nav(alertTo[a.to] || `/p/${pid}/gaps`)}><AlertCircle size={13} />{a.text}</button>)}{!lc.alerts.length && <span className="pill good">no blockers</span>}</div>
          <details style={{ marginTop: 12 }}><summary className="small" style={{ cursor: 'pointer', color: 'var(--accent-ink)', fontWeight: 600 }}>INSPECT CRITERIA <ArrowRight size={12} /></summary><table className="dt" style={{ marginTop: 8, minWidth: 0 }}><tbody>{g.criteria.map((c: any) => <tr key={c.key}><td>{c.ok ? <CheckCircle2 size={14} color="var(--good)" /> : <AlertCircle size={14} color="var(--bad)" />}</td><td>{c.criterion}</td><td className="mono">{c.value}</td><td className="muted small">{c.key === 'tests_passed_share' ? `≥ ${c.limit}` : `≤ ${c.limit}`}</td></tr>)}</tbody></table>
            <div className="row" style={{ marginTop: 8 }}><button className="btn sm primary" onClick={() => send(`Plan the work needed to pass gate ${g.gate}: for each failing criterion stage work items with owners and due dates before ${g.date}, and handoffs for cross-team evidence`)}>Ask the program agent to plan the gate</button></div></details>
        </> : <div className="muted">No gates defined — ask the program agent to set them up.</div>}</div>
    </div>
    <Workflows lc={lc} />
    <div className="card"><div className="row between"><h4>Interrelationship view</h4><button className="btn sm" onClick={() => nav(`/p/${pid}/graph`)}>Open graph →</button></div><div className="muted small">See how lifecycle artifacts connect: needs → requirements → architecture → failure modes → tests → process steps → suppliers, with teams, work items and findings attached.</div></div>
  </div>
}

export function Workflows({ lc }: { lc: any }) {
  const { pid, send, toast } = useProject(); const nav = useNavigate(); const w = lc.workflows
  const act = async (id: string, status: string) => { try { await P(pid).post('/patch', { ops: [{ op: 'update', kind: 'handoffs', id, value: { status, accepted_by: status === 'accepted' ? lc.user || 'me' : '' } }], rationale: `${status} handoff ${id}` }); toast(`${id} ${status}`) } catch (e: any) { toast(e.message) } }
  return <div className="card"><div className="row between"><div><h4>Concurrent workflows</h4><div className="row"><h3>Cross-functional sync & evidence handoffs</h3>{w.pending_total > 0 && <span className="pill bad">{w.pending_total} blocking</span>}</div><div className="muted small">{w.pairs.length} parallel workflows across {w.groups.length} participating groups</div></div><button className="btn sm" onClick={() => nav(`/p/${pid}/teams`)}>Teams →</button></div>
    <div className="stack" style={{ gap: 8, marginTop: 10 }}>{w.pairs.map((p: any, i: number) => <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 10, padding: '10px 12px' }}><div className="row between"><b>{p.from} <ArrowRight size={13} /> {p.to}</b><span className="small muted">{p.accepted.length} accepted · {p.pending.length} pending{p.rejected.length ? ` · ${p.rejected.length} rejected` : ''}</span></div>
      {p.pending.map((h: any) => <div key={h.id} className="row between small" style={{ marginTop: 6, padding: '6px 8px', background: 'var(--warn-soft)', borderRadius: 8 }}><span><IdLink id={h.id} kind="handoffs" /> {h.what} <span className="muted">· due {h.due}{h.gate ? ` · ${h.gate}` : ''}</span> {h.elements?.map((e: string) => <span key={e}> <IdLink id={e} /></span>)}</span><span className="row"><button className="btn good sm" onClick={() => act(h.id, 'accepted')}>Accept</button><button className="btn sm" onClick={() => act(h.id, 'rejected')}>Reject</button></span></div>)}</div>)}
      {!w.pairs.length && <div className="muted small">No handoffs yet. <button className="chip" onClick={() => send('Create the cross-team handoffs needed before the next gate')}>ask the program agent</button></div>}</div></div>
}

export function Teams() {
  const { pid, send, project } = useProject(); const lc = useLifecycle(); const nav = useNavigate()
  if (!lc) return null
  const teams = Object.entries(lc.teams) as [string, any][]; const pteams = (project?.teams || {}) as Record<string, any>
  const sub = teams.filter(([id]) => pteams[id]?.kind === 'subsystem'), fun = teams.filter(([id]) => pteams[id]?.kind !== 'subsystem')
  // functional teams grouped by department (Quality shows its two halves); departments come from the schema
  const DEPTS: Record<string, string[]> = (project as any)?.departments || {}
  const deptOf = (id: string) => { const f = pteams[id]?.focus || pteams[id]?.discipline || ''; return Object.entries(DEPTS).find(([, fs]) => fs.includes(f))?.[0] || 'Other' }
  const groups: [string, string, [string, any][]][] = [['Subsystem teams', 'own a slice of the architecture', sub], ...Object.keys(DEPTS).map(d => [d, d === 'Quality' ? 'design quality + manufacturing quality' : d === 'Engineering' ? 'disciplines, design studio, test, safety, reliability, regulatory compliance' : d === 'Supply chain' ? 'sourcing, procurement, industrialization, logistics' : 'functional', fun.filter(([id]) => deptOf(id) === d)] as [string, string, [string, any][]]).filter(g => g[2].length), ['Other functional teams', 'cut across every subsystem', fun.filter(([id]) => deptOf(id) === 'Other')]].filter(g => g[2].length || g[0] === 'Subsystem teams') as any
  return <div className="stack" style={{ gap: 14 }}>
    <div className="row between"><div><h2>Teams & handoffs</h2><div className="muted small">What each group owns and what is waiting on them before the next gate.</div></div><button className="btn" onClick={() => send('Define teams with leads and disciplines, assign owner_team on every part and test, and create the handoffs needed before the next gate')}>▶ Ask the program agent</button></div>
    {groups.map(([title, sub2, list]: any) => <div key={title}><h4 style={{ margin: '6px 0 8px' }}>{title} <span className="muted" style={{ fontWeight: 400 }}>— {sub2}</span></h4><div className="gallery" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))' }}>{(list as [string, any][]).map(([id, t]) => <div key={id} className="card clickable" onClick={() => nav(`/p/${pid}/team/${id}`)}><div className="row between"><b>{t.name}</b><span className="pill">{pteams[id]?.focus || t.discipline}</span></div><div className="muted small">{t.lead}{pteams[id]?.kind === 'subsystem' && pteams[id]?.parts?.length ? ` · scope ${pteams[id].parts.join(', ')}` : ''}</div>
      <div className="stack small" style={{ marginTop: 8, gap: 3 }}>
        <div className="row between"><span>Open work items</span><b>{t.work_items.length}</b></div><div className="row between"><span>Open findings</span><b style={{ color: t.findings.length ? 'var(--bad)' : undefined }}>{t.findings.length}</b></div>
        <div className="row between"><span>Handoffs waiting on them</span><b style={{ color: t.handoffs_in.length ? 'var(--warn)' : undefined }}>{t.handoffs_in.length}</b></div><div className="row between"><span>Handoffs they owe</span><b style={{ color: t.handoffs_out.length ? 'var(--warn)' : undefined }}>{t.handoffs_out.length}</b></div>
        <div className="row between"><span>Parts · tests · steps</span><b>{t.parts.length} · {t.tests.length} · {t.process_steps.length}</b></div></div>
      <div className="row" style={{ marginTop: 8, gap: 4 }}>{t.work_items.slice(0, 3).map((w: string) => <IdLink key={w} id={w} kind="work_items" />)}{t.handoffs_in.slice(0, 3).map((h: string) => <IdLink key={h} id={h} kind="handoffs" />)}</div></div>)}{!list.length && title === 'Subsystem teams' && <div className="empty">No subsystem teams yet — <a href="#" onClick={e => { e.preventDefault(); send('Propose the subsystem teams for this product from the physical and logical architecture (e.g. drive system, energy system, sensing), each with root parts, logical components and the MoEs it owns, as teams with kind=subsystem') }}>ask the agent to propose them from the architecture</a>.</div>}</div></div>)}
    <Workflows lc={lc} />
    <div className="card"><h4>Stale items — upstream evolved</h4>{lc.staleness.upstream_evolved.length ? <div className="stack small" style={{ gap: 3 }}>{lc.staleness.upstream_evolved.slice(0, 30).map((x: any, i: number) => <div key={i}><IdLink id={x.from} /> <span className="muted">{x.rel} →</span> <IdLink id={x.to} /> <span className="muted">changed after its downstream</span></div>)}</div> : <span className="muted small">none</span>}
      {lc.staleness.stale_verification.length > 0 && <><h4 style={{ marginTop: 10 }}>Stale verification links</h4>{lc.staleness.stale_verification.map((x: any, i: number) => <div key={i} className="small"><IdLink id={x.req} kind="requirements" /> changed after <IdLink id={x.test} kind="tests" /> last produced a result</div>)}</>}
      <div style={{ marginTop: 8 }}><button className="btn sm" onClick={() => nav(`/p/${pid}/form/dvpr`)}>Open DVP&R</button></div></div>
  </div>
}

export function Comments({ element }: { element: string }) {
  const { pid, project, toast } = useProject(); const [rows, setRows] = useState<any[]>([]); const [text, setText] = useState(''); const [assign, setAssign] = useState('')
  const load = () => P(pid).get('/comments?element=' + encodeURIComponent(element)).then(setRows).catch(() => setRows([]))
  useEffect(() => { load() }, [pid, element])
  const post = async () => { if (!text.trim()) return; try { await P(pid).post('/comments', { element, text, assign: assign || null }); setText(''); setAssign(''); load() } catch (e: any) { toast(e.message) } }
  const leads = Object.values((project as any)?.teams || {})
  return <div className="card" style={{ marginTop: 14 }}><div className="row between"><h4><MessageSquare size={13} /> Comments</h4><span className="muted small">{rows.filter(r => !r.resolved).length} open</span></div>
    {rows.map(r => <div key={r.id} className="link" style={{ opacity: r.resolved ? .55 : 1 }}><span className="rel">{new Date(r.ts * 1000).toLocaleString()}</span><span><b>{r.user}</b>{r.assign ? <span className="pill accent" style={{ marginLeft: 6 }}>→ {r.assign}</span> : null}<br /><Linkified text={r.text} />{!r.resolved && <a href="#" className="small" style={{ marginLeft: 8 }} onClick={e => { e.preventDefault(); P(pid).post(`/comments/${r.id}/resolve`).then(load) }}>resolve</a>}</span></div>)}
    <div className="row" style={{ marginTop: 8, alignItems: 'flex-start' }}><textarea className="field" rows={2} placeholder="Comment… use @email to mention; ids like R-012 become links" value={text} onChange={e => setText(e.target.value)} /><div className="stack" style={{ width: 200 }}><input className="field" placeholder="assign to (email)" value={assign} onChange={e => setAssign(e.target.value)} list="leads" /><datalist id="leads">{leads.map((t: any) => <option key={t.lead} value={t.lead} />)}</datalist><button className="btn primary sm" onClick={post}><Send size={13} />Post</button></div></div></div>
}

export function Notifications() {
  const { pid } = useProject(); const nav = useNavigate(); const [rows, setRows] = useState<any[]>([])
  useEffect(() => { api.get('/notifications').then(setRows).catch(() => setRows([])); api.post('/notifications/read').catch(() => { }) }, [])
  return <div><h2>Notifications</h2><div className="muted small" style={{ marginBottom: 10 }}>Mentions, assignments and agent proposals addressed to you.</div>
    {rows.map(r => <div key={r.id} className="link" style={{ borderBottom: '1px solid var(--line)', padding: '8px 0', opacity: r.read ? .7 : 1 }}><span className="rel">{new Date(r.ts * 1000).toLocaleString()}</span><span><span className="pill accent">{r.kind}</span> <Linkified text={r.text} /> <a href="#" className="small" onClick={e => { e.preventDefault(); nav(r.link.replace('{kind}', 'requirements').replace(/^\/p\/[^/]+/, `/p/${r.project || pid}`)) }}>open</a></span></div>)}
    {!rows.length && <div className="empty">Nothing for you yet.</div>}</div>
}
