/** A tiny SVG sparkline (no chart library): team rate (solid) vs comparable teams (dashed). Kept out of the
 *  charts bundle so the first screen loads without Recharts. */
export function Spark({ data, flagged }: { data: { month: string; rate: number; baseline: number }[]; flagged?: boolean }) {
  const W = 112, H = 32, P = 3
  const max = Math.max(1e-9, ...data.flatMap((d) => [d.rate, d.baseline]))
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, data.length - 1)
  const y = (v: number) => H - P - (v / max) * (H - 2 * P)
  const line = (k: 'rate' | 'baseline') => data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d[k]).toFixed(1)}`).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Trend over ${data.length} months${flagged ? ', above normal variation' : ''}`}>
      {data.length > 1 && <>
        <path d={line('baseline')} fill="none" stroke="#98A2B3" strokeWidth={1.2} strokeDasharray="2 2" />
        <path d={line('rate')} fill="none" stroke={flagged ? '#D92D20' : '#101828'} strokeWidth={1.7} strokeLinejoin="round" />
      </>}
    </svg>
  )
}
