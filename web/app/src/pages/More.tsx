// Graph, Gaps, Scorecard, Inbox, Integrations, Documents, History, Budgets, Search, Landing, Login
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import cytoscape from 'cytoscape'
import { useProject } from '../state'
import { api, P, KIND_LABEL } from '../api'
import { Bar, IdLink, StagePill } from '../components/common'
import { PatchCard } from '../components/Agent'

const HEX: Record<string, string> = { 'Concept': '#c2410c', 'Stakeholder needs and requirements definition': '#c2410c', 'Business or mission analysis': '#9a3412', 'System requirements definition': '#b45309', 'System architecture definition': '#1d4ed8', 'Design definition': '#0f766e', 'System analysis': '#7e22ce', 'Verification': '#15803d', 'Implementation': '#6d28d9', 'Transition': '#7c5c2b', 'Operation': '#15803d', 'Project planning': '#0e7490', 'Risk management': '#0e7490', 'Quality assurance': '#9f1239', 'Project assessment and control': '#0e7490', 'Risk (derived)': '#b91c1c' }

export function Graph() {
  const { focus } = useParams(); const { pid, openTab, theme } = useProject(); const nav = useNavigate(); const el = useRef<HTMLDivElement>(null); const [q, setQ] = useState(focus || ''); const [n, setN] = useState(0)
  useEffect(() => { setQ(focus || '') }, [focus])
  useEffect(() => { let cy: cytoscape.Core | null = null
    P(pid).get('/graph').then((g: any) => { if (!el.current) return
      let nodes = g.nodes as any[], edges = g.edges as any[]
      if (focus) { const keep = new Set([focus]); for (const e of edges) { if (e.source === focus) keep.add(e.target); if (e.target === focus) keep.add(e.source) } const k2 = new Set(keep); for (const e of edges) { if (keep.has(e.source) && !keep.has(e.target)) k2.add(e.target); if (keep.has(e.target) && !keep.has(e.source)) k2.add(e.source) } nodes = nodes.filter(n => k2.has(n.id)); edges = edges.filter(e => k2.has(e.source) && k2.has(e.target)) }
      else if (nodes.length > 400) { nodes = nodes.filter(n => n.kind !== 'fmea' && n.kind !== 'fm_assessments'); const ids = new Set(nodes.map(n => n.id)); edges = edges.filter(e => ids.has(e.source) && ids.has(e.target)) }
      setN(nodes.length); const ink = theme === 'dark' ? '#e6e9ef' : '#141a22', line = theme === 'dark' ? '#333c4a' : '#cbd5e1'
      cy = cytoscape({ container: el.current, elements: [...nodes.map(n => ({ data: { ...n, label: n.id } })), ...edges.map((e, i) => ({ data: { id: 'e' + i, ...e } }))],
        style: [{ selector: 'node', style: { label: 'data(label)', 'font-size': 9, 'background-color': (e: any) => HEX[e.data('stage')] || '#888', color: ink, 'text-valign': 'bottom', 'text-margin-y': 3, width: (e: any) => e.data('id') === focus ? 34 : 16, height: (e: any) => e.data('id') === focus ? 34 : 16, 'border-width': (e: any) => e.data('id') === focus ? 3 : 0, 'border-color': ink } as any },
          { selector: 'edge', style: { width: 1, 'line-color': line, 'target-arrow-color': line, 'target-arrow-shape': 'triangle', 'arrow-scale': .7, 'curve-style': 'bezier', label: 'data(rel)', 'font-size': 7, color: '#94a3b8', 'text-rotation': 'autorotate' } as any }],
        layout: focus ? { name: 'concentric', concentric: (n: any) => n.data('id') === focus ? 10 : n.degree(), levelWidth: () => 2, animate: false, padding: 30 } as any : { name: 'cose', animate: false, nodeRepulsion: 8000, idealEdgeLength: 70, padding: 30 } as any })
      cy.on('tap', 'node', ev => { const d = ev.target.data(); openTab({ key: `el:${d.kind}:${d.id}`, title: d.id, path: `/p/${pid}/element/${d.kind}/${encodeURIComponent(d.id)}`, stage: d.stage }) })
      cy.on('dbltap', 'node', ev => nav(`/p/${pid}/graph/${encodeURIComponent(ev.target.data('id'))}`)) })
    return () => { cy?.destroy() } }, [pid, focus, theme])
  return <div>
    <div className="row between" style={{ marginBottom: 8 }}><div><h2>Trace graph</h2><div className="muted small">{n} nodes · click a node to open it, double-click to focus its neighbourhood{focus ? ` · focused on ${focus}` : ''}</div></div>
      <div className="row"><input className="field" style={{ width: 200 }} placeholder="focus on id…" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') nav(`/p/${pid}/graph/${encodeURIComponent(q.trim())}`) }} /><button className="btn sm" onClick={() => nav(`/p/${pid}/graph`)}>whole graph</button>
        <span className="row" style={{ gap: 6 }}>{Object.entries(HEX).map(([s, c]) => <span key={s} className="small muted row" style={{ gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 4, background: c }} />{s.replace(/^\d /, '')}</span>)}</span></div></div>
    <div id="cy" ref={el} />
  </div>
}

export function Gaps() {
  const { pid, send, project, patches } = useProject(); const [g, setG] = useState<any[]>([])
  useEffect(() => { P(pid).get('/collection/gaps').then(setG) }, [pid, patches.length, project?.meta?.rev])
  const by: Record<string, any[]> = {}; for (const x of g) (by[x.gap] ??= []).push(x.item)
  return <div><div className="row between" style={{ marginBottom: 10 }}><div><h2>Open gaps <span className={'pill ' + (g.length ? 'warn' : 'good')}>{g.length}</span></h2><div className="muted small">Every row is a hole in the trace. The agent closes them in order; you approve each patch.</div></div><button className="btn primary" onClick={() => send('Close the open trace gaps in order of leverage, in reviewable patches; stop when a human decision is needed')}>Ask the agent to close gaps</button></div>
    {Object.entries(by).map(([k, items]) => <div key={k} className="card" style={{ marginBottom: 10 }}><h4>{k.replace(/_/g, ' ')} ({items.length})</h4><div className="row" style={{ gap: 6 }}>{items.map((i, j) => typeof i === 'string' ? <IdLink key={j} id={i} /> : <span key={j} className="small">{JSON.stringify(i)}</span>)}</div></div>)}
    {!g.length && <div className="empty">No gaps. Trace is clean.</div>}</div>
}

export function Scorecard() {
  const { pid, send, project, patches } = useProject(); const [sc, setSc] = useState<any>(null); const [rq, setRq] = useState<any[]>([])
  useEffect(() => { P(pid).get('/scorecard').then(setSc); P(pid).get('/requirements_quality').then(setRq) }, [pid, patches.length, project?.meta?.rev])
  const names: Record<string, string> = { trace_coverage: 'Trace coverage', requirement_quality: 'Requirement quality (INCOSE GtWR)', fmea_completeness: 'FMEA completeness', high_ap_test_coverage: 'High-AP failure modes covered by tests', architecture_completeness: 'Architecture completeness', verification_completeness: 'Verification completeness', provenance: 'Provenance (share through reviewed patches)' }
  if (!sc) return <div className="empty">Loading…</div>
  const bad = rq.filter(r => r.score < 100).sort((a, b) => a.score - b.score)
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Scorecard <span className={'pill ' + (sc.grade <= 'B' ? 'good' : 'warn')} style={{ fontSize: 14 }}>{sc.grade} · {sc.overall}</span></h2><div className="muted small">Deterministic quality measures over the model. The agent sees the same numbers and works on the lowest first.</div></div><button className="btn primary" onClick={() => send('Look at the scorecard, pick the lowest dimension, and stage patches that raise it. Report the before/after.')}>Ask the agent to raise the score</button></div>
    <div className="grid2">
      <div className="card"><h4>Dimensions</h4>{Object.entries(sc.dimensions).map(([k, v]: any) => <div key={k} style={{ margin: '8px 0' }}><div className="row between"><span>{names[k] || k}</span><b>{v}</b></div><Bar v={v} /></div>)}</div>
      <div className="card"><div className="row between"><h4>Requirements needing rewrite</h4><span className="pill warn">{bad.length} of {rq.length}</span></div>
        {bad.slice(0, 30).map(r => <div key={r.id} className="link" style={{ borderBottom: '1px solid var(--line)', padding: '6px 0' }}><span className="rel" style={{ minWidth: 70 }}><IdLink id={r.id} kind="requirements" /><br /><b style={{ color: r.score >= 85 ? 'var(--warn)' : 'var(--bad)' }}>{r.score}</b></span><span>{r.text}<div className="row" style={{ gap: 4, marginTop: 3 }}>{r.findings.map((f: any) => <span key={f.rule} className="pill warn" style={{ fontWeight: 500 }}>{f.rule} {f.msg}</span>)}</div></span></div>)}
        {bad.length > 0 && <button className="chip" style={{ marginTop: 8 }} onClick={() => send('Rewrite the requirements with quality score below 85 so each is atomic, measurable with a unit, has no vague terms or escape clauses, and keeps its tests. Use check_requirement on each; one patch.')}>▶ ask the agent to rewrite them</button>}</div></div>
  </div>
}

export function Inbox() {
  const { patches, refreshPatches } = useProject(); const [f, setF] = useState('staged')
  useEffect(() => { refreshPatches() }, [])
  const list = patches.filter(p => !f || p.status === f).slice().reverse()
  return <div><div className="row between" style={{ marginBottom: 10 }}><div><h2>Review inbox <span className={'pill ' + (patches.filter(p => p.status === 'staged').length ? 'warn' : '')}>{patches.filter(p => p.status === 'staged').length} staged</span></h2><div className="muted small">Every change to the model arrives here as a patch with its diff, rationale and sources.</div></div>
    <div className="row">{['staged', 'applied', 'rejected', ''].map(s => <button key={s} className="chip" style={f === s ? { borderColor: 'var(--accent)', color: 'var(--accent-ink)', background: 'var(--accent-soft)' } : {}} onClick={() => setF(s)}>{s || 'all'}</button>)}</div></div>
    {list.map(p => <PatchCard key={p.id} p={p} />)}{!list.length && <div className="empty">Nothing here.</div>}</div>
}

export function Integrations() {
  const { pid, send } = useProject(); const [tok, setTok] = useState<any>(null); const [cons, setCons] = useState<any[]>([]); const [name, setName] = useState(''); const [created, setCreated] = useState<any>(null); const [url, setUrl] = useState(''); const [kind, setKind] = useState('requirements'); const [res, setRes] = useState('')
  const base = location.origin; const load = () => api.get('/oslc/consumers').then(setCons).catch(() => setCons([]))
  useEffect(() => { api.get('/token').then(setTok).catch(() => { }); load() }, [])
  const add = async () => { try { const c = await api.post('/oslc/consumers', { name: name || 'consumer' }); setCreated(c); load() } catch (e: any) { setRes(e.message) } }
  const pull = async () => { setRes('pulling…'); try { const r = await P(pid).post('/sync', { direction: 'pull', adapter: 'oslc', path: url, kind }); setRes(`staged patch ${r.patch_id} (${r.ops} ops) — review in the inbox`) } catch (e: any) { setRes(e.message) } }
  return <div className="stack" style={{ gap: 14 }}>
    <div><h2>Integrations</h2><div className="muted small">Launch is an OSLC 3.0 provider (RM, QM, AM, CM) and consumer; the model tools are also available over MCP.</div></div>
    <div className="card"><h4>OSLC provider — this project</h4><dl className="kv"><dt>Root services</dt><dd><code>{base}/oslc/rootservices</code></dd><dt>Catalog</dt><dd><code>{base}/oslc/catalog</code></dd><dt>Service provider</dt><dd><code>{base}/oslc/p/{pid}</code></dd><dt>Query example</dt><dd><code>{base}/oslc/p/{pid}/requirements?oslc.where=launch:type="SAFE"</code></dd><dt>Change requests</dt><dd><code>{base}/oslc/p/{pid}/patches</code></dd></dl>
      {tok && <div style={{ marginTop: 8 }} className="small"><b>Your API token</b> (HTTP Basic <code>{tok.user}:&lt;token&gt;</code>) <code style={{ userSelect: 'all' }}>{tok.token}</code> <button className="btn sm" onClick={() => navigator.clipboard?.writeText(tok.token).catch(() => { })}>copy</button></div>}</div>
    <div className="card"><h4>IBM DOORS Next / ELM — OAuth 1.0a friend</h4><ol className="small" style={{ margin: '0 0 8px 18px' }}><li>ELM: <i>Administration → Server → Friends → Add</i>; root services URI <code>{base}/oslc/rootservices</code>.</li><li>Create a consumer below; paste key and secret into ELM.</li><li>DOORS Next project: <i>Manage Project → Associations → Add</i>; click Allow once on Launch's authorize page.</li></ol>
      <div className="row"><input className="field" style={{ flex: 1 }} placeholder="consumer name, e.g. DOORS Next prod" value={name} onChange={e => setName(e.target.value)} /><button className="btn primary" onClick={add}>Create consumer</button></div>
      {created && <div className="small" style={{ marginTop: 6 }}><b>Key</b> <code style={{ userSelect: 'all' }}>{created.key}</code> &nbsp; <b>Secret</b> <code style={{ userSelect: 'all' }}>{created.secret}</code> <span className="muted">— shown once</span></div>}
      <div style={{ marginTop: 6 }}>{cons.map(c => <div key={c.key} className="link"><span className="rel">{c.name}</span><span><code>{c.key}</code> · by {c.created_by} <a href="#" className="id" onClick={e => { e.preventDefault(); api.del('/oslc/consumers/' + c.key).then(load) }}>revoke</a></span></div>)}{!cons.length && <span className="muted small">no consumers yet</span>}</div></div>
    <div className="card"><h4>Jama Connect / Codebeamer / Polarion</h4><div className="small">HTTP Basic with your API token, or OAuth2 bearer. In Jama: <i>Admin → Integrations → OSLC</i> with the catalog URL. To pull from Jama use the form below with <code>OSLC_AUTH=oauth2-client</code> on the server.</div></div>
    <div className="card"><h4>Pull from another OSLC tool</h4><div className="row"><input className="field" style={{ flex: 1 }} placeholder="query base URL from the other tool's ServiceProvider" value={url} onChange={e => setUrl(e.target.value)} /><select className="field" style={{ width: 'auto' }} value={kind} onChange={e => setKind(e.target.value)}><option value="requirements">requirements</option><option value="tests">test cases</option></select><button className="btn primary" onClick={pull}>Pull → staged patch</button></div><div className="small muted" style={{ marginTop: 4 }}>{res || 'Credentials via server env OSLC_USER / OSLC_TOKEN, OSLC_BEARER or OSLC_AUTH=jazz. Re-pulling updates in place.'}</div></div>
    <div className="card"><h4>Engineering tools</h4><dl className="kv"><dt>Pull</dt><dd>kicad netlist · cad-bom CSV · step · alm CSV/JSON · test-results · oslc</dd><dt>Push</dt><dd>kicad constraints · cad-bom requirement sheet · modelica parameter record · alm CSV · test plan CSV</dd><dt>Run</dt><dd>FMU simulation with constraint checks; CadQuery/FreeCAD, KiCad CLI, OpenModelica, ngspice, firmware builds through the agent</dd><dt>MCP</dt><dd><code>launch serve-mcp &lt;dir&gt;</code> exposes the model tools to Claude Code, Cursor or any MCP client</dd></dl>
      <div className="row" style={{ marginTop: 8 }}><button className="chip" onClick={() => send('Import the KiCad netlist in elec/ with tool_pull and map the components to parts under the right assembly')}>import a KiCad netlist</button><button className="chip" onClick={() => send('Import the CAD BOM CSV in mech/ with tool_pull')}>import a CAD BOM</button><button className="chip" onClick={() => send('Export the requirement limits to a Modelica parameter record in sim/')}>export limits to Modelica</button></div></div>
  </div>
}

export function Documents() {
  const { pid, send, toast } = useProject(); const [docs, setDocs] = useState<string[]>([])
  const load = () => P(pid).get('/artifacts').then((a: any) => setDocs(a.documents || []))
  useEffect(() => { load() }, [pid])
  const up = async (files: FileList | null) => { if (!files) return; for (const f of Array.from(files)) await P(pid).upload('/documents', f); toast(`${files.length} uploaded`); load() }
  return <div><h2>Source documents</h2><div className="muted small" style={{ marginBottom: 10 }}>PRDs, datasheets, standards, test reports. The agent reads these and cites them as patch sources.</div>
    <div className="card" style={{ marginBottom: 10 }} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); up(e.dataTransfer.files) }}><input type="file" multiple onChange={e => up(e.target.files)} /> <span className="muted small">or drop files here</span></div>
    <div className="card">{docs.map(d => <div key={d} className="link"><a className="id" href={`/api/p/${pid}/file?path=docs/${encodeURIComponent(d)}`} target="_blank">{d}</a><button className="chip" onClick={() => send(`Read ${d} and extract everything relevant to the model (needs, requirements, regulations, parts, limits); stage patches`)}>ingest</button></div>)}{!docs.length && <span className="muted">none yet</span>}</div></div>
}

export function History() {
  const { pid, toast, project } = useProject(); const [h, setH] = useState<any>(null); const [name, setName] = useState(''); const [diff, setDiff] = useState<any>(null); const [a, setA] = useState(''); const [b, setB] = useState('')
  const load = () => P(pid).get('/history').then(setH)
  useEffect(() => { load() }, [pid, project?.meta?.rev])
  if (!h) return null
  if (!h.supported) return <div className="empty">{h.note}</div>
  return <div><h2>History & baselines <span className="pill">rev {h.rev}</span></h2>
    <div className="grid2" style={{ marginTop: 10 }}>
      <div className="card"><h4>Baselines</h4>{h.baselines.map((x: any) => <div key={x.name} className="link"><span className="rel">rev {x.rev}</span><span><b>{x.name}</b> <span className="muted small">{x.created_by} · {new Date(x.created * 1000).toLocaleDateString()}</span></span></div>)}{!h.baselines.length && <span className="muted small">none yet</span>}
        <div className="row" style={{ marginTop: 8 }}><input className="field" style={{ width: 180 }} placeholder="e.g. PDR" value={name} onChange={e => setName(e.target.value)} /><button className="btn sm" onClick={async () => { await P(pid).post('/baselines', { name }); toast(`Baseline ${name} at rev ${h.rev}`); setName(''); load() }}>Create baseline at rev {h.rev}</button></div>
        <div className="row" style={{ marginTop: 10 }}><input className="field" style={{ width: 70 }} placeholder="rev A" value={a} onChange={e => setA(e.target.value)} /><input className="field" style={{ width: 70 }} placeholder="rev B" value={b} onChange={e => setB(e.target.value)} /><button className="btn sm" onClick={() => P(pid).get(`/diff/${a}/${b}`).then(setDiff)}>Diff</button></div>
        {diff && <div className="small" style={{ marginTop: 8 }}><div><b>added</b> {diff.added.map((x: string) => <IdLink key={x} id={x.split('/')[1]} kind={x.split('/')[0]} />)}</div><div><b>removed</b> {diff.removed.join(', ') || '—'}</div><div><b>changed</b> {diff.changed.map((c: any) => <span key={c.id}><IdLink id={c.id.split('/')[1]} kind={c.id.split('/')[0]} /> <span className="muted">({c.fields.join(', ')})</span> </span>)}</div></div>}</div>
      <div className="card"><h4>Applied patches</h4>{h.patches.slice().reverse().map((p: any) => <div key={p.id} className="link"><span className="rel">{new Date(p.created * 1000).toLocaleString()}</span><span><code>{p.id}</code> {p.author} — {p.rationale}</span></div>)}</div></div></div>
}

export function Budgets() {
  const { pid, send, project } = useProject(); const [b, setB] = useState<any>(null)
  useEffect(() => { P(pid).get('/budgets').then(setB) }, [pid, project?.meta?.rev])
  if (!b) return null; const keys = Object.keys(b)
  if (!keys.length) return <div><h2>Budgets</h2><div className="empty">No part carries mass_g / power_W / cost_usd attributes yet. <button className="chip" onClick={() => send('Add mass_g, power_W and cost_usd estimates to every leaf part from datasheets or stated assumptions (mark assumed), so the budgets roll up')}>ask the agent to fill them</button></div></div>
  return <div><h2>Budgets</h2>{keys.map(k => b[k].map((r: any) => <div key={k + r.root} className="card" style={{ margin: '10px 0' }}><div className="row between"><h4>{k} — {r.name}</h4><span className="pill">{r.total} {r.unit}</span></div>
    <table className="dt" style={{ minWidth: 0 }}><tbody>{r.children.map((c: any) => <tr key={c.id}><td><IdLink id={c.id} kind="parts" /></td><td>{c.name}</td><td style={{ textAlign: 'right' }}>{c.value} {r.unit}</td></tr>)}</tbody></table>
    {r.limits.map((l: any) => <div key={l.req} className="link"><IdLink id={l.req} kind="requirements" /><span>{l.text}</span><b style={{ color: l.margin >= 0 ? 'var(--good)' : 'var(--bad)' }}>margin {l.margin} {r.unit}</b></div>)}
    {r.parts_without_value.length > 0 && <div className="small muted">no value yet: {r.parts_without_value.map((p: string) => <IdLink key={p} id={p} kind="parts" />)}</div>}</div>))}</div>
}

export function SearchPage() {
  const { q = '' } = useParams(); const { pid, openTab, project } = useProject(); const [hits, setHits] = useState<any[]>([])
  useEffect(() => { P(pid).get('/search?q=' + encodeURIComponent(q)).then(setHits) }, [pid, q])
  return <div><h2>Search “{q}” <span className="pill">{hits.length}</span></h2><div className="tablewrap" style={{ marginTop: 10 }}><table className="dt"><tbody>{hits.map(h => <tr key={h.kind + h.id} className="clickable" onClick={() => openTab({ key: `el:${h.kind}:${h.id}`, title: h.id, path: `/p/${pid}/element/${h.kind}/${encodeURIComponent(h.id)}`, stage: project?.stage_of[h.kind] })}><td><StagePill stage={project?.stage_of[h.kind]} /></td><td><span className="id">{h.id}</span></td><td>{h.name}</td><td className="muted">{KIND_LABEL[h.kind]}</td></tr>)}</tbody></table></div></div>
}

export function Landing() {
  const nav = useNavigate(); const [me, setMe] = useState<any>(null); const [ps, setPs] = useState<any[]>([]); const [email, setEmail] = useState(''); const [invite, setInvite] = useState(''); const [err, setErr] = useState(''); const [np, setNp] = useState({ id: '', name: '', description: '' }); const [show, setShow] = useState(false)
  useEffect(() => { api.get('/me').then(m => { setMe(m); if (m.user) { if (m.single) nav('/p/default', { replace: true }); else api.get('/projects').then(setPs) } }) }, [])
  if (!me) return null
  if (!me.user) return <div style={{ maxWidth: 420, margin: '14vh auto', padding: 0 }}><div className="card" style={{ padding: 28 }}><div className="logo" style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--accent)', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 700, marginBottom: 12 }}>L</div><h1>Launch</h1><div className="muted" style={{ marginBottom: 16 }}>Agentic systems engineering for hardware teams</div>
    <label className="small muted">Work email</label><input className="field" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" style={{ margin: '4px 0 10px' }} />
    {me.invite_required && <><label className="small muted">Invite code</label><input className="field" value={invite} onChange={e => setInvite(e.target.value)} style={{ margin: '4px 0 10px' }} /></>}
    <button className="btn primary" onClick={() => api.post('/login', { email, invite }).then(() => location.reload()).catch(e => setErr(e.message))}>Continue</button>{err && <div style={{ color: 'var(--bad)', marginTop: 8 }}>{err}</div>}</div></div>
  return <div style={{ maxWidth: 1100, margin: '40px auto', padding: '0 20px' }}>
    <div className="row between"><div><h1>Projects</h1><div className="muted small">{me.user} · <a href="#" onClick={e => { e.preventDefault(); api.post('/logout').then(() => location.reload()) }}>sign out</a></div></div><button className="btn primary" onClick={() => setShow(true)}>New project</button></div>
    {show && <div className="card" style={{ margin: '14px 0' }}><h4>New project</h4><div className="row"><input className="field" style={{ width: 160 }} placeholder="short id, e.g. ebike-v2" value={np.id} onChange={e => setNp({ ...np, id: e.target.value })} /><input className="field" style={{ flex: 1 }} placeholder="Product name" value={np.name} onChange={e => setNp({ ...np, name: e.target.value })} /><input className="field" style={{ flex: 2 }} placeholder="one-line description" value={np.description} onChange={e => setNp({ ...np, description: e.target.value })} /><button className="btn primary" onClick={() => api.post('/projects', np).then(p => nav('/p/' + p.id)).catch(e => setErr(e.message))}>Create</button></div>{err && <div style={{ color: 'var(--bad)' }}>{err}</div>}</div>}
    <div className="gallery" style={{ marginTop: 16, gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))' }}>{ps.map(p => <div key={p.id} className="artcard" onClick={() => nav('/p/' + p.id)}><div className="t" style={{ fontSize: 16 }}>{p.name}</div><div className="d">{p.description}</div><div className="row" style={{ marginTop: 'auto' }}><span className={'pill ' + (p.clean ? 'good' : 'warn')}>{p.clean ? 'trace clean' : 'gaps open'}</span>{p.staged ? <span className="pill warn">{p.staged} to review</span> : null}{p.rev ? <span className="pill">rev {p.rev}</span> : null}</div><div className="d">{p.counts.requirements} requirements · {p.counts.parts} parts · {p.counts.tests} tests{p.updated ? ` · ${new Date(p.updated * 1000).toLocaleDateString()}` : ''}</div></div>)}{!ps.length && <div className="empty">No projects yet — create one.</div>}</div></div>
}
