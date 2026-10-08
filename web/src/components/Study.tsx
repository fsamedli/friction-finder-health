import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, ClipboardCheck, Play, Square } from 'lucide-react'
import { cx } from './ui'

// Usability study mode (docs/usability/PROTOCOL.md). Active only with ?study=1 in the URL; logs task
// start and finish times to study.jsonl via /api/study. Nothing is logged in normal use.
export const TASKS = [
  'Find the team that is costing the hospital the most right now.',
  'Explain why: what moved, and what is behind it?',
  'Approve a plan for that team, then check whether it worked.',
]

export const studyOn = () => { try { return new URLSearchParams(window.location.search).get('study') === '1' || sessionStorage.getItem('ff.study') === '1' } catch { return false } }

async function log(body: Record<string, unknown>) {
  await fetch('/api/study', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export default function StudyBar() {
  const nav = useNavigate()
  const [pid, setPid] = useState(() => { try { return sessionStorage.getItem('ff.pid') ?? '' } catch { return '' } })
  const [draft, setDraft] = useState('P1')
  const [task, setTask] = useState<number | null>(null)
  const [done, setDone] = useState<number[]>([])
  try { sessionStorage.setItem('ff.study', '1') } catch { /* private mode */ }
  if (!pid) {
    return (
      <div className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 rounded-xl border border-border bg-surface p-3 shadow-pop flex items-center gap-2 text-[13px]">
        <ClipboardCheck size={16} className="text-info-700" /> Study mode · participant id
        <input value={draft} onChange={(e) => setDraft(e.target.value.toUpperCase())} className="w-16 rounded-md border border-border-strong px-2 py-1" aria-label="Participant id" />
        <button onClick={() => { if (/^P\d{1,3}$/.test(draft)) { setPid(draft); try { sessionStorage.setItem('ff.pid', draft) } catch { /* */ } } }} className="rounded-md bg-fg px-2.5 py-1 text-white">Begin</button>
      </div>
    )
  }
  const start = async (t: number) => { await log({ participant: pid, event: 'task_start', task: t }); setTask(t) }
  const finish = async (success: boolean) => { if (task == null) return; await log({ participant: pid, event: 'task_finish', task, success }); setDone((d) => [...d, task]); setTask(null) }
  return (
    <div className="fixed bottom-4 left-1/2 z-40 w-[min(640px,calc(100vw-24px))] -translate-x-1/2 rounded-xl border border-border bg-surface p-3 shadow-pop text-[13px]">
      <div className="flex items-center justify-between"><span className="font-medium">Study · {pid}</span><span className="text-fg-mute">{done.length}/3 tasks</span></div>
      {task == null ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {TASKS.map((_, i) => (
            <button key={i} disabled={done.includes(i + 1)} onClick={() => start(i + 1)}
              className={cx('inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 ring-1 ring-border', done.includes(i + 1) ? 'text-fg-faint' : 'hover:bg-canvas')}>
              {done.includes(i + 1) ? <Check size={13} /> : <Play size={13} />} Task {i + 1}
            </button>
          ))}
          {done.length === 3 && <button onClick={() => nav('/study/sus')} className="rounded-md bg-fg px-2.5 py-1 text-white">Questionnaire</button>}
        </div>
      ) : (
        <div className="mt-2">
          <p className="text-fg-soft">Task {task}: {TASKS[task - 1]}</p>
          <div className="mt-2 flex gap-2">
            <button onClick={() => finish(true)} className="inline-flex items-center gap-1 rounded-md bg-fg px-2.5 py-1 text-white"><Square size={12} /> Done</button>
            <button onClick={() => finish(false)} className="rounded-md px-2.5 py-1 ring-1 ring-border hover:bg-canvas">Gave up</button>
          </div>
        </div>
      )}
    </div>
  )
}
