import { useNavigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import { cx } from './ui'

export type Step = 'detect' | 'explain' | 'act' | 'execute' | 'prove'
export const STEPS: { id: Step; label: string; q: string }[] = [
  { id: 'detect', label: 'Today', q: 'What is happening, and what is it costing?' },
  { id: 'explain', label: 'Investigate', q: 'Is it real, and what explains it?' },
  { id: 'act', label: 'Plan', q: 'One plan, one owner, one date' },
  { id: 'execute', label: 'Checklist', q: 'Who does what by when' },
  { id: 'prove', label: 'Review', q: 'Did the operating number move, and what is it worth?' },
]

/** The product's loop, shown on the five screens that make it up (Prof. Hall's five-step flow, Oct 21, 2026).
 *  Earlier steps are ticked; each step links to its screen when the team or plan it needs is known. */
export default function Journey({ at, teamId, planId }: { at: Step; teamId?: number; planId?: string }) {
  const nav = useNavigate()
  const idx = STEPS.findIndex((s) => s.id === at)
  const to: Record<Step, string | null> = {
    detect: '/',
    explain: teamId ? `/investigate/${teamId}` : null,
    act: teamId ? `/investigate/${teamId}?focus=act&tab=plan` : null,
    execute: planId ? `/plans/${planId}` : null,
    prove: planId ? `/review/${planId}` : null,
  }
  return (
    <ol className="mb-5 flex flex-wrap items-center gap-1.5 text-[13px]" aria-label="Today, investigate, plan, checklist, review">
      {STEPS.map((s, i) => {
        const done = i < idx, on = i === idx, target = to[s.id]
        return (
          <li key={s.id} className="flex items-center gap-1.5">
            <button disabled={!target || on} onClick={() => target && nav(target)} title={s.q}
              className={cx('flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ring-1 transition-colors',
                on ? 'bg-fg text-white ring-fg' : done ? 'bg-brand-50 text-brand-700 ring-brand-100 hover:bg-brand-100' : 'bg-surface text-fg-mute ring-border',
                target && !on && 'cursor-pointer', !target && !on && 'cursor-default opacity-70')}>
              <span className={cx('flex h-4 w-4 items-center justify-center rounded-full text-[10px]', on ? 'bg-white/15' : done ? 'bg-brand text-white' : 'bg-canvas ring-1 ring-border')}>
                {done ? <Check size={10} /> : i + 1}
              </span>
              {s.label}
            </button>
            {i < STEPS.length - 1 && <span className={cx('h-px w-4', done ? 'bg-brand-500' : 'bg-border-strong')} />}
          </li>
        )
      })}
    </ol>
  )
}
