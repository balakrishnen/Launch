// Analytics — project status and lifecycle intelligence in one tab: a project-maturity composite against the expected profile
// at the next gate, the burndown over revisions, gate readiness, departments, verification, risk, quality, supply, cost, TRL,
// critical design attributes, change and activity. Charts are inline SVG with the validated chart palette (never brand colours);
// every number links back to the elements behind it.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'

// validated chart palette (light / dark) — categorical in fixed order, status reserved
const C = { s1: 'var(--ch-1)', s2: 'var(--ch-2)', s3: 'var(--ch-3)', s4: 'var(--ch-4)', good: 'var(--ch-good)', warn: 'var(--ch-warn)', serious: 'var(--ch-serious)', bad: 'var(--ch-bad)', ink: 'var(--ink)', ink3: 'var(--ink-3)', line: 'var(--line)' }
const STYLE = `:root{--ch-1:#2a78d6;--ch-2:#eb6834;--ch-3:#1baf7a;--ch-4:#eda100;--ch-good:#0ca30c;--ch-warn:#fab219;--ch-serious:#ec835a;--ch-bad:#d03b3b}
:root[data-theme="dark"]{--ch-1:#3987e5;--ch-2:#d95926;--ch-3:#199e70;--ch-4:#c98500;--ch-good:#0ca30c;--ch-warn:#fab219;--ch-serious:#ec835a;--ch-bad:#d03b3b}
.an-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}.an-card h4{margin-bottom:6px}.an-sub{color:var(--ink-3);font-size:12px;margin-bottom:8px}.an-leg{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--ink-2);margin-top:6px}.an-leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.an-svg text{font-family:var(--font);fill:var(--ink-3);font-size:11px}.an-svg .v{fill:var(--ink);font-weight:600}.an-svg rect.bar:hover,.an-svg circle:hover{opacity:.8}`

const fmt = (v: any, d = 0) => v === null || v === undefined ? '—' : typeof v === 'number' ? v.toFixed(d) : String(v)

// --- primitives ------------------------------------------------------------------------------------------------
function HBars({ rows, max, label = (r: any) => r.name, value = (r: any) => r.value, color = () => C.s1, marker, onClick, h = 22 }: { rows: any[]; max?: number; label?: (r: any) => string; value?: (r: any) => number; color?: (r: any) => string; marker?: (r: any) => number | null | undefined; onClick?: (r: any) => void; h?: number }) {
  const W = 420, L = 150, R = 56; const mx = max ?? Math.max(1, ...rows.map(r => value(r) || 0)); const H = rows.length * h + 4
  return <svg className="an-svg" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }}>{rows.map((r, i) => { const v = value(r) || 0; const w = Math.max(0, (W - L - R) * v / mx); const y = i * h + 2; const mk = marker?.(r)
    return <g key={i} style={{ cursor: onClick ? 'pointer' : undefined }} onClick={() => onClick?.(r)}><title>{label(r)}: {fmt(v, 1)}</title><text x={L - 8} y={y + h / 2 + 4} textAnchor="end">{label(r).slice(0, 24)}</text>
      <rect className="bar" x={L} y={y + 4} width={w} height={h - 8} rx={3} fill={color(r)} />{mk !== null && mk !== undefined && <line x1={L + (W - L - R) * mk / mx} x2={L + (W - L - R) * mk / mx} y1={y + 1} y2={y + h - 1} stroke={C.ink} strokeWidth={2} />}
      <text className="v" x={L + w + 6} y={y + h / 2 + 4}>{fmt(v, v % 1 ? 1 : 0)}</text></g> })}</svg>
}
function Stacked({ rows, keys, colors, label = (r: any) => r.name, onClick, h = 22 }: { rows: any[]; keys: string[]; colors: string[]; label?: (r: any) => string; onClick?: (r: any) => void; h?: number }) {
  const W = 420, L = 110, R = 40; const mx = Math.max(1, ...rows.map(r => keys.reduce((a, k) => a + (r[k] || 0), 0))); const H = rows.length * h + 4
  return <svg className="an-svg" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }}>{rows.map((r, i) => { let x = L; const y = i * h + 2; const tot = keys.reduce((a, k) => a + (r[k] || 0), 0)
    return <g key={i} style={{ cursor: onClick ? 'pointer' : undefined }} onClick={() => onClick?.(r)}><text x={L - 8} y={y + h / 2 + 4} textAnchor="end">{label(r).slice(0, 16)}</text>{keys.map((k, j) => { const w = (W - L - R) * (r[k] || 0) / mx; const el = <rect key={k} className="bar" x={x} y={y + 4} width={Math.max(0, w - 2)} height={h - 8} rx={2} fill={colors[j]}><title>{label(r)} · {k}: {r[k] || 0}</title></rect>; x += w; return el })}<text className="v" x={x + 6} y={y + h / 2 + 4}>{tot}</text></g> })}</svg>
}
function Lines({ points, keys, colors, x = (p: any) => p.rev, W = 420, H = 150 }: { points: any[]; keys: string[]; colors: string[]; x?: (p: any) => any; W?: number; H?: number }) {
  const L = 36, B = 22, T = 8; const n = points.length; if (n < 2) return <div className="muted small">Not enough history yet.</div>
  const mx = Math.max(1, ...points.flatMap(p => keys.map(k => p[k] || 0))); const X = (i: number) => L + (W - L - 8) * i / (n - 1); const Y = (v: number) => T + (H - T - B) * (1 - v / mx)
  const [hover, setHover] = useState<number | null>(null)
  return <svg className="an-svg" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }} onMouseLeave={() => setHover(null)}>
    {[0, 0.5, 1].map(f => <g key={f}><line x1={L} x2={W - 8} y1={Y(mx * f)} y2={Y(mx * f)} stroke={C.line} /><text x={L - 4} y={Y(mx * f) + 4} textAnchor="end">{Math.round(mx * f)}</text></g>)}
    {keys.map((k, j) => <polyline key={k} fill="none" stroke={colors[j]} strokeWidth={2} points={points.map((p, i) => `${X(i)},${Y(p[k] || 0)}`).join(' ')} />)}
    {points.map((_p, i) => <rect key={i} x={X(i) - (W - L) / n / 2} y={0} width={(W - L) / n} height={H} fill="transparent" onMouseEnter={() => setHover(i)} />)}
    {hover !== null && <g><line x1={X(hover)} x2={X(hover)} y1={T} y2={H - B} stroke={C.ink3} strokeDasharray="3 3" />{keys.map((k, j) => <circle key={k} cx={X(hover)} cy={Y(points[hover][k] || 0)} r={4} fill={colors[j]} stroke="var(--bg)" strokeWidth={2} />)}
      <text x={Math.min(X(hover) + 6, W - 120)} y={T + 12} className="v">{String(x(points[hover]))} · {keys.map(k => `${k} ${fmt(points[hover][k], 1)}`).join(' · ')}</text></g>}
    <text x={L} y={H - 6}>{String(x(points[0]))}</text><text x={W - 8} y={H - 6} textAnchor="end">{String(x(points[n - 1]))}</text></svg>
}
function Cols({ rows, keys, colors, label = (r: any) => r.week, W = 420, H = 140 }: { rows: any[]; keys: string[]; colors: string[]; label?: (r: any) => string; W?: number; H?: number }) {
  const L = 30, B = 24, T = 8; const n = Math.max(1, rows.length); const mx = Math.max(1, ...rows.map(r => keys.reduce((a, k) => a + (r[k] || 0), 0))); const bw = (W - L - 8) / n
  if (!rows.length) return <div className="muted small">No data yet.</div>
  return <svg className="an-svg" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }}>{rows.map((r, i) => { let y = H - B; return <g key={i}>{keys.map((k, j) => { const h = (H - B - T) * (r[k] || 0) / mx; y -= h; return <rect key={k} className="bar" x={L + i * bw + 2} y={y + 1} width={Math.max(1, bw - 4)} height={Math.max(0, h - 2)} rx={2} fill={colors[j]}><title>{label(r)} · {k}: {r[k] || 0}</title></rect> })}{(i % Math.ceil(n / 6) === 0 || i === n - 1) && <text x={L + i * bw + bw / 2} y={H - 8} textAnchor="middle">{label(r).slice(-6)}</text>}</g> })}<text x={L - 4} y={T + 10} textAnchor="end">{mx}</text></svg>
}
const Tile = ({ v, l, c, to, nav }: { v: any; l: string; c?: string; to?: string; nav?: (p: string) => void }) => <div className="kpi" style={{ cursor: to ? 'pointer' : undefined }} onClick={() => to && nav?.(to)}><div className="v" style={{ color: c }}>{v ?? '—'}</div><div className="l">{l}</div></div>

// --- page ------------------------------------------------------------------------------------------------------
export function Analytics() {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate(); const go = (p: string) => nav(`/p/${pid}${p.startsWith('/') ? p : '/' + p}`)
  const [d, setD] = useState<any>(null)
  useEffect(() => { P(pid).get('/analytics').then(setD).catch(() => setD(null)) }, [pid, patches.length, project?.meta?.rev])
  if (!d) return <div className="empty">Loading…</div>
  const h = d.headline; const mt = d.maturity_score; const subs = Object.entries(mt.sub || {}).map(([k, v]: any) => ({ key: k, name: k.replace(/_/g, ' '), value: v.score ?? 0, detail: v.detail, link: v.link, weight: mt.weights[k] }))
  const lvl = (s: string) => s === 'red' ? C.bad : s === 'amber' ? C.warn : s === 'green' ? C.good : C.ink3
  const shortfall = mt.shortfall_next
  return <div><style>{STYLE}</style>
    <div className="row between" style={{ marginBottom: 10 }}><div><h2>Analytics</h2><div className="muted small">Lifecycle intelligence for {project?.meta?.name}: where the project is, how fast it is maturing, and what will surprise the next gate. Everything here derives from the model and its history.</div></div>
      <button className="chip" onClick={() => send('Read the analytics and maturity: give me the steering-committee summary — maturity vs expected at the next gate, the three sub-scores holding it back with the element ids, the gate-slip risk and the interventions already in flight', 'program')}><Sparkles size={13} />steering summary</button></div>
    <div className="kpis" style={{ marginBottom: 14 }}>
      <Tile v={mt.score} l={`project maturity · ${mt.level}`} c={shortfall !== null && shortfall > 0 ? C.serious : C.good} />
      <Tile v={mt.expected_next ?? '—'} l={`expected at ${mt.next_gate || 'next gate'} (${h.days_to_next ?? '—'} d)`} />
      <Tile v={shortfall !== null && shortfall !== undefined ? (shortfall > 0 ? '−' + shortfall : '+' + (-shortfall).toFixed(1)) : '—'} l={shortfall > 0 ? 'behind the profile' : 'ahead of the profile'} c={shortfall > 0 ? C.bad : C.good} />
      <Tile v={h.indicators.red} l="red indicators" c={h.indicators.red ? C.bad : C.good} to="/indicators" nav={go} />
      <Tile v={`${h.tests_passed}/${h.tests}`} l="tests passed" to="/form/dvpr" nav={go} /><Tile v={h.high_ap} l="High-AP failure modes" to="/form/dfmea" nav={go} /><Tile v={h.open_gaps} l="trace gaps" to="/artifacts" nav={go} /><Tile v={h.open_work} l="open work items" to="/board" nav={go} /></div>

    <div className="an-grid">
      <div className="card an-card" style={{ gridColumn: 'span 2' }}><h4>Project maturity</h4><div className="an-sub">Composite of eight sub-scores (weights in brackets), each derived from the graph. The marker is the sub-score's share of the expected profile at {mt.next_gate || 'the next gate'}: a bar short of its marker is where the shortfall comes from.</div>
        <div className="grid2" style={{ gap: 14, alignItems: 'start' }}>
          <HBars rows={subs} max={100} label={r => `${r.name} (${r.weight})`} color={r => r.value >= (mt.expected_next || 0) ? C.s3 : r.value >= (mt.expected_next || 0) * 0.6 ? C.s4 : C.s2} marker={() => mt.expected_next} onClick={r => go(r.link)} />
          <div><table className="dt"><tbody>{subs.map(s => <tr key={s.key} className="clickable" onClick={() => go(s.link)}><td className="small" style={{ textTransform: 'capitalize' }}>{s.name}</td><td className="num"><b>{fmt(s.value, 0)}</b></td><td className="small muted">{s.detail}</td></tr>)}</tbody></table>
            <div className="an-leg"><span><i style={{ background: C.s3 }} />at or above profile</span><span><i style={{ background: C.s4 }} />within 60 %</span><span><i style={{ background: C.s2 }} />below</span><span>▏ expected {mt.expected_next ?? '—'} at {mt.next_gate}</span></div></div></div>
        {d.maturity_history?.length > 1 && <div style={{ marginTop: 10 }}><div className="an-sub">Maturity over revisions — the slope is the question: at this rate, does it reach {mt.expected_next} by {mt.next_date}?</div><Lines points={d.maturity_history} keys={['score', 'verification', 'industrialization']} colors={[C.s1, C.s2, C.s3]} /><div className="an-leg"><span><i style={{ background: C.s1 }} />composite</span><span><i style={{ background: C.s2 }} />verification</span><span><i style={{ background: C.s3 }} />industrialization</span></div></div>}</div>

      <div className="card an-card"><h4>Burndown</h4><div className="an-sub">Open trace gaps, unassessed failure modes and open work over the last revisions.</div>
        {d.trend?.supported ? <><Lines points={d.trend.points} keys={['open_gaps', 'unassessed', 'open_work']} colors={[C.s2, C.s4, C.s1]} /><div className="an-leg"><span><i style={{ background: C.s2 }} />open gaps</span><span><i style={{ background: C.s4 }} />unassessed</span><span><i style={{ background: C.s1 }} />open work</span></div></> : <div className="muted small">History needs the database store.</div>}</div>

      <div className="card an-card"><h4>Gate readiness</h4><div className="an-sub">Deliverables done / partial / missing per gate; the dot is the slip risk from the leading indicators.</div>
        <Stacked rows={d.gates.map((g: any) => ({ ...g, name: `${g.id}${g.days !== null && g.days !== undefined ? ' · ' + g.days + 'd' : ''}` }))} keys={['done', 'partial', 'missing', 'waived']} colors={[C.good, C.warn, C.serious, C.ink3]} onClick={() => go('/pdp')} />
        <div className="an-leg"><span><i style={{ background: C.good }} />done</span><span><i style={{ background: C.warn }} />partial</span><span><i style={{ background: C.serious }} />missing</span><span><i style={{ background: C.ink3 }} />waived</span>{d.gates.map((g: any) => <span key={g.id}><i style={{ background: lvl(g.risk), borderRadius: 5 }} />{g.id} {g.risk || '—'}</span>)}</div></div>

      <div className="card an-card"><h4>Departments</h4><div className="an-sub">Open deliverables by department across all gates, and open work.</div>
        <Stacked rows={d.departments} keys={['done', 'partial', 'missing']} colors={[C.good, C.warn, C.serious]} onClick={r => go(`/dept/${encodeURIComponent(r.name)}`)} /><div className="an-leg"><span><i style={{ background: C.good }} />done</span><span><i style={{ background: C.warn }} />partial</span><span><i style={{ background: C.serious }} />missing</span></div></div>

      <div className="card an-card"><h4>Team load</h4><div className="an-sub">Open work items per team; overdue shown in the darker segment.</div>
        <Stacked rows={d.teams.filter((t: any) => t.open_work || t.deliverables_open).slice(0, 12).map((t: any) => ({ ...t, name: t.name, onTime: t.open_work - t.overdue }))} keys={['onTime', 'overdue', 'deliverables_open']} colors={[C.s1, C.bad, C.s4]} onClick={r => go(`/team/${r.id}`)} /><div className="an-leg"><span><i style={{ background: C.s1 }} />open work</span><span><i style={{ background: C.bad }} />overdue</span><span><i style={{ background: C.s4 }} />deliverables open</span></div></div>

      <div className="card an-card"><h4>Verification</h4><div className="an-sub">Test status, and runs per week (pass / fail).</div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>{Object.entries(d.verification.status).map(([k, v]: any) => <span key={k} className="pill">{k} <b>{v}</b></span>)}<span className="muted small">· {d.verification.runs} runs</span></div>
        <Cols rows={d.verification.runs_by_week} keys={['pass', 'fail']} colors={[C.good, C.bad]} /><div className="an-leg"><span><i style={{ background: C.good }} />pass</span><span><i style={{ background: C.bad }} />fail</span></div></div>

      <div className="card an-card"><h4>Risk</h4><div className="an-sub">Action-priority distribution of assessed failure modes; High-AP by element.</div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>{['H', 'M', 'L'].map(k => <span key={k} className="pill" style={{ background: k === 'H' ? 'var(--bad-soft)' : k === 'M' ? 'var(--warn-soft)' : undefined }}>AP {k} <b>{d.risk.ap[k] || 0}</b></span>)}<span className="pill">unassessed <b>{d.risk.unassessed}</b></span></div>
        {d.risk.high_by_element.length ? <HBars rows={d.risk.high_by_element.map(([e, n]: any) => ({ name: e, value: n }))} color={() => C.bad} onClick={r => go(`/element/parts/${r.name}`)} /> : <div className="muted small">No High-AP failure modes yet — {d.risk.unassessed} candidates wait for assessment.</div>}</div>

      <div className="card an-card"><h4>Quality</h4><div className="an-sub">Supplier PPM, CAPA, build yield.</div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}><span className="pill">CAPA open <b>{d.quality.capa_open}</b></span><span className="pill" style={d.quality.capa_overdue ? { background: 'var(--bad-soft)' } : {}}>overdue <b>{d.quality.capa_overdue}</b></span>{Object.entries(d.quality.findings_status).map(([k, v]: any) => <span key={k} className="pill">findings {k} <b>{v}</b></span>)}</div>
        {d.quality.ppm.length ? <HBars rows={d.quality.ppm.map((p: any) => ({ name: p.supplier, value: p.ppm || 0 }))} color={r => r.value > 500 ? C.bad : C.s3} onClick={() => go('/form/ppm')} /> : <div className="muted small">No incoming inspections yet.</div>}
        {d.quality.work_orders.length > 0 && <div className="small" style={{ marginTop: 6 }}>{d.quality.work_orders.map((w: any) => <div key={w.id}>{w.id} ({w.build}): {w.complete}/{w.built} complete, {w.failed} failed · FPY {w.fpy ?? '—'} %</div>)}</div>}</div>

      <div className="card an-card"><h4>Supply</h4><div className="an-sub">Longest lead times with order-by dates; tooling status.</div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>{Object.entries(d.supply.quote_status).map(([k, v]: any) => <span key={k} className="pill">quotes {k} <b>{v}</b></span>)}<span className="pill" style={d.supply.late ? { background: 'var(--bad-soft)' } : {}}>late to order <b>{d.supply.late}</b></span></div>
        <HBars rows={d.supply.lead_times.map((r: any) => ({ name: `${r.part} · by ${r.order_by || '?'}`, value: r.lead, late: r.late }))} color={r => r.late ? C.bad : C.s1} onClick={() => go('/form/procurement')} />
        <div className="small" style={{ marginTop: 6 }}>{d.supply.tooling.map((t: any) => <span key={t.id} className="pill" style={{ marginRight: 4, background: t.late ? 'var(--bad-soft)' : undefined }}>{t.id} {t.status} · PPAP {t.ppap}</span>)}</div></div>

      <div className="card an-card"><h4>Cost</h4><div className="an-sub">BOM {fmt(d.cost.bom, 2)} vs target {fmt(d.cost.target, 0)} · price {fmt(d.cost.price, 0)} · margin {d.cost.margin !== null ? (d.cost.margin * 100).toFixed(0) + ' %' : '—'} · capex {fmt(d.cost.capex, 0)} · {d.cost.missing} parts without cost. Top items; the marker is the actual (received) cost where known.</div>
        <HBars rows={d.cost.top.map((r: any) => ({ name: `${r.part} ${r.name}`, value: r.cost, actual: r.actual }))} color={() => C.s1} marker={r => r.actual ?? null} onClick={() => go('/form/cost')} /></div>

      <div className="card an-card"><h4>Technology readiness</h4><div className="an-sub">Declared TRL (bar) vs demonstrated by evidence (marker) for new technologies; a bar far past its marker is a claim without proof.</div>
        <HBars rows={d.maturity.trl.filter((r: any) => r.new).map((r: any) => ({ name: r.part, value: r.declared ?? 0, demo: r.demonstrated }))} max={9} color={r => (r.value - r.demo) >= 2 ? C.serious : C.s3} marker={r => r.demo} onClick={() => go('/form/trl')} /></div>

      <div className="card an-card"><h4>Critical design attributes</h4><div className="an-sub">Margin to limit (%): negative is a violation; inside 10 % is tight. Trend from the last runs.</div>
        <HBars rows={d.maturity.cda.map((r: any) => ({ name: `${r.id} ${r.name}`, value: r.margin_limit ?? 0, st: r.status, trend: r.trend }))} max={Math.max(20, ...d.maturity.cda.map((r: any) => Math.abs(r.margin_limit || 0)))} color={r => r.st === 'violating limit' ? C.bad : r.st === 'below target' || r.st === 'tight' ? C.warn : r.st === 'unmeasured' ? C.ink3 : C.good} onClick={() => go('/form/cda')} />
        <div className="an-leg">{d.maturity.cda.filter((r: any) => r.trend).map((r: any) => <span key={r.id}>{r.id} {r.trend === 'worsening' ? '↓' : r.trend === 'improving' ? '↑' : '→'} {r.trend}</span>)}</div></div>

      <div className="card an-card"><h4>Change & activity</h4><div className="an-sub">ECOs by status; patches per week with the share proposed by agents ({d.activity.agent_share ?? '—'} % of {d.activity.total ?? 0}).</div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>{Object.entries(d.change.eco_status).map(([k, v]: any) => <span key={k} className="pill">ECO {k} <b>{v}</b></span>)}</div>
        <Cols rows={d.activity.by_week || []} keys={['patches']} colors={[C.s1]} /></div>
    </div>
  </div>
}
