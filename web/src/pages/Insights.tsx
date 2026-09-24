import { useState } from 'react'
import { api, KPI_ORDER, type Kpi } from '../lib/api'
import { num, per10, pval, signed } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { useLoad, useStore } from '../lib/store'
import { LinkScatter, QuartileBars } from '../components/charts'
import { Badge, Card, CardHeader, Empty, ErrorState, Method, PageHeader, PageSkeleton, cx } from '../components/ui'

const ITEMS = ['grand', 'q01', 'q02', 'q03', 'q04', 'q05', 'q06', 'q07', 'q08', 'q09', 'q10', 'q11', 'q12']

export default function Insights() {
  const { meta } = useStore()
  const grid = useLoad(() => api.links(), [])
  const [sel, setSel] = useState<{ kpi: Kpi; item: string }>({ kpi: 'late_departures', item: 'q02' })
  const one = useLoad(() => api.link(sel.kpi, sel.item), [sel.kpi, sel.item])
  if (grid.error) return <ErrorState error={grid.error} />
  if (!grid.data) return <PageSkeleton />
  const tested = grid.data.filter((x) => x.slope != null).length
  const linked = grid.data.filter((x) => x.verdict === 'association').length
  const a = one.data?.association, q = one.data?.quartile
  const lbl = (it: string) => (it === 'grand' ? 'Overall' : it.toUpperCase())
  return (
    <div>
      <PageHeader title="Engagement × operations" sub={<>Which engagement items move with which operating KPIs, across every reportable team-wave at Northline. This is the comparison Gallup delivers today as a once-a-year Business Impact Analysis — here it runs on the client's own records, every month.</>}
        actions={<Badge tone="neutral">Association, not cause</Badge>} />
      <Card>
        <CardHeader title="Link map" sub={`${linked} of ${tested} pairs linked at 95% confidence · about ${Math.round(tested * 0.05)} would light up by chance, so treat a single cell as a lead, not a finding`}
          right={<Method>For each KPI × item pair: OLS of the team-wave KPI rate (the quarter the survey closed in) on the item mean, standard errors clustered by team. A cell is "linked" when the 95% interval excludes zero. Injuries are too rare at this size to test.</Method>} />
        <div className="overflow-x-auto scroll-thin">
          <table className="w-full min-w-[760px] border-separate border-spacing-1 text-[12px]">
            <thead><tr><th className="w-36" />{ITEMS.map((it) => <th key={it} title={meta?.items[it]} className={cx('pb-1 font-medium', it === sel.item ? 'text-brand-700' : 'text-fg-mute')}>{lbl(it)}</th>)}</tr></thead>
            <tbody>
              {KPI_ORDER.map((k) => (
                <tr key={k}>
                  <td className={cx('pr-2 text-[12.5px] font-medium whitespace-nowrap', k === sel.kpi ? 'text-brand-700' : 'text-fg-soft')}>{KPI_SHORT[k]}</td>
                  {ITEMS.map((it) => {
                    const c = grid.data!.find((x) => x.kpi === k && x.item === it)
                    const on = k === sel.kpi && it === sel.item
                    const strength = c?.p != null ? Math.min(1, -Math.log10(Math.max(c.p, 1e-6)) / 5) : 0
                    return (
                      <td key={it}>
                        <button onClick={() => setSel({ kpi: k, item: it })} title={c ? `${c.verdict}${c.slope != null ? ` · ${pval(c.p)}` : ''}` : ''}
                          className={cx('h-9 w-full rounded-md text-[11px] font-medium transition', on ? 'ring-2 ring-fg ring-offset-1' : '',
                            c?.verdict === 'association' ? 'text-white' : c?.verdict === 'too rare to test' ? 'bg-canvas text-fg-faint' : 'bg-surface text-fg-faint ring-1 ring-border')}
                          style={c?.verdict === 'association' ? { background: `rgba(14,138,126,${0.45 + 0.55 * strength})` } : undefined}>
                          {c?.verdict === 'association' ? 'linked' : c?.verdict === 'too rare to test' ? '·' : '—'}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title={`${KPI_SHORT[sel.kpi]} vs ${sel.item === 'grand' ? 'overall engagement' : `${sel.item.toUpperCase()} · ${meta?.items[sel.item] ?? ''}`}`} sub={`Each dot is one team in one survey wave · ${a?.n_cells ?? '…'} team-waves`} />
          {!a ? <PageSkeleton /> : a.verdict === 'too rare to test' ? <Empty title="Too rare to test" sub="Most team-quarters have zero events. Needs a year or more of history." />
            : <LinkScatter a={a} xLabel={`${lbl(sel.item)} mean (1–5)`} yLabel="per 10 people / month" />}
          {a?.slope != null && <p className="mt-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px] text-fg-soft"><b className="text-fg">{a.verdict === 'association' ? 'Linked.' : 'No link detected.'}</b> Each 1-point lower score goes with {per10(Math.abs(a.slope))} {a.slope < 0 ? 'more' : 'fewer'} {KPI_SHORT[sel.kpi].toLowerCase()} per 10 people a month (95% CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}, {pval(a.p)}; {a.n_teams} teams).</p>}
        </Card>
        <Card>
          <CardHeader title="Top vs bottom quartile" sub="Median KPI per 10 people a month, by engagement quartile — the presentation Gallup's meta-analysis uses" />
          {q ? <QuartileBars q={q} /> : <PageSkeleton />}
          {q?.pct_diff != null && <p className="mt-2 text-[13px] text-fg-soft">Top-quartile team-waves have <b className="text-fg">{num(Math.abs(q.pct_diff))}% {q.pct_diff >= 0 ? 'fewer' : 'more'}</b> {KPI_SHORT[sel.kpi].toLowerCase()} than bottom-quartile ones ({q.n_per_quartile} team-waves each).</p>}
        </Card>
      </div>
    </div>
  )
}
