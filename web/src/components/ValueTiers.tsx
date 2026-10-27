import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import type { PlanValue, ValueInput, ValueTier } from '../lib/value'
import { money, num } from '../lib/format'
import { Badge, Button, Card, Details, cx } from './ui'

/** The money block on Review (Oct 27, 2026 round). Three tiers from `app/impact.py` `value_of_plan`, each with its
 *  assumption printed next to the number and its inputs one click away. Full dollars; nothing is typed in here. */

const KIND: Record<ValueTier['kind'], { chip: string; tone: 'brand' | 'info' | 'neutral'; plain: string }> = {
  measured: { chip: 'Measured', tone: 'brand', plain: 'Computed from this unit’s records: the established effect only.' },
  projection: { chip: 'Projection', tone: 'info', plain: 'Published, correlational evidence applied to this unit. Association, not cause.' },
  scenario: { chip: 'Scenario', tone: 'neutral', plain: 'The Business case assumption for a whole hospital.' },
}

const fmtInput = (i: ValueInput) => {
  const v = i.value
  if (Array.isArray(v)) return v.map((x) => (x < 1 ? `${Math.round(x * 100)}%` : num(x))).join(' to ')
  if (typeof v === 'number') return i.label.toLowerCase().startsWith('cost') || /replacing|injury|separation/i.test(i.label) ? money(v) : v < 1 ? `${(v * 100).toFixed(1)}%` : num(v)
  return String(v)
}
const KIND_LABEL: Record<string, string> = { sourced: 'sourced', assumption: 'assumption', client_entered: 'client-entered (fictional)', none: 'no source' }

function Inputs({ inputs }: { inputs: ValueInput[] }) {
  return (
    <dl className="grid grid-cols-1 gap-y-2 text-[12.5px]">
      {inputs.map((i, n) => (
        <div key={n} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3">
          <dt className="text-fg-soft">{i.label}{i.kind && <span className="text-fg-faint"> · {KIND_LABEL[i.kind] ?? i.kind}</span>}
            <div className="text-[11.5px] leading-snug text-fg-mute">{i.source}</div></dt>
          <dd className="tnum font-medium text-fg text-right whitespace-nowrap">{fmtInput(i)}</dd>
        </div>
      ))}
    </dl>
  )
}

function Figure({ t }: { t: ValueTier }) {
  const big = 'font-semibold tracking-[-0.02em] tnum leading-none'
  if (t.kind === 'measured') return <div className={cx(big, 'text-[34px] text-fg')}>{money(t.dollars)}</div>
  return (
    <div>
      <div className={cx(big, 'text-[32px] text-fg')}>{money(t.low)}</div>
      <div className={cx(big, 'mt-1 text-[22px] text-fg-soft')}><span className="text-[14px] font-normal text-fg-mute">to </span>{money(t.high)}</div>
    </div>
  )
}

function Tier({ t, lead }: { t: ValueTier; lead?: boolean }) {
  const nav = useNavigate()
  const k = KIND[t.kind]
  return (
    <Card className={cx('flex flex-col', lead && 'ring-2 ring-brand/15')}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="eyebrow">{t.label}</span>
        <Badge tone={k.tone} className="!text-[11px]" dot>{k.chip}</Badge>
      </div>
      <div className="mt-3"><Figure t={t} /></div>
      <p className="mt-3 text-[13.5px] leading-snug text-fg-soft">{t.sentence}</p>
      {t.kind === 'measured' && t.excluded.length > 0 && (
        <p className="mt-2 text-[12px] text-fg-mute">Not counted: {t.excluded.map((e) => e.kpi_label.toLowerCase().replace(/\s*\(.*?\)/g, '')).join(', ')}: {t.excluded.every((e) => e.verdict === 'inconclusive') ? 'the 95% interval includes zero (two months is short for these)' : t.excluded.map((e) => e.why.split(' (')[0]).filter((x, i, a) => a.indexOf(x) === i).join('; ')}.</p>
      )}
      {t.kind === 'measured' && t.dollars > 0 && t.dollars < 10000 && <p className="mt-1 text-[12px] text-fg-mute">{t.small_because}</p>}
      {t.kind === 'projection' && (
        <>
          <p className="mt-2 text-[12.5px] leading-snug text-fg-mute">{t.condition}</p>
          {!t.in_range && <p className="mt-2 rounded-md bg-warn-50 px-2 py-1 text-[12px] text-warn-700">Outside the plausible range for one unit ({t.sane_range[0]} to {t.sane_range[1]} quits a year); shown for transparency, not for the deck.</p>}
        </>
      )}
      {t.kind === 'scenario' && <p className="mt-2 text-[12.5px] leading-snug text-fg-mute">{t.condition}</p>}
      <div className="mt-auto pt-4">
        <Details summary={<span>Inputs and assumptions ({t.inputs.length})</span>}>
          <Inputs inputs={t.inputs} />
          {t.kind === 'projection' && t.mechanism.length > 0 && (
            <div className="mt-3 border-t border-border pt-3 text-[12px] text-fg-mute">
              <b className="text-fg-soft">Mechanism in this data</b> (OLS over {t.mechanism[0].n_cells} unit-waves, SEs clustered by team):{' '}
              {t.mechanism.map((m) => `${m.kpi.replace('_', ' ')} vs ${t.focus.item}: ${m.verdict}${m.slope != null ? ` (slope ${m.slope}, 95% CI ${m.ci_low} to ${m.ci_high})` : ''}`).join('; ')}. Not used in the figure above.
            </div>
          )}
        </Details>
        {t.kind === 'scenario' && <div className="mt-3"><Button variant="secondary" size="sm" icon={<ArrowRight size={14} />} onClick={() => nav(t.link)}>Business case</Button></div>}
      </div>
    </Card>
  )
}

export default function ValueTiers({ v, improved }: { v: PlanValue; improved: boolean }) {
  return (
    <section aria-labelledby="worth-h" className="mb-6">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div>
          <h2 id="worth-h" className="text-[20px] font-semibold tracking-[-0.01em] text-fg">What it is worth</h2>
          <p className="mt-0.5 text-[13.5px] text-fg-mute">
            {improved ? 'Three figures, each with its assumption. The measured one is small by construction; the retention value is where the money is.'
              : 'The plan has no established effect yet, so nothing is measured. The projection and the hospital scenario show what a working plan would be worth.'}
          </p>
        </div>
        <span title={v.illustrative_reason}><Badge tone="neutral" className="!whitespace-normal text-left">Illustrative · synthetic follow-up months</Badge></span>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 stagger">
        {v.tiers.map((t) => <Tier key={t.id} t={t} lead={t.id === 'projected'} />)}
      </div>
    </section>
  )
}
