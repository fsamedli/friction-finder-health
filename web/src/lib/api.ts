// Typed client for api/main.py. Every number on screen comes from one of these calls.

export type Kpi = 'absence_days' | 'late_departures' | 'quits' | 'injuries' | 'rework'
export const KPI_ORDER: Kpi[] = ['late_departures', 'absence_days', 'quits', 'injuries', 'rework']

export interface Meta {
  company: string
  sites: { site_id: number; site_name: string }[]
  as_of_presets: { value: string; label: string; hint: string }[]
  kpis: Record<Kpi, string>
  items: Record<string, string>
  min_n: number
  model: string | null
}

export interface Excess {
  observed: number; expected: number; p: number | null; judgeable: boolean; flagged: boolean
  count: number; rate: number; baseline: number; dollars: number
}
export interface Drop { item: string; label: string; delta: number; p: number; significant: boolean }
export interface Engagement { n_w1: number; n_w2: number; grand_w1: number | null; grand_w2: number | null; biggest_drop: Drop | null }
export type Status = 'red' | 'amber' | 'green' | 'rolled_up'
export interface TeamRow {
  team_id: number; team_name: string; shift: string; headcount: number; status: Status
  signal?: string; elevated?: Kpi[]; excess_cost: number
  excess_by_kpi: Partial<Record<Kpi, Excess>>
  spark: Partial<Record<Kpi, { month: string; rate: number; baseline: number }[]>>
  engagement: Engagement | null
}
export interface Board {
  site_id: number; site: string; as_of: string; window: string[]; total_excess: number; annualized: number
  by_kpi: Record<Kpi, number>; counts_by_kpi: Record<Kpi, number>; teams: TeamRow[]
  rules: { ops_p: number; item_drop: number; item_p: number; min_expected: number; min_n: number }
}
export interface Assoc {
  kpi: Kpi; item: string; slope: number | null; ci_low: number | null; ci_high: number | null; p: number | null
  n_cells: number; n_teams?: number; verdict: 'association' | 'no association detected' | 'too rare to test'
  points?: { team_id: number; wave: number; x: number; rate: number }[]
}
export interface Quartile {
  kpi: Kpi; item: string; top_q_rate: number; bottom_q_rate: number; pct_diff: number | null
  n_cells: number; n_per_quartile: number; quartiles: { q: number; median_rate: number; x_range: [number, number] }[]
}
export interface ItemChange { item: string; label: string; w1: number; w2: number; delta: number }
export interface Why {
  team: { team_id: number; team_name: string; shift: string; site: string; site_id: number; headcount: number }
  suppressed: boolean; reason: string | null
  kpi_trend: ({ month: string } & Record<string, number | string>)[]
  item_changes: ItemChange[]; engagement: Engagement | null
  excess?: Partial<Record<Kpi, Excess>>; excess_cost?: number; status?: Status; window?: string[]
  links: Assoc[]
}
export interface PlanAction { text: string; owner: string; due: string }
export interface Plan {
  id: string; team_id: number; item: string; kpi: Kpi; obstacle: string; focus: string
  actions: PlanAction[]; start: string; review: string; status: string; note: string; team_label?: string
  // v0.8 (all optional; the seeded plan and v0.7 plans do not have them)
  owner?: string; measure?: string; baseline?: string; success?: string; assumptions?: string[]; finding?: string; rationale?: string
  investigation_id?: string | null; evidence_ids?: string[]; request_id?: string; decided_at?: string; created_at?: string
  edits?: { field: string; from: string; to: string }[]
}
export interface Did {
  plan_id: string; kpi: Kpi; kpi_label: string; start: string; review: string
  status: 'ok' | 'not_reached' | 'insufficient'; days_to_go?: number; reason?: string
  estimate?: number; se?: number; ci_low?: number; ci_high?: number
  verdict?: 'worked' | 'inconclusive' | 'no effect'
  treated?: { pre: number; post: number }
  comparison?: { pre: number; post: number; teams: string[] }
  placebo?: { team_id: number; team: string; estimate: number }[]
  pre_months?: string[]; post_months?: string[]
  events_avoided_per_quarter?: number; dollars_per_quarter?: number | null; unit_cost?: number
  series?: { month: string; treated: number; comparison: number }[]
  also?: Did[]
}
export interface Cost { label: string; value: number; unit: string; kind: 'sourced' | 'assumption' | 'client_entered' | 'none'; source: string; note: string }
export interface Value {
  headcount: number; baseline_turnover_cost: number; baseline_injury_cost: number; low: number; high: number
  segment: { establishments: number; employees: number; source: string }
  scenario: string; inputs: { label: string; value: number; source: string }[]
}
export interface Evidence { id: string; kind: string; statement: string; sql: string | null; rows: Record<string, unknown>[]; source: string; origin: string }
export interface AskResult {
  id: string; status: string; question: string; message: string; mode: 'model' | 'rules'; seconds: number; notes: string[]
  assessment: { verdict: string; label: string; level: string; reasons: string[]; n: Record<string, unknown> } | null
  brief: { obstacle: string; evidence_for: { claim: string; evidence_ids?: string[] }[]; evidence_against: { claim: string; evidence_ids?: string[] }[]; missing: string[]; owner: string; proposed_test: string; limits: string; mode: string; check_notes: string[] } | null
  evidence: Evidence[]
  grounding: { checked: number; total: number; unmatched: string[] }
  trace: { step: string; detail: string; mode: 'model' | 'rules' | 'code' | 'template'; seconds: number | null }[]
  prepared: { generated_at: string; model: string } | null
}

// ---------------------------------------------------------------- v0.8 investigation contract (api/main.py, app/investigate.py)
export type EvidenceState = 'supported' | 'mixed' | 'insufficient' | 'unavailable'
export type FunctionId =
  | 'why_flagged' | 'could_explain' | 'compare' | 'normal' | 'when_started' | 'how_widespread' | 'whats_missing'
  | 'provenance' | 'precedent' | 'draft_plan' | 'did_it_work' | 'team_conversation' | 'metric'
export interface InvContext {
  site_id: number | null; site: string | null; team_id: number | null; team: string | null; shift: string | null
  as_of: string; kpi: Kpi | null; kpi_label: string | null; item: string | null; item_label: string | null
  finding: { status: Status | null; kpi: Kpi | null; item: string | null } | null
  dataset: 'demo' | 'upload'; version: string
}
export interface InvEvidence extends Evidence { tool: string; turn: number; stale?: boolean }
export interface ChartSpec {
  type: 'bars' | 'line' | 'range'
  title: string; unit: string; period: string; baseline: string | null
  x: string; series: { key: string; label: string; role: 'team' | 'comparison' | 'other' }[]
  rows: Record<string, string | number | null>[]
  highlight?: string | null   // x value of the team being investigated
}
export interface TableSpec { caption: string; columns: { key: string; label: string; unit?: string }[]; rows: Record<string, string | number | null>[] }
export interface Hypothesis { id: string; label: string; evidence_state: EvidenceState; text: string; evidence_ids: string[] }
export interface Gap { gap: string; step: string; owner: string }
export interface PlanDraft {
  team_id: number; team_label: string; finding: string; rationale: string; owner: string; owner_source: string
  action: string; actions: PlanAction[]; kpi: Kpi; measure: string; baseline: string; start: string; review: string
  success: string; assumptions: string[]; item: string; focus: string; obstacle: string; evidence_ids: string[]
}
export interface InvAnswer {
  conclusion: string; evidence_state: EvidenceState; evidence_ids: string[]
  competing: { text: string; evidence_state: EvidenceState; evidence_ids: string[] } | null
  next_step: { kind: 'action' | 'gather'; text: string; owner: string } | null
  hypotheses?: Hypothesis[]; chart?: ChartSpec | null; table?: TableSpec | null
  plan_draft?: PlanDraft | null; review?: Did | null; gaps?: Gap[]; questions?: { items: string[]; source: string } | null
}
export interface TraceStep { step: string; detail: string; mode: 'code' | 'model' | 'rules'; seconds: number | null; tool?: string }
export interface Investigation {
  id: string; conversation_id: string; question: string; created_at: string
  status: 'running' | 'answered' | 'declined' | 'clarify' | 'error'; message: string | null
  function: { id: FunctionId; label: string } | null
  context: InvContext; answer: InvAnswer | null; evidence: InvEvidence[]; trace: TraceStep[]
  budget: { tool_calls: number; max_tool_calls: number; model_requests: number; max_model_requests: number; seconds: number; max_seconds: number; stopped: string | null }
  mode: 'model' | 'rules'; model: string | null; selection: 'function_calling' | 'json_schema' | 'fixed_plan'; fallback: string | null
  check: { passed: boolean; notes: string[]; numbers_checked: number; numbers_total: number }
  prepared: { generated_at: string; model: string } | null
  suggestions: { label: string; question: string; function: FunctionId }[]
}
export interface InvestigateIn {
  question: string; conversation_id?: string | null
  context?: { site_id?: number | null; team_id?: number | null; as_of?: string; kpi?: Kpi | null; item?: string | null }
  mode?: 'auto' | 'rules'; live?: boolean; function?: FunctionId | null
  async?: boolean   // true: returns at once with status 'running'; poll GET /api/investigate/{id} for the trace as it grows
}
export interface ManagerFunction { id: FunctionId; label: string; chip: string; question: string; shipped: boolean; research_label: string }
export type PlanState = 'draft' | 'approved' | 'in_review' | 'reviewed'
export interface PlanRow extends Plan { state: PlanState; result: Did | null; owner?: string; measure?: string; success?: string; baseline?: string; assumptions?: string[] }
export interface PlansBoard { plans: PlanRow[]; queue: { due_reviews: string[]; missing_follow_ups: string[]; inconclusive: string[] } }

export interface PackRun { file: string; ts: string; model: string; passed: number; total: number }
export interface Quality {
  packs: { pack: string; note: string; mode: string | null; first: PackRun | null; now: PackRun | null }[]
  declines: { file: string; ts: string; correct: number; total: number }[]
  grounding: { file: string; briefs: number; checked: number; total: number; generated: string[] } | null
  latency: { mode: string; n: number; p50: number | null; p95: number | null; files: string[] }[]
  feedback: { file: string; total: number; useful: number; not_useful: number; reasons: Record<string, number> }
}

export interface Source { id: string; name: string; vendor: string; owner: string; status: 'demo_csv' | 'not_connected'; method: string; rows: number; detail: string; last: string | null }

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    let msg = `${r.status}`
    try { msg = (await r.json()).detail ?? msg } catch { /* not JSON */ }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return r.json() as Promise<T>
}
const q = (o: Record<string, string | number>) => '?' + new URLSearchParams(Object.entries(o).map(([k, v]) => [k, String(v)]))

export const api = {
  meta: () => j<Meta>('/api/meta'),
  board: (site_id: number, as_of: string) => j<Board>('/api/board' + q({ site_id, as_of })),
  why: (team_id: number, as_of: string) => j<Why>(`/api/why/${team_id}` + q({ as_of })),
  link: (kpi: Kpi, item: string) => j<{ quartile: Quartile; association: Assoc }>('/api/link' + q({ kpi, item })),
  links: () => j<Assoc[]>('/api/links'),
  plans: () => j<Plan[]>('/api/plans'),
  createPlan: (p: Omit<Plan, 'id' | 'review'> & { review?: string }) =>
    j<Plan>('/api/plans', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }),
  result: (id: string, as_of: string) => j<Did>(`/api/plans/${id}/result` + q({ as_of })),
  costs: () => j<Record<string, Cost>>('/api/costs'),
  putCosts: (u: Record<string, number>) =>
    j<Record<string, Cost>>('/api/costs', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(u) }),
  resetCosts: () => j<Record<string, Cost>>('/api/costs', { method: 'DELETE' }),
  value: (headcount = 300) => j<Value>('/api/value' + q({ headcount })),
  assumptions: () => j<{ rows: { k: string; v: string; why: string }[]; with_real_data: string[] }>('/api/assumptions'),
  evals: () => j<{ file: string; model: string; passed: number; total: number; matrix: Record<string, number>; ts: string; rows: { id: string; class: string; question: string; status: string; verdict: string; passed: boolean; outcome: string }[] }[]>('/api/evals/latest'),
  feedback: () => j<{ who: string; when: string; said: string; changed: string }[]>('/api/feedback'),
  resetDemo: () => j<{ ok: boolean }>('/api/demo', { method: 'DELETE' }),
  quality: () => j<Quality>('/api/quality'),
  useful: (target: 'ask' | 'plan' | 'investigation', target_id: string, useful: boolean, reason?: string) =>
    j<Record<string, unknown>>('/api/useful', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target, target_id, useful, reason: reason ?? null }) }),
  opsUpload: () => j<{ active: boolean; rows?: number; teams?: number; months?: string[] }>('/api/ops-upload'),
  opsUploadSend: async (file: File) => {
    const f = new FormData(); f.append('file', file)
    const r = await fetch('/api/ops-upload', { method: 'POST', body: f })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw Object.assign(new Error('upload rejected'), { problems: (body?.detail?.problems ?? [typeof body?.detail === 'string' ? body.detail : 'Upload failed']) as string[] })
    return body as { active: boolean; rows: number; teams: number; months: string[]; message: string }
  },
  opsUploadClear: () => j<{ active: boolean }>('/api/ops-upload', { method: 'DELETE' }),
  sources: () => j<Source[]>('/api/sources'),
  upload: async (file: File) => { const f = new FormData(); f.append('file', file); return j<{ rows_added: number }>('/api/upload', { method: 'POST', body: f }) },
  reviewLog: () => j<Record<string, unknown>[]>('/api/review-log'),
  ask: (question: string, rules = false, live = false) =>
    j<AskResult>('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, rules, live }) }),
  investigate: (body: InvestigateIn) =>
    j<Investigation>('/api/investigate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  investigation: (id: string) => j<Investigation>(`/api/investigate/${id}`),
  functions: () => j<ManagerFunction[]>('/api/functions'),
  plansBoard: (as_of: string) => j<PlansBoard>('/api/plans/board' + q({ as_of })),
  planCheck: (team_id: number, kpi: Kpi, start: string) => j<{ existing: Plan[]; explanation: string }>('/api/plans/check' + q({ team_id, kpi, start })),
  approvePlan: (id: string, body: { request_id: string; edits: { field: string; from: string; to: string }[] }) =>
    j<Plan>(`/api/plans/${id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  invFeedback: (investigation_id: string, reason: string, evidence_ids: string[], note = '') =>
    j<Record<string, unknown>>('/api/useful', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: 'investigation', target_id: investigation_id, useful: false, reason, evidence_ids, note }) }),
  approve: (result_id: string, decision: 'approved' | 'rejected' | 'flagged', note = '') =>
    j<Record<string, unknown>>('/api/approve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ result_id, decision, note }) }),
}
