// API client for the Launch backend. All project routes are under /api/p/{pid}.
export type Kind = string
export const KIND_LABEL: Record<string, string> = {
  stakeholders: 'Stakeholders', needs: 'Needs', moes: 'Measures of effectiveness', actors: 'Actors', use_cases: 'Use cases', scenarios: 'Scenarios',
  regulations: 'Regulations', requirements: 'Requirements', functions: 'Functions', logical_components: 'Logical components', logical_interfaces: 'Logical interfaces',
  parts: 'Parts', nodes: 'Physical nodes', interfaces: 'Interfaces', states: 'States', transitions: 'Transitions', arch_decisions: 'Architecture decisions',
  trades: 'Trade studies', constraints: 'Constraints', tests: 'Tests', gates: 'Gates', fm_assessments: 'FMEA assessments', fmea: 'Failure modes',
}
export const STAGE_COLOR: Record<string, string> = {
  '1 Needs': 'var(--s1)', '2 Requirements': 'var(--s2)', '3 Logical architecture': 'var(--s3)', '4 Physical architecture': 'var(--s4)',
  '5 Analysis': 'var(--s5)', '6 Verification': 'var(--s6)', 'Risk (derived)': 'var(--sr)',
}
export const FORMS: { id: string; title: string; std: string; stage: string; group: string }[] = [
  { id: 'reqspec', title: 'Requirements specification', std: 'ISO/IEC/IEEE 29148', stage: '2 Requirements', group: 'Requirements' },
  { id: 'vcrm', title: 'VCRM / RTM', std: 'ISO/IEC/IEEE 29148', stage: '6 Verification', group: 'Verification' },
  { id: 'dvpr', title: 'DVP&R', std: 'AIAG APQP', stage: '6 Verification', group: 'Verification' },
  { id: 'dfmea', title: 'DFMEA', std: 'AIAG & VDA 2019', stage: 'Risk (derived)', group: 'Risk' },
  { id: 'hazards', title: 'Hazard register', std: 'safety decisions, S ≥ 9', stage: 'Risk (derived)', group: 'Risk' },
  { id: 'fta', title: 'Fault trees', std: 'IEC 61025 (tabular)', stage: 'Risk (derived)', group: 'Risk' },
  { id: 'drbfm', title: 'DRBFM', std: 'Toyota GD³', stage: 'Risk (derived)', group: 'Risk' },
  { id: 'n2', title: 'N² — physical', std: 'NASA SE Handbook', stage: '4 Physical architecture', group: 'Architecture' },
  { id: 'n2l', title: 'N² — logical', std: 'NASA SE Handbook', stage: '3 Logical architecture', group: 'Architecture' },
  { id: 'icd', title: 'ICD index', std: 'MIL-STD-961 outline', stage: '4 Physical architecture', group: 'Architecture' },
  { id: 'pugh', title: 'Trade matrices', std: 'Pugh / weighted', stage: '5 Analysis', group: 'Analysis' },
]
export const MATRIX_PAIRS: [string, string][] = [['requirements', 'functions'], ['functions', 'parts'], ['requirements', 'tests'], ['needs', 'requirements'], ['regulations', 'requirements'], ['logical_components', 'parts'], ['functions', 'logical_components'], ['constraints', 'tests']]

export class ApiError extends Error { status: number; constructor(s: number, m: string) { super(m); this.status = s } }
async function handle(r: Response) {
  if (!r.ok) { let m = r.statusText; try { const j = await r.json(); m = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j) } catch { } throw new ApiError(r.status, m) }
  return r.json()
}
export const api = {
  get: (p: string) => fetch('/api' + p).then(handle),
  post: (p: string, body?: unknown) => fetch('/api' + p, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}) }).then(handle),
  del: (p: string) => fetch('/api' + p, { method: 'DELETE' }).then(handle),
  upload: (p: string, file: File) => { const fd = new FormData(); fd.append('file', file); return fetch('/api' + p, { method: 'POST', body: fd }).then(handle) },
}
export const P = (pid: string) => ({
  get: (p: string) => api.get(`/p/${pid}${p}`),
  post: (p: string, body?: unknown) => api.post(`/p/${pid}${p}`, body),
  upload: (p: string, f: File) => api.upload(`/p/${pid}${p}`, f),
  out: (path: string) => (import.meta.env.VITE_REVIEW === '1' ? `out/${path}` : `/p/${pid}/out/${path}`),
})

export const ID_RE = /\b((?:STK|MOE|UC|SC|REG|LC|LI|ND|IF|TR|TD|AD|FM|FA|HZ|FT|N|R|P|S|C|T|G)-[A-Za-z0-9_.-]+|F\d{2}[a-z]?)\b/g

export type Project = { id: string; user: string; meta: Record<string, any>; counts: Record<string, number>; stage_of: Record<string, string>; fmea_counts: Record<string, number>; coverage: Record<string, any>; staged: number; busy: boolean; auto: boolean; toolchain: any; roles: Record<string, string>; role_order: string[] }
export type ElementPage = { kind: string; id: string; data: Record<string, any>; stage: string; up: Link[]; down: Link[]; provenance: any[]; fmea?: any[]; screened?: any[]; unassessed?: any[]; disciplines?: string[] }
export type Link = { kind: string | null; id: string; rel: string; name: string }
export type Form = { name: string; title: string; standard: string; groups: [string, number][]; headers: string[]; widths: number[]; rows: any[][]; row_keys?: (string | null)[]; editable?: Record<number, string>; merge_cols?: number[]; row_elements?: string[]; rating_tables?: Record<string, [number, string][]>; kind?: string; pairs?: [string, string][] }
export type PatchSummary = { id: string; status: string; author: string; rationale: string; sources: string[]; created: number; ops: { op: string; kind: string; id: string; name: string; diff: string }[]; warnings: string[]; errors: string[]; coverage_delta: Record<string, [number, number]>; valid: boolean }
