// Native CAD panel for a part: build123d code (editable), Build, measurements, checks against the thread, STEP download,
// and a 3D view of the mesh (three.js loaded from cdnjs on first use).
import { useEffect, useRef, useState } from 'react'
import { Box, Play, Sparkles, Download } from 'lucide-react'
import { useProject } from '../state'
import { P } from '../api'

export function CadPanel({ part }: { part: string }) {
  const { pid, project, patches, toast, send } = useProject()
  const [c, setC] = useState<any>(null); const [code, setCode] = useState(''); const [busy, setBusy] = useState(false); const [edit, setEdit] = useState(false); const [err, setErr] = useState('')
  const load = () => P(pid).get(`/cad/${encodeURIComponent(part)}`).then(x => { setC(x); setCode(x.code); setErr(x.error || '') }).catch(() => setC(null))
  useEffect(() => { load() }, [pid, part, patches.length, project?.meta?.rev])
  const build = async () => { setBusy(true); setErr(''); try { const r = await P(pid).post(`/cad/${encodeURIComponent(part)}/build`, { code }); if (!r.ok) { setErr(r.error); toast('Build failed — see the error') } else { toast(`Built — ${r.patch_id}`); setEdit(false) } } catch (e: any) { toast(e.message) } setBusy(false); load() }
  if (!c) return null
  const built = c.status && c.status.startsWith('built')
  return <div className="card" style={{ marginBottom: 14 }}>
    <div className="row between" style={{ flexWrap: 'wrap', gap: 8 }}><div><h4><Box size={14} style={{ verticalAlign: -2 }} /> Native CAD <span className={'pill ' + (c.status === 'built' ? 'good' : c.status === 'built-with-findings' ? 'warn' : c.status === 'error' ? 'bad' : '')}>{c.status === 'none' ? 'not modelled' : c.status}</span></h4><div className="muted small">build123d (OpenCascade) code kept in the thread; built into STEP/STL, measured and checked against budgets, interfaces and requirements.{c.built ? ` Built ${c.built} by ${c.by}.` : ''}</div></div>
      <div className="row"><button className="chip" onClick={() => send(`Model part ${part} in build123d: call cad_brief for ${part}, write the code (mm, density, features, mates for every mechanical interface), build it with cad_build, and iterate until every check passes`)}><Sparkles size={13} />ask the agent to model it</button><button className="btn sm" onClick={() => setEdit(e => !e)}>{edit ? 'Hide code' : 'Code'}</button><button className="btn sm primary" disabled={busy} onClick={build}><Play size={14} />{busy ? 'Building…' : 'Build'}</button></div></div>
    {edit && <textarea className="field mono" style={{ minHeight: 260, fontSize: 12.5, marginTop: 8 }} value={code} onChange={e => setCode(e.target.value)} spellCheck={false} />}
    {err && <pre className="diff" style={{ color: 'var(--bad)', marginTop: 8, whiteSpace: 'pre-wrap' }}>{err}</pre>}
    {built && <div className="grid2" style={{ marginTop: 10, gridTemplateColumns: '1fr 320px', alignItems: 'start' }}>
      <Viewer url={`/api/p/${pid}/cad/${encodeURIComponent(part)}/mesh?v=${c.built}`} />
      <div className="stack" style={{ gap: 8 }}>
        <div className="small"><b>Envelope</b> {c.bbox_mm?.map((x: number) => +x.toFixed(1)).join(' × ')} mm · <b>Volume</b> {Math.round(c.volume_mm3 / 1000)} cm³{c.mass_g != null ? <> · <b>Mass</b> {c.mass_g} g</> : null}</div>
        {c.features?.length > 0 && <div className="small"><b>Features</b>: {c.features.join(' · ')}</div>}
        <div><div className="small" style={{ fontWeight: 600, marginBottom: 4 }}>Checks against the thread</div>{c.checks?.length ? c.checks.map((k: any, i: number) => <div key={i} className="row small" style={{ gap: 6 }}><span style={{ color: k.ok ? 'var(--good)' : 'var(--bad)' }}>{k.ok ? '✓' : '✗'}</span><span>{k.check}</span><span className="muted">{k.measured} · {k.limit}</span></div>) : <span className="muted small">No budgets, envelope or mechanical interfaces on this part yet — set attrs.mass_budget_g / attrs.envelope_mm or model interfaces.</span>}</div>
        <div className="row" style={{ gap: 6 }}>{c.files?.step && <a className="btn sm" href={`/api/p/${pid}/file?path=cad/${c.files.step}`}><Download size={13} />STEP</a>}{c.files?.stl && <a className="btn sm" href={`/api/p/${pid}/file?path=cad/${c.files.stl}`}><Download size={13} />STL</a>}</div>
      </div></div>}
  </div>
}

async function loadThree(): Promise<any> { return await import('three') }   // bundled, no CDN dependency

function Viewer({ url }: { url: string }) {
  const ref = useRef<HTMLDivElement>(null); const [msg, setMsg] = useState('loading mesh…')
  useEffect(() => { let stop = false; let raf = 0; let renderer: any
    (async () => { try { const [THREE, mesh] = await Promise.all([loadThree(), fetch(url).then(r => { if (!r.ok) throw new Error('mesh not built'); return r.json() })]); if (stop || !ref.current) return
      const el = ref.current; const w = el.clientWidth, h = 340
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); renderer.setSize(w, h); renderer.setPixelRatio(Math.min(2, window.devicePixelRatio)); el.innerHTML = ''; el.appendChild(renderer.domElement)
      const scene = new THREE.Scene(); const cam = new THREE.PerspectiveCamera(35, w / h, 0.1, 100000)
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(mesh.v, 3)); geo.setIndex(mesh.i); geo.computeVertexNormals(); geo.computeBoundingSphere()
      const mat = new THREE.MeshStandardMaterial({ color: 0x8fa3c7, metalness: 0.2, roughness: 0.55, side: THREE.DoubleSide }); const obj = new THREE.Mesh(geo, mat); scene.add(obj)
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), new THREE.LineBasicMaterial({ color: 0x334155 })); scene.add(edges)
      scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.1)); const dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(1, 2, 3); scene.add(dl)
      const r = geo.boundingSphere.radius, c = geo.boundingSphere.center; const grid = new THREE.GridHelper(r * 4, 20, 0xcbd5e1, 0xe2e8f0); grid.position.set(c.x, c.y - r, c.z); grid.rotation.x = 0; scene.add(grid)
      let theta = 0.8, phi = 1.0, dist = r * 3.2; let drag = false, lx = 0, ly = 0
      const place = () => { cam.position.set(c.x + dist * Math.sin(phi) * Math.cos(theta), c.y + dist * Math.cos(phi), c.z + dist * Math.sin(phi) * Math.sin(theta)); cam.lookAt(c); renderer.render(scene, cam) }
      el.onmousedown = e => { drag = true; lx = e.clientX; ly = e.clientY }; window.addEventListener('mouseup', () => drag = false)
      el.onmousemove = e => { if (!drag) return; theta += (e.clientX - lx) * 0.01; phi = Math.max(0.1, Math.min(3.0, phi - (e.clientY - ly) * 0.01)); lx = e.clientX; ly = e.clientY; place() }
      el.onwheel = e => { e.preventDefault(); dist = Math.max(r * 1.2, Math.min(r * 12, dist * (1 + e.deltaY * 0.001))); place() }
      place(); setMsg('') } catch (e: any) { setMsg(e.message) } })()
    return () => { stop = true; cancelAnimationFrame(raf); if (renderer) renderer.dispose?.() } }, [url])
  return <div><div ref={ref} className="viewer" style={{ height: 340 }} />{msg && <div className="muted small">{msg}</div>}<div className="muted small">drag to orbit · wheel to zoom · Z up</div></div>
}
