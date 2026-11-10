// A collection is a spreadsheet: schema-driven columns, inline editing, add/paste rows, custom columns — all as patches.
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useProject } from '../state'
import { P, KIND_LABEL } from '../api'
import { Cell, StagePill } from '../components/common'
import { Sheet, type Col } from '../components/Sheet'

const DERIVED_LINK: Record<string, (r: any) => { kind: string; id: string }> = { fmea: r => ({ kind: 'fmea', id: r.id }), unassessed: r => ({ kind: r.kind, id: r.element }), screened: r => ({ kind: r.kind, id: r.element }), gaps: r => ({ kind: r.kind || '', id: r.item }), verification_matrix: r => ({ kind: 'requirements', id: r.requirement || r.id }), certification_plan: r => ({ kind: 'regulations', id: r.regulation || r.id }) }
const HIDE = ['disciplines', 'higher', 'focus', 'lower', '__new']
const LABEL: Record<string, string> = { from_: 'from needs', regs: 'regulations', uc: 'use cases', stk: 'stakeholder', moe: 'MoE', alloc: 'allocated to', reqs: 'requirements', funcs: 'functions', frm: 'from', lcs: 'logical components', passfail: 'pass / fail', attr: 'attribute' }

export function Collection() {
  const { kind = '' } = useParams(); const { pid, project, openTab, send, patches, toast } = useProject()
  const [rows, setRows] = useState<any[]>([]); const [extra, setExtra] = useState<Col[]>([])
  useEffect(() => { P(pid).get('/collection/' + kind).then(setRows).catch(() => setRows([])) }, [pid, kind, patches.length, project?.meta?.rev])
  const spec = project?.schema?.[kind]; const derived = !spec
  const cols = useMemo<Col[]>(() => {
    const seen = new Set<string>(); const out: Col[] = []
    const push = (key: string, dflt?: any) => { if (seen.has(key) || HIDE.includes(key)) return; seen.add(key); const sample = rows.find(r => r[key] !== undefined && r[key] !== null && r[key] !== '')?.[key] ?? dflt
      const type: Col['type'] = Array.isArray(sample) ? 'list' : typeof sample === 'number' ? 'number' : typeof sample === 'boolean' ? 'bool' : spec?.refs?.[key] ? 'ref' : 'text'
      out.push({ key, name: LABEL[key] || key.replace(/_/g, ' '), type, readonly: derived }) }
    push('id'); if (spec) { for (const k of spec.req) push(k); for (const [k, d] of Object.entries(spec.opt)) push(k, d) }
    for (const r of rows) for (const k of Object.keys(r)) if (k !== 'attrs') push(k)
    if (rows.some(r => r.attrs && Object.keys(r.attrs).length)) for (const r of rows) for (const k of Object.keys(r.attrs || {})) if (!seen.has('attrs.' + k)) { seen.add('attrs.' + k); out.push({ key: 'attrs.' + k, name: k, type: 'text' }) }
    return [...out, ...extra]
  }, [rows, spec, extra, derived])
  const flat = useMemo(() => rows.map(r => { const o: any = { ...r }; for (const [k, v] of Object.entries(r.attrs || {})) o['attrs.' + k] = v; delete o.attrs; return o }), [rows])
  const stage = project?.stage_of[kind] || 'System analysis'
  const open = (r: any) => { const t = DERIVED_LINK[kind] ? DERIVED_LINK[kind](r) : { kind, id: r.id }; if (!t.kind) return; openTab({ key: `el:${t.kind}:${t.id}`, title: t.id, path: `/p/${pid}/element/${t.kind}/${encodeURIComponent(t.id)}`, stage: project?.stage_of[t.kind] || stage }) }
  const nextId = () => { const ids = rows.map(r => String(r.id)); const m = ids.map(i => i.match(/^(.*?)(\d+)$/)).filter(Boolean) as RegExpMatchArray[]; if (!m.length) return `${kind.slice(0, 3).toUpperCase()}-${String(rows.length + 1).padStart(2, '0')}`; const pre = m[m.length - 1][1]; const n = Math.max(...m.map(x => parseInt(x[2]))) + 1; return pre + String(n).padStart(m[m.length - 1][2].length, '0') }
  const template = () => { const t: any = {}; if (spec) { for (const k of spec.req) t[k] = ['tests', 'reqs', 'funcs', 'alloc', 'parts', 'lcs', 'items', 'columns', 'rows', 'elements'].includes(k) ? [] : ''; for (const [k, d] of Object.entries(spec.opt)) t[k] = Array.isArray(d) ? [] : typeof d === 'object' && d ? {} : d } return t }
  const unflat = (o: any) => { const v: any = {}; for (const [k, x] of Object.entries(o)) { if (k === '__new' || k === 'id') continue; if (k.startsWith('attrs.')) (v.attrs ??= {})[k.slice(6)] = x; else v[k] = x } return v }
  const onCommit = async ({ updates, adds, deletes }: any, stageIt: boolean) => {
    const ops: any[] = []; let n = 0
    for (const [id, val] of Object.entries(updates)) { const v = unflat(val); const orig = rows.find(r => r.id === id); if (v.attrs) v.attrs = { ...(orig?.attrs || {}), ...v.attrs }; ops.push({ op: 'update', kind, id, value: v }) }
    for (const a of adds) { const id = a.id && a.id !== 'new' ? a.id : (() => { const base = nextId(); const m = base.match(/^(.*?)(\d+)$/)!; return m[1] + String(parseInt(m[2]) + n++).padStart(m[2].length, '0') })(); ops.push({ op: 'add', kind, id, value: unflat(a) }) }
    for (const id of deletes) ops.push({ op: 'remove', kind, id })
    const r = await P(pid).post('/patch', { ops, rationale: `${KIND_LABEL[kind] || kind}: ${ops.length} change(s) in the sheet`, apply: !stageIt })
    toast(stageIt ? `Staged ${r.patch_id} for review` : `Applied ${r.patch_id}`); if (r.warnings?.length) toast(r.warnings.join('; '))
    P(pid).get('/collection/' + kind).then(setRows)
  }
  return <div>
    <div className="row between" style={{ marginBottom: 10 }}><div><h2>{KIND_LABEL[kind] || kind.replace(/_/g, ' ')} <span className="pill">{rows.length}</span></h2><div className="muted small"><StagePill stage={stage} /> {derived ? 'derived view — computed from the model, not editable' : 'edit any cell; changes become patches with provenance'}</div></div>
      <div className="row"><button className="chip" onClick={() => send(`Populate ${KIND_LABEL[kind] || kind} from the source documents and the model, staged in reviewable patches`)}><Sparkles size={13} />ask the agent to fill this</button></div></div>
    {derived ? <div className="tablewrap"><table className="dt"><thead><tr>{cols.map(c => <th key={c.key}>{c.name}</th>)}</tr></thead><tbody>{flat.map((r, i) => <tr key={i} className="clickable" onClick={() => open(r)}>{cols.map(c => <td key={c.key} className={c.name === 'AP' ? 'ap-' + r[c.key] : ''}><Cell v={r[c.key]} col={c.name} /></td>)}</tr>)}{!flat.length && <tr><td colSpan={cols.length} className="muted" style={{ padding: 18 }}>Nothing here yet.</td></tr>}</tbody></table></div>
      : <Sheet cols={cols} rows={flat} onCommit={onCommit} onOpen={open} newRowTemplate={template} onAddColumn={(name, type) => setExtra(x => [...x, { key: 'attrs.' + name.replace(/\W+/g, '_').toLowerCase(), name, type }])} />}
  </div>
}
