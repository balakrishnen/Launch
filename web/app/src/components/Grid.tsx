// Data grid for standard forms and matrices: grouped sticky headers, sort, per-column filter, merged structure cells,
// inline editing that becomes a patch, hide-empty-columns. Rows are plain arrays from the forms API.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Cell } from './common'
import { useProject } from '../state'
import type { Form } from '../api'

export function Grid({ form, onSaved }: { form: Form; onSaved?: () => void }) {
  const { pid, toast } = useProject()
  const [filters, setFilters] = useState<string[]>(() => form.headers.map(() => ''))
  const [sort, setSort] = useState<{ c: number; d: 1 | -1 } | null>(null)
  const [hideEmpty, setHideEmpty] = useState(true); const [dirty, setDirty] = useState<Record<string, string>>({}); const [quick, setQuick] = useState('')
  const wrap = useRef<HTMLDivElement>(null)
  useEffect(() => { setFilters(form.headers.map(() => '')); setDirty({}) }, [form.name, form.headers.length])
  const hidden = useMemo(() => new Set(hideEmpty ? form.headers.map((_, ci) => ci).filter(ci => form.rows.every(r => String(r[ci] ?? '').trim() === '')) : []), [form, hideEmpty])
  const apCol = form.headers.findIndex(h => h === 'DFMEA AP' || h === 'AP')
  const idx = useMemo(() => {
    let ix = form.rows.map((_, i) => i)
    ix = ix.filter(i => filters.every((q, ci) => !q || String(form.rows[i][ci] ?? '').toLowerCase().includes(q.toLowerCase())) && (!quick || apCol < 0 || String(form.rows[i][apCol]) === quick))
    if (sort) { const { c, d } = sort; ix.sort((x, y) => { const a = form.rows[x][c], b = form.rows[y][c]; const na = parseFloat(a), nb = parseFloat(b); const r = !isNaN(na) && !isNaN(nb) ? na - nb : String(a ?? '').localeCompare(String(b ?? '')); return d * r }) }
    return ix
  }, [form, filters, sort, quick, apCol])
  // sticky offsets after render
  useEffect(() => { const trs = wrap.current?.querySelectorAll('thead tr'); let top = 0; trs?.forEach(tr => { tr.querySelectorAll('th').forEach(th => (th as HTMLElement).style.top = top + 'px'); top += tr.getBoundingClientRect().height }) })
  const merge = sort ? [] : (form.merge_cols || [])
  // rowspans for merged structure cells
  const spans: Record<string, number> = {}; const first: Record<string, boolean> = {}
  if (merge.length && form.row_elements) { let prev: string | null = null, start = -1
    idx.forEach((ri, k) => { const el = form.row_elements![ri]; if (el !== prev) { start = k; prev = el; for (const ci of merge) { spans[`${ci}-${k}`] = 1; first[`${ci}-${k}`] = true } } else for (const ci of merge) spans[`${ci}-${start}`]++ }) }
  const editable = form.editable || {}
  const onInput = (ri: number, ci: number, el: HTMLElement) => { const v = el.innerText.trim(); const key = `${ri}-${ci}`; setDirty(d => { const n = { ...d }; if (v !== String(form.rows[ri][ci] ?? '')) n[key] = v; else delete n[key]; return n }); el.classList.toggle('dirty', v !== String(form.rows[ri][ci] ?? '')) }
  const save = async (stage: boolean) => {
    const byKey: Record<string, Record<string, any>> = {}
    for (const [k, v] of Object.entries(dirty)) { const [ri, ci] = k.split('-').map(Number); const key = form.row_keys?.[ri]; if (!key) continue; const fld = editable[ci]; (byKey[key] ??= {})[fld] = ['S', 'O', 'D'].includes(fld) ? Number(v) : v }
    const ops = Object.entries(byKey).map(([id, value]) => ({ op: 'update', kind: form.kind || 'fm_assessments', id, value }))
    try { const r = await fetch(`/api/p/${pid}/patch`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ops, rationale: `${form.title}: ${ops.length} row(s) edited in the table`, apply: !stage }) }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json() })
      toast(stage ? `Staged ${r.patch_id} for review` : `Applied ${r.patch_id}`); setDirty({}); onSaved?.() } catch (e: any) { toast(e.message) }
  }
  const groups = (() => { let c0 = 0; return form.groups.map(([g, n]) => { const span = [...Array(n).keys()].filter(i => !hidden.has(c0 + i)).length; c0 += n; return [g, span] as [string, number] }).filter(([, n]) => n > 0) })()
  const nDirty = Object.keys(dirty).length
  return <div>
    <div className="row between" style={{ margin: '6px 0 10px' }}>
      <div className="row">{apCol >= 0 && <>{['', 'H', 'M', 'L'].map(v => <button key={v} className={'chip' + (quick === v ? ' active' : '')} style={quick === v ? { borderColor: 'var(--accent)', color: 'var(--accent-ink)', background: 'var(--accent-soft)' } : {}} onClick={() => setQuick(v)}>{v ? <span className={'ap-' + v}>{v}</span> : 'all'}</button>)}</>}
        <span className="muted small">{idx.length} of {form.rows.length} rows{hidden.size ? ` · ${hidden.size} empty columns hidden` : ''}</span>
        <label className="small muted" style={{ display: 'flex', gap: 5, alignItems: 'center' }}><input type="checkbox" checked={hideEmpty} onChange={e => setHideEmpty(e.target.checked)} /> hide empty columns</label></div>
      {nDirty > 0 && <div className="row"><b>{nDirty} edited</b><button className="btn good sm" onClick={() => save(false)}>Save (apply)</button><button className="btn sm" onClick={() => save(true)}>Stage for review</button><button className="btn ghost sm" onClick={() => { setDirty({}); onSaved?.() }}>Discard</button></div>}
    </div>
    <div className="tablewrap" ref={wrap}>
      <table className="dt">
        <thead>
          {groups.length > 1 && <tr className="groups">{groups.map(([g, n], i) => <th key={i} colSpan={n}>{g}</th>)}</tr>}
          <tr>{form.headers.map((h, ci) => hidden.has(ci) ? null : <th key={ci} onClick={() => setSort(s => s?.c === ci ? (s.d === 1 ? { c: ci, d: -1 } : null) : { c: ci, d: 1 })} style={{ minWidth: Math.max(44, (form.widths[ci] || 12) * 5), maxWidth: Math.max(70, (form.widths[ci] || 12) * 8.5) }}>{h}{sort?.c === ci && <span style={{ color: 'var(--accent)' }}> {sort.d === 1 ? '▲' : '▼'}</span>}</th>)}</tr>
          <tr className="filters">{form.headers.map((_, ci) => hidden.has(ci) ? null : <th key={ci}><input placeholder="filter" value={filters[ci] || ''} onChange={e => setFilters(f => { const n = [...f]; n[ci] = e.target.value; return n })} /></th>)}</tr>
        </thead>
        <tbody>{idx.map((ri, k) => <tr key={ri}>{form.headers.map((h, ci) => { if (hidden.has(ci)) return null
          if (merge.includes(ci)) { if (!first[`${ci}-${k}`]) return null; return <td key={ci} className="merged" rowSpan={spans[`${ci}-${k}`]}><Cell v={form.rows[ri][ci]} col={h} /></td> }
          const ed = editable[ci] !== undefined && !!form.row_keys?.[ri]; const num = ['S', 'O', 'D'].includes(editable[ci])
          return <td key={ci} className={num ? 'num' : ''} contentEditable={ed || undefined} suppressContentEditableWarning onInput={ed ? e => onInput(ri, ci, e.currentTarget) : undefined}><Cell v={form.rows[ri][ci]} col={h} /></td> })}</tr>)}</tbody>
      </table>
    </div>
  </div>
}
