import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import type { Assoc, ItemChange, Quartile } from '../lib/api'
import { month, per10, pts } from '../lib/format'

const INK = '#1B3A4B', TEAL = '#1F8FA8', RUST = '#C8553D', MIST = '#B9C6CC', LINE = '#E3DFD5'

function Tip({ active, payload, label, fmt }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; fmt: (v: number) => string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-line bg-paper-card px-3 py-2 text-[12.5px] shadow-lift">
      <div className="font-semibold mb-1">{label ? month(String(label)) + ' ' + String(label).slice(0, 4) : ''}</div>
      {payload.map((p) => <div key={p.name} className="flex gap-3 justify-between"><span style={{ color: p.color }}>{p.name}</span><span className="tab">{fmt(p.value)}</span></div>)}
    </div>
  )
}

/** Team vs comparable teams, per 10 people per month. Wave closes marked; scoring window shaded. */
export function TrendChart({ data, k, window: win, marks = [], teamLabel }: {
  data: Record<string, number | string>[]; k: string; window?: string[]; marks?: { m: string; label: string; color?: string }[]; teamLabel: string
}) {
  const rows = data.map((d) => ({ month: d.month as string, team: Number(d[k]) * 10, base: Number(d['baseline_' + k]) * 10 }))
  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 16, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid stroke={LINE} vertical={false} />
          {win && win.length > 0 && <ReferenceArea x1={win[0]} x2={win[win.length - 1]} fill={RUST} fillOpacity={0.06} />}
          <XAxis dataKey="month" tickFormatter={month} tickLine={false} axisLine={{ stroke: LINE }} />
          <YAxis tickLine={false} axisLine={false} width={48} />
          {marks.map((x) => <ReferenceLine key={x.m} x={x.m} stroke={x.color ?? MIST} strokeDasharray="2 3" label={{ value: x.label, position: 'top', fontSize: 11, fill: '#6B7F8A' }} />)}
          <Tooltip content={<Tip fmt={(v) => v.toFixed(1)} />} />
          <Line name="Comparable teams" dataKey="base" stroke={MIST} strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
          <Line name={teamLabel} dataKey="team" stroke={RUST} strokeWidth={2.6} dot={{ r: 2.5, fill: RUST }} animationDuration={600} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Wave 1 -> wave 2 change per item, points on a 5-point scale. Drops of 0.30 or more in rust. */
export function ItemChanges({ items }: { items: ItemChange[] }) {
  const max = Math.max(0.9, ...items.map((i) => Math.abs(i.delta)))
  return (
    <ul className="space-y-1.5">
      {items.map((it) => {
        const w = (Math.abs(it.delta) / max) * 50
        const down = it.delta < 0
        const hot = it.delta <= -0.3
        return (
          <li key={it.item} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)_64px] items-center gap-3 text-[13px]">
            <span className={`truncate ${hot ? 'font-semibold text-ink' : 'text-ink-soft'}`} title={it.label}>{it.label}</span>
            <span className="relative h-3.5">
              <span className="absolute left-1/2 top-0 h-full w-px bg-mist" />
              <span className={`absolute top-0.5 h-2.5 rounded-sm ${hot ? 'bg-rust' : down ? 'bg-mist' : 'bg-teal/60'}`}
                style={down ? { right: '50%', width: `${w}%` } : { left: '50%', width: `${w}%` }} />
            </span>
            <span className={`num text-right text-[13px] ${hot ? 'text-rust' : 'text-ink-mute'}`}>{pts(it.delta).replace(' pts', '')}</span>
          </li>
        )
      })}
    </ul>
  )
}

/** Team-waves: item mean (x) vs KPI rate (y). This team highlighted; OLS line through the means. */
export function LinkScatter({ a, teamId, xLabel }: { a: Assoc; teamId: number; xLabel: string }) {
  const pts_ = (a.points ?? []).map((p) => ({ x: p.x, y: p.rate * 10, mine: p.team_id === teamId, wave: p.wave }))
  const others = pts_.filter((p) => !p.mine), mine = pts_.filter((p) => p.mine)
  let line: { x: number; y: number }[] = []
  if (a.slope != null && pts_.length) {
    const mx = pts_.reduce((s, p) => s + p.x, 0) / pts_.length
    const my = pts_.reduce((s, p) => s + p.y, 0) / pts_.length
    const xs = pts_.map((p) => p.x), x0 = Math.min(...xs), x1 = Math.max(...xs)
    const b = a.slope * 10
    line = [{ x: x0, y: my + b * (x0 - mx) }, { x: x1, y: my + b * (x1 - mx) }]
  }
  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 16, bottom: 18, left: -12 }}>
          <CartesianGrid stroke={LINE} />
          <XAxis type="number" dataKey="x" domain={['dataMin - 0.1', 'dataMax + 0.1']} tickFormatter={(v) => Number(v).toFixed(1)} tickLine={false}
            label={{ value: xLabel, position: 'insideBottom', offset: -10, fontSize: 12, fill: '#6B7F8A' }} />
          <YAxis type="number" dataKey="y" tickLine={false} axisLine={false} width={48} />
          <ZAxis range={[46, 46]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v) => Number(v).toFixed(2)} />
          <Scatter name="Other team-waves" data={others} fill={INK} fillOpacity={0.35} isAnimationActive={false} />
          {line.length > 0 && <Scatter data={line} line={{ stroke: TEAL, strokeWidth: 2 }} shape={() => <g />} isAnimationActive={false} legendType="none" />}
          <Scatter name="This team" data={mine} fill={RUST} shape="diamond" isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Gallup meta-analysis style: median KPI rate by engagement quartile. */
export function QuartileBars({ q }: { q: Quartile }) {
  const data = q.quartiles.map((x) => ({ name: x.q === 1 ? 'Bottom' : x.q === 4 ? 'Top' : `Q${x.q}`, v: x.median_rate * 10, q: x.q }))
  return (
    <div className="h-[200px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 18, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke={LINE} vertical={false} />
          <XAxis dataKey="name" tickLine={false} axisLine={{ stroke: LINE }} />
          <YAxis tickLine={false} axisLine={false} width={44} />
          <Tooltip formatter={(v) => [per10(Number(v) / 10), 'per 10 people / month']} cursor={{ fill: 'rgba(27,58,75,0.04)' }} />
          <Bar dataKey="v" radius={[6, 6, 0, 0]} label={{ position: 'top', fontSize: 12, fill: INK, formatter: (v: unknown) => Number(v).toFixed(1) }}>
            {data.map((d) => <Cell key={d.q} fill={d.q === 1 ? RUST : d.q === 4 ? TEAL : MIST} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
