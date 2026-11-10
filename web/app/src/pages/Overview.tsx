import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '../state'
import { P, KIND_LABEL, STAGE_COLOR, FORMS } from '../api'
import { Bar, IdLink } from '../components/common'
import { PatchCard } from '../components/Agent'

export function Overview() {
  const { pid, project, patches, send } = useProject(); const nav = useNavigate()
  const [sc, setSc] = useState<any>(null); const [gaps, setGaps] = useState<any[]>([]); const [art, setArt] = useState<any>(null)
  useEffect(() => { const p = P(pid); p.get('/scorecard').then(setSc).catch(() => { }); p.get('/collection/gaps').then(setGaps).catch(() => { }); p.get('/artifacts').then(setArt).catch(() => { }) }, [pid, project?.counts])
  if (!project) return null
  const stages: Record<string, string[]> = {}; for (const [k, s] of Object.entries(project.stage_of)) (stages[s] ??= []).push(k)
  const staged = patches.filter(p => p.status === 'staged')
  const total = Object.values(project.counts).reduce((a, b) => a + b, 0)
  return <div className="stack" style={{ gap: 16 }}>
    <div className="row between"><div><h1>{project.meta.name}</h1><div className="muted">{project.meta.description} · {project.meta.method || 'OOSEM'}{project.meta.rev ? ` · rev ${project.meta.rev}` : ''}</div></div>
      <div className="row"><button className="btn" onClick={() => nav(`/p/${pid}/artifacts`)}>Artifact library</button><button className="btn primary" onClick={() => send('Look at the scorecard and open gaps, pick the highest-leverage work, and stage patches')}>Ask the agent what to do next</button></div></div>
    <div className="grid3" style={{ gridTemplateColumns: "minmax(260px,1.1fr) minmax(360px,2fr) minmax(220px,1fr)" }}>
      <div className="card"><div className="row between"><h4>Scorecard</h4>{sc && <span className={'pill ' + (sc.grade <= 'B' ? 'good' : 'warn')}>{sc.grade} · {sc.overall}</span>}</div>
        {sc ? <div className="stack" style={{ gap: 8 }}>{Object.entries(sc.dimensions).slice(0, 5).map(([k, v]: any) => <div key={k}><div className="row between small"><span>{k.replace(/_/g, ' ')}</span><b>{v}</b></div><Bar v={v} /></div>)}<a href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/scorecard`) }} className="small">all dimensions →</a></div> : <span className="muted">…</span>}</div>
      <div className="card"><div className="row between"><h4>Model</h4><span className="pill">{total} elements</span></div>
        <div className="stack" style={{ gap: 4 }}>{Object.entries(stages).filter(([s]) => s !== 'Risk (derived)').map(([s, ks]) => <div key={s} className="small" style={{ display: 'grid', gridTemplateColumns: '12px 170px 1fr', gap: 6, alignItems: 'baseline' }}><span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: STAGE_COLOR[s] }} /><span style={{ color: STAGE_COLOR[s], fontWeight: 500 }}>{s}</span><span className="muted">{ks.map(k => `${project.counts[k]} ${KIND_LABEL[k].toLowerCase()}`).join(' · ')}</span></div>)}
          <div className="small" style={{ display: 'grid', gridTemplateColumns: '12px 170px 1fr', gap: 6, alignItems: 'baseline' }}><span className="sw" style={{ width: 8, height: 8, borderRadius: 2, background: STAGE_COLOR['Risk (derived)'] }} /><span style={{ color: STAGE_COLOR['Risk (derived)'], fontWeight: 500 }}>Risk (derived)</span><span className="muted">{project.fmea_counts.assessed} assessed · {project.fmea_counts.high_ap} High AP · {project.fmea_counts.screened} screened</span></div></div></div>
      <div className="card"><div className="row between"><h4>Review inbox</h4><span className={'pill ' + (staged.length ? 'warn' : '')}>{staged.length} staged</span></div>
        {staged.length ? <div className="stack">{staged.slice(0, 3).map(p => <div key={p.id} className="small"><IdLink id={p.id} /> <span className="muted">{p.author}</span><br />{p.rationale.slice(0, 90)}</div>)}<a href="#" className="small" onClick={e => { e.preventDefault(); nav(`/p/${pid}/inbox`) }}>open inbox →</a></div> : <span className="muted small">Nothing waiting for review.</span>}</div>
    </div>
    <div className="grid2">
      <div className="card"><div className="row between"><h4>Open gaps</h4><span className={'pill ' + (gaps.length ? 'warn' : 'good')}>{gaps.length}</span></div>
        {gaps.length ? <div className="stack" style={{ gap: 3 }}>{gaps.slice(0, 8).map((g, i) => <div key={i} className="small"><span className="muted">{g.gap.replace(/_/g, ' ')}</span> <IdLink id={String(g.item)} /></div>)}<div className="row" style={{ marginTop: 6 }}><button className="btn sm" onClick={() => send('Close the open trace gaps in order of leverage, in reviewable patches; stop when a human decision is needed')}>Ask the agent to close them</button><a className="small" href="#" onClick={e => { e.preventDefault(); nav(`/p/${pid}/gaps`) }}>all gaps →</a></div></div> : <span className="muted small">Trace is clean.</span>}</div>
      <div className="card"><div className="row between"><h4>Artifacts</h4><span className="pill">{FORMS.length + 8 + (art?.views?.length || 0) + (art?.sysml?.length || 0) + (art?.docs?.length ? 1 : 0)}</span></div>
        <div className="row" style={{ gap: 6 }}>{FORMS.map(f => <button key={f.id} className="chip" onClick={() => nav(`/p/${pid}/form/${f.id}`)}><span className="sw" style={{ width: 7, height: 7, borderRadius: 2, background: STAGE_COLOR[f.stage] }} />{f.title}</button>)}
          <button className="chip" onClick={() => nav(`/p/${pid}/views`)}>Diagrams {art?.views?.length || 0}</button><button className="chip" onClick={() => nav(`/p/${pid}/docs`)}>Design documentation</button><button className="chip" onClick={() => nav(`/p/${pid}/sysml`)}>SysML v2</button></div></div>
    </div>
    {staged.length > 0 && <div><h4 style={{ margin: '4px 0 8px' }}>Waiting for your review</h4>{staged.slice(0, 2).map(p => <PatchCard key={p.id} p={p} compact />)}</div>}
  </div>
}
