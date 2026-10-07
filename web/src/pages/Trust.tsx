import { useState } from 'react'
import { api, type Quality } from '../lib/api'
import { useLoad, useStore } from '../lib/store'
import { Badge, Card, CardHeader, CsvButton, PageHeader, PageSkeleton, Tabs } from '../components/ui'

type T = 'quality' | 'assumptions' | 'architecture' | 'evaluation' | 'feedback'

function Architecture() {
  type Tone = 'plain' | 'code' | 'ai' | 'person' | 'guard'
  const box = (x: number, y: number, w: number, title: string, sub: string, tone: Tone = 'plain') => {
    const c = { plain: ['#FFFFFF', '#D0D5DD'], code: ['#E7F6F4', '#0E8A7E'], ai: ['#F4F3FF', '#6941C6'], person: ['#FDF1EC', '#C4501E'], guard: ['#F5F6F8', '#101828'] }[tone]
    return (
      <g>
        <rect x={x} y={y} width={w} height={54} rx={10} fill={c[0]} stroke={c[1]} strokeWidth={tone === 'guard' ? 1.6 : 1.3} strokeDasharray={tone === 'guard' ? '4 3' : undefined} />
        <text x={x + 11} y={y + 22} fontFamily="Geist, sans-serif" fontWeight={600} fontSize={12.5} fill="#101828">{title}</text>
        <text x={x + 11} y={y + 39} fontFamily="Geist, sans-serif" fontSize={10.5} fill="#667085">{sub}</text>
      </g>
    )
  }
  const arrow = (x1: number, y1: number, x2: number, y2: number) => <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#98A2B3" strokeWidth={1.3} markerEnd="url(#ah)" />
  return (
    <svg viewBox="0 0 1000 400" className="w-full h-auto min-w-[720px]" role="img" aria-label="Architecture: client data flows through suppressed views and a SQL guard into two computing engines; the AI reads the question and writes the brief; a checker verifies it; a person decides.">
      <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#98A2B3" /></marker></defs>
      {box(10, 20, 190, 'Client data (synthetic)', 'survey export · ops CSVs · docs')}
      {box(10, 110, 190, 'Suppressed views', 'n ≥ 4 enforced in SQL', 'guard')}
      {box(10, 200, 190, 'SQL guard (sqlglot)', 'allowlist · no table functions', 'guard')}
      {box(10, 300, 190, 'Question', 'from the manager')}
      {box(250, 300, 200, 'Out-of-scope guard', 'no individuals, no judging people', 'guard')}
      {box(250, 20, 230, 'Impact engine', 'Poisson excess · OLS · DiD · no AI', 'code')}
      {box(250, 110, 230, 'Evidence engine', 'templated SQL · retrieval · counts', 'code')}
      {box(250, 200, 230, 'Verdict rules', 'computed by code, not the AI', 'code')}
      {box(510, 300, 200, 'AI · read the question', 'into a fixed schema (gpt-5-mini)', 'ai')}
      {box(530, 200, 200, 'AI · write the brief', 'from the evidence only', 'ai')}
      {box(530, 110, 200, 'Checker', 'every number & citation in evidence', 'guard')}
      {box(780, 60, 200, 'Web app', 'board · team · plan · impact · ask')}
      {box(780, 170, 200, 'Person decides', 'approve · reject · flag · plan', 'person')}
      {arrow(105, 74, 105, 108)}{arrow(105, 164, 105, 198)}{arrow(200, 227, 248, 137)}{arrow(200, 137, 248, 47)}
      {arrow(200, 327, 248, 327)}{arrow(450, 327, 508, 327)}{arrow(610, 300, 480, 164)}{arrow(365, 164, 365, 198)}
      {arrow(480, 227, 528, 227)}{arrow(630, 200, 630, 166)}{arrow(730, 137, 778, 94)}{arrow(480, 47, 778, 80)}{arrow(880, 114, 880, 168)}
    </svg>
  )
}

const TECHNIQUES = [
  { t: 'Question → fixed schema → templated SQL on views, sqlglot guard', pro: 'The model never writes SQL; every query is auditable; suppression lives in the views', con: 'Only answers question types that have a template', alt: 'Free-form model-written SQL; vanna.ai; the earlier regex guard', why: 'vanna.ai archived (last release Feb 2, 2026); regex guard was bypassable, replaced Sept 23; free-form SQL: Farid to confirm' },
  { t: 'Retrieval with citations (embeddings, keyword fallback)', pro: 'No extra service; every passage cited; works without a key', con: 'No reranker; retrieval quality not yet measured', alt: 'A vector database; RAGAS', why: 'Vector DB out of scope for this cut (SPEC); RAGAS development has slowed' },
  { t: 'Rule-based verdict', pro: 'Transparent; the model cannot overclaim; tested on planted cases', con: 'Screening rules, not significance tests', alt: 'A trained classifier (EBM, as FraudLens); an agent framework', why: '24 teams × 2 waves is too small to train or report an AUC; agent frameworks out of scope (SPEC)' },
  { t: 'Poisson excess vs comparable teams', pro: 'Flags only what exceeds normal variation; says "too rare to judge"', con: 'Assumes Poisson counts; about 1 false flag per site at p < 0.01', alt: 'Positive excess over the comparable-team median (first v0.6 design)', why: 'Tried Sept 23: flagged half the teams on noise; replaced' },
  { t: 'Difference-in-differences + placebo', pro: 'Cancels site-wide and seasonal shifts; placebo shows how unusual the result is', con: 'One treated team, 4 comparisons; directional, not causal; synthetic follow-up', alt: 'Bootstrap CI over comparison teams; DoWhy', why: 'Bootstrap → Poisson SE: Farid to confirm; DoWhy: the data cannot defend causal claims' },
]

function Techniques() {
  return (
    <div className="mt-6 overflow-x-auto scroll-thin">
      <table className="w-full min-w-[900px] text-[12.5px]">
        <thead><tr className="border-b border-border text-left text-[12px] text-fg-mute"><th className="py-2 pr-3 font-medium">Technique</th><th className="py-2 pr-3 font-medium">Pros</th><th className="py-2 pr-3 font-medium">Cons</th><th className="py-2 pr-3 font-medium">Alternatives considered</th><th className="py-2 font-medium">Why not used</th></tr></thead>
        <tbody>{TECHNIQUES.map((x) => (
          <tr key={x.t} className="border-b border-border align-top last:border-0"><td className="py-2.5 pr-3 font-medium">{x.t}</td><td className="py-2.5 pr-3 text-fg-soft">{x.pro}</td><td className="py-2.5 pr-3 text-fg-soft">{x.con}</td><td className="py-2.5 pr-3 text-fg-soft">{x.alt}</td><td className="py-2.5 text-fg-soft">{x.why}</td></tr>
        ))}</tbody>
      </table>
      <p className="mt-2 text-[11.5px] text-fg-faint">Full version with sources and file references: docs/ARCHITECTURE.md.</p>
    </div>
  )
}

const d = (ts?: string) => (ts ? new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—')
const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : '—')

function Src({ file, ts }: { file: string; ts?: string }) {
  return <span className="font-mono text-[11px] text-fg-faint break-all">{file}{ts ? ` · ${d(ts)}` : ''}</span>
}

function QualityTab({ q }: { q: Quality }) {
  return (
    <div className="space-y-6">
      <Card pad={false}>
        <div className="p-5 pb-0"><CardHeader title="Pass rate by test pack" sub="First recorded run vs the latest run. Every number is read from the saved result file shown under it."
          right={<CsvButton filename="quality_packs.csv" rows={() => q.packs.map((p) => ({ pack: p.pack, note: p.note, mode: p.mode ?? '', first_passed: p.first?.passed ?? '', first_total: p.first?.total ?? '', first_file: p.first?.file ?? '', now_passed: p.now?.passed ?? '', now_total: p.now?.total ?? '', now_file: p.now?.file ?? '' }))} />} /></div>
        <div className="overflow-x-auto scroll-thin">
          <table className="w-full min-w-[720px] text-[13.5px]">
            <thead><tr className="border-y border-border bg-canvas/60 text-left text-[12px] text-fg-mute"><th className="px-5 py-2.5 font-medium">Pack</th><th className="px-3 py-2.5 font-medium">Mode</th><th className="px-3 py-2.5 font-medium">First run</th><th className="px-3 py-2.5 font-medium">Now</th></tr></thead>
            <tbody>{q.packs.map((p, i) => (
              <tr key={i} className="border-b border-border last:border-0 align-top">
                <td className="px-5 py-3"><div className="font-medium">{p.pack}</div><div className="text-[12px] text-fg-mute">{p.note}</div></td>
                <td className="px-3 py-3">{p.mode ?? '—'}</td>
                <td className="px-3 py-3">{p.first ? <><div className="tnum font-medium">{p.first.passed}/{p.first.total} <span className="text-fg-mute font-normal">({pct(p.first.passed, p.first.total)})</span></div><Src file={p.first.file} ts={p.first.ts} /></> : <Badge tone="neutral">pending</Badge>}</td>
                <td className="px-3 py-3">{p.now ? <><div className="tnum font-semibold">{p.now.passed}/{p.now.total} <span className="text-fg-mute font-normal">({pct(p.now.passed, p.now.total)})</span></div><Src file={p.now.file} ts={p.now.ts} /></> : <Badge tone="neutral">pending</Badge>}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader title="Declines when it should" sub="Cases that must refuse, suppress or say 'insufficient' (rules mode)" />
          {q.declines.map((x) => <div key={x.file} className="flex items-baseline justify-between border-t border-border py-2.5 first:border-0"><Src file={x.file} ts={x.ts} /><span className="tnum font-semibold">{x.correct}/{x.total}</span></div>)}
        </Card>
        <Card>
          <CardHeader title="Numbers checked against the evidence" sub="Every number in a model-written brief must appear in the SQL results or evidence" />
          {q.grounding ? <><div className="text-[26px] font-semibold tnum">{q.grounding.checked} of {q.grounding.total}</div><p className="text-[12.5px] text-fg-mute">across {q.grounding.briefs} model-written briefs (the prepared answers)</p><Src file={q.grounding.file} ts={q.grounding.generated[0]} /></> : <p className="text-fg-mute">No model-written briefs saved yet.</p>}
        </Card>
        <Card>
          <CardHeader title="Time per question" sub="From the latest saved runs (gold + adversarial)" />
          {q.latency.map((l) => (
            <div key={l.mode} className="border-t border-border py-2.5 first:border-0">
              <div className="flex items-baseline justify-between"><span className="font-medium">{l.mode}</span><span className="tnum">p50 {l.p50 ?? '—'} s · p95 {l.p95 ?? '—'} s <span className="text-fg-mute">(n={l.n})</span></span></div>
              <div className="mt-0.5">{l.files.map((f) => <div key={f}><Src file={f} /></div>)}</div>
            </div>))}
        </Card>
        <Card>
          <CardHeader title="Was it useful?" sub="Yes / no from users on Ask briefs and plans" />
          {q.feedback.total === 0 ? <p className="text-[13.5px] text-fg-mute">No data yet. Counts appear here as people answer "Useful?" in the app.</p> : (
            <><div className="text-[26px] font-semibold tnum">{q.feedback.useful} of {q.feedback.total} useful</div>
              <ul className="mt-2 text-[12.5px] text-fg-soft">{Object.entries(q.feedback.reasons).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul></>)}
          <Src file={q.feedback.file} />
        </Card>
      </div>
      <p className="text-[12px] text-fg-mute">The gold and adversarial packs were written by the builder, so they are not independent. The holdout pack is for a teammate who has not seen the planted answers.</p>
      <p className="text-[12px] text-fg-mute">Approvals are recorded as decisions. An approval is never evidence that an answer was correct; correctness is measured by the packs above and, at the review date, by the operating number.</p>
    </div>
  )
}

export default function Trust() {
  const { meta } = useStore()
  const [t, setT] = useState<T>('quality')
  const q = useLoad(() => api.quality(), [])
  const a = useLoad(() => api.assumptions(), [])
  const ev = useLoad(() => api.evals(), [])
  const fb = useLoad(() => api.feedback(), [])
  return (
    <div>
      <PageHeader title="Trust & method" sub="What we assumed, how the system works, how we know it's right, and what the judges changed. The company is fictional and the data is synthetic; the methods are what we're showing." />
      <Tabs value={t} onChange={setT} tabs={[{ id: 'quality', label: 'Quality' }, { id: 'assumptions', label: 'Assumptions' }, { id: 'architecture', label: 'Architecture' }, { id: 'evaluation', label: 'Evaluation' }, { id: 'feedback', label: 'You told us → we changed', count: fb.data?.length }]} />
      <div className="mt-6">
        {t === 'quality' && (!q.data ? <PageSkeleton /> : <QualityTab q={q.data} />)}
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
              right={<><Badge tone="brand">code computes</Badge><Badge tone="ai">AI reads & writes</Badge><Badge tone="act">person decides</Badge><Badge tone="neutral">guard</Badge></>} />
            <div className="overflow-x-auto scroll-thin"><Architecture /></div>
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3 text-[13px]">
              <div className="rounded-lg bg-canvas p-3"><b>What the AI does</b><p className="mt-1 text-fg-soft">Turns a question into a structured request, and writes the brief from evidence it is handed. Model: {meta?.model ?? 'none configured (rules mode)'}.</p></div>
              <div className="rounded-lg bg-canvas p-3"><b>What the AI never does</b><p className="mt-1 text-fg-soft">Produce a number, decide a verdict, see respondent rows, or approve a plan. Every number in a brief is checked against the evidence.</p></div>
              <div className="rounded-lg bg-canvas p-3"><b>Without a model key</b><p className="mt-1 text-fg-soft">Everything except the written brief still works: rules-based question reading, keyword retrieval, templated text.</p></div>
            </div>
            <h4 className="mt-8 text-[14px] font-semibold">Why these techniques</h4>
            <Techniques />
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
