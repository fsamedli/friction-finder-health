import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { CalendarClock, CheckCircle2, FastForward, FileText } from 'lucide-react'
import { api, type Did } from '../lib/api'
import { longDate, money, month, num, per10, signed } from '../lib/format'
import { REVIEW, SEED_PLAN, useLoad, useStore, visiblePlans } from '../lib/store'
import { DidChart } from '../components/charts'
import { Badge, Button, Card, CardHeader, ErrorState, Method, PageHeader, PageSkeleton, Provenance, Stat } from '../components/ui'

function Placebo({ r }: { r: Did }) {
  const all = [...(r.placebo ?? []).map((p) => ({ ...p, mine: false })), { team_id: -1, team: 'This team', estimate: r.estimate!, mine: true }]
  const m = Math.max(0.5, ...all.map((x) => Math.abs(x.estimate))) * 1.2
  const pos = (v: number) => `${50 + (v / m) * 50}%`
  return (
    <div>
      <div className="relative h-20">
        <div className="absolute left-0 right-0 top-10 h-px bg-border-strong" />
        <div className="absolute top-5 h-10 w-px bg-fg-faint" style={{ left: '50%' }} />
        <span className="absolute top-14 -translate-x-1/2 text-[11px] text-fg-mute" style={{ left: '50%' }}>no change</span>
        {all.map((x) => (
          <span key={x.team_id} title={`${x.team}: ${signed(x.estimate * 10, 1)} per 10 people/month`}
            className={`absolute top-10 -translate-x-1/2 -translate-y-1/2 rounded-full ${x.mine ? 'h-4 w-4 bg-crit ring-4 ring-crit/15' : 'h-3 w-3 bg-fg-faint'}`} style={{ left: pos(x.estimate) }} />
        ))}
        <span className="absolute top-0 -translate-x-1/2 text-[11.5px] font-medium text-crit-700 whitespace-nowrap" style={{ left: pos(r.estimate!) }}>this team {signed(r.estimate! * 10, 1)}</span>
      </div>
      <p className="text-[12.5px] text-fg-mute">Each grey dot is a comparison team run through the same test as if it had acted. None moves as far as the team that did.</p>
    </div>
  )
}

export default function Impact() {
  const { planId } = useParams()
  const { asOf, setAsOf } = useStore()
  const nav = useNavigate()
  const plans = useLoad(() => api.plans(), [])
  const res = useLoad(() => api.result(planId ?? SEED_PLAN, asOf), [planId, asOf])
  if (!planId) {
    const latest = plans.data ? visiblePlans(plans.data, asOf).slice(-1)[0] : undefined
    return plans.data ? <Navigate to={`/impact/${latest?.id ?? SEED_PLAN}`} replace /> : <PageSkeleton />
  }
  if (res.error) return <ErrorState error={res.error} />
  if (!res.data || !plans.data) return <PageSkeleton />
  const r = res.data
  const p = plans.data.find((x) => x.id === planId)
  const crumbs = <><button onClick={() => nav('/plans')} className="hover:text-fg">Action plans</button><span>/</span><span>{p?.team_label}</span></>
  const actions = <a href={`/api/report/${planId}`} target="_blank" rel="noreferrer"><Button variant="secondary" icon={<FileText size={15} />}>One-page report</Button></a>

  if (r.status === 'not_reached') {
    return (
      <div>
        <PageHeader crumbs={crumbs} title="Impact review" sub={`${p?.obstacle ?? ''} · started ${longDate(r.start)}`} actions={actions} />
        <Card className="py-14 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-info-50 text-info-700"><CalendarClock size={22} /></div>
          <div className="mt-4 text-[44px] font-semibold tracking-tight tnum">{r.days_to_go} days</div>
          <p className="text-fg-mute">until the review on {longDate(r.review)}</p>
          <p className="mx-auto mt-3 max-w-lg text-[13.5px] text-fg-soft">On the review date, {r.kpi_label.toLowerCase()} for this team before and after the plan are compared with similar teams that did not act.</p>
          <div className="mt-6"><Button variant="brand" icon={<FastForward size={15} />} onClick={() => setAsOf(REVIEW)}>Fast-forward to the review date</Button></div>
          <p className="mt-3 text-[12px] text-fg-faint">Demo clock: moves the workspace to Nov 30, 2026. Follow-up months are synthetic.</p>
        </Card>
      </div>
    )
  }
  if (r.status === 'insufficient') {
    return <div><PageHeader crumbs={crumbs} title="Impact review" sub={r.reason} actions={actions} /></div>
  }
  const fell = (r.estimate ?? 0) < 0
  const worked = r.verdict === 'worked'
  return (
    <div>
      <PageHeader crumbs={crumbs}
        title={<span className="flex flex-wrap items-center gap-3">Impact review {worked ? <Badge tone="ok" dot>It worked</Badge> : <Badge tone="warn" dot>{r.verdict}</Badge>}</span>}
        sub={worked
          ? <>After the plan, <b className="text-fg">{r.kpi_label.toLowerCase()} fell {per10(Math.abs(r.estimate!))} per 10 people a month more</b> than at comparable teams over the same months{r.dollars_per_quarter ? <> — about <b className="text-fg">{money(r.dollars_per_quarter)}</b> a quarter</> : null}. Directional, not causal.</>
          : <>{r.kpi_label}: {r.verdict}. The plan may need more time or a different action.</>}
        actions={actions} />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6 stagger">
        <Stat label="Change vs comparable teams" value={signed((r.estimate ?? 0) * 10, 1)} tone={worked ? 'ok' : 'warn'} sub={`per 10 people / month · 95% CI ${signed(r.ci_low! * 10, 1)} to ${signed(r.ci_high! * 10, 1)}`} />
        <Stat label="Per quarter" value={num(Math.abs(r.events_avoided_per_quarter ?? 0))} tone="brand" sub={`${fell ? 'fewer' : 'more'} ${r.kpi_label.toLowerCase()}`} />
        <Stat label="Worth per quarter" value={worked && r.dollars_per_quarter != null ? money(r.dollars_per_quarter) : '—'} tone="brand" sub={r.unit_cost ? `at ${money(r.unit_cost)} each (client-entered)` : 'no unit cost entered'} />
        <Stat label="Compared with" value={r.comparison?.teams.length ?? 0} sub={<span className="line-clamp-2" title={r.comparison?.teams.join(', ')}>{r.comparison?.teams.join(', ')}</span>} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader title={`${r.kpi_label}, per 10 people per month`} sub="This team vs the comparison teams' average, before and after the plan" right={<><Provenance kind="computed" /><Provenance kind="synthetic" /></>} />
          <DidChart series={r.series ?? []} pre={r.pre_months ?? []} post={r.post_months ?? []} start={r.start} compLabel={`Comparable teams (${r.comparison?.teams.length})`} />
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Before and after" sub={`Before: ${(r.pre_months ?? []).map(month).join(', ')} · After: ${(r.post_months ?? []).map(month).join(', ')}`}
              right={<Method title="Difference-in-differences">The team's change (after minus before) minus the comparison teams' change over the same months, so a seasonal or company-wide shift cancels out. Standard error from the event counts (Poisson). "Worked" only if the whole 95% interval is below zero. Directional, not causal: another change at the same time could explain it, which is why the plan owner confirms what else happened.</Method>} />
            <table className="w-full text-[13.5px] tnum">
              <thead><tr className="text-[12px] text-fg-mute"><th className="text-left font-medium pb-2" /><th className="text-right font-medium">Before</th><th className="text-right font-medium">After</th><th className="text-right font-medium">Change</th></tr></thead>
              <tbody>
                <tr className="border-t border-border"><td className="py-2 font-medium text-crit-700">This team</td><td className="text-right">{per10(r.treated?.pre)}</td><td className="text-right">{per10(r.treated?.post)}</td><td className="text-right">{signed(((r.treated?.post ?? 0) - (r.treated?.pre ?? 0)) * 10, 1)}</td></tr>
                <tr className="border-t border-border"><td className="py-2 text-fg-soft">Comparable teams</td><td className="text-right">{per10(r.comparison?.pre)}</td><td className="text-right">{per10(r.comparison?.post)}</td><td className="text-right">{signed(((r.comparison?.post ?? 0) - (r.comparison?.pre ?? 0)) * 10, 1)}</td></tr>
                <tr className="border-t-2 border-fg"><td className="py-2 font-semibold">Difference</td><td /><td /><td className="text-right font-semibold">{signed((r.estimate ?? 0) * 10, 1)}</td></tr>
              </tbody>
            </table>
          </Card>
          <Card><CardHeader title="Placebo check" sub="Would the same test find an effect where there was no plan?" /><Placebo r={r} /></Card>
        </div>
      </div>

      {r.also && r.also.length > 0 && (
        <Card className="mt-6">
          <CardHeader title="Other KPIs the obstacle could touch" sub="Reported as they are — two months is short for rare events" />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {r.also.filter((a) => a.status === 'ok').map((a) => (
              <div key={a.kpi} className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
                <div><div className="font-medium">{a.kpi_label}</div><div className="text-[12px] text-fg-mute tnum">{signed((a.estimate ?? 0) * 10, 1)} per 10 / month · CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}</div></div>
                <Badge tone={a.verdict === 'worked' ? 'ok' : 'warn'} dot>{a.verdict}</Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
      {worked && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok-100 bg-ok-50 px-5 py-4">
          <p className="flex items-center gap-2 text-[13.5px] text-ok-700"><CheckCircle2 size={17} /> Keep the new routine, tell the team what changed because of their survey answers, and check again at the next wave.</p>
          <Button variant="secondary" onClick={() => nav('/value')}>What is this worth across sites?</Button>
        </div>
      )}
    </div>
  )
}
