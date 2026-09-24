import { useState } from 'react'
import { api, type Cost } from '../lib/api'
import { money, num } from '../lib/format'
import { useLoad } from '../lib/store'
import { Button, Card, Chip, ErrorNote, Eyebrow, Loading, PageTitle, Stat } from '../components/ui'

const KIND: Record<Cost['kind'], { label: string; kind: 'computed' | 'person' | 'synthetic' | 'neutral' }> = {
  sourced: { label: 'Sourced', kind: 'computed' },
  assumption: { label: 'Assumption', kind: 'person' },
  client_entered: { label: 'Client-entered (fictional)', kind: 'synthetic' },
  none: { label: 'No source', kind: 'neutral' },
}

function CostRow({ k, c, onSave }: { k: string; c: Cost; onSave: (k: string, v: number) => Promise<void> }) {
  const [v, setV] = useState(String(c.value))
  const [err, setErr] = useState<string | null>(null)
  const dirty = Number(v) !== c.value
  const save = async () => {
    const n = Number(v)
    if (v.trim() === '' || !Number.isFinite(n) || n < 0) { setErr('Enter a number of 0 or more'); return }
    setErr(null)
    try { await onSave(k, n) } catch (e) { setErr(String((e as Error).message)) }
  }
  return (
    <div className="grid gap-3 border-t border-line py-4 md:grid-cols-[1.2fr_170px_1.6fr] md:items-start">
      <div>
        <div className="font-semibold">{c.label}</div>
        <div className="mt-1"><Chip kind={KIND[c.kind].kind}>{KIND[c.kind].label}</Chip></div>
      </div>
      <div>
        <div className="flex items-center rounded-lg border border-line bg-paper focus-within:ring-2 focus-within:ring-teal/30">
          <span className="pl-3 text-ink-mute">$</span>
          <input inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && save()} onBlur={() => dirty && save()}
            className="w-full bg-transparent px-2 py-2 num text-[1.1rem] focus:outline-none" aria-label={c.label} />
        </div>
        <div className="text-[11.5px] text-ink-mute mt-1">{c.unit}</div>
        {err && <div className="text-[12px] text-rust mt-1">{err}</div>}
      </div>
      <div className="text-[13px] text-ink-soft leading-snug">{c.source}<div className="text-ink-mute mt-1">{c.note}</div></div>
    </div>
  )
}

export default function Value() {
  const costs = useLoad(() => api.costs(), [])
  const [tick, setTick] = useState(0)
  const [head, setHead] = useState(300)
  const value = useLoad(() => api.value(head), [tick, head])
  if (costs.error) return <ErrorNote error={costs.error} />
  if (!costs.data || !value.data) return <Loading />
  const v = value.data
  const save = async (k: string, n: number) => { costs.setData(await api.putCosts({ [k]: n })); setTick((t) => t + 1) }
  const reset = async () => { costs.setData(await api.resetCosts()); setTick((t) => t + 1) }

  return (
    <div>
      <PageTitle kicker="Business case · for the buyer" title={<>For one 300-person distribution center, the problem costs about <span className="text-rust num">{money(v.baseline_turnover_cost + v.baseline_injury_cost, true)}</span> a year. A small improvement is worth <span className="text-teal num">{money(v.low, true)}–{money(v.high, true)}</span>.</>}
        lede="Every input has a source or is marked as an assumption. The buyer can replace any of them with their own numbers, and everything on this page and on the site board recomputes." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 border-y border-line py-6 mb-10 stagger">
        <Stat label="Voluntary turnover, per year" value={money(v.baseline_turnover_cost, true)} sub={`${num(v.headcount * 0.26)} quits × replacement cost`} tone="rust" />
        <Stat label="Days-away injuries, per year" value={money(v.baseline_injury_cost, true)} sub={`${num(v.headcount * 0.015, 1)} cases × cost per case`} tone="rust" />
        <Stat label="Value if it helps a little" value={`${money(v.low, true)}–${money(v.high, true)}`} sub="per site, per year (assumption below)" tone="teal" />
        <Stat label="US warehousing sites" value={num(v.segment.establishments)} sub="starting segment, BLS NAICS 493" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <Eyebrow>Unit costs · editable</Eyebrow>
            <Button kind="quiet" onClick={reset}>Reset to defaults</Button>
          </div>
          <div className="mt-3">{Object.entries(costs.data).map(([k, c]) => <CostRow key={k + c.value} k={k} c={c} onSave={save} />)}</div>
        </Card>
        <div className="space-y-6">
          <Card className="p-6" tone="rust">
            <Eyebrow>The assumption, stated plainly</Eyebrow>
            <p className="mt-2 text-[14.5px] leading-relaxed">{v.scenario}</p>
            <label className="block mt-5">
              <span className="eyebrow">Site headcount</span>
              <input type="range" min={100} max={1000} step={50} value={head} onChange={(e) => setHead(Number(e.target.value))} className="w-full accent-[#1F8FA8] mt-2" />
              <span className="num text-[1.3rem]">{num(head)} people</span>
            </label>
          </Card>
          <Card className="p-6">
            <Eyebrow>Sector inputs</Eyebrow>
            <ul className="mt-2 space-y-3 text-[13px]">
              {v.inputs.slice(0, 2).map((i) => <li key={i.label}><b>{i.label}: {(i.value * 100).toFixed(1)}%</b><div className="text-ink-mute">{i.source}</div></li>)}
              <li><b>Segment</b><div className="text-ink-mute">{v.segment.source}</div></li>
            </ul>
          </Card>
          <Card className="p-6">
            <Eyebrow>Who is who</Eyebrow>
            <dl className="mt-2 grid grid-cols-[110px_1fr] gap-y-2 text-[13.5px]">
              <dt className="font-semibold">User</dt><dd className="text-ink-soft">Site or shift manager</dd>
              <dt className="font-semibold">Buyer</dt><dd className="text-ink-soft">Operations or HR leader who owns the site budget</dd>
              <dt className="font-semibold">Data owners</dt><dd className="text-ink-soft">HR (survey export) and operations (timekeeping, WMS)</dd>
              <dt className="font-semibold">Pilot test</dt><dd className="text-ink-soft">Can one site fill the monthly template in under a day? If not, stop.</dd>
            </dl>
            <p className="text-[12px] text-ink-mute mt-3">Working hypotheses, to be tested in a pilot. Gallup is the sponsor, not a sales channel.</p>
          </Card>
        </div>
      </div>
    </div>
  )
}
