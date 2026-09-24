import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, KPI_ORDER, type AskResult, type Kpi, type Plan, type PlanAction, type Why } from '../lib/api'
import { longDate } from '../lib/format'
import { DETECT, useLoad } from '../lib/store'
import { Button, Card, Chip, ErrorNote, Eyebrow, Loading, PageTitle } from '../components/ui'

const SHORT: Record<Kpi, string> = { late_departures: 'late departures', absence_days: 'absence days', quits: 'quits', injuries: 'injuries', rework: 'rework' }
const addDays = (d: string, n: number) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }

function ActivePlan({ p, team }: { p: Plan; team: Why['team'] }) {
  const nav = useNavigate()
  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr] stagger">
      <Card className="p-7" tone="teal">
        <div className="flex flex-wrap items-center gap-2">
          <Chip kind="person">Approved by a person</Chip>
          <Chip kind="neutral">In progress since {longDate(p.start)}</Chip>
        </div>
        <h2 className="font-serif text-[1.7rem] font-semibold mt-4 leading-tight">{p.obstacle}</h2>
        <p className="mt-2 text-ink-soft">Focus item: <b className="text-ink">{p.focus}</b> · KPI to watch: <b className="text-ink">{SHORT[p.kpi]}</b></p>
        <ol className="mt-6 space-y-4">
          {p.actions.map((a, i) => (
            <li key={i} className="grid grid-cols-[32px_1fr] gap-3">
              <span className="num text-[1.4rem] text-teal leading-none">{i + 1}</span>
              <div>
                <div className="font-semibold">{a.text}</div>
                <div className="text-[13px] text-ink-mute">{a.owner} · due {longDate(a.due)}</div>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button onClick={() => nav(`/proof/${p.id}`)}>Did it work? →</Button>
          <a href={`/api/report/${p.id}`} target="_blank" rel="noreferrer"><Button kind="ghost">One-page report</Button></a>
        </div>
      </Card>
      <Card className="p-7">
        <Eyebrow>Review</Eyebrow>
        <div className="num text-[2.4rem] mt-2">{longDate(p.review)}</div>
        <p className="text-ink-soft mt-2 text-[14px]">On the review date the tool compares {team.team_name}'s {SHORT[p.kpi]} before and after the plan with similar teams that did not act.</p>
        <Eyebrow className="mt-6 mb-2">Every other Monday, ten minutes</Eyebrow>
        <ul className="text-[14px] space-y-1.5 text-ink-soft">
          <li>Did we complete the actions we committed to?</li>
          <li>Did completing them make a difference?</li>
          <li>What do we keep, change, or stop?</li>
        </ul>
        <p className="text-[12px] text-ink-mute mt-3">The check-in questions follow Gallup's State of the Team handout.</p>
      </Card>
    </div>
  )
}

function Draft({ w, ev }: { w: Why; ev: AskResult | null }) {
  const nav = useNavigate()
  const drop = w.item_changes.find((c) => c.delta <= -0.3)
  const kpi: Kpi = KPI_ORDER.find((k) => w.excess?.[k]?.flagged) ?? 'late_departures'
  const ownerLine = ev?.evidence.find((e) => e.kind === 'owner')?.statement ?? ''
  const owner = ownerLine.match(/: (.+?) \(/)?.[1] ?? 'Site operations manager'
  const theme = ev?.assessment?.label.match(/: ([^.]+)\./)?.[1] ?? drop?.label.toLowerCase() ?? 'the obstacle behind the drop'
  const start = DETECT > '2026-09-21' ? DETECT : '2026-09-21'
  const [obstacle, setObstacle] = useState(`${theme[0].toUpperCase()}${theme.slice(1)}`)
  const [actions, setActions] = useState<PlanAction[]>([
    { text: `Fix the ${theme} step that the comments describe, and write the new routine down`, owner, due: addDays(start, 7) },
    { text: `Ask the team in the next huddle what gets in the way of “${drop?.label ?? 'doing the work right'}”`, owner: `${w.team.team_name} team manager`, due: addDays(start, 14) },
    { text: 'Ten-minute check-in every other Monday: did the actions happen, did they help?', owner: `${w.team.team_name} team manager`, due: addDays(start, 21) },
  ])
  const [saved, setSaved] = useState<Plan | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const set = (i: number, k: keyof PlanAction, v: string) => setActions((a) => a.map((x, j) => (j === i ? { ...x, [k]: v } : x)))

  const approve = async () => {
    setBusy(true); setErr(null)
    try {
      const p = await api.createPlan({ team_id: w.team.team_id, item: drop?.item ?? 'grand', kpi, obstacle, focus: drop ? `${drop.label} (${drop.item})` : 'Overall engagement',
        actions: actions.filter((a) => a.text.trim()), start, status: 'approved', note: 'Approved in the demo' })
      setSaved(p)
    } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(false) }
  }

  if (saved) {
    return (
      <Card className="p-8 max-w-3xl animate-rise" tone="teal">
        <Chip kind="person">Approved</Chip>
        <h2 className="font-serif text-[1.8rem] font-semibold mt-3">Plan saved. Review on {longDate(saved.review)}.</h2>
        <p className="text-ink-soft mt-2">The tool will compare {w.team.team_name}'s {SHORT[saved.kpi]} before and after, against similar teams, on that date. Until then it shows how many days are left.</p>
        <div className="mt-6 flex gap-3"><Button onClick={() => nav(`/proof/${saved.id}`)}>Open the review →</Button>
          <a href={`/api/report/${saved.id}`} target="_blank" rel="noreferrer"><Button kind="ghost">One-page report</Button></a></div>
      </Card>
    )
  }

  return (
    <Card className="p-7 max-w-4xl" tone="rust">
      <div className="flex flex-wrap items-center gap-2"><Chip kind="computed">Drafted from the evidence</Chip><Chip kind="person">Needs your decision</Chip></div>
      <label className="block mt-5">
        <Eyebrow>Obstacle to test</Eyebrow>
        <input value={obstacle} onChange={(e) => setObstacle(e.target.value)} className="mt-1 w-full bg-transparent font-serif text-[1.6rem] font-semibold border-b border-line focus:border-rust focus:outline-none py-1" />
      </label>
      <p className="mt-3 text-ink-soft text-[14px]">Focus item: <b className="text-ink">{drop?.label ?? 'overall engagement'}</b> · KPI to watch: <b className="text-ink">{SHORT[kpi]}</b> · review 60 days after start</p>
      <div className="mt-6 space-y-4">
        {actions.map((a, i) => (
          <div key={i} className="grid grid-cols-[28px_1fr] gap-3">
            <span className="num text-[1.3rem] text-rust">{i + 1}</span>
            <div className="grid gap-2 sm:grid-cols-[1fr_220px_140px]">
              <input value={a.text} onChange={(e) => set(i, 'text', e.target.value)} className="rounded-lg border border-line bg-paper px-3 py-2 text-[14px] focus:outline-none focus:ring-2 focus:ring-rust/25" />
              <input value={a.owner} onChange={(e) => set(i, 'owner', e.target.value)} className="rounded-lg border border-line bg-paper px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-rust/25" />
              <input type="date" value={a.due} onChange={(e) => set(i, 'due', e.target.value)} className="rounded-lg border border-line bg-paper px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-rust/25" />
            </div>
          </div>
        ))}
      </div>
      {err && <p className="mt-4 text-rust text-sm">{err}</p>}
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Button kind="person" onClick={approve} disabled={busy || !obstacle.trim()}>{busy ? 'Saving…' : 'Approve plan'}</Button>
        <Button kind="quiet" onClick={() => nav(`/why/${w.team.team_id}`)}>Back to the evidence</Button>
        <span className="text-[12.5px] text-ink-mute ml-auto max-w-xs">The tool drafts; a person decides. Nothing is sent to the team until someone approves.</span>
      </div>
    </Card>
  )
}

export default function PlanPage() {
  const { teamId } = useParams()
  const id = Number(teamId)
  const why = useLoad(() => api.why(id, DETECT), [id])  // the plan is drafted from what was known when wave 2 came in
  const plans = useLoad(() => api.plans(), [id])
  const [ev, setEv] = useState<AskResult | null>(null)
  useEffect(() => {
    if (why.data && !why.data.suppressed) api.ask(`Why did the ${why.data.team.site} ${why.data.team.team_name} team's scores drop?`, true).then(setEv).catch(() => setEv(null))
  }, [why.data])
  if (why.error || plans.error) return <ErrorNote error={(why.error ?? plans.error)!} />
  if (!why.data || !plans.data) return <Loading />
  const w = why.data
  const existing = plans.data.filter((p) => p.team_id === id && p.status === 'approved').slice(-1)[0]
  const name = `${w.team.site} ${w.team.team_name}`
  if (w.suppressed) return <PageTitle step="03" kicker={`Act · ${name}`} title="Plans for teams under 4 people are made at site level." lede={w.reason} />
  return (
    <div>
      <PageTitle step="03" kicker={`Act · ${name}`}
        title={existing ? <>{name} already has a plan. <span className="text-teal">One focus item, three actions, one review date.</span></> : <>Draft a plan a busy manager can approve in one minute.</>}
        lede="Shaped like Gallup's State of the Team conversation: one item to work on, a few actions with owners and dates, and a short check-in. The finished plan fits alongside Gallup Access; it does not replace it." />
      {existing ? <ActivePlan p={existing} team={w.team} /> : <Draft w={w} ev={ev} />}
    </div>
  )
}
