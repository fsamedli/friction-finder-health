import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Lock, Search } from 'lucide-react'
import { api, type Status, type TeamRow } from '../lib/api'
import { money, monthRange, num, signed } from '../lib/format'
import { useLoad, useStore } from '../lib/store'
import { Spark } from '../components/charts'
import { Badge, Card, ErrorState, Method, PageHeader, PageSkeleton, Segmented, StatusBadge, cx } from '../components/ui'

type Filter = 'all' | 'attention' | 'normal'

function Kpi({ t, k }: { t: TeamRow; k: 'late_departures' | 'absence_days' | 'quits' }) {
  const e = t.excess_by_kpi[k]
  if (!e) return <span className="text-fg-faint">—</span>
  if (!e.judgeable) return <span className="text-[12px] text-fg-faint whitespace-nowrap" title={`${e.observed} observed, ${e.expected} expected: fewer than 3 expected in three months`}>too rare to judge</span>
  return (
    <div className="flex items-center gap-2">
      <Spark data={t.spark[k] ?? []} flagged={e.flagged} />
      <span className={cx('tnum text-[12.5px] whitespace-nowrap', e.flagged ? 'text-crit-700 font-medium' : 'text-fg-mute')}>{num(e.observed)} <span className="text-fg-faint">/ {num(e.expected)}</span></span>
    </div>
  )
}

export default function Teams() {
  const { siteId, asOf } = useStore()
  const nav = useNavigate()
  const [f, setF] = useState<Filter>('all')
  const [q, setQ] = useState('')
  const { data: b, error } = useLoad(() => api.board(siteId, asOf), [siteId, asOf])
  if (error) return <ErrorState error={error} />
  if (!b) return <PageSkeleton />
  const order: Record<Status, number> = { red: 0, amber: 1, green: 2, rolled_up: 3 }
  const rows = b.teams
    .filter((t) => f === 'all' || (f === 'attention' ? t.status === 'red' || t.status === 'amber' : t.status === 'green'))
    .filter((t) => t.team_name.toLowerCase().includes(q.toLowerCase()))
    .sort((a, c) => order[a.status] - order[c.status] || c.excess_cost - a.excess_cost)
  const nAtt = b.teams.filter((t) => t.status === 'red' || t.status === 'amber').length

  return (
    <div>
      <PageHeader crumbs={<>{b.site} DC</>} title="Teams" sub={`Every team at ${b.site}, compared with teams on the same shift at the other sites · ${monthRange(b.window)}`}
        actions={<Method>Observed / expected: the team's count in the last three full months vs the count comparable teams' rate predicts for a team this size. Red means both operations and engagement moved beyond normal variation; amber means one did.</Method>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <Segmented value={f} onChange={setF} options={[{ id: 'all', label: `All ${b.teams.length}` }, { id: 'attention', label: `Needs attention ${nAtt}` }, { id: 'normal', label: 'Normal' }]} />
          <label className="ml-auto flex h-9 items-center gap-2 rounded-lg border border-border-strong px-2.5 focus-within:ring-4 focus-within:ring-brand/10">
            <Search size={15} className="text-fg-faint" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search teams" className="w-40 bg-transparent text-[13px] focus:outline-none" />
          </label>
        </div>
        <div className="overflow-x-auto scroll-thin">
          <table className="w-full min-w-[1040px] text-[13.5px]">
            <thead>
              <tr className="border-b border-border bg-canvas/60 text-left text-[12px] font-medium text-fg-mute">
                <th className="px-4 py-2.5 font-medium">Team</th>
                <th className="px-3 py-2.5 font-medium">Status</th>
                <th className="px-3 py-2.5 font-medium">Late departures <span className="text-fg-faint">obs / exp</span></th>
                <th className="px-3 py-2.5 font-medium">Absence days <span className="text-fg-faint">obs / exp</span></th>
                <th className="px-3 py-2.5 font-medium">Quits</th>
                <th className="px-3 py-2.5 font-medium">Largest survey change</th>
                <th className="px-3 py-2.5 font-medium text-right">Excess cost</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => {
                const locked = t.status === 'rolled_up'
                const d = t.engagement?.biggest_drop
                return (
                  <tr key={t.team_id} onClick={() => !locked && nav(`/teams/${t.team_id}`)}
                    className={cx('border-b border-border last:border-0', locked ? 'bg-canvas/40 text-fg-mute' : 'cursor-pointer hover:bg-canvas/60')}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-fg">{t.team_name}</div>
                      <div className="text-[12px] text-fg-mute">{t.shift} shift · {t.headcount} people</div>
                    </td>
                    <td className="px-3 py-3"><StatusBadge s={t.status} /></td>
                    {locked ? (
                      <td colSpan={5} className="px-3 py-3 text-[12.5px]"><span className="inline-flex items-center gap-1.5"><Lock size={13} /> Fewer than 4 people. Included in site totals only, so no one can be identified.</span></td>
                    ) : (<>
                      <td className="px-3 py-3"><Kpi t={t} k="late_departures" /></td>
                      <td className="px-3 py-3"><Kpi t={t} k="absence_days" /></td>
                      <td className="px-3 py-3"><Kpi t={t} k="quits" /></td>
                      <td className="px-3 py-3">
                        {d ? <div className="max-w-[240px]"><div className="truncate text-fg-soft" title={d.label}>{d.label}</div>
                          <div className="flex items-center gap-2 text-[12px]"><span className={cx('tnum font-medium', d.significant ? 'text-crit-700' : 'text-fg-mute')}>{signed(d.delta)} pts</span>{d.significant ? <Badge tone="crit">beyond noise</Badge> : <span className="text-fg-faint">within noise</span>}</div></div>
                          : <span className="text-[12.5px] text-fg-faint">Hidden: a wave has &lt; 4 respondents</span>}
                      </td>
                      <td className="px-3 py-3 text-right tnum font-medium">{t.excess_cost > 0 ? money(t.excess_cost) : <span className="text-fg-faint">—</span>}</td>
                    </>)}
                    <td className="pr-3">{!locked && <ChevronRight size={16} className="text-fg-faint" />}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="border-t border-border px-4 py-3 text-[12px] text-fg-faint">Ranks obstacles, not managers. Observed / expected over the last three full months; expected = comparable teams' rate × this team's size.</p>
      </Card>
    </div>
  )
}
