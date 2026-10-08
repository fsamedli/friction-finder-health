import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUp, ClipboardPlus, Loader2, RotateCw, ShieldCheck, Sparkles } from 'lucide-react'
import { api, type FunctionId, type Investigation, type Plan, type TeamRow } from '../lib/api'
import { longDate, signed } from '../lib/format'
import { reviewTone, reviewWord } from '../lib/labels'
import { DETECT, REVIEW, useFunctions, useLoad, useStore } from '../lib/store'
import { Cites, EvidenceBody, SpecChart, SpecTable, TraceList } from './InvParts'
import PlanEditor, { seedFromDraft } from './PlanEditor'
import { Badge, Button, Details, EvidenceChip, Provenance, StateNote, cx } from './ui'

export interface PanelContext { site_id: number | null; team_id: number | null; as_of: string }

/** Wall-clock milliseconds, read in event handlers only (the elapsed-seconds counter while a run is live). */
const clock = () => Date.now()

const REASONS = ['wrong context', 'not actionable', 'missing evidence', 'wrong number', 'other'] as const

function Feedback({ inv }: { inv: Investigation }) {
  const [sent, setSent] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  if (sent) return <span className="text-[12px] text-fg-mute">Thanks, recorded ({sent}).</span>
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
      <span className="text-fg-mute">Something wrong?</span>
      {REASONS.map((r) => (
        <button key={r} type="button" onClick={async () => { try { await api.invFeedback(inv.id, r, inv.answer?.evidence_ids ?? []); setSent(r) } catch (e) { setErr(String((e as Error).message)) } }}
          className="rounded-md px-2 py-0.5 ring-1 ring-border hover:bg-canvas">{r}</button>
      ))}
      {err && <span className="text-crit-700">{err}</span>}
    </div>
  )
}

/** One answered turn: conclusion first, then its evidence state, the chart or table, the competing explanation,
 *  the next step, the citations, and the record of what ran. */
function Turn({ inv, onAsk, onPlanned }: { inv: Investigation; onAsk: (q: string, fn?: FunctionId, live?: boolean) => void; onPlanned: (p: Plan) => void }) {
  const nav = useNavigate()
  const [drafting, setDrafting] = useState(false)
  const [planned, setPlanned] = useState<Plan | null>(null)
  const a = inv.answer
  const reg = inv.evidence
  const model = inv.mode === 'model'
  const draft = a?.plan_draft
  return (
    <article className="rounded-xl border border-border bg-surface p-4" aria-label={`Answer to: ${inv.question}`}>
      <p className="text-[12.5px] text-fg-mute"><span className="font-medium text-fg-soft">You asked:</span> {inv.question}</p>
      {inv.prepared && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-info-50 px-3 py-2 text-[12px] text-info-700 ring-1 ring-inset ring-info-100">
          <span><b>Prepared answer</b> · generated {new Date(inv.prepared.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} with {inv.prepared.model}. Not re-run now.</span>
          <Button size="sm" variant="secondary" onClick={() => onAsk(inv.question, inv.function?.id, true)}>Run live</Button>
        </div>
      )}
      {inv.status === 'declined' && <div className="mt-3"><StateNote kind="unavailable" title="Declined before any check ran">{inv.message}</StateNote></div>}
      {inv.status === 'clarify' && <div className="mt-3"><StateNote kind="insufficient" title="Which one do you mean?">{inv.message}</StateNote></div>}
      {inv.status === 'error' && <div className="mt-3"><StateNote kind="fallback" title="The investigation stopped">{inv.message}</StateNote></div>}
      {inv.status === 'answered' && a && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceChip state={a.evidence_state} />
            {model ? <Provenance kind="model" /> : <Badge tone="brand">Written by code · rules mode</Badge>}
            {inv.check.numbers_total > 0 && <Badge tone={inv.check.passed ? 'ok' : 'warn'}><ShieldCheck size={12} /> {inv.check.numbers_checked} of {inv.check.numbers_total} numbers checked against the evidence</Badge>}
          </div>
          <p className={cx('text-[15px] font-medium leading-snug', model ? 'text-ai-700' : 'text-fg')}>{a.conclusion} <Cites ids={a.evidence_ids} register={reg} /></p>
          {inv.fallback && <StateNote kind="fallback" title="Fallback used">{inv.fallback}</StateNote>}
          {a.hypotheses && a.hypotheses.length > 0 && (
            <ol className="space-y-1.5">
              {a.hypotheses.map((h, i) => (
                <li key={h.id} className="rounded-lg bg-canvas px-3 py-2 text-[12.5px]">
                  <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium text-fg">{i + 1}. {h.label}</span><EvidenceChip state={h.evidence_state} /></div>
                  <p className="mt-0.5 text-fg-soft">{h.text} <Cites ids={h.evidence_ids} register={reg} /></p>
                </li>
              ))}
            </ol>
          )}
          {a.chart && <SpecChart spec={a.chart} />}
          {a.table && <SpecTable spec={a.table} />}
          {a.gaps && a.gaps.length > 0 && (
            <ul className="space-y-1.5 text-[12.5px]">
              {a.gaps.map((g, i) => <li key={i} className="rounded-lg bg-canvas px-3 py-2"><b className="text-fg">{g.gap}</b><div className="text-fg-soft">{g.step}</div><div className="text-fg-mute">Owner: {g.owner}</div></li>)}
            </ul>
          )}
          {a.review && (
            <div className="rounded-lg bg-canvas px-3 py-2 text-[12.5px]">
              {a.review.status === 'ok'
                ? <><Badge tone={reviewTone(a.review.verdict)} dot>{reviewWord(a.review.verdict)}</Badge> <span className="text-fg-soft">{a.review.kpi_label}: {signed((a.review.estimate ?? 0) * 10, 1)} per 10 people a month vs comparable teams (95% CI {signed((a.review.ci_low ?? 0) * 10, 1)} to {signed((a.review.ci_high ?? 0) * 10, 1)}). Directional, not causal.</span></>
                : a.review.status === 'not_reached' ? <span className="text-fg-soft">Not ready: the review is on {longDate(a.review.review)}, {a.review.days_to_go} days away.</span>
                  : <span className="text-fg-soft">{a.review.reason ?? 'Not enough follow-up data yet.'}</span>}
              <div className="mt-1"><button type="button" onClick={() => nav(`/review/${a.review!.plan_id}`)} className="font-medium text-fg-soft underline hover:text-fg">Open the review</button></div>
            </div>
          )}
          {a.questions && a.questions.items.length > 0 && (
            <div className="rounded-lg bg-canvas px-3 py-2 text-[12.5px]">
              <ul className="list-disc space-y-1 pl-4 text-fg-soft">{a.questions.items.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="mt-1 text-[11px] text-fg-mute">Source: {a.questions.source}</p>
            </div>
          )}
          {a.competing && (
            <div className="rounded-lg border border-border px-3 py-2 text-[12.5px]">
              <div className="flex flex-wrap items-center gap-2"><span className="label">Competing explanation</span><EvidenceChip state={a.competing.evidence_state} /></div>
              <p className="mt-0.5 text-fg-soft">{a.competing.text} <Cites ids={a.competing.evidence_ids} register={reg} /></p>
            </div>
          )}
          {a.next_step && (
            <div className={cx('rounded-lg px-3 py-2 text-[12.5px]', a.next_step.kind === 'action' ? 'bg-act-50 ring-1 ring-inset ring-act-100' : 'bg-canvas')}>
              <span className="label">{a.next_step.kind === 'action' ? 'Next step (your decision)' : 'Next step: find out'}</span>
              <p className="mt-0.5 text-fg-soft">{a.next_step.text} <span className="text-fg-mute">· {a.next_step.owner}</span></p>
              {a.next_step.kind === 'action' && !planned && !drafting && (
                <div className="mt-2"><Button size="sm" variant="decide" icon={<ClipboardPlus size={14} />}
                  onClick={() => (draft ? setDrafting(true) : onAsk('Draft a plan I can review', 'draft_plan'))}>Draft a plan</Button></div>
              )}
            </div>
          )}
          {draft && (drafting || (!a.next_step && !planned) || inv.function?.id === 'draft_plan') && !planned && (
            <PlanEditor seed={seedFromDraft(draft, inv.id)} onSaved={(p) => { setPlanned(p); setDrafting(false); onPlanned(p) }} />
          )}
          {planned && (
            <div className="rounded-lg bg-ok-50 px-3 py-2 text-[12.5px] text-ok-700 ring-1 ring-inset ring-ok-100">
              Plan approved and recorded. <button type="button" onClick={() => nav('/plans')} className="font-medium underline">Action plans</button> · <button type="button" onClick={() => nav(`/review/${planned.id}`)} className="font-medium underline">Review</button>
            </div>
          )}
          {inv.suggestions.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {inv.suggestions.map((s) => <button key={s.label} type="button" onClick={() => onAsk(s.question, s.function)} className="rounded-full border border-border px-2.5 py-1 text-[12px] text-fg-soft hover:bg-canvas">{s.label}</button>)}
            </div>
          )}
        </div>
      )}
      <Details className="mt-3" summary={<span>How this answer was produced · {inv.trace.length} steps · {inv.budget.seconds.toFixed(1)} s · {inv.mode === 'model' ? `AI model ${inv.model ?? ''}` : 'rules mode, no model'}</span>}>
        <TraceList trace={inv.trace} />
        <p className="mt-3 text-[11.5px] text-fg-mute">
          Budget used: {inv.budget.tool_calls} of {inv.budget.max_tool_calls} checks · {inv.budget.model_requests} of {inv.budget.max_model_requests} model requests · {inv.budget.seconds.toFixed(1)} of {inv.budget.max_seconds} s
          {inv.budget.stopped ? ` · stopped: ${inv.budget.stopped}` : ''} · next check chosen by {inv.selection === 'fixed_plan' ? 'a fixed plan for this question type (code)' : inv.selection === 'function_calling' ? 'the AI model (function calling)' : 'the AI model (validated JSON)'}.
        </p>
        {inv.check.notes.length > 0 && <ul className="mt-2 list-disc pl-4 text-[11.5px] text-fg-mute">{inv.check.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      </Details>
      {inv.status === 'answered' && reg.length > 0 && (
        <Details className="mt-2" summary={<span>Evidence register · {reg.length} items</span>}>
          <ul className="space-y-3">{reg.map((e) => <li key={e.id} className="text-[12px]"><span className="mr-2 font-mono text-[11px] text-fg-faint">{e.id}</span><EvidenceBody e={e} /></li>)}</ul>
        </Details>
      )}
      {inv.status === 'answered' && <div className="mt-3 border-t border-border pt-2"><Feedback inv={inv} /></div>}
    </article>
  )
}

function Running({ inv, started }: { inv: Investigation | null; started: number }) {
  const [now, setNow] = useState(started)
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(t) }, [])
  return (
    <div className="rounded-xl border border-border bg-surface p-4" role="status" aria-live="polite">
      <div className="flex items-center justify-between text-[13px]">
        <span className="flex items-center gap-2 font-medium"><Loader2 size={15} className="animate-spin text-brand" /> Investigating</span>
        <span className="tnum text-fg-mute">{((now - started) / 1000).toFixed(0)} s</span>
      </div>
      <div className="mt-3">{inv && inv.trace.length > 0 ? <TraceList trace={inv.trace} /> : <p className="text-[12.5px] text-fg-mute">Waiting for the first check to report.</p>}</div>
    </div>
  )
}

/** The AI-assisted investigation: the model (or, without a key, a fixed plan) chooses which read-only check runs next,
 *  under a budget; code computes every number; a person approves every action. */
export default function InvestigationPanel({ initial, full = false, teams }: { initial: PanelContext; full?: boolean; teams?: TeamRow[] }) {
  const { meta } = useStore()
  const fns = useFunctions()
  const [ctx, setCtx] = useState<PanelContext>(initial)
  const [conv, setConv] = useState<string | null>(null)
  const [turns, setTurns] = useState<Investigation[]>([])
  const [running, setRunning] = useState<{ started: number; inv: Investigation | null } | null>(null)
  const [err, setErr] = useState<{ msg: string; retry: () => void } | null>(null)
  const [q, setQ] = useState('')
  const alive = useRef(true)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => () => { alive.current = false }, [])
  const board = useLoad(() => (teams || ctx.site_id == null ? Promise.resolve(null) : api.board(ctx.site_id, ctx.as_of)), [ctx.site_id, ctx.as_of, !!teams])
  const teamList = (teams ?? board.data?.teams ?? []).filter((t) => t.status !== 'rolled_up')
  const teamName = teamList.find((t) => t.team_id === ctx.team_id)?.team_name

  const ask = async (question: string, fn?: FunctionId, live = false) => {
    const text = question.trim()
    if (!text || running) return
    setErr(null); setQ('')
    const started = clock()
    setRunning({ started, inv: null })
    try {
      let inv = await api.investigate({ question: text, conversation_id: conv, context: { site_id: ctx.site_id, team_id: ctx.team_id, as_of: ctx.as_of }, mode: 'auto', async: true, live, function: fn ?? null })
      while (inv.status === 'running' && alive.current) {
        setRunning({ started, inv })
        await new Promise((r) => setTimeout(r, 400))
        inv = await api.investigation(inv.id)
      }
      if (!alive.current) return
      setConv(inv.conversation_id)
      setTurns((t) => [...t, inv])
      setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50)
    } catch (e) {
      setErr({ msg: String((e as Error).message), retry: () => ask(text, fn, live) })
      setQ(text)  // keep what the manager typed
    } finally { if (alive.current) setRunning(null) }
  }
  const chips = (fns ?? []).filter((f) => f.shipped)
  const last = turns[turns.length - 1]
  const finding = last?.context.finding
  return (
    <section aria-label="AI-assisted investigation" className={cx('flex flex-col gap-3', full ? '' : 'rounded-2xl border border-border bg-canvas/60 p-3 sm:p-4')}>
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-[15px] font-semibold"><Sparkles size={16} className="text-ai" /> Ask about {teamName ?? 'this hospital'}</h2>
          <p className="text-[12px] text-fg-mute">AI-assisted investigation: {meta?.model ? <>the AI model ({meta.model}) chooses which read-only check runs next, under a budget</> : <>no model key, so a fixed plan per question type chooses the checks</>}; code computes every number; you approve every action.</p>
        </div>
        {turns.length > 0 && <button type="button" onClick={() => { setTurns([]); setConv(null) }} className="shrink-0 text-[12px] font-medium text-fg-mute hover:text-fg">New conversation</button>}
      </header>
      <div className="flex flex-wrap items-center gap-1.5 text-[12px]" aria-label="Context">
        <label className="inline-flex items-center gap-1 rounded-full bg-surface px-2 py-0.5 ring-1 ring-border"><span className="text-fg-mute">Hospital</span>
          <select aria-label="Context: hospital" value={ctx.site_id ?? ''} onChange={(e) => setCtx((c) => ({ ...c, site_id: Number(e.target.value), team_id: null }))} className="bg-transparent font-medium focus:outline-none">
            {(meta?.sites ?? []).map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name}</option>)}
          </select></label>
        <label className="inline-flex items-center gap-1 rounded-full bg-surface px-2 py-0.5 ring-1 ring-border"><span className="text-fg-mute">Team</span>
          <select aria-label="Context: team" value={ctx.team_id ?? ''} onChange={(e) => setCtx((c) => ({ ...c, team_id: e.target.value ? Number(e.target.value) : null }))} className="max-w-[130px] bg-transparent font-medium focus:outline-none">
            <option value="">Whole hospital</option>
            {teamList.map((t) => <option key={t.team_id} value={t.team_id}>{t.team_name}</option>)}
          </select></label>
        <label className="inline-flex items-center gap-1 rounded-full bg-surface px-2 py-0.5 ring-1 ring-border"><span className="text-fg-mute">As of</span>
          <select aria-label="Context: as-of date" value={ctx.as_of} onChange={(e) => setCtx((c) => ({ ...c, as_of: e.target.value }))} className="bg-transparent font-medium focus:outline-none">
            <option value={DETECT}>Sept 15, 2026</option><option value={REVIEW}>Nov 30, 2026</option>
          </select></label>
        {finding && finding.status && <span className="rounded-full bg-surface px-2 py-0.5 ring-1 ring-border"><span className="text-fg-mute">Finding</span> <b className="font-medium">{finding.kpi ? `${finding.kpi.replace('_', ' ')}` : ''}{finding.item ? ` · ${finding.item.toUpperCase()}` : ''}</b></span>}
      </div>
      {fns && fns.length === 0 && <StateNote kind="unavailable" title="The investigation service is not available on this server">Every screen still works; questions cannot be investigated here.</StateNote>}
      {turns.map((t) => <Turn key={t.id} inv={t} onAsk={ask} onPlanned={() => window.dispatchEvent(new Event('ff:plans-changed'))} />)}
      {running && <Running inv={running.inv} started={running.started} />}
      {err && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-crit-50 px-3 py-2 text-[12.5px] text-crit-700 ring-1 ring-inset ring-crit-100">
          <span>The question was not answered: {err.msg}. Your question is kept below.</span>
          <Button size="sm" variant="secondary" icon={<RotateCw size={13} />} onClick={err.retry}>Try again</Button>
        </div>
      )}
      <div ref={end} />
      {fns && fns.length > 0 && (
        <>
          <div className="flex flex-wrap gap-1.5">
            {chips.slice(0, turns.length ? 6 : 12).map((f) => (
              <button key={f.id} type="button" disabled={!!running} onClick={() => ask(f.question.replace('{team}', teamName ?? 'this team'), f.id)}
                className="rounded-full border border-border bg-surface px-2.5 py-1 text-[12px] text-fg-soft hover:bg-canvas disabled:opacity-40">{f.chip}</button>
            ))}
          </div>
          <form onSubmit={(e) => { e.preventDefault(); ask(q) }} className="flex items-center gap-2 rounded-xl border border-border-strong bg-surface p-1.5 pl-3 focus-within:ring-4 focus-within:ring-brand/10">
            <input aria-label="Ask a question" value={q} onChange={(e) => setQ(e.target.value)} placeholder={turns.length ? 'Ask a follow-up, e.g. Could staffing explain this?' : `e.g. Why is ${teamName ?? 'this team'} flagged?`}
              className="min-w-0 flex-1 bg-transparent text-[13.5px] focus:outline-none" />
            <Button type="submit" variant="primary" size="sm" disabled={!q.trim() || !!running} icon={<ArrowUp size={14} />}>Ask</Button>
          </form>
        </>
      )}
    </section>
  )
}
