import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts'

/** Team rate (solid) vs comparable teams (dashed). Last `hi` months shaded as the scoring window. */
export default function Spark({ data, flagged }: { data: { month: string; rate: number; baseline: number }[]; flagged?: boolean }) {
  const stroke = flagged ? '#C8553D' : '#1B3A4B'
  return (
    <div className="h-[38px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={[0, 'dataMax']} />
          <Line type="monotone" dataKey="baseline" stroke="#B9C6CC" strokeWidth={1.25} strokeDasharray="3 3" dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="rate" stroke={stroke} strokeWidth={1.8} dot={false} isAnimationActive animationDuration={900} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
