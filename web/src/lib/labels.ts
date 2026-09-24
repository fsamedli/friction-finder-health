import type { Kpi } from './api'

export const KPI_SHORT: Record<Kpi, string> = {
  late_departures: 'Late departures', absence_days: 'Absence days', quits: 'Quits', injuries: 'Injuries', rework: 'Rework',
}
export const KPI_UNIT: Record<Kpi, string> = {
  late_departures: 'late trucks', absence_days: 'absence days', quits: 'quits', injuries: 'injuries', rework: 'rework events',
}
