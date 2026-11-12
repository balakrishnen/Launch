// Trade studies — the decision record behind every architecture choice. Weighted decision matrix (INCOSE SEH §4.3), Pugh view vs the
// datum, knock-out limits, and a sensitivity analysis that says whether the decision is robust. Every score, weight and decision is a
// patch with provenance; the agent fills raw values from tests, simulations and supplier quotes.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Sparkles, CheckCircle2, AlertTriangle, Ban, Bot, User } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { IdLink } from '../components/common'

const fmt = (v: any, d = 1) => v === null || v === undefined || v === '' ? '—' : typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(d)) : String(v)

export function TradesList() {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate()
  const [d, setD] = useState<{ studies: any[]; checks: any[] } | null>(null)
  useEffect(() => { P(pid).get('/trades').then(setD).catch(() => setD({ studies: [], checks: [] })) }, [pid, patches.length, project?.meta?.rev])
  if (!d) return <div className="empty">Loading…</div>
  const issues: Record<string, string[]> = {}; for (const c of d.checks) (issues[c.id] ??= []).push(c.issue)
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Trade studies</h2><div className="muted small">Weighted decision matrices tied to MoEs and requirements, with knock-out limits and sensitivity. Open studies block the gate they belong to.</div></div>
      <button className="chip" onClick={() => send('List the open architecture choices in this model (heater, carafe, radio, pump, HMI, enclosure…), create a trade study for each with criteria tied to MoEs and requirement attributes, fill raw values from tests, simulations and supplier data with evidence ids, evaluate the sensitivity, and decide the robust ones with a rationale', 'analysis')}><Sparkles size={13} />run trade studies with the agent</button></div>
    <div className="tablewrap"><table className="dt"><thead><tr><th>Study</th><th>Status</th><th>Options</th><th>Criteria</th><th>Leader</th><th>Decision</th><th>Margin</th><th>Robust</th><th>Affects</th><th>Issues</th></tr></thead><tbody>
      {d.studies.map(s => <tr key={s.id} className="clickable" onClick={() => nav(`/p/${pid}/trades/${s.id}`)}><td><span className="id">{s.id}</span> {s.name}</td><td><span className={'pill ' + (s.status === 'decided' ? 'good' : 'warn')}>{s.status}</span></td><td className="num">{s.options}</td><td className="num">{s.criteria}</td><td className="small">{s.leader || '—'}</td>
        <td className="small">{s.decision ? <span className="row" style={{ gap: 4 }}>{s.agrees === false ? <AlertTriangle size={13} color="var(--warn)" /> : <CheckCircle2 size={13} color="var(--good)" />}{s.decision}</span> : '—'}</td><td className="num">{fmt(s.margin)}</td><td>{s.complete ? (s.robust ? <CheckCircle2 size={14} color="var(--good)" /> : <AlertTriangle size={14} color="var(--warn)" />) : <span className="muted small">incomplete</span>}</td>
        <td className="ids small">{s.affects.slice(0, 4).map((r: string) => <IdLink key={r} id={r} />)}</td><td className="small" style={{ color: 'var(--warn)' }}>{(issues[s.id] || []).join('; ')}</td></tr>)}
      {!d.studies.length && <tr><td colSpan={10} className="empty">No trade studies yet — ask the analysis agent, or add one under Decision management.</td></tr>}</tbody></table></div>
    <div className="muted small" style={{ marginTop: 8 }}>Scores are 1–5 (best = 5) or raw measured values normalized by direction; a criterion with a limit knocks out options that violate it. Robust = no single ±25 % weight change or −1 score on the leader changes the leader.</div>
  </div>
}

export function TradePage() {
  const { tid = '' } = useParams(); const { pid, project, patches, toast, send, openTab } = useProject(); const nav = useNavigate()
  const [e, setE] = useState<any>(null); const [cell, setCell] = useState<{ o: string; c: string; score: string; raw: string; evidence: string; note: string } | null>(null)
  const [w, setW] = useState<number[] | null>(null); const [dec, setDec] = useState<{ decision: string; rationale: string } | null>(null)
  useEffect(() => { P(pid).get('/trades/' + tid).then(d => { setE(d); setW(null); openTab({ key: 'trade:' + tid, title: tid, path: `/p/${pid}/trades/${tid}`, stage: 'System analysis' }) }).catch(() => setE(null)) }, [pid, tid, patches.length, project?.meta?.rev])
  if (!e) return <div className="empty">Loading…</div>
  const crit: any[] = e.criteria; const opts: any[] = e.options; const S = e.sensitivity
  const saveCell = async () => { if (!cell) return; try { await P(pid).post(`/trades/${tid}/score`, { option: cell.o, criterion: cell.c, score: cell.score, raw: cell.raw, evidence: cell.evidence.split(/[,\s]+/).filter(Boolean), note: cell.note }); toast('Recorded'); setCell(null) } catch (err: any) { toast(err.message) } }
  const saveW = async () => { if (!w) return; try { await P(pid).post(`/trades/${tid}/weights`, { weights: w }); toast('Weights recorded'); setW(null) } catch (err: any) { toast(err.message) } }
  const decide = async () => { if (!dec) return; try { await P(pid).post(`/trades/${tid}/decide`, dec); toast('Decision recorded'); setDec(null) } catch (err: any) { toast(err.message) } }
  const weights = w || crit.map(c => c.weight)
  return <div>
    <div className="elhead" style={{ marginBottom: 10 }}><div style={{ flex: 1 }}><div className="row" style={{ marginBottom: 4 }}><span className="pill accent">Trade study</span><span className={'pill ' + (e.status === 'decided' ? 'good' : 'warn')}>{e.status}</span><span className="id">{e.id}</span></div><div className="title">{e.name}</div>{e.question && <div className="muted" style={{ marginTop: 4 }}>{e.question}</div>}</div>
      <div className="row" style={{ flex: 'none' }}><button className="btn sm" onClick={() => nav(`/p/${pid}/trades`)}>All studies</button><button className="chip" onClick={() => send(`Complete trade study ${tid}: fill every missing raw value or score from tests, simulations, supplier data or budgets with evidence ids, check the limits, evaluate the sensitivity and, if robust, decide with a rationale and create the arch_decisions record`, 'analysis')}><Sparkles size={13} />complete with the agent</button></div></div>

    <div className="card" style={{ padding: 0, overflow: 'auto' }}><table className="dt"><thead><tr><th style={{ minWidth: 220 }}>Criterion</th><th>Basis</th><th>Weight</th>{opts.map(o => <th key={o.name} style={{ minWidth: 150 }}>{o.name}{o.datum && <span className="pill" style={{ marginLeft: 6 }}>datum</span>}{o.infeasible.length > 0 && <span className="pill bad" style={{ marginLeft: 6 }}><Ban size={11} /> infeasible</span>}</th>)}</tr></thead><tbody>
      {crit.map((c, i) => <tr key={c.name}><td><b>{c.name}</b><div className="muted small">{c.direction === 'min' ? '↓ lower is better' : '↑ higher is better'}{c.unit && ` · ${c.unit}`}{c.limit !== null && c.limit !== undefined && c.limit !== '' && <span style={{ color: 'var(--bad)' }}> · limit {c.direction === 'min' ? '≤' : '≥'} {c.limit}</span>}</div></td>
        <td className="small muted">{c.moe && <IdLink id={c.moe} />} {c.req && <IdLink id={c.req} />} {c.basis}</td>
        <td><input className="field" type="number" step="0.5" min={0} style={{ width: 64, padding: '4px 8px' }} value={weights[i]} onChange={ev => { const n = [...weights]; n[i] = Number(ev.target.value); setW(n) }} /></td>
        {opts.map(o => { const s = o.scores[c.name]; const r = o.raw[c.name]; const ev = o.evidence[c.name] || []; const viol = o.infeasible.find((x: string) => x.startsWith(c.name))
          return <td key={o.name} className="clickable" style={viol ? { background: 'var(--bad-soft)' } : {}} onClick={() => setCell({ o: o.name, c: c.name, score: r === null || r === undefined ? fmt(s) === '—' ? '' : String(s) : '', raw: r === null || r === undefined ? '' : String(r), evidence: ev.join(', '), note: '' })}>
            <div className="row" style={{ gap: 6, alignItems: 'baseline' }}><b style={{ fontSize: 15 }}>{fmt(s)}</b>{r !== null && r !== undefined && <span className="muted small">{fmt(r, 2)}{c.unit && ` ${c.unit}`}</span>}</div>
            {ev.length > 0 && <div className="ids small">{ev.slice(0, 3).map((x: string) => <IdLink key={x} id={x} />)}</div>}{viol && <div className="small" style={{ color: 'var(--bad)' }}>{viol.split(' limit')[0]}</div>}</td> })}</tr>)}
      <tr style={{ background: 'var(--surface-2)' }}><td><b>Weighted total</b><div className="muted small">of {fmt(opts[0]?.total.max)}</div></td><td /><td className="num">{weights.reduce((a, b) => a + b, 0)}</td>{opts.map(o => <td key={o.name}><b style={{ fontSize: 18, color: o.infeasible.length ? 'var(--bad)' : o.name === e.leader ? 'var(--good)' : 'var(--ink)' }}>{o.infeasible.length ? 'knocked out' : fmt(o.total.score)}</b><div className="muted small">rank {o.rank}{o.total.filled < o.total.of && ` · ${o.total.filled}/${o.total.of} scored`}</div></td>)}</tr>
      {e.pugh && <tr><td><b>Pugh vs datum</b><div className="muted small">+ better · − worse · S same</div></td><td /><td />{opts.map(o => { const p = e.pugh.options[o.name]; return <td key={o.name} className="small">{p ? <>{crit.map(c => <span key={c.name} style={{ marginRight: 4, fontFamily: 'var(--mono)' }}>{p.marks[c.name] || '·'}</span>)}<div className="muted">net {p.net > 0 ? '+' : ''}{p.net} ({p.plus}+ / {p.minus}−)</div></> : ''}</td> })}</tr>}
    </tbody></table></div>
    {w && <div className="row" style={{ marginTop: 8, gap: 8 }}><span className="small muted">Weights changed — totals above are live; record them to keep the change.</span><button className="btn sm" onClick={() => setW(null)}>Discard</button><button className="btn sm primary" onClick={saveW}>Record weights</button></div>}
    {cell && <div className="card row" style={{ gap: 8, marginTop: 10, flexWrap: 'wrap', alignItems: 'center', borderColor: 'var(--ink)' }}><b className="small">{cell.o} × {cell.c}</b>
      <input className="field" style={{ width: 130 }} placeholder="raw value" value={cell.raw} onChange={ev => setCell({ ...cell, raw: ev.target.value, score: '' })} /><span className="muted small">or</span><input className="field" style={{ width: 90 }} placeholder="score 1–5" value={cell.score} onChange={ev => setCell({ ...cell, score: ev.target.value, raw: '' })} />
      <input className="field" style={{ width: 220 }} placeholder="evidence ids (TST-01, SUP-02…)" value={cell.evidence} onChange={ev => setCell({ ...cell, evidence: ev.target.value })} /><input className="field" style={{ flex: 1, minWidth: 200 }} placeholder="note" value={cell.note} onChange={ev => setCell({ ...cell, note: ev.target.value })} />
      <button className="btn sm" onClick={() => setCell(null)}>Cancel</button><button className="btn sm primary" onClick={saveCell}>Record</button></div>}

    <div className="grid2" style={{ marginTop: 14, gap: 14 }}>
      <div className="card"><h4>Sensitivity</h4>
        <div className="row" style={{ margin: '6px 0 10px', gap: 8 }}>{e.complete ? (S.robust ? <span className="pill good"><CheckCircle2 size={12} /> robust</span> : <span className="pill warn"><AlertTriangle size={12} /> not robust</span>) : <span className="pill">incomplete</span>}<span className="small muted">leader <b>{S.leader}</b>{S.runner_up && <> over <b>{S.runner_up}</b> by {fmt(S.margin)}</>}</span></div>
        <table className="dt"><thead><tr><th>Criterion</th><th>Weight</th><th>Flips at weight</th><th>−25 %</th><th>+25 %</th><th>Leader −1</th></tr></thead><tbody>
          {S.rows.map((r: any) => <tr key={r.criterion}><td className="small">{r.criterion}</td><td className="num">{r.weight}</td><td className="num">{r.flip_weight === null || r.flip_weight === undefined ? '—' : r.flip_weight}</td>
            {['w_minus', 'w_plus', 'leader_minus1'].map(k => <td key={k} className="small" style={{ color: r[k] && r[k] !== S.leader ? 'var(--warn)' : 'var(--ink-3)' }}>{r[k] ? (r[k] === S.leader ? 'same' : r[k]) : '—'}</td>)}</tr>)}</tbody></table>
        <div className="muted small" style={{ marginTop: 6 }}>Flip weight: the weight on that criterion at which the runner-up would overtake the leader, other weights held.</div></div>
      <div className="card"><h4>Decision</h4>
        {e.decision ? <div style={{ marginTop: 6 }}><div className="row" style={{ gap: 6 }}><b style={{ fontSize: 16 }}>{e.decision}</b>{e.decision_agrees_with_scores === false && <span className="pill warn"><AlertTriangle size={12} /> differs from the scored leader</span>}</div><div className="small" style={{ marginTop: 6 }}>{e.rationale || <span style={{ color: 'var(--warn)' }}>No rationale recorded.</span>}</div><div className="muted small row" style={{ gap: 4, marginTop: 6 }}>{String(e.decided_by).startsWith('agent') ? <Bot size={12} /> : <User size={12} />}{e.decided_by} · {e.date}</div></div>
          : <div className="muted small" style={{ marginTop: 6 }}>Open. {e.recommendation && <>Recommendation: {e.recommendation}</>}</div>}
        {dec ? <div className="stack" style={{ gap: 6, marginTop: 10 }}><select className="field" value={dec.decision} onChange={ev => setDec({ ...dec, decision: ev.target.value })}>{opts.map(o => <option key={o.name} value={o.name} disabled={o.infeasible.length > 0}>{o.name}{o.infeasible.length ? ' (infeasible)' : ''}</option>)}</select><textarea className="field" rows={3} placeholder="rationale — mandatory, and must explain any departure from the scored leader" value={dec.rationale} onChange={ev => setDec({ ...dec, rationale: ev.target.value })} /><div className="row"><button className="btn sm" onClick={() => setDec(null)}>Cancel</button><button className="btn sm primary" disabled={!dec.rationale.trim()} onClick={decide}>Record decision</button></div></div>
          : <button className="btn sm" style={{ marginTop: 10 }} onClick={() => setDec({ decision: e.decision || e.leader || opts[0]?.name, rationale: e.rationale || '' })}>{e.decision ? 'Revise decision' : 'Decide'}</button>}
        <h4 style={{ marginTop: 14 }}>Linked</h4>
        <div className="small" style={{ marginTop: 4 }}><div><span className="muted">Requirements affected</span> <span className="ids">{e.links.requirements.map((r: string) => <IdLink key={r} id={r} />)}</span></div><div><span className="muted">Elements</span> <span className="ids">{e.links.elements.map((r: string) => <IdLink key={r} id={r} />)}</span></div><div><span className="muted">MoEs</span> <span className="ids">{e.links.moes.map((r: string) => <IdLink key={r} id={r} />)}</span></div><div><span className="muted">Architecture decisions</span> <span className="ids">{e.links.decisions.map((r: string) => <IdLink key={r} id={r} />)}</span>{!e.links.decisions.length && e.decision && <span className="muted"> none yet — the agent creates one on decide</span>}</div></div></div>
    </div>
  </div>
}
