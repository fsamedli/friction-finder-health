const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Full dollars everywhere ($228,270, never $228K): Prof. Hall, Oct 21, 2026. `compact` now abbreviates only at
 *  ten million and above, so every figure the demo shows prints in full; the flag is kept so callers still compile. */
export const money = (v: number | null | undefined, compact = false) => {
  if (v == null || !Number.isFinite(v)) return '—'
  if (compact && Math.abs(v) >= 10_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}
/** "$31,093 to $75,511" for a range; one figure when the ends match. */
export const moneyRange = (lo: number | null | undefined, hi: number | null | undefined) =>
  lo == null || hi == null ? money(lo ?? hi) : lo === hi ? money(lo) : `${money(lo)} to ${money(hi)}`
export const pts = (v: number | null | undefined) =>
  v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(2)} pts`
export const signed = (v: number | null | undefined, d = 2) =>
  v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`
export const num = (v: number | null | undefined, d = 0) =>
  v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })
export const per10 = (rate: number | null | undefined) => (rate == null ? '—' : (rate * 10).toFixed(1))
export const month = (m: string) => MONTHS[Number(m.slice(5, 7)) - 1] ?? m
export const monthRange = (ms: string[]) => (ms.length ? `${month(ms[0])}–${month(ms[ms.length - 1])} ${ms[0].slice(0, 4)}` : '')
export const longDate = (d: string) => {
  const [y, m, day] = d.split('-').map(Number)
  return `${MONTHS[m - 1]} ${day}, ${y}`
}
export const pval = (p: number | null | undefined) => (p == null ? '—' : p < 0.001 ? 'p < 0.001' : `p = ${p.toFixed(3)}`)
export const dataThrough = (months: string[]) => {
  if (!months.length) return ''
  const m = months[months.length - 1], y = Number(m.slice(0, 4)), mo = Number(m.slice(5, 7))
  return `data through ${MONTHS[mo - 1]} ${new Date(y, mo, 0).getDate()}, ${y}`
}
