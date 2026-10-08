import { useEffect, useMemo, useRef, useState } from 'react'
import { ClipboardPlus } from 'lucide-react'
import { api, type Kpi, type Plan, type PlanAction, type PlanDraft } from '../lib/api'
import { longDate } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { useFunctions } from '../lib/store'
import { Badge, Button, Card, CardHeader, Provenance, StateNote } from './ui'

/** Review date rule, the same one api/main.py `_default_review` applies when none is sent: operating data is monthly,
 *  so the review is the last day of the second full month after the start (Sept 21 -> Nov 30). Display only. */
export function defaultReview(start: string): string {
  const [y, m] = start.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + 3, 1) - 864e5)
  return d.toISOString().slice(0, 10)
}

export interface DraftSeed {
  team_id: number; team_label: string; kpi: Kpi; item: string; focus: string; obstacle: string; actions: PlanAction[]; start: string
  owner?: string; measure?: string; success?: string; baseline?: string; assumptions?: string[]; finding?: string; rationale?: string
  review?: string; evidence_ids?: string[]; investigation_id?: string | null
}

export function seedFromDraft(d: PlanDraft, investigation_id?: string | null): DraftSeed {
  return { team_id: d.team_id, team_label: d.team_label, kpi: d.kpi, item: d.item, focus: d.focus, obstacle: d.obstacle, actions: d.actions,
    start: d.start, review: d.review, owner: d.owner, measure: d.measure, success: d.success, baseline: d.baseline, assumptions: d.assumptions,
    finding: d.finding, rationale: d.rationale, evidence_ids: d.evidence_ids, investigation_id: investigation_id ?? null }
}

const rid = () => (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)
const KEY = (team: number) => `ff.draft.${team}`

/** A drafted plan the manager edits and approves. Approval is the manager's: one click, blocked while saving, and a
 *  request id made once per draft so a double click cannot record two plans. The draft is kept in this browser until
 *  it is approved, so an error or a reload never loses the manager's edits. */
export default function PlanEditor({ seed, onSaved, title = 'Draft action plan' }: { seed: DraftSeed; onSaved: (p: Plan) => void; title?: string }) {
  const saved = useMemo(() => { try { const v = localStorage.getItem(KEY(seed.team_id)); return v ? JSON.parse(v) : null } catch { return null } }, [seed.team_id])
  const [obstacle, setObstacle] = useState<string>(saved?.obstacle ?? seed.obstacle)
  const [actions, setActions] = useState<PlanAction[]>(saved?.actions ?? seed.actions)
  const [owner, setOwner] = useState<string>(saved?.owner ?? seed.owner ?? '')
  const [measure, setMeasure] = useState<string>(saved?.measure ?? seed.measure ?? '')
  const [success, setSuccess] = useState<string>(saved?.success ?? seed.success ?? '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [check, setCheck] = useState<{ existing: Plan[]; explanation: string } | null>(null)
  const [checkErr, setCheckErr] = useState<string | null>(null)
  const requestId = useRef<string>(saved?.request_id ?? rid())
  const review = seed.review ?? defaultReview(seed.start)

  const [dirty, setDirty] = useState<boolean>(!!saved)
  useEffect(() => {  // only the manager's own edits are kept, never an untouched prefill
    if (!dirty) return
    try { localStorage.setItem(KEY(seed.team_id), JSON.stringify({ obstacle, actions, owner, measure, success, request_id: requestId.current })) } catch { /* private mode */ }
  }, [dirty, seed.team_id, obstacle, actions, owner, measure, success])
  const fns = useFunctions()
  const v08 = !!fns?.length
  useEffect(() => {
    if (!v08) return
    let live = true
    api.planCheck(seed.team_id, seed.kpi, seed.start).then((c) => { if (live) setCheck(c) }).catch((e) => { if (live) setCheckErr(String(e.message)) })
    return () => { live = false }
  }, [v08, seed.team_id, seed.kpi, seed.start])

  const edits = () => {
    const out: { field: string; from: string; to: string }[] = []
    const cmp = (field: string, a: string | undefined, b: string) => { if ((a ?? '') !== b) out.push({ field, from: a ?? '', to: b }) }
    cmp('obstacle', seed.obstacle, obstacle); cmp('owner', seed.owner, owner); cmp('measure', seed.measure, measure); cmp('success', seed.success, success)
    actions.forEach((a, i) => { const s = seed.actions[i]; cmp(`action ${i + 1}`, s?.text, a.text); cmp(`action ${i + 1} owner`, s?.owner, a.owner); cmp(`action ${i + 1} due`, s?.due, a.due) })
    return out
  }
  const approve = async () => {
    if (busy) return
    setBusy(true); setErr(null)
    try {
      const p = await api.createPlan({
        team_id: seed.team_id, item: seed.item, kpi: seed.kpi, obstacle, focus: seed.focus,
        actions: actions.filter((a) => a.text.trim()), start: seed.start, review, status: 'approved', note: 'Approved in the app',
        owner, measure, success, baseline: seed.baseline, assumptions: seed.assumptions, finding: seed.finding, rationale: seed.rationale,
        evidence_ids: seed.evidence_ids, investigation_id: seed.investigation_id ?? null, request_id: requestId.current, edits: edits(),
      })
      try { localStorage.removeItem(KEY(seed.team_id)) } catch { /* private mode */ }
      onSaved(p)
    } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(false) }
  }
  const set = (i: number, k: keyof PlanAction, v: string) => { setDirty(true); setActions((a) => a.map((x, j) => (j === i ? { ...x, [k]: v } : x))) }
  const input = 'rounded-lg border border-border-strong bg-surface px-3 py-2 text-[13.5px] focus:outline-none focus:ring-4 focus:ring-brand/10'
  return (
    <Card>
      <CardHeader title={title} sub="Drafted from this team's evidence. Edit anything, then approve. Nothing reaches the team until a person approves." right={<Provenance kind="person" />} />
      {seed.finding && <p className="mb-3 rounded-lg bg-canvas px-3 py-2 text-[13px] text-fg-soft"><b className="text-fg">Finding:</b> {seed.finding}</p>}
      <label className="block"><span className="label">Obstacle to test</span>
        <input value={obstacle} onChange={(e) => { setDirty(true); setObstacle(e.target.value) }} className={`mt-1 w-full ${input} text-[15px] font-medium`} /></label>
      <p className="mt-2 text-[12.5px] text-fg-mute">Focus item: {seed.focus} · KPI to watch: {KPI_SHORT[seed.kpi]} · starts {longDate(seed.start).replace(', 2026', '')}, reviewed {longDate(review)} (two full months of operating data)</p>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <label className="block"><span className="label">Owner</span><input aria-label="Plan owner" value={owner} onChange={(e) => { setDirty(true); setOwner(e.target.value) }} placeholder="Owner needed" className={`mt-1 w-full ${input}`} /></label>
        <label className="block"><span className="label">Operational measure</span><input aria-label="Operational measure" value={measure} onChange={(e) => { setDirty(true); setMeasure(e.target.value) }} className={`mt-1 w-full ${input}`} /></label>
        <label className="block"><span className="label">Success criterion</span><input aria-label="Success criterion" value={success} onChange={(e) => { setDirty(true); setSuccess(e.target.value) }} className={`mt-1 w-full ${input}`} /></label>
      </div>
      {seed.baseline && <p className="mt-2 text-[12.5px] text-fg-mute">Baseline: {seed.baseline}</p>}
      <div className="mt-4 space-y-2">
        <div className="label">Actions</div>
        {actions.map((a, i) => (
          <div key={i} className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_220px_150px]">
            <input aria-label={`Action ${i + 1}`} value={a.text} onChange={(e) => set(i, 'text', e.target.value)} className={input} />
            <input aria-label={`Action ${i + 1} owner`} value={a.owner} onChange={(e) => set(i, 'owner', e.target.value)} className={input} />
            <input aria-label={`Action ${i + 1} due date`} type="date" value={a.due} onChange={(e) => set(i, 'due', e.target.value)} className={input} />
          </div>
        ))}
      </div>
      {seed.assumptions && seed.assumptions.length > 0 && (
        <div className="mt-4"><div className="label">Assumptions</div><ul className="mt-1 list-disc pl-5 text-[12.5px] text-fg-soft">{seed.assumptions.map((x) => <li key={x}>{x}</li>)}</ul></div>
      )}
      <div className="mt-4">
        {check && check.existing.length > 0 && (
          <StateNote kind="fallback" title={`An existing plan covers this team${check.existing.length > 1 ? ` (${check.existing.length})` : ''}`}>
            {check.explanation} {check.existing.map((p) => `${p.team_label ?? ''} · ${p.obstacle} · ${longDate(p.start)} → ${longDate(p.review)}`).join('; ')}
          </StateNote>
        )}
        {check && check.existing.length === 0 && <p className="text-[12.5px] text-fg-mute"><Badge tone="brand">Checked</Badge> {check.explanation}</p>}
        {(checkErr || (fns && !v08)) && <p className="text-[12.5px] text-fg-mute">The existing-plan check is unavailable on this server{checkErr ? ` (${checkErr})` : ''}.</p>}
      </div>
      {err && <p role="alert" className="mt-3 text-[13px] text-crit-700">Not saved: {err}. Your edits are kept; try again.</p>}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button variant="decide" onClick={approve} disabled={busy || !obstacle.trim()} icon={<ClipboardPlus size={15} />}>{busy ? 'Saving…' : 'Approve plan'}</Button>
        <span className="text-[12px] text-fg-mute">Your approval is recorded with your edits and the time.</span>
      </div>
    </Card>
  )
}
