import type { Kpi } from './api'

export const KPI_SHORT: Record<Kpi, string> = {
  late_doses: 'Late doses', absence_days: 'Absence days', quits: 'Quits', injuries: 'Injuries', overtime_shifts: 'Overtime shifts',
}
export const KPI_UNIT: Record<Kpi, string> = {
  late_doses: 'late doses', absence_days: 'absence days', quits: 'quits', injuries: 'injuries', overtime_shifts: 'overtime shifts',
}

/** Review verdicts in plain words (v0.8). app/impact.py returns worked / no effect / inconclusive; 'no effect'
 *  there means the whole 95% interval is above zero, i.e. the KPI rose relative to the comparison teams. */
export type ReviewWord = 'Improved' | 'Deteriorated' | 'Inconclusive'
export const reviewWord = (v?: string | null): ReviewWord => (v === 'worked' ? 'Improved' : v === 'no effect' ? 'Deteriorated' : 'Inconclusive')
export const reviewTone = (v?: string | null): 'ok' | 'crit' | 'warn' => (v === 'worked' ? 'ok' : v === 'no effect' ? 'crit' : 'warn')
