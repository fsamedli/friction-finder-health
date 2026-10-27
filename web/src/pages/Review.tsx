import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { CalendarClock, CheckCircle2, ClipboardList, FastForward, FileText } from 'lucide-react'
import { api, type Did } from '../lib/api'
import { longDate, month, num, per10, signed } from '../lib/format'
import { reviewTone, reviewWord } from '../lib/labels'
import { REVIEW, SEED_PLAN, useLoad, useStore, visiblePlans } from '../lib/store'
import { DidChart } from '../components/charts'
import Journey from '../components/Journey'
import ValueTiers from '../components/ValueTiers'
import { Badge, Button, Card, CardHeader, CsvButton, ErrorState, Method, PageHeader, PageSkeleton, Provenance, Stat, StateNote } from '../components/ui'

/* Oct 27, 2026 round (Prof. Hall, Oct 21): the verdict and the money first, in full dollars with the assumption next to
 * each figure; the before/after chart he praised stays; the interval, placebo, DiD table and other KPIs stay too but
 * read as secondary ("Evidence detail"); illustrative results are labelled. */

function Placebo({ r }: { r: Did }) {
  const all = [...(r.placebo ?? []).map((p) => ({ ...p, mine: false })), { team_id: -1, team: 'This team', estimate: r.estimate!, mine: true }]
  const m = Math.max(0.5, ...all.map((x) => Math.abs(x.estimate))) * 1.2
  const pos = (v: number) => `${50 + (v / m) * 50}%`
  const beyond = (r.placebo ?? []).filter((p) => Math.abs(p.estimate) >= Math.abs(r.estimate ?? 0)).length
  return (
    <div>
      <div className="relative h-20" role="img" aria-label={`Placebo estimates per 10 people per month: ${all.map((x) => `${x.team} ${signed(x.estimate * 10, 1)}`).join(', ')}`}>
        <div className="absolute left-0 right-0 top-10 h-px bg-border-strong" />
        <div className="absolute top-5 h-10 w-px bg-fg-faint" style={{ left: '50%' }} />
        <span className="absolute top-14 -translate-x-1/2 text-[11px] text-fg-mute" style={{ left: '50%' }}>no change</span>
        {all.map((x) => (
          <span key={x.team_id} title={`${x.team}: ${signed(x.estimate * 10, 1)} per 10 people/month`}
            className={`absolute top-10 -translate-x-1/2 -translate-y-1/2 rounded-full ${x.mine ? 'h-4 w-4 bg-crit ring-4 ring-crit/15' : 'h-3 w-3 bg-fg-faint'}`} style={{ left: pos(x.estimate) }} />
        ))}
        <span className="absolute top-0 -translate-x-1/2 text-[11.5px] font-medium text-crit-700 whitespace-nowrap" style={{ left: pos(r.estimate!) }}>this team {signed(r.estimate! * 10, 1)}</span>
      </div>
      <p className="text-[12.5px] text-fg-mute">Each grey dot is a comparison team run through the same test as if it had acted. {beyond === 0 ? 'None moves as far as the team that did.' : `${beyond} of ${r.placebo?.length ?? 0} move at least as far, so this result is less unusual than it looks.`}</p>
    </div>
  )
}

function Limits() {
  return (
    <Card>
      <CardHeader title="Read this before acting on it" sub="What this review can and cannot say" />
      <ul className="space-y-2 text-[13.5px] text-fg-soft">
        <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-faint" /><span><b className="text-fg">Directional, not causal.</b> Something else that changed at the same time could explain the result; the plan owner should confirm what else changed.</span></li>
        <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-faint" /><span><b className="text-fg">Synthetic follow-up data.</b> Lanford Health is fictional and the months after the plan started are synthetic, planted so the method can be shown.</span></li>
        <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-faint" /><span><b className="text-fg">Assumption for a pilot:</b> a two-month follow-up pulse survey on the plan's focus item would show whether engagement moved too. It is not in the demo data, so this review judges the operating number only, and the retention value above is a projection until the pulse confirms it.</span></li>
        <li className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-faint" /><span>One team that acted, compared with a handful of teams that did not. Rare events (quits, injuries) need a longer window than two months.</span></li>
      </ul>
    </Card>
  )
}

export default function Review() {
  const { planId } = useParams()
  const { asOf, setAsOf } = useStore()
  const nav = useNavigate()
  const plans = useLoad(() => api.plans(), [])
  const res = useLoad(() => api.result(planId ?? SEED_PLAN, asOf), [planId, asOf])
  if (!planId) {
    if (plans.error) return <ErrorState error={plans.error} onRetry={() => window.location.reload()} />
    const latest = plans.data ? visiblePlans(plans.data, asOf).slice(-1)[0] : undefined
    return plans.data ? <Navigate to={`/review/${latest?.id ?? SEED_PLAN}`} replace /> : <PageSkeleton />
  }
  if (res.error) return <ErrorState error={res.error} onRetry={() => window.location.reload()} />
  if (!res.data || !plans.data) return <PageSkeleton />
  const r = res.data
  const p = plans.data.find((x) => x.id === planId)
  const crumbs = <><button onClick={() => nav('/plans')} className="hover:text-fg">Action plans</button><span>/</span><span>{p?.team_label}</span></>
  const checklist = <Button variant="secondary" icon={<ClipboardList size={15} />} onClick={() => nav(`/plans/${planId}`)}>Open the checklist</Button>
  const actions = <>
    {checklist}
    <a href={`/api/report/${planId}?as_of=${asOf}`} target="_blank" rel="noreferrer"><Button variant="primary" icon={<FileText size={15} />}>One-page report</Button></a>
    <a href={`/api/report/${planId}?as_of=${asOf}&download=true`} className="text-[12.5px] font-medium text-fg-mute hover:text-fg underline">Download</a>
  </>

  if (r.status === 'not_reached') {
    return (
      <div>
        <PageHeader crumbs={crumbs} title={<span className="flex flex-wrap items-center gap-3">Review <Badge tone="info" dot>Not ready</Badge></span>} sub={`${p?.obstacle ?? ''} · started ${longDate(r.start)}`} actions={actions} />
        <Card className="py-14 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-info-50 text-info-700"><CalendarClock size={22} /></div>
          <div className="mt-4 text-[44px] font-semibold tracking-tight tnum">{r.days_to_go} days</div>
          <p className="text-fg-mute">until the review on {longDate(r.review)}</p>
          <p className="mx-auto mt-3 max-w-lg text-[13.5px] text-fg-soft">Not ready: on the review date, {r.kpi_label.toLowerCase()} for this team before and after the plan are compared with similar teams that did not act. Until then the checklist is where the plan is run.</p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3"><Button variant="primary" icon={<FastForward size={15} />} onClick={() => setAsOf(REVIEW)}>Fast-forward to the review date</Button>{checklist}</div>
          <p className="mt-3 text-[12px] text-fg-faint">Demo clock: moves the workspace to Nov 30, 2026. Follow-up months are synthetic.</p>
        </Card>
        <div className="mt-6"><Limits /></div>
        <div className="mt-6"><Journey at="prove" teamId={p?.team_id} planId={planId} /></div>
      </div>
    )
  }
  if (r.status === 'insufficient') {
    return (
      <div>
        <PageHeader crumbs={crumbs} title={<span className="flex flex-wrap items-center gap-3">Review <Badge tone="neutral" dot>Missing follow-up</Badge></span>} sub={p?.obstacle} actions={actions} />
        <StateNote kind="insufficient" title="Not enough follow-up data to judge yet">{r.reason}</StateNote>
        <div className="mt-6"><Limits /></div>
      </div>
    )
  }
  const word = reviewWord(r.verdict)
  const tone = reviewTone(r.verdict)
  const fell = (r.estimate ?? 0) < 0
  const improved = r.verdict === 'worked'
  const compTeams = r.comparison?.teams ?? []
  return (
    <div>
      <PageHeader crumbs={crumbs}
        title={<span className="flex flex-wrap items-center gap-3">Review <Badge tone={tone} dot className="!text-[13px] !px-2.5 !py-1">{word}</Badge></span>}
        sub={<span className="text-[15px] text-fg-soft">{word}: after the plan, <b className="text-fg">{r.kpi_label.toLowerCase()} {fell ? 'fell' : 'rose'} {per10(Math.abs(r.estimate!))} per 10 people a month more</b> than at the {compTeams.length} comparable teams over the same months. {r.verdict === 'inconclusive' ? 'The 95% interval includes no change. ' : ''}Directional, not causal.</span>}
        actions={actions} />

      {r.value && <ValueTiers v={r.value} improved={improved} />}

      <Card>
        <CardHeader title={`${r.kpi_label}, per 10 people per month`} sub="This team vs the comparison teams' average, before and after the plan"
          right={<><Provenance kind="computed" /><Provenance kind="synthetic" /><CsvButton filename={`review_${planId}.csv`} rows={() => (r.series ?? []).map((x) => ({ month: x.month, this_team_per_10: +(x.treated * 10).toFixed(2), comparison_per_10: +(x.comparison * 10).toFixed(2), period: (r.pre_months ?? []).includes(x.month) ? 'before' : (r.post_months ?? []).includes(x.month) ? 'after' : '' }))} /></>} />
        <DidChart series={r.series ?? []} pre={r.pre_months ?? []} post={r.post_months ?? []} start={r.start} compLabel={`Comparable teams (${compTeams.length})`} />
        <p className="mt-1 text-[12px] text-fg-mute">Unit: events per 10 people per month · before: {(r.pre_months ?? []).map(month).join(', ')} · after: {(r.post_months ?? []).map(month).join(', ')} · baseline: the comparison teams (other hospitals, same shift)</p>
      </Card>

      {improved && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok-100 bg-ok-50 px-5 py-4">
          <p className="flex items-center gap-2 text-[14px] text-ok-700"><CheckCircle2 size={17} /> Your decision: keep the new routine, tell the team what changed because of their survey answers, and check again at the next wave.</p>
          <div className="flex flex-wrap gap-2">{checklist}<Button variant="secondary" onClick={() => nav('/value')}>What is this worth across hospitals?</Button></div>
        </div>
      )}

      {/* Evidence detail: everything a judge may ask about, kept, but visually second to the verdict and the money. */}
      <section aria-labelledby="evidence-h" className="mt-8 rounded-2xl border border-border bg-canvas/70 p-4 md:p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="evidence-h" className="eyebrow !text-[12px]">Evidence detail</h2>
            <p className="mt-0.5 text-[13px] text-fg-mute">The interval, the placebo check and the other KPIs the obstacle could touch. For Q&amp;A; the headline above already reflects them.</p>
          </div>
          <Method title="Difference-in-differences">The team's change (after minus before) minus the comparison teams' change over the same months, so a seasonal or company-wide shift cancels out. Standard error from the event counts (Poisson). Improved only if the whole 95% interval is below zero; deteriorated only if it is entirely above zero; otherwise inconclusive. Directional, not causal: another change at the same time could explain it, which is why the plan owner confirms what else happened.</Method>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 mb-4">
          <Stat label="Change vs comparable teams" value={signed((r.estimate ?? 0) * 10, 1)} tone={improved ? 'ok' : tone === 'crit' ? 'crit' : 'warn'} sub={`per 10 people / month · 95% CI ${signed(r.ci_low! * 10, 1)} to ${signed(r.ci_high! * 10, 1)}`} />
          <Stat label="Per quarter" value={num(Math.abs(r.events_avoided_per_quarter ?? 0))} tone="brand" sub={`${fell ? 'fewer' : 'more'} ${r.kpi_label.toLowerCase()} on ${r.value?.team.headcount ?? ''} people`} />
          <Stat label="Compared with" value={compTeams.length} sub={<span className="line-clamp-2" title={compTeams.join(', ')}>{compTeams.join(', ')}</span>} />
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card>
            <CardHeader title="Before and after" sub={`Before: ${(r.pre_months ?? []).map(month).join(', ')} · After: ${(r.post_months ?? []).map(month).join(', ')}`} />
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
          <Card>
            <CardHeader title="Other KPIs the obstacle could touch" sub="Reported as they are; two months is short for rare events" />
            {r.also && r.also.filter((a) => a.status === 'ok').length > 0 ? (
              <div className="space-y-2">
                {r.also.filter((a) => a.status === 'ok').map((a) => (
                  <div key={a.kpi} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                    <div><div className="font-medium text-[13.5px]">{a.kpi_label}</div><div className="text-[12px] text-fg-mute tnum">{signed((a.estimate ?? 0) * 10, 1)} per 10 / month · CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}</div></div>
                    <Badge tone={reviewTone(a.verdict)} dot>{reviewWord(a.verdict)}</Badge>
                  </div>
                ))}
              </div>
            ) : <p className="text-[13px] text-fg-mute">No other KPI has enough follow-up data yet.</p>}
          </Card>
        </div>
        <div className="mt-4"><Limits /></div>
      </section>

      <div className="mt-6"><Journey at="prove" teamId={p?.team_id} planId={planId} /></div>
    </div>
  )
}
