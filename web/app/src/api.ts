// API client for the Launch backend. All project routes are under /api/p/{pid}.
export type Kind = string
export const KIND_LABEL: Record<string, string> = {
  stakeholders: 'Stakeholders', needs: 'Needs', moes: 'Measures of effectiveness', actors: 'Actors', use_cases: 'Use cases', scenarios: 'Scenarios',
  regulations: 'Regulations', requirements: 'Requirements', functions: 'Functions', logical_components: 'Logical components', logical_interfaces: 'Logical interfaces',
  parts: 'Parts', nodes: 'Physical nodes', interfaces: 'Interfaces', states: 'States', transitions: 'Transitions', arch_decisions: 'Architecture decisions',
  trades: 'Trade studies', constraints: 'Constraints', tests: 'Tests', gates: 'Gates', fm_assessments: 'FMEA assessments', fmea: 'Failure modes',
  teams: 'Teams', process_steps: 'Process steps', suppliers: 'Suppliers', work_items: 'Work items', findings: 'Findings', handoffs: 'Handoffs', field_events: 'Field events', risks: 'Program risks', reviews: 'Design reviews', tables: 'Tables', notes: 'Notes', test_runs: 'Test runs', phases: 'Phases', deliverables: 'Deliverables', dfx_reviews: 'DfX reviews', cad_models: 'CAD models', simulations: 'Simulations', attachments: 'Attachments',
}
// INCOSE SE Handbook / ISO 15288: life-cycle stages, technical processes (each in the stage where it is primarily exercised), management processes
export const LIFECYCLE = ['Concept', 'Development', 'Production', 'Utilization', 'Support', 'Retirement']
export const PROCESS_STAGE: Record<string, string> = {
  'Business or mission analysis': 'Concept', 'Stakeholder needs and requirements definition': 'Concept',
  'System requirements definition': 'Development', 'System architecture definition': 'Development', 'Design definition': 'Development', 'System analysis': 'Development', 'Implementation': 'Development', 'Integration': 'Development', 'Verification': 'Development',
  'Transition': 'Production', 'Validation': 'Production', 'Operation': 'Utilization', 'Maintenance': 'Support', 'Disposal': 'Retirement',
  'Project planning': 'Management', 'Project assessment and control': 'Management', 'Decision management': 'Management', 'Risk management': 'Management', 'Configuration management': 'Management', 'Information management': 'Management', 'Measurement': 'Management', 'Quality assurance': 'Management',
}
export const STAGE_COLOR: Record<string, string> = {
  Concept: 'var(--s1)', Development: 'var(--s3)', Production: '#7c5c2b', Utilization: '#15803d', Support: '#0e7490', Retirement: '#6b7280', Management: '#6d28d9', 'Risk (derived)': 'var(--sr)',
}
export const PROCESS_COLOR: Record<string, string> = {   // distinguish the many Development processes
  'System requirements definition': 'var(--s2)', 'System architecture definition': 'var(--s3)', 'Design definition': 'var(--s4)', 'System analysis': 'var(--s5)', 'Verification': 'var(--s6)', 'Implementation': '#6d28d9', 'Integration': '#0f766e',
}
export const stageColor = (s?: string) => !s ? 'var(--sx)' : PROCESS_COLOR[s] || STAGE_COLOR[s] || STAGE_COLOR[PROCESS_STAGE[s]] || 'var(--sx)'
export const stageOf = (s?: string) => (s && (STAGE_COLOR[s] ? s : PROCESS_STAGE[s])) || ''
export const FORMS: { id: string; title: string; std: string; stage: string; group: string }[] = [
  { id: 'reqspec', title: 'Requirements specification', std: 'ISO/IEC/IEEE 29148', stage: 'System requirements definition', group: 'Requirements' },
  { id: 'vcrm', title: 'VCRM / RTM', std: 'ISO/IEC/IEEE 29148', stage: 'Verification', group: 'Verification' },
  { id: 'dvpr', title: 'DVP&R', std: 'AIAG APQP', stage: 'Verification', group: 'Verification' },
  { id: 'dfmea', title: 'DFMEA', std: 'AIAG & VDA 2019', stage: 'System analysis', group: 'Risk' },
  { id: 'hazards', title: 'Hazard register', std: 'safety decisions, S ≥ 9', stage: 'System analysis', group: 'Risk' },
  { id: 'fta', title: 'Fault trees', std: 'IEC 61025 (tabular)', stage: 'System analysis', group: 'Risk' },
  { id: 'drbfm', title: 'DRBFM', std: 'Toyota GD³', stage: 'System analysis', group: 'Risk' },
  { id: 'n2', title: 'N² — physical', std: 'NASA SE Handbook', stage: 'System architecture definition', group: 'Architecture' },
  { id: 'n2l', title: 'N² — logical', std: 'NASA SE Handbook', stage: 'System architecture definition', group: 'Architecture' },
  { id: 'icd', title: 'ICD index', std: 'MIL-STD-961 outline', stage: 'System architecture definition', group: 'Architecture' },
  { id: 'pugh', title: 'Trade matrices', std: 'Pugh / weighted', stage: 'System analysis', group: 'Analysis' },
  { id: 'pfmea', title: 'PFMEA', std: 'AIAG & VDA 2019', stage: 'Transition', group: 'Manufacturing' },
  { id: 'control_plan', title: 'Control plan', std: 'AIAG APQP', stage: 'Transition', group: 'Manufacturing' },
  { id: 'avl', title: 'AVL / sourcing', std: 'approved vendor list', stage: 'Implementation', group: 'Supply chain' },
  { id: 'work_items', title: 'Work items', std: 'program tasks', stage: 'Project planning', group: 'Program' },
  { id: 'findings', title: 'Findings', std: 'reviews, audits, tests, field', stage: 'Quality assurance', group: 'Program' },
  { id: 'handoffs', title: 'Handoffs', std: 'cross-functional evidence', stage: 'Project assessment and control', group: 'Program' },
  { id: 'risks', title: 'Program risk register', std: '5×5', stage: 'Risk management', group: 'Program' },
  { id: 'fracas', title: 'FRACAS', std: 'field failures → DFMEA', stage: 'Maintenance', group: 'Operations' },
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
  del: (p: string) => api.del(`/p/${pid}${p}`),
  out: (path: string) => (import.meta.env.VITE_REVIEW === '1' ? `out/${path}` : `/p/${pid}/out/${path}`),
})

export const ID_RE = /\b((?:STK|MOE|UC|SC|REG|LC|LI|ND|IF|TR|TD|AD|FM|FA|HZ|FT|N|R|P|S|C|T|G)-[A-Za-z0-9_.-]+|F\d{2}[a-z]?)\b/g

export type Project = { id: string; user: string; meta: Record<string, any>; counts: Record<string, number>; stage_of: Record<string, string>; lifecycle: string[]; processes: { name: string; stage: string; kinds: string[] }[]; management: { name: string; kinds: string[] }[]; stage?: string; teams?: Record<string, any>; schema: Record<string, { req: string[]; opt: Record<string, any>; refs: Record<string, string> }>; fmea_counts: Record<string, number>; coverage: Record<string, any>; staged: number; busy: boolean; auto: boolean; toolchain: any; roles: Record<string, string>; role_order: string[] }
export type ElementPage = { kind: string; id: string; data: Record<string, any>; stage: string; up: Link[]; down: Link[]; provenance: any[]; fmea?: any[]; screened?: any[]; unassessed?: any[]; disciplines?: string[] }
export type Link = { kind: string | null; id: string; rel: string; name: string }
export type Form = { name: string; title: string; standard: string; groups: [string, number][]; headers: string[]; widths: number[]; rows: any[][]; row_keys?: (string | null)[]; editable?: Record<number, string>; merge_cols?: number[]; row_elements?: string[]; rating_tables?: Record<string, [number, string][]>; kind?: string; pairs?: [string, string][] }
export type PatchSummary = { id: string; status: string; author: string; rationale: string; sources: string[]; created: number; ops: { op: string; kind: string; id: string; name: string; diff: string }[]; warnings: string[]; errors: string[]; coverage_delta: Record<string, [number, number]>; valid: boolean }
