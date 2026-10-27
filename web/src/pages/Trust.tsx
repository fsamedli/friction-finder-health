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
    <svg viewBox="0 0 1000 430" className="w-full h-auto min-w-[720px]" role="img" aria-label="Architecture: hospital data (unit-level counts, no patient data) flows through suppressed views and a SQL guard into read-only tools. A question passes the out-of-scope guard; the AI model, or without a key a fixed plan, chooses which read-only tool runs next under a budget; code runs the tool and computes every number; a self-check verifies the answer; a person approves every action.">
      <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#98A2B3" /></marker></defs>
      {box(10, 20, 190, 'Hospital data (synthetic)', 'survey · eMAR · timekeeping · docs')}
      {box(10, 110, 190, 'Suppressed views', 'n ≥ 4 enforced in SQL', 'guard')}
      {box(10, 200, 190, 'SQL guard (sqlglot)', 'allowlist · no table functions', 'guard')}
      {box(10, 330, 190, 'Question + context', 'team · site · date · finding')}
      {box(250, 330, 200, 'Out-of-scope guard', 'runs first, on every follow-up', 'guard')}
      {box(250, 20, 230, 'Impact engine', 'Poisson excess · OLS · DiD · no AI', 'code')}
      {box(250, 110, 230, 'Read-only tools (registry)', 'metric · compare · benchmark · timeline…', 'code')}
      {box(250, 200, 230, 'Evidence states', 'set by rules in code', 'code')}
      {box(510, 330, 220, 'AI · choose the next check', 'or a fixed plan without a key', 'ai')}
      {box(510, 240, 220, 'Budget (host code)', '6 checks · 8 model calls · 60 s', 'guard')}
      {box(530, 150, 200, 'AI · write the answer', 'from tool results only', 'ai')}
      {box(530, 60, 200, 'Self-check', 'citations · numbers · provenance', 'guard')}
      {box(780, 60, 200, 'Web app', 'Today · Investigate · plans · review')}
      {box(780, 170, 200, 'Person decides', 'approve · edit · reject · plan', 'person')}
      {arrow(105, 74, 105, 108)}{arrow(105, 164, 105, 198)}{arrow(200, 227, 248, 137)}{arrow(200, 137, 248, 47)}
      {arrow(200, 357, 248, 357)}{arrow(450, 357, 508, 357)}{arrow(560, 330, 470, 166)}{arrow(365, 164, 365, 198)}
      {arrow(620, 330, 620, 296)}{arrow(480, 227, 528, 177)}{arrow(630, 150, 630, 116)}{arrow(730, 87, 778, 87)}{arrow(480, 47, 778, 74)}{arrow(880, 114, 880, 168)}
    </svg>
  )
}

const TECHNIQUES = [
  { t: 'Bounded AI-assisted investigation: the model picks the next read-only check from a fixed registry', pro: 'Answers follow-ups ("could staffing explain this?") without a template per sentence; every step is in the trace; host code enforces the budget and the scope guard', con: 'Tool choice can be wrong or wasteful; more model calls means more latency; needs its own eval pack', alt: 'A fixed pipeline only (v0.7); an agent framework; free-form tool use with no budget', why: 'Fixed pipeline could not answer challenges; frameworks out of scope (SPEC); no budget = unbounded cost and latency. Without a key a fixed plan per question type runs the same tools' },
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
            <CardHeader title="An AI-assisted workflow" sub="The model chooses which of a fixed set of read-only tools to run next, under a budget; code computes every number; a person approves every action. Nothing is done outside the app."
              right={<><Badge tone="brand">code computes</Badge><Badge tone="ai">AI chooses checks & writes</Badge><Badge tone="act">person decides</Badge><Badge tone="neutral">guard</Badge></>} />
            <p className="text-[14px] leading-relaxed text-fg-soft">
              <b className="text-fg">Which part is AI, and where does the model decide?</b> Friction Finder is an AI-assisted workflow, not an autonomous system.
              Code detects (Poisson excess vs comparable units), adjusts (tenure-mix shift-share), links (OLS, clustered by team) and proves
              (difference-in-differences with a placebo). The model makes two kinds of decisions, both bounded: in the investigation it chooses
              which of eleven read-only checks to run next (function calling, budget of 6 checks, 8 requests, 60 seconds), and it writes the brief,
              the plan draft and the owner notices from the numbers code handed it; a code check rejects any sentence whose numbers, team or
              period are not in the cited evidence. It never writes SQL, never sets a verdict, never sends anything. The nurse manager edits and
              approves; after approval code assigns owners, schedules the review and drafts the notices, and the manager sends them.
            </p>
            <div className="mt-4 mb-6 overflow-x-auto scroll-thin">
              <table className="w-full min-w-[640px] text-[13px]">
                <caption className="sr-only">Who decides what in Friction Finder</caption>
                <thead><tr className="border-b border-border text-left text-[12px] text-fg-mute"><th scope="col" className="py-2 pr-3 font-medium">Who decides</th><th scope="col" className="py-2 pr-3 font-medium">What</th><th scope="col" className="py-2 font-medium">Where</th></tr></thead>
                <tbody>
                  <tr className="border-b border-border align-top"><td className="py-2.5 pr-3 font-medium"><Badge tone="brand">Code decides</Badge></td><td className="py-2.5 pr-3 text-fg-soft">Which team is flagged, whether a change is beyond normal variation, the evidence state of every answer, the review verdict and its interval, the placebo, the three value tiers, the owners assigned, the review date and the KPI watch at approval.</td><td className="py-2.5 text-fg-soft"><code>app/impact.py</code>, <code>app/metrics.py</code>, <code>app/investigate.py</code> (states, self-check), <code>api/main.py</code> (execution record)</td></tr>
                  <tr className="border-b border-border align-top"><td className="py-2.5 pr-3 font-medium"><Badge tone="ai">The model decides</Badge></td><td className="py-2.5 pr-3 text-fg-soft">Which read-only check runs next for a manager's question (from a fixed registry, under the budget), and the wording of the brief, the plan draft, a regenerated action list and the owner notices, all from the numbers it is handed and all checked by code before they are shown.</td><td className="py-2.5 text-fg-soft"><code>app/investigate.py</code> (<code>_model_loop</code>, <code>_model_write</code>), <code>app/agent.py</code> (<code>write_brief</code>, <code>regenerate_actions</code>, <code>draft_notices_llm</code>)</td></tr>
                  <tr className="align-top"><td className="py-2.5 pr-3 font-medium"><Badge tone="act">The person decides</Badge></td><td className="py-2.5 pr-3 text-fg-soft">Whether to act, what the plan says, who owns each task and by when, when a task is done, whether to send a notice (nothing is sent by the prototype), and whether to keep, change or stop the routine at the review date.</td><td className="py-2.5 text-fg-soft">Investigate › What do I do?, the checklist at <code>/plans/&#123;id&#125;</code>, Review; every decision is logged with the time in <code>approvals.jsonl</code></td></tr>
                </tbody>
              </table>
            </div>
            <div className="overflow-x-auto scroll-thin"><Architecture /></div>
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3 text-[13px]">
              <div className="rounded-lg bg-canvas p-3"><b>What the AI does</b><p className="mt-1 text-fg-soft">Chooses which read-only check runs next for a manager's question, within a budget, and writes the answer from the tool results it is handed. Model: {meta?.model ?? 'none configured (rules mode)'}.</p></div>
              <div className="rounded-lg bg-canvas p-3"><b>What the AI never does</b><p className="mt-1 text-fg-soft">Produce a number, set an evidence state, see respondent rows, approve a plan, or act outside the app. Every number and citation in an answer is checked against the tool results.</p></div>
              <div className="rounded-lg bg-canvas p-3"><b>Without a model key</b><p className="mt-1 text-fg-soft">A fixed plan per question type runs the same tools; answers are templated from the results; retrieval uses keywords. Everything except model-written wording still works.</p></div>
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
            <Card className="md:col-span-2 border-warn-100 bg-warn-50/50"><p className="text-[13px] text-warn-700"><b>Known limit.</b> The team wrote both the data and the gold questions. A held-out set written by someone who has not seen the planted answers, and a small user test with nurse managers, are next.</p></Card>
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
