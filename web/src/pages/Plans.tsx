import { useNavigate } from 'react-router-dom'
import { CalendarClock, ClipboardCheck, ClipboardList, FileText, HelpCircle, Plus, Timer } from 'lucide-react'
import { api, type Did, type Plan, type PlanRow, type PlansBoard, type PlanState } from '../lib/api'
import { longDate } from '../lib/format'
import { KPI_SHORT, reviewTone, reviewWord } from '../lib/labels'
import { useFunctions, useLoad, useStore, visiblePlans } from '../lib/store'
import { Badge, Button, Card, CardHeader, CsvButton, Empty, ErrorState, PageHeader, PageSkeleton } from '../components/ui'

const STATE: Record<PlanState, { label: string; tone: 'neutral' | 'info' | 'warn' | 'ok' }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  approved: { label: 'Approved', tone: 'info' },
  in_review: { label: 'In review', tone: 'warn' },
  reviewed: { label: 'Reviewed', tone: 'ok' },
}

/** Used only when this server has no /api/plans/board: the same states, derived from the plan and its review result. */
async function deriveBoard(asOf: string): Promise<PlansBoard> {
  const all = await api.plans()
  const ps = [...visiblePlans(all, asOf), ...all.filter((p) => p.status === 'draft')]
  const rs = await Promise.all(ps.map((p) => (p.status === 'draft' ? Promise.resolve(null) : api.result(p.id, asOf).catch(() => null))))
  const plans: PlanRow[] = ps.map((p, i) => {
    const r: Did | null = rs[i]
    const state: PlanState = p.status === 'draft' ? 'draft' : !r || r.status === 'not_reached' ? 'approved' : r.status === 'insufficient' ? 'in_review' : 'reviewed'
    return { ...p, state, result: r }
  })
  return {
    plans,
    queue: {
      due_reviews: plans.filter((p) => p.state === 'reviewed' || p.state === 'in_review').map((p) => p.id),
      missing_follow_ups: plans.filter((p) => p.state === 'in_review').map((p) => p.id),
      inconclusive: plans.filter((p) => p.result?.status === 'ok' && p.result.verdict === 'inconclusive').map((p) => p.id),
    },
  }
}

function StateCell({ p }: { p: PlanRow }) {
  const r = p.result
  const s = STATE[p.state] ?? STATE.approved
  return (
    <div className="space-y-1">
      <Badge tone={s.tone} dot>{s.label}</Badge>
      {r?.status === 'not_reached' && <div className="text-[12px] text-fg-mute">{r.days_to_go} days to review</div>}
      {r?.status === 'insufficient' && <div className="text-[12px] text-fg-mute">waiting for follow-up data</div>}
      {r?.status === 'ok' && <div><Badge tone={reviewTone(r.verdict)}>{reviewWord(r.verdict)}</Badge></div>}
    </div>
  )
}

function Queue({ title, icon, ids, rows, empty }: { title: string; icon: React.ReactNode; ids: string[]; rows: PlanRow[]; empty: string }) {
  const nav = useNavigate()
  const items = ids.map((id) => rows.find((p) => p.id === id)).filter(Boolean) as PlanRow[]
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2">{icon}{title}</span>} right={<Badge tone={items.length ? 'warn' : 'neutral'}>{items.length}</Badge>} />
      {items.length === 0 ? <p className="text-[13px] text-fg-mute">{empty}</p> : (
        <ul className="space-y-2">
          {items.map((p) => (
            <li key={p.id}><button onClick={() => nav(`/review/${p.id}`)} className="w-full rounded-lg border border-border px-3 py-2 text-left text-[13px] hover:bg-canvas">
              <span className="font-medium">{p.team_label}</span> · <span className="text-fg-soft">{p.obstacle}</span>
              <span className="block text-[12px] text-fg-mute">review {longDate(p.review)}</span>
            </button></li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function Plans() {
  const { asOf, teamId } = useStore()
  const nav = useNavigate()
  const fns = useFunctions()
  const board = useLoad<PlansBoard | null>(() => (fns === null ? Promise.resolve(null) : fns.length ? api.plansBoard(asOf) : deriveBoard(asOf)), [asOf, fns === null, !!fns?.length])
  if (board.error) return <ErrorState error={board.error} onRetry={() => window.location.reload()} />
  if (!board.data) return <PageSkeleton />
  const rows: PlanRow[] = [...board.data.plans].reverse()
  const q = board.data.queue
  const owner = (p: Plan) => p.owner || p.actions[0]?.owner || 'Owner needed'
  const measure = (p: Plan) => p.measure || `${KPI_SHORT[p.kpi]} per 10 people a month`
  return (
    <div>
      <PageHeader title="Action plans" sub="Each plan is a checklist with a responsible person and a due date per task, one operational measure, a review date and a success criterion. A person approves every plan; at the review date the operating number is compared with similar teams that did not act."
        actions={<><CsvButton filename="action_plans.csv" rows={() => rows.map((p) => ({ team: p.team_label, state: p.state, obstacle: p.obstacle, owner: owner(p), measure: measure(p), success: p.success ?? '', focus: p.focus, kpi: p.kpi, start: p.start, review: p.review,
          result: p.result?.status === 'ok' ? reviewWord(p.result.verdict) : p.result?.status ?? '', tasks_done: p.progress?.done ?? 0, tasks: p.progress?.total ?? p.actions.length, actions: p.actions.map((a) => `${a.status === 'done' ? '[x]' : '[ ]'} ${a.text} (${a.owner}, ${a.due})`).join(' | ') }))} /><Button variant="decide" icon={<Plus size={15} />} onClick={() => nav(`/investigate/${teamId}?focus=act`)}>New plan</Button></>} />
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Queue title="Due reviews" icon={<CalendarClock size={16} className="text-fg-mute" />} ids={q.due_reviews} rows={rows} empty="No review is due on this date." />
        <Queue title="Missing follow-ups" icon={<Timer size={16} className="text-fg-mute" />} ids={q.missing_follow_ups} rows={rows} empty="No plan is waiting for follow-up data." />
        <Queue title="Inconclusive outcomes" icon={<HelpCircle size={16} className="text-fg-mute" />} ids={q.inconclusive} rows={rows} empty="No inconclusive outcome yet." />
      </div>
      <Card pad={false}>
        {rows.length === 0 ? <Empty icon={<ClipboardList size={20} />} title="No plans yet" sub="Open a team that needs attention and draft a plan from its evidence." /> : (
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[1000px] text-[13.5px]">
              <thead><tr className="border-b border-border bg-canvas/60 text-left text-[12px] text-fg-mute">
                <th className="px-4 py-2.5 font-medium">Team and obstacle</th><th className="px-3 py-2.5 font-medium">Owner</th><th className="px-3 py-2.5 font-medium">Operational measure</th>
                <th className="px-3 py-2.5 font-medium">Success criterion</th><th className="px-3 py-2.5 font-medium">Checklist</th><th className="px-3 py-2.5 font-medium">Start → review</th><th className="px-3 py-2.5 font-medium">State</th><th className="px-3 py-2.5" /></tr></thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id} onClick={() => nav(p.state === 'draft' ? `/investigate/${p.team_id}?focus=act` : `/plans/${p.id}`)} className="cursor-pointer border-b border-border align-top last:border-0 hover:bg-canvas/60">
                    <td className="px-4 py-3 max-w-[300px]"><div className="font-medium">{p.team_label}</div><div className="text-fg-soft truncate" title={p.obstacle}>{p.obstacle}</div><div className="text-[12px] text-fg-mute">{p.actions.length} actions · focus {p.focus}</div></td>
                    <td className="px-3 py-3 text-fg-soft">{owner(p)}</td>
                    <td className="px-3 py-3 text-fg-soft">{measure(p)}</td>
                    <td className="px-3 py-3 text-fg-soft max-w-[220px]">{p.success || <span className="text-fg-faint">not recorded with this plan</span>}</td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {(() => { const d = p.progress?.done ?? 0, t = p.progress?.total ?? p.actions.length; return (
                        <div className="min-w-[110px]"><div className="flex items-center gap-1.5 tnum text-[13px]"><ClipboardCheck size={14} className={d === t && t > 0 ? 'text-ok-700' : 'text-fg-mute'} />{d} of {t} done</div>
                          <div className="mt-1 h-1 w-24 overflow-hidden rounded-full bg-canvas"><div className="h-full rounded-full bg-ok" style={{ width: `${t ? (d / t) * 100 : 0}%` }} /></div></div>) })()}
                    </td>
                    <td className="px-3 py-3 tnum text-fg-soft whitespace-nowrap">{longDate(p.start)} → {longDate(p.review)}</td>
                    <td className="px-3 py-3"><StateCell p={p} /></td>
                    <td className="px-3 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {p.state !== 'draft' && <span className="inline-flex items-center gap-3 whitespace-nowrap">
                        <button onClick={() => nav(`/review/${p.id}`)} className="text-[12.5px] font-medium text-fg-mute hover:text-fg">Review</button>
                        <a href={`/api/report/${p.id}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12.5px] font-medium text-fg-mute hover:text-fg"><FileText size={14} /> Report</a></span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="mt-3 text-[12px] text-fg-mute">Approving a plan records the decision; it is never evidence that an answer was correct. The review judges the operating number.</p>
    </div>
  )
}
