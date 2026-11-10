// Review build: serve the API from a frozen data.json (no backend). Enabled when VITE_REVIEW=1.
export function installReviewShim(data: Record<string, any>) {
  const real = window.fetch.bind(window)
  window.fetch = async (input: any, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.url
    if (!url.startsWith('/api')) return real(input, init)
    const json = (b: any, status = 200) => new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })
    if (url === '/api/me') return json({ user: 'reviewer', single: true })
    if (url === '/api/token') return json(null, 404)
    if (url.startsWith('/api/oslc/consumers')) return json([])
    if ((init?.method || 'GET') !== 'GET') return json({ detail: 'Review build: read-only snapshot. In the app this would stage a patch for approval.' }, 400)
    const p = url.replace(/^\/api\/p\/[^/]+/, '')
    if (p.startsWith('/search?q=')) { const q = decodeURIComponent(p.slice(10)).toLowerCase(); const hits: any[] = []; for (const n of data['/graph'].nodes) { if (n.kind === 'fmea') continue; const row = (data['/collection/' + n.kind] || []).find((r: any) => r.id === n.id); if ((n.id + ' ' + JSON.stringify(row || n)).toLowerCase().includes(q)) hits.push({ kind: n.kind, id: n.id, name: n.name }) } return json(hits.slice(0, 60)) }
    if (p === '/history') return json({ supported: false, note: 'History needs the database store; not in the review snapshot.' })
    if (p in data) return json(data[p])
    if (p.startsWith('/events')) return new Response('', { status: 204 })
    return json({ detail: 'not in review snapshot: ' + p }, 404)
  }
  // SSE is not available: EventSource no-op
  ;(window as any).EventSource = class { addEventListener() { } close() { } onerror: any = null }
}
