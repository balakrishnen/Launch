// Agent drawer: chat, tool activity, permission cards, patch cards (diff + approve), triage cards. Slides over the main pane.
import React, { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import { Square, Send, X, Play } from 'lucide-react'
import { useProject, type Ev } from '../state'
import { Linkified, IdLink } from './common'
import type { PatchSummary } from '../api'

export function PatchCard({ p, compact }: { p: PatchSummary; compact?: boolean }) {
  const { decide, send } = useProject(); const [open, setOpen] = useState<Record<number, boolean>>({})
  const delta = Object.entries(p.coverage_delta || {})
  return <div className={'pcard ' + p.status}>
    <div className="row between"><b>Patch {p.id}</b><span className="muted small">{p.author} · {p.ops.length} changes · {p.status}</span></div>
    <div style={{ margin: '4px 0' }}><Linkified text={p.rationale} /></div>
    {p.sources?.length > 0 && <div className="muted small">sources: {p.sources.join(', ')}</div>}
    <div className="ops" style={{ margin: '6px 0' }}>{p.ops.slice(0, compact ? 6 : 200).map((o, i) => <React.Fragment key={i}>
      <div className={o.op} onClick={() => setOpen(s => ({ ...s, [i]: !s[i] }))}><span className="op">{o.op}</span><IdLink id={o.id} kind={o.kind} /><span className="muted">{o.kind} · {o.name}</span></div>
      {open[i] && <pre className="diff">{o.diff.split('\n').map((l, j) => <span key={j} className={l.startsWith('+') ? 'a' : l.startsWith('-') ? 'd' : ''}>{l + '\n'}</span>)}</pre>}</React.Fragment>)}
      {compact && p.ops.length > 6 && <div className="muted small">… {p.ops.length - 6} more</div>}</div>
    {p.errors?.length > 0 && <div className="small" style={{ color: 'var(--bad)' }}>{p.errors.join(' · ')}</div>}
    {p.warnings?.length > 0 && <div className="small muted">⚠ {p.warnings.join(' · ')}</div>}
    {delta.length > 0 && <div className="small muted">coverage if approved: {delta.map(([k, [a, b]]) => <b key={k} style={{ color: b < a ? 'var(--good)' : 'var(--bad)', marginRight: 8 }}>{k.replace(/_/g, ' ')} {a}→{b}</b>)}</div>}
    {p.status === 'staged' && <div className="row" style={{ marginTop: 8 }}><button className="btn good sm" onClick={() => decide(p.id, 'approve')}>Approve</button><button className="btn danger sm" onClick={() => decide(p.id, 'reject')}>Reject</button><button className="btn ghost sm" onClick={() => send(`Revise patch ${p.id}: `)}>Ask for changes</button></div>}
  </div>
}

function Event({ ev }: { ev: Ev }) {
  const { answerPermission, send, patches } = useProject(); const [answered, setAnswered] = useState<string | null>(null)
  switch (ev.type) {
    case 'user': return <div className="msg user"><Linkified text={ev.text} /></div>
    case 'assistant': return <div className="msg assistant" dangerouslySetInnerHTML={{ __html: linkHtml(marked.parse(ev.text) as string) }} />
    case 'tool': return <div className="tool">⚙ {ev.name} <span style={{ opacity: .7 }}>{ev.arg}</span></div>
    case 'tool_error': return <div className="tool err">✗ {ev.text}</div>
    case 'permission': return <div className="pcard perm"><b>The agent wants to run <code>{ev.tool}</code></b><pre className="diff" style={{ maxHeight: 110 }}>{ev.detail}</pre>{answered ? <span className="small muted">{answered}</span> : <div className="row">{[['allow', 'Allow', 'btn good sm'], ['always', 'Always this session', 'btn sm'], ['deny', 'Deny', 'btn danger sm']].map(([a, l, c]) => <button key={a} className={c} onClick={() => { answerPermission(ev.id, a); setAnswered(l) }}>{l}</button>)}</div>}</div>
    case 'patch_staged': { const live = patches.find(p => p.id === ev.patch?.id) || ev.patch; return <PatchCard p={live} compact /> }
    case 'patch_applied': return <div className="tool">✓ applied {ev.id}{ev.user ? ` by ${ev.user}` : ''}</div>
    case 'patch_rejected': return <div className="tool">✗ rejected {ev.id}</div>
    case 'result': return <div className="tool">· {ev.turns} turns · {ev.seconds}s{ev.cost ? ` · $${Number(ev.cost).toFixed(3)}` : ''}</div>
    case 'error': return <div className="msg" style={{ color: 'var(--bad)' }}>{ev.text}</div>
    case 'triage': { const d = Object.entries(ev.delta || {}); if (!d.length && !ev.gaps?.length) return null
      return <div className="pcard" style={{ borderColor: '#bfdbfe', background: 'var(--info-soft)' }}><b>Model changed — scorecard {ev.grade} · {ev.overall}</b>
        {d.length > 0 && <div className="small">{d.map(([k, [a, b]]: any) => <b key={k} style={{ color: b >= a ? 'var(--good)' : 'var(--bad)', marginRight: 8 }}>{k.replace(/_/g, ' ')} {a}→{b}</b>)}</div>}
        {ev.gaps?.length > 0 ? <><div className="small muted" style={{ marginTop: 4 }}>open: {ev.gaps.slice(0, 5).map((g: any, i: number) => <span key={i}>{g.gap.replace(/_/g, ' ')} <IdLink id={String(g.item)} />{i < 4 ? ' · ' : ''}</span>)}</div><div style={{ marginTop: 6 }}><button className="btn sm" onClick={() => send('Close the open gaps the watcher just listed, in reviewable patches')}>Ask the agent to close them</button></div></> : <div className="small muted">no open gaps</div>}</div> }
    default: return null
  }
}
function linkHtml(html: string) { return html.replace(/\b((?:STK|MOE|UC|SC|REG|LC|LI|ND|IF|TR|TD|AD|FM|FA|N|R|P|S|C|T|G)-[A-Za-z0-9_.-]+|F\d{2}[a-z]?)\b/g, m => `<a class="id" data-id="${m}">${m}</a>`) }

export function AgentDrawer() {
  const { drawer, setDrawer, events, busy, send, interrupt, project, pid } = useProject()
  const [text, setText] = useState(''); const log = useRef<HTMLDivElement>(null); const [auto, setAuto] = useState(false); const [menu, setMenu] = useState(false)
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight }) }, [events.length, drawer])
  useEffect(() => { if (project) setAuto(project.auto) }, [project?.auto])
  // delegate clicks on ids inside rendered markdown
  useEffect(() => { const h = (e: MouseEvent) => { const a = (e.target as HTMLElement).closest('a.id[data-id]') as HTMLElement | null; if (a && log.current?.contains(a)) { e.preventDefault(); const id = a.dataset.id!; fetch(`/api/p/${pid}/search?q=${encodeURIComponent(id)}`).then(r => r.json()).then(hits => { const h = hits.find((x: any) => x.id === id); if (h) window.dispatchEvent(new CustomEvent('open-element', { detail: h })) }) } }; document.addEventListener('click', h); return () => document.removeEventListener('click', h) }, [pid])
  const submit = () => { const t = text.trim(); if (!t) return; setText(''); send(t) }
  return <div className={'drawer' + (drawer ? ' open' : '')}>
    <header><b>Agent</b>{busy ? <span className="row small muted"><span className="spinner" /> working</span> : <span className="small muted">idle</span>}<div style={{ flex: 1 }} />
      <label className="small muted" style={{ display: 'flex', gap: 5, alignItems: 'center' }}><input type="checkbox" checked={auto} onChange={async e => { setAuto(e.target.checked); await fetch(`/api/p/${pid}/settings`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto: e.target.checked }) }) }} /> auto-approve</label>
      {busy && <button className="btn ghost sm" onClick={interrupt} title="Stop"><Square size={13} /></button>}<button className="btn ghost sm" onClick={() => setDrawer(false)}><X size={14} /></button></header>
    <div className="log" ref={log}>
      {events.length === 0 && <div className="empty small">Ask for anything: “Read the PRD and set up stakeholders and needs”, “Design the charger for a 2S pack”, “Assess all failure modes of F07”. The agent stages patches; you approve them here or in the Review inbox.</div>}
      {events.map((ev, i) => <Event key={i} ev={ev} />)}
    </div>
    <footer>
      <div className="row" style={{ alignItems: 'flex-end' }}><div className="rolemenu"><button className="btn sm" onClick={() => setMenu(m => !m)} title="Run a whole OOSEM stage"><Play size={13} />Stage</button>{menu && <div className="menu" onMouseLeave={() => setMenu(false)}>{project?.role_order.map(r => <button key={r} onClick={() => { setMenu(false); send('', r) }}>{project.roles[r]}</button>)}</div>}</div><textarea className="field" rows={2} value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit() }} placeholder="Tell the agent what to do… (⌘⏎ to send)" /><button className="btn primary" onClick={submit} disabled={busy}><Send size={14} /></button></div>
    </footer>
  </div>
}
