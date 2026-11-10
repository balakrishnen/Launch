// Office replacement: Tables (spreadsheets with formulas, inside the model), Notes (specs, minutes, decision logs) and
// Import (bring an existing .xlsx/.csv in as elements or as a table — the migration path off Excel).
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { marked } from 'marked'
import { Plus, Table2, FileText, Upload, Sparkles } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL } from '../api'
import { Sheet, type Col } from '../components/Sheet'
import { IdLink } from '../components/common'

// ---------------------------------------------------------------- Tables
export function Tables() {
  const { pid, project, patches, toast, send } = useProject(); const nav = useNavigate()
  const [rows, setRows] = useState<any[]>([]); const [name, setName] = useState('')
  useEffect(() => { P(pid).get('/collection/tables').then(setRows).catch(() => setRows([])) }, [pid, patches.length, project?.meta?.rev])
  const create = async () => { const n = name.trim(); if (!n) return; const id = 'TBL-' + n.toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 24)
    await P(pid).post('/patch', { ops: [{ op: 'add', kind: 'tables', id, value: { name: n, columns: [{ key: 'item', name: 'Item', type: 'text' }, { key: 'owner', name: 'Owner', type: 'text' }, { key: 'status', name: 'Status', type: 'text' }, { key: 'due', name: 'Due', type: 'date' }], rows: [] } }], rationale: `New table ${n}`, apply: true }); toast(`Created ${id}`); nav(`/p/${pid}/table/${id}`) }
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Tables</h2><div className="muted small">Trackers, rollups and lists that used to live in spreadsheets — now rows in the model with formulas that can reach any element.</div></div>
      <div className="row"><input className="field" style={{ width: 220 }} placeholder="new table name" value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && create()} /><button className="btn primary sm" onClick={create}><Plus size={14} />Table</button><button className="btn sm" onClick={() => nav(`/p/${pid}/import`)}><Upload size={14} />Import spreadsheet</button></div></div>
    <div className="gallery" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))' }}>{rows.map(t => <div key={t.id} className="artcard" onClick={() => nav(`/p/${pid}/table/${t.id}`)}><div className="row between"><div className="t"><Table2 size={15} style={{ verticalAlign: -2, marginRight: 6 }} />{t.name}</div><span className="pill">{(t.rows || []).length} rows</span></div><div className="d">{t.description || (t.columns || []).map((c: any) => c.name).join(' · ')}</div><div className="d">{(t.columns || []).filter((c: any) => c.type === 'formula').length ? `${(t.columns || []).filter((c: any) => c.type === 'formula').length} formula column(s)` : ''}{t.owner_team ? ` · ${t.owner_team}` : ''}</div></div>)}
      {!rows.length && <div className="empty">No tables yet. Create one, import a spreadsheet, or <a href="#" onClick={e => { e.preventDefault(); send('Create a cost rollup table over all parts with qty, unit cost and a formula column for extended cost, and a totals row') }}>ask the agent to build one</a>.</div>}</div>
  </div>
}

export function TablePage() {
  const { tid = '' } = useParams(); const { pid, project, patches, toast, openTab, send } = useProject()
  void toast
  const [t, setT] = useState<any>(null); const [err, setErr] = useState('')
  const load = () => P(pid).get('/table/' + tid).then(x => { setT(x); setErr('') }).catch(e => setErr(e.message))
  useEffect(() => { load() }, [pid, tid, patches.length, project?.meta?.rev])
  useEffect(() => { if (t) openTab({ key: 'table:' + tid, title: t.name, path: `/p/${pid}/table/${tid}`, stage: 'Information management' }) }, [t?.id])
  if (err) return <div className="empty">{err}</div>
  if (!t) return <div className="empty">Loading…</div>
  const cols: Col[] = [{ key: '__i', name: '#', readonly: true, width: 36 }, ...t.columns.map((c: any) => ({ key: c.key, name: c.name, type: c.type, formula: c.formula }))]
  const rows = t.rows.map((r: any, i: number) => ({ ...r, __i: i + 1, id: String(i) }))
  const save = async (newRows: any[], newCols?: any[], rationale = `${t.name}: rows edited`) => {
    const clean = newRows.map(r => { const o: any = {}; for (const c of (newCols || t.columns)) if (c.type !== 'formula') o[c.key] = r[c.key] ?? ''; return o })
    const value: any = { rows: clean }; if (newCols) value.columns = newCols
    const r = await P(pid).post('/patch', { ops: [{ op: 'update', kind: 'tables', id: tid, value }], rationale, apply: true }); toast(`Applied ${r.patch_id}`); load()
  }
  const onCommit = async ({ updates, adds, deletes }: any, stageIt: boolean) => {
    let next = t.rows.map((r: any, i: number) => ({ ...r, ...(updates[String(i)] || {}) })).filter((_: any, i: number) => !deletes.includes(String(i)))
    next = [...next, ...adds.map((a: any) => { const o = { ...a }; delete o.__new; delete o.__i; delete o.id; return o })]
    if (stageIt) { const r = await P(pid).post('/patch', { ops: [{ op: 'update', kind: 'tables', id: tid, value: { rows: next.map((r: any) => { const o: any = {}; for (const c of t.columns) if (c.type !== 'formula') o[c.key] = r[c.key] ?? ''; return o }) } }], rationale: `${t.name}: rows edited`, apply: false }); toast(`Staged ${r.patch_id}`); return }
    await save(next)
  }
  const addColumn = (name: string, type: Col['type'], formula?: string) => { const key = name.toLowerCase().replace(/\W+/g, '_').replace(/^_|_$/g, '') || 'c' + t.columns.length; save(t.rows, [...t.columns, { key, name, type, ...(formula ? { formula } : {}) }], `${t.name}: column ${name} added`) }
  const dropColumn = (key: string) => save(t.rows, t.columns.filter((c: any) => c.key !== key), `${t.name}: column ${key} removed`)
  return <div>
    <div className="row between" style={{ marginBottom: 8 }}><div><h2>{t.name}</h2><div className="muted small">{t.description}{t.elements?.length ? <> · {t.elements.map((e: string) => <IdLink key={e} id={e} />)}</> : null}</div></div>
      <div className="row"><button className="chip" onClick={() => send(`Fill the empty cells of table ${tid} (${t.name}) from the model and the source documents`)}><Sparkles size={13} />ask the agent to fill</button></div></div>
    <Sheet cols={cols} rows={rows} onCommit={onCommit} newRowTemplate={() => Object.fromEntries(t.columns.map((c: any) => [c.key, c.type === 'number' ? '' : '']))} onAddColumn={addColumn} totals={t.totals}
      extraActions={t.columns.length > 1 && <select className="field" style={{ width: 'auto', padding: '4px 8px' }} value="" onChange={e => e.target.value && confirmDrop(e.target.value, t.columns, dropColumn)}><option value="">Remove column…</option>{t.columns.map((c: any) => <option key={c.key} value={c.key}>{c.name}</option>)}</select>} />
    <div className="muted small" style={{ marginTop: 8 }}>Formulas: <code>qty * unit_cost</code> · <code>part(part_id).attrs.mass</code> · <code>el('tests', test_id, 'status')</code> · <code>sum(cols.cost)</code>, <code>avg</code>, <code>count</code> · <code>if_(status == 'open', 1, 0)</code> · <code>days(start, due)</code></div>
  </div>
}
function confirmDrop(key: string, cols: any[], fn: (k: string) => void) { const c = cols.find((x: any) => x.key === key); fn(c.key) }

// ---------------------------------------------------------------- Notes
export function Notes() {
  const { pid, project, patches } = useProject(); const nav = useNavigate()
  const [rows, setRows] = useState<any[]>([]); const [title, setTitle] = useState(''); const [kind, setKind] = useState('note')
  useEffect(() => { P(pid).get('/collection/notes').then(setRows).catch(() => setRows([])) }, [pid, patches.length, project?.meta?.rev])
  const create = async () => { const n = title.trim(); if (!n) return; const id = 'NOTE-' + String(rows.length + 1).padStart(3, '0')
    await P(pid).post('/patch', { ops: [{ op: 'add', kind: 'notes', id, value: { title: n, kind, body: `# ${n}\n\n`, date: new Date().toISOString().slice(0, 10), author: project?.user || '', status: 'draft' } }], rationale: `New ${kind}: ${n}`, apply: true }); nav(`/p/${pid}/note/${id}`) }
  const groups = useMemo(() => { const g: Record<string, any[]> = {}; for (const r of rows) (g[r.kind || 'note'] ??= []).push(r); return Object.entries(g) }, [rows])
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Notes</h2><div className="muted small">Specs, meeting minutes, decision logs and reports written here, linked to the elements they talk about. No Word, no Google Docs.</div></div>
      <div className="row"><select className="field" style={{ width: 'auto' }} value={kind} onChange={e => setKind(e.target.value)}>{['note', 'spec', 'minutes', 'decision', 'report', 'test report', 'memo'].map(k => <option key={k}>{k}</option>)}</select><input className="field" style={{ width: 240 }} placeholder="title" value={title} onChange={e => setTitle(e.target.value)} onKeyDown={e => e.key === 'Enter' && create()} /><button className="btn primary sm" onClick={create}><Plus size={14} />Note</button></div></div>
    {groups.map(([k, rs]) => <div key={k} style={{ marginBottom: 18 }}><h4 style={{ textTransform: 'capitalize' }}>{k}s</h4><div className="list">{rs.map(r => <div key={r.id} className="li" onClick={() => nav(`/p/${pid}/note/${r.id}`)}><span className="t"><FileText size={14} style={{ verticalAlign: -2, marginRight: 6 }} />{r.title}</span><span className="muted small">{r.date}{r.author ? ` · ${r.author}` : ''}</span><span className={'pill ' + (r.status === 'final' ? 'good' : '')}>{r.status}</span><span className="muted small">{(r.elements || []).length ? `${r.elements.length} linked` : ''}</span></div>)}</div></div>)}
    {!rows.length && <div className="empty">No notes yet.</div>}
  </div>
}

export function NotePage() {
  const { nid = '' } = useParams(); const { pid, project, patches, toast, openTab, send } = useProject()
  const [n, setN] = useState<any>(null); const [body, setBody] = useState(''); const [title, setTitle] = useState(''); const [edit, setEdit] = useState(false); const ta = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { P(pid).get(`/element/notes/${nid}`).then(e => { setN(e.data); setBody(e.data.body); setTitle(e.data.title); openTab({ key: 'note:' + nid, title: e.data.title, path: `/p/${pid}/note/${nid}`, stage: 'Information management' }) }).catch(() => { }) }, [pid, nid, patches.length, project?.meta?.rev])
  if (!n) return <div className="empty">Loading…</div>
  const links = [...new Set((body.match(/\b[A-Z]{1,6}-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b/g) || []))]
  const save = async (status?: string) => { const r = await P(pid).post('/patch', { ops: [{ op: 'update', kind: 'notes', id: nid, value: { title, body, elements: links, ...(status ? { status } : {}) } }], rationale: `${title}: edited`, apply: true }); toast(`Saved ${r.patch_id}`); setEdit(false) }
  const html = marked.parse(body) as string
  return <div>
    <div className="row between" style={{ marginBottom: 8 }}><div>{edit ? <input className="field" style={{ fontSize: 18, fontWeight: 600, width: 480 }} value={title} onChange={e => setTitle(e.target.value)} /> : <h2>{n.title}</h2>}<div className="muted small"><span className="pill">{n.kind}</span> {n.date}{n.author ? ` · ${n.author}` : ''} · <span className={'pill ' + (n.status === 'final' ? 'good' : '')}>{n.status}</span>{links.length ? <> · links: {links.slice(0, 12).map(l => <IdLink key={l} id={l} />)}</> : null}</div></div>
      <div className="row">{edit ? <><button className="btn sm" onClick={() => { setEdit(false); setBody(n.body); setTitle(n.title) }}>Cancel</button><button className="btn sm primary" onClick={() => save()}>Save</button></> : <><button className="btn sm" onClick={() => setEdit(true)}>Edit</button>{n.status !== 'final' && <button className="btn sm" onClick={() => save('final')}>Mark final</button>}<button className="chip" onClick={() => send(`Draft or extend the ${n.kind} "${n.title}" (${nid}) from the model; keep every claim traceable to an element id`)}><Sparkles size={13} />ask the agent to draft</button></>}</div></div>
    {edit ? <div className="grid2" style={{ gridTemplateColumns: '1fr 1fr' }}><textarea ref={ta} className="field mono" style={{ minHeight: 520, fontSize: 13 }} value={body} onChange={e => setBody(e.target.value)} /><div className="card doc" dangerouslySetInnerHTML={{ __html: html }} /></div>
      : <div className="card doc" style={{ maxWidth: 900 }} dangerouslySetInnerHTML={{ __html: html }} />}
    <div className="muted small" style={{ marginTop: 6 }}>Markdown. Any element id in the text (R-012, P-PACK, TST-04…) becomes a link and is recorded on the note.</div>
  </div>
}

// ---------------------------------------------------------------- Import a spreadsheet
export function ImportSheet() {
  const { pid, toast } = useProject(); const nav = useNavigate()
  const [prev, setPrev] = useState<any>(null); const [si, setSi] = useState(0); const [kind, setKind] = useState('tables'); const [map, setMap] = useState<Record<string, string>>({}); const [idCol, setIdCol] = useState(''); const [prefix, setPrefix] = useState(''); const [tname, setTname] = useState(''); const [busy, setBusy] = useState(false)
  const sheet = prev?.sheets?.[si]
  const up = async (f: File | undefined) => { if (!f) return; setBusy(true); try { const p = await P(pid).upload('/sheet/preview', f); setPrev(p); setSi(0); const g = p.sheets[0]?.guess || 'tables'; setKind(g); setTname(p.sheets[0]?.name || ''); auto(g, p.sheets[0]?.headers || [], p.kinds) } catch (e: any) { toast(e.message) } setBusy(false) }
  const auto = (k: string, headers: string[], kinds: any) => { if (k === 'tables' || !kinds?.[k]) { setMap({}); return } const fields = [...kinds[k].req, ...Object.keys(kinds[k].opt)]; const m: Record<string, string> = {}; for (const f of fields) { const h = headers.find(h => h.toLowerCase().replace(/[^a-z0-9]/g, '') === f.toLowerCase().replace(/[^a-z0-9]/g, '') || h.toLowerCase().includes(f.toLowerCase())); if (h) m[f] = h } setMap(m); setIdCol(headers.find(h => /^id$|identifier|^key$/i.test(h)) || '') }
  const commit = async (apply: boolean) => { setBusy(true); try { const r = await P(pid).post('/sheet/commit', { file: prev.file, sheet: sheet.name, headers: sheet.headers, rows: sheet.rows, kind, mapping: map, id_column: idCol, id_prefix: prefix, table_name: tname, apply }); toast(apply ? `Imported — ${r.patch_id}` : `Staged ${r.patch_id} for review`); nav(kind === 'tables' ? `/p/${pid}/tables` : `/p/${pid}/collection/${kind}`) } catch (e: any) { toast(e.message) } setBusy(false) }
  const fields = kind !== 'tables' && prev?.kinds?.[kind] ? [...prev.kinds[kind].req, ...Object.keys(prev.kinds[kind].opt)] : []
  return <div>
    <h2>Import a spreadsheet</h2><div className="muted small" style={{ marginBottom: 12 }}>Bring the last Excel or Google Sheet in once — as elements of a collection (requirements, parts, tests, work items…) or as a table. After that it lives here.</div>
    <div className="card" style={{ marginBottom: 14 }}><label className="btn primary" style={{ display: 'inline-flex' }}><Upload size={14} />{busy ? 'Working…' : 'Choose .xlsx / .csv / .tsv'}<input type="file" accept=".xlsx,.xlsm,.csv,.tsv,.txt" style={{ display: 'none' }} onChange={e => up(e.target.files?.[0])} /></label>{prev && <span className="muted small" style={{ marginLeft: 10 }}>{prev.file} · {prev.sheets.length} sheet(s)</span>}</div>
    {sheet && <>
      <div className="row" style={{ gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        {prev.sheets.length > 1 && <select className="field" style={{ width: 'auto' }} value={si} onChange={e => { const i = Number(e.target.value); setSi(i); const g = prev.sheets[i].guess; setKind(g); setTname(prev.sheets[i].name); auto(g, prev.sheets[i].headers, prev.kinds) }}>{prev.sheets.map((s: any, i: number) => <option key={i} value={i}>{s.name} ({s.rows.length} rows)</option>)}</select>}
        <span className="small">Import as</span><select className="field" style={{ width: 'auto' }} value={kind} onChange={e => { setKind(e.target.value); auto(e.target.value, sheet.headers, prev.kinds) }}><option value="tables">a new table (keep all columns)</option>{Object.keys(prev.kinds).filter(k => k !== 'tables').map(k => <option key={k} value={k}>{KIND_LABEL[k] || k}</option>)}</select>
        {kind === 'tables' ? <input className="field" style={{ width: 220 }} value={tname} onChange={e => setTname(e.target.value)} placeholder="table name" /> : <><span className="small">id column</span><select className="field" style={{ width: 'auto' }} value={idCol} onChange={e => setIdCol(e.target.value)}><option value="">generate ids</option>{sheet.headers.map((h: string) => <option key={h}>{h}</option>)}</select><input className="field" style={{ width: 110 }} placeholder="id prefix" value={prefix} onChange={e => setPrefix(e.target.value)} /></>}
      </div>
      {kind !== 'tables' && <div className="card" style={{ marginBottom: 10 }}><h4>Map columns → {KIND_LABEL[kind] || kind} fields</h4><div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>{fields.map(f => <label key={f} className="row small" style={{ gap: 4, border: '1px solid var(--line)', borderRadius: 8, padding: '4px 8px' }}><b style={{ color: prev.kinds[kind].req.includes(f) ? 'var(--ink)' : 'var(--ink-3)' }}>{f}</b><select className="field" style={{ width: 'auto', padding: '2px 6px' }} value={map[f] || ''} onChange={e => setMap(m => ({ ...m, [f]: e.target.value }))}><option value="">—</option>{sheet.headers.map((h: string) => <option key={h}>{h}</option>)}</select></label>)}</div><div className="muted small" style={{ marginTop: 6 }}>Bold fields are required; list fields (tests, reqs, from_…) accept comma-separated ids. Dangling references are rejected by validation, so import in dependency order (stakeholders → needs → requirements → tests).</div></div>}
      <div className="tablewrap" style={{ maxHeight: 360 }}><table className="dt"><thead><tr>{sheet.headers.map((h: string) => <th key={h}>{h}</th>)}</tr></thead><tbody>{sheet.rows.slice(0, 50).map((r: any[], i: number) => <tr key={i}>{sheet.headers.map((_: string, j: number) => <td key={j}>{String(r[j] ?? '')}</td>)}</tr>)}</tbody></table></div>
      <div className="row" style={{ marginTop: 10 }}><button className="btn sm" disabled={busy} onClick={() => commit(false)}>Stage for review</button><button className="btn sm primary" disabled={busy} onClick={() => commit(true)}>Import {sheet.rows.length} rows</button></div>
    </>}
  </div>
}
