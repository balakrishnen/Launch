import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { GitBranch, MessageSquare, Search } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL, type ElementPage } from '../api'
import { Cell, IdLink, StagePill, Linkified } from '../components/common'

export function Element() {
  const { kind = '', id = '' } = useParams(); const { pid, send, openTab, project, patches } = useProject(); const nav = useNavigate()
  const [e, setE] = useState<ElementPage | null>(null); const [im, setIm] = useState<any>(null); const [tab, setTab] = useState('overview'); const [err, setErr] = useState('')
  const eid = decodeURIComponent(id)
  useEffect(() => { setE(null); setErr(''); const p = P(pid); p.get(`/element/${kind}/${encodeURIComponent(eid)}`).then(setE).catch(x => setErr(x.message)); p.get(`/impact/${encodeURIComponent(eid)}`).then(setIm).catch(() => setIm(null)) }, [pid, kind, eid, patches.length, project?.meta?.rev])
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
    <div className="sectabs">{[['overview', 'Overview'], ['trace', `Trace (${e.up.length + e.down.length})`], ['fmea', `Failure modes${e.fmea ? ` (${e.fmea.length})` : ''}`], ['impact', `Impact${im ? ` (${im.affected.length})` : ''}`], ['history', `History (${e.provenance.length})`]].filter(([k]) => k !== 'fmea' || e.fmea || e.unassessed).map(([k, l]) => <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
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
    {tab === 'history' && <div className="card">{e.provenance.length ? e.provenance.map((p: any, i: number) => <div key={i} className="link"><span className="rel">{new Date(p.ts * 1000).toLocaleString()}</span><span><b>{p.author}</b> → approved by {p.approver} · {p.rationale}{p.sources?.length ? <span className="muted"> · sources: {p.sources.join(', ')}</span> : null}{p.rev ? <span className="muted"> · rev {p.rev}</span> : null}</span></div>) : <span className="muted">No patch history (seeded element).</span>}</div>}
  </div>
}
