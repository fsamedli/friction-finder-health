import type { Kpi } from './api'

export const KPI_SHORT: Record<Kpi, string> = {
  late_departures: 'Late departures', absence_days: 'Absence days', quits: 'Quits', injuries: 'Injuries', rework: 'Rework',
}
export const KPI_UNIT: Record<Kpi, string> = {
  late_departures: 'late trucks', absence_days: 'absence days', quits: 'quits', injuries: 'injuries', rework: 'rework events',
}

/** Review verdicts in plain words (v0.8). app/impact.py returns worked / no effect / inconclusive; 'no effect'
 *  there means the whole 95% interval is above zero, i.e. the KPI rose relative to the comparison teams. */
export type ReviewWord = 'Improved' | 'Deteriorated' | 'Inconclusive'
export const reviewWord = (v?: string | null): ReviewWord => (v === 'worked' ? 'Improved' : v === 'no effect' ? 'Deteriorated' : 'Inconclusive')
export const reviewTone = (v?: string | null): 'ok' | 'crit' | 'warn' => (v === 'worked' ? 'ok' : v === 'no effect' ? 'crit' : 'warn')
