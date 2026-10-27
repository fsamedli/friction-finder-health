import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, CalendarCheck, Check, ClipboardCheck, Copy, Eye, FileText, Mail, Plus, UserCheck } from 'lucide-react'
import { api, type ActionStatus, type Plan, type PlanAction } from '../lib/api'
import { longDate } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { useLoad, useStore } from '../lib/store'
import Useful from '../components/Useful'
import Journey from '../components/Journey'
import { Badge, Button, Card, CardHeader, ErrorState, PageHeader, PageSkeleton, Provenance, StateNote, cx } from '../components/ui'

/** The Execute step (Prof. Hall, Oct 21): the approved plan as a checklist the nurse manager runs. Each task has a
 *  responsible person, a due date and a status the manager ticks; edits save on blur and are recorded with the time.
 *  Below it, what the system did when the plan was approved: owners assigned, review scheduled, KPI watch set, owner
 *  notices drafted. Nothing is sent by this prototype. */

const STATUS: Record<ActionStatus, { label: string; tone: 'neutral' | 'ok' | 'warn' }> = {
  todo: { label: 'Open', tone: 'neutral' }, done: { label: 'Done', tone: 'ok' }, blocked: { label: 'Blocked', tone: 'warn' },
}
const input = 'w-full rounded-lg border border-transparent bg-transparent px-2 py-1.5 text-[13.5px] hover:border-border-strong focus:border-border-strong focus:bg-surface focus:outline-none focus:ring-4 focus:ring-brand/10'

function TaskRow({ a, i, planId, onSaved }: { a: PlanAction; i: number; planId: string; onSaved: (p: Plan) => void }) {
  const [text, setText] = useState(a.text)
  const [owner, setOwner] = useState(a.owner)
  const [due, setDue] = useState(a.due)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const status: ActionStatus = a.status ?? 'todo'
  const save = async (body: Partial<Pick<PlanAction, 'text' | 'owner' | 'due' | 'status'>>) => {
    if (busy || !a.id) return
    setBusy(true); setErr(null)
    try { onSaved(await api.patchAction(planId, a.id, body)) } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(false) }
  }
  const toggle = () => save({ status: status === 'done' ? 'todo' : 'done' })
  return (
    <li className={cx('grid grid-cols-[28px_minmax(0,1fr)] gap-x-3 px-3 py-3', status === 'done' && 'bg-ok-50/40')}>
      <button type="button" role="checkbox" aria-checked={status === 'done'} aria-label={`Task ${i + 1} done`} onClick={toggle} disabled={busy}
        className={cx('mt-1 flex h-6 w-6 items-center justify-center rounded-md ring-1 ring-inset transition-colors', status === 'done' ? 'bg-ok text-white ring-ok' : 'bg-surface text-transparent ring-border-strong hover:ring-fg')}>
        <Check size={15} />
      </button>
      <div className="min-w-0">
        {/* the task reads in full on its own line (Prof. Hall: enlarge key information); who, when and status sit under it */}
        <textarea aria-label={`Task ${i + 1}`} value={text} rows={1} onChange={(e) => { setText(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${e.target.scrollHeight}px` }}
          ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px` } }}
          onBlur={() => text.trim() !== a.text && text.trim().length >= 3 && save({ text: text.trim() })}
          className={cx(input, 'resize-none overflow-hidden text-[15px] font-medium leading-snug', status === 'done' && 'text-fg-mute line-through decoration-fg-faint')} />
        <div className="mt-1 grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-[minmax(0,1.4fr)_150px_96px] sm:items-center">
          <label className="flex min-w-0 items-center gap-2 text-[12px] text-fg-mute"><span className="shrink-0">Responsible</span>
            <input aria-label={`Task ${i + 1} responsible`} value={owner} onChange={(e) => setOwner(e.target.value)} onBlur={() => owner.trim() !== a.owner && owner.trim() && save({ owner: owner.trim() })}
              className={cx(input, 'text-fg-soft')} placeholder="Responsible" /></label>
          <label className="flex items-center gap-2 text-[12px] text-fg-mute"><span className="shrink-0">Due</span>
            <input aria-label={`Task ${i + 1} due date`} type="date" value={due} onChange={(e) => setDue(e.target.value)} onBlur={() => due !== a.due && due && save({ due })}
              className={cx(input, 'tnum text-fg-soft')} /></label>
          <div className="flex items-center sm:justify-end">
            <button type="button" onClick={() => save({ status: status === 'blocked' ? 'todo' : 'blocked' })} disabled={busy} title={status === 'blocked' ? 'Unblock' : 'Mark blocked'}
              className="rounded-md focus:outline-none focus-visible:shadow-ring"><Badge tone={STATUS[status].tone} dot>{STATUS[status].label}</Badge></button>
          </div>
        </div>
        {err && <p role="alert" className="mt-1 text-[12px] text-crit-700">Not saved: {err}</p>}
      </div>
    </li>
  )
}

function AddTask({ plan, onSaved }: { plan: Plan; onSaved: (p: Plan) => void }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [owner, setOwner] = useState(plan.owner ?? '')
  const [due, setDue] = useState(plan.review)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  if (!open) return <Button variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => setOpen(true)}>Add a task</Button>
  const add = async () => {
    if (busy || text.trim().length < 3) return
    setBusy(true); setErr(null)
    try { onSaved(await api.addAction(plan.id, { text: text.trim(), owner: owner.trim(), due })); setText(''); setOpen(false) } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(false) }
  }
  const box = 'rounded-lg border border-border-strong bg-surface px-3 py-2 text-[13.5px] focus:outline-none focus:ring-4 focus:ring-brand/10'
  return (
    <div className="grid grid-cols-1 gap-2 rounded-lg border border-dashed border-border-strong p-3 md:grid-cols-[1.6fr_1fr_150px_auto]">
      <input aria-label="New task" autoFocus value={text} onChange={(e) => setText(e.target.value)} placeholder="What has to happen" className={box} onKeyDown={(e) => e.key === 'Enter' && add()} />
      <input aria-label="New task responsible" value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Responsible (blank = plan owner)" className={box} />
      <input aria-label="New task due date" type="date" value={due} onChange={(e) => setDue(e.target.value)} className={cx(box, 'tnum')} />
      <div className="flex gap-2"><Button size="sm" variant="decide" onClick={add} disabled={busy || text.trim().length < 3}>{busy ? 'Saving…' : 'Add'}</Button><Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
      {err && <p role="alert" className="col-span-full text-[12px] text-crit-700">{err}</p>}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'ok' | 'fail'>('idle')
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setState('ok') } catch { setState('fail') }
    setTimeout(() => setState('idle'), 1800)
  }
  return <Button size="sm" variant="secondary" icon={<Copy size={13} />} onClick={copy}>{state === 'ok' ? 'Copied' : state === 'fail' ? 'Select and copy' : 'Copy'}</Button>
}

export default function PlanDetail() {
  const { planId } = useParams()
  const nav = useNavigate()
  const { asOf } = useStore()
  const plan = useLoad(() => api.plan(planId ?? ''), [planId])
  const result = useLoad(() => (planId ? api.result(planId, asOf) : Promise.resolve(null)), [planId, asOf])
  // model mode: the notices are templated at approval and reworded in the background; poll until the rewrite lands
  useEffect(() => {
    if (!planId || plan.data?.execution?.notices_status !== 'drafting') return
    let n = 0
    const t = setInterval(async () => { n += 1; try { const p = await api.plan(planId); plan.setData(p); if (p.execution?.notices_status !== 'drafting' || n > 20) clearInterval(t) } catch { clearInterval(t) } }, 3000)
    return () => clearInterval(t)
  }, [planId, plan.data?.execution?.notices_status]) // eslint-disable-line react-hooks/exhaustive-deps
  if (plan.error) return <ErrorState error={plan.error} onRetry={() => window.location.reload()} />
  if (!plan.data) return <PageSkeleton />
  const p = plan.data
  const ex = p.execution
  const done = p.actions.filter((a) => a.status === 'done').length
  const total = p.actions.length
  const r = result.data
  const stateBadge = p.status !== 'approved' ? <Badge tone="neutral" dot>Draft</Badge>
    : r?.status === 'ok' ? <Badge tone="info" dot>Reviewed</Badge> : r?.status === 'insufficient' ? <Badge tone="warn" dot>In review</Badge> : <Badge tone="ok" dot>Approved</Badge>
  const crumbs = <><button onClick={() => nav('/plans')} className="hover:text-fg">Action plans</button><span>/</span><span>{p.team_label}</span></>
  const actions = <>
    <Button variant="primary" onClick={() => nav(`/review/${p.id}`)} icon={<ArrowRight size={15} />}>See if the plan worked</Button>
    <a href={`/api/report/${p.id}?as_of=${asOf}`} target="_blank" rel="noreferrer"><Button variant="secondary" icon={<FileText size={15} />}>One-page report</Button></a>
  </>
  const bySource = (ex?.assigned ?? []).reduce<Record<string, number>>((m, x) => ({ ...m, [x.source]: (m[x.source] ?? 0) + 1 }), {})
  const sourceWords = Object.entries(bySource).map(([k, v]) => (k === 'manager' ? `${v} chosen by you` : `${v} from the ${k}`)).join(', ')
  return (
    <div>
      <PageHeader crumbs={crumbs}
        title={<span className="flex flex-wrap items-center gap-3">{p.obstacle || 'Action plan'} {stateBadge}</span>}
        sub={<>{p.team_label} · focus item {p.focus || p.item} · KPI to watch {KPI_SHORT[p.kpi]} · starts {longDate(p.start)}, review {longDate(p.review)}</>}
        actions={actions} />

      {p.status !== 'approved' && (
        <div className="mb-6"><StateNote kind="insufficient" title="This plan is still a draft">Nothing happens until a person approves it. <button onClick={() => nav(`/investigate/${p.team_id}?focus=act`)} className="underline">Open the draft on the Investigate screen</button>.</StateNote></div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader title={<span className="flex items-center gap-2"><ClipboardCheck size={17} className="text-fg-mute" /> Checklist</span>}
            sub="Each task has a responsible person, a due date and a status. Tick a task when it is done; edit any cell and it saves when you leave it."
            right={<><Badge tone={done === total && total > 0 ? 'ok' : 'brand'}>{done} of {total} done</Badge><Provenance kind="person" /></>} />
          <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-canvas" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Tasks done">
            <div className="h-full rounded-full bg-ok transition-all" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
          </div>
          <ul className="divide-y divide-border rounded-lg border border-border">
            {/* keyed on the saved values, so a row remounts with fresh inputs after the server answers; no effect needed */}
            {p.actions.map((a, i) => <TaskRow key={`${a.id ?? i}|${a.text}|${a.owner}|${a.due}`} a={a} i={i} planId={p.id} onSaved={plan.setData} />)}
          </ul>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            {p.status === 'approved' ? <AddTask plan={p} onSaved={plan.setData} /> : <span />}
            <span className="text-[12px] text-fg-mute">Every tick and edit is recorded with the time.</span>
          </div>
          {(p.owner || p.measure || p.success) && (
            <dl className="mt-5 grid grid-cols-1 gap-3 border-t border-border pt-4 text-[13px] sm:grid-cols-3">
              {p.owner && <div><dt className="label">Plan owner</dt><dd className="text-fg-soft">{p.owner}</dd></div>}
              {p.measure && <div><dt className="label">Operational measure</dt><dd className="text-fg-soft">{p.measure}</dd></div>}
              {p.success && <div><dt className="label">Success criterion</dt><dd className="text-fg-soft">{p.success}</dd></div>}
            </dl>
          )}
          <div className="mt-4 border-t border-border pt-3"><Useful target="plan" id={p.id} /></div>
        </Card>

        <div className="space-y-6">
          {ex ? (
            <>
              <Card>
                <CardHeader title="What happened when you approved" sub={ex.derived ? 'Derived from the plan as saved; nothing was sent.' : 'Done by code the moment you approved; recorded, nothing sent.'} right={<Provenance kind="computed" />} />
                <ul className="space-y-3 text-[13.5px]">
                  <li className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700"><UserCheck size={14} /></span>
                    <span><b className="text-fg">Owners assigned</b> to {ex.assigned.length} task{ex.assigned.length === 1 ? '' : 's'}{sourceWords ? <span className="text-fg-mute"> ({sourceWords})</span> : null}.</span></li>
                  <li className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700"><CalendarCheck size={14} /></span>
                    <span><b className="text-fg">Review scheduled</b> for {longDate(ex.review_scheduled.date)}, in the {ex.review_scheduled.queue} queue: <span className="text-fg-soft">{ex.review_scheduled.what}</span>.</span></li>
                  <li className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700"><Eye size={14} /></span>
                    <span><b className="text-fg">KPI watch set</b>: {ex.kpi_watch.kpi_label.toLowerCase()} for {ex.kpi_watch.team_label}, {ex.kpi_watch.cadence}, until {longDate(ex.kpi_watch.until)}.</span></li>
                  <li className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ai-50 text-ai-700"><Mail size={14} /></span>
                    <span><b className="text-fg">Owner notices drafted</b>: {ex.notices.length}, below. <b className="text-fg">Nothing is sent by this prototype</b>; you copy each one into email or the staffing system.</span></li>
                </ul>
              </Card>
              <Card>
                <CardHeader title="Owner notices" sub={ex.notices_status === 'drafting' ? 'Templated now; the AI-assisted rewrite from the same facts is on its way.' : 'One per responsible person, drafted from the plan. Read, change, then send it yourself.'}
                  right={ex.notices.some((n) => n.written_by === 'model') ? <Provenance kind="model" /> : <Badge tone="neutral">Templated · {ex.notices_status === 'drafting' ? 'rewriting' : 'rules mode'}</Badge>} />
                <div className="space-y-4">
                  {ex.notices.map((n, i) => (
                    <article key={i} aria-label={`Notice to ${n.to}`} className={cx('rounded-xl border p-4', n.written_by === 'model' ? 'border-ai-100 bg-ai-50/40' : 'border-border bg-canvas/60')}>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0 text-[13px]"><div><span className="text-fg-mute">To:</span> <b className="text-fg">{n.to}</b></div><div><span className="text-fg-mute">Subject:</span> {n.subject}</div></div>
                        <CopyButton text={`To: ${n.to}\nSubject: ${n.subject}\n\n${n.body}`} />
                      </div>
                      <pre className="mt-3 whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-fg-soft">{n.body}</pre>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11.5px] text-fg-mute">
                        {n.written_by === 'model' ? <Badge tone="ai">AI-written · checked</Badge> : <Badge tone="neutral">Templated</Badge>}
                        <span>{(n.check ?? []).join('; ')}</span><span>· not sent</span>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
            </>
          ) : (
            <Card><CardHeader title="What happens when you approve" /><p className="text-[13.5px] text-fg-soft">Owners are assigned to every task (your choice, else the ownership directory), the review is scheduled, the KPI watch is set and one notice per owner is drafted for you to send. Nothing is sent by this prototype.</p></Card>
          )}
        </div>
      </div>
      <div className="mt-6"><Journey at="execute" teamId={p.team_id} planId={p.id} /></div>
    </div>
  )
}
