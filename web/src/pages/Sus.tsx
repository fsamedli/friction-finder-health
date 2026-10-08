import { useState } from 'react'
import { Button, Card, PageHeader, cx } from '../components/ui'

// System Usability Scale, Brooke (1996), standard wording; 1 = strongly disagree, 5 = strongly agree.
const SUS = [
  'I think that I would like to use this system frequently.',
  'I found the system unnecessarily complex.',
  'I thought the system was easy to use.',
  'I think that I would need the support of a technical person to be able to use this system.',
  'I found the various functions in this system were well integrated.',
  'I thought there was too much inconsistency in this system.',
  'I would imagine that most people would learn to use this system very quickly.',
  'I found the system very cumbersome to use.',
  'I felt very confident using the system.',
  'I needed to learn a lot of things before I could get going with this system.',
]
const OPEN = ['What would stop you from using this on your unit?', 'What was the most useful thing you saw, and why?']

export default function Sus() {
  const pid = (() => { try { return sessionStorage.getItem('ff.pid') ?? '' } catch { return '' } })()
  const [a, setA] = useState<(number | null)[]>(Array(10).fill(null))
  const [open, setOpen] = useState(['', ''])
  const [state, setState] = useState<'form' | 'sent' | string>('form')
  const submit = async () => {
    const r = await fetch('/api/study', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ participant: pid, event: 'sus', answers: a, open_answers: open }) })
    setState(r.ok ? 'sent' : `Could not save (${r.status})`)
  }
  if (!pid) return <PageHeader title="Questionnaire" sub="Open this from study mode (add ?study=1 to the address) so the answers are linked to a participant." />
  if (state === 'sent') return <PageHeader title="Thank you" sub="Your answers are saved. You can hand the laptop back." />
  return (
    <div className="max-w-3xl">
      <PageHeader title="Questionnaire" sub={`Participant ${pid} · 1 = strongly disagree, 5 = strongly agree`} />
      <Card>
        <ol className="space-y-4">
          {SUS.map((q, i) => (
            <li key={i}>
              <div className="text-[14px]">{i + 1}. {q}</div>
              <div className="mt-2 flex gap-2" role="radiogroup" aria-label={q}>
                {[1, 2, 3, 4, 5].map((v) => (
                  <button key={v} role="radio" aria-checked={a[i] === v} onClick={() => setA((x) => x.map((y, j) => (j === i ? v : y)))}
                    className={cx('h-9 w-11 rounded-lg ring-1 text-[13px] font-medium', a[i] === v ? 'bg-fg text-white ring-fg' : 'ring-border hover:bg-canvas')}>{v}</button>
                ))}
              </div>
            </li>
          ))}
          {OPEN.map((q, i) => (
            <li key={q}>
              <label className="text-[14px]">{11 + i}. {q}
                <textarea value={open[i]} onChange={(e) => setOpen((o) => o.map((y, j) => (j === i ? e.target.value : y)))} rows={3}
                  className="mt-2 w-full rounded-lg border border-border-strong p-2 text-[13.5px] focus:outline-none focus:ring-4 focus:ring-brand/10" />
              </label>
            </li>
          ))}
        </ol>
        <div className="mt-5 flex items-center gap-3">
          <Button onClick={submit} disabled={a.some((x) => x == null)}>Submit</Button>
          {state !== 'form' && <span className="text-crit-700 text-[13px]">{state}</span>}
        </div>
      </Card>
    </div>
  )
}
