import { useState } from 'react'
import { api, type AskResult, type Evidence } from '../lib/api'
import { useStore } from '../lib/store'
import { Button, Card, Chip, Eyebrow, PageTitle } from '../components/ui'

const EXAMPLES = [
  "Why did the Richmond night shift's scores drop and why are deliveries late?",
  'Did the Norfolk Day B team really decline?',
  'Who owns the shift handoff procedure at Richmond?',
  'Why did the Denver site drop?',
]

function Ev({ e }: { e: Evidence }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="border-t border-line py-2.5">
      <div className="flex gap-3">
        <span className="font-mono text-[11.5px] text-ink-mute w-8 shrink-0 pt-0.5">{e.id}</span>
        <div className="flex-1">
          <div className="text-[14px]">{e.statement}</div>
          <div className="mt-1 flex gap-2 items-center">
            <Chip kind={e.origin === 'retrieved' ? 'neutral' : 'computed'}>{e.origin === 'retrieved' ? 'retrieved text' : 'computed'}</Chip>
            {e.sql && <button onClick={() => setOpen((o) => !o)} className="text-[12px] font-semibold text-teal underline decoration-dotted underline-offset-4">{open ? 'Hide' : 'Show me'} the SQL</button>}
          </div>
          {open && e.sql && <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-ink text-paper/90 p-3 font-mono text-[11.5px]">{e.sql}</pre>}
        </div>
      </div>
    </li>
  )
}

export default function Ask() {
  const { meta } = useStore()
  const [q, setQ] = useState('')
  const [r, setR] = useState<AskResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [decided, setDecided] = useState<string | null>(null)
  const go = async (text: string) => {
    setQ(text); setBusy(true); setErr(null); setR(null); setDecided(null)
    try { setR(await api.ask(text)) } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(false) }
  }
  const decide = async (d: 'approved' | 'rejected' | 'flagged') => { if (r) { await api.approve(r.id, d); setDecided(d) } }
  const b = r?.brief
  return (
    <div>
      <PageTitle kicker="Ask a question · drill-down" title="Ask about the survey and operating data in plain language."
        lede={<>The model reads the question and writes the brief; the numbers come from SQL on the views and are checked. Model: <b>{meta?.model ?? 'none (rules mode)'}</b>.</>} />
      <Card className="p-5">
        <form onSubmit={(e) => { e.preventDefault(); if (q.trim()) go(q) }} className="flex flex-wrap gap-3">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Why did the Richmond night shift's scores drop?"
            className="flex-1 min-w-[260px] rounded-full border border-line bg-paper px-5 py-3 text-[15px] focus:outline-none focus:ring-2 focus:ring-teal/30" />
          <Button type="submit" disabled={busy || !q.trim()}>{busy ? 'Working…' : 'Ask'}</Button>
        </form>
        <div className="flex flex-wrap gap-2 mt-3">{EXAMPLES.map((x) => <button key={x} onClick={() => go(x)} className="rounded-full border border-line px-3 py-1 text-[12.5px] text-ink-soft hover:border-ink-mute">{x}</button>)}</div>
      </Card>

      {busy && <p className="mt-8 text-ink-mute">Reading the question, querying the views, retrieving comments, checking the draft{meta?.model ? ' — about 30 seconds with the model' : ''}…</p>}
      {err && <p className="mt-6 text-rust">{err}</p>}

      {r && (
        <div className="mt-8 grid gap-6 lg:grid-cols-[1.3fr_1fr] animate-rise">
          <Card className="p-6" tone={r.status === 'ok' ? 'teal' : 'ink'}>
            <div className="flex flex-wrap gap-2 items-center">
              <Chip kind={r.mode === 'model' ? 'model' : 'computed'}>{r.mode === 'model' ? 'model-written, checked' : 'rules mode'}</Chip>
              <Chip kind="neutral">{r.seconds}s</Chip>
              {r.assessment && <Chip kind="computed">verdict computed by code</Chip>}
            </div>
            <h2 className="font-serif text-[1.5rem] font-semibold mt-3">{r.assessment?.label ?? r.message}</h2>
            {b && (
              <div className="mt-4 space-y-4 text-[14.5px]">
                <div><Eyebrow>Likely obstacle</Eyebrow><p className="mt-1">{b.obstacle}</p></div>
                <div><Eyebrow>Evidence for</Eyebrow><ul className="mt-1 list-disc pl-5 space-y-1">{b.evidence_for.map((x, i) => <li key={i}>{x.claim} <span className="font-mono text-[11px] text-ink-mute">{(x.evidence_ids ?? []).join(' ')}</span></li>)}</ul></div>
                {b.evidence_against.length > 0 && <div><Eyebrow>Evidence against</Eyebrow><ul className="mt-1 list-disc pl-5 space-y-1">{b.evidence_against.map((x, i) => <li key={i}>{x.claim}</li>)}</ul></div>}
                {b.missing.length > 0 && <div><Eyebrow>What is missing</Eyebrow><ul className="mt-1 list-disc pl-5">{b.missing.map((x, i) => <li key={i}>{x}</li>)}</ul></div>}
                <div className="grid sm:grid-cols-2 gap-4"><div><Eyebrow>Owner</Eyebrow><p className="mt-1">{b.owner}</p></div><div><Eyebrow>Proposed test</Eyebrow><p className="mt-1">{b.proposed_test}</p></div></div>
              </div>
            )}
            {r.status !== 'ok' && <p className="mt-3 text-ink-soft">{r.message}</p>}
            {r.status === 'ok' && (
              <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-line pt-4">
                {decided ? <Chip kind="person">Recorded: {decided}</Chip> : (<>
                  <Button kind="person" onClick={() => decide('approved')}>Approve</Button>
                  <Button kind="ghost" onClick={() => decide('rejected')}>Reject</Button>
                  <Button kind="quiet" onClick={() => decide('flagged')}>This doesn't sound right</Button></>)}
              </div>
            )}
          </Card>
          <Card className="p-6">
            <Eyebrow>Evidence register · {r.evidence.length} items</Eyebrow>
            <ul className="mt-2">{r.evidence.map((e) => <Ev key={e.id} e={e} />)}</ul>
          </Card>
        </div>
      )}
    </div>
  )
}
