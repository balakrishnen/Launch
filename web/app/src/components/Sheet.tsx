// Sheet — the spreadsheet replacement. One editable grid for every collection and every ad-hoc table:
// click a cell to edit, Tab/Enter to move, add/delete rows, add columns, paste rows from a clipboard (TSV/CSV),
// per-column filter, sort, group-by, numeric totals. Every change becomes a patch (applied by you or staged for review),
// so nothing ever leaves the digital thread for Excel.
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Plus, Trash2, Columns3, ClipboardPaste, Check, Send, Undo2 } from 'lucide-react'
import { Cell } from './common'
import { useProject } from '../state'

export type Col = { key: string; name: string; type?: 'text' | 'number' | 'date' | 'ref' | 'formula' | 'list' | 'bool'; formula?: string; readonly?: boolean; width?: number }
type Row = Record<string, any> & { id?: string }

export function Sheet({ cols, rows, idKey = 'id', onCommit, onOpen, onAddColumn, allowAddRow = true, allowDelete = true, newRowTemplate, totals, title, dense, extraActions }: {
  cols: Col[]; rows: Row[]; idKey?: string
  onCommit: (change: { updates: Record<string, Record<string, any>>; adds: Row[]; deletes: string[] }, stage: boolean) => Promise<void>
  onOpen?: (r: Row) => void; onAddColumn?: (name: string, type: Col['type'], formula?: string) => void
  allowAddRow?: boolean; allowDelete?: boolean; newRowTemplate?: () => Row; totals?: Record<string, number>; title?: string; dense?: boolean; extraActions?: React.ReactNode
}) {
  const { toast } = useProject()
  const [edits, setEdits] = useState<Record<string, Record<string, any>>>({}); const [adds, setAdds] = useState<Row[]>([]); const [dels, setDels] = useState<Set<string>>(new Set())
  const [filters, setFilters] = useState<Record<string, string>>({}); const [sort, setSort] = useState<{ c: string; d: 1 | -1 } | null>(null); const [group, setGroup] = useState(''); const [showF, setShowF] = useState(false)
  const [addCol, setAddCol] = useState(false); const [nc, setNc] = useState<{ name: string; type: Col['type']; formula: string }>({ name: '', type: 'text', formula: '' })
  const wrap = useRef<HTMLDivElement>(null)
  useEffect(() => { setEdits({}); setAdds([]); setDels(new Set()) }, [rows])
  const all = useMemo(() => [...rows.map(r => ({ ...r, ...(edits[r[idKey]] || {}) })), ...adds], [rows, edits, adds])
  const view = useMemo(() => {
    let v = all.filter(r => !dels.has(r[idKey]))
    for (const [k, q] of Object.entries(filters)) if (q) v = v.filter(r => String(fmt(r[k])).toLowerCase().includes(q.toLowerCase()))
    if (sort) { const { c, d } = sort; v = [...v].sort((a, b) => { const x = a[c], y = b[c]; const nx = parseFloat(x), ny = parseFloat(y); return d * (!isNaN(nx) && !isNaN(ny) ? nx - ny : String(fmt(x)).localeCompare(String(fmt(y)))) }) }
    return v
  }, [all, dels, filters, sort, idKey])
  const groups = useMemo(() => { if (!group) return [['', view]] as [string, Row[]][]; const g: Record<string, Row[]> = {}; for (const r of view) { const k = String(fmt(r[group]) || '—'); (g[k] ??= []).push(r) } return Object.entries(g) }, [view, group])
  const nDirty = Object.keys(edits).length + adds.length + dels.size
  const setCell = (r: Row, key: string, raw: string) => {
    const col = cols.find(c => c.key === key); const v = coerce(raw, col, r[key])
    if (adds.includes(r)) { r[key] = v; setAdds(a => [...a]); return }
    const id = String(r[idKey]); setEdits(e => { const n: Record<string, Record<string, any>> = { ...e, [id]: { ...(e[id] || {}), [key]: v } }; if (JSON.stringify(v) === JSON.stringify(rows.find(x => x[idKey] === id)?.[key])) { delete n[id][key]; if (!Object.keys(n[id]).length) delete n[id] } return n })
  }
  const commit = async (stage: boolean) => {
    try { await onCommit({ updates: edits, adds: adds.map(a => ({ ...a })), deletes: [...dels] }, stage); setEdits({}); setAdds([]); setDels(new Set()) } catch (e: any) { toast(e.message) }
  }
  const addRow = () => { const t = newRowTemplate ? newRowTemplate() : {}; setAdds(a => [...a, { ...t, __new: true }]) }
  const onPaste = (e: React.ClipboardEvent) => {
    const txt = e.clipboardData.getData('text/plain'); if (!txt || !txt.includes('\n') && !txt.includes('\t')) return
    const target = e.target as HTMLElement; if (target.isContentEditable && !txt.includes('\n')) return   // single-cell paste
    e.preventDefault(); const lines = txt.replace(/\r/g, '').split('\n').filter(l => l.trim()); const sep = lines[0].includes('\t') ? '\t' : ','
    const grid = lines.map(l => l.split(sep)); let hdr = grid[0].map(h => h.trim()); let body = grid.slice(1)
    const keyOf = (h: string) => cols.find(c => c.key === h || c.name.toLowerCase() === h.toLowerCase())?.key
    const mapped = hdr.map(keyOf); if (mapped.filter(Boolean).length < Math.max(1, hdr.length / 2)) { hdr = cols.filter(c => c.key !== idKey && !c.readonly).map(c => c.key); body = grid; mapped.splice(0, mapped.length, ...hdr) }
    const news = body.map(cells => { const r: Row = newRowTemplate ? newRowTemplate() : {}; cells.forEach((v, i) => { const k = mapped[i]; if (k) r[k] = coerce(v.trim(), cols.find(c => c.key === k), undefined) }); r.__new = true; return r })
    setAdds(a => [...a, ...news]); toast(`${news.length} row(s) pasted — review and apply`)
  }
  const keyNav = (e: React.KeyboardEvent<HTMLTableCellElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); (e.currentTarget as HTMLElement).blur(); const tr = e.currentTarget.parentElement as HTMLTableRowElement; const ci = e.currentTarget.cellIndex; const next = (tr.nextElementSibling as HTMLTableRowElement)?.cells[ci] as HTMLElement; next?.isContentEditable && next.focus() }
    if (e.key === 'Escape') { e.currentTarget.innerText = String(fmt((e.currentTarget as any).__orig ?? '')); e.currentTarget.blur() }
  }
  const editable = (c: Col) => !c.readonly && c.key !== idKey && c.type !== 'formula'
  return <div className="sheet" onPaste={onPaste}>
    <div className="row between" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        {allowAddRow && <button className="btn sm" onClick={addRow}><Plus size={14} />Row</button>}
        {onAddColumn && <button className="btn sm" onClick={() => setAddCol(v => !v)}><Columns3 size={14} />Column</button>}
        <button className="btn sm" onClick={() => setShowF(v => !v)}>Filter</button>
        <select className="field" style={{ width: 'auto', padding: '4px 8px' }} value={group} onChange={e => setGroup(e.target.value)}><option value="">No grouping</option>{cols.filter(c => c.key !== idKey).map(c => <option key={c.key} value={c.key}>Group by {c.name}</option>)}</select>
        <span className="muted small"><ClipboardPaste size={12} style={{ verticalAlign: -2 }} /> paste rows from a spreadsheet anywhere in the table</span>
        {extraActions}
      </div>
      <div className="row" style={{ gap: 6 }}>
        {nDirty > 0 && <><span className="pill warn">{nDirty} change{nDirty > 1 ? 's' : ''}</span><button className="btn sm" onClick={() => { setEdits({}); setAdds([]); setDels(new Set()) }}><Undo2 size={14} />Discard</button><button className="btn sm" onClick={() => commit(true)}><Send size={14} />Stage for review</button><button className="btn sm primary" onClick={() => commit(false)}><Check size={14} />Apply</button></>}
      </div>
    </div>
    {addCol && <div className="card row" style={{ gap: 8, marginBottom: 8, padding: 10, flexWrap: 'wrap' }}>
      <input className="field" style={{ width: 180 }} placeholder="column name" value={nc.name} onChange={e => setNc({ ...nc, name: e.target.value })} />
      <select className="field" style={{ width: 'auto' }} value={nc.type} onChange={e => setNc({ ...nc, type: e.target.value as any })}><option value="text">text</option><option value="number">number</option><option value="date">date</option><option value="ref">reference (element id)</option><option value="formula">formula</option></select>
      {nc.type === 'formula' && <input className="field mono" style={{ flex: 1, minWidth: 260 }} placeholder="e.g. qty * unit_cost   ·   part(part_id).attrs.mass   ·   sum(cols.cost)" value={nc.formula} onChange={e => setNc({ ...nc, formula: e.target.value })} />}
      <button className="btn sm primary" disabled={!nc.name} onClick={() => { onAddColumn!(nc.name, nc.type, nc.formula); setAddCol(false); setNc({ name: '', type: 'text', formula: '' }) }}>Add column</button>
    </div>}
    <div className={'tablewrap' + (dense ? ' dense' : '')} ref={wrap}><table className="dt sheet-t"><thead>
      <tr>{allowDelete && <th style={{ width: 28 }} />}{cols.map(c => <th key={c.key} title={c.formula ? '= ' + c.formula : c.type} onClick={() => setSort(s => s?.c === c.key ? (s.d === 1 ? { c: c.key, d: -1 } : null) : { c: c.key, d: 1 })} style={c.width ? { minWidth: c.width } : {}}>{c.name}{c.type === 'formula' ? <span className="muted"> ƒ</span> : ''}{sort?.c === c.key ? (sort.d === 1 ? ' ▲' : ' ▼') : ''}</th>)}</tr>
      {showF && <tr className="filters">{allowDelete && <th />}{cols.map(c => <th key={c.key}><input value={filters[c.key] || ''} onChange={e => setFilters(f => ({ ...f, [c.key]: e.target.value }))} placeholder="filter" /></th>)}</tr>}
    </thead><tbody>
      {groups.map(([g, rs]) => <React.Fragment key={g}>
        {group && <tr className="grp"><td colSpan={cols.length + (allowDelete ? 1 : 0)}><b>{g}</b> <span className="muted">· {rs.length}</span></td></tr>}
        {rs.map((r, i) => { const id = r[idKey]; const isNew = !!r.__new; const changed = edits[id]
          return <tr key={id || 'new' + i} className={isNew ? 'new' : changed ? 'changed' : ''}>
            {allowDelete && <td className="rowtool" onClick={() => isNew ? setAdds(a => a.filter(x => x !== r)) : setDels(d => { const n = new Set(d); n.add(id); return n })} title="delete row"><Trash2 size={13} /></td>}
            {cols.map(c => { const v = r[c.key]; const ed = editable(c)
              return <td key={c.key} className={(ed ? 'ed' : '') + (changed?.[c.key] !== undefined ? ' dirty' : '') + (c.type === 'number' || c.type === 'formula' ? ' num' : '') + (typeof v === 'string' && v.startsWith('#') && c.type === 'formula' ? ' err' : '')}
                contentEditable={ed} suppressContentEditableWarning ref={el => { if (el) (el as any).__orig = v }}
                onFocus={e => { if (ed) e.currentTarget.innerText = String(fmt(v)) }} onBlur={e => ed && setCell(r, c.key, e.currentTarget.innerText)} onKeyDown={keyNav}
                onClick={e => { if (!ed && c.key === idKey && onOpen && !isNew) { e.preventDefault(); onOpen(r) } }}>
                {c.key === idKey ? <span className="id" style={{ cursor: onOpen ? 'pointer' : 'default' }}>{isNew ? <span className="muted">new</span> : id}</span> : <Cell v={v} col={c.name} />}</td> })}
          </tr> })}
      </React.Fragment>)}
      {totals && Object.keys(totals).length > 0 && <tr className="totals">{allowDelete && <td />}{cols.map(c => <td key={c.key} className="num">{totals[c.key] !== undefined ? <b>{totals[c.key]}</b> : c.key === idKey ? <span className="muted">Σ</span> : ''}</td>)}</tr>}
      {view.length === 0 && <tr><td colSpan={cols.length + 1} className="muted" style={{ padding: 18 }}>No rows — add one, or paste rows from a spreadsheet.</td></tr>}
    </tbody></table></div>
    {title && <div className="muted small" style={{ marginTop: 6 }}>{title}</div>}
  </div>
}

function fmt(v: any): string { if (v === null || v === undefined) return ''; if (Array.isArray(v)) return v.join(', '); if (typeof v === 'object') return JSON.stringify(v); return String(v) }
function coerce(raw: string, col?: Col, prev?: any) {
  if (col?.type === 'number') { const n = Number(raw.replace(/,/g, '')); return raw.trim() === '' ? '' : isNaN(n) ? raw : n }
  if (col?.type === 'list' || Array.isArray(prev)) return raw.trim() === '' ? [] : raw.split(/[,;]\s*/).map(s => s.trim()).filter(Boolean)
  if (col?.type === 'bool' || typeof prev === 'boolean') return /^(true|yes|1|y)$/i.test(raw.trim())
  if (typeof prev === 'number' && raw.trim() !== '' && !isNaN(Number(raw))) return Number(raw)
  if (prev && typeof prev === 'object' && !Array.isArray(prev)) { try { return JSON.parse(raw) } catch { return prev } }
  return raw
}
