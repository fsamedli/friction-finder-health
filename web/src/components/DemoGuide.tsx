import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Play, X } from 'lucide-react'
import { api } from '../lib/api'
import { REVIEW, SEED_PLAN, useStore, visiblePlans } from '../lib/store'
import { cx } from './ui'

// Prof. Hall's five-step flow (Oct 21, 2026): problem and money → investigate → plan → execute → review.
// One sentence per step. No numbers here: every number the audience sees is on the screen itself.
const STEPS = [
  { title: 'Today', say: 'The nurse manager opens this on Monday: one unit team needs attention, what it is costing the hospital in its own operating records, and one next step.' },
  { title: 'Investigate', say: "The manager's questions organise the evidence: is it real, is it normal for teams like ours, what explains it, what is missing, what do I do. Code computes every number; the AI-assisted investigation says how strong the evidence is." },
  { title: 'Plan', say: 'The tool drafts one plan from the evidence. The nurse manager edits the owner, the measure and the actions, then approves; nothing happens without a person.' },
  { title: 'Checklist', say: 'Approval turns the plan into a checklist: each task with a responsible person and a due date, owner notices drafted for the manager to send, and the review date scheduled.' },
  { title: 'Review', say: 'At the review date the unit is compared with similar units that did not act, and the result is translated into dollars with its assumptions stated. Directional, not causal; the follow-up months are synthetic.' },
]
const LAST = STEPS.length - 1
const KEY = 'ff.demo'

export function useDemo() {
  const read = () => { try { const v = localStorage.getItem(KEY); return v == null ? -1 : Number(v) } catch { return -1 } }
  const [step, setStep] = useState<number>(read)
  const set = (n: number) => { try { if (n < 0) localStorage.removeItem(KEY); else localStorage.setItem(KEY, String(n)) } catch { /* private mode */ } setStep(n) }
  // guided highlighting: the block each step talks about carries data-demo="focus|explain|act|checklist|money" and index.css rings it
  useEffect(() => {
    if (step >= 0 && step <= LAST) document.body.setAttribute('data-demo-step', String(step))
    else document.body.removeAttribute('data-demo-step')
    return () => document.body.removeAttribute('data-demo-step')
  }, [step])
  return { step, set }
}

export function StartDemo({ onStart }: { onStart: () => void }) {
  return (
    <button onClick={onStart} className="hidden md:inline-flex h-9 items-center gap-1.5 rounded-lg border border-border-strong px-3 text-[13px] font-medium text-fg-soft hover:bg-canvas">
      <Play size={14} className="text-act" /> Start demo
    </button>
  )
}

export default function DemoGuide({ step, set }: { step: number; set: (n: number) => void }) {
  const nav = useNavigate()
  const { setAsOf } = useStore()
  const [busy, setBusy] = useState(false)
  if (step < 0 || step > LAST) return null
  const s = STEPS[step]
  // the plan approved live in the demo if there is one, otherwise the seeded fallback plan
  const planId = async () => visiblePlans(await api.plans(), REVIEW).filter((p) => p.team_id === 4).slice(-1)[0]?.id ?? SEED_PLAN
  const go = async (n: number) => {
    setBusy(true)
    try {
      if (n === 0) nav('/')
      if (n === 1) nav('/investigate/4')
      if (n === 2) nav('/investigate/4?focus=act&tab=plan')
      if (n === 3) nav(`/plans/${await planId()}`)
      if (n === 4) { const id = await planId(); setAsOf(REVIEW); nav(`/review/${id}`) }
      set(n)
    } finally { setBusy(false) }
  }
  return (
    <div className="fixed bottom-4 right-4 z-40 w-[min(380px,calc(100vw-32px))] rounded-2xl border border-border bg-surface p-4 shadow-pop animate-in" role="dialog" aria-label="Guided demo">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {STEPS.map((x, i) => <span key={x.title} className={cx('h-1.5 rounded-full transition-all', i === step ? 'w-6 bg-fg' : i < step ? 'w-3 bg-brand-500' : 'w-3 bg-border-strong')} />)}
          <span className="ml-2 text-[12.5px] font-medium text-fg-mute">Step {step + 1} of {STEPS.length}</span>
        </div>
        <button onClick={() => set(-1)} aria-label="Close demo" className="rounded-md p-1 text-fg-faint hover:bg-canvas hover:text-fg"><X size={16} /></button>
      </div>
      <div className="mt-3 text-[17px] font-semibold">{s.title}</div>
      <p className="mt-1 text-[14px] leading-relaxed text-fg-soft">{s.say}</p>
      {step === 2 && <p className="mt-2 text-[13px] text-act-700">Approve the plan below; the checklist opens on approval.</p>}
      <div className="mt-4 flex items-center justify-between">
        <button onClick={() => step > 0 && go(step - 1)} disabled={step === 0 || busy} className="text-[13px] font-medium text-fg-mute hover:text-fg disabled:opacity-30">Back</button>
        {step < LAST
          ? <button onClick={() => go(step + 1)} disabled={busy} className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-fg px-3.5 text-[14px] font-medium text-white hover:bg-fg-soft">
              {step === LAST - 1 ? 'Fast-forward to the review' : `Next: ${STEPS[step + 1].title}`} <ArrowRight size={15} />
            </button>
          : <button onClick={() => set(-1)} className="inline-flex h-9 items-center rounded-lg bg-fg px-3.5 text-[14px] font-medium text-white hover:bg-fg-soft">Finish</button>}
      </div>
    </div>
  )
}
