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
}

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
  ask: (question: string, rules = false) =>
    j<AskResult>('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, rules }) }),
  approve: (result_id: string, decision: 'approved' | 'rejected' | 'flagged', note = '') =>
    j<Record<string, unknown>>('/api/approve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ result_id, decision, note }) }),
}
