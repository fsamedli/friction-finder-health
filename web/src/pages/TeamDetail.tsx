import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowRight, ClipboardPlus, FileText, Lock, MessageSquareQuote, UserRound } from 'lucide-react'
import { api, KPI_ORDER, type AskResult, type Kpi, type Plan, type PlanAction, type Why } from '../lib/api'
import { longDate, money, monthRange, num, per10, pval, signed } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { DETECT, useLoad, useStore, visiblePlans } from '../lib/store'
import { ItemChanges, LinkScatter, QuartileBars, TrendChart } from '../components/charts'
import Journey from '../components/Journey'
import { Badge, Button, Card, CardHeader, Empty, ErrorState, Method, PageHeader, PageSkeleton, Provenance, Segmented, Stat, StatusBadge, Tabs } from '../components/ui'

type Tab = 'overview' | 'drivers' | 'evidence' | 'plan'

function conclusion(w: Why) {
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const drops = w.item_changes.filter((c) => c.delta <= -0.3).slice(0, 2)
  if (!flagged.length && !w.engagement?.biggest_drop?.significant) return 'Operations and engagement are within the range comparable teams would predict.'
  const parts: string[] = []
  if (flagged.length) { const e = w.excess![flagged[0]]!; parts.push(`${KPI_SHORT[flagged[0]].toLowerCase()} ran ${(e.observed / Math.max(1, e.expected)).toFixed(1)}× what comparable teams predict (${num(e.observed)} vs ${num(e.expected)})`) }
  else parts.push('operating KPIs stayed within normal range')
  if (drops.length) parts.push(`${drops.map((d) => `“${d.label}”`).join(' and ')} fell`)
  const out = parts.join(', while ') + '.'
  return out.charAt(0).toUpperCase() + out.slice(1)
}

function Overview({ w }: { w: Why }) {
  const [k, setK] = useState<Kpi>(KPI_ORDER.find((x) => w.excess?.[x]?.flagged) ?? 'late_departures')
  const e = w.excess?.[k]
  const marks = [{ m: '2026-03', label: 'Wave 1' }, { m: '2026-09', label: 'Wave 2' }].filter((x) => w.kpi_trend.some((d) => d.month === x.m))
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.45fr_1fr]">
      <Card>
        <CardHeader title="Operating KPIs" sub="Per 10 people per month · this team vs comparable teams" right={<Provenance kind="computed" />} />
        <Segmented value={k} onChange={setK} options={KPI_ORDER.map((x) => ({ id: x, label: <span className={w.excess?.[x]?.flagged ? 'text-crit-700' : ''}>{KPI_SHORT[x]}</span> }))} />
        <div className="mt-3"><TrendChart data={w.kpi_trend} k={k} window={w.window} marks={marks} teamLabel={w.team.team_name} /></div>
        {e && <p className="mt-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px] text-fg-soft">
          {monthRange(w.window ?? [])}: <b className="text-fg">{num(e.observed)}</b> observed vs <b className="text-fg">{num(e.expected, 1)}</b> expected
          {e.judgeable ? <> ({pval(e.p)}) — {e.flagged ? <b className="text-crit-700">beyond normal variation{e.dollars > 0 ? `, ${money(e.dollars)}` : ''}</b> : 'within normal variation'}</> : ' — too rare to judge in three months'}.
        </p>}
      </Card>
      <Card>
        <CardHeader title="Survey change, wave 1 → wave 2" sub={`Points on a 5-point scale · n = ${w.engagement?.n_w1} → ${w.engagement?.n_w2} respondents`} right={<Provenance kind="computed" />} />
        {w.item_changes.length ? <ItemChanges items={w.item_changes} /> : <Empty icon={<Lock size={18} />} title="Item changes hidden" sub={w.reason ?? ''} />}
        {w.engagement?.biggest_drop && <p className="mt-3 text-[12.5px] text-fg-mute">Adjusted for who responded, the largest change is {signed(w.engagement.biggest_drop.delta)} pts ({pval(w.engagement.biggest_drop.p)}; must be below 0.0042 after choosing the worst of 12).</p>}
      </Card>
    </div>
  )
}

function Drivers({ w }: { w: Why }) {
  const { meta } = useStore()
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const best = [...w.links].filter((l) => l.verdict === 'association' && (!flagged.length || flagged.includes(l.kpi))).sort((a, b) => (a.p ?? 1) - (b.p ?? 1))[0]
  const firstDrop = w.item_changes.find((c) => c.delta <= -0.3)?.item ?? 'grand'
  const [sel, setSel] = useState<{ kpi: Kpi; item: string }>(best ? { kpi: best.kpi, item: best.item } : { kpi: flagged[0] ?? 'late_departures', item: firstDrop })
  const one = useLoad(() => api.link(sel.kpi, sel.item), [sel.kpi, sel.item])
  const a = one.data?.association, q = one.data?.quartile
  const itemLabel = sel.item === 'grand' ? 'Overall engagement' : `${sel.item.toUpperCase()} · ${meta?.items[sel.item] ?? ''}`
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Is this bigger than one team?" sub="The same comparison across every reportable team-wave at Northline: does this engagement item move with this KPI?"
          right={<Badge tone="neutral">Association, not cause</Badge>} />
        <div className="flex flex-wrap gap-2">
          {w.links.map((l) => (
            <button key={l.kpi + l.item} onClick={() => setSel({ kpi: l.kpi, item: l.item })}
              className={`rounded-lg border px-2.5 py-1.5 text-[12.5px] ${sel.kpi === l.kpi && sel.item === l.item ? 'border-brand bg-brand-50 text-brand-900' : 'border-border hover:bg-canvas'}`}>
              {l.item === 'grand' ? 'Overall' : l.item.toUpperCase()} × {KPI_SHORT[l.kpi]} · <span className={l.verdict === 'association' ? 'text-brand-700 font-medium' : 'text-fg-mute'}>{l.verdict === 'association' ? 'linked' : l.verdict === 'too rare to test' ? 'too rare' : 'no link'}</span>
            </button>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title={`${KPI_SHORT[sel.kpi]} vs ${itemLabel}`} sub={`Each dot is one team in one survey wave · ${a?.n_cells ?? '…'} team-waves`} right={<span className="text-[12px] text-fg-mute"><span className="text-crit">◆</span> {w.team.team_name}</span>} />
          {!a ? <PageSkeleton /> : a.verdict === 'too rare to test' ? <Empty title="Too rare to test" sub="Most team-quarters have zero events. Needs a year or more of history." />
            : <LinkScatter a={a} teamId={w.team.team_id} xLabel={`${sel.item === 'grand' ? 'Overall engagement' : sel.item.toUpperCase()} (mean, 1–5)`} yLabel="per 10 people / month" />}
          {a?.slope != null && (
            <p className="mt-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px] text-fg-soft">
              <b className="text-fg">{a.verdict === 'association' ? 'Linked.' : 'No link detected.'}</b> Each 1-point lower score goes with {per10(Math.abs(a.slope))} {a.slope < 0 ? 'more' : 'fewer'} {KPI_SHORT[sel.kpi].toLowerCase()} per 10 people a month
              {' '}(95% CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}; {a.n_teams} teams). <Method>OLS of each team-wave's KPI rate (the quarter the survey closed in) on the item mean, standard errors clustered by team because each team appears twice. Team-waves under 4 respondents are excluded. With 24 teams this detects strong links only.</Method>
            </p>
          )}
        </Card>
        <Card>
          <CardHeader title="Top vs bottom quartile" sub={`Median ${KPI_SHORT[sel.kpi].toLowerCase()} per 10 people a month, by ${sel.item === 'grand' ? 'overall engagement' : sel.item.toUpperCase()} quartile — the comparison Gallup's own research uses`} />
          {q ? <QuartileBars q={q} /> : <PageSkeleton />}
          {q?.pct_diff != null && <p className="mt-2 text-[13px] text-fg-soft">Top-quartile team-waves have <b className="text-fg">{num(Math.abs(q.pct_diff))}% {q.pct_diff >= 0 ? 'fewer' : 'more'}</b> {KPI_SHORT[sel.kpi].toLowerCase()} than bottom-quartile ones ({q.n_per_quartile} per quartile).</p>}
        </Card>
      </div>
    </div>
  )
}

function useEvidence(w: Why) {
  const [r, setR] = useState<AskResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (!w.team.site) return
    let live = true
    api.ask(`Why did the ${w.team.site} ${w.team.team_name} team's scores drop?`, true).then((x) => { if (live) setR(x) }).catch((e) => { if (live) setErr(String(e.message)) })
    return () => { live = false }
  }, [w.team.site, w.team.team_name])
  return { r, err }
}

function Evidence({ ev }: { ev: { r: AskResult | null; err: string | null } }) {
  if (ev.err) return <ErrorState error={ev.err} />
  const r = ev.r
  if (!r) return <PageSkeleton />
  const mix = r.evidence.find((e) => e.kind === 'tenure_mix' || e.kind === 'signal_check')
  const themes = r.evidence.find((e) => e.kind === 'comment_themes')
  const comments = r.evidence.filter((e) => e.kind === 'comment')
  const owner = r.evidence.find((e) => e.kind === 'owner')
  const ops = r.evidence.find((e) => e.kind === 'ops_hour')
  const staffing = r.evidence.find((e) => e.kind === 'staffing')
  const quote = (s: string) => s.match(/"(.+)"/)?.[1] ?? s
  const meta = (s: string) => s.match(/\(([^)]*wave \d[^)]*)\)/)?.[1] ?? ''
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
      <Card>
        <CardHeader title={r.assessment?.label ?? r.message} sub="Verdict computed by rules from survey, operating records and comments" right={<><Provenance kind="computed" /><Badge tone="neutral">rules mode · {r.seconds.toFixed(1)} s</Badge></>} />
        <ul className="space-y-2 text-[13.5px]">
          {(r.assessment?.reasons ?? []).map((x) => <li key={x} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 rounded-full bg-brand shrink-0" /><span className="text-fg-soft">{x}</span></li>)}
        </ul>
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 border-t border-border pt-4 text-[13px]">
          <div><div className="label mb-1">Is the drop real?</div><p className="text-fg-soft">{mix?.statement ?? '—'}</p></div>
          <div><div className="label mb-1">Operating detail</div><p className="text-fg-soft">{ops?.statement ?? '—'}</p>{staffing && <p className="text-fg-soft mt-2">{staffing.statement}</p>}</div>
        </div>
        {owner && <div className="mt-4 flex items-center gap-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px]"><UserRound size={16} className="text-fg-mute" /><span>{owner.statement}</span></div>}
      </Card>
      <Card>
        <CardHeader title="What employees wrote" sub={themes?.statement} icon={<MessageSquareQuote size={16} />} right={<Provenance kind="retrieved" />} />
        <ul className="space-y-3">
          {comments.map((c) => (
            <li key={c.id} className="rounded-lg border border-border p-3">
              <p className="text-[13.5px] text-fg">“{quote(c.statement)}”</p>
              <p className="mt-1 text-[11.5px] text-fg-mute">{meta(c.statement)}</p>
            </li>
          ))}
          {comments.length === 0 && <Empty title="No comments retrieved" />}
        </ul>
      </Card>
    </div>
  )
}

const addDays = (d: string, n: number) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }

function PlanTab({ w, ev, existing, onSaved }: { w: Why; ev: AskResult | null; existing?: Plan; onSaved: (p: Plan) => void }) {
  const nav = useNavigate()
  const kpi: Kpi = KPI_ORDER.find((k) => w.excess?.[k]?.flagged) ?? 'late_departures'
  // focus on the dropped item that is linked to the KPI the plan must move; otherwise the largest drop
  const dropped = w.item_changes.filter((c) => c.delta <= -0.3)
  const linked = w.links.filter((l) => l.kpi === kpi && l.verdict === 'association').sort((a, b) => (a.p ?? 1) - (b.p ?? 1))
  const drop = dropped.find((c) => linked.some((l) => l.item === c.item)) ?? dropped[0]
  const owner = ev?.evidence.find((e) => e.kind === 'owner')?.statement.match(/: (.+?) \(/)?.[1] ?? 'Site operations manager'
  const theme = ev?.assessment?.label.match(/: ([^.]+)\./)?.[1] ?? drop?.label.toLowerCase() ?? 'the obstacle behind the drop'
  const start = '2026-09-21'
  const [obstacle, setObstacle] = useState(theme.charAt(0).toUpperCase() + theme.slice(1))
  const [actions, setActions] = useState<PlanAction[]>([
    { text: `Fix the ${theme} step the comments describe, and write the new routine down`, owner, due: addDays(start, 7) },
    { text: `Ask the team in the next huddle what gets in the way of “${drop?.label ?? 'doing the work right'}”`, owner: `${w.team.team_name} team manager`, due: addDays(start, 14) },
    { text: 'Ten-minute check-in every other Monday: did the actions happen, did they help?', owner: `${w.team.team_name} team manager`, due: addDays(start, 21) },
  ])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  if (existing) {
    return (
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader title={existing.obstacle} sub={`Focus item: ${existing.focus} · KPI to watch: ${KPI_SHORT[existing.kpi]}`} right={<Badge tone="ok" dot>Approved</Badge>} />
          <ol className="divide-y divide-border rounded-lg border border-border">
            {existing.actions.map((a, i) => (
              <li key={i} className="flex gap-3 p-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-[12px] font-semibold text-brand-700">{i + 1}</span>
                <div><div className="text-[13.5px] font-medium">{a.text}</div><div className="text-[12px] text-fg-mute">{a.owner} · due {longDate(a.due)}</div></div>
              </li>
            ))}
          </ol>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => nav(`/impact/${existing.id}`)} icon={<ArrowRight size={15} />}>See if it worked</Button>
            <a href={`/api/report/${existing.id}`} target="_blank" rel="noreferrer"><Button variant="secondary" icon={<FileText size={15} />}>One-page report</Button></a>
          </div>
        </Card>
        <Card>
          <CardHeader title="Review date" sub={`Plan starts ${longDate(existing.start)}`} />
          <div className="text-[26px] font-semibold tracking-tight">{longDate(existing.review)}</div>
          <p className="text-[13px] text-fg-mute mt-1">On this date the {KPI_SHORT[existing.kpi].toLowerCase()} before and after the plan are compared with similar teams that did not act.</p>
          <div className="mt-4 label">Every other Monday, ten minutes</div>
          <ul className="mt-1.5 space-y-1 text-[13px] text-fg-soft"><li>Did we complete the actions?</li><li>Did completing them make a difference?</li><li>What do we keep, change, or stop?</li></ul>
          <p className="mt-2 text-[11.5px] text-fg-faint">Check-in questions follow Gallup's State of the Team handout.</p>
        </Card>
      </div>
    )
  }
  const approve = async () => {
    setBusy(true); setErr(null)
    try {
      const p = await api.createPlan({ team_id: w.team.team_id, item: drop?.item ?? 'grand', kpi, obstacle, focus: drop ? `${drop.label} (${drop.item})` : 'Overall engagement',
        actions: actions.filter((a) => a.text.trim()), start, status: 'approved', note: 'Approved in the app' })
      onSaved(p)
    } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(false) }
  }
  const set = (i: number, k: keyof PlanAction, v: string) => setActions((a) => a.map((x, j) => (j === i ? { ...x, [k]: v } : x)))
  return (
    <Card>
      <CardHeader title="Draft action plan" sub="Drafted from this team's evidence. Edit anything, then approve. Nothing reaches the team until a person approves." right={<Provenance kind="person" />} />
      <label className="block"><span className="label">Obstacle to test</span>
        <input value={obstacle} onChange={(e) => setObstacle(e.target.value)} className="mt-1 w-full rounded-lg border border-border-strong px-3 py-2 text-[15px] font-medium focus:outline-none focus:ring-4 focus:ring-brand/10" /></label>
      <p className="mt-2 text-[12.5px] text-fg-mute">Focus item: {drop?.label ?? 'overall engagement'} · KPI to watch: {KPI_SHORT[kpi]} · starts Sept 21, reviewed Nov 30 (two full months of operating data)</p>
      <div className="mt-4 space-y-2">
        {actions.map((a, i) => (
          <div key={i} className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_220px_150px]">
            <input value={a.text} onChange={(e) => set(i, 'text', e.target.value)} className="rounded-lg border border-border-strong px-3 py-2 text-[13.5px] focus:outline-none focus:ring-4 focus:ring-brand/10" />
            <input value={a.owner} onChange={(e) => set(i, 'owner', e.target.value)} className="rounded-lg border border-border-strong px-3 py-2 text-[13px] focus:outline-none focus:ring-4 focus:ring-brand/10" />
            <input type="date" value={a.due} onChange={(e) => set(i, 'due', e.target.value)} className="rounded-lg border border-border-strong px-3 py-2 text-[13px] focus:outline-none focus:ring-4 focus:ring-brand/10" />
          </div>
        ))}
      </div>
      {err && <p className="mt-3 text-[13px] text-crit-700">{err}</p>}
      <div className="mt-5 flex items-center gap-2"><Button variant="decide" onClick={approve} disabled={busy || !obstacle.trim()} icon={<ClipboardPlus size={15} />}>{busy ? 'Saving…' : 'Approve plan'}</Button></div>
    </Card>
  )
}

export default function TeamDetail() {
  const { teamId } = useParams()
  const id = Number(teamId)
  const [sp, setSp] = useSearchParams()
  const tab = (sp.get('tab') as Tab) || 'overview'
  const setTab = (t: Tab) => setSp(t === 'overview' ? {} : { tab: t }, { replace: true })
  const { asOf, setTeamId } = useStore()
  const nav = useNavigate()
  useEffect(() => { if (id) setTeamId(id) }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  const why = useLoad(() => api.why(id, asOf), [id, asOf])
  const detect = useLoad(() => api.why(id, DETECT), [id])
  const plans = useLoad(() => api.plans(), [id])
  const ev = useEvidence(detect.data ?? ({ team: { site: '', team_name: '' } } as Why))
  const existing = useMemo(() => (plans.data ? visiblePlans(plans.data, asOf) : []).filter((p) => p.team_id === id).slice(-1)[0], [plans.data, id, asOf])
  if (why.error) return <ErrorState error={why.error} />
  if (!why.data || !detect.data) return <PageSkeleton />
  const w = why.data
  const crumbs = <><button onClick={() => nav('/teams')} className="hover:text-fg">Teams</button><span>/</span><span>{w.team.site} {w.team.team_name}</span></>
  if (w.suppressed) {
    return (
      <div>
        <PageHeader crumbs={crumbs} title={`${w.team.site} ${w.team.team_name}`} sub={`${w.team.shift} shift · ${w.team.headcount} people`} />
        <Card><Empty icon={<Lock size={20} />} title="Too small to report on its own" sub={`Fewer than 4 people. Survey answers and operating counts are included in the ${w.team.site} site totals only, so no one on this team can be identified. Gallup's reporting threshold is 4.`}
          action={<Button variant="secondary" onClick={() => nav('/teams')}>Back to teams</Button>} /></Card>
      </div>
    )
  }
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const e = flagged[0] ? w.excess![flagged[0]] : undefined
  const drop = w.engagement?.biggest_drop
  return (
    <div>
      <Journey at={tab === 'plan' ? 'act' : 'explain'} teamId={w.team.team_id} planId={existing?.id} />
      <PageHeader crumbs={crumbs}
        title={<span className="flex flex-wrap items-center gap-3">{w.team.site} {w.team.team_name} {w.status && <StatusBadge s={w.status} />}</span>}
        sub={<>{w.team.shift} shift · {w.team.headcount} people · {monthRange(w.window ?? [])}. <span className="text-fg">{conclusion(w)}</span></>}
        actions={existing
          ? <Button variant="primary" onClick={() => nav(`/impact/${existing.id}`)} icon={<ArrowRight size={15} />}>See if the plan worked</Button>
          : <Button variant="decide" onClick={() => setTab('plan')} icon={<ClipboardPlus size={15} />}>Create action plan</Button>} />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6 stagger">
        <Stat label={e ? `${KPI_SHORT[flagged[0]]} · 3 months` : 'Operating KPIs'} value={e ? <>{num(e.observed)}<span className="text-[16px] text-fg-faint"> vs {num(e.expected)}</span></> : 'Normal'} tone={e ? 'crit' : 'ok'} sub={e ? `expected from comparable teams · ${pval(e.p)}` : 'within normal variation'} />
        <Stat label="Excess operating cost" value={money(w.excess_cost ?? 0)} tone={(w.excess_cost ?? 0) > 0 ? 'crit' : undefined} sub="last 3 months · unit costs editable" />
        <Stat label="Largest survey change" value={drop ? `${signed(drop.delta)}` : '—'} tone={drop?.significant ? 'crit' : undefined} sub={drop ? <span className="line-clamp-2">{drop.label}</span> : 'hidden: small wave'} />
        <Stat label="Respondents" value={`${w.engagement?.n_w1 ?? '—'} → ${w.engagement?.n_w2 ?? '—'}`} sub="wave 1 → wave 2 · minimum 4" />
      </div>

      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'overview', label: 'Overview' }, { id: 'drivers', label: 'Drivers' }, { id: 'evidence', label: 'Evidence' }, { id: 'plan', label: existing ? 'Action plan' : 'Create plan' }]} />
      <div className="mt-6">
        {tab === 'overview' && <Overview w={w} />}
        {tab === 'drivers' && <Drivers w={detect.data} />}
        {tab === 'evidence' && <Evidence ev={ev} />}
        {tab === 'plan' && <PlanTab key={ev.r ? 'with-evidence' : 'drafting'} w={detect.data} ev={ev.r} existing={existing} onSaved={(p) => { plans.setData([...(plans.data ?? []), p]); }} />}
      </div>
    </div>
  )
}
