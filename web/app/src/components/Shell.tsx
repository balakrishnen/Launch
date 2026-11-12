import React, { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BarChart3, Building2, Users, Home, Library, GitBranch, Inbox, Plug, Sparkles, Search, Sun, Moon, ChevronDown, X, Hammer, PanelLeft, HelpCircle, FolderOpen, Bell } from 'lucide-react'
import { useProject } from '../state'
import { FORMS, KIND_LABEL, STAGE_COLOR, stageColor, LIFECYCLE } from '../api'
import { AgentDrawer } from './Agent'
import { Palette } from './Palette'


// non-collection artifacts per ISO 15288 process: [route, label, count key]
const EXTRA: Record<string, [string, string, string?][]> = {
  'Stakeholder needs and requirements definition': [['matrix/needs/requirements', 'Needs × requirements']],
  'System requirements definition': [['form/reqspec', 'Requirements specification'], ['matrix/regulations/requirements', 'Regulations × requirements'], ['collection/certification_plan', 'Certification plan']],
  'Business or mission analysis': [['form/claims', 'Claims substantiation', 'claims'], ['form/markets', 'Market readiness'], ['form/cost', 'Cost & margin']],
  'System architecture definition': [['form/n2l', 'N² — logical'], ['form/n2', 'N² — physical'], ['form/icd', 'ICD index'], ['matrix/functions/logical_components', 'Functions × logical components'], ['diagrams', 'SysML v2 diagrams'], ['views', 'Rendered views']],
  'Design definition': [['eda', 'Electrical (native EDA)'], ['budgets', 'Cost & mass budgets'], ['matrix/logical_components/parts', 'Logical × parts'], ['matrix/functions/parts', 'Functions × parts']],
  'System analysis': [['form/cda', 'Critical design attributes', 'cdas'], ['form/trl', 'Technology readiness'], ['dfx', 'Design for X'], ['trades', 'Trade studies'], ['form/dfmea', 'DFMEA', 'fmea'], ['collection/unassessed', 'Unassessed candidates', 'unassessed'], ['form/hazards', 'Hazard register'], ['form/fta', 'Fault trees'], ['form/drbfm', 'DRBFM'], ['form/pugh', 'Trade matrices']],
  'Implementation': [['form/purchase_orders', 'Purchase orders', 'purchase_orders'], ['form/tooling', 'Tooling & PPAP', 'tooling'], ['form/procurement', 'Procurement plan', 'quotes'], ['form/avl', 'AVL / sourcing'], ['form/cost', 'Product cost roll-up']],
  'Integration': [['form/icd', 'Interface control'], ['matrix/logical_components/parts', 'Integration map']],
  'Verification': [['runs', 'Test results', 'test_runs'], ['form/dvpr', 'DVP&R'], ['form/vcrm', 'VCRM / RTM'], ['matrix/requirements/tests', 'Requirements × tests']],
  'Transition': [['form/work_orders', 'Work orders & yield', 'work_orders'], ['form/pfmea', 'PFMEA'], ['form/control_plan', 'Control plan'], ['form/ppm', 'Supplier PPM', 'inspections']],
  'Validation': [['matrix/needs/requirements', 'Needs validated'], ['collection/moes', 'Measures of effectiveness'], ['form/claims', 'Claims substantiation', 'claims'], ['form/markets', 'Market readiness']],
  'Operation': [['form/fracas', 'FRACAS']],
  'Maintenance': [['form/fracas', 'FRACAS'], ['collection/field_events', 'Field events']],
  'Disposal': [['search?q=disposal', 'Disposal requirements']],
  'Project planning': [['pdp', 'Development process'], ['form/staffing', 'Staffing plan'], ['board', 'Board'], ['timeline', 'Timeline'], ['trend', 'Trend'], ['teams', 'Lifecycle & gates']],
  'Project assessment and control': [['analytics', 'Analytics & maturity'], ['indicators', 'Leading indicators'], ['teams', 'Teams & handoffs'], ['form/handoffs', 'Handoffs board']],
  // team workspaces are added dynamically from project.teams
  'Decision management': [['trades', 'Trade studies'], ['collection/arch_decisions', 'Architecture decisions']],
  'Risk management': [['form/risks', 'Risk register']],
  'Configuration management': [['form/eco', 'Change orders (ECO)', 'change_orders'], ['history', 'History & baselines']],
  'Information management': [['tables', 'Tables (spreadsheets)', 'tables'], ['notes', 'Notes & specs', 'notes'], ['import', 'Import spreadsheet'], ['documents', 'Source documents'], ['docs', 'Design documentation'], ['sysml', 'SysML v2 text'], ['artifacts', 'Artifact library']],
  'Measurement': [['scorecard', 'Scorecard'], ['gaps', 'Open gaps']],
  'Quality assurance': [['form/capa', 'CAPA / 8D log', 'capa'], ['form/findings', 'Findings log'], ['inbox', 'Review inbox']],
}

export function Shell() {
  const { pid, project, tabs, closeTab, activeTab, drawer, setDrawer, setPalette, theme, setTheme } = useProject()
  const loc = useLocation(); const nav = useNavigate(); const [side, setSide] = useState(true)
  const crumbs = useMemo(() => crumbsFor(loc.pathname, pid), [loc.pathname, pid])
  return <div className={'shell' + (side ? '' : ' nosidebar') + (drawer ? ' drawer-open' : '')}>
    <header className="topbar">
      {!side && <button className="btn ghost sm" onClick={() => setSide(true)} title="Show sidebar"><PanelLeft size={16} /></button>}
      <div className="crumbs">{crumbs.map((c, i) => <React.Fragment key={i}>{i > 0 && <span>/</span>}{c.to ? <a href={c.to} onClick={e => { e.preventDefault(); nav(c.to!) }}>{c.label}</a> : <b>{c.label}</b>}</React.Fragment>)}</div>
      <div className="search" onClick={() => setPalette(true)}><Search size={15} /><span>Search elements, artifacts, actions…</span><kbd>⌘K</kbd></div>
      {project && <span className={'pill ' + (project.coverage.clean ? 'good' : 'warn')} onClick={() => nav(`/p/${pid}/gaps`)} style={{ cursor: 'pointer' }}>{project.coverage.clean ? 'trace clean' : `${Object.entries(project.coverage).filter(([k, v]) => k !== 'clean' && v).reduce((a, [, v]) => a + (v as number), 0)} gaps`}</span>}
      <BuildButton />
      <button className={'btn sm' + (drawer ? ' primary' : '')} onClick={() => setDrawer(!drawer)} title="Agent (⌘J)"><Sparkles size={15} />Agent</button>
      <button className="btn ghost sm" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title="Theme">{theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}</button>
      <button className="btn ghost sm" title="Help" onClick={() => window.open('https://github.com/balakrishnen/Launch#readme')}><HelpCircle size={16} /></button>
    </header>
    <aside className="sidebar">
      <div className="brand"><span className="mark">L</span><span style={{ cursor: 'pointer' }} onClick={() => nav('/')}>Launch</span><button className="btn ghost sm" style={{ marginLeft: 'auto' }} onClick={() => setSide(false)} title="Hide sidebar"><PanelLeft size={15} /></button></div>
      <Tree />
      <div className="user"><span className="av">{(project?.user || 'U')[0].toUpperCase()}</span><div><div className="nm">{project?.user?.split('@')[0] || 'you'}</div><div className="ws">{project?.meta?.name || pid}</div></div></div>
    </aside>
    <main className="main">
      {tabs.length > 0 && <div className="tabbar">{tabs.map(t => <div key={t.key} className={'tab' + (t.key === activeTab || loc.pathname === t.path ? ' active' : '')} onClick={() => nav(t.path)}>{t.stage && <span className="dot" style={{ background: stageColor(t.stage) }} />}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.title}</span><button className="x" onClick={e => { e.stopPropagation(); closeTab(t.key) }}><X size={12} /></button></div>)}</div>}
      <div className="content"><Outlet /></div>
    </main>
    <AgentDrawer />
    <Palette />
  </div>
}

function BuildButton() {
  const { pid, toast, refresh } = useProject(); const [busy, setBusy] = useState(false)
  const run = async () => { setBusy(true); try { await fetch(`/api/p/${pid}/build`, { method: 'POST' }).then(r => r.json()); toast('Artifacts rebuilt'); refresh() } catch (e: any) { toast(e.message) } finally { setBusy(false) } }
  return <button className="btn sm" onClick={run} disabled={busy}><Hammer size={14} />{busy ? 'Building…' : 'Build'}</button>
}

function crumbsFor(path: string, pid: string) {
  const parts = path.replace(`/p/${pid}`, '').split('/').filter(Boolean); const out = [{ label: 'Home', to: `/p/${pid}` }]
  if (parts[0] === 'element') out.push({ label: KIND_LABEL[parts[1]] || parts[1], to: `/p/${pid}/collection/${parts[1]}` }, { label: decodeURIComponent(parts[2] || ''), to: '' })
  else if (parts[0] === 'collection') out.push({ label: KIND_LABEL[parts[1]] || parts[1], to: '' })
  else if (parts[0] === 'form') out.push({ label: 'Artifacts', to: `/p/${pid}/artifacts` }, { label: FORMS.find(f => f.id === parts[1])?.title || parts[1], to: '' })
  else if (parts[0] === 'matrix') out.push({ label: 'Artifacts', to: `/p/${pid}/artifacts` }, { label: `Matrix ${KIND_LABEL[parts[1]] || parts[1]} × ${KIND_LABEL[parts[2]] || parts[2]}`, to: '' })
  else if (parts[0]) out.push({ label: parts[0][0].toUpperCase() + parts[0].slice(1).replace(/-/g, ' '), to: '' })
  return out
}

function Tree() {
  const { pid, project, patches } = useProject()
  const [open, setOpen] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem('tree2') || '{}') } catch { return {} } })
  useEffect(() => { try { localStorage.setItem('tree2', JSON.stringify(open)) } catch { } }, [open])
  const [myTeams, setMyTeams] = useState<string[]>([])
  useEffect(() => { fetch(`/api/p/${pid}/me/team`).then(r => r.json()).then(x => setMyTeams(x.teams || [])).catch(() => { }) }, [pid, project?.meta?.rev])
  if (!project) return null
  const isOpen = (k: string) => open[k] === true
  const staged = patches.filter(p => p.status === 'staged').length
  const Item = ({ to, label, n, icon, end, pill }: { to: string; label: string; n?: number; icon?: React.ReactNode; end?: boolean; pill?: string }) => <NavLink to={to} end={end} className={({ isActive }) => isActive ? 'active' : ''}>{icon}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>{pill && <span className="pill warn" style={{ marginLeft: 'auto' }}>{pill}</span>}{n !== undefined && !pill && <span className="n">{n}</span>}</NavLink>
  const Group = ({ k, label, color, n, children, small, current }: { k: string; label: string; color?: string; n?: number; children: React.ReactNode; small?: boolean; current?: boolean }) => <>
    <div className={'group' + (small ? ' small' : '') + (current ? ' current' : '')} title={current ? 'current life-cycle stage' : label} onClick={() => setOpen(o => ({ ...o, [k]: !isOpen(k) }))}><span className="sw" style={{ width: 9, height: 9, borderRadius: 3, background: color || 'var(--sx)' }} /><span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>{current && <span className="pill accent" style={{ fontSize: 10, padding: '0 6px' }}>now</span>}{n !== undefined && <span className="n">{n}</span>}<ChevronDown size={14} style={{ color: 'var(--ink-3)', transform: isOpen(k) ? 'none' : 'rotate(-90deg)', transition: 'transform .15s' }} /></div>
    {isOpen(k) && <div className="sub">{children}</div>}</>
    return <div className="tree">
    <Item to={`/p/${pid}`} end label="Home" icon={<Home size={17} />} />
    <Item to={`/p/${pid}/chat`} label="Conversations" icon={<Sparkles size={17} />} />
    {myTeams.map(t => <Item key={t} to={`/p/${pid}/team/${t}`} label={`My team · ${project.teams?.[t]?.name || t}`} icon={<Users size={17} />} />)}
    <Item to={`/p/${pid}/analytics`} label="Analytics" icon={<BarChart3 size={17} />} />
    <Item to={`/p/${pid}/artifacts`} label="Artifacts" icon={<Library size={17} />} />
    <Item to={`/p/${pid}/inbox`} label="Reviews" icon={<Inbox size={17} />} pill={staged ? String(staged) : undefined} />
    <Item to={`/p/${pid}/notifications`} label="Notifications" icon={<Bell size={17} />} />
    <Item to={`/p/${pid}/graph`} label="Graph" icon={<GitBranch size={17} />} />
    {/* Departments — fixed top level; the organization defines sub-units and teams. Each department tab holds its artifacts. */}
    <h4>Departments</h4>
    {['Engineering', 'Quality', 'Supply chain', 'Manufacturing', 'Service', 'Program', 'Go-to-market', 'Corporate'].map(d => <Item key={d} to={`/p/${pid}/dept/${encodeURIComponent(d)}`} label={d} icon={<Building2 size={15} />} />)}
    {/* Life cycle per INCOSE SE Handbook / ISO 15288: stage → technical process → artifacts */}
    <h4>Life cycle</h4>
    {LIFECYCLE.map(st => { const procs = project.processes.filter(p => p.stage === st); const n = procs.reduce((a, p) => a + p.kinds.reduce((b, k) => b + (project.counts[k] || 0), 0), 0)
      return <Group key={st} k={'lc:' + st} label={st} color={STAGE_COLOR[st]} n={n} current={project.stage === st}>
        {procs.map(p => <Group key={p.name} k={'pr:' + p.name} label={p.name} color={stageColor(p.name)} n={p.kinds.reduce((b, k) => b + (project.counts[k] || 0), 0) || undefined} small>
          {p.kinds.map(k => <Item key={k} to={`/p/${pid}/collection/${k}`} label={KIND_LABEL[k]} n={project.counts[k]} />)}
          {(EXTRA[p.name] || []).map(([to, label, nk]) => <Item key={to} to={`/p/${pid}/${to}`} label={label} n={nk ? (nk === 'fmea' ? project.fmea_counts.assessed : nk === 'unassessed' ? project.coverage.unassessed_candidates : project.counts[nk]) : undefined} />)}
        </Group>)}
      </Group> })}
    <h4>Technical management</h4>
    {project.management.map(p => <Group key={p.name} k={'mg:' + p.name} label={p.name} color={STAGE_COLOR.Management} n={p.kinds.reduce((b, k) => b + (project.counts[k] || 0), 0) || undefined} small>
      {p.kinds.filter(k => !['tables', 'notes', 'phases', 'deliverables', 'dfx_reviews', 'cad_models'].includes(k)).map(k => <Item key={k} to={`/p/${pid}/collection/${k}`} label={KIND_LABEL[k]} n={project.counts[k]} />)}
      {p.name === 'Project assessment and control' && Object.entries(project.teams || {}).map(([t, tv]: any) => <Item key={t} to={`/p/${pid}/team/${t}`} label={tv.name} />)}
      {(EXTRA[p.name] || []).map(([to, label, nk]) => <Item key={to} to={`/p/${pid}/${to}`} label={label} n={nk ? project.counts[nk] : undefined} pill={to === 'inbox' && staged ? String(staged) : undefined} />)}
    </Group>)}
    <div className="sep" />
    <Item to={`/p/${pid}/harness`} label="Agent harness" icon={<Hammer size={17} />} />
    <Item to={`/p/${pid}/documents`} label="Source documents" icon={<FolderOpen size={17} />} />
    <Item to={`/p/${pid}/integrations`} label="Integrations" icon={<Plug size={17} />} />
  </div>
}
