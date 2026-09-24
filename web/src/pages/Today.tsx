import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowRight, CalendarClock, CheckCircle2, ClipboardList, DollarSign, Eye, Users } from 'lucide-react'
import { api, KPI_ORDER, type Board, type Did, type Plan, type TeamRow } from '../lib/api'
import { dataThrough, longDate, money, monthRange, num, signed } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { PERSONA, useLoad, useStore, visiblePlans } from '../lib/store'
import { Spark } from '../components/charts'
import Journey from '../components/Journey'
import { Badge, Button, Card, CardHeader, Empty, ErrorState, Method, PageHeader, PageSkeleton, Stat, StatusBadge, cx } from '../components/ui'

function AttentionRow({ t, site, onOpen }: { t: TeamRow; site?: string; onOpen: () => void }) {
  const k = (t.elevated ?? [])[0]
  const e = k ? t.excess_by_kpi[k] : undefined
  const drop = t.engagement?.biggest_drop
  return (
    <button onClick={onOpen} className="group grid w-full grid-cols-[4px_minmax(0,1fr)_auto] gap-4 rounded-xl border border-border bg-surface p-4 text-left transition-shadow hover:shadow-pop">
      <span className={cx('rounded-full', t.status === 'red' ? 'bg-crit' : 'bg-warn')} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-[15px]">{site ? `${site} · ` : ''}{t.team_name}</span>
          <StatusBadge s={t.status} />
          <span className="text-[12.5px] text-fg-mute">{t.shift} shift · {t.headcount} people</span>
        </div>
        <p className="mt-1 text-[13.5px] text-fg-soft">
          {e ? <><b className="text-fg">{num(e.observed)}</b> {KPI_SHORT[k!].toLowerCase()} vs <b className="text-fg">{num(e.expected)}</b> expected from comparable teams</> : 'Operations within normal range'}
          {drop?.significant && <> · <b className="text-fg">“{drop.label}”</b> {signed(drop.delta)} pts</>}
          {!drop?.significant && t.status === 'amber' && drop && <> · survey change not beyond noise</>}
        </p>
      </div>
      <div className="flex items-center gap-4">
        {k && t.spark[k] && <div className="hidden md:block"><Spark data={t.spark[k]!} flagged /></div>}
        <div className="text-right hidden sm:block">
          <div className="tnum font-semibold">{t.excess_cost > 0 ? money(t.excess_cost) : '—'}</div>
          <div className="text-[11.5px] text-fg-mute">excess, 3 mo</div>
        </div>
        <ArrowRight size={18} className="text-fg-faint group-hover:text-fg" />
      </div>
    </button>
  )
}

function PlanRow({ p, r }: { p: Plan; r: Did | null }) {
  const nav = useNavigate()
  const total = (new Date(p.review).getTime() - new Date(p.start).getTime()) / 864e5
  const left = r?.status === 'not_reached' ? r.days_to_go ?? 0 : 0
  const pct = Math.max(4, Math.min(100, ((total - left) / total) * 100))
  return (
    <button onClick={() => nav(`/impact/${p.id}`)} className="w-full text-left rounded-xl border border-border p-4 hover:shadow-pop transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium text-[14px]">{p.team_label}</div>
          <div className="text-[12.5px] text-fg-mute line-clamp-2">{p.obstacle}</div>
        </div>
        {r?.status === 'ok' ? <Badge tone={r.verdict === 'worked' ? 'ok' : 'warn'} dot>Review: {r.verdict}</Badge> : <Badge tone="info" dot>In progress</Badge>}
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-canvas overflow-hidden"><div className={cx('h-full rounded-full', r?.status === 'ok' ? 'bg-ok' : 'bg-brand')} style={{ width: `${pct}%` }} /></div>
      <div className="mt-1.5 flex justify-between text-[11.5px] text-fg-mute"><span>{r?.status === 'not_reached' && (r.days_to_go ?? 0) > total ? `Starts ${longDate(p.start)}` : `Started ${longDate(p.start)}`}</span><span>{r?.status === 'not_reached' ? `${r.days_to_go} days to review` : `Reviewed ${longDate(p.review)}`}</span></div>
    </button>
  )
}

function ManagerToday() {
  const { siteId, asOf, role } = useStore()
  const nav = useNavigate()
  const board = useLoad(() => api.board(siteId, asOf), [siteId, asOf])
  const pr = useLoad(async () => {
    const ps = visiblePlans(await api.plans(), asOf)
    const rs = await Promise.all(ps.map((p) => api.result(p.id, asOf)))
    return ps.map((p, i) => ({ p, r: rs[i] }))
  }, [asOf])
  if (board.error) return <ErrorState error={board.error} />
  if (!board.data || !pr.data) return <PageSkeleton />
  const b: Board = board.data
  const attention = b.teams.filter((t) => t.status === 'red' || t.status === 'amber')
  const reds = b.teams.filter((t) => t.status === 'red')
  const active = pr.data.filter(({ p }) => b.teams.some((t) => t.team_id === p.team_id))
  const main = active.find((x) => x.r.status === 'ok') ?? active[active.length - 1]
  const r: Did | null = main?.r ?? null
  const reviewReady = r?.status === 'ok'
  const top = reds[0]
  const topK = top ? (top.elevated ?? [])[0] : undefined

  const headline = reviewReady && r?.verdict === 'worked'
    ? <>{main?.p.team_label}'s plan worked: {r.kpi_label.toLowerCase()} fell <b>{Math.abs((r.estimate ?? 0) * 10).toFixed(1)} per 10 people a month</b> more than at comparable teams. {reds.length === 0 ? 'No team needs attention.' : ''}</>
    : top && topK
      ? <><b>{top.team_name}</b> needs attention: {KPI_SHORT[topK].toLowerCase()} are running {((top.excess_by_kpi[topK]!.observed) / Math.max(1, top.excess_by_kpi[topK]!.expected)).toFixed(1)}× what comparable teams would predict, and engagement fell at the same time.</>
      : <>No team is outside normal variation in {monthRange(b.window)}.</>

  return (
    <div>
      <Journey at="detect" teamId={top?.team_id ?? main?.p.team_id} planId={main?.p.id} />
      <PageHeader
        crumbs={<>{b.site} DC · {role === 'manager' ? 'your site' : 'selected site'} · {dataThrough(b.window)}</>}
        title={<>Good morning, {PERSONA[role].name.split(' ')[0]}</>}
        sub={headline}
        actions={reviewReady
          ? <Button variant="primary" onClick={() => nav(`/impact/${main?.p.id}`)} icon={<CheckCircle2 size={16} />}>See the review</Button>
          : top ? <Button variant="primary" onClick={() => nav(`/teams/${top.team_id}`)} icon={<Eye size={16} />}>Investigate {top.team_name}</Button> : undefined}
      />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
        <Stat label="Excess operating cost" value={money(b.total_excess)} icon={<DollarSign size={16} />} tone={b.total_excess > 0 ? 'crit' : undefined}
          sub={<>{monthRange(b.window)} · {money(b.annualized, true)} a year if it held</>} />
        <Stat label="Teams needing attention" value={<>{reds.length}<span className="text-fg-faint text-[18px]"> / {b.teams.length}</span></>} icon={<AlertTriangle size={16} />} tone={reds.length ? 'crit' : 'ok'}
          sub={<>{attention.length - reds.length} to watch · {b.teams.filter((t) => t.status === 'rolled_up').length} rolled up for privacy</>} />
        <Stat label="Active action plans" value={active.length} icon={<ClipboardList size={16} />} sub="approved by a person" />
        <Stat label={reviewReady ? 'Plan review' : 'Next review'} value={reviewReady ? (r?.verdict === 'worked' ? 'Worked' : r?.verdict) : r?.status === 'not_reached' ? `${r.days_to_go} days` : '—'}
          icon={<CalendarClock size={16} />} tone={reviewReady && r?.verdict === 'worked' ? 'ok' : 'brand'} sub={main ? `${main.p.team_label} · ${longDate(main.p.review)}` : 'no plan yet'} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader title="Needs your attention" sub={`Teams whose operating KPIs or engagement moved beyond normal variation · ${monthRange(b.window)}`}
            right={<Method>
              Each team's count is compared with what comparable teams' rate (same shift, other sites) predicts; it is flagged only if a Poisson test gives p &lt; {b.rules.ops_p}.
              Engagement counts as moved only if the biggest item drop is at least {Math.abs(b.rules.item_drop).toFixed(2)} points, adjusted for who responded, and passes a Welch t-test
              corrected for choosing the worst of 12 items (p &lt; {b.rules.item_p}). KPIs expected fewer than {b.rules.min_expected} times in three months are "too rare to judge." Teams under {b.rules.min_n} people are never shown.
            </Method>} />
          {attention.length === 0 ? (
            <Empty icon={<CheckCircle2 size={20} />} title="Nothing outside normal variation" sub={reviewReady ? `${main?.p.team_label} is back within the range of comparable teams after its plan. Open the review to see by how much.` : 'Every team is within the range comparable teams would predict.'}
              action={reviewReady ? <Button variant="secondary" onClick={() => nav(`/impact/${main?.p.id}`)}>Open the review</Button> : undefined} />
          ) : (
            <div className="space-y-3">{attention.map((t) => <AttentionRow key={t.team_id} t={t} onOpen={() => nav(`/teams/${t.team_id}`)} />)}</div>
          )}
          <p className="mt-4 text-[12px] text-fg-faint">Ranks obstacles, not managers. Teams under 4 people are counted in site totals only.</p>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Action plans" sub="One focus item, a few actions, one review date" right={<Button size="sm" variant="ghost" onClick={() => nav('/plans')}>All plans</Button>} />
            {active.length === 0 ? <Empty icon={<ClipboardList size={20} />} title="No active plans" sub="Plans are drafted from a team's evidence and approved by a person." />
              : <div className="space-y-3">{active.map(({ p, r: pr_ }) => <PlanRow key={p.id} p={p} r={pr_} />)}</div>}
          </Card>
          <Card>
            <CardHeader title="Where the excess sits" sub={`${b.site} · ${monthRange(b.window)}`} />
            <ul className="space-y-2.5">
              {KPI_ORDER.map((k) => {
                const n = b.counts_by_kpi[k], d = b.by_kpi[k]
                return (
                  <li key={k} className="flex items-center justify-between text-[13.5px]">
                    <span className="flex items-center gap-2"><span className={cx('h-2 w-2 rounded-full', n > 0 ? 'bg-crit' : 'bg-border-strong')} />{KPI_SHORT[k]}</span>
                    <span className="tnum text-fg-soft">{n > 0 ? <>{num(n)} above expected{d > 0 && <> · <b className="text-fg">{money(d)}</b></>}</> : <span className="text-fg-faint">normal</span>}</span>
                  </li>
                )
              })}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}

function HrToday() {
  const { asOf, meta, setSiteId } = useStore()
  const nav = useNavigate()
  const boards = useLoad(() => Promise.all([1, 2, 3].map((s) => api.board(s, asOf))), [asOf])
  if (boards.error) return <ErrorState error={boards.error} />
  if (!boards.data) return <PageSkeleton />
  const all = boards.data
  const total = all.reduce((s, b) => s + b.total_excess, 0)
  const reds = all.flatMap((b) => b.teams.filter((t) => t.status === 'red').map((t) => ({ t, b })))
  const ambers = all.flatMap((b) => b.teams.filter((t) => t.status === 'amber').map((t) => ({ t, b })))
  return (
    <div>
      <PageHeader crumbs={<>Northline Logistics · all sites</>} title={<>Good morning, Jordan</>}
        sub={<>{reds.length ? <><b>{reds.length} team{reds.length > 1 ? 's' : ''}</b> across {meta?.sites.length ?? 3} sites need attention</> : 'No team is outside normal variation'}; {ambers.length} to watch. Excess operating cost {money(total)} in {monthRange(all[0].window)}.</>} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 stagger">
        {all.map((b) => {
          const r = b.teams.filter((t) => t.status === 'red').length, a = b.teams.filter((t) => t.status === 'amber').length
          return (
            <Card key={b.site_id} className="hover:shadow-pop transition-shadow cursor-pointer">
              <button className="w-full text-left" onClick={() => { setSiteId(b.site_id); nav('/teams') }}>
                <div className="flex items-center justify-between"><span className="font-semibold">{b.site} DC</span>{r ? <Badge tone="crit" dot>{r} need attention</Badge> : a ? <Badge tone="warn" dot>{a} to watch</Badge> : <Badge tone="ok" dot>Normal</Badge>}</div>
                <div className="mt-4 text-[26px] font-semibold tnum tracking-tight">{money(b.total_excess)}</div>
                <div className="text-[12.5px] text-fg-mute">excess operating cost · {monthRange(b.window)}</div>
                <div className="mt-4 flex gap-4 text-[12.5px] text-fg-soft"><span className="flex items-center gap-1"><Users size={13} />{b.teams.length} teams</span><span>{b.teams.filter((t) => t.status === 'rolled_up').length} rolled up</span></div>
              </button>
            </Card>
          )
        })}
      </div>
      <Card className="mt-6">
        <CardHeader title="Needs attention across sites" sub="Ranked by how far operations moved beyond normal variation" />
        {reds.length + ambers.length === 0 ? <Empty icon={<CheckCircle2 size={20} />} title="Nothing outside normal variation" />
          : <div className="space-y-3">{[...reds, ...ambers].map(({ t, b }) => <AttentionRow key={`${b.site_id}-${t.team_id}`} t={t} site={b.site} onOpen={() => { setSiteId(b.site_id); nav(`/teams/${t.team_id}`) }} />)}</div>}
      </Card>
    </div>
  )
}

export default function Today() {
  const { role } = useStore()
  return role === 'hr' ? <HrToday /> : <ManagerToday />
}
