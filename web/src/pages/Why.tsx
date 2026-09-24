import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, KPI_ORDER, type Assoc, type AskResult, type Kpi, type Why as W } from '../lib/api'
import { money, monthRange, num, per10, pts, pval, signed } from '../lib/format'
import { useLoad, useStore } from '../lib/store'
import { ItemChanges, LinkScatter, QuartileBars, TrendChart } from '../components/charts'
import { Button, Card, Chip, ErrorNote, Eyebrow, How, Loading, PageTitle, StatusChip } from '../components/ui'

const SHORT: Record<Kpi, string> = { late_departures: 'Late departures', absence_days: 'Absence days', quits: 'Quits', injuries: 'Injuries', rework: 'Rework' }
const ITEMS_SHOWN = ['grand', 'q01', 'q02', 'q03', 'q04', 'q05', 'q06', 'q07', 'q08', 'q09', 'q10', 'q11', 'q12']

function title(w: W) {
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const drops = w.item_changes.filter((c) => c.delta <= -0.3).slice(0, 2)
  const name = `${w.team.site} ${w.team.team_name}`
  if (!flagged.length && !drops.length) return <>{name}: nothing here moved beyond normal variation.</>
  const k = flagged[0]
  const e = k ? w.excess![k]! : null
  return (
    <>
      {name}: {e ? <><span className="text-rust">{SHORT[k].toLowerCase()} ran {(e.rate / Math.max(e.baseline, 1e-9)).toFixed(1)}×</span> comparable teams</> : 'operations stayed normal'}
      {drops.length > 0 && <> while <span className="text-rust">{drops.map((d) => `“${d.label}”`).join(' and ')}</span> fell</>}.
    </>
  )
}

function VerdictCell({ a, on, onClick }: { a?: Assoc; on: boolean; onClick: () => void }) {
  if (!a) return <td />
  const cls = a.verdict === 'association' ? 'bg-teal text-white' : a.verdict === 'too rare to test' ? 'bg-paper-deep text-ink-mute' : 'bg-paper-card text-ink-mute'
  const sym = a.verdict === 'association' ? '●' : a.verdict === 'too rare to test' ? '·' : '○'
  return (
    <td className="p-0.5">
      <button onClick={onClick} title={`${a.verdict}${a.slope != null ? `, slope ${a.slope}` : ''}`}
        className={`h-7 w-full rounded-md text-[11px] border ${on ? 'border-rust ring-2 ring-rust/30' : 'border-line'} ${cls}`}>{sym}</button>
    </td>
  )
}

function Linkage({ w, meta }: { w: W; meta: Record<string, string> }) {
  // open on the strongest link among this team's dropped items and elevated KPIs; fall back to the first pair
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const found = [...w.links].filter((l) => l.verdict === 'association' && (!flagged.length || flagged.includes(l.kpi)))
    .sort((a, b) => (a.p ?? 1) - (b.p ?? 1))[0]
  const firstDrop = w.item_changes.find((c) => c.delta <= -0.3)?.item ?? 'grand'
  const [sel, setSel] = useState<{ kpi: Kpi; item: string }>(found ? { kpi: found.kpi, item: found.item } : { kpi: flagged[0] ?? 'late_departures', item: firstDrop })
  const grid = useLoad(() => api.links(), [])
  const one = useLoad(() => api.link(sel.kpi, sel.item), [sel.kpi, sel.item])
  const a = one.data?.association
  const q = one.data?.quartile
  const label = (it: string) => (it === 'grand' ? 'Overall' : it.toUpperCase())
  return (
    <Card className="p-6 lg:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <Eyebrow>Is this bigger than one team?</Eyebrow>
          <h2 className="font-serif text-[1.55rem] font-semibold mt-1">Across all {q?.n_cells ?? '…'} reportable team-waves, which engagement items move with which operating KPIs</h2>
        </div>
        <Chip kind="synthetic">Association, not cause</Chip>
      </div>
      <p className="text-ink-soft mt-2 max-w-3xl text-[14.5px]">
        This is the comparison Gallup delivers today as a once-a-year Business Impact Analysis. Here it runs on the client's own records, every month, down to the team.
      </p>

      <div className="mt-6 grid gap-8 xl:grid-cols-[1.05fr_1fr]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-separate border-spacing-0 text-[12px]">
            <thead>
              <tr><th className="text-left font-semibold text-ink-mute pb-1.5 w-[120px]">KPI \ item</th>
                {ITEMS_SHOWN.map((it) => <th key={it} className={`pb-1.5 font-semibold ${it === sel.item ? 'text-rust' : 'text-ink-mute'}`} title={meta[it]}>{label(it)}</th>)}</tr>
            </thead>
            <tbody>
              {KPI_ORDER.map((k) => (
                <tr key={k}>
                  <td className={`pr-2 py-0.5 font-semibold whitespace-nowrap ${k === sel.kpi ? 'text-rust' : 'text-ink-soft'}`}>{SHORT[k]}</td>
                  {ITEMS_SHOWN.map((it) => (
                    <VerdictCell key={it} a={grid.data?.find((x) => x.kpi === k && x.item === it)} on={k === sel.kpi && it === sel.item} onClick={() => setSel({ kpi: k, item: it })} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex gap-4 mt-3 text-[12px] text-ink-mute">
            <span><span className="text-teal">●</span> association (95% CI excludes zero)</span><span>○ none detected</span><span>· too rare to test</span>
          </div>
          <p className="mt-2 text-[12px] text-ink-mute max-w-xl">
            {grid.data ? `${grid.data.filter((x) => x.slope != null).length} pairs tested; at 95% confidence about ${Math.round(grid.data.filter((x) => x.slope != null).length * 0.05)} would light up by chance. ` : ''}
            Treat a single lit cell as a lead to check, not a finding. A link that also shows up in this team's own records and comments is stronger.
          </p>
          {q && (
            <div className="mt-6">
              <div className="flex items-baseline justify-between">
                <Eyebrow>{SHORT[sel.kpi]} per 10 people per month, by {sel.item === 'grand' ? 'overall engagement' : sel.item.toUpperCase()} quartile</Eyebrow>
                {q.pct_diff != null && <span className="text-[13px]"><b className="num">{num(Math.abs(q.pct_diff))}%</b> {q.pct_diff >= 0 ? 'lower' : 'higher'} in the top quartile</span>}
              </div>
              <QuartileBars q={q} />
            </div>
          )}
        </div>

        <div>
          <div className="flex items-baseline justify-between">
            <Eyebrow>{SHORT[sel.kpi]} vs “{meta[sel.item]}”</Eyebrow>
            <span className="text-[12px] text-ink-mute"><span className="text-rust">◆</span> {w.team.team_name}</span>
          </div>
          {one.loading || !a ? <Loading /> : a.verdict === 'too rare to test' ? (
            <p className="py-20 text-center text-ink-mute">Too rare to test: most team-quarters have zero events. Needs a year or more of history.</p>
          ) : <LinkScatter a={a} teamId={w.team.team_id} xLabel={sel.item === 'grand' ? 'Overall engagement (1–5)' : `${sel.item.toUpperCase()} mean (1–5)`} />}
          {a && a.slope != null && (
            <div className="mt-3 rounded-xl bg-paper-deep/70 px-4 py-3 text-[13.5px] leading-relaxed">
              <b>{a.verdict === 'association' ? 'Association found.' : 'No association detected.'}</b>{' '}
              Each 1-point lower score goes with <b className="num">{per10(Math.abs(a.slope))}</b> {a.slope < 0 ? 'more' : 'fewer'} {SHORT[sel.kpi].toLowerCase()} per 10 people a month
              {' '}(95% CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}, {pval(a.p)}; {a.n_cells} team-waves, {a.n_teams} teams).{' '}
              <How>OLS of the team's KPI rate (the quarter the survey closed in) on the item mean. Each team appears twice, once per wave, so standard errors are clustered by team. Team-waves with fewer than 4 respondents are excluded. With 24 teams this detects strong links only; a null here means "not detectable at this size," not "no link."</How>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

function Behind({ w }: { w: W }) {
  const [r, setR] = useState<AskResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    // rules mode: the same evidence engine as the Ask page, without the model-written brief, so this stays instant
    api.ask(`Why did the ${w.team.site} ${w.team.team_name} team's scores drop?`, true).then(setR).catch((e) => setErr(String(e.message)))
  }, [w.team.site, w.team.team_name])
  if (err) return <ErrorNote error={err} />
  if (!r) return <Loading label="Reading comments and documents" />
  const mix = r.evidence.find((e) => e.kind === 'tenure_mix' || e.kind === 'signal_check')
  const themes = r.evidence.find((e) => e.kind === 'comment_themes')
  const comments = r.evidence.filter((e) => e.kind === 'comment').slice(0, 3)
  const owner = r.evidence.find((e) => e.kind === 'owner')
  const ops = r.evidence.find((e) => e.kind === 'ops_hour')
  const quote = (s: string) => { const m = s.match(/"(.+)"/); return m ? m[1] : s }
  return (
    <Card className="p-6 lg:p-8" tone="ink">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <Eyebrow>What's behind it</Eyebrow>
          <h2 className="font-serif text-[1.55rem] font-semibold mt-1">{r.assessment?.label ?? r.message}</h2>
        </div>
        <Chip kind={r.mode === 'model' ? 'model' : 'computed'}>{r.mode === 'model' ? 'model-written' : 'rules mode'} · {r.seconds}s</Chip>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div>
          <Eyebrow className="mb-2">Is the drop real?</Eyebrow>
          <p className="text-[14px] text-ink-soft">{mix?.statement ?? 'No signal check available.'}</p>
          {ops && <><Eyebrow className="mt-4 mb-2">Operating detail</Eyebrow><p className="text-[14px] text-ink-soft">{ops.statement}</p></>}
        </div>
        <div>
          <Eyebrow className="mb-2">What employees wrote</Eyebrow>
          {themes && <p className="text-[13px] text-ink-mute mb-3">{themes.statement}</p>}
          <ul className="space-y-3">
            {comments.map((c) => (
              <li key={c.id} className="border-l-2 border-rust/60 pl-3 font-serif italic text-[15px] leading-snug">“{quote(c.statement)}”</li>
            ))}
          </ul>
        </div>
        <div>
          <Eyebrow className="mb-2">Who owns the fix</Eyebrow>
          <p className="text-[14px]">{owner?.statement ?? 'No process owner matched.'}</p>
          <Eyebrow className="mt-4 mb-2">Reasons for the verdict</Eyebrow>
          <ul className="list-disc pl-4 text-[13.5px] text-ink-soft space-y-1">{(r.assessment?.reasons ?? []).slice(0, 4).map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      </div>
    </Card>
  )
}

export default function Why() {
  const { teamId } = useParams()
  const id = Number(teamId)
  const { asOf, meta, setTeamId } = useStore()
  const nav = useNavigate()
  const [k, setK] = useState<Kpi | null>(null)
  useEffect(() => { if (id) setTeamId(id) }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  const { data: w, error, loading } = useLoad(() => api.why(id, asOf), [id, asOf])
  if (error) return <ErrorNote error={error} />
  if (loading || !w) return <Loading />

  if (w.suppressed) {
    return (
      <div>
        <PageTitle step="02" kicker={`Explain · ${w.team.site} ${w.team.team_name}`} title="This team is too small to report on its own." lede={w.reason} />
        <Card className="p-8 max-w-2xl"><p>Its survey answers and operating counts are included in the {w.team.site} site totals. Showing them separately would let anyone identify the people on it — Gallup's reporting threshold is 4.</p>
          <div className="mt-6"><Button kind="ghost" onClick={() => nav('/')}>Back to the site board</Button></div></Card>
      </div>
    )
  }

  const kpi: Kpi = k ?? (KPI_ORDER.find((x) => w.excess?.[x]?.flagged) ?? 'late_departures')
  const e = w.excess?.[kpi]
  const marks = [{ m: '2026-03', label: 'Wave 1' }, { m: '2026-09', label: 'Wave 2' }].filter((x) => w.kpi_trend.some((d) => d.month === x.m))
  return (
    <div>
      <PageTitle step="02" kicker={`Explain · ${w.team.site} ${w.team.team_name} · ${w.team.headcount} people`} title={title(w)}
        lede="Operating records and survey results side by side, then the same comparison across every team — so the manager sees whether this is a pattern or a one-off." />

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr] stagger">
        <Card className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3"><Eyebrow>Operating KPIs · per 10 people per month</Eyebrow>{w.status && <StatusChip s={w.status} />}</div>
            <div className="flex flex-wrap gap-1">
              {KPI_ORDER.map((x) => (
                <button key={x} onClick={() => setK(x)}
                  className={`rounded-full px-2.5 py-1 text-[12px] font-semibold border ${x === kpi ? 'bg-ink text-paper border-ink' : w.excess?.[x]?.flagged ? 'border-rust/50 text-rust' : 'border-line text-ink-soft hover:border-ink-mute'}`}>
                  {SHORT[x]}
                </button>
              ))}
            </div>
          </div>
          <TrendChart data={w.kpi_trend} k={kpi} window={w.window} marks={marks} teamLabel={w.team.team_name} />
          {e && (
            <p className="text-[13.5px] text-ink-soft mt-2">
              {monthRange(w.window ?? [])}: <b className="text-ink">{num(e.observed)}</b> observed vs <b className="text-ink">{num(e.expected, 1)}</b> expected from comparable teams
              {e.judgeable ? <> ({pval(e.p)}){e.flagged ? <> — <span className="text-rust font-semibold">above normal variation{e.dollars > 0 && `, ${money(e.dollars)}`}</span></> : ' — within normal variation'}</> : ' — too rare to judge in three months'}.
            </p>
          )}
        </Card>

        <Card className="p-6">
          <div className="flex items-baseline justify-between">
            <Eyebrow>Survey · wave 1 → wave 2</Eyebrow>
            <span className="text-[12px] text-ink-mute">n = {w.engagement?.n_w1} → {w.engagement?.n_w2}</span>
          </div>
          {w.item_changes.length ? <div className="mt-4"><ItemChanges items={w.item_changes} /></div>
            : <p className="mt-6 text-ink-mute">{w.reason}</p>}
          {w.engagement?.biggest_drop && (
            <p className="text-[12.5px] text-ink-mute mt-4">
              Adjusted for who responded, the largest change is {pts(w.engagement.biggest_drop.delta)} ({pval(w.engagement.biggest_drop.p)}; threshold p &lt; 0.0042 after choosing the worst of 12).
            </p>
          )}
        </Card>
      </div>

      <div className="mt-6 space-y-6">
        <Linkage w={w} meta={meta?.items ?? {}} />
        <Behind w={w} />
      </div>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
        <p className="text-ink-soft max-w-xl">Everything above is computed from the client's data. The next step needs a person: choose what to try, who owns it, and when to check.</p>
        <Button kind="person" onClick={() => nav(`/plan/${w.team.team_id}`)}>Draft a plan for this team →</Button>
      </div>
    </div>
  )
}
