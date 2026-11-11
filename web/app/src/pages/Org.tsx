// Organization — what the company defines once: its product-development process (phases, gates, deliverables), its team
// catalog, its members and roles, the tools it uses, and harness policy defaults. Every new project inherits it; existing
// projects can re-apply it as a reviewable patch. Outside any project (no ProjectProvider), so it has its own tiny state.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, GitBranch, Users, UserPlus, Plug, Shield, Save } from 'lucide-react'
import { api } from '../api'

type Col = { key: string; name: string; type?: 'text' | 'number' | 'list' | 'bool' | 'select'; options?: string[]; width?: number }
const TABS = ['Process', 'Teams', 'Members', 'Tools', 'Policy']

export function Org() {
  const nav = useNavigate()
  const [o, setO] = useState<any>(null); const [tab, setTab] = useState('Process'); const [msg, setMsg] = useState(''); const [dirty, setDirty] = useState(false); const [tpls, setTpls] = useState<any>(null); const [ps, setPs] = useState<any[]>([])
  useEffect(() => { api.get('/org').then(setO).catch(e => setMsg(e.message)); api.get('/org/templates').then(setTpls).catch(() => { }); api.get('/projects').then(setPs).catch(() => { }) }, [])
  const toast = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2600) }
  const save = async () => { try { const r = await api.post('/org', { name: o.name, processes: o.processes, default_process: o.default_process, teams: o.teams, members: o.members, tools: o.tools, policy: o.policy }); setO(r); setDirty(false); toast('Organization saved') } catch (e: any) { toast(e.message) } }
  const set = (k: string, v: any) => { setO((x: any) => ({ ...x, [k]: v })); setDirty(true) }
  const [pv, setPv] = useState<string>('')
  const cur = (o && (o.processes || []).find((x: any) => x.id === (pv || o.default_process))) || o?.process
  const setP = (k: string, v: any) => { setO((x: any) => { const id = pv || x.default_process; const procs = (x.processes || []).map((p: any) => p.id === id ? { ...p, [k]: v } : p); const proc = procs.find((p: any) => p.id === x.default_process) || procs[0]; return { ...x, processes: procs, process: proc } }); setDirty(true) }
  const addVariant = () => { const name = prompt('Name of the new process variant (e.g. Derivative product, Accessory, Platform)'); if (!name) return; const id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); setO((x: any) => ({ ...x, processes: [...x.processes, { ...JSON.parse(JSON.stringify(cur)), id, name }] })); setPv(id); setDirty(true) }
  const delVariant = () => { if (!pv || pv === o.default_process) return; setO((x: any) => ({ ...x, processes: x.processes.filter((p: any) => p.id !== pv) })); setPv(''); setDirty(true) }
  if (!o) return <div className="empty">{msg || 'Loading organization…'}</div>
  const canEdit = ['admin', 'program_manager'].includes(o.me?.role)
  const teamIds = o.teams.map((t: any) => t.id); const gateIds = (cur.gates || []).map((g: any) => g.id)
  return <div style={{ maxWidth: 1200, margin: '28px auto', padding: '0 20px' }}>
    <div className="row between" style={{ marginBottom: 6 }}><div><div className="row" style={{ gap: 8 }}><Building2 size={18} /><h1 style={{ margin: 0 }}>{o.name}</h1><span className="pill">{o.me?.role}</span></div><div className="muted small">Defined once, inherited by every project. {o.me?.email} · <a href="#" onClick={e => { e.preventDefault(); nav('/') }}>projects</a></div></div>
      <div className="row">{dirty && <span className="pill warn">unsaved</span>}<button className="btn primary" disabled={!canEdit || !dirty} onClick={save}><Save size={14} />Save</button></div></div>
    {!canEdit && <div className="card small" style={{ margin: '8px 0', borderColor: '#f5d78e' }}>You can view the organization; admins and program managers edit it. The first users before any member is listed are admins — add yourself under Members.</div>}
    <div className="sectabs">{TABS.map(t => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>

    {tab === 'Process' && <div className="stack" style={{ gap: 14 }}>
      <div className="card"><div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10, alignItems: 'center' }}><span className="small" style={{ fontWeight: 600 }}>Process variants</span>{o.processes.map((p: any) => <button key={p.id} className="chip" style={(pv || o.default_process) === p.id ? { borderColor: 'var(--accent)', color: 'var(--accent-ink)', background: 'var(--accent-soft)' } : {}} onClick={() => setPv(p.id)}>{p.name || p.id}{p.id === o.default_process ? ' · default' : ''}</button>)}<button className="btn sm" onClick={addVariant}>+ Variant</button>{pv && pv !== o.default_process && <><button className="btn sm" onClick={() => { set('default_process', pv) }}>Make default</button><button className="btn sm" onClick={delVariant}>Delete</button></>}<span className="muted small">A multi-product company keeps several (platform, derivative, accessory…); a project picks one and tailors it.</span></div>
        <div className="row between" style={{ flexWrap: 'wrap', gap: 8 }}><div><h4><GitBranch size={14} style={{ verticalAlign: -2 }} /> {cur.name || 'Product development process'}</h4><div className="muted small">Phases in order, each closed by a gate; deliverables owed per team at each gate. Start from a template, then tailor.</div></div>
        <div className="row" style={{ gap: 6 }}><select className="field" style={{ width: 'auto' }} value="" onChange={e => { const t = tpls?.detail?.[e.target.value]; if (t) { setP('template', e.target.value); setP('name', t.name); setP('phases', t.phases); setP('gates', t.gates); setP('deliverables', t.deliverables) } }}><option value="">Replace with template…</option>{(tpls?.templates || []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}</select><span className="small">gate spacing</span><input className="field" style={{ width: 70 }} type="number" value={cur.spacing_days} onChange={e => setP('spacing_days', Number(e.target.value))} /><span className="small">days</span></div></div>
        <div className="phases" style={{ marginTop: 10 }}>{(cur.phases || []).slice().sort((a: any, b: any) => a.order - b.order).map((p: any, i: number) => <div key={p.id} className="phase"><div className="ph">{i + 1}. {p.name}<div className="muted small">{p.stage}</div></div><div className="gate"><b>{p.gate}</b></div></div>)}</div></div>
      <Table title="Phases" rows={cur.phases || []} onChange={rows => setP('phases', rows)} idPrefix="PH-" cols={[{ key: 'id', name: 'id' }, { key: 'name', name: 'name' }, { key: 'order', name: 'order', type: 'number' }, { key: 'stage', name: 'ISO 15288 stage', type: 'select', options: ['Concept', 'Development', 'Production', 'Utilization', 'Support', 'Retirement'] }, { key: 'gate', name: 'closed by gate', type: 'select', options: gateIds }, { key: 'description', name: 'description' }]} />
      <Table title="Gates" rows={cur.gates || []} onChange={rows => setP('gates', rows)} idPrefix="G" cols={[{ key: 'id', name: 'id' }, { key: 'name', name: 'name' }, { key: 'exit', name: 'exit criteria', width: 360 }]} />
      <Table title="Deliverables" rows={(cur.deliverables || []).map((d: any) => ({ ...d, check: typeof d.check === 'string' ? d.check : JSON.stringify(d.check || {}) }))} onChange={rows => setP('deliverables', rows.map((r: any) => ({ ...r, check: parseJson(r.check) })))} idPrefix="D-"
        cols={[{ key: 'id', name: 'id' }, { key: 'name', name: 'name', width: 220 }, { key: 'gate', name: 'gate', type: 'select', options: gateIds }, { key: 'team', name: 'team', type: 'select', options: ['', ...teamIds] }, { key: 'team_kind', name: 'every team of kind', type: 'select', options: ['', 'subsystem', 'functional'] }, { key: 'focus', name: 'every team with focus', type: 'select', options: ['', ...o.focus_options] }, { key: 'required', name: 'required', type: 'bool' }, { key: 'check', name: 'check (JSON)', width: 300 }]}
        help={<>Checks the model evaluates: <code>{'{"type":"coverage","key":"requirements_without_tests","max":0}'}</code> · <code>{'{"type":"scope","key":"fmea_complete"}'}</code> (subsystem teams: boundary_items, req_coverage, fmea_complete, tests_passed) · <code>{'{"type":"attachment","roles":["cad"]}'}</code> · <code>{'{"type":"note","kind":"report","status":"final"}'}</code> · <code>{'{"type":"collection","kind":"process_steps","n":1}'}</code> · <code>{'{"type":"tests_passed_share","min":1}'}</code></>} />
    </div>}

    {tab === 'Teams' && <Table title="Team catalog" icon={<Users size={14} />} rows={o.teams} onChange={rows => set('teams', rows)} idPrefix="TM-" cols={[{ key: 'id', name: 'id' }, { key: 'name', name: 'name', width: 200 }, { key: 'kind', name: 'kind', type: 'select', options: ['functional', 'subsystem'] }, { key: 'focus', name: 'focus (functional)', type: 'select', options: ['', ...o.focus_options] }, { key: 'discipline', name: 'discipline' }, { key: 'lead', name: 'lead (email)' }, { key: 'parts', name: 'scope root parts (subsystem; per project)', type: 'list' }]}
      help="Subsystem teams are product-specific (wash system, brew performance, BMS, drive). Define them here with the names the company uses; their scope (root parts, logical components, MoEs) is set per project, or proposed by the agent from the architecture." />}

    {tab === 'Members' && <Table title="Members" icon={<UserPlus size={14} />} rows={o.members} onChange={rows => set('members', rows)} idPrefix="" idKey="email" cols={[{ key: 'email', name: 'email', width: 220 }, { key: 'name', name: 'name' }, { key: 'role', name: 'role', type: 'select', options: o.roles }, { key: 'teams', name: 'teams', type: 'list' }, { key: 'title', name: 'title' }]}
      help="Roles: admin (everything), program_manager (process, gates, deliverables), engineer (edit records, approve patches of own team), reviewer (approve only), viewer. Team membership drives 'My team' and reviewer routing in every project. SSO/SCIM will populate this list when connected." />}

    {tab === 'Tools' && <div className="card"><h4><Plug size={14} style={{ verticalAlign: -2 }} /> Tools</h4><div className="muted small" style={{ marginBottom: 10 }}>Launch apps are built on the kernel; integrations are drivers to tools that already do a deep job. Enabled apps appear in every project's navigation.</div>
      {[['app', 'Launch apps'], ['integration', 'Integrations']].map(([kind, label]) => <div key={kind} style={{ marginBottom: 14 }}><div className="small" style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div><div className="stack" style={{ gap: 6 }}>{o.tool_catalog.filter((t: any) => t.kind === kind).map((t: any) => { const cur = o.tools.find((x: any) => x.id === t.id) || { id: t.id, enabled: t.default, config: t.config || {} }
        return <div key={t.id} className="row" style={{ gap: 10, alignItems: 'flex-start', padding: '6px 8px', border: '1px solid var(--line)', borderRadius: 9 }}><input type="checkbox" checked={!!cur.enabled} disabled={t.status === 'planned'} onChange={e => set('tools', [...o.tools.filter((x: any) => x.id !== t.id), { ...cur, enabled: e.target.checked }])} /><div style={{ flex: 1 }}><div className="row" style={{ gap: 6 }}><b className="small">{t.name}</b>{t.status === 'planned' && <span className="pill" style={{ fontSize: 10 }}>planned</span>}</div>
          {cur.enabled && t.config && <div className="row" style={{ gap: 6, marginTop: 4, flexWrap: 'wrap' }}>{Object.keys(t.config).map(k => <label key={k} className="row small" style={{ gap: 4 }}>{k}<input className="field" style={{ width: 220 }} type={k === 'token' ? 'password' : 'text'} value={cur.config?.[k] || ''} onChange={e => set('tools', [...o.tools.filter((x: any) => x.id !== t.id), { ...cur, config: { ...cur.config, [k]: e.target.value } }])} /></label>)}</div>}</div></div> })}</div></div>)}</div>}

    {tab === 'Policy' && <div className="card"><h4><Shield size={14} style={{ verticalAlign: -2 }} /> Harness policy defaults</h4><div className="muted small" style={{ marginBottom: 8 }}>Applied to new projects; each project can tighten or loosen it on its Agent harness page.</div>
      <div className="small" style={{ fontWeight: 600 }}>Agents may apply on their own (kinds)</div><input className="field" value={(o.policy.auto_apply_kinds || []).join(', ')} onChange={e => set('policy', { ...o.policy, auto_apply_kinds: e.target.value.split(/[,\s]+/).filter(Boolean) })} />
      <div className="small" style={{ fontWeight: 600, marginTop: 10 }}>Always needs a reviewer (kinds)</div><input className="field" value={(o.policy.require_review_kinds || []).join(', ')} onChange={e => set('policy', { ...o.policy, require_review_kinds: e.target.value.split(/[,\s]+/).filter(Boolean) })} /></div>}

    <div className="card" style={{ marginTop: 16 }}><h4>Apply to a project</h4><div className="muted small" style={{ marginBottom: 8 }}>New projects inherit the organization automatically. Re-apply to an existing project as one reviewable patch (teams gain members; process phases, gates and deliverables are added or updated; existing gate dates are kept).</div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>{ps.map(p => <button key={p.id} className="chip" onClick={async () => { try { const r = await api.post(`/org/apply/${p.id}`, { apply: true }); toast(r.patch_id ? `Applied to ${p.name} — ${r.patch_id}` : 'Nothing to apply') } catch (e: any) { toast(e.message) } }}>{p.name}</button>)}</div></div>
    {msg && <div className="toast">{msg}</div>}
  </div>
}
function parseJson(s: any) { if (typeof s !== 'string') return s || {}; try { return JSON.parse(s || '{}') } catch { return {} } }

// A small editable table for org config (no patches — the org is a document, saved as a whole).
function Table({ title, icon, rows, onChange, cols, idPrefix, idKey = 'id', help }: { title: string; icon?: any; rows: any[]; onChange: (rows: any[]) => void; cols: Col[]; idPrefix: string; idKey?: string; help?: any }) {
  const upd = (i: number, k: string, v: any) => { const n = rows.map((r, j) => j === i ? { ...r, [k]: v } : r); onChange(n) }
  const add = () => onChange([...rows, Object.fromEntries(cols.map(c => [c.key, c.type === 'list' ? [] : c.type === 'bool' ? true : c.type === 'number' ? rows.length + 1 : c.key === idKey ? `${idPrefix}${String(rows.length + 1).padStart(2, '0')}` : '']))])
  const del = (i: number) => onChange(rows.filter((_, j) => j !== i))
  const sorted = useMemo(() => rows, [rows])
  return <div className="card"><div className="row between"><h4>{icon} {title} <span className="pill">{rows.length}</span></h4><button className="btn sm" onClick={add}>+ Row</button></div>
    <div className="tablewrap" style={{ maxHeight: 420 }}><table className="dt"><thead><tr><th style={{ width: 28 }} />{cols.map(c => <th key={c.key} style={c.width ? { minWidth: c.width } : {}}>{c.name}</th>)}</tr></thead><tbody>
      {sorted.map((r, i) => <tr key={i}><td className="rowtool" style={{ cursor: 'pointer', color: 'var(--ink-3)' }} onClick={() => del(i)} title="remove">✕</td>{cols.map(c => <td key={c.key}>
        {c.type === 'select' ? <select className="field" style={{ padding: '3px 6px' }} value={r[c.key] ?? ''} onChange={e => upd(i, c.key, e.target.value || (c.key === 'team' ? null : ''))}>{(c.options || []).map(x => <option key={x} value={x}>{x || '—'}</option>)}</select>
          : c.type === 'bool' ? <input type="checkbox" checked={r[c.key] !== false} onChange={e => upd(i, c.key, e.target.checked)} />
            : c.type === 'number' ? <input className="field" style={{ padding: '3px 6px', width: 70 }} type="number" value={r[c.key] ?? ''} onChange={e => upd(i, c.key, Number(e.target.value))} />
              : c.type === 'list' ? <input className="field" style={{ padding: '3px 6px' }} value={(r[c.key] || []).join(', ')} onChange={e => upd(i, c.key, e.target.value.split(/[,;]\s*/).filter(Boolean))} />
                : <input className="field" style={{ padding: '3px 6px' }} value={r[c.key] ?? ''} onChange={e => upd(i, c.key, e.target.value)} />}</td>)}</tr>)}
      {!rows.length && <tr><td colSpan={cols.length + 1} className="muted" style={{ padding: 14 }}>Empty — add a row.</td></tr>}</tbody></table></div>
    {help && <div className="muted small" style={{ marginTop: 6 }}>{help}</div>}</div>
}
