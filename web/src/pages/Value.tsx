import { useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { api, type Cost } from '../lib/api'
import { money, num } from '../lib/format'
import { useLoad } from '../lib/store'
import { Badge, Button, Card, CardHeader, ErrorState, PageHeader, PageSkeleton, Stat } from '../components/ui'

const KIND: Record<Cost['kind'], { label: string; tone: 'brand' | 'warn' | 'neutral' }> = {
  sourced: { label: 'Sourced', tone: 'brand' }, assumption: { label: 'Assumption', tone: 'warn' },
  client_entered: { label: 'Client-entered (fictional)', tone: 'neutral' }, none: { label: 'No source', tone: 'neutral' },
}

function CostRow({ k, c, onSave }: { k: string; c: Cost; onSave: (k: string, v: number) => Promise<void> }) {
  const [v, setV] = useState(String(c.value))
  const [err, setErr] = useState<string | null>(null)
  const save = async () => {
    const n = Number(v)
    if (v.trim() === '' || !Number.isFinite(n) || n < 0) { setErr('Enter a number of 0 or more'); return }
    if (n === c.value) return
    setErr(null)
    try { await onSave(k, n) } catch (e) { setErr(String((e as Error).message)) }
  }
  return (
    <div className="grid gap-3 border-t border-border py-4 first:border-0 md:grid-cols-[1fr_150px_1.4fr] md:items-start">
      <div><div className="font-medium text-[13.5px]">{c.label}</div><div className="mt-1"><Badge tone={KIND[c.kind].tone}>{KIND[c.kind].label}</Badge></div></div>
      <div>
        <div className="flex items-center rounded-lg border border-border-strong focus-within:ring-4 focus-within:ring-brand/10">
          <span className="pl-3 text-fg-mute">$</span>
          <input inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && save()} onBlur={save}
            className="w-full bg-transparent px-2 py-2 tnum font-medium focus:outline-none" aria-label={c.label} />
        </div>
        <div className="mt-1 text-[11.5px] text-fg-mute">{c.unit}</div>
        {err && <div className="mt-1 text-[12px] text-crit-700">{err}</div>}
      </div>
      <div className="text-[12.5px] leading-snug text-fg-soft">{c.source}<div className="mt-1 text-fg-mute">{c.note}</div></div>
    </div>
  )
}

export default function Value() {
  const costs = useLoad(() => api.costs(), [])
  const [tick, setTick] = useState(0)
  const [head, setHead] = useState(300)
  const value = useLoad(() => api.value(head), [tick, head])
  if (costs.error) return <ErrorState error={costs.error} />
  if (!costs.data || !value.data) return <PageSkeleton />
  const v = value.data
  const save = async (k: string, n: number) => { costs.setData(await api.putCosts({ [k]: n })); setTick((t) => t + 1) }
  const reset = async () => { costs.setData(await api.resetCosts()); setTick((t) => t + 1) }
  // Pricing hypothesis derived from the value estimate, not a market price: 10% of the low case, per site per month.
  const price = Math.round((v.low * 0.1) / 12 / 10) * 10
  return (
    <div>
      <PageHeader title="Business case" sub={<>For a {num(v.headcount)}-person distribution center, voluntary turnover and days-away injuries cost about <b className="text-fg">{money(v.baseline_turnover_cost + v.baseline_injury_cost, true)}</b> a year. A small improvement is worth <b className="text-fg">{money(v.low, true)}–{money(v.high, true)}</b> per site per year.</>}
        actions={<Button variant="secondary" icon={<RotateCcw size={15} />} onClick={reset}>Reset inputs</Button>} />
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
        <Stat label="Voluntary turnover, per year" value={money(v.baseline_turnover_cost, true)} tone="crit" sub={`${num(v.headcount * 0.26)} quits × replacement cost`} />
        <Stat label="Days-away injuries, per year" value={money(v.baseline_injury_cost, true)} tone="crit" sub={`${num(v.headcount * 0.015, 1)} cases × cost per case`} />
        <Stat label="Value if it helps a little" value={`${money(v.low, true)}–${money(v.high, true)}`} tone="brand" sub="per site, per year · assumption below" />
        <Stat label="US warehousing sites" value={num(v.segment.establishments)} sub="starting segment · BLS NAICS 493" />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader title="Unit costs" sub="Every input has a source or is marked as an assumption. Edit any value; the site board and this page recompute." />
          {Object.entries(costs.data).map(([k, c]) => <CostRow key={k + c.value} k={k} c={c} onSave={save} />)}
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="The assumption, stated plainly" />
            <p className="text-[13.5px] leading-relaxed text-fg-soft">{v.scenario}</p>
            <label className="mt-5 block">
              <div className="flex justify-between text-[12.5px]"><span className="label">Site headcount</span><b className="tnum">{num(head)}</b></div>
              <input type="range" min={100} max={1000} step={50} value={head} onChange={(e) => setHead(Number(e.target.value))} className="mt-2 w-full accent-[#0E8A7E]" />
            </label>
          </Card>
          <Card>
            <CardHeader title="Pricing hypothesis" sub="To be tested in a pilot — not a validated price" right={<Badge tone="warn">Hypothesis</Badge>} />
            <div className="text-[28px] font-semibold tnum tracking-tight">{money(price)}<span className="text-[14px] font-normal text-fg-mute"> per site / month</span></div>
            <p className="mt-2 text-[12.5px] text-fg-soft">Set at 10% of the low value case ({money(v.low, true)} a year), so a site keeps about 90% of the value it gets even in the conservative scenario.</p>
            <dl className="mt-4 grid grid-cols-[100px_1fr] gap-y-2 border-t border-border pt-3 text-[12.5px]">
              <dt className="text-fg-mute">User</dt><dd>Site or shift manager</dd>
              <dt className="text-fg-mute">Buyer</dt><dd>Operations or HR leader who owns the site budget</dd>
              <dt className="text-fg-mute">Data owners</dt><dd>HR (survey export) · Operations (timekeeping, WMS)</dd>
              <dt className="text-fg-mute">Pilot test</dt><dd>Can one site fill the monthly template in under a day? If not, stop.</dd>
            </dl>
          </Card>
          <Card>
            <CardHeader title="Sector inputs" />
            <ul className="space-y-3 text-[12.5px]">
              {v.inputs.slice(0, 2).map((i) => <li key={i.label}><b>{i.label}: {(i.value * 100).toFixed(1)}%</b><div className="text-fg-mute">{i.source}</div></li>)}
              <li><b>Segment</b><div className="text-fg-mute">{v.segment.source}</div></li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
