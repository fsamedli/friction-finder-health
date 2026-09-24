import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Play, X } from 'lucide-react'
import { api } from '../lib/api'
import { REVIEW, SEED_PLAN, useStore, visiblePlans } from '../lib/store'
import { cx } from './ui'

// Four clicks, one sentence each. No numbers here: every number the audience sees is on the screen itself.
const STEPS = [
  { title: 'Detect', say: "The site's own operating records show which team is running above comparable teams, and whether its engagement moved at the same time." },
  { title: 'Explain', say: 'Across every team, the tool checks which engagement items move with which operating KPIs, then reads what employees wrote. Association, not cause.' },
  { title: 'Act', say: 'The tool drafts one plan from the evidence. The site manager edits it and approves it; nothing happens without a person.' },
  { title: 'Prove', say: 'At the review date, the team is compared with similar teams that did not act. Directional, not causal; the follow-up months are synthetic.' },
]
const KEY = 'ff.demo'

export function useDemo() {
  const read = () => { try { const v = localStorage.getItem(KEY); return v == null ? -1 : Number(v) } catch { return -1 } }
  const [step, setStep] = useState<number>(read)
  const set = (n: number) => { try { if (n < 0) localStorage.removeItem(KEY); else localStorage.setItem(KEY, String(n)) } catch { /* private mode */ } setStep(n) }
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
  if (step < 0 || step >= STEPS.length) return null
  const s = STEPS[step]
  const go = async (n: number) => {
    setBusy(true)
    try {
      if (n === 0) nav('/')
      if (n === 1) nav('/teams/4')
      if (n === 2) nav('/teams/4?tab=plan')
      if (n === 3) {
        // the plan approved live in the demo if there is one, otherwise the seeded fallback plan
        const live = visiblePlans(await api.plans(), REVIEW).filter((p) => p.team_id === 4).slice(-1)[0]
        setAsOf(REVIEW)
        nav(`/impact/${live?.id ?? SEED_PLAN}`)
      }
      set(n)
    } finally { setBusy(false) }
  }
  return (
    <div className="fixed bottom-4 right-4 z-40 w-[min(380px,calc(100vw-32px))] rounded-2xl border border-border bg-surface p-4 shadow-pop animate-in" role="dialog" aria-label="Guided demo">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {STEPS.map((x, i) => <span key={x.title} className={cx('h-1.5 rounded-full transition-all', i === step ? 'w-6 bg-fg' : i < step ? 'w-3 bg-brand-500' : 'w-3 bg-border-strong')} />)}
          <span className="ml-2 text-[12px] font-medium text-fg-mute">Step {step + 1} of 4</span>
        </div>
        <button onClick={() => set(-1)} aria-label="Close demo" className="rounded-md p-1 text-fg-faint hover:bg-canvas hover:text-fg"><X size={16} /></button>
      </div>
      <div className="mt-3 text-[16px] font-semibold">{s.title}</div>
      <p className="mt-1 text-[13.5px] leading-relaxed text-fg-soft">{s.say}</p>
      {step === 2 && <p className="mt-2 text-[12.5px] text-act-700">Approve the plan below, or go straight to the review.</p>}
      <div className="mt-4 flex items-center justify-between">
        <button onClick={() => step > 0 && go(step - 1)} disabled={step === 0 || busy} className="text-[12.5px] font-medium text-fg-mute hover:text-fg disabled:opacity-30">Back</button>
        {step < 3
          ? <button onClick={() => go(step + 1)} disabled={busy} className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-fg px-3.5 text-[13.5px] font-medium text-white hover:bg-fg-soft">
              {step === 2 ? 'Fast-forward to the review' : `Next: ${STEPS[step + 1].title}`} <ArrowRight size={15} />
            </button>
          : <button onClick={() => set(-1)} className="inline-flex h-9 items-center rounded-lg bg-fg px-3.5 text-[13.5px] font-medium text-white hover:bg-fg-soft">Finish</button>}
      </div>
    </div>
  )
}
