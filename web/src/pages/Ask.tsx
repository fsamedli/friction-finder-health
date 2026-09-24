import { useEffect, useState } from 'react'
import { ArrowUp, Check, ChevronDown, Code2, Flag, Loader2, ShieldCheck, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import { api, type AskResult, type Evidence } from '../lib/api'
import { useStore } from '../lib/store'
import { Badge, Button, Card, CardHeader, PageHeader, Provenance, cx } from '../components/ui'

const EXAMPLES = [
  "Why did the Richmond night shift's scores drop and why are deliveries late?",
  'Did the Norfolk Day B team really decline?',
  'Who owns the shift handoff procedure at Richmond?',
  'Why did the Denver site drop?',
]
// What the run does, in order. Shown while the model works so the page never looks frozen.
const STAGES = ['Understand the question', 'Query the database views', 'Retrieve comments and documents', 'Compute the verdict', 'Write the brief', 'Check the brief']

function Progress({ started, model }: { started: number; model: boolean }) {
  const [now, setNow] = useState(started)
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(t) }, [])
  const s = (now - started) / 1000
  // step starts measured on gpt-5-mini (Sept 23: 2.8 s to read, 0.5 s to query, 11.2 s to write); rules mode is near-instant
  const marks = model ? [0, 2.8, 3.1, 3.4, 3.6, 14.5] : [0, 0.1, 0.2, 0.3, 0.4, 0.5]
  const at = marks.filter((m) => s >= m).length - 1
  return (
    <Card className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 font-medium"><Loader2 size={16} className="animate-spin text-brand" /> Working on it</div>
        <span className="tnum text-[12.5px] text-fg-mute">{s.toFixed(0)} s{model ? ' · usually 15–30 s with the model' : ''}</span>
      </div>
      <ol className="space-y-2">
        {STAGES.map((st, i) => (
          <li key={st} className="flex items-center gap-2.5 text-[13.5px]">
            <span className={cx('flex h-5 w-5 items-center justify-center rounded-full', i < at ? 'bg-brand text-white' : i === at ? 'bg-brand-50 ring-2 ring-brand' : 'bg-canvas ring-1 ring-border')}>
              {i < at ? <Check size={12} /> : i === at ? <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse2" /> : null}
            </span>
            <span className={i <= at ? 'text-fg' : 'text-fg-faint'}>{st}</span>
            {(i === 0 || i === 4) && model && <Badge tone="ai" className="ml-1">AI</Badge>}
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[11.5px] text-fg-faint">Progress is estimated from typical timings; the real time of each step is shown with the answer.</p>
    </Card>
  )
}

function EvidenceRow({ e }: { e: Evidence }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="border-t border-border py-3 first:border-0">
      <div className="flex gap-3">
        <span className="w-8 shrink-0 font-mono text-[11px] text-fg-faint pt-0.5">{e.id}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] text-fg-soft">{e.statement}</p>
          <div className="mt-1.5 flex items-center gap-2">
            <Provenance kind={e.origin === 'retrieved' ? 'retrieved' : 'computed'} />
            {e.sql && <button onClick={() => setOpen((o) => !o)} className="inline-flex items-center gap-1 text-[12px] font-medium text-fg-mute hover:text-fg"><Code2 size={13} />{open ? 'Hide SQL' : 'Show SQL'}</button>}
          </div>
          {open && e.sql && <pre className="mt-2 overflow-x-auto rounded-lg bg-side p-3 font-mono text-[11.5px] leading-relaxed text-side-fg scroll-thin">{e.sql}</pre>}
        </div>
      </div>
    </li>
  )
}

function Trace({ r }: { r: AskResult }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-5 rounded-lg border border-border">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-3.5 py-2.5 text-[13px] font-medium">
        <span>How this answer was produced · {r.trace.length} steps · {r.seconds} s</span><ChevronDown size={16} className={cx('text-fg-faint transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ol className="border-t border-border px-3.5 py-3 space-y-2.5">
          {r.trace.map((t, i) => (
            <li key={i} className="grid grid-cols-[20px_1fr_auto] gap-3 text-[13px]">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-canvas text-[11px] font-medium text-fg-mute ring-1 ring-border">{i + 1}</span>
              <div><div className="font-medium">{t.step}</div><div className="text-fg-mute">{t.detail}</div></div>
              <div className="flex items-start gap-2">
                <Badge tone={t.mode === 'model' ? 'ai' : t.mode === 'code' ? 'brand' : 'neutral'}>{t.mode === 'model' ? 'AI model' : t.mode === 'code' ? 'code' : t.mode}</Badge>
                {t.seconds != null && <span className="tnum text-[12px] text-fg-mute">{t.seconds.toFixed(1)} s</span>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default function Ask() {
  const { meta } = useStore()
  const [q, setQ] = useState('')
  const [r, setR] = useState<AskResult | null>(null)
  const [started, setStarted] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [decided, setDecided] = useState<string | null>(null)
  const model = !!meta?.model
  const go = async (text: string) => {
    setQ(text); setStarted(Date.now()); setErr(null); setR(null); setDecided(null)
    try { setR(await api.ask(text)) } catch (e) { setErr(String((e as Error).message)) } finally { setStarted(null) }
  }
  const decide = async (d: 'approved' | 'rejected' | 'flagged') => { if (r) { await api.approve(r.id, d); setDecided(d) } }
  const b = r?.brief
  const g = r?.grounding
  return (
    <div className="max-w-[1180px]">
      <PageHeader title={<span className="flex items-center gap-2"><Sparkles size={22} className="text-ai" /> Ask</span>}
        sub={<>Ask about the survey and operating data in plain language. The AI reads the question and writes the brief; every number comes from SQL on the database and is checked. {model ? <>Model: <b>{meta?.model}</b> (GW Azure OpenAI).</> : <>No model key: rules mode.</>}</>} />
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); if (q.trim() && !started) go(q) }} className="flex items-center gap-2 rounded-xl border border-border-strong p-1.5 pl-4 focus-within:ring-4 focus-within:ring-brand/10">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why did the Richmond night shift's scores drop?" className="flex-1 bg-transparent text-[14.5px] focus:outline-none" />
          <Button type="submit" variant="brand" disabled={!q.trim() || !!started} icon={<ArrowUp size={16} />}>Ask</Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((x) => <button key={x} disabled={!!started} onClick={() => go(x)} className="rounded-full border border-border px-3 py-1 text-[12.5px] text-fg-soft hover:bg-canvas disabled:opacity-40">{x}</button>)}
        </div>
      </Card>

      {started && <Progress started={started} model={model} />}
      {err && <Card className="mt-6 border-crit-100 text-crit-700">{err}</Card>}

      {r && (
        <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.35fr_1fr] animate-in">
          <Card>
            <div className="flex flex-wrap items-center gap-2">
              <Provenance kind={r.mode === 'model' ? 'model' : 'computed'} />
              {r.assessment && <Badge tone="brand">Verdict computed by code</Badge>}
              {g && g.total > 0 && <Badge tone={g.checked === g.total ? 'ok' : 'warn'}><ShieldCheck size={12} /> {g.checked} of {g.total} numbers checked against the evidence</Badge>}
            </div>
            <h2 className="mt-3 text-[18px] font-semibold leading-snug">{r.assessment?.label ?? r.message}</h2>
            {b && (
              <div className="mt-4 space-y-4 text-[14px]">
                <div><div className="label mb-1">Likely obstacle</div><p>{b.obstacle}</p></div>
                <div><div className="label mb-1">Evidence for</div><ul className="space-y-1.5">{b.evidence_for.map((x, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" /><span>{x.claim} <span className="font-mono text-[11px] text-fg-faint">{(x.evidence_ids ?? []).join(' ')}</span></span></li>)}</ul></div>
                {b.evidence_against.length > 0 && <div><div className="label mb-1">Evidence against</div><ul className="space-y-1.5">{b.evidence_against.map((x, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-faint" /><span className="text-fg-soft">{x.claim}</span></li>)}</ul></div>}
                {b.missing.length > 0 && <div><div className="label mb-1">What the data can't tell us</div><ul className="list-disc pl-5 text-fg-soft">{b.missing.map((x, i) => <li key={i}>{x}</li>)}</ul></div>}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 rounded-lg bg-canvas p-3"><div><div className="label mb-1">Owner</div><p>{b.owner}</p></div><div><div className="label mb-1">Proposed test</div><p>{b.proposed_test}</p></div></div>
              </div>
            )}
            {r.status !== 'ok' && <p className="mt-3 text-fg-soft">{r.message}</p>}
            <Trace r={r} />
            {r.status === 'ok' && (
              <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
                {decided ? <Badge tone={decided === 'approved' ? 'ok' : 'warn'} dot>Recorded in the review log: {decided}</Badge> : (<>
                  <span className="mr-1 text-[12.5px] text-fg-mute">Your decision:</span>
                  <Button size="sm" variant="brand" icon={<ThumbsUp size={14} />} onClick={() => decide('approved')}>Approve</Button>
                  <Button size="sm" variant="secondary" icon={<ThumbsDown size={14} />} onClick={() => decide('rejected')}>Reject</Button>
                  <Button size="sm" variant="ghost" icon={<Flag size={14} />} onClick={() => decide('flagged')}>This doesn't sound right</Button></>)}
              </div>
            )}
          </Card>
          <Card>
            <CardHeader title="Evidence register" sub={`${r.evidence.length} items the brief is allowed to use`} />
            <ul className="max-h-[720px] overflow-y-auto scroll-thin pr-1">{r.evidence.map((e) => <EvidenceRow key={e.id} e={e} />)}</ul>
          </Card>
        </div>
      )}
    </div>
  )
}
