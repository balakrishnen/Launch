// Named skills — packaged jobs a role agent runs over this project's graph. "Suggested now" is computed from the model
// (open trades, parts without DFMEA, lots without CAPA, …); the catalog is the whole set, by department. Running one opens
// a conversation with the skill's role and the procedure scoped to the chosen ids; every write is a staged patch.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, ChevronDown, ChevronRight } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { IdLink } from '../components/common'

const DEPT: Record<string, string> = { engineering: 'Engineering', quality: 'Quality', supply_chain: 'Supply chain', manufacturing: 'Manufacturing', program: 'Program', service: 'Service', go_to_market: 'Go-to-market', corporate: 'Corporate' }

export function useSkills(pid: string, deps: any[] = []) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { P(pid).get('/skills').then(setD).catch(() => setD(null)) }, [pid, ...deps])
  return d
}

export function runSkill(pid: string, id: string, ids: string[] | undefined, nav: (p: string) => void) {
  return P(pid).post(`/skill/${id}/run`, { ids }).then((r: any) => nav(`/p/${pid}/chat/${r.thread}`))
}

export function Skills() {
  const { pid, patches, project } = useProject(); const nav = useNavigate()
  const d = useSkills(pid, [patches.length, project?.meta?.rev])
  const [open, setOpen] = useState<string | null>(null)
  if (!d) return <div className="empty">Loading…</div>
  const sugg: any[] = d.suggested || []; const byId: Record<string, any> = {}; for (const s of d.skills) byId[s.id] = s
  const groups: Record<string, any[]> = {}; for (const s of d.skills) (groups[s.department] ||= []).push(s)
  return <div>
    <div className="row between" style={{ marginBottom: 12 }}><div><h2>Skills</h2><div className="muted small">Packaged, repeatable jobs over the model — each with a trigger, what it reads, the procedure, and what it leaves behind. A skill runs as the named role in a conversation; every change it makes is a patch staged for review. The same catalog is served to MCP clients as prompts.</div></div></div>

    <h4 style={{ margin: '14px 0 6px' }}>Suggested now</h4>
    <div className="card" style={{ padding: 0, overflow: 'auto' }}><table className="dt"><thead><tr><th>Skill</th><th>Why now</th><th>Scope</th><th>Role</th><th /></tr></thead><tbody>
      {sugg.map(s => <tr key={s.id}><td><b>{s.name}</b><div className="muted small">{DEPT[s.department] || s.department}</div></td><td className="small">{s.why}</td><td className="ids small">{(s.ids || []).slice(0, 6).map((x: string) => <IdLink key={x} id={x} />)}{s.n > 6 && <span className="muted"> +{s.n - 6}</span>}</td><td className="small muted">{s.role}</td>
        <td><button className="chip" onClick={() => runSkill(pid, s.id, s.ids?.length ? s.ids : undefined, nav)}><Sparkles size={12} />run</button></td></tr>)}
      {!sugg.length && <tr><td colSpan={5} className="muted">Nothing is calling for a skill right now.</td></tr>}</tbody></table></div>

    <h4 style={{ margin: '22px 0 6px' }}>Catalog</h4>
    <div className="card" style={{ padding: 0, overflow: 'auto' }}><table className="dt"><thead><tr><th style={{ width: 22 }} /><th>Skill</th><th>When to use</th><th>Leaves behind</th><th>Role</th><th /></tr></thead><tbody>
      {Object.entries(groups).flatMap(([dk, list]) => [<tr key={'d:' + dk} style={{ background: 'var(--surface-2)' }}><td colSpan={6}><b className="small" style={{ textTransform: 'uppercase', letterSpacing: 1 }}>{DEPT[dk] || dk}</b></td></tr>,
        ...list.flatMap(s => [<tr key={s.id} className="clickable" onClick={() => setOpen(open === s.id ? null : s.id)}><td>{open === s.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td><td><b>{s.name}</b></td><td className="small">{s.trigger}</td><td className="small muted">{s.outputs.join(', ')}</td><td className="small muted">{s.role}</td>
          <td><button className="chip" onClick={e => { e.stopPropagation(); runSkill(pid, s.id, undefined, nav) }}><Sparkles size={12} />run</button></td></tr>,
        open === s.id && <tr key={s.id + ':p'}><td /><td colSpan={5}><div className="small" style={{ whiteSpace: 'pre-wrap', maxWidth: 820 }}><div className="muted" style={{ marginBottom: 4 }}>Reads: {s.reads.join(', ')}{s.form ? ` · form: ${s.form}` : ''}</div>{s.procedure}</div></td></tr>])])}</tbody></table></div>
  </div>
}
