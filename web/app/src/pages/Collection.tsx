import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProject } from '../state'
import { P, KIND_LABEL } from '../api'
import { Cell, StagePill } from '../components/common'

const DERIVED_LINK: Record<string, (r: any) => { kind: string; id: string }> = { fmea: r => ({ kind: 'fmea', id: r.id }), unassessed: r => ({ kind: r.kind, id: r.element }), screened: r => ({ kind: r.kind, id: r.element }), verification_matrix: r => ({ kind: 'tests', id: r.id }), certification_plan: r => ({ kind: 'regulations', id: r.id }) }

export function Collection() {
  const { kind = '' } = useParams(); const { pid, project, openTab, send, patches } = useProject()
  const [rows, setRows] = useState<any[]>([]); const [q, setQ] = useState(''); const [sort, setSort] = useState<{ c: string; d: 1 | -1 } | null>(null)
  useEffect(() => { P(pid).get('/collection/' + kind).then(setRows).catch(() => setRows([])) }, [pid, kind, patches.length, project?.meta?.rev])
  const cols = useMemo(() => [...new Set(rows.flatMap(r => Object.keys(r)))].filter(k => !['disciplines', 'attrs', 'higher', 'focus', 'lower'].includes(k)).slice(0, 12), [rows])
  const view = useMemo(() => { let v = rows; const ql = q.toLowerCase(); if (ql) v = v.filter(r => JSON.stringify(r).toLowerCase().includes(ql)); if (sort) { const { c, d } = sort; v = [...v].sort((a, b) => { const x = a[c], y = b[c]; const nx = parseFloat(x), ny = parseFloat(y); return d * (!isNaN(nx) && !isNaN(ny) ? nx - ny : String(x ?? '').localeCompare(String(y ?? ''))) }) } return v }, [rows, q, sort])
  const stage = project?.stage_of[kind] || 'Risk (derived)'
  const open = (r: any) => { const t = DERIVED_LINK[kind] ? DERIVED_LINK[kind](r) : { kind, id: r.id }; openTab({ key: `el:${t.kind}:${t.id}`, title: t.id, path: `/p/${pid}/element/${t.kind}/${encodeURIComponent(t.id)}`, stage: project?.stage_of[t.kind] || stage }) }
  return <div>
    <div className="row between" style={{ marginBottom: 10 }}><div><h2>{KIND_LABEL[kind] || kind.replace(/_/g, ' ')} <span className="pill">{view.length}{view.length !== rows.length ? ` of ${rows.length}` : ''}</span></h2><div className="muted small"><StagePill stage={stage} /> click a row to open the element with everything linked to it</div></div>
      <div className="row"><input className="field" style={{ width: 260 }} placeholder="filter rows…" value={q} onChange={e => setQ(e.target.value)} /><button className="chip" onClick={() => send(`Populate ${KIND_LABEL[kind] || kind} from the source documents and the model, staged in reviewable patches`)}>▶ ask the agent</button></div></div>
    {rows.length === 0 ? <div className="empty">Nothing here yet.</div> :
      <div className="tablewrap"><table className="dt"><thead><tr>{cols.map(c => <th key={c} onClick={() => setSort(s => s?.c === c ? (s.d === 1 ? { c, d: -1 } : null) : { c, d: 1 })}>{c}{sort?.c === c ? (sort.d === 1 ? ' ▲' : ' ▼') : ''}</th>)}</tr></thead>
        <tbody>{view.map((r, i) => <tr key={i} className="clickable" onClick={() => open(r)}>{cols.map(c => <td key={c} className={c === 'AP' ? 'ap-' + r[c] : ''}>{c === 'id' ? <span className="id">{r[c]}</span> : <Cell v={r[c]} col={c} />}</td>)}</tr>)}</tbody></table></div>}
  </div>
}
