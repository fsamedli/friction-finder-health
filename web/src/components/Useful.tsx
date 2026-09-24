import { useState } from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { api } from '../lib/api'
import { cx } from './ui'

const REASONS = ['wrong number', 'wrong owner', 'not actionable', 'other'] as const

/** "Useful? yes / no" with a reason. Saved to feedback.jsonl; counts appear on Trust › Quality. */
export default function Useful({ target, id }: { target: 'ask' | 'plan'; id: string }) {
  const [state, setState] = useState<'ask' | 'why' | 'done'>('ask')
  const [err, setErr] = useState<string | null>(null)
  const send = async (useful: boolean, reason?: string) => {
    try { await api.useful(target, id, useful, reason); setState('done') } catch (e) { setErr(String((e as Error).message)) }
  }
  if (state === 'done') return <span className="text-[12.5px] text-fg-mute">Thanks, recorded.</span>
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
      <span className="text-fg-mute">Useful?</span>
      {state === 'ask' ? (
        <>
          <button onClick={() => send(true)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 ring-1 ring-border hover:bg-canvas"><ThumbsUp size={13} /> Yes</button>
          <button onClick={() => setState('why')} className="inline-flex items-center gap-1 rounded-md px-2 py-1 ring-1 ring-border hover:bg-canvas"><ThumbsDown size={13} /> No</button>
        </>
      ) : (
        <>
          <span className="text-fg-soft">What was wrong?</span>
          {REASONS.map((r) => (
            <button key={r} onClick={() => send(false, r)} className={cx('rounded-md px-2 py-1 ring-1 ring-border hover:bg-canvas')}>{r}</button>
          ))}
        </>
      )}
      {err && <span className="text-crit-700">{err}</span>}
    </div>
  )
}
