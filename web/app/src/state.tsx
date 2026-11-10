// Project context: project summary, live events (SSE), open tabs, agent drawer, toasts.
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, P, type Project, type PatchSummary } from './api'

export type Tab = { key: string; title: string; path: string; stage?: string }
export type Ev = { type: string; ts: number; [k: string]: any }

type Ctx = {
  pid: string; project: Project | null; refresh: () => Promise<void>
  events: Ev[]; busy: boolean; send: (text: string, role?: string) => Promise<void>; interrupt: () => void
  tabs: Tab[]; openTab: (t: Tab) => void; closeTab: (key: string) => void; activeTab: string | null
  drawer: boolean; setDrawer: (v: boolean) => void; palette: boolean; setPalette: (v: boolean) => void
  toast: (m: string) => void; patches: PatchSummary[]; refreshPatches: () => Promise<void>
  decide: (id: string, what: 'approve' | 'reject') => Promise<void>; answerPermission: (id: string, a: string) => Promise<void>
  theme: string; setTheme: (t: string) => void
}
const C = createContext<Ctx>(null as any)
export const useProject = () => useContext(C)

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { pid = 'default' } = useParams(); const nav = useNavigate(); const p = useMemo(() => P(pid), [pid])
  const [project, setProject] = useState<Project | null>(null)
  const [events, setEvents] = useState<Ev[]>([]); const [busy, setBusy] = useState(false)
  const [tabs, setTabs] = useState<Tab[]>(() => { try { return JSON.parse(localStorage.getItem('tabs:' + pid) || '[]') } catch { return [] } })
  const [activeTab, setActive] = useState<string | null>(null)
  const [drawer, setDrawer] = useState(() => { try { return localStorage.getItem('drawer') !== '0' } catch { return true } })
  const [palette, setPalette] = useState(false); const [msg, setMsg] = useState<string | null>(null)
  const [patches, setPatches] = useState<PatchSummary[]>([])
  const [theme, setThemeState] = useState(() => { try { return localStorage.getItem('theme') || 'light' } catch { return 'light' } })
  const esRef = useRef<EventSource | null>(null)

  const refresh = useCallback(async () => { try { setProject(await p.get('/project')) } catch { } }, [p])
  const refreshPatches = useCallback(async () => { try { setPatches(await p.get('/patches')) } catch { } }, [p])
  useEffect(() => { refresh(); refreshPatches() }, [refresh, refreshPatches])
  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); try { localStorage.setItem('theme', theme) } catch { } }, [theme])
  useEffect(() => { try { localStorage.setItem('tabs:' + pid, JSON.stringify(tabs.slice(-12))) } catch { } }, [tabs, pid])
  useEffect(() => { try { localStorage.setItem('drawer', drawer ? '1' : '0') } catch { } }, [drawer])

  useEffect(() => {
    let alive = true
    const connect = () => {
      const es = new EventSource(`/api/p/${pid}/events`); esRef.current = es
      es.addEventListener('ev', e => { if (!alive) return; const ev = JSON.parse((e as MessageEvent).data) as Ev
        setEvents(xs => [...xs.slice(-400), ev])
        if (ev.type === 'user') setBusy(true); if (ev.type === 'idle') setBusy(false)
        if (['model_changed', 'patch_staged', 'patch_applied', 'patch_rejected', 'built'].includes(ev.type)) { refresh(); refreshPatches() } })
      es.onerror = () => { es.close(); if (alive) setTimeout(connect, 2500) }
    }
    connect(); return () => { alive = false; esRef.current?.close() }
  }, [pid, refresh, refreshPatches])

  const toast = useCallback((m: string) => { setMsg(m); setTimeout(() => setMsg(null), 2600) }, [])
  const send = useCallback(async (text: string, role?: string) => { setDrawer(true); try { await p.post('/chat', { text, role }) } catch (e: any) { toast(e.message) } }, [p, toast])
  const interrupt = useCallback(() => { p.post('/interrupt') }, [p])
  const decide = useCallback(async (id: string, what: 'approve' | 'reject') => { try { await p.post(`/patches/${id}/${what}`); toast(what === 'approve' ? `Applied ${id}` : `Rejected ${id}`) } catch (e: any) { toast(e.message) } }, [p, toast])
  const answerPermission = useCallback(async (id: string, a: string) => { await p.post(`/permission/${id}`, { answer: a }) }, [p])
  const openTab = useCallback((t: Tab) => { setTabs(ts => ts.find(x => x.key === t.key) ? ts : [...ts, t].slice(-12)); setActive(t.key); nav(t.path) }, [nav])
  const closeTab = useCallback((key: string) => { setTabs(ts => { const i = ts.findIndex(x => x.key === key); const next = ts.filter(x => x.key !== key); if (activeTab === key) { const nb = next[Math.max(0, i - 1)]; if (nb) nav(nb.path); else nav(`/p/${pid}`) } return next }) }, [activeTab, nav, pid])
  const setTheme = useCallback((t: string) => setThemeState(t), [])

  useEffect(() => { const h = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(v => !v) } if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') { e.preventDefault(); setDrawer(v => !v) } }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h) }, [])

  const value: Ctx = { pid, project, refresh, events, busy, send, interrupt, tabs, openTab, closeTab, activeTab, drawer, setDrawer, palette, setPalette, toast, patches, refreshPatches, decide, answerPermission, theme, setTheme }
  return <C.Provider value={value}>{children}{msg && <div className="toast">{msg}</div>}</C.Provider>
}
export { api }
