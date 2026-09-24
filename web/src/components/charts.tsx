import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import type { Assoc, ItemChange, Quartile } from '../lib/api'
import { month } from '../lib/format'

export const C = { brand: '#0E8A7E', brandSoft: '#C9ECE7', crit: '#D92D20', critSoft: '#FEE4E2', grey: '#98A2B3', grid: '#EEF0F3', fg: '#101828', mute: '#667085' }
const axis = { tickLine: false, axisLine: false, tick: { fill: C.mute, fontSize: 11.5 } }

function Tip({ active, payload, label, unit }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; unit?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-[12px] shadow-pop">
      {label && <div className="font-semibold mb-1">{/^\d{4}-\d{2}$/.test(String(label)) ? `${month(String(label))} ${String(label).slice(0, 4)}` : label}</div>}
      {payload.filter((p) => p.name).map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: p.color }} />{p.name}</span>
          <span className="tnum font-medium">{Number(p.value).toFixed(1)}{unit ? ` ${unit}` : ''}</span>
        </div>
      ))}
    </div>
  )
}

export function Spark({ data, flagged }: { data: { month: string; rate: number; baseline: number }[]; flagged?: boolean }) {
  return (
    <div className="h-8 w-28" role="img" aria-label={`Trend over ${data.length} months${flagged ? ', above normal variation' : ''}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 3, right: 2, bottom: 3, left: 2 }}>
          <YAxis hide domain={[0, 'dataMax']} />
          <Line dataKey="baseline" stroke={C.grey} strokeWidth={1.2} strokeDasharray="2 2" dot={false} isAnimationActive={false} />
          <Line dataKey="rate" stroke={flagged ? C.crit : C.fg} strokeWidth={1.7} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** A team vs comparable teams, per 10 people per month. */
export function TrendChart({ data, k, window: win, marks = [], teamLabel, height = 280 }: {
  data: Record<string, number | string>[]; k: string; window?: string[]; marks?: { m: string; label: string }[]; teamLabel: string; height?: number
}) {
  const rows = data.map((d) => ({ month: d.month as string, team: Number(d[k]) * 10, base: Number(d['baseline_' + k]) * 10 }))
  const last = rows[rows.length - 1]
  const label = `Line chart, per 10 people per month: ${teamLabel} vs comparable teams, ${rows.length} months${last ? `; latest month ${last.team.toFixed(1)} vs ${last.base.toFixed(1)}` : ''}.`
  return (
    <div style={{ height }} role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 22, right: 8, bottom: 0, left: -14 }}>
          <defs><linearGradient id="gTeam" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={C.crit} stopOpacity={0.16} /><stop offset="100%" stopColor={C.crit} stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid stroke={C.grid} vertical={false} />
          {win && win.length > 0 && <ReferenceArea x1={win[0]} x2={win[win.length - 1]} fill={C.crit} fillOpacity={0.05} label={{ value: 'last 3 months', position: 'insideTopRight', fontSize: 11, fill: C.mute }} />}
          <XAxis dataKey="month" tickFormatter={month} {...axis} />
          <YAxis {...axis} width={44} />
          {marks.map((x) => <ReferenceLine key={x.m} x={x.m} stroke={C.grey} strokeDasharray="3 3" label={{ value: x.label, position: 'top', fontSize: 11, fill: C.mute }} />)}
          <Tooltip content={<Tip unit="per 10 ppl" />} />
          <Legend verticalAlign="bottom" height={26} iconType="plainline" wrapperStyle={{ fontSize: 12, color: C.mute }} />
          <Line name="Comparable teams (same shift, other sites)" dataKey="base" stroke={C.grey} strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
          <Area name={teamLabel} dataKey="team" stroke={C.crit} strokeWidth={2.4} fill="url(#gTeam)" dot={{ r: 2.5, fill: C.crit, strokeWidth: 0 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DidChart({ series, pre, post, start, compLabel, height = 300 }: {
  series: { month: string; treated: number; comparison: number }[]; pre: string[]; post: string[]; start: string; compLabel: string; height?: number
}) {
  const rows = series.map((s) => ({ month: s.month, team: s.treated * 10, comp: s.comparison * 10 }))
  return (
    <div style={{ height }} role="img" aria-label={`Line chart, per 10 people per month: this team vs ${compLabel}, before (${pre.join(', ')}) and after (${post.join(', ')}) the plan start ${start}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 22, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          {pre.length > 0 && <ReferenceArea x1={pre[0]} x2={pre[pre.length - 1]} fill={C.crit} fillOpacity={0.05} label={{ value: 'Before', position: 'insideTop', fontSize: 11, fill: C.crit }} />}
          {post.length > 0 && <ReferenceArea x1={post[0]} x2={post[post.length - 1]} fill={C.brand} fillOpacity={0.08} label={{ value: 'After', position: 'insideTop', fontSize: 11, fill: C.brand }} />}
          <ReferenceLine x={start.slice(0, 7)} stroke={C.fg} strokeDasharray="3 3" label={{ value: 'Plan starts', position: 'top', fontSize: 11, fill: C.fg }} />
          <XAxis dataKey="month" tickFormatter={month} {...axis} />
          <YAxis {...axis} width={44} />
          <Tooltip content={<Tip unit="per 10 ppl" />} />
          <Legend verticalAlign="bottom" height={26} iconType="plainline" wrapperStyle={{ fontSize: 12, color: C.mute }} />
          <Line name={compLabel} dataKey="comp" stroke={C.grey} strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
          <Line name="This team" dataKey="team" stroke={C.crit} strokeWidth={2.6} dot={{ r: 3, fill: C.crit, strokeWidth: 0 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Wave 1 -> wave 2 change per item, points on a 5-point scale. Labels wrap; nothing is clipped. */
export function ItemChanges({ items }: { items: ItemChange[] }) {
  const max = Math.max(0.9, ...items.map((i) => Math.abs(i.delta)))
  return (
    <ul className="divide-y divide-border">
      {items.map((it) => {
        const w = (Math.abs(it.delta) / max) * 50
        const hot = it.delta <= -0.3
        return (
          <li key={it.item} className="grid grid-cols-[minmax(0,1fr)_120px_52px] items-center gap-3 py-2 text-[13px]">
            <span className={hot ? 'font-medium text-fg' : 'text-fg-soft'}><span className="font-mono text-[11px] text-fg-faint mr-1.5">{it.item.toUpperCase()}</span>{it.label}</span>
            <span className="relative h-3">
              <span className="absolute left-1/2 top-0 h-full w-px bg-border-strong" />
              <span className={`absolute top-0.5 h-2 rounded-sm ${hot ? 'bg-crit' : it.delta < 0 ? 'bg-fg-faint' : 'bg-brand-500'}`}
                style={it.delta < 0 ? { right: '50%', width: `${w}%` } : { left: '50%', width: `${w}%` }} />
            </span>
            <span className={`tnum text-right font-medium ${hot ? 'text-crit-700' : 'text-fg-mute'}`}>{it.delta > 0 ? '+' : ''}{it.delta.toFixed(2)}</span>
          </li>
        )
      })}
    </ul>
  )
}

export function LinkScatter({ a, teamId, xLabel, yLabel, height = 280 }: { a: Assoc; teamId?: number; xLabel: string; yLabel: string; height?: number }) {
  const pts = (a.points ?? []).map((p) => ({ x: p.x, y: p.rate * 10, mine: p.team_id === teamId }))
  const others = pts.filter((p) => !p.mine), mine = pts.filter((p) => p.mine)
  let line: { x: number; y: number }[] = []
  if (a.slope != null && pts.length) {
    const mx = pts.reduce((s, p) => s + p.x, 0) / pts.length, my = pts.reduce((s, p) => s + p.y, 0) / pts.length
    const xs = pts.map((p) => p.x), x0 = Math.min(...xs), x1 = Math.max(...xs), b = a.slope * 10
    line = [{ x: x0, y: my + b * (x0 - mx) }, { x: x1, y: my + b * (x1 - mx) }]
  }
  return (
    <div style={{ height }} role="img" aria-label={`Scatter plot of ${pts.length} team-waves: ${xLabel} against ${yLabel}${a.slope != null ? `; slope ${(a.slope * 10).toFixed(2)} per 10 people per point` : ''}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 12, bottom: 22, left: 4 }}>
          <CartesianGrid stroke={C.grid} />
          <XAxis type="number" dataKey="x" domain={['dataMin - 0.1', 'dataMax + 0.1']} tickFormatter={(v) => Number(v).toFixed(1)} {...axis}
            label={{ value: xLabel, position: 'insideBottom', offset: -14, fontSize: 11.5, fill: C.mute }} />
          <YAxis type="number" dataKey="y" {...axis} width={44} label={{ value: yLabel, angle: -90, position: 'insideLeft', offset: 12, fontSize: 11.5, fill: C.mute, dy: 50 }} />
          <ZAxis range={[44, 44]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v) => Number(v).toFixed(2)} />
          <Scatter name="Team-waves" data={others} fill={C.fg} fillOpacity={0.3} isAnimationActive={false} />
          {line.length > 0 && <Scatter data={line} line={{ stroke: C.brand, strokeWidth: 2 }} shape={() => <g />} isAnimationActive={false} legendType="none" />}
          {mine.length > 0 && <Scatter name="This team" data={mine} fill={C.crit} shape="diamond" isAnimationActive={false} />}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

export function QuartileBars({ q, height = 220 }: { q: Quartile; height?: number }) {
  const data = q.quartiles.map((x) => ({ name: x.q === 1 ? 'Bottom 25%' : x.q === 4 ? 'Top 25%' : x.q === 2 ? '2nd' : '3rd', v: x.median_rate * 10, q: x.q }))
  return (
    <div style={{ height }} role="img" aria-label={`Bar chart, median per 10 people per month by engagement quartile: ${data.map((d) => `${d.name} ${d.v.toFixed(1)}`).join(', ')}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 4, bottom: 0, left: -18 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="name" {...axis} />
          <YAxis {...axis} width={40} />
          <Tooltip formatter={(v) => [Number(v).toFixed(1), 'per 10 people / month']} cursor={{ fill: 'rgba(16,24,40,0.03)' }} />
          <Bar dataKey="v" radius={[6, 6, 0, 0]} maxBarSize={56} isAnimationActive={false} label={{ position: 'top', fontSize: 12, fill: C.fg, formatter: (v: unknown) => Number(v).toFixed(1) }}>
            {data.map((d) => <Cell key={d.q} fill={d.q === 1 ? C.crit : d.q === 4 ? C.brand : '#D0D5DD'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
