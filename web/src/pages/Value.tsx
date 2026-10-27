import { useState } from 'react'
import { ExternalLink, RotateCcw } from 'lucide-react'
import { api, type Cost, type Value as ValueCase } from '../lib/api'
import type { PriceBenchmark, PricingHypothesis } from '../lib/value'
import { money, num } from '../lib/format'
import { useLoad } from '../lib/store'
import { Badge, Button, Card, CardHeader, CsvButton, ErrorState, PageHeader, PageSkeleton, Stat } from '../components/ui'

/* Oct 27, 2026 round (Prof. Hall, Oct 21): the money first, in full dollars and large type; pricing framed as SaaS per
 * hospital per month and positioned against researched benchmarks once data/docs/pricing_benchmarks.json exists. */

const KIND: Record<Cost['kind'], { label: string; tone: 'brand' | 'warn' | 'neutral' }> = {
  sourced: { label: 'Sourced', tone: 'brand' }, assumption: { label: 'Assumption', tone: 'warn' },
  client_entered: { label: 'Client-entered (fictional)', tone: 'neutral' }, none: { label: 'No source', tone: 'neutral' },
}

type ValueResponse = ValueCase & { benchmarks?: PriceBenchmark[] | null; benchmarks_note?: string | null; pricing?: PricingHypothesis | null }

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
    <div className="grid grid-cols-1 gap-3 border-t border-border py-4 first:border-0 md:grid-cols-[1fr_150px_1.4fr] md:items-start">
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

const notPublic = (b: PriceBenchmark) => b.price == null || b.price === '' || /^not\b/i.test(String(b.price))
/** Context rows (headcount references the research note uses to derive per-employee figures) are not benchmarks. */
const isContext = (b: PriceBenchmark) => /context for|reference/i.test(`${b.vendor} ${b.category ?? ''}`)

/** The AONL median span of control, read from the benchmark file's context row (never typed here). */
const spanOfControl = (rows?: PriceBenchmark[] | null): { n: number; source?: string } | null => {
  const r = (rows ?? []).find((b) => /AONL/i.test(b.vendor))
  const m = r ? /span of control[^0-9]*(\d+)/i.exec(String(r.price ?? '')) : null
  return m ? { n: Number(m[1]), source: r?.source_url } : null
}

/* Six benchmarks on the page (the system-of-record list price, the two UK public-sector per-employee sheets, the US hospital
 * procurement record, the per-user floor, timekeeping); the rest stay in the research note. */
const PREFERRED: RegExp[] = [/oracle.*base/i, /qualtrics.*xm for people/i, /workday.*380/i, /press ganey/i, /microsoft/i, /ukg/i]
function pickSix(all: PriceBenchmark[]): PriceBenchmark[] {
  const priced = all.filter((b) => !notPublic(b))
  const out: PriceBenchmark[] = []
  for (const re of PREFERRED) { const hit = priced.find((b) => re.test(`${b.vendor} ${b.product ?? ''}`) && !out.includes(b)); if (hit) out.push(hit) }
  for (const b of priced) { if (out.length >= 6) break; if (!out.includes(b)) out.push(b) }
  return out.slice(0, 6)
}

function Benchmarks({ rows, note }: { rows?: PriceBenchmark[] | null; note?: string | null }) {
  const all = (rows ?? []).filter((b) => !isContext(b))
  if (all.length === 0) return <p className="mt-3 text-[12.5px] text-fg-mute">{note ?? 'No benchmark on file.'}</p>
  const shown = pickSix(all)
  return (
    <div className="mt-3">
      <table className="w-full table-fixed text-[12.5px]">
        <thead><tr className="text-left text-[11.5px] text-fg-mute"><th className="w-[34%] pb-1.5 pr-2 font-medium">Vendor · model</th><th className="w-[36%] pb-1.5 pr-2 font-medium">Price as stated</th><th className="pb-1.5 font-medium">Basis · source</th></tr></thead>
        <tbody>
          {shown.map((b, i) => (
            <tr key={i} className="border-t border-border align-top">
              <td className="py-2 pr-2 min-w-0"><div className="font-semibold text-fg break-words">{b.vendor}</div>{b.product && <div className="text-[11.5px] text-fg-mute line-clamp-2 break-words" title={b.product}>{b.product}</div>}{b.model && <div className="text-[11.5px] text-fg-soft line-clamp-2 break-words" title={b.model}>{b.model}</div>}</td>
              <td className="py-2 pr-2 min-w-0 tnum"><div className="font-medium text-fg line-clamp-3 break-words" title={String(b.price)}>{typeof b.price === 'number' ? money(b.price) : b.price}</div>{b.unit && <div className="text-[11.5px] font-normal text-fg-mute line-clamp-2 break-words">{b.unit}</div>}</td>
              <td className="py-2 min-w-0 text-[11.5px] text-fg-mute"><div className="line-clamp-2 break-words" title={b.basis}>{b.confidence ?? b.basis}</div>
                {b.source_url ? <a href={b.source_url} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex items-center gap-1 underline hover:text-fg">source <ExternalLink size={11} /></a> : 'no source'}{b.retrieved ? <> · {b.retrieved}</> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {all.length > shown.length && <p className="mt-2 text-[11.5px] text-fg-mute">{all.length - shown.length} more in the research note (My Notes, Oct 27, 2026); every row carries its source.</p>}
    </div>
  )
}

export default function Value() {
  const costs = useLoad(() => api.costs(), [])
  const [tick, setTick] = useState(0)
  const [head, setHead] = useState(300)
  const value = useLoad(() => api.value(head) as Promise<ValueResponse>, [tick, head])
  if (costs.error) return <ErrorState error={costs.error} />
  if (!costs.data || !value.data) return <PageSkeleton />
  const v = value.data
  // Sector rates come from the API's sourced inputs (turnover first, injury second), never typed here.
  const turnoverRate = v.inputs[0]?.value ?? 0, injuryRate = v.inputs[1]?.value ?? 0
  const save = async (k: string, n: number) => { costs.setData(await api.putCosts({ [k]: n })); setTick((t) => t + 1) }
  const reset = async () => { costs.setData(await api.resetCosts()); setTick((t) => t + 1) }
  // Pricing (Oct 27 polish): the hypothesis comes from data/docs/pricing_hypothesis.json via the API; the shares of value and
  // the per-staff / per-unit equivalents are computed here from the API's value, headcount and benchmark file, never typed.
  const pricing = v.pricing ?? null
  const tier = pricing?.tiers.find((t) => v.headcount <= t.up_to_staff) ?? null
  const price = tier?.monthly_usd ?? null
  const topTier = pricing ? Math.max(...pricing.tiers.map((t) => t.up_to_staff)) : null
  const floor = Math.round((v.low * 0.1) / 12 / 10) * 10   // the earlier working figure: 10% of the low case, per month
  const shareLow = price ? (price * 12) / v.low : null, shareHigh = price ? (price * 12) / v.high : null
  const perStaff = price ? (price * 12) / v.headcount : null
  const span = spanOfControl(v.benchmarks)
  const perUnit = price && span ? price / (v.headcount / span.n) : null
  const pct = (x: number | null) => (x == null ? '—' : `${Math.round(x * 100)}%`)
  const bmCount = (v.benchmarks ?? []).filter((b) => !isContext(b)).length
  const big = 'font-semibold tracking-[-0.02em] tnum leading-none'
  return (
    <div>
      <PageHeader title="Business case" sub={<>For a hospital with {num(v.headcount)} nursing and support staff, voluntary turnover and days-away staff injuries cost about <b className="text-fg">{money(v.baseline_turnover_cost + v.baseline_injury_cost)}</b> a year. Every figure below shows its source or its assumption.</>}
        actions={<Button variant="secondary" icon={<RotateCcw size={15} />} onClick={reset}>Reset inputs</Button>} />

      <Card className="mb-6 ring-2 ring-brand/15">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr] lg:items-center">
          <div>
            <div className="eyebrow">Worth to one hospital, per year</div>
            <div className={`mt-3 text-[40px] md:text-[48px] text-fg ${big}`}>{money(v.low)}</div>
            <div className={`mt-2 text-[26px] md:text-[30px] text-fg-soft ${big}`}><span className="text-[16px] font-normal text-fg-mute">to </span>{money(v.high)}</div>
            <p className="mt-4 max-w-xl text-[14px] leading-relaxed text-fg-soft">{v.scenario}</p>
          </div>
          <div className="rounded-xl border border-border bg-canvas/70 p-4">
            <div className="label">The assumptions, in one place</div>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[13px]">
              <dt className="text-fg-mute">Hospital size</dt><dd className="tnum font-medium">{num(v.headcount)} nursing and support staff</dd>
              <dt className="text-fg-mute">Time period</dt><dd className="font-medium">12 months</dd>
              <dt className="text-fg-mute">Turnover falls</dt><dd className="font-medium">1 point (low) to 3 points (high)</dd>
              <dt className="text-fg-mute">Cost per RN separation</dt><dd className="tnum font-medium">{money(v.inputs[2]?.value)} <span className="font-normal text-fg-mute">· NSI, sourced</span></dd>
              <dt className="text-fg-mute">Injuries avoided</dt><dd className="font-medium">one days-away case a year</dd>
            </dl>
            <label className="mt-4 block">
              <div className="flex justify-between text-[12.5px]"><span className="label">Nursing and support headcount</span><b className="tnum">{num(head)}</b></div>
              <input type="range" min={100} max={1000} step={50} value={head} onChange={(e) => setHead(Number(e.target.value))} className="mt-2 w-full accent-[#0E8A7E]" aria-label="Nursing and support headcount" />
            </label>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
        <Stat label="Voluntary turnover, per year" value={money(v.baseline_turnover_cost)} tone="crit" sub={`${num(v.headcount * turnoverRate)} quits × cost per RN turnover`} />
        <Stat label="Days-away staff injuries, per year" value={money(v.baseline_injury_cost)} tone="crit" sub={`${num(v.headcount * injuryRate, 1)} cases × cost per case`} />
        <Stat label="Value if it helps a little" value={<span className="text-[22px]">{money(v.low)}<span className="text-fg-mute font-normal text-[14px]"> to </span>{money(v.high)}</span>} tone="brand" sub="per hospital, per year · assumption above" />
        <Stat label="US hospitals" value={num(v.segment.establishments)} sub="starting segment · BLS NAICS 622" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card className="min-w-0">
          <CardHeader title="Unit costs" sub="Late dose, overtime shift, absence day, quit, injury. Every input has a source or is marked as an assumption or client-entered. Edit any value; the board and this page recompute."
            right={<CsvButton filename="unit_costs.csv" rows={() => Object.entries(costs.data!).map(([k, c]) => ({ key: k, label: c.label, value: c.value, unit: c.unit, kind: c.kind, source: c.source, note: c.note }))} />} />
          {Object.entries(costs.data).map(([k, c]) => <CostRow key={k + c.value} k={k} c={c} onSave={save} />)}
        </Card>
        <div className="min-w-0 space-y-6">
          <Card className="min-w-0">
            <CardHeader title="Pricing hypothesis (SaaS, per hospital per month)"
              sub={pricing ? `An assumption from the Oct 27, 2026 benchmark research, positioned between what hospitals pay for engagement surveys and for systems of record; a hypothesis until a pilot, not a validated price` : 'To be positioned against what hospitals already pay for operations software; not a validated price'}
              right={<Badge tone="warn">Hypothesis</Badge>} />
            {pricing && price && tier ? (
              <>
                <div className="text-[32px] font-semibold tnum tracking-tight">{money(price)}<span className="text-[14px] font-normal text-fg-mute"> per hospital / month</span></div>
                <div className="text-[12.5px] text-fg-mute">up to {num(tier.up_to_staff)} nursing and support staff · annual term</div>
                <p className="mt-2 text-[13px] leading-snug text-fg-soft">{pct(shareLow)} of the low value case and {pct(shareHigh)} of the high case ({money(v.low)} to {money(v.high)} a year at {num(v.headcount)} staff), so the hospital keeps {pct(shareLow == null ? null : 1 - shareLow)} to {pct(shareHigh == null ? null : 1 - shareHigh)} of the value.</p>
                <dl className="mt-3 grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                  <dt className="text-fg-mute">Per staff member</dt><dd className="tnum">{money(perStaff)} a year</dd>
                  {perUnit != null && span && <><dt className="text-fg-mute">Per unit team</dt><dd className="tnum">about {money(perUnit)} a month <span className="text-fg-mute">(AONL median span of control, {span.n})</span></dd></>}
                  {topTier != null && <><dt className="text-fg-mute">Above {num(topTier)} staff</dt><dd>{pricing.above}</dd></>}
                  <dt className="text-fg-mute">Replaces</dt><dd>{money(floor)} a month (10% of the low case), the earlier working figure, which sat inside the engagement-survey band</dd>
                </dl>
                <p className="mt-3 text-[12px] leading-snug text-fg-mute">{pricing.basis}</p>
                {pricing.usage_based && <p className="mt-1 text-[12px] leading-snug text-fg-mute">Usage-based part: {pricing.usage_based}.</p>}
                {pricing.to_confirm && <p className="mt-1 text-[12px] text-fg-mute">{pricing.to_confirm}.</p>}
              </>
            ) : pricing && topTier != null ? (
              <>
                <div className="text-[24px] font-semibold tracking-tight">{pricing.above[0].toUpperCase() + pricing.above.slice(1)}<span className="text-[14px] font-normal text-fg-mute"> above {num(topTier)} staff</span></div>
                <p className="mt-2 text-[12.5px] text-fg-soft">Tiers: {pricing.tiers.map((t) => `${money(t.monthly_usd)} a month up to ${num(t.up_to_staff)} staff`).join('; ')}. {pricing.basis}</p>
              </>
            ) : (
              <>
                <div className="text-[32px] font-semibold tnum tracking-tight">{money(floor)}<span className="text-[14px] font-normal text-fg-mute"> per hospital / month</span></div>
                <p className="mt-2 text-[12.5px] text-fg-soft">Working figure: 10% of the low value case ({money(v.low)} a year), so a hospital keeps about 90% of the value it gets even in the conservative scenario.</p>
              </>
            )}
            <dl className="mt-4 grid grid-cols-[100px_1fr] gap-y-2 border-t border-border pt-3 text-[12.5px]">
              <dt className="text-fg-mute">User</dt><dd>Unit nurse manager or charge nurse</dd>
              <dt className="text-fg-mute">Buyer</dt><dd>Chief Nursing Officer; HR / people analytics</dd>
              <dt className="text-fg-mute">Data owners</dt><dd>HR (survey export) · Pharmacy and nursing informatics (eMAR) · Timekeeping · HRIS · Employee health</dd>
              <dt className="text-fg-mute">Pilot test</dt><dd>Can one hospital fill the monthly template in under a day? If not, stop.</dd>
            </dl>
            <div className="mt-4 border-t border-border pt-3">
              <div className="flex items-center justify-between"><span className="label">Comparable software, what it charges</span>{bmCount > 0 && <Badge tone="info">{bmCount} sourced</Badge>}</div>
              <Benchmarks rows={v.benchmarks} note={v.benchmarks_note} />
            </div>
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
