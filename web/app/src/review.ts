// Review build: serve the API from a frozen data.json (no backend). Enabled when VITE_REVIEW=1.
export function installReviewShim(data: Record<string, any>) {
  const real = window.fetch.bind(window)
  const dgCache: Record<string, Promise<Record<string, any>>> = {}
  const diagrams = (pid: string) => dgCache[pid] ??= real(`diagrams_${pid}.json`).then(r => r.ok ? r.json() : {}).catch(() => ({}))
  window.fetch = async (input: any, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.url
    if (!url.startsWith('/api')) return real(input, init)
    const json = (b: any, status = 200) => new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })
    if (url === '/api/me') return json({ user: 'reviewer', single: false, invite_required: false })
    if (url === '/api/projects') return json(data.list || [])
    if (url === '/api/examples') return json(data.examples || [])
    if (url === '/api/org') return json(data.org || {})
    if (url === '/api/roadmap') return json(data.roadmap || { items: [], horizons: [], statuses: [], areas: [] })
    if (url === '/api/org/templates') return json(data.org_templates || { templates: [], detail: {} })
    if (url === '/api/token') return json(null, 404)
    if (url.startsWith('/api/oslc/consumers')) return json([])
    if ((init?.method || 'GET') !== 'GET') return json({ detail: 'Review build: read-only snapshot. In the app this would stage a patch for approval.' }, 400)
    const mm = url.match(/^\/api\/p\/([^/]+)(.*)$/); if (!mm) return json({ detail: 'not in review snapshot' }, 404)
    const pid = mm[1], p = mm[2]; const pd = (data.projects || {})[pid]; if (!pd) return json({ detail: 'project not in review snapshot: ' + pid }, 404)
    if (p.startsWith('/search?q=')) { const q = decodeURIComponent(p.slice(10)).toLowerCase(); const hits: any[] = []; for (const n of pd['/graph'].nodes) { if (n.kind === 'fmea') continue; const row = (pd['/collection/' + n.kind] || []).find((r: any) => r.id === n.id); if ((n.id + ' ' + JSON.stringify(row || n)).toLowerCase().includes(q)) hits.push({ kind: n.kind, id: n.id, name: n.name }) } return json(hits.slice(0, 60)) }
    if (p === '/history') return json({ supported: false, note: 'History needs the database store; not in the review snapshot.' })
    { const mm2 = p.match(/^\/cad\/([^/?]+)\/mesh/); if (mm2) { const r = await real(`mesh_${pid}_${decodeURIComponent(mm2[1])}.json`); return r.ok ? r : json({ detail: 'mesh not in snapshot' }, 404) } }
    { const base = p.split('?')[0]; if (base.startsWith('/diagram/')) { const dg = await diagrams(pid); if (dg[base]) return json(dg[base]); if (pd[base]) return json(pd[base]); return json({ detail: 'This diagram is not in the review snapshot (it is rendered live in the app).' }, 404) } }
    if (p in pd && pd[p] !== null) return json(pd[p])
    if (p.startsWith('/events')) return new Response('', { status: 204 })
    return json({ detail: 'not in review snapshot: ' + p }, 404)
  }
  // SSE is not available: EventSource no-op
  ;(window as any).EventSource = class { addEventListener() { } close() { } onerror: any = null }
}
