import React, { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Home, Library, GitBranch, Inbox, Plug, Sparkles, Search, Sun, Moon, ChevronDown, X, Hammer, ShieldCheck, PanelLeft, FileText, History, ListChecks, HelpCircle, Image, Code2, FolderOpen, Bell } from 'lucide-react'
import { useProject } from '../state'
import { FORMS, KIND_LABEL, STAGE_COLOR } from '../api'
import { AgentDrawer } from './Agent'
import { Palette } from './Palette'

const STAGES = ['1 Needs', '2 Requirements', '3 Logical architecture', '4 Physical architecture', '5 Analysis', '6 Verification']

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
      {tabs.length > 0 && <div className="tabbar">{tabs.map(t => <div key={t.key} className={'tab' + (t.key === activeTab || loc.pathname === t.path ? ' active' : '')} onClick={() => nav(t.path)}>{t.stage && <span className="dot" style={{ background: STAGE_COLOR[t.stage] || 'var(--sx)' }} />}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.title}</span><button className="x" onClick={e => { e.stopPropagation(); closeTab(t.key) }}><X size={12} /></button></div>)}</div>}
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
  if (!project) return null
  const byStage: Record<string, string[]> = {}; for (const [k, s] of Object.entries(project.stage_of)) (byStage[s] ??= []).push(k)
  const isOpen = (k: string) => open[k] === true
  const staged = patches.filter(p => p.status === 'staged').length
  const Item = ({ to, label, n, icon, end, pill }: { to: string; label: string; n?: number; icon?: React.ReactNode; end?: boolean; pill?: string }) => <NavLink to={to} end={end} className={({ isActive }) => isActive ? 'active' : ''}>{icon}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>{pill && <span className="pill warn" style={{ marginLeft: 'auto' }}>{pill}</span>}{n !== undefined && !pill && <span className="n">{n}</span>}</NavLink>
  const Group = ({ k, label, color, n, children }: { k: string; label: string; color?: string; n?: number; children: React.ReactNode }) => <>
    <div className="group" onClick={() => setOpen(o => ({ ...o, [k]: !isOpen(k) }))}><span className="sw" style={{ width: 9, height: 9, borderRadius: 3, background: color || 'var(--sx)' }} /><span>{label}</span>{n !== undefined && <span className="n">{n}</span>}<ChevronDown size={14} style={{ color: 'var(--ink-3)', transform: isOpen(k) ? 'none' : 'rotate(-90deg)', transition: 'transform .15s' }} /></div>
    {isOpen(k) && <div className="sub">{children}</div>}</>
  const stageN = (s: string) => (byStage[s] || []).reduce((a, k) => a + (project.counts[k] || 0), 0)
  return <div className="tree">
    <Item to={`/p/${pid}`} end label="Home" icon={<Home size={17} />} />
    <Item to={`/p/${pid}/artifacts`} label="Artifacts" icon={<Library size={17} />} />
    <Item to={`/p/${pid}/inbox`} label="Reviews" icon={<Inbox size={17} />} pill={staged ? String(staged) : undefined} />
    <Item to={`/p/${pid}/notifications`} label="Notifications" icon={<Bell size={17} />} />
    <Item to={`/p/${pid}/graph`} label="Graph" icon={<GitBranch size={17} />} />
    <h4>Digital thread</h4>
    {STAGES.map(s => <Group key={s} k={s} label={s.replace(/^\d /, '')} color={STAGE_COLOR[s]} n={stageN(s)}>{(byStage[s] || []).map(k => <Item key={k} to={`/p/${pid}/collection/${k}`} label={KIND_LABEL[k]} n={project.counts[k]} />)}</Group>)}
    <h4>Analysis</h4>
    <Group k="risk" label="Risk" color={STAGE_COLOR['Risk (derived)']} n={project.fmea_counts.assessed}>
      <Item to={`/p/${pid}/form/dfmea`} label="DFMEA" /><Item to={`/p/${pid}/collection/unassessed`} label="Unassessed candidates" n={project.coverage.unassessed_candidates} /><Item to={`/p/${pid}/form/hazards`} label="Hazard register" /><Item to={`/p/${pid}/form/fta`} label="Fault trees" /><Item to={`/p/${pid}/form/drbfm`} label="DRBFM" />
    </Group>
    <Group k="arch" label="Architecture" color={STAGE_COLOR['4 Physical architecture']}>
      <Item to={`/p/${pid}/form/n2`} label="N² — physical" /><Item to={`/p/${pid}/form/n2l`} label="N² — logical" /><Item to={`/p/${pid}/form/icd`} label="ICD index" /><Item to={`/p/${pid}/form/pugh`} label="Trade matrices" /><Item to={`/p/${pid}/matrix/requirements/functions`} label="Dependency matrices" />
    </Group>
    <Group k="ver" label="Verification" color={STAGE_COLOR['6 Verification']} n={project.counts.tests}>
      <Item to={`/p/${pid}/form/dvpr`} label="DVP&R" /><Item to={`/p/${pid}/form/vcrm`} label="VCRM / RTM" /><Item to={`/p/${pid}/form/reqspec`} label="Requirements spec" /><Item to={`/p/${pid}/collection/certification_plan`} label="Certification plan" />
    </Group>
    <h4>Teams & program</h4>
    <Group k="program" label="Program" color={STAGE_COLOR['Program']} n={(project.counts.work_items || 0) + (project.counts.findings || 0)}>
      <Item to={`/p/${pid}/teams`} label="Teams & handoffs" /><Item to={`/p/${pid}/form/work_items`} label="Work items" n={project.counts.work_items} /><Item to={`/p/${pid}/form/findings`} label="Findings" n={project.counts.findings} /><Item to={`/p/${pid}/form/risks`} label="Program risks" n={project.counts.risks} /><Item to={`/p/${pid}/collection/reviews`} label="Design reviews" n={project.counts.reviews} /><Item to={`/p/${pid}/collection/gates`} label="Gates" n={project.counts.gates} />
    </Group>
    <Group k="mfg" label="Manufacturing" color={STAGE_COLOR['Manufacturing']} n={project.counts.process_steps}>
      <Item to={`/p/${pid}/collection/process_steps`} label="Process flow" n={project.counts.process_steps} /><Item to={`/p/${pid}/form/pfmea`} label="PFMEA" /><Item to={`/p/${pid}/form/control_plan`} label="Control plan" />
    </Group>
    <Group k="sc" label="Supply chain" color={STAGE_COLOR['Supply chain']} n={project.counts.suppliers}>
      <Item to={`/p/${pid}/form/avl`} label="AVL / sourcing" /><Item to={`/p/${pid}/collection/suppliers`} label="Suppliers" n={project.counts.suppliers} /><Item to={`/p/${pid}/budgets`} label="Cost & mass budgets" />
    </Group>
    <Group k="ops" label="Operations" color={STAGE_COLOR['Operations']} n={project.counts.field_events}>
      <Item to={`/p/${pid}/form/fracas`} label="FRACAS" n={project.counts.field_events} />
    </Group>
    <h4>Quality</h4>
    <Item to={`/p/${pid}/scorecard`} label="Scorecard" icon={<ShieldCheck size={17} />} />
    <Item to={`/p/${pid}/gaps`} label="Open gaps" icon={<ListChecks size={17} />} n={Object.entries(project.coverage).filter(([k, v]) => k !== 'clean' && v).length} />
    <h4>Outputs</h4>
    <Item to={`/p/${pid}/views`} label="Diagrams" icon={<Image size={17} />} /><Item to={`/p/${pid}/docs`} label="Design documentation" icon={<FileText size={17} />} /><Item to={`/p/${pid}/sysml`} label="SysML v2 text" icon={<Code2 size={17} />} /><Item to={`/p/${pid}/history`} label="History & baselines" icon={<History size={17} />} />
    <div className="sep" />
    <Item to={`/p/${pid}/documents`} label="Source documents" icon={<FolderOpen size={17} />} />
    <Item to={`/p/${pid}/integrations`} label="Integrations" icon={<Plug size={17} />} />
  </div>
}
