import { useNavigate } from 'react-router-dom'
import { api, KPI_ORDER, type Board as B, type Kpi, type TeamRow } from '../lib/api'
import { money, monthRange, num, pts, pval } from '../lib/format'
import { useLoad, useStore } from '../lib/store'
import Spark from '../components/Spark'
import { Card, Chip, ErrorNote, Eyebrow, How, Loading, PageTitle, Stat, StatusChip } from '../components/ui'

const SHORT: Record<Kpi, string> = { late_departures: 'Late departures', absence_days: 'Absence days', quits: 'Quits', injuries: 'Injuries', rework: 'Rework' }

function headline(b: B) {
  const top = b.teams.find((t) => t.status === 'red')
  if (!top) return { title: <>No team at {b.site} is outside normal variation in {monthRange(b.window)}.</>, team: null }
  const k = (top.elevated ?? [])[0]
  const e = k ? top.excess_by_kpi[k] : undefined
  return {
    team: top,
    title: (
      <>
        <span className="text-rust">{top.team_name}</span> is running{' '}
        {e ? <><span className="num">{num(e.count)}</span> {SHORT[k!].toLowerCase()} above</> : 'above'} comparable {top.shift.toLowerCase()} teams
        {top.excess_cost > 0 && <> — about <span className="num">{money(top.excess_cost)}</span> this quarter</>}, and its engagement fell at the same time.
      </>
    ),
  }
}

function TeamCard({ t, onOpen }: { t: TeamRow; onOpen: () => void }) {
  if (t.status === 'rolled_up') {
    return (
      <Card className="p-5 opacity-80">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-serif text-[1.2rem] font-semibold">{t.team_name}</div>
            <div className="text-[13px] text-ink-mute">{t.shift} shift · {t.headcount} people</div>
          </div>
          <StatusChip s="rolled_up" />
        </div>
        <p className="mt-6 text-[13.5px] text-ink-mute">Fewer than 4 people. Counted in the site totals only, so no one on this team can be identified.</p>
      </Card>
    )
  }
  const drop = t.engagement?.biggest_drop
  const hot = t.status === 'red'
  return (
    <button onClick={onOpen} className="text-left group">
      <Card tone={hot ? 'rust' : t.status === 'amber' ? undefined : undefined} className={`p-5 h-full transition-all group-hover:shadow-lift group-hover:-translate-y-0.5 ${hot ? 'ring-1 ring-rust/25' : ''}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-serif text-[1.25rem] font-semibold leading-tight">{t.team_name}</div>
            <div className="text-[13px] text-ink-mute">{t.shift} shift · {t.headcount} people</div>
          </div>
          <StatusChip s={t.status} />
        </div>

        <div className="mt-4 flex items-end justify-between">
          <div>
            <div className={`num text-[1.9rem] leading-none ${t.excess_cost > 0 ? 'text-ink' : 'text-ink-mute'}`}>{money(t.excess_cost)}</div>
            <div className="text-[12px] text-ink-mute mt-1">excess operating cost, 3 months</div>
          </div>
          <div className="text-right text-[12.5px] text-ink-soft max-w-[48%]">{t.signal}</div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-3">
          {(['late_departures', 'absence_days', 'quits'] as Kpi[]).map((k) => {
            const e = t.excess_by_kpi[k]
            return (
              <div key={k}>
                <div className={`text-[11px] font-semibold ${e?.flagged ? 'text-rust' : 'text-ink-mute'}`}>{SHORT[k]}</div>
                <Spark data={t.spark[k] ?? []} flagged={e?.flagged} />
                <div className="text-[11.5px] text-ink-mute tab">
                  {e?.judgeable === false ? 'too rare to judge' : e?.flagged ? <span className="text-rust font-semibold">+{num(e.count)} vs expected</span> : 'normal'}
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-3 border-t border-line pt-3 text-[13px] flex items-baseline justify-between gap-3">
          {drop ? (
            <>
              <span className="text-ink-soft truncate">Biggest item change: <b className="text-ink">{drop.label}</b></span>
              <span className={`num whitespace-nowrap ${drop.significant ? 'text-rust' : 'text-ink-mute'}`}>{pts(drop.delta)}</span>
            </>
          ) : (
            <span className="text-ink-mute">Engagement change hidden: a wave has fewer than 4 respondents.</span>
          )}
        </div>
      </Card>
    </button>
  )
}

export default function Board() {
  const { siteId, asOf, setTeamId } = useStore()
  const nav = useNavigate()
  const { data: b, error, loading } = useLoad(() => api.board(siteId, asOf), [siteId, asOf])
  if (error) return <ErrorNote error={error} />
  if (loading || !b) return <Loading label="Reading the site's operating records" />
  const h = headline(b)
  const reds = b.teams.filter((t) => t.status === 'red').length
  const rolled = b.teams.filter((t) => t.status === 'rolled_up').length
  const open = (t: TeamRow) => { setTeamId(t.team_id); nav(`/why/${t.team_id}`) }

  return (
    <div>
      <PageTitle step="01" kicker={`Detect · ${b.site} · ${monthRange(b.window)}`} title={h.title}
        lede="The client's own operating records, compared with teams on the same shift at the other sites. Only what exceeds normal variation is counted — noise is not a finding." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 border-y border-line py-6 mb-10 stagger">
        <Stat label="Excess operating cost" value={money(b.total_excess)} sub={`${monthRange(b.window)} · above comparable teams`} tone={b.total_excess > 0 ? 'rust' : 'ink'} />
        <Stat label="Annualized" value={money(b.annualized, true)} sub="if the pattern held for a year" />
        <Stat label="Teams to look at" value={reds} sub="operations and engagement both moved" />
        <Stat label="Rolled up for privacy" value={rolled} sub="teams under 4 people" />
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-6">
        <Eyebrow className="mr-2">Where the excess sits</Eyebrow>
        {KPI_ORDER.filter((k) => b.counts_by_kpi[k] > 0).map((k) => (
          <Chip key={k} kind="computed">{SHORT[k]}: {num(b.counts_by_kpi[k])}{b.by_kpi[k] > 0 ? ` · ${money(b.by_kpi[k])}` : ''}</Chip>
        ))}
        {KPI_ORDER.every((k) => !b.counts_by_kpi[k]) && <span className="text-sm text-ink-mute">nothing above normal variation</span>}
        <span className="ml-auto">
          <How>
            <b>Detect, in one sentence:</b> for each team and KPI, we compare the observed count with the count predicted by comparable teams' rate
            (same shift, other sites) and flag it only if a Poisson test gives {pval(b.rules.ops_p).replace('p = ', 'p < ')}.
            Engagement counts as moved only if the biggest item drop is at least {Math.abs(b.rules.item_drop).toFixed(2)} points
            <i> and</i> passes a Welch t-test corrected for choosing the worst of 12 items. KPIs expected to occur fewer than {b.rules.min_expected} times
            in three months are marked "too rare to judge." Dollars use the unit costs on the Business case page.
          </How>
        </span>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3 stagger">
        {b.teams.map((t) => <TeamCard key={t.team_id} t={t} onOpen={() => open(t)} />)}
      </div>
    </div>
  )
}
