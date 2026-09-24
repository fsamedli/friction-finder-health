import { api } from '../lib/api'
import { useLoad } from '../lib/store'
import { Card, Chip, Eyebrow, Loading, PageTitle } from '../components/ui'

function Architecture() {
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, tone: 'ink' | 'teal' | 'rust' | 'model' = 'ink') => {
    const fill = { ink: '#FFFEFB', teal: '#D6ECF1', rust: '#F6DED7', model: '#E9E4F2' }[tone]
    const stroke = { ink: '#1B3A4B', teal: '#1F8FA8', rust: '#C8553D', model: '#4B3F72' }[tone]
    return (
      <g>
        <rect x={x} y={y} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={1.3} />
        <text x={x + 12} y={y + 22} fontFamily="Fraunces, Georgia, serif" fontWeight={600} fontSize={14} fill="#1B3A4B">{title}</text>
        <text x={x + 12} y={y + 40} fontFamily="'Source Sans 3', sans-serif" fontSize={11.5} fill="#3E5A69">{sub}</text>
      </g>
    )
  }
  const arrow = (x1: number, y1: number, x2: number, y2: number) => <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#6B7F8A" strokeWidth={1.2} markerEnd="url(#a)" />
  return (
    <svg viewBox="0 0 960 330" className="w-full h-auto" role="img" aria-label="Architecture">
      <defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#6B7F8A" /></marker></defs>
      {box(20, 20, 200, 56, 'Client data', 'Survey export (HR) · ops logs (CSV)')}
      {box(20, 110, 200, 56, 'DuckDB views', 'n ≥ 4 enforced in SQL', 'teal')}
      {box(20, 200, 200, 56, 'Documents', 'Comments · procedures · directory')}
      {box(290, 60, 250, 56, 'impact.py · detect / explain / prove', 'Poisson excess · OLS · DiD · no model', 'teal')}
      {box(290, 170, 250, 56, 'agent.py · evidence brief', 'text-to-SQL views · retrieval · verdict rules', 'teal')}
      {box(290, 260, 250, 56, 'Azure OpenAI (GW)', 'gpt-5-mini: reads question, writes brief', 'model')}
      {box(610, 110, 150, 56, 'FastAPI', 'typed endpoints')}
      {box(800, 60, 140, 56, 'React app', 'board · why · plan · proof')}
      {box(800, 170, 140, 56, 'Manager', 'approves · flags · edits', 'rust')}
      {arrow(120, 76, 120, 108)}{arrow(220, 138, 288, 92)}{arrow(220, 138, 288, 196)}{arrow(220, 228, 288, 206)}
      {arrow(415, 226, 415, 258)}{arrow(540, 90, 608, 132)}{arrow(540, 196, 608, 146)}{arrow(760, 132, 798, 92)}{arrow(870, 116, 870, 168)}
      <text x={290} y={46} fontSize={11} fill="#146C80" fontFamily="'Source Sans 3', sans-serif">every number comes from here ↓</text>
    </svg>
  )
}

export default function Hood() {
  const a = useLoad(() => api.assumptions(), [])
  const ev = useLoad(() => api.evals(), [])
  const fb = useLoad(() => api.feedback(), [])
  return (
    <div>
      <PageTitle kicker="Under the hood" title="What we assumed, how it works, how we know it's right, and what judges changed."
        lede="State the assumptions first (Fullowan, Sept 18). The data is synthetic and the company is fictional; the methods are what we're showing." />
      <div className="space-y-6">
        <Card className="p-6">
          <Eyebrow>Assumptions</Eyebrow>
          {!a.data ? <Loading /> : (
            <>
              <table className="w-full mt-3 text-[14px]">
                <tbody>{a.data.rows.map((r) => (
                  <tr key={r.k} className="border-t border-line align-top"><td className="py-2.5 pr-4 font-semibold w-[170px]">{r.k}</td><td className="py-2.5 pr-4">{r.v}</td><td className="py-2.5 text-ink-mute text-[13px]">{r.why}</td></tr>
                ))}</tbody>
              </table>
              <div className="mt-4 text-[13.5px]"><b>With real data we would need:</b> <span className="text-ink-soft">{a.data.with_real_data.join(' · ')}</span></div>
            </>
          )}
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between"><Eyebrow>Architecture</Eyebrow><div className="flex gap-2"><Chip kind="computed">code computes</Chip><Chip kind="model">model reads &amp; writes</Chip><Chip kind="person">person decides</Chip></div></div>
          <div className="mt-4"><Architecture /></div>
          <p className="text-[13px] text-ink-mute mt-2">An AI-assisted workflow, not autonomous agents: fixed steps, the model at two of them, deterministic queries and statistical checks, and a person at the decision.</p>
        </Card>

        <Card className="p-6">
          <Eyebrow>Evaluation · gold questions scored against planted answers</Eyebrow>
          {!ev.data ? <Loading /> : (
            <div className="grid gap-6 md:grid-cols-2 mt-3">
              {ev.data.map((e) => (
                <div key={e.file}>
                  <div className="flex items-baseline justify-between"><b>{e.model}</b><span className="num text-[1.6rem]">{e.passed}/{e.total}</span></div>
                  <div className="grid grid-cols-4 gap-2 mt-2 text-center text-[12px]">
                    {Object.entries(e.matrix ?? {}).filter(([k]) => k !== 'FN*').map(([k, n]) => <div key={k} className="rounded-lg bg-paper-deep py-2"><div className="num text-[1.2rem]">{n}</div>{k}</div>)}
                  </div>
                  <p className="text-[12px] text-ink-mute mt-2">{e.ts?.slice(0, 10)} · refusals and suppressions count as true negatives</p>
                </div>
              ))}
            </div>
          )}
          <p className="text-[12.5px] text-rust-deep mt-4">Known limit: the team wrote both the data and the questions. A held-out set written by someone who has not seen the answers is next.</p>
        </Card>

        <Card className="p-6">
          <Eyebrow>You told us → we changed</Eyebrow>
          {!fb.data ? <Loading /> : (
            <table className="w-full mt-3 text-[13.5px]">
              <tbody>{fb.data.map((f, i) => (
                <tr key={i} className="border-t border-line align-top"><td className="py-2.5 pr-4 w-[210px]"><b>{f.who}</b><div className="text-ink-mute text-[12px]">{f.when}</div></td><td className="py-2.5 pr-4 text-ink-soft italic font-serif">“{f.said}”</td><td className="py-2.5 text-teal-deep">{f.changed}</td></tr>
              ))}</tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  )
}
