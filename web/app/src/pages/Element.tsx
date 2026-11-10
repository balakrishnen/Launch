import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { GitBranch, MessageSquare, Search, Paperclip, Upload } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL, type ElementPage } from '../api'
import { Cell, IdLink, StagePill, Linkified } from '../components/common'
import { Comments } from './Lifecycle'

export function Element() {
  const { kind = '', id = '' } = useParams(); const { pid, send, openTab, project, patches } = useProject(); const nav = useNavigate()
  const [e, setE] = useState<ElementPage | null>(null); const [im, setIm] = useState<any>(null); const [tab, setTab] = useState('overview'); const [err, setErr] = useState(''); const [att, setAtt] = useState<any[]>([]); const [runs, setRuns] = useState<any[]>([]); const [mem, setMem] = useState<any>(null); const { toast } = useProject()
  const eid = decodeURIComponent(id)
  useEffect(() => { setE(null); setErr(''); const p = P(pid); p.get(`/element/${kind}/${encodeURIComponent(eid)}`).then(setE).catch(x => setErr(x.message)); p.get(`/impact/${encodeURIComponent(eid)}`).then(setIm).catch(() => setIm(null)); p.get(`/attachments/${encodeURIComponent(eid)}`).then(setAtt).catch(() => setAtt([])); if (kind === 'tests') p.get('/runs').then((rs: any[]) => setRuns(rs.filter(r => r.test === eid))).catch(() => setRuns([])) }, [pid, kind, eid, patches.length, project?.meta?.rev])
  useEffect(() => { if (e) openTab({ key: `el:${kind}:${eid}`, title: eid, path: `/p/${pid}/element/${kind}/${encodeURIComponent(eid)}`, stage: e.stage }) }, [e?.id])
  const title = useMemo(() => e ? (e.data.name || e.data.title || e.data.mode || String(e.data.text || '').slice(0, 120) || eid) : '', [e])
  if (err) return <div className="empty">{err}</div>
  if (!e) return <div className="empty">Loading…</div>
  const groups = (arr: any[]) => { const g: Record<string, any[]> = {}; for (const x of arr) (g[x.rel] ??= []).push(x); return Object.entries(g) }
  const lst = (xs: string[]) => xs.length ? <span className="row" style={{ gap: 6 }}>{xs.slice(0, 40).map(x => <IdLink key={x} id={x} />)}{xs.length > 40 && <span className="muted">+{xs.length - 40}</span>}</span> : <span className="muted">—</span>
  const highAp = im?.high_ap_fms?.length || 0
  return <div>
    <div className="elhead">
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="row" style={{ marginBottom: 6 }}><StagePill stage={e.stage} /><span className="pill">{KIND_LABEL[kind] || kind}</span><span className="id" style={{ fontSize: 13 }}>{eid}</span>{e.data.type && <span className="pill accent">{e.data.type}</span>}{e.data.discipline && <span className="pill">{e.data.discipline}</span>}{e.data.AP && <span className={'pill ' + (e.data.AP === 'H' ? 'bad' : e.data.AP === 'M' ? 'warn' : 'good')}>AP {e.data.AP}</span>}</div>
        <div className="title"><Linkified text={title} /></div>
      </div>
      <div className="row" style={{ flex: 'none' }}>
        <button className="btn sm" onClick={() => nav(`/p/${pid}/graph/${encodeURIComponent(eid)}`)}><GitBranch size={14} />Graph</button>
        <button className="btn sm" onClick={() => send(`Review ${eid} and everything linked to it; tell me what is inconsistent or missing`)}><Search size={14} />Review</button>
        <button className="btn sm" onClick={() => send(`I want to change ${eid}. Run an impact analysis, tell me which requirements, failure modes and tests are affected, and propose the patch set that keeps the thread consistent`)}><MessageSquare size={14} />Plan a change</button>
      </div>
    </div>
    <div className="sectabs">{[['overview', 'Overview'], ['trace', `Trace (${e.up.length + e.down.length})`], ['fmea', `Failure modes${e.fmea ? ` (${e.fmea.length})` : ''}`], ['impact', `Impact${im ? ` (${im.affected.length})` : ''}`], ['files', `Files (${att.length})`], ...(kind === 'tests' ? [['runs', `Results (${runs.length})`]] : []), ['memory', 'Memory'], ['history', `History (${e.provenance.length})`]].filter(([k]) => k !== 'fmea' || e.fmea || e.unassessed).map(([k, l]) => <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
    {tab === 'overview' && <div className="grid2">
      <div className="card"><h4>Fields</h4><dl className="kv">{Object.entries(e.data).map(([k, v]) => <><dt key={k + 'k'}>{k}</dt><dd key={k + 'v'}><Cell v={v} col={k} /></dd></>)}{e.disciplines && <><dt>disciplines</dt><dd>{e.disciplines.join(', ')}</dd></>}</dl></div>
      <div className="stack" style={{ gap: 14 }}>
        <div className="card"><h4>Upstream — where it comes from</h4>{groups(e.up).map(([rel, xs]) => <div key={rel} className="link"><span className="rel">{rel}</span><span className="stack" style={{ gap: 2 }}>{xs.map(x => <span key={x.id}><IdLink id={x.id} kind={x.kind || undefined} /> <span className="muted small">{x.name}</span></span>)}</span></div>)}{!e.up.length && <span className="muted">—</span>}</div>
        <div className="card"><h4>Downstream — what depends on it</h4>{groups(e.down).map(([rel, xs]) => <div key={rel} className="link"><span className="rel">{rel}</span><span className="stack" style={{ gap: 2 }}>{xs.map(x => <span key={x.id}><IdLink id={x.id} kind={x.kind || undefined} /> <span className="muted small">{x.name}</span></span>)}</span></div>)}{!e.down.length && <span className="muted">—</span>}</div>
      </div></div>}
    {tab === 'trace' && <div className="card"><div className="tablewrap" style={{ maxHeight: 'none', border: 0 }}><table className="dt"><thead><tr><th>Direction</th><th>Relation</th><th>Element</th><th>Name</th><th>Kind</th></tr></thead><tbody>
      {e.up.map((x, i) => <tr key={'u' + i}><td>upstream</td><td>{x.rel}</td><td><IdLink id={x.id} kind={x.kind || undefined} /></td><td>{x.name}</td><td className="muted">{x.kind}</td></tr>)}
      {e.down.map((x, i) => <tr key={'d' + i}><td>downstream</td><td>{x.rel}</td><td><IdLink id={x.id} kind={x.kind || undefined} /></td><td>{x.name}</td><td className="muted">{x.kind}</td></tr>)}</tbody></table></div></div>}
    {tab === 'fmea' && <div className="card"><h4>Failure modes of {eid}</h4>
      {(e.fmea || []).map(f => <div key={f.id} className="link"><IdLink id={f.id} kind="fmea" /><span className={'ap-' + f.AP}>{f.AP}</span><span>{f.guide} — {f.mode} → <span className="muted">{f.effect}</span></span></div>)}
      {(e.screened || []).length > 0 && <div className="small muted" style={{ marginTop: 6 }}>screened: {e.screened!.map(s => `${s.guide} (${s.reason})`).join('; ')}</div>}
      {(e.unassessed || []).length > 0 && <div style={{ marginTop: 8 }}><b style={{ color: 'var(--warn)' }}>{e.unassessed!.length} unassessed</b>: {e.unassessed!.map(u => u.guide).join(', ')} <button className="chip" onClick={() => send(`Assess or screen every remaining failure-mode candidate of ${eid} with causes derived from the architecture`)}>ask the agent</button></div>}</div>}
    {tab === 'impact' && (im ? <div className="card" style={{ borderColor: '#f5d78e' }}><div className="row between"><h4>If {eid} changes — {im.affected.length} elements within 3 hops</h4>{highAp > 0 && <span className="pill bad">{highAp} High-AP failure modes</span>}</div>
      <div className="link"><span className="rel">requirements</span>{lst(im.requirements)}</div><div className="link"><span className="rel">functions</span>{lst(im.functions)}</div><div className="link"><span className="rel">parts</span>{lst(im.parts)}</div><div className="link"><span className="rel">decisions</span>{lst(im.arch_decisions)}</div><div className="link"><span className="rel">failure modes</span>{lst(im.failure_modes)}</div><div className="link"><span className="rel"><b>tests to re-run</b></span>{lst(im.tests_to_rerun)}</div></div> : <div className="empty">no impact data</div>)}
    {tab === 'memory' && <MemoryPanel pid={pid} eid={eid} mem={mem} setMem={setMem} />}
    {tab === 'files' && <div className="card"><div className="row between"><h4>Files — CAD, drawings, schematics, reports</h4><label className="btn sm"><Upload size={14} />Attach<input type="file" style={{ display: 'none' }} onChange={async ev => { const f = ev.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append('element', eid); fd.append('role', /\.(step|stp|stl|sldprt|iges|igs|x_t)$/i.test(f.name) ? 'cad' : /\.(pdf)$/i.test(f.name) ? 'report' : /\.(sch|kicad_sch|brd|kicad_pcb)$/i.test(f.name) ? 'schematic' : 'document'); fd.append('file', f); try { await fetch(`/api/p/${pid}/attach`, { method: 'POST', body: fd }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail) }); toast('Attached'); P(pid).get(`/attachments/${encodeURIComponent(eid)}`).then(setAtt) } catch (x: any) { toast(x.message) } }} /></label></div>
      {att.length ? <table className="dt"><thead><tr><th>File</th><th>Role</th><th>Rev</th><th>Date</th><th>By</th><th>Size</th></tr></thead><tbody>{att.map(a => <tr key={a.id}><td><Paperclip size={12} style={{ verticalAlign: -2, marginRight: 4 }} /><a href={`/api/p/${pid}/file?path=${encodeURIComponent(a.file)}`} target="_blank" rel="noreferrer">{a.title}</a></td><td><span className="pill">{a.role}</span></td><td>{a.rev || '—'}</td><td>{a.date}</td><td className="muted small">{a.uploaded_by}</td><td className="muted small">{Math.round(a.size / 1024)} KB</td></tr>)}</tbody></table> : <span className="muted small">No files yet. STEP/STL/SLDPRT are tagged as CAD, PDFs as reports, KiCad as schematics.</span>}</div>}
    {tab === 'runs' && <div className="card"><h4>Test results</h4>{runs.length ? <table className="dt"><thead><tr><th>Run</th><th>Date</th><th>Unit</th><th>Result</th><th>Checks</th></tr></thead><tbody>{runs.map(r => <tr key={r.id} className="clickable" onClick={() => nav(`/p/${pid}/run/${r.id}`)}><td className="id">{r.id}</td><td>{r.date}</td><td>{r.unit || '—'}</td><td><span className={'pill ' + (r.result === 'pass' ? 'good' : r.result === 'fail' ? 'bad' : '')}>{r.result}</span></td><td>{(r.checks || []).filter((c: any) => c.ok).length}/{(r.checks || []).length}</td></tr>)}</tbody></table> : <span className="muted small">No results yet — <a href="#" onClick={ev => { ev.preventDefault(); nav(`/p/${pid}/runs`) }}>record one</a> or let TestRUNS post it.</span>}</div>}
    {tab !== 'history' && <Comments element={eid} />}
    {tab === 'history' && <div className="card">{e.provenance.length ? e.provenance.map((p: any, i: number) => <div key={i} className="link"><span className="rel">{new Date(p.ts * 1000).toLocaleString()}</span><span><b>{p.author}</b> → approved by {p.approver} · {p.rationale}{p.sources?.length ? <span className="muted"> · sources: {p.sources.join(', ')}</span> : null}{p.rev ? <span className="muted"> · rev {p.rev}</span> : null}</span></div>) : <span className="muted">No patch history (seeded element).</span>}</div>}
  </div>
}

// What the harness recalls about this element before any agent answers — the graph as memory, shown to the human too.
function MemoryPanel({ pid, eid, mem, setMem }: { pid: string; eid: string; mem: any; setMem: (m: any) => void }) {
  useEffect(() => { if (!mem || mem.id !== eid) P(pid).get(`/memory/${encodeURIComponent(eid)}`).then(setMem).catch(() => setMem(null)) }, [pid, eid])
  if (!mem || mem.id !== eid) return <div className="empty">Recalling…</div>
  return <div className="grid2" style={{ alignItems: 'start' }}>
    <div className="stack" style={{ gap: 12 }}>
      <div className="card"><h4>Decisions that shaped it</h4>{mem.decisions.length ? mem.decisions.map((d: any, i: number) => <div key={i} className="link"><span className="rel">{new Date(d.ts * 1000).toLocaleDateString()}</span><span><b>{d.author}</b> — <Linkified text={d.rationale} />{d.sources?.length ? <span className="muted small"> · {d.sources.join(', ')}</span> : null}</span></div>) : <span className="muted small">Seeded — no recorded decisions yet.</span>}</div>
      <div className="card"><h4>Said about it</h4>{mem.comments.length ? mem.comments.map((c: any, i: number) => <div key={i} className="small"><b>{c.user}</b>: <Linkified text={c.text} /></div>) : <span className="muted small">No comments.</span>}{mem.notes.length > 0 && <div className="small" style={{ marginTop: 6 }}>notes: {mem.notes.map((n: any) => <IdLink key={n.id} id={n.id} kind="notes" />)}</div>}{mem.threads.length > 0 && <div className="small" style={{ marginTop: 6 }}>conversations: {mem.threads.map((t: any) => <div key={t.id}>• {t.title}</div>)}</div>}</div>
    </div>
    <div className="card"><h4>What the agent is handed</h4><pre className="diff" style={{ maxHeight: 520, whiteSpace: 'pre-wrap' }}>{mem.text}</pre><div className="muted small">Recalled automatically for any message that mentions {eid} or is sent while viewing it.</div></div>
  </div>
}