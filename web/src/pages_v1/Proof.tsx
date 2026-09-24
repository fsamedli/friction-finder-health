import { useParams, useNavigate } from 'react-router-dom'
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type Did } from '../lib/api'
import { longDate, money, month, num, per10, signed } from '../lib/format'
import { REVIEW, useLoad, useStore } from '../lib/store'
import { Button, Card, Chip, ErrorNote, Eyebrow, How, Loading, PageTitle, Stat } from '../components/ui'

const VERDICT = {
  worked: { label: 'It worked', cls: 'bg-moss text-white' },
  inconclusive: { label: 'Inconclusive', cls: 'bg-amber-soft text-[#7A5A12]' },
  'no effect': { label: 'No effect', cls: 'bg-rust-soft text-rust-deep' },
} as const

function Placebo({ r }: { r: Did }) {
  const all = [...(r.placebo ?? []).map((p) => ({ ...p, mine: false })), { team_id: -1, team: 'This team', estimate: r.estimate!, mine: true }]
  const m = Math.max(0.5, ...all.map((x) => Math.abs(x.estimate))) * 1.15
  const pos = (v: number) => `${50 + (v / m) * 50}%`
  return (
    <div>
      <div className="relative h-16 mt-2">
        <div className="absolute left-0 right-0 top-8 h-px bg-line" />
        <div className="absolute top-3 bottom-3 w-px bg-ink-mute" style={{ left: '50%' }} />
        <span className="absolute top-12 text-[11px] text-ink-mute -translate-x-1/2" style={{ left: '50%' }}>0</span>
        {all.map((x) => (
          <span key={x.team_id} title={`${x.team}: ${signed(x.estimate * 10, 1)} per 10 people/month`}
            className={`absolute top-8 -translate-x-1/2 -translate-y-1/2 rounded-full ${x.mine ? 'h-4 w-4 bg-rust ring-4 ring-rust/20' : 'h-2.5 w-2.5 bg-ink/40'}`}
            style={{ left: pos(x.estimate) }} />
        ))}
        <span className="absolute text-[11.5px] font-semibold text-rust -translate-x-1/2 top-0" style={{ left: pos(r.estimate!) }}>this team</span>
      </div>
      <p className="text-[12.5px] text-ink-mute">Each grey dot is a comparison team run through the same test as if it had acted. None moves as far as the team that did.</p>
    </div>
  )
}

function Result({ r }: { r: Did }) {
  const v = VERDICT[r.verdict!]
  const fell = (r.estimate ?? 0) < 0
  const series = (r.series ?? []).map((s) => ({ month: s.month, team: s.treated * 10, comp: s.comparison * 10 }))
  const pre = r.pre_months ?? [], post = r.post_months ?? []
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr] stagger">
        <Card className="p-6">
          <div className="flex items-baseline justify-between"><Eyebrow>{r.kpi_label} · per 10 people per month</Eyebrow><Chip kind="synthetic">Oct–Nov synthetic</Chip></div>
          <div className="h-[300px] mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} margin={{ top: 18, right: 12, bottom: 0, left: -12 }}>
                <CartesianGrid stroke="#E3DFD5" vertical={false} />
                {pre.length > 0 && <ReferenceArea x1={pre[0]} x2={pre[pre.length - 1]} fill="#C8553D" fillOpacity={0.06} label={{ value: 'before', position: 'insideTop', fontSize: 11, fill: '#9E3F2B' }} />}
                {post.length > 0 && <ReferenceArea x1={post[0]} x2={post[post.length - 1]} fill="#1F8FA8" fillOpacity={0.08} label={{ value: 'after', position: 'insideTop', fontSize: 11, fill: '#146C80' }} />}
                <ReferenceLine x={r.start.slice(0, 7)} stroke="#1B3A4B" strokeDasharray="3 3" label={{ value: 'plan starts', position: 'top', fontSize: 11, fill: '#1B3A4B' }} />
                <XAxis dataKey="month" tickFormatter={month} tickLine={false} axisLine={{ stroke: '#E3DFD5' }} />
                <YAxis tickLine={false} axisLine={false} width={48} />
                <Tooltip formatter={(x) => Number(x).toFixed(1)} labelFormatter={(l) => month(String(l))} />
                <Legend verticalAlign="bottom" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
                <Line name={`Comparable teams (${r.comparison?.teams.length})`} dataKey="comp" stroke="#B9C6CC" strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
                <Line name="This team" dataKey="team" stroke="#C8553D" strokeWidth={2.8} dot={{ r: 3, fill: '#C8553D' }} animationDuration={600} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-6" tone={r.verdict === 'worked' ? 'teal' : undefined}>
          <span className={`inline-flex rounded-full px-3 py-1 text-[13px] font-bold ${v.cls}`}>{v.label}</span>
          <div className="num text-[3.4rem] leading-none mt-5 text-ink">{signed((r.estimate ?? 0) * 10, 1)}</div>
          <div className="text-ink-soft mt-2 text-[14.5px]">
            {r.kpi_label.toLowerCase()} per 10 people per month, {fell ? 'fewer' : 'more'} than comparable teams over the same months
          </div>
          <div className="mt-2 text-[13px] text-ink-mute">95% CI {signed(r.ci_low! * 10, 1)} to {signed(r.ci_high! * 10, 1)}</div>
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-line pt-5">
            <Stat label="Per quarter" value={num(Math.abs(r.events_avoided_per_quarter ?? 0))} sub={`${fell ? 'fewer' : 'more'} ${r.kpi_label.toLowerCase()}`} tone="teal" />
            <Stat label="Worth" value={r.dollars_per_quarter != null && r.verdict === 'worked' ? money(r.dollars_per_quarter, true) : '—'} sub={r.unit_cost ? `at ${money(r.unit_cost)} each, per quarter` : 'no unit cost entered'} tone="teal" />
          </div>
          <div className="mt-5">
            <How label="How this is tested">
              <b>Difference-in-differences.</b> The team's change (after minus before) minus the change for {r.comparison?.teams.join(', ')} over the same months — so a site-wide or seasonal shift cancels out.
              Before = {pre.map(month).join(', ')}; after = {post.map(month).join(', ')}. The standard error comes from the event counts (Poisson). "Worked" only if the whole 95% interval is below zero.
              Directional, not causal: another change at the same time could explain it, which is why the owner confirms what else happened.
            </How>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Card className="p-6">
          <Eyebrow>Before and after, side by side</Eyebrow>
          <table className="w-full mt-4 text-[14px] tab">
            <thead><tr className="text-ink-mute text-[12px]"><th className="text-left font-semibold pb-2"></th><th className="text-right font-semibold">Before</th><th className="text-right font-semibold">After</th><th className="text-right font-semibold">Change</th></tr></thead>
            <tbody>
              <tr className="border-t border-line"><td className="py-2 font-semibold text-rust">This team</td><td className="text-right">{per10(r.treated?.pre)}</td><td className="text-right">{per10(r.treated?.post)}</td><td className="text-right">{signed(((r.treated?.post ?? 0) - (r.treated?.pre ?? 0)) * 10, 1)}</td></tr>
              <tr className="border-t border-line"><td className="py-2 text-ink-soft">Comparable teams</td><td className="text-right">{per10(r.comparison?.pre)}</td><td className="text-right">{per10(r.comparison?.post)}</td><td className="text-right">{signed(((r.comparison?.post ?? 0) - (r.comparison?.pre ?? 0)) * 10, 1)}</td></tr>
              <tr className="border-t-2 border-ink"><td className="py-2 font-bold">Difference</td><td /><td /><td className="text-right num text-[1.1rem]">{signed((r.estimate ?? 0) * 10, 1)}</td></tr>
            </tbody>
          </table>
        </Card>
        <Card className="p-6">
          <Eyebrow>Placebo check</Eyebrow>
          <Placebo r={r} />
        </Card>
      </div>

      {r.also && r.also.length > 0 && (
        <Card className="p-6">
          <Eyebrow>Other KPIs the obstacle could touch</Eyebrow>
          <div className="grid sm:grid-cols-2 gap-4 mt-3">
            {r.also.filter((a) => a.status === 'ok').map((a) => (
              <div key={a.kpi} className="flex items-baseline justify-between border-t border-line pt-3">
                <span className="font-semibold">{a.kpi_label}</span>
                <span className="text-[13.5px] text-ink-soft">{signed((a.estimate ?? 0) * 10, 1)} per 10/month (CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}) ·{' '}
                  <b className={a.verdict === 'worked' ? 'text-moss' : 'text-[#7A5A12]'}>{a.verdict}</b></span>
              </div>
            ))}
          </div>
          <p className="text-[12.5px] text-ink-mute mt-3">The tool reports these as they are. Two months is too short to see a change in quits; it says "inconclusive" rather than claim one.</p>
        </Card>
      )}
    </div>
  )
}

export default function Proof() {
  const { planId } = useParams()
  const { asOf, setAsOf } = useStore()
  const nav = useNavigate()
  const plans = useLoad(() => api.plans(), [])
  const res = useLoad(() => api.result(planId!, asOf), [planId, asOf])
  if (res.error) return <ErrorNote error={res.error} />
  if (!res.data || !plans.data) return <Loading label="Comparing before and after" />
  const r = res.data
  const p = plans.data.find((x) => x.id === planId)
  const name = p?.team_label ?? 'Plan'

  if (r.status === 'not_reached') {
    return (
      <div>
        <PageTitle step="04" kicker={`Prove · ${name}`} title={<>The review date hasn't arrived. <span className="text-ink-mute">{r.days_to_go} days to go.</span></>}
          lede={`The plan started ${longDate(r.start)}. On ${longDate(r.review)} the tool compares ${r.kpi_label.toLowerCase()} before and after, against similar teams that did not act.`} />
        <Card className="p-10 text-center max-w-3xl mx-auto" tone="ink">
          <div className="num text-[5rem] leading-none text-teal">{r.days_to_go}</div>
          <div className="eyebrow mt-3">days until {longDate(r.review)}</div>
          <div className="mt-8"><Button onClick={() => setAsOf(REVIEW)}>Fast-forward to the review date →</Button></div>
          <p className="text-[12.5px] text-ink-mute mt-4">Demo only: moves the whole app to Nov 30, 2026. The follow-up months are synthetic.</p>
        </Card>
      </div>
    )
  }
  if (r.status === 'insufficient') {
    return <PageTitle step="04" kicker={`Prove · ${name}`} title="Not enough follow-up data yet." lede={r.reason} />
  }
  const worked = r.verdict === 'worked'
  return (
    <div>
      <PageTitle step="04" kicker={`Prove · review on ${longDate(r.review)}`}
        title={worked
          ? <>It worked: <span className="text-teal">{r.kpi_label.toLowerCase()} fell {per10(Math.abs(r.estimate!))} per 10 people a month</span> more than at comparable teams{r.dollars_per_quarter ? <> — about <span className="num">{money(r.dollars_per_quarter)}</span> a quarter</> : null}.</>
          : <>{r.kpi_label}: {r.verdict}. The plan may need more time or a different action.</>}
        lede="Directional, not causal. The comparison teams share the season and the company; they did not share the plan." />
      <Result r={r} />
      <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
        <p className="text-ink-soft max-w-xl">{worked ? 'Keep the new routine, tell the team what changed because of their answers, and check again at the next survey wave.' : 'Extend the review, or return to the evidence and try the next obstacle.'}</p>
        <div className="flex gap-3"><Button kind="ghost" onClick={() => nav('/value')}>What is this worth across sites? →</Button></div>
      </div>
    </div>
  )
}
