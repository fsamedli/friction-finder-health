import { useNavigate } from 'react-router-dom'
import { ClipboardList, FileText, Plus } from 'lucide-react'
import { api, type Did, type Plan } from '../lib/api'
import { longDate } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { useLoad, useStore, visiblePlans } from '../lib/store'
import { Badge, Button, Card, Empty, ErrorState, PageHeader, PageSkeleton } from '../components/ui'

function StatusCell({ r }: { r: Did | undefined }) {
  if (!r) return <Badge tone="neutral">—</Badge>
  if (r.status === 'not_reached') return <Badge tone="info" dot>In progress · {r.days_to_go} days to review</Badge>
  if (r.status === 'insufficient') return <Badge tone="neutral" dot>Waiting for follow-up data</Badge>
  return <Badge tone={r.verdict === 'worked' ? 'ok' : r.verdict === 'no effect' ? 'crit' : 'warn'} dot>Reviewed · {r.verdict}</Badge>
}

export default function Plans() {
  const { asOf, teamId } = useStore()
  const nav = useNavigate()
  const plans = useLoad(async () => visiblePlans(await api.plans(), asOf), [asOf])
  const results = useLoad(async () => {
    const ps = visiblePlans(await api.plans(), asOf)
    const rs = await Promise.all(ps.map((p) => api.result(p.id, asOf).catch(() => undefined)))
    return Object.fromEntries(ps.map((p, i) => [p.id, rs[i]])) as Record<string, Did | undefined>
  }, [asOf])
  if (plans.error) return <ErrorState error={plans.error} />
  if (!plans.data) return <PageSkeleton />
  const rows: Plan[] = [...plans.data].reverse()
  return (
    <div>
      <PageHeader title="Action plans" sub="Each plan has one focus item, a few actions with owners, and a review date. At the review date the operating KPI is compared with similar teams that did not act."
        actions={<Button variant="decide" icon={<Plus size={15} />} onClick={() => nav(`/teams/${teamId}?tab=plan`)}>New plan</Button>} />
      <Card pad={false}>
        {rows.length === 0 ? <Empty icon={<ClipboardList size={20} />} title="No plans yet" sub="Open a team that needs attention and draft a plan from its evidence." /> : (
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[860px] text-[13.5px]">
              <thead><tr className="border-b border-border bg-canvas/60 text-left text-[12px] text-fg-mute">
                <th className="px-4 py-2.5 font-medium">Team</th><th className="px-3 py-2.5 font-medium">Obstacle</th><th className="px-3 py-2.5 font-medium">KPI to watch</th>
                <th className="px-3 py-2.5 font-medium">Start → review</th><th className="px-3 py-2.5 font-medium">Status</th><th className="px-3 py-2.5" /></tr></thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id} onClick={() => nav(`/impact/${p.id}`)} className="cursor-pointer border-b border-border last:border-0 hover:bg-canvas/60">
                    <td className="px-4 py-3 font-medium">{p.team_label}</td>
                    <td className="px-3 py-3 text-fg-soft max-w-[320px]"><div className="truncate" title={p.obstacle}>{p.obstacle}</div><div className="text-[12px] text-fg-mute">{p.actions.length} actions · owner {p.actions[0]?.owner}</div></td>
                    <td className="px-3 py-3">{KPI_SHORT[p.kpi]}</td>
                    <td className="px-3 py-3 tnum text-fg-soft whitespace-nowrap">{longDate(p.start)} → {longDate(p.review)}</td>
                    <td className="px-3 py-3"><StatusCell r={results.data?.[p.id]} /></td>
                    <td className="px-3 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <a href={`/api/report/${p.id}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12.5px] font-medium text-fg-mute hover:text-fg"><FileText size={14} /> Report</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
