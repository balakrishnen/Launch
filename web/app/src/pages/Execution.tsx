// Agile execution visuals driven by the graph: Board (kanban over work items; moving a card is a patch), Timeline (gates,
// handoffs, work, results on one time axis), Trend (the thread's burndown over revisions), and the Harness page
// (policy, roles, tools, skills, watchers — the agent harness as something you can see and set).
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Shield, Bot, Wrench, BookOpen, Eye } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL } from '../api'
import { IdLink } from '../components/common'

const COL_LABEL: Record<string, string> = { open: 'Open', in_progress: 'In progress', blocked: 'Blocked', review: 'In review', done: 'Done' }

export function Board() {
  const { pid, project, patches, toast, send } = useProject(); const nav = useNavigate()
  const [b, setB] = useState<any>(null); const [team, setTeam] = useState(''); const [drag, setDrag] = useState<string | null>(null)
  useEffect(() => { P(pid).get('/board').then(setB).catch(() => { }) }, [pid, patches.length, project?.meta?.rev])
  if (!b) return <div className="empty">Loading board…</div>
  const move = async (id: string, status: string) => { try { const r = await P(pid).post('/patch', { ops: [{ op: 'update', kind: 'work_items', id, value: { status } }], rationale: `${id} → ${COL_LABEL[status]} (board)`, apply: true }); toast(`Applied ${r.patch_id}`) } catch (e: any) { toast(e.message) } }
  const nextGate = b.gates.find((g: any) => g.status !== 'passed')
  return <div>
    <div className="row between" style={{ marginBottom: 10 }}><div><h2>Board</h2><div className="muted small">Work items by status, drag to move (each move is a patch). {nextGate ? <>Next gate <b>{nextGate.id}</b> · {nextGate.date}</> : ''}</div></div>
      <div className="row"><select className="field" style={{ width: 'auto' }} value={team} onChange={e => setTeam(e.target.value)}><option value="">All teams</option>{Object.entries(b.teams).map(([t, n]: any) => <option key={t} value={t}>{n}</option>)}</select><button className="chip" onClick={() => send(`Groom the board: for every open finding and pending handoff without a work item, propose a work item with owner, team, due date before ${nextGate?.date || 'the next gate'} and priority`)}><Sparkles size={13} />groom with the agent</button></div></div>
    <div className="board">{b.columns.map((c: string) => { const items = (b.items[c] || []).filter((w: any) => !team || w.team === team)
      return <div key={c} className={'col' + (drag ? ' droppable' : '')} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (drag) { move(drag, c); setDrag(null) } }}>
        <div className="colhead"><span>{COL_LABEL[c]}</span><span className="n">{items.length}</span></div>
        {items.map((w: any) => <div key={w.id} className={'wcard' + (w.overdue ? ' overdue' : '')} draggable onDragStart={() => setDrag(w.id)} onDragEnd={() => setDrag(null)} onClick={() => nav(`/p/${pid}/element/work_items/${w.id}`)}>
          <div className="row between"><span className="id small">{w.id}</span><span className={'pill ' + (w.priority === 'P0' || w.priority === 'P1' ? 'bad' : '')} style={{ fontSize: 10 }}>{w.priority}</span></div>
          <div className="t">{w.title}</div>
          <div className="row between small muted"><span>{b.teams[w.team] || w.owner}</span><span className={w.overdue ? 'bad' : ''} style={w.overdue ? { color: 'var(--bad)' } : {}}>{w.due}{w.gate ? ` · ${w.gate}` : ''}</span></div>
          {w.links?.length > 0 && <div className="small" style={{ marginTop: 4 }}>{w.links.slice(0, 4).map((l: string) => <IdLink key={l} id={l} />)}</div>}
        </div>)}
      </div> })}</div>
    <div className="grid2" style={{ marginTop: 16 }}>
      <div className="card"><h4>Open findings without a work item</h4>{b.findings_open.filter((f: any) => !Object.values(b.items).flat().some((w: any) => (w.links || []).includes(f.id))).map((f: any) => <div key={f.id} className="link"><span className={'pill ' + (f.severity === 'critical' || f.severity === 'major' ? 'bad' : 'warn')}>{f.severity}</span><span><IdLink id={f.id} kind="findings" /> {f.title}</span></div>)}</div>
      <div className="card"><h4>Pending handoffs</h4>{b.handoffs_pending.map((h: any) => <div key={h.id} className="link"><span className="rel">{b.teams[h.from_team] || h.from_team} → {b.teams[h.to_team] || h.to_team}</span><span><IdLink id={h.id} kind="handoffs" /> {h.what} <span className="muted small">{h.due}</span></span></div>)}{!b.handoffs_pending.length && <span className="muted small">None.</span>}</div>
    </div>
  </div>
}

export function Timeline() {
  const { pid, project, patches } = useProject(); const nav = useNavigate()
  const [t, setT] = useState<any>(null)
  useEffect(() => { P(pid).get('/timeline').then(setT).catch(() => { }) }, [pid, patches.length, project?.meta?.rev])
  const lanes = useMemo(() => { if (!t) return []; const g: Record<string, any[]> = {}; for (const r of t.rows) (g[r.lane] ??= []).push(r); const order = (l: string) => l === 'Program' ? 0 : l === 'Gates' ? 1 : l === 'Test results' ? 9 : 5; return Object.entries(g).sort((a, b) => order(a[0]) - order(b[0]) || a[0].localeCompare(b[0])) }, [t])
  if (!t) return <div className="empty">Loading timeline…</div>
  if (!t.rows.length) return <div className="empty">Nothing dated yet — gates, handoffs and work items with due dates appear here.</div>
  const ds = t.rows.flatMap((r: any) => [r.start, r.end]).concat([t.today]).map((d: string) => Date.parse(d)).filter((x: number) => !isNaN(x))
  const d0 = Math.min(...ds) - 5 * 864e5, d1 = Math.max(...ds) + 10 * 864e5; const W = 1100, L = 220, R = 20, rowH = 26, top = 36
  const H = top + lanes.reduce((a, [, rs]) => a + Math.max(1, rs.length) * rowH + 8, 0) + 10
  const x = (d: string) => L + (Date.parse(d) - d0) / (d1 - d0) * (W - L - R)
  const col: Record<string, string> = { gates: '#0e7490', handoffs: '#b45309', work_items: '#2f6fed', test_runs: '#15803d', program: '#6d28d9' }
  const months: string[] = []; for (let d = new Date(d0); d.getTime() < d1; d.setMonth(d.getMonth() + 1, 1)) months.push(new Date(d).toISOString().slice(0, 10))
  let y = top
  return <div>
    <div className="row between" style={{ marginBottom: 8 }}><div><h2>Timeline</h2><div className="muted small">Gates, handoffs, work and test results on one axis — every bar is a record; click to open.</div></div><div className="row small" style={{ gap: 10 }}>{Object.entries(col).map(([k, c]) => <span key={k} className="row" style={{ gap: 4 }}><span className="sw" style={{ width: 10, height: 10, borderRadius: 2, background: c }} />{KIND_LABEL[k] || k}</span>)}</div></div>
    <div className="card" style={{ overflowX: 'auto' }}><svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', minWidth: 900, height: 'auto', display: 'block' }}>
      {months.filter((m, i) => i === 0 ? (months[1] ? x(months[1]) - x(m) > 48 : true) : true).map(m => <g key={m}><line x1={x(m)} x2={x(m)} y1={top - 10} y2={H} stroke="var(--line)" /><text x={x(m) + 3} y={14} fontSize="11" fill="var(--ink-3)">{new Date(m).toLocaleString(undefined, { month: 'short', year: '2-digit' })}</text></g>)}
      <line x1={x(t.today)} x2={x(t.today)} y1={top - 10} y2={H} stroke="var(--accent)" strokeDasharray="4 3" /><text x={x(t.today) + 3} y={top - 14} fontSize="10" fill="var(--accent-ink)">today</text>
      {lanes.map(([lane, rs]) => { const y0 = y; y += Math.max(1, rs.length) * rowH + 8
        return <g key={lane}><line x1={0} x2={W} y1={y0 - 4} y2={y0 - 4} stroke="var(--line)" /><text x={8} y={y0 + 14} fontSize="12" fontWeight={600} fill="var(--ink)">{lane.length > 30 ? lane.slice(0, 29) + '…' : lane}</text>
          {rs.map((r: any, i: number) => { const xs = x(r.start), xe = Math.max(x(r.end), xs + 6); const yy = y0 + i * rowH; const c = col[r.kind] || 'var(--sx)'; const done = ['done', 'passed', 'accepted', 'pass', 'closed'].includes(r.status)
            return <g key={r.id} style={{ cursor: 'pointer' }} onClick={() => nav(r.kind === 'test_runs' ? `/p/${pid}/run/${r.id}` : r.kind === 'program' ? `/p/${pid}/teams` : `/p/${pid}/element/${r.kind}/${encodeURIComponent(r.id)}`)}>
              {r.kind === 'gates' ? <polygon points={`${xs},${yy + 4} ${xs + 7},${yy + 11} ${xs},${yy + 18} ${xs - 7},${yy + 11}`} fill={done ? c : 'var(--surface)'} stroke={c} strokeWidth={2} /> : <rect x={xs} y={yy + 5} width={xe - xs} height={14} rx={4} fill={c} opacity={done ? 0.45 : 0.9} />}
              <text x={xe + 8} y={yy + 16} fontSize="11" fill="var(--ink-2)">{r.label}{r.status && r.kind !== 'program' ? ` · ${r.status}` : ''}</text></g> })}</g> })}
    </svg></div>
  </div>
}

export function Trend() {
  const { pid, project, patches } = useProject()
  const [t, setT] = useState<any>(null)
  useEffect(() => { P(pid).get('/trend').then(setT).catch(() => { }) }, [pid, patches.length, project?.meta?.rev])
  if (!t) return <div className="empty">Loading…</div>
  if (!t.supported || t.points.length < 2) return <div className="empty">Trend needs the database store and more than one revision. {t.note || ''}</div>
  const series = [['open_gaps', 'Open trace gaps', '#b91c1c'], ['unassessed', 'Unassessed failure modes', '#c2410c'], ['open_findings', 'Open findings', '#b45309'], ['open_work', 'Open work items', '#2f6fed'], ['tests_passed', 'Tests passed', '#15803d'], ['requirements', 'Requirements', '#6d28d9']]
  return <div><h2>Trend</h2><div className="muted small" style={{ marginBottom: 10 }}>The thread's burndown over revisions — what the agents and the team closed, and what grew.</div>
    <div className="grid3">{series.map(([k, label, c]) => <Spark key={k} label={label} color={c} xs={t.points.map((p: any) => p.rev)} ys={t.points.map((p: any) => p[k])} />)}</div></div>
}
function Spark({ label, color, xs, ys }: { label: string; color: string; xs: number[]; ys: number[] }) {
  const W = 320, H = 110, L = 30, R = 10, T = 10, B = 22; const y0 = 0, y1 = Math.max(1, ...ys) * 1.1; const x0 = xs[0], x1 = xs[xs.length - 1] || x0 + 1
  const sx = (v: number) => L + (v - x0) / Math.max(1, x1 - x0) * (W - L - R), sy = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B)
  const pts = xs.map((x, i) => `${sx(x).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join(' ')
  return <div className="card"><div className="row between"><h4>{label}</h4><b style={{ color }}>{ys[ys.length - 1]}</b></div><svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}><polyline points={pts} fill="none" stroke={color} strokeWidth={2} /><polygon points={`${sx(x0)},${sy(0)} ${pts} ${sx(x1)},${sy(0)}`} fill={color} opacity={0.08} /><text x={L} y={H - 6} fontSize="10" fill="var(--ink-3)">rev {x0}</text><text x={W - R} y={H - 6} fontSize="10" textAnchor="end" fill="var(--ink-3)">rev {x1}</text></svg></div>
}

export function Harness() {
  const { pid, project, toast } = useProject()
  const [h, setH] = useState<any>(null); const [pol, setPol] = useState<any>(null)
  useEffect(() => { P(pid).get('/harness').then(x => { setH(x); setPol(x.policy) }).catch(() => { }) }, [pid])
  if (!h || !pol) return <div className="empty">Loading harness…</div>
  const kinds = Object.keys(project?.schema || {})
  const toggle = (list: string[], v: string) => list.includes(v) ? list.filter(x => x !== v) : [...list, v]
  const save = async () => { try { const r = await P(pid).post('/harness', { policy: pol }); setH(r); toast('Harness policy saved') } catch (e: any) { toast(e.message) } }
  const Chips = ({ list, onToggle, all }: { list: string[]; onToggle: (v: string) => void; all: string[] }) => <div className="row" style={{ gap: 5, flexWrap: 'wrap' }}>{all.map(k => <button key={k} className="chip" style={list.includes(k) ? { borderColor: 'var(--accent)', color: 'var(--accent-ink)', background: 'var(--accent-soft)' } : {}} onClick={() => onToggle(k)}>{KIND_LABEL[k] || k}</button>)}</div>
  return <div>
    <div className="row between" style={{ marginBottom: 10 }}><div><h2>Agent harness</h2><div className="muted small">What the agents are allowed to do in this project, and how. Versioned with the project (<code>.sethread/harness.yaml</code>).</div></div><button className="btn primary" onClick={save}>Save policy</button></div>
    <div className="grid2" style={{ alignItems: 'start' }}>
      <div className="stack" style={{ gap: 14 }}>
        <div className="card"><h4><Shield size={14} style={{ verticalAlign: -2 }} /> Policy — the syscall</h4><div className="small muted" style={{ marginBottom: 8 }}>{h.syscall}</div>
          <div className="small" style={{ fontWeight: 600, marginTop: 8 }}>Auto-apply without a reviewer when every op is in</div><Chips all={kinds} list={pol.auto_apply.kinds} onToggle={v => setPol({ ...pol, auto_apply: { ...pol.auto_apply, kinds: toggle(pol.auto_apply.kinds, v) } })} />
          <div className="row small" style={{ marginTop: 6, gap: 8 }}>and the patch has at most <input className="field" style={{ width: 70 }} type="number" value={pol.auto_apply.max_ops} onChange={e => setPol({ ...pol, auto_apply: { ...pol.auto_apply, max_ops: Number(e.target.value) } })} /> ops</div>
          <div className="small" style={{ fontWeight: 600, marginTop: 12 }}>Always needs a reviewer</div><Chips all={kinds} list={pol.require_review.kinds} onToggle={v => setPol({ ...pol, require_review: { ...pol.require_review, kinds: toggle(pol.require_review.kinds, v) } })} />
          <div className="row small" style={{ marginTop: 6, gap: 8 }}>reviewer is the element's owner team; fallback <select className="field" style={{ width: 'auto' }} value={pol.require_review.fallback_team || ''} onChange={e => setPol({ ...pol, require_review: { ...pol.require_review, fallback_team: e.target.value || null } })}><option value="">—</option>{Object.entries(project?.teams || {}).map(([t, v]: any) => <option key={t} value={t}>{v.name}</option>)}</select></div></div>
        <div className="card"><h4><Bot size={14} style={{ verticalAlign: -2 }} /> Roles (processes)</h4><div className="stack" style={{ gap: 4 }}>{h.roles.map((r: any) => <label key={r.id} className="row small" style={{ gap: 8 }}><input type="checkbox" checked={pol.agents.enabled.includes(r.id)} onChange={() => setPol({ ...pol, agents: { ...pol.agents, enabled: toggle(pol.agents.enabled, r.id) } })} /><b style={{ width: 120 }}>{r.id}</b><span>{r.title}</span><span className="muted">{r.kinds.join(', ')}</span></label>)}</div>
          <div className="row small" style={{ marginTop: 8, gap: 12 }}><label className="row" style={{ gap: 5 }}><input type="checkbox" checked={pol.agents.web} onChange={e => setPol({ ...pol, agents: { ...pol.agents, web: e.target.checked } })} />web research</label><label className="row" style={{ gap: 5 }}><input type="checkbox" checked={pol.agents.shell} onChange={e => setPol({ ...pol, agents: { ...pol.agents, shell: e.target.checked } })} />shell / toolchain without asking</label><span>max turns <input className="field" style={{ width: 70 }} type="number" value={pol.agents.max_turns} onChange={e => setPol({ ...pol, agents: { ...pol.agents, max_turns: Number(e.target.value) } })} /></span></div></div>
      </div>
      <div className="stack" style={{ gap: 14 }}>
        <div className="card"><h4><Eye size={14} style={{ verticalAlign: -2 }} /> Watchers — run after every applied patch</h4>{h.watchers.map((w: any) => <div key={w.id} className="link"><span className="rel">{w.id}</span><span className="small">{w.what}</span></div>)}</div>
        <div className="card"><h4><BookOpen size={14} style={{ verticalAlign: -2 }} /> Skills — knowledge the agents consult before inventing</h4>{h.skills.map((s: any) => <div key={s.id} className="row between small"><span>{s.id.replace(/_/g, ' ')}</span><b>{s.entries} entries</b></div>)}<div className="muted small" style={{ marginTop: 6 }}>YAML under <code>sethread/library/</code>; a project can add its own under <code>.sethread/library/</code>.</div></div>
        <div className="card"><h4><Wrench size={14} style={{ verticalAlign: -2 }} /> Tools the agents hold</h4><div className="row" style={{ gap: 4, flexWrap: 'wrap' }}>{h.tools.map((t: string) => <span key={t} className="pill mono" style={{ fontSize: 11 }}>{t}</span>)}</div></div>
        <div className="card"><h4>Graph memory</h4><div className="small">{h.memory}</div></div>
      </div>
    </div>
  </div>
}
