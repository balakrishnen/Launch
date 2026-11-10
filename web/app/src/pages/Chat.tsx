// Conversations — Claude for physical-product engineers. A project has many threads; each is an agent session grounded in the
// same model graph. Left: threads. Middle: the conversation with patch cards, tool activity and permissions. Every message
// carries what the engineer is looking at, so "this" means this.
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Square, Send, Trash2, MessageSquare } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'
import { Event } from '../components/Agent'

export function ChatPage() {
  const { tid } = useParams(); const { pid, project, events, busy, send, interrupt, thread, setThread, threads, refreshThreads, toast, setDrawer } = useProject(); const nav = useNavigate()
  useEffect(() => { setDrawer(false) }, [])
  const [text, setText] = useState(''); const [hist, setHist] = useState<any[]>([]); const log = useRef<HTMLDivElement>(null)
  useEffect(() => { if (tid && tid !== thread) setThread(tid); if (!tid && thread) nav(`/p/${pid}/chat/${thread}`, { replace: true }) }, [tid])
  useEffect(() => { if (!thread) { setHist([]); return } P(pid).get('/threads/' + thread).then(t => setHist(t.events)).catch(() => setHist([])) }, [pid, thread])
  const live = events.filter(e => e.thread === thread && e.ts > (hist[hist.length - 1]?.ts || 0))
  const all = [...hist, ...live]
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight }) }, [all.length])
  // ids inside rendered markdown → element pages
  useEffect(() => { const h = (e: MouseEvent) => { const a = (e.target as HTMLElement).closest('a.id[data-id]') as HTMLElement | null; if (a && log.current?.contains(a)) { e.preventDefault(); const id = a.dataset.id!; fetch(`/api/p/${pid}/search?q=${encodeURIComponent(id)}`).then(r => r.json()).then((hits: any[]) => { const h = hits.find(x => x.id === id); if (h) nav(`/p/${pid}/element/${h.kind}/${encodeURIComponent(id)}`) }) } }; document.addEventListener('click', h); return () => document.removeEventListener('click', h) }, [pid])
  const submit = async () => { const t = text.trim(); if (!t) return; setText(''); const id = await send(t, undefined, { thread }); if (id && id !== thread) nav(`/p/${pid}/chat/${id}`) }
  const newThread = () => { setThread(null); setHist([]); nav(`/p/${pid}/chat`) }
  const del = async (id: string) => { await P(pid).del('/threads/' + id); refreshThreads(); if (id === thread) newThread(); toast('Deleted') }
  const starters = ['What is blocking the next gate, and what should we do first?', 'Which requirements have no test, and propose the tests', 'Review the architecture for single points of failure', 'What changed since the last baseline and what does it affect?']
  return <div className="chatpage">
    <aside className="threads">
      <button className="btn primary" style={{ width: '100%', justifyContent: 'center' }} onClick={newThread}><Plus size={14} />New conversation</button>
      <div className="stack" style={{ gap: 2, marginTop: 10 }}>{threads.map(t => <div key={t.id} className={'th' + (t.id === thread ? ' active' : '')} onClick={() => { setThread(t.id); nav(`/p/${pid}/chat/${t.id}`) }}><div className="row between"><span className="t">{t.title}</span>{t.busy && <span className="spinner" />}</div><div className="d">{t.last || '—'}</div><div className="row between small muted"><span>{new Date(t.updated * 1000).toLocaleDateString()} · {t.n} msgs</span><button className="btn ghost sm" onClick={e => { e.stopPropagation(); del(t.id) }} title="delete"><Trash2 size={12} /></button></div></div>)}
        {!threads.length && <div className="muted small" style={{ padding: 8 }}>No conversations yet.</div>}</div>
    </aside>
    <section className="conv">
      <div className="log" ref={log}>
        {!thread && <div className="hero" style={{ margin: '8vh auto 0', maxWidth: 720 }}><div className="hi"><MessageSquare size={18} /></div><h1>Ask {project?.meta?.name || 'the project'}</h1><div className="muted" style={{ marginBottom: 14 }}>Everything is answered from the model graph — needs, requirements, architecture, failure modes, tests, gates — and every change comes back as a patch you approve.</div>
          <div className="sugg" style={{ gridTemplateColumns: '1fr 1fr' }}>{starters.map(q => <button key={q} onClick={() => { setText(q); }}><span className="t">{q}</span></button>)}</div></div>}
        {all.map((ev, i) => <Event key={i} ev={ev} />)}
      </div>
      <footer>
        <div className="prompt" style={{ margin: 0 }}><div className="wrap"><textarea value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }} placeholder={thread ? 'Reply… (Enter to send, Shift+Enter for a new line)' : 'Ask anything about this product, or tell the agents what to build…'} rows={2} />
          {busy ? <button className="btn go" onClick={interrupt} title="Stop" style={{ padding: 8 }}><Square size={14} /></button> : <button className="btn primary go" onClick={submit} style={{ padding: 8 }}><Send size={14} /></button>}</div></div>
      </footer>
    </section>
  </div>
}
