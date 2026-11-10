import React, { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, GitBranch, Table2, Library, Inbox, Plug, Sparkles, Search, Sun, Moon, ChevronDown, X, Hammer, ShieldCheck, Home } from 'lucide-react'
import { useProject } from '../state'
import { FORMS, KIND_LABEL, STAGE_COLOR } from '../api'
import { AgentDrawer } from './Agent'
import { Palette } from './Palette'

const STAGES = ['1 Needs', '2 Requirements', '3 Logical architecture', '4 Physical architecture', '5 Analysis', '6 Verification']

export function Shell() {
  const { pid, project, tabs, closeTab, activeTab, drawer, setDrawer, setPalette, patches, theme, setTheme } = useProject()
  const loc = useLocation(); const nav = useNavigate(); const [side, setSide] = useState(true)
  const staged = patches.filter(p => p.status === 'staged').length
  const crumbs = useMemo(() => crumbsFor(loc.pathname, pid), [loc.pathname, pid])
  const rail = [
    { to: `/p/${pid}`, icon: <Home size={18} />, label: 'Overview', end: true },
    { to: `/p/${pid}/artifacts`, icon: <Library size={18} />, label: 'Artifact library' },
    { to: `/p/${pid}/graph`, icon: <GitBranch size={18} />, label: 'Graph' },
    { to: `/p/${pid}/form/dfmea`, icon: <Table2 size={18} />, label: 'DFMEA' },
    { to: `/p/${pid}/scorecard`, icon: <ShieldCheck size={18} />, label: 'Scorecard' },
    { to: `/p/${pid}/inbox`, icon: <Inbox size={18} />, label: 'Review inbox', badge: staged },
    { to: `/p/${pid}/integrations`, icon: <Plug size={18} />, label: 'Integrations' },
  ]
  return <div className={'shell' + (side ? '' : ' nosidebar') + (drawer ? ' drawer-open' : '')}>
    <nav className="rail">
      <div className="logo" title="Launch" onClick={() => nav('/')}>L</div>
      {rail.map(r => <NavLink key={r.to} to={r.to} end={r.end} className={({ isActive }) => 'railbtn' + (isActive ? ' active' : '')}>{r.icon}{r.badge ? <span className="badge">{r.badge}</span> : null}<span className="tip">{r.label}</span></NavLink>)}
      <div style={{ flex: 1 }} />
      <button className={'railbtn' + (drawer ? ' active' : '')} onClick={() => setDrawer(!drawer)} title="Agent (⌘J)"><Sparkles size={18} /><span className="tip">Agent · ⌘J</span></button>
      <button className="railbtn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}<span className="tip">Theme</span></button>
    </nav>
    <header className="topbar">
      <button className="btn ghost sm" onClick={() => setSide(!side)} title="Toggle sidebar"><LayoutDashboard size={15} /></button>
      <div className="crumbs">{crumbs.map((c, i) => <React.Fragment key={i}>{i > 0 && <span>/</span>}{c.to ? <a href={c.to} onClick={e => { e.preventDefault(); nav(c.to!) }}>{c.label}</a> : <b>{c.label}</b>}</React.Fragment>)}</div>
      <div className="search" onClick={() => setPalette(true)}><Search size={14} /><span>Search elements, artifacts, actions…</span><kbd>⌘K</kbd></div>
      {project && <span className={'pill ' + (project.coverage.clean ? 'good' : 'warn')} onClick={() => nav(`/p/${pid}/gaps`)} style={{ cursor: 'pointer' }}>{project.coverage.clean ? 'trace clean' : `${Object.entries(project.coverage).filter(([k, v]) => k !== 'clean' && v).reduce((a, [, v]) => a + (v as number), 0)} gaps`}</span>}
      <BuildButton />
    </header>
    <aside className="sidebar"><Tree /></aside>
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
  return <button className="btn sm" onClick={run} disabled={busy}><Hammer size={14} />{busy ? 'Building…' : 'Build artifacts'}</button>
}

function crumbsFor(path: string, pid: string) {
  const parts = path.replace(`/p/${pid}`, '').split('/').filter(Boolean); const out = [{ label: 'Project', to: `/p/${pid}` }]
  if (parts[0] === 'element') out.push({ label: KIND_LABEL[parts[1]] || parts[1], to: `/p/${pid}/collection/${parts[1]}` }, { label: decodeURIComponent(parts[2] || ''), to: '' })
  else if (parts[0] === 'collection') out.push({ label: KIND_LABEL[parts[1]] || parts[1], to: '' })
  else if (parts[0] === 'form') out.push({ label: 'Artifacts', to: `/p/${pid}/artifacts` }, { label: FORMS.find(f => f.id === parts[1])?.title || parts[1], to: '' })
  else if (parts[0] === 'matrix') out.push({ label: 'Artifacts', to: `/p/${pid}/artifacts` }, { label: `Matrix ${parts[1]} × ${parts[2]}`, to: '' })
  else if (parts[0]) out.push({ label: parts[0][0].toUpperCase() + parts[0].slice(1), to: '' })
  return out
}

function Tree() {
  const { pid, project } = useProject()
  const [open, setOpen] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem('tree') || '{}') } catch { return {} } })
  useEffect(() => { try { localStorage.setItem('tree', JSON.stringify(open)) } catch { } }, [open])
  if (!project) return null
  const byStage: Record<string, string[]> = {}; for (const [k, s] of Object.entries(project.stage_of)) (byStage[s] ??= []).push(k)
  const isOpen = (k: string) => open[k] !== false
  const Group = ({ k, label, color, children }: { k: string; label: string; color?: string; children: React.ReactNode }) => <>
    <div className={'group' + (isOpen(k) ? '' : ' closed')} onClick={() => setOpen(o => ({ ...o, [k]: !isOpen(k) }))} style={{ color }}><ChevronDown size={12} />{label}</div>
    {isOpen(k) && children}</>
  const Item = ({ to, label, n, sw }: { to: string; label: string; n?: number; sw?: string }) => <NavLink to={to} className={({ isActive }) => isActive ? 'active' : ''}>{sw && <span className="sw" style={{ background: sw }} />}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>{n !== undefined && <span className="n">{n}</span>}</NavLink>
  return <div className="tree">
    <Item to={`/p/${pid}`} label="Overview" />
    <Item to={`/p/${pid}/gaps`} label="Open gaps" n={Object.entries(project.coverage).filter(([k, v]) => k !== 'clean' && v).length} />
    <Item to={`/p/${pid}/documents`} label="Source documents" />
    <h4 style={{ marginTop: 14 }}>Digital thread</h4>
    {STAGES.map(s => <Group key={s} k={s} label={s} color={STAGE_COLOR[s]}>{(byStage[s] || []).map(k => <Item key={k} to={`/p/${pid}/collection/${k}`} label={KIND_LABEL[k]} n={project.counts[k]} />)}</Group>)}
    <h4 style={{ marginTop: 14 }}>Derived artifacts</h4>
    <Group k="risk" label="Risk" color={STAGE_COLOR['Risk (derived)']}>
      <Item to={`/p/${pid}/form/dfmea`} label="DFMEA (AIAG-VDA)" n={project.fmea_counts.assessed} />
      <Item to={`/p/${pid}/collection/unassessed`} label="Unassessed candidates" n={project.coverage.unassessed_candidates} />
      <Item to={`/p/${pid}/form/hazards`} label="Hazard register" />
      <Item to={`/p/${pid}/form/fta`} label="Fault trees" />
      <Item to={`/p/${pid}/form/drbfm`} label="DRBFM" />
    </Group>
    <Group k="ver" label="Verification" color={STAGE_COLOR['6 Verification']}>
      <Item to={`/p/${pid}/form/dvpr`} label="DVP&R" /><Item to={`/p/${pid}/form/vcrm`} label="VCRM / RTM" /><Item to={`/p/${pid}/form/reqspec`} label="Requirements spec" /><Item to={`/p/${pid}/collection/certification_plan`} label="Certification plan" />
    </Group>
    <Group k="arch" label="Architecture" color={STAGE_COLOR['4 Physical architecture']}>
      <Item to={`/p/${pid}/form/n2`} label="N² — physical" /><Item to={`/p/${pid}/form/n2l`} label="N² — logical" /><Item to={`/p/${pid}/form/icd`} label="ICD index" /><Item to={`/p/${pid}/form/pugh`} label="Trade matrices" /><Item to={`/p/${pid}/matrix/requirements/functions`} label="Dependency matrices" /><Item to={`/p/${pid}/budgets`} label="Budgets" />
    </Group>
    <Group k="out" label="Outputs">
      <Item to={`/p/${pid}/views`} label="Diagrams" /><Item to={`/p/${pid}/docs`} label="Design documentation" /><Item to={`/p/${pid}/sysml`} label="SysML v2 text" /><Item to={`/p/${pid}/history`} label="History & baselines" />
    </Group>
  </div>
}
