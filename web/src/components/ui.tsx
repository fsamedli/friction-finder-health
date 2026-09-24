import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Status } from '../lib/api'

export function Card({ children, className = '', tone }: { children: ReactNode; className?: string; tone?: 'teal' | 'rust' | 'ink' }) {
  const edge = tone === 'teal' ? 'before:bg-teal' : tone === 'rust' ? 'before:bg-rust' : tone === 'ink' ? 'before:bg-ink' : 'before:bg-transparent'
  return (
    <section className={`relative rounded-[14px] border border-line bg-paper-card shadow-card overflow-hidden before:absolute before:left-0 before:top-0 before:h-full before:w-[3px] ${edge} ${className}`}>
      {children}
    </section>
  )
}

export function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`eyebrow ${className}`}>{children}</div>
}

export function PageTitle({ step, kicker, title, lede }: { step?: string; kicker: string; title: ReactNode; lede?: ReactNode }) {
  return (
    <header className="mb-8 animate-rise">
      <div className="flex items-baseline gap-3">
        {step && <span className="num text-teal text-sm">{step}</span>}
        <Eyebrow>{kicker}</Eyebrow>
      </div>
      <h1 className="font-serif text-[2.35rem] leading-[1.08] font-semibold mt-2 max-w-4xl text-balance">{title}</h1>
      {lede && <p className="mt-3 text-ink-soft text-[1.05rem] max-w-3xl">{lede}</p>}
    </header>
  )
}

const STATUS: Record<Status, { label: string; cls: string; dot: string }> = {
  red: { label: 'Look here first', cls: 'bg-rust-soft text-rust-deep', dot: 'bg-rust animate-pulseRing' },
  amber: { label: 'Watch', cls: 'bg-amber-soft text-[#7A5A12]', dot: 'bg-amber' },
  green: { label: 'Normal variation', cls: 'bg-moss-soft text-moss', dot: 'bg-moss' },
  rolled_up: { label: 'Rolled up to site', cls: 'bg-paper-deep text-ink-mute', dot: 'bg-mist' },
}
export function StatusChip({ s }: { s: Status }) {
  const x = STATUS[s]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[12px] font-semibold ${x.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${x.dot}`} />{x.label}
    </span>
  )
}

/** Teal = computed by code; rust = needs a person. The legend the whole app speaks. */
export function Chip({ kind, children }: { kind: 'computed' | 'person' | 'model' | 'synthetic' | 'neutral'; children: ReactNode }) {
  const cls = {
    computed: 'bg-teal-soft text-teal-deep',
    person: 'bg-rust-soft text-rust-deep',
    model: 'bg-[#E9E4F2] text-[#4B3F72]',
    synthetic: 'bg-paper-deep text-ink-mute border border-line',
    neutral: 'bg-paper-deep text-ink-soft',
  }[kind]
  return <span className={`inline-flex items-center rounded-full px-2 py-[2px] text-[11.5px] font-semibold tracking-wide ${cls}`}>{children}</span>
}

/** "How was this computed?" — every number on screen can explain itself. */
export function How({ children, label = 'How computed' }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  return (
    <span ref={ref} className="relative inline-block">
      <button type="button" onClick={(e) => { e.stopPropagation(); setOpen((o) => !o) }}
        className="text-[12px] font-semibold text-teal hover:text-teal-deep underline decoration-dotted underline-offset-4">
        {label}
      </button>
      {open && (
        <span onClick={(e) => e.stopPropagation()} className="absolute z-30 left-0 top-7 w-[360px] max-w-[80vw] rounded-xl border border-line bg-paper-card p-4 text-[13.5px] leading-relaxed text-ink shadow-lift animate-rise block">
          {children}
        </span>
      )}
    </span>
  )
}

export function Stat({ label, value, sub, tone = 'ink' }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'ink' | 'teal' | 'rust' }) {
  const c = tone === 'teal' ? 'text-teal-deep' : tone === 'rust' ? 'text-rust' : 'text-ink'
  return (
    <div>
      <Eyebrow>{label}</Eyebrow>
      <div className={`num text-[2.1rem] leading-none mt-2 ${c}`}>{value}</div>
      {sub && <div className="text-[13px] text-ink-mute mt-1.5">{sub}</div>}
    </div>
  )
}

export function Loading({ label = 'Computing' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink-mute py-16 justify-center">
      <span className="h-2 w-2 rounded-full bg-teal animate-ping" />
      <span className="eyebrow">{label}</span>
    </div>
  )
}

export function ErrorNote({ error }: { error: string }) {
  return <div className="rounded-xl border border-rust/40 bg-rust-soft/50 text-rust-deep px-4 py-3 text-sm">Could not load: {error}. Is the API running on port 8000?</div>
}

export function Button({ children, onClick, kind = 'primary', disabled, type = 'button' }: {
  children: ReactNode; onClick?: () => void; kind?: 'primary' | 'ghost' | 'person' | 'quiet'; disabled?: boolean; type?: 'button' | 'submit'
}) {
  const cls = {
    primary: 'bg-ink text-paper hover:bg-ink-soft',
    person: 'bg-rust text-white hover:bg-rust-deep',
    ghost: 'border border-ink text-ink hover:bg-ink hover:text-paper',
    quiet: 'text-ink-soft hover:text-ink hover:bg-paper-deep',
  }[kind]
  return (
    <button type={type} disabled={disabled} onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-[14px] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${cls}`}>
      {children}
    </button>
  )
}
