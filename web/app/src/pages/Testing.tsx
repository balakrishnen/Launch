// Test results intake — NOT a test-execution system (TestRUNS executes, Kanalysis analyses; both integrate here later via POST /runs).
// Launch only needs the result of a run to land in the thread: verdict against the requirement limits, metrics, a quick look at the data.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Upload, CheckCircle2, XCircle, HelpCircle, Sparkles } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { IdLink } from '../components/common'

export function Runs() {
  const { pid, project, patches, toast, send } = useProject(); const nav = useNavigate()
  const [runs, setRuns] = useState<any[]>([]); const [tests, setTests] = useState<any[]>([]); const [f, setF] = useState({ test: '', unit: '', station: '', notes: '', limits: '' }); const [file, setFile] = useState<File | null>(null); const [busy, setBusy] = useState(false)
  useEffect(() => { P(pid).get('/runs').then(setRuns).catch(() => setRuns([])); P(pid).get('/collection/tests').then(setTests).catch(() => { }) }, [pid, patches.length, project?.meta?.rev])
  const submit = async () => { if (!f.test) return toast('pick a test'); setBusy(true); try { const fd = new FormData(); for (const [k, v] of Object.entries(f)) fd.append(k, v); if (file) fd.append('file', file); const r = await fetch(`/api/p/${pid}/runs`, { method: 'POST', body: fd }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json() }); toast(`${r.id}: ${r.result}`); setFile(null); setF({ ...f, notes: '' }); nav(`/p/${pid}/run/${r.id}`) } catch (e: any) { toast(e.message) } setBusy(false) }
  const byTest = useMemo(() => { const g: Record<string, any[]> = {}; for (const r of runs) (g[r.test] ??= []).push(r); return g }, [runs])
  const Icon = ({ r }: { r: string }) => r === 'pass' ? <CheckCircle2 size={15} color="var(--good)" /> : r === 'fail' ? <XCircle size={15} color="var(--bad)" /> : <HelpCircle size={15} color="var(--ink-3)" />
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Test results</h2><div className="muted small">Results of test runs landing in the thread — from TestRUNS and Kanalysis once integrated (same API as this form), or recorded here by hand. Limits come from the requirement attributes the test verifies; the test's status and freshness follow the latest run.</div></div></div>
    <div className="grid2" style={{ gridTemplateColumns: '360px 1fr', alignItems: 'start' }}>
      <div className="card stack" style={{ gap: 8 }}><h4>Record a result</h4>
        <select className="field" value={f.test} onChange={e => setF({ ...f, test: e.target.value })}><option value="">test…</option>{tests.map(t => <option key={t.id} value={t.id}>{t.id} — {t.name}</option>)}</select>
        <div className="row"><input className="field" placeholder="unit / serial" value={f.unit} onChange={e => setF({ ...f, unit: e.target.value })} /><input className="field" placeholder="station" value={f.station} onChange={e => setF({ ...f, station: e.target.value })} /></div>
        <textarea className="field" style={{ minHeight: 48 }} placeholder="extra limits, one per line: channel <= value unit   (e.g. temp_c <= 60 C)" value={f.limits} onChange={e => setF({ ...f, limits: e.target.value })} />
        <input className="field" placeholder="notes" value={f.notes} onChange={e => setF({ ...f, notes: e.target.value })} />
        <label className="btn" style={{ display: 'inline-flex', justifyContent: 'center' }}><Upload size={14} />{file ? file.name : 'Data file (.csv / .tsv time series)'}<input type="file" accept=".csv,.tsv,.txt" style={{ display: 'none' }} onChange={e => setFile(e.target.files?.[0] || null)} /></label>
        <button className="btn primary" disabled={busy} onClick={submit}>{busy ? 'Analysing…' : 'Record result'}</button>
        <div className="muted small">Time column: <code>time</code>/<code>t</code>/<code>timestamp</code>. Other numeric columns are channels. Limits match channel names (<code>pedal_latency &lt;= 50 ms</code>) or <code>channel.metric</code> (<code>torque.rise_10_90 &lt;= 0.05</code>).</div>
      </div>
      <div className="stack" style={{ gap: 14 }}>
        {Object.entries(byTest).map(([t, rs]) => <div key={t} className="card"><div className="row between"><h4><IdLink id={t} kind="tests" /> <span className="muted" style={{ fontWeight: 400 }}>{rs[0].test_name}</span></h4><span className="pill">{rs.length} run{rs.length > 1 ? 's' : ''}</span></div>
          <table className="dt" style={{ marginTop: 6 }}><thead><tr><th>Run</th><th>Date</th><th>Unit</th><th>Result</th><th>Channels</th><th>Checks</th><th>Rev</th></tr></thead><tbody>
            {rs.map(r => <tr key={r.id} className="clickable" onClick={() => nav(`/p/${pid}/run/${r.id}`)}><td className="id">{r.id}</td><td>{r.date}</td><td>{r.unit || '—'}</td><td><span className="row" style={{ gap: 4 }}><Icon r={r.result} />{r.result}</span></td><td className="muted small">{(r.channels || []).slice(0, 5).join(', ')}{(r.channels || []).length > 5 ? '…' : ''}</td><td>{(r.checks || []).filter((c: any) => c.ok).length}/{(r.checks || []).length}</td><td className="muted">{r.rev ?? ''}</td></tr>)}</tbody></table></div>)}
        {!runs.length && <div className="empty">No runs yet. Record one with a CSV, or <a href="#" onClick={e => { e.preventDefault(); send('Which tests are planned for the next gate and what data channels and limits should each run capture?') }}>ask the agent what each test should capture</a>.</div>}
      </div>
    </div>
  </div>
}

export function RunPage() {
  const { rid = '' } = useParams(); const { pid, openTab, send } = useProject()
  const [r, setR] = useState<any>(null); const [sel, setSel] = useState<string[]>([])
  useEffect(() => { P(pid).get('/run/' + rid).then(x => { setR(x); setSel(Object.keys(x.series?.channels || {}).slice(0, 3)); openTab({ key: 'run:' + rid, title: rid, path: `/p/${pid}/run/${rid}`, stage: 'Verification' }) }).catch(() => { }) }, [pid, rid])
  if (!r) return <div className="empty">Loading…</div>
  const chans = Object.keys(r.series?.channels || {})
  return <div>
    <div className="row between" style={{ marginBottom: 8 }}><div><h2>{rid} <span className={'pill ' + (r.result === 'pass' ? 'good' : r.result === 'fail' ? 'bad' : '')}>{r.result}</span></h2><div className="muted small"><IdLink id={r.test} kind="tests" /> {r.test_name} · {r.date} · unit {r.unit || '—'} · {r.operator} · rev {r.rev ?? '—'} · verifies {r.requirements.map((q: string) => <IdLink key={q} id={q} kind="requirements" />)}</div></div>
      <button className="chip" onClick={() => send(`Analyse test run ${rid} (${r.test}): explain the metrics against the limits, flag anomalies in the channels, and tell me whether the requirement is met with margin`)}><Sparkles size={13} />ask the agent to analyse</button></div>
    <div className="grid2" style={{ gridTemplateColumns: '1fr 380px', alignItems: 'start' }}>
      <div className="card">
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>{chans.map((c, i) => <button key={c} className="chip" style={sel.includes(c) ? { borderColor: COLORS[i % COLORS.length], color: COLORS[i % COLORS.length], background: 'var(--surface)' } : {}} onClick={() => setSel(s => s.includes(c) ? s.filter(x => x !== c) : [...s, c])}><span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: COLORS[i % COLORS.length] }} />{c}</button>)}</div>
        {r.series ? <Chart x={r.series.x} channels={r.series.channels} sel={sel} colors={Object.fromEntries(chans.map((c, i) => [c, COLORS[i % COLORS.length]]))} limits={(r.checks || []).filter((c: any) => sel.includes(c.channel))} /> : <div className="empty">No data file on this run.</div>}
      </div>
      <div className="stack" style={{ gap: 12 }}>
        <div className="card"><h4>Limit checks</h4>{(r.checks || []).length ? <table className="dt"><thead><tr><th>Channel</th><th>Limit</th><th>Measured</th><th></th></tr></thead><tbody>{r.checks.map((c: any, i: number) => <tr key={i}><td>{c.channel}{c.metric ? <span className="muted">.{c.metric}</span> : ''}{c.requirement ? <div className="small"><IdLink id={c.requirement} kind="requirements" /></div> : null}</td><td className="mono">{c.op} {c.value} {c.unit}</td><td className="mono">{c.measured ?? '—'}</td><td>{c.ok === null ? <span className="muted small">{c.note}</span> : c.ok ? <CheckCircle2 size={15} color="var(--good)" /> : <XCircle size={15} color="var(--bad)" />}</td></tr>)}</tbody></table> : <span className="muted small">No limits — the requirement attribute has no channel expression, and none were given on the run.</span>}</div>
        <div className="card"><h4>Metrics</h4><div className="tablewrap" style={{ maxHeight: 360, border: 0 }}><table className="dt"><thead><tr><th>Channel</th><th>min</th><th>mean</th><th>max</th><th>rms</th><th>p95</th><th>rise 10→90</th></tr></thead><tbody>{Object.entries(r.metrics || {}).map(([c, m]: any) => <tr key={c}><td>{c}</td><td className="mono">{m.min}</td><td className="mono">{m.mean}</td><td className="mono">{m.max}</td><td className="mono">{m.rms}</td><td className="mono">{m.p95}</td><td className="mono">{m.rise_10_90 ?? '—'}</td></tr>)}</tbody></table></div></div>
        {r.notes && <div className="card"><h4>Notes</h4><div className="small">{r.notes}</div></div>}
        {r.data && <div className="muted small">data: <a href={`/api/p/${pid}/file?path=runs/${rid}/${encodeURIComponent(r.data)}`} target="_blank" rel="noreferrer">{r.data}</a></div>}
      </div>
    </div>
  </div>
}

const COLORS = ['#ff4d8b', '#1a3a3a', '#b8a4ed', '#ffb084', '#e8b94a', '#a4d4c5', '#ff6b5a', '#6a6a6a']
function Chart({ x, channels, sel, colors, limits }: { x: number[]; channels: Record<string, (number | null)[]>; sel: string[]; colors: Record<string, string>; limits: any[] }) {
  const W = 860, H = 340, L = 56, R = 16, T = 12, B = 30
  const ys = sel.flatMap(c => (channels[c] || []).filter((v): v is number => v !== null)); const lv = limits.map(l => l.value)
  if (!ys.length) return <div className="empty">Pick a channel.</div>
  let y0 = Math.min(...ys, ...lv), y1 = Math.max(...ys, ...lv); if (y0 === y1) { y0 -= 1; y1 += 1 } const pad = (y1 - y0) * 0.06; y0 -= pad; y1 += pad
  const x0 = x[0], x1 = x[x.length - 1] === x0 ? x0 + 1 : x[x.length - 1]
  const sx = (v: number) => L + (v - x0) / (x1 - x0) * (W - L - R), sy = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B)
  const ticks = 5; const yt = [...Array(ticks + 1).keys()].map(i => y0 + (y1 - y0) * i / ticks); const xt = [...Array(ticks + 1).keys()].map(i => x0 + (x1 - x0) * i / ticks)
  const fmt = (v: number) => Math.abs(v) >= 1000 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(3).replace(/\.?0+$/, '')
  return <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block', fontFamily: 'inherit' }}>
    {yt.map((v, i) => <g key={i}><line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} stroke="var(--line)" /><text x={L - 6} y={sy(v) + 4} fontSize="11" textAnchor="end" fill="var(--ink-3)">{fmt(v)}</text></g>)}
    {xt.map((v, i) => <text key={i} x={sx(v)} y={H - 8} fontSize="11" textAnchor="middle" fill="var(--ink-3)">{fmt(v)}</text>)}
    {limits.map((l, i) => <g key={'l' + i}><line x1={L} x2={W - R} y1={sy(l.value)} y2={sy(l.value)} stroke={l.ok === false ? 'var(--bad)' : 'var(--good)'} strokeDasharray="6 4" strokeWidth={1.5} /><text x={W - R - 4} y={sy(l.value) - 4} fontSize="11" textAnchor="end" fill={l.ok === false ? 'var(--bad)' : 'var(--good)'}>{l.channel} {l.op} {l.value} {l.unit}</text></g>)}
    {sel.map(c => { const pts = (channels[c] || []).map((v, i) => v === null ? null : `${sx(x[i]).toFixed(1)},${sy(v).toFixed(1)}`).filter(Boolean).join(' '); return <polyline key={c} points={pts} fill="none" stroke={colors[c]} strokeWidth={1.6} strokeLinejoin="round" /> })}
    <line x1={L} x2={L} y1={T} y2={H - B} stroke="var(--line-2)" /><line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="var(--line-2)" />
  </svg>
}
