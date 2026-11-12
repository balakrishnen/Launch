// Leading indicators — anticipatory control. Each indicator comes from the graph and its history with a threshold; reds and ambers
// roll into a gate-slip risk per upcoming gate, and each one carries the intervention (agent role + prompt) that acts on it now.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, AlertTriangle, CheckCircle2, HelpCircle, OctagonAlert } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { IdLink } from '../components/common'

const Lvl = ({ l }: { l: string }) => l === 'red' ? <OctagonAlert size={15} color="var(--bad)" /> : l === 'amber' ? <AlertTriangle size={15} color="var(--warn)" /> : l === 'green' ? <CheckCircle2 size={15} color="var(--good)" /> : <HelpCircle size={15} color="var(--ink-3)" />
const color = (l: string) => l === 'red' ? 'var(--bad)' : l === 'amber' ? 'var(--warn)' : l === 'green' ? 'var(--good)' : 'var(--ink-3)'

export function Indicators() {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate()
  const [d, setD] = useState<any>(null)
  useEffect(() => { P(pid).get('/indicators').then(setD).catch(() => setD(null)) }, [pid, patches.length, project?.meta?.rev])
  if (!d) return <div className="empty">Loading…</div>
  const byKey: Record<string, any> = {}; for (const x of d.interventions || []) byKey[x.key] = x
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Leading indicators</h2><div className="muted small">Computed from the model and its last {d.window_revs || '—'} revisions. Reds are the surprises the next gate review would otherwise discover; each has an intervention that runs now.</div></div>
      <button className="chip" onClick={() => send('Run leading_indicators and act on every red: send each intervention to its role, raise the work items and program risks, then report the gate-slip risk for the next gate with its drivers', 'program')}><Sparkles size={13} />act on all reds</button></div>
    <div className="kpis" style={{ marginBottom: 14 }}>
      <div className="kpi"><div className="v" style={{ color: 'var(--bad)' }}>{d.summary.red}</div><div className="l">red</div></div><div className="kpi"><div className="v" style={{ color: 'var(--warn)' }}>{d.summary.amber}</div><div className="l">amber</div></div><div className="kpi"><div className="v" style={{ color: 'var(--good)' }}>{d.summary.green}</div><div className="l">green</div></div>
      <div className="kpi"><div className="v">{d.days_to_next ?? '—'}</div><div className="l">days to {d.next_gate || 'next gate'}</div></div></div>
    <div className="stack" style={{ gap: 14 }}>
      <div className="card" style={{ padding: 0, overflow: 'auto', order: 2 }}><table className="dt"><thead><tr><th style={{ width: 28 }} /><th>Indicator</th><th>Value</th><th>Amber / red</th><th>Behind it</th><th>Intervention</th></tr></thead><tbody>
        {d.indicators.map((i: any) => <tr key={i.key} style={i.level === 'green' ? { opacity: 0.75 } : {}}><td><Lvl l={i.level} /></td><td><div>{i.name}</div>{i.note && <div className="muted small">{i.note}</div>}</td><td className="num" style={{ color: color(i.level), fontWeight: 600 }}>{i.value ?? '—'}{i.value !== null && i.value !== undefined ? ' ' + (i.unit || '') : ''}</td><td className="small muted">{i.higher_worse === false ? '≤' : '≥'} {i.amber} / {i.red}</td>
          <td className="ids small">{(i.ids || []).slice(0, 6).map((x: string) => <IdLink key={x} id={x} />)}{i.n > 6 && <span className="muted"> +{i.n - 6}</span>}</td>
          <td>{byKey[i.key] && <button className="chip" onClick={() => send(byKey[i.key].prompt + (byKey[i.key].ids?.length ? ' — ' + byKey[i.key].ids.slice(0, 12).join(', ') : ''), byKey[i.key].role)}><Sparkles size={12} />{byKey[i.key].role}</button>}</td></tr>)}</tbody></table></div>
      <div className="card" style={{ order: 1 }}><h4>Gate-slip risk</h4><div className="muted small" style={{ margin: '2px 0 8px' }}>Open deliverables against days remaining, plus the red/amber indicators that bear on the gate. Burn = deliverables that must close per week to make the date.</div>
        <table className="dt"><thead><tr><th /><th>Gate</th><th>Date</th><th>Days</th><th>Open</th><th>Burn / wk</th><th>Drivers</th></tr></thead><tbody>
          {d.gates.map((g: any) => <tr key={g.gate} className="clickable" onClick={() => nav(`/p/${pid}/pdp`)}><td><Lvl l={g.level} /></td><td><b>{g.gate}</b> <span className="muted small">{g.name !== g.gate ? g.name : ''}</span></td><td className="small">{g.date}</td><td className="num">{g.days}</td><td className="num">{g.open_deliverables}/{g.deliverables}</td><td className="num">{g.burn_per_week}</td><td className="small muted">{(g.drivers || []).join(', ')}</td></tr>)}</tbody></table>
        <div className="muted small" style={{ marginTop: 8 }}>Thresholds are the platform defaults; the organization can tune them under Policy. The history window is the last {d.window_revs || 'n'} patches.</div></div>
    </div>
  </div>
}
