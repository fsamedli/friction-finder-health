import { useState } from 'react'
import { api } from '../lib/api'
import { useLoad, useStore } from '../lib/store'
import { Badge, Card, CardHeader, PageHeader, PageSkeleton, Tabs } from '../components/ui'

type T = 'assumptions' | 'architecture' | 'evaluation' | 'feedback'

function Architecture() {
  const box = (x: number, y: number, w: number, title: string, sub: string, tone: 'plain' | 'code' | 'ai' | 'person' = 'plain') => {
    const s = { plain: ['#FFFFFF', '#D0D5DD'], code: ['#E7F6F4', '#0E8A7E'], ai: ['#F4F3FF', '#6941C6'], person: ['#FFFAEB', '#DC6803'] }[tone]
    return (
      <g>
        <rect x={x} y={y} width={w} height={56} rx={10} fill={s[0]} stroke={s[1]} strokeWidth={1.3} />
        <text x={x + 12} y={y + 23} fontFamily="Geist, sans-serif" fontWeight={600} fontSize={13} fill="#101828">{title}</text>
        <text x={x + 12} y={y + 41} fontFamily="Geist, sans-serif" fontSize={11} fill="#667085">{sub}</text>
      </g>
    )
  }
  const arrow = (x1: number, y1: number, x2: number, y2: number) => <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#98A2B3" strokeWidth={1.3} markerEnd="url(#ah)" />
  return (
    <svg viewBox="0 0 980 340" className="w-full h-auto" role="img" aria-label="Architecture">
      <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#98A2B3" /></marker></defs>
      {box(20, 20, 210, 'Client data', 'Survey export (HR) · ops logs (CSV)')}
      {box(20, 120, 210, 'DuckDB views', 'n ≥ 4 enforced in SQL', 'code')}
      {box(20, 220, 210, 'Documents & comments', 'retrieval index (small teams excluded)')}
      {box(300, 50, 270, 'impact.py · detect / explain / prove', 'Poisson excess · OLS · DiD · no AI', 'code')}
      {box(300, 160, 270, 'agent.py · evidence brief', 'SQL on views · retrieval · verdict rules', 'code')}
      {box(300, 262, 270, 'Azure OpenAI (GW) · gpt-5-mini', 'reads the question · writes the brief', 'ai')}
      {box(640, 110, 150, 'FastAPI', 'typed endpoints')}
      {box(830, 50, 130, 'Web app', 'this product')}
      {box(830, 170, 130, 'Manager', 'approves · flags', 'person')}
      {arrow(125, 76, 125, 118)}{arrow(230, 148, 298, 82)}{arrow(230, 148, 298, 186)}{arrow(230, 248, 298, 196)}
      {arrow(435, 216, 435, 260)}{arrow(570, 78, 638, 130)}{arrow(570, 188, 638, 146)}{arrow(790, 132, 828, 82)}{arrow(895, 106, 895, 168)}
      <text x={300} y={40} fontSize={11} fill="#0B6E65" fontFamily="Geist, sans-serif">every number on screen comes from these two modules</text>
    </svg>
  )
}

export default function Trust() {
  const { meta } = useStore()
  const [t, setT] = useState<T>('assumptions')
  const a = useLoad(() => api.assumptions(), [])
  const ev = useLoad(() => api.evals(), [])
  const fb = useLoad(() => api.feedback(), [])
  return (
    <div>
      <PageHeader title="Trust & method" sub="What we assumed, how the system works, how we know it's right, and what the judges changed. The company is fictional and the data is synthetic; the methods are what we're showing." />
      <Tabs value={t} onChange={setT} tabs={[{ id: 'assumptions', label: 'Assumptions' }, { id: 'architecture', label: 'Architecture' }, { id: 'evaluation', label: 'Evaluation' }, { id: 'feedback', label: 'You told us → we changed', count: fb.data?.length }]} />
      <div className="mt-6">
        {t === 'assumptions' && (!a.data ? <PageSkeleton /> : (
          <Card pad={false}>
            <table className="w-full text-[13.5px]">
              <tbody>{a.data.rows.map((r) => (
                <tr key={r.k} className="border-b border-border last:border-0 align-top"><td className="w-48 px-5 py-3 font-medium">{r.k}</td><td className="px-3 py-3">{r.v}</td><td className="px-5 py-3 text-[12.5px] text-fg-mute">{r.why}</td></tr>
              ))}</tbody>
            </table>
            <div className="border-t border-border bg-canvas/50 px-5 py-3 text-[13px]"><b>With real data we would need:</b> <span className="text-fg-soft">{a.data.with_real_data.join(' · ')}</span></div>
          </Card>
        ))}
        {t === 'architecture' && (
          <Card>
            <CardHeader title="An AI-assisted workflow" sub="Fixed steps; the AI model at two of them; deterministic queries and statistical checks; a person at every decision. No autonomous actions."
              right={<><Badge tone="brand">code computes</Badge><Badge tone="ai">AI reads & writes</Badge><Badge tone="warn">person decides</Badge></>} />
            <Architecture />
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3 text-[13px]">
              <div className="rounded-lg bg-canvas p-3"><b>What the AI does</b><p className="mt-1 text-fg-soft">Turns a question into a structured request, and writes the brief from evidence it is handed. Model: {meta?.model ?? 'none configured (rules mode)'}.</p></div>
              <div className="rounded-lg bg-canvas p-3"><b>What the AI never does</b><p className="mt-1 text-fg-soft">Produce a number, decide a verdict, see respondent rows, or approve a plan. Every number in a brief is checked against the evidence.</p></div>
              <div className="rounded-lg bg-canvas p-3"><b>Without a model key</b><p className="mt-1 text-fg-soft">Everything except the written brief still works: rules-based question reading, keyword retrieval, templated text.</p></div>
            </div>
          </Card>
        )}
        {t === 'evaluation' && (!ev.data ? <PageSkeleton /> : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {ev.data.map((e) => (
              <Card key={e.file}>
                <CardHeader title={e.model === 'rules-only' ? 'Rules mode (no model)' : e.model} sub={`Gold questions scored against planted answers · ${e.ts?.slice(0, 10)}`} right={<span className="text-[26px] font-semibold tnum">{e.passed}/{e.total}</span>} />
                <div className="grid grid-cols-4 gap-2 text-center text-[12px]">
                  {Object.entries(e.matrix ?? {}).filter(([k]) => k !== 'FN*').map(([k, n]) => <div key={k} className="rounded-lg bg-canvas py-2.5"><div className="text-[18px] font-semibold tnum">{n}</div><div className="text-fg-mute">{k}</div></div>)}
                </div>
                <p className="mt-3 text-[12px] text-fg-mute">Refusals and suppressions count as true negatives.</p>
              </Card>
            ))}
            <Card className="md:col-span-2 border-warn-100 bg-warn-50/50"><p className="text-[13px] text-warn-700"><b>Known limit.</b> The team wrote both the data and the gold questions. A held-out set written by someone who has not seen the planted answers, and a small user test with site managers, are next.</p></Card>
          </div>
        ))}
        {t === 'feedback' && (!fb.data ? <PageSkeleton /> : (
          <Card pad={false}>
            <table className="w-full text-[13.5px]">
              <thead><tr className="border-b border-border bg-canvas/60 text-left text-[12px] text-fg-mute"><th className="px-5 py-2.5 font-medium">Who</th><th className="px-3 py-2.5 font-medium">What they said</th><th className="px-5 py-2.5 font-medium">What changed</th></tr></thead>
              <tbody>{fb.data.map((f, i) => (
                <tr key={i} className="border-b border-border last:border-0 align-top"><td className="w-56 px-5 py-3"><div className="font-medium">{f.who}</div><div className="text-[12px] text-fg-mute">{f.when}</div></td><td className="px-3 py-3 text-fg-soft">“{f.said}”</td><td className="px-5 py-3 text-brand-700">{f.changed}</td></tr>
              ))}</tbody>
            </table>
          </Card>
        ))}
      </div>
    </div>
  )
}
