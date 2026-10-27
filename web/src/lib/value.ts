/** What a plan is worth: the three tiers `app/impact.py` `value_of_plan` returns (Oct 27, 2026 round).
 *  Every tier carries its inputs so the screen prints the assumption next to the number. Nothing here is typed in. */
import type { Kpi } from './api'

export type CostKind = 'sourced' | 'assumption' | 'client_entered' | 'none'

export interface ValueInput { label: string; value: number | string | number[]; source: string; kind?: CostKind | null }

export interface MeasuredComponent {
  kpi: Kpi; kpi_label: string; events_avoided_per_quarter: number; events_avoided_per_year: number
  unit_cost: number; unit_kind: CostKind; unit_source: string; comparison_teams: number
  ci_low_per_10: number; ci_high_per_10: number; dollars: number
}
export interface ExcludedKpi { kpi: Kpi; kpi_label: string; verdict: string | null; why: string; estimate?: number; ci_low?: number; ci_high?: number }

export interface Mechanism { kpi: Kpi; item: string; slope: number | null; ci_low: number | null; ci_high: number | null; p: number | null; n_cells: number; n_teams: number; verdict: string }

interface TierBase { id: 'measured' | 'projected' | 'hospital'; kind: 'measured' | 'projection' | 'scenario'; label: string; sentence: string; inputs: ValueInput[]; dollars: number | null; low: number | null; high: number | null }
export interface MeasuredTier extends TierBase { id: 'measured'; kind: 'measured'; dollars: number; components: MeasuredComponent[]; excluded: ExcludedKpi[]; small_because: string }
export interface ProjectedTier extends TierBase {
  id: 'projected'; kind: 'projection'; low: number; high: number; quits_avoided_low: number; quits_avoided_high: number; quits_per_year_now: number
  in_range: boolean; sane_range: [number, number]; condition: string
  recovery?: { low: string; high: string }   // Oct 27 polish: low = to the median, high = to the top quartile
  focus: { item: string; label: string; w1: number | null; w2: number | null; quartile_w1: number | null; quartile_w2: number | null; n_cells: number }
  mechanism: Mechanism[]
}
export interface HospitalTier extends TierBase { id: 'hospital'; kind: 'scenario'; low: number; high: number; headcount: number; link: string; condition: string }
export type ValueTier = MeasuredTier | ProjectedTier | HospitalTier

export interface PlanValue {
  illustrative: boolean; illustrative_reason: string
  team: { team_id: number; label: string; headcount: number }
  as_of: string
  tiers: ValueTier[]
}

/** Price benchmarks for comparable software, from data/docs/pricing_benchmarks.json when stream P has written it. */
export interface PriceBenchmark {
  vendor: string; product?: string; category?: string; model?: string; price?: string | number | null; unit?: string
  basis?: string; source_url?: string; retrieved?: string; confidence?: string
}

/** The price hypothesis, from data/docs/pricing_hypothesis.json (Oct 27, 2026 research); an assumption until a pilot. */
export interface PricingHypothesis {
  as_of: string; status: string; model: string; tiers: { up_to_staff: number; monthly_usd: number }[]; above: string
  basis: string; replaces?: string; usage_based?: string; to_confirm?: string
}
