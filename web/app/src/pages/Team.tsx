// Team workspace — the system-of-record home for one team: KPIs, every record they own (editable sheets), what waits on
// them, failure modes and tests on their parts, activity on their records, and the conversations that touched them.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Sparkles, ArrowRight, Users } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL } from '../api'
import { IdLink, Linkified } from '../components/common'
import { Sheet, type Col } from '../components/Sheet'
import { TeamDeliverables } from './Pdp'
import { SysmlDiagram } from '../components/Diagram'

const TABS = ['Overview', 'Subsystem', 'Focus', 'Work', 'Records', 'Risk & tests', 'Handoffs', 'Activity']

export function TeamPage() {
  const { tid = '' } = useParams(); const { pid, project, patches, send, openTab, toast } = useProject(); const nav = useNavigate()
  const [w, setW] = useState<any>(null); const [tab, setTab] = useState('Overview'); const [kind, setKind] = useState('parts'); const [rows, setRows] = useState<any[]>([])
  useEffect(() => { P(pid).get('/team/' + tid).then(x => { setW(x); openTab({ key: 'team:' + tid, title: x.name, path: `/p/${pid}/team/${tid}`, stage: 'Project assessment and control' }) }).catch(() => setW(null)) }, [pid, tid, patches.length, project?.meta?.rev])
  useEffect(() => { if (!w) return; const ids = new Set(w.records[kind] || []); P(pid).get('/collection/' + kind).then((rs: any[]) => setRows(rs.filter(r => ids.has(r.id)))).catch(() => setRows([])) }, [pid, kind, w, patches.length])
  const Kpi = ({ label, v, bad, to }: { label: string; v: any; bad?: boolean; to?: string }) => <div className="card kpi" onClick={() => to && nav(to)} style={{ cursor: to ? 'pointer' : 'default' }}><div className="small muted">{label}</div><div className="big" style={{ color: bad ? 'var(--bad)' : 'var(--ink)' }}>{Array.isArray(v) ? `${v[0]} / ${v[1]}` : v}</div></div>
  const spec = project?.schema?.[kind]
  const cols = useMemo<Col[]>(() => { const out: Col[] = [{ key: 'id', name: 'id' }]; if (spec) { for (const f of [...spec.req, ...Object.keys(spec.opt)]) if (!['attrs', 'context'].includes(f)) out.push({ key: f, name: f.replace(/_/g, ' '), type: Array.isArray(spec.opt[f]) ? 'list' : typeof spec.opt[f] === 'number' ? 'number' : 'text' }) } return out }, [spec])
  if (!w) return <div className="empty">Loading team…</div>
  const k = w.kpis
  const business = ['marketing', 'sales', 'finance', 'hr', 'people', 'facilities', 'legal', 'service'].includes(w.focus?.name)
  const commit = async ({ updates, adds, deletes }: any, stageIt: boolean) => {
    const ops: any[] = []; for (const [id, v] of Object.entries(updates)) ops.push({ op: 'update', kind, id, value: v })
    let n = rows.length; for (const a of adds) { const v: any = { ...a }; delete v.__new; delete v.id; if (kind === 'parts' || kind === 'tests' || kind === 'tables' || kind === 'notes') v.owner_team = tid; if (kind === 'work_items' || kind === 'risks' || kind === 'process_steps') v.team = tid; ops.push({ op: 'add', kind, id: `${kind.slice(0, 2).toUpperCase()}-${tid.replace('TM-', '')}-${String(++n).padStart(2, '0')}`, value: v }) }
    for (const id of deletes) ops.push({ op: 'remove', kind, id })
    const r = await P(pid).post('/patch', { ops, rationale: `${w.name}: ${ops.length} change(s) in ${KIND_LABEL[kind] || kind}`, apply: !stageIt }); toast(stageIt ? `Staged ${r.patch_id}` : `Applied ${r.patch_id}`)
  }
  const recKinds = Object.entries(w.records as Record<string, string[]>)
  return <div>
    <div className="elhead" style={{ marginBottom: 10 }}><div style={{ flex: 1 }}>
      <div className="row" style={{ marginBottom: 4 }}><span className={'pill ' + (w.kind === 'subsystem' ? 'accent' : '')}><Users size={12} /> {w.kind === 'subsystem' ? 'subsystem team' : `functional team${w.focus ? ' · ' + w.focus.name : ''}`}</span>{w.discipline && <span className="pill accent">{w.discipline}</span>}<span className="muted small">lead {w.lead || '—'} · {w.members.length} member{w.members.length === 1 ? '' : 's'}</span></div>
      <div className="title">{w.name}</div></div>
      <div className="row" style={{ flex: 'none' }}><button className="btn sm" onClick={() => send(`As the ${w.name} team: what should we do this week to be ready for the next gate? Use our open work items, findings, handoffs and High-AP failure modes on our parts`)}><Sparkles size={14} />Plan our week</button><button className="btn sm" onClick={() => nav(`/p/${pid}/teams`)}>All teams</button></div></div>
    <div className="sectabs">{TABS.filter(t => (t !== 'Subsystem' || w.subsystem) && (t !== 'Focus' || w.focus) && !(business && (t === 'Risk & tests' || t === 'Focus'))).map(t => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t === 'Focus' ? `Focus · ${w.focus.name}` : t}</button>)}</div>
    {tab === 'Overview' && <div className="stack" style={{ gap: 16 }}>
      {business && w.focus && <FocusView f={w.focus} />}
      <div className="kpis">
        <Kpi label="Open work items" v={k.open_work_items} to={`/p/${pid}/team/${tid}`} /><Kpi label="Overdue" v={k.overdue} bad={k.overdue > 0} /><Kpi label="Open findings" v={k.open_findings} bad={k.critical_findings > 0} /><Kpi label="Handoffs waiting on us" v={k.handoffs_waiting_on_us} bad={k.handoffs_waiting_on_us > 0} /><Kpi label="We wait for" v={k.handoffs_we_wait_for} />{!business && <><Kpi label="Tests passed" v={k.tests_passed} /><Kpi label="High-AP on our parts" v={k.high_ap_on_our_parts} bad={k.high_ap_without_test > 0} /></>}<Kpi label="Open risks" v={k.open_risks} />{k.req_coverage && <Kpi label="Requirements with a test" v={k.req_coverage} bad={k.req_coverage[0] < k.req_coverage[1]} />}{k.boundary_interfaces !== undefined && <Kpi label="Boundary interfaces" v={k.boundary_interfaces} />}
      </div>
      <TeamDeliverables tid={tid} />
      <div className="grid2">
        <div className="card"><h4>Due next</h4>{w.due_soon.length ? <div className="list due">{w.due_soon.map((x: any) => <div key={x.id} className="li" onClick={() => nav(`/p/${pid}/element/work_items/${x.id}`)}><span className="t">{x.title}</span><span className="muted small">{x.owner}</span><span className={'pill ' + (x.due < new Date().toISOString().slice(0, 10) ? 'bad' : '')}>{x.due}</span><span className="muted small">{x.status}</span></div>)}</div> : <span className="muted small">Nothing with a due date.</span>}</div>
        <div className="card"><h4>Waiting on us</h4>{w.handoffs_in.length ? w.handoffs_in.map((h: any) => <div key={h.id} className="link"><span className="rel">{h.from_team}</span><span><IdLink id={h.id} kind="handoffs" /> {h.what} <span className="muted small">due {h.due || '—'}{h.gate ? ` · ${h.gate}` : ''}</span></span></div>) : <span className="muted small">No pending handoffs to this team.</span>}
          <h4 style={{ marginTop: 12 }}>We are waiting for</h4>{w.handoffs_out.length ? w.handoffs_out.map((h: any) => <div key={h.id} className="link"><span className="rel">{h.to_team}</span><span><IdLink id={h.id} kind="handoffs" /> {h.what}</span></div>) : <span className="muted small">—</span>}</div>
      </div>
      <div className="grid3">
        <div className="card"><h4>Our records</h4><div className="stack" style={{ gap: 4 }}>{recKinds.filter(([, ids]) => ids.length).map(([kd, ids]) => <div key={kd} className="row between small clickable" onClick={() => { setKind(kd); setTab('Records') }}><span>{KIND_LABEL[kd] || kd}</span><b>{ids.length}</b></div>)}<div className="row between small"><span>functions on our parts</span><b>{w.functions.length}</b></div><div className="row between small"><span>interfaces</span><b>{w.interfaces.length}</b></div><div className="row between small"><span>requirements we realize</span><b>{w.requirements.length}</b></div></div></div>
        <div className="card"><h4>Recent activity</h4>{w.activity.length ? <div className="stack" style={{ gap: 6 }}>{w.activity.slice(0, 8).map((a: any) => <div key={a.patch} className="small"><span className="muted">{new Date(a.ts * 1000).toLocaleDateString()}</span> <b>{a.author}</b> — <Linkified text={a.rationale} /> <span className="muted">({a.n} of ours)</span></div>)}</div> : <span className="muted small">No changes to this team's records yet.</span>}</div>
        <div className="card"><h4>Conversations</h4>{w.conversations.length ? w.conversations.map((c: any) => <div key={c.id} className="small clickable" onClick={() => nav(`/p/${pid}/chat/${c.id}`)}>• {c.title}</div>) : <span className="muted small">None touched our records yet.</span>}<div style={{ marginTop: 8 }}><button className="chip" onClick={() => send(`Summarise the state of the ${w.name} team's records: parts, open work, findings, risks, and what blocks the next gate`)}><Sparkles size={13} />ask about this team</button></div></div>
      </div>
    </div>}
    {tab === 'Subsystem' && w.subsystem && <SubsystemView s={w.subsystem} w={w} />}
    {tab === 'Focus' && w.focus && <FocusView f={w.focus} />}
    {tab === 'Work' && <div className="stack" style={{ gap: 14 }}>
      <TeamSheet pid={pid} kind="work_items" ids={w.records.work_items} tid={tid} title="Work items" />
      <TeamSheet pid={pid} kind="findings" ids={w.records.findings} tid={tid} title="Findings" />
      <TeamSheet pid={pid} kind="risks" ids={w.records.risks} tid={tid} title="Risks" />
    </div>}
    {tab === 'Records' && <div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>{recKinds.map(([kd, ids]) => <button key={kd} className="chip" style={kind === kd ? { borderColor: 'var(--accent)', color: 'var(--accent-ink)', background: 'var(--accent-soft)' } : {}} onClick={() => setKind(kd)}>{KIND_LABEL[kd] || kd} <b>{ids.length}</b></button>)}</div>
      <Sheet cols={cols} rows={rows} onCommit={commit} onOpen={r => nav(`/p/${pid}/element/${kind}/${encodeURIComponent(String(r.id))}`)} newRowTemplate={() => { const t: any = {}; if (spec) { for (const f of spec.req) t[f] = ['tests', 'reqs', 'funcs', 'alloc', 'parts', 'items', 'columns', 'rows', 'elements', 'links'].includes(f) ? [] : ''; for (const [f, d] of Object.entries(spec.opt)) t[f] = Array.isArray(d) ? [] : (typeof d === 'object' && d) ? {} : d } return t }} />
    </div>}
    {tab === 'Risk & tests' && <div className="grid2">
      <div className="card"><div className="row between"><h4>High-AP failure modes on our parts</h4><span className={'pill ' + (k.high_ap_without_test ? 'bad' : 'good')}>{k.high_ap_without_test} without a test</span></div>{w.high_ap.length ? <div className="stack" style={{ gap: 3 }}>{w.high_ap.map((f: any) => <div key={f.id} className="link"><IdLink id={f.id} kind="fmea" /><span className="ap-H">H</span><span><IdLink id={f.element} /> {f.guide} — {f.mode}{f.tests?.length ? '' : <span className="muted small"> · no test</span>}</span></div>)}</div> : <span className="muted small">None.</span>}<div style={{ marginTop: 8 }}><button className="chip" onClick={() => send(`For the ${w.name} team: assess the remaining failure-mode candidates on our parts and propose tests for every High-AP mode without one`)}><Sparkles size={13} />ask the risk agent</button></div></div>
      <div className="card"><h4>Our tests</h4>{w.records.tests.length ? <table className="dt"><thead><tr><th>Test</th><th>Status</th><th>Gate</th></tr></thead><tbody>{w.records.tests.map((t: string) => <tr key={t} className="clickable" onClick={() => nav(`/p/${pid}/element/tests/${t}`)}><td><IdLink id={t} kind="tests" /></td><td>—</td><td>—</td></tr>)}</tbody></table> : <span className="muted small">No tests owned by this team. <a href="#" onClick={e => { e.preventDefault(); send(`Assign owner_team ${tid} to the tests that verify requirements realized by our parts`) }}>Assign ours</a></span>}
        <h4 style={{ marginTop: 12 }}>Requirements we realize</h4><div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>{w.requirements.slice(0, 40).map((r: string) => <IdLink key={r} id={r} kind="requirements" />)}{!w.requirements.length && <span className="muted small">—</span>}</div></div>
    </div>}
    {tab === 'Handoffs' && <div className="card"><div className="row between"><h4>Handoffs</h4><button className="btn sm" onClick={() => nav(`/p/${pid}/teams`)}>Board <ArrowRight size={13} /></button></div>
      <table className="dt"><thead><tr><th>Id</th><th>Direction</th><th>With</th><th>What</th><th>Due</th><th>Gate</th><th>Status</th></tr></thead><tbody>{[...w.handoffs_in.map((h: any) => ({ ...h, dir: 'to us', with: h.from_team })), ...w.handoffs_out.map((h: any) => ({ ...h, dir: 'from us', with: h.to_team }))].map(h => <tr key={h.id} className="clickable" onClick={() => nav(`/p/${pid}/element/handoffs/${h.id}`)}><td className="id">{h.id}</td><td>{h.dir}</td><td>{h.with}</td><td>{h.what}</td><td>{h.due}</td><td>{h.gate}</td><td><span className="pill warn">{h.status}</span></td></tr>)}</tbody></table></div>}
    {tab === 'Activity' && <div className="card">{w.activity.length ? w.activity.map((a: any) => <div key={a.patch} className="link"><span className="rel">{new Date(a.ts * 1000).toLocaleString()}</span><span><b>{a.author}</b> — <Linkified text={a.rationale} /><div className="small muted">{a.ids.map((i: string) => <IdLink key={i} id={i} />)} · patch {a.patch}</div></span></div>) : <span className="muted">No activity yet.</span>}</div>}
  </div>
}

function TeamSheet({ pid, kind, ids, tid, title }: { pid: string; kind: string; ids: string[]; tid: string; title: string }) {
  const { project, patches, toast } = useProject(); const nav = useNavigate(); const [rows, setRows] = useState<any[]>([])
  useEffect(() => { const s = new Set(ids); P(pid).get('/collection/' + kind).then((rs: any[]) => setRows(rs.filter(r => s.has(r.id)))).catch(() => setRows([])) }, [pid, kind, ids.join(','), patches.length])
  const spec = project?.schema?.[kind]
  const cols: Col[] = [{ key: 'id', name: 'id' }, ...(spec ? [...spec.req, ...Object.keys(spec.opt)].filter(f => !['links', 'notes', 'eight_d'].includes(f)).map(f => ({ key: f, name: f.replace(/_/g, ' '), type: (Array.isArray(spec.opt[f]) ? 'list' : 'text') as Col['type'] })) : [])]
  const commit = async ({ updates, adds, deletes }: any, stageIt: boolean) => {
    const ops: any[] = []; for (const [id, v] of Object.entries(updates)) ops.push({ op: 'update', kind, id, value: v })
    let n = rows.length; for (const a of adds) { const v: any = { ...a }; delete v.__new; delete v.id; v.team = tid; if (kind === 'findings') { delete v.team; v.owner = v.owner || tid } ops.push({ op: 'add', kind, id: `${{ work_items: 'WI', findings: 'FD', risks: 'RK' }[kind] || kind.slice(0, 2).toUpperCase()}-${tid.replace('TM-', '')}-${String(++n).padStart(2, '0')}`, value: v }) }
    for (const id of deletes) ops.push({ op: 'remove', kind, id })
    const r = await P(pid).post('/patch', { ops, rationale: `${title}: ${ops.length} change(s)`, apply: !stageIt }); toast(stageIt ? `Staged ${r.patch_id}` : `Applied ${r.patch_id}`)
  }
  return <div className="card"><h4>{title} <span className="pill">{rows.length}</span></h4><Sheet cols={cols} rows={rows} dense onCommit={commit} onOpen={r => nav(`/p/${pid}/element/${kind}/${encodeURIComponent(String(r.id))}`)} newRowTemplate={() => { const t: any = {}; if (spec) { for (const f of spec.req) t[f] = f === 'status' ? 'open' : ''; for (const [f, d] of Object.entries(spec.opt)) t[f] = Array.isArray(d) ? [] : (typeof d === 'object' && d) ? {} : d } return t }} /></div>
}

// The subsystem team's slice of the architecture: scope tree, boundary ICD, requirements with verification, performance MoEs, DFMEA slice, budgets.
function SubsystemView({ s, w }: { s: any; w: any }) {
  const { pid, send } = useProject(); const nav = useNavigate()
  const byParent: Record<string, any[]> = {}; for (const t of s.tree) (byParent[t.parent || ''] ??= []).push(t)
  const Node = ({ p, depth }: { p: any; depth: number }) => <div><div className="row small" style={{ paddingLeft: depth * 16, gap: 6, padding: '3px 0 3px ' + depth * 16 + 'px' }}><IdLink id={p.id} kind="parts" /><span>{p.name}</span><span className="muted">{p.discipline}{p.make_buy ? ` · ${p.make_buy}` : ''}</span>{p.owner_team && p.owner_team !== w.id && <span className="pill" style={{ fontSize: 10 }}>{p.owner_team}</span>}</div>{(byParent[p.id] || []).map(c => <Node key={c.id} p={c} depth={depth + 1} />)}</div>
  return <div className="stack" style={{ gap: 14 }}>
    <SysmlDiagram path={`/diagram/element/teams/${w.id}`} title={`${w.name} — subsystem boundary`} height={420} showText={false} />
    <div className="grid2" style={{ alignItems: 'start' }}>
      <div className="card"><div className="row between"><h4>Scope — {s.parts.length} parts, {s.lcs.length} logical components</h4><button className="chip" onClick={() => send(`Define the ${w.name} subsystem precisely: confirm its root parts and logical components, and propose any parts that should move in or out of scope`)}><Sparkles size={13} />refine scope</button></div>
        {(byParent[''] || []).map(p => <Node key={p.id} p={p} depth={0} />)}<div className="small muted ids" style={{ marginTop: 6 }}>logical: {s.lcs.map((l: string) => <IdLink key={l} id={l} kind="logical_components" />)}</div>
        {Object.keys(s.budgets).length > 0 && <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: 'wrap' }}>{Object.entries(s.budgets).map(([k, v]: any) => <span key={k} className="pill">{k.replace(/_/g, ' ')} <b>{v}</b></span>)}</div>}</div>
      <div className="card"><h4>Performance — measures of effectiveness we own</h4>{s.moes.length ? <table className="dt"><thead><tr><th>MoE</th><th>Name</th><th>Target</th></tr></thead><tbody>{s.moes.map((x: any) => <tr key={x.id}><td><IdLink id={x.id} kind="moes" /></td><td>{x.name}</td><td className="mono small">{String(x.target)}</td></tr>)}</tbody></table> : <span className="muted small">No MoEs linked — set <code>teams.moes</code> or link needs through requirements.</span>}
        <h4 style={{ marginTop: 12 }}>Functions we realize</h4><div className="row ids" style={{ gap: 6, flexWrap: 'wrap' }}>{s.functions.map((f: string) => <IdLink key={f} id={f} kind="functions" />)}</div></div>
    </div>
    <div className="card"><div className="row between"><h4>Boundary — interfaces to the rest of the product ({s.interfaces_boundary.length}) · the subsystem ICD</h4><button className="btn sm" onClick={() => nav(`/p/${pid}/form/icd`)}>Full ICD</button></div>
      {s.boundary.length ? <table className="dt"><thead><tr><th>Interface</th><th>Name</th><th>Kind</th><th>Items</th><th>Other side</th><th>Functions</th></tr></thead><tbody>{s.boundary.map((i: any) => <tr key={i.id}><td><IdLink id={i.id} kind="interfaces" /></td><td>{i.name}</td><td>{i.kind}</td><td className="small">{(i.items || []).join(', ')}</td><td><IdLink id={i.outside} kind="parts" /></td><td className="small ids">{(i.funcs || []).map((f: string) => <IdLink key={f} id={f} kind="functions" />)}</td></tr>)}</tbody></table> : <span className="muted small">No boundary interfaces — the subsystem is isolated or interfaces are not modelled yet.</span>}
      <div className="small muted" style={{ marginTop: 6 }}>{s.interfaces_internal.length} internal interfaces</div></div>
    <div className="grid2" style={{ alignItems: 'start' }}>
      <div className="card"><div className="row between"><h4>Requirements we realize ({s.requirements.length})</h4><span className={'pill ' + (s.verification.covered === s.verification.total ? 'good' : 'warn')}>{s.verification.covered}/{s.verification.total} with a test · {s.verification.passed}/{s.verification.tests} passed</span></div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>{s.requirements.map((r: string) => <IdLink key={r} id={r} kind="requirements" />)}</div>
        <div className="row" style={{ marginTop: 8 }}><button className="chip" onClick={() => send(`For the ${w.name} subsystem: list every requirement we realize with its verification status, and propose tests for any without one`)}><Sparkles size={13} />verification plan</button><button className="btn sm" onClick={() => nav(`/p/${pid}/form/dvpr`)}>DVP&R</button></div></div>
      <div className="card"><div className="row between"><h4>Failure modes on our scope ({s.fmea.length})</h4><button className="btn sm" onClick={() => nav(`/p/${pid}/form/dfmea`)}>DFMEA</button></div>
        <div className="stack" style={{ gap: 3, maxHeight: 320, overflow: 'auto' }}>{s.fmea.slice(0, 40).map((f: any) => <div key={f.id} className="link"><IdLink id={f.id} kind="fmea" /><span className={'ap-' + f.AP}>{f.AP}</span><span className="small"><IdLink id={f.element} /> {f.guide} — {f.mode}</span></div>)}{!s.fmea.length && <span className="muted small">None assessed yet.</span>}</div>
        <div className="row" style={{ marginTop: 8 }}><button className="chip" onClick={() => send(`Assess every unassessed failure-mode candidate on the ${w.name} subsystem (parts ${s.parts.join(', ')}) with causes derived from the architecture`)}><Sparkles size={13} />ask the risk agent</button></div></div>
    </div>
  </div>
}

// A functional team's cross-cutting view: whatever its focus is made of, across every subsystem.
function FocusView({ f }: { f: any }) {
  const { pid, send } = useProject(); const nav = useNavigate()
  const lists = Object.entries(f).filter(([k]) => k !== 'name') as [string, any[]][]
  const LINK: Record<string, string> = { high_ap: 'fmea', unassessed: '', field_events: 'field_events', findings_open: 'findings', reviews: 'reviews', hazards: 'fmea', safety_functions: 'functions', regulations: 'regulations', regulations_without_requirements: 'regulations', certification: 'tests', tests: 'tests', requirements_without_tests: 'requirements', process_steps: 'process_steps', process_steps_without_pfmea: 'process_steps', suppliers: 'suppliers', buy_parts_without_supplier: 'parts', gates: 'gates', pending_handoffs: 'handoffs', risks: 'risks', claims: 'claims', claims_unsubstantiated: 'claims', claims_substantiated: 'claims', claims_unapproved: 'claims', moes: 'moes', labelling_regulations: 'regulations', consumer_needs: 'needs', positioning_notes: 'notes', parts_without_cost: 'parts', capex_items: 'process_steps', open_risks: 'risks', teams: 'teams', teams_without_lead: 'teams', teams_without_members: 'teams', overloaded_teams: 'teams', process_steps_without_station: 'process_steps', lab_tests_needing_equipment: 'tests', mains_safety_tests: 'tests', facility_notes: 'notes', suppliers_without_agreement: 'suppliers', ip_notes: 'notes', field_events_open: 'field_events', field_replaceable_parts: 'parts', user_replaceable_parts: 'parts', high_ap_without_diagnostic: 'fmea', service_notes: 'notes' }
  const FORM: Record<string, string> = { reliability: 'dfmea', quality: 'findings', safety: 'hazards', compliance: 'reqspec', test: 'dvpr', manufacturing: 'pfmea', sourcing: 'avl', program: 'risks', marketing: 'claims', sales: 'markets', finance: 'cost', hr: 'staffing', people: 'staffing', legal: 'claims', service: 'fracas', facilities: 'pfmea' }
  const TEXT = new Set(['price_and_launch', 'cost_roll_up', 'roles_needed'])
  return <div className="stack" style={{ gap: 14 }}>
    <div className="row between"><div className="muted small">Cross-cutting view for <b>{f.name}</b> across every subsystem.</div><div className="row">{FORM[f.name] && <button className="btn sm" onClick={() => nav(`/p/${pid}/form/${FORM[f.name]}`)}>Open the {f.name} form</button>}<button className="chip" onClick={() => send(`As the ${f.name} team: review the whole product across subsystems and tell me the top 5 things we should act on this week, each with the element ids`, ({ marketing: 'marketing', sales: 'sales', finance: 'finance', hr: 'people', people: 'people', facilities: 'facilities', legal: 'legal', service: 'service', reliability: 'risk', quality: 'field_quality', safety: 'risk', compliance: 'requirements', test: 'verification', manufacturing: 'manufacturing', sourcing: 'sourcing', program: 'program' } as Record<string, string>)[f.name])}><Sparkles size={13} />what should we act on</button></div></div>
    <div className="grid3">{lists.map(([k, xs]) => <div key={k} className="card"><div className="row between"><h4>{k.replace(/_/g, ' ')}</h4><span className={'pill ' + (/without|open|unassessed|pending/.test(k) && xs.length ? 'warn' : '')}>{xs.length}</span></div>
      <div className="stack" style={{ gap: 3, maxHeight: 260, overflow: 'auto' }}>{xs.slice(0, 40).map((x: any, i: number) => { const id = typeof x === 'string' ? x : x.id || x.item || JSON.stringify(x); const kind = LINK[k] || (typeof x === 'object' ? x.kind : undefined)
        if (TEXT.has(k)) return <div key={i} className="small">{String(x)}</div>
        return <div key={i} className="small"><IdLink id={id} kind={kind || undefined} />{typeof x === 'object' && x.mode ? <span className="muted"> {x.guide} — {x.mode}</span> : typeof x === 'object' && x.guide ? <span className="muted"> {x.element} · {x.guide}</span> : null}</div> })}{xs.length > 40 && <span className="muted small">+{xs.length - 40} more</span>}{!xs.length && <span className="muted small">—</span>}</div></div>)}</div>
  </div>
}