const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const money = (v: number | null | undefined, compact = false) => {
  if (v == null || !Number.isFinite(v)) return '—'
  if (compact && Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`
  if (compact && Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(Math.abs(v) >= 100000 ? 0 : 1)}K`
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}
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
