import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Info, X } from 'lucide-react'
import type { Status } from '../lib/api'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

export function Card({ children, className, pad = true }: { children: ReactNode; className?: string; pad?: boolean }) {
  return <section className={cx('rounded-xl border border-border bg-surface shadow-card', pad && 'p-5', className)}>{children}</section>
}

export function CardHeader({ title, sub, right, icon }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div className="flex items-start gap-2.5 min-w-0">
        {icon && <span className="mt-0.5 text-fg-mute">{icon}</span>}
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold text-fg leading-tight">{title}</h3>
          {sub && <p className="text-[13px] text-fg-mute mt-0.5">{sub}</p>}
        </div>
      </div>
      {right && <div className="shrink-0 flex items-center gap-2">{right}</div>}
    </div>
  )
}

export function PageHeader({ title, sub, crumbs, actions }: { title: ReactNode; sub?: ReactNode; crumbs?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 animate-in">
      <div className="min-w-0">
        {crumbs && <div className="text-[12.5px] text-fg-mute mb-1.5 flex items-center gap-1.5">{crumbs}</div>}
        <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-fg">{title}</h1>
        {sub && <p className="text-[14px] text-fg-mute mt-1 max-w-3xl">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

type Tone = 'crit' | 'warn' | 'ok' | 'info' | 'ai' | 'brand' | 'neutral'
const TONE: Record<Tone, string> = {
  crit: 'bg-crit-50 text-crit-700 ring-crit-100',
  warn: 'bg-warn-50 text-warn-700 ring-warn-100',
  ok: 'bg-ok-50 text-ok-700 ring-ok-100',
  info: 'bg-info-50 text-info-700 ring-info-100',
  ai: 'bg-ai-50 text-ai-700 ring-ai-100',
  brand: 'bg-brand-50 text-brand-700 ring-brand-100',
  neutral: 'bg-canvas text-fg-soft ring-border',
}
const DOT: Record<Tone, string> = { crit: 'bg-crit', warn: 'bg-warn', ok: 'bg-ok', info: 'bg-info', ai: 'bg-ai', brand: 'bg-brand', neutral: 'bg-fg-faint' }

export function Badge({ tone = 'neutral', children, dot, className }: { tone?: Tone; children: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[12px] font-medium ring-1 ring-inset whitespace-nowrap', TONE[tone], className)}>
      {dot && <span className={cx('h-1.5 w-1.5 rounded-full', DOT[tone])} />}{children}
    </span>
  )
}

export const STATUS: Record<Status, { label: string; tone: Tone }> = {
  red: { label: 'Needs attention', tone: 'crit' },
  amber: { label: 'Watch', tone: 'warn' },
  green: { label: 'Normal', tone: 'ok' },
  rolled_up: { label: 'Rolled up', tone: 'neutral' },
}
export const StatusBadge = ({ s }: { s: Status }) => <Badge tone={STATUS[s].tone} dot>{STATUS[s].label}</Badge>

export function Button({ children, onClick, variant = 'primary', size = 'md', disabled, type = 'button', icon, className }: {
  children?: ReactNode; onClick?: () => void; variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'brand'; size?: 'sm' | 'md'
  disabled?: boolean; type?: 'button' | 'submit'; icon?: ReactNode; className?: string
}) {
  const v = {
    primary: 'bg-fg text-white hover:bg-fg-soft shadow-xs',
    brand: 'bg-brand text-white hover:bg-brand-700 shadow-xs',
    secondary: 'bg-surface text-fg-soft border border-border-strong hover:bg-canvas shadow-xs',
    ghost: 'text-fg-soft hover:bg-canvas',
    danger: 'bg-surface text-crit-700 border border-crit-100 hover:bg-crit-50',
  }[variant]
  const s = size === 'sm' ? 'h-8 px-3 text-[13px]' : 'h-9 px-3.5 text-[13.5px]'
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={cx('inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:shadow-ring', v, s, className)}>
      {icon}{children}
    </button>
  )
}

export function Stat({ label, value, delta, sub, tone, icon }: { label: string; value: ReactNode; delta?: ReactNode; sub?: ReactNode; tone?: 'crit' | 'ok' | 'brand' | 'warn'; icon?: ReactNode }) {
  const c = tone === 'crit' ? 'text-crit-700' : tone === 'ok' ? 'text-ok-700' : tone === 'brand' ? 'text-brand-700' : tone === 'warn' ? 'text-warn-700' : 'text-fg'
  return (
    <Card className="!p-4">
      <div className="flex items-center justify-between"><span className="label">{label}</span>{icon && <span className="text-fg-faint">{icon}</span>}</div>
      <div className={cx('mt-2 text-[26px] font-semibold tracking-[-0.02em] tnum leading-none', c)}>{value}</div>
      <div className="mt-2 flex items-center gap-2 text-[12.5px] text-fg-mute">{delta}{sub}</div>
    </Card>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode; count?: number }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="border-b border-border flex gap-5 overflow-x-auto scroll-thin">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={cx('relative pb-2.5 pt-1 text-[13.5px] font-medium whitespace-nowrap transition-colors', value === t.id ? 'text-fg' : 'text-fg-mute hover:text-fg-soft')}>
          {t.label}{t.count != null && <span className="ml-1.5 rounded-full bg-canvas px-1.5 text-[11px] text-fg-mute ring-1 ring-border">{t.count}</span>}
          {value === t.id && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />}
        </button>
      ))}
    </div>
  )
}

export function Segmented<T extends string>({ options, value, onChange }: { options: { id: T; label: ReactNode }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="inline-flex rounded-lg bg-canvas p-0.5 ring-1 ring-border">
      {options.map((o) => (
        <button key={o.id} onClick={() => onChange(o.id)}
          className={cx('rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors', value === o.id ? 'bg-surface text-fg shadow-xs' : 'text-fg-mute hover:text-fg-soft')}>{o.label}</button>
      ))}
    </div>
  )
}

/** Every number can explain itself: a small "i" that opens the method in plain language. */
export function Method({ children, title = 'How this is computed' }: { children: ReactNode; title?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close)
  }, [])
  return (
    <span ref={ref} className="relative inline-flex">
      <button type="button" aria-label={title} onClick={(e) => { e.stopPropagation(); setOpen((o) => !o) }}
        className="inline-flex items-center gap-1 text-[12px] font-medium text-fg-mute hover:text-brand-700"><Info size={14} /> Method</button>
      {open && (
        <span onClick={(e) => e.stopPropagation()} className="absolute right-0 top-7 z-40 w-[380px] max-w-[85vw] rounded-xl border border-border bg-surface p-4 text-[13px] leading-relaxed text-fg-soft shadow-pop animate-in block text-left">
          <span className="flex items-center justify-between mb-1.5"><b className="text-fg text-[13px]">{title}</b><button onClick={() => setOpen(false)} className="text-fg-faint hover:text-fg"><X size={14} /></button></span>
          {children}
        </span>
      )}
    </span>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('rounded-lg bg-gradient-to-r from-canvas via-border/60 to-canvas bg-[length:200%_100%] animate-pulse2', className)} />
}

export function PageSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-8 w-80" />
      <div className="grid grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[104px]" />)}</div>
      <Skeleton className="h-72" />
    </div>
  )
}

export function ErrorState({ error }: { error: string }) {
  return <Card className="border-crit-100 bg-crit-50/40 text-crit-700 text-[13.5px]">Could not load: {error}. Is the API running on port 8000?</Card>
}

export function Empty({ icon, title, sub, action }: { icon?: ReactNode; title: string; sub?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center text-center py-12 px-6">
      {icon && <div className="h-11 w-11 rounded-xl bg-canvas ring-1 ring-border flex items-center justify-center text-fg-mute mb-3">{icon}</div>}
      <div className="font-semibold text-fg">{title}</div>
      {sub && <p className="text-[13px] text-fg-mute mt-1 max-w-md">{sub}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Drawer({ open, onClose, title, children, width = 560 }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: number }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    if (open) document.addEventListener('keydown', k)
    return () => document.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-fg/25 animate-in" onClick={onClose} />
      <aside className="absolute right-0 top-0 h-full bg-surface shadow-pop flex flex-col animate-slide" style={{ width: `min(${width}px, 100vw)` }}>
        <div className="flex items-center justify-between border-b border-border px-5 h-14 shrink-0">
          <div className="font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-md p-1.5 text-fg-mute hover:bg-canvas"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto scroll-thin p-5">{children}</div>
      </aside>
    </div>
  )
}

export function Provenance({ kind }: { kind: 'computed' | 'model' | 'person' | 'synthetic' | 'retrieved' }) {
  const m = {
    computed: { t: 'Computed', tone: 'brand' as Tone },
    model: { t: 'AI-written · checked', tone: 'ai' as Tone },
    person: { t: 'Needs a decision', tone: 'warn' as Tone },
    synthetic: { t: 'Synthetic data', tone: 'neutral' as Tone },
    retrieved: { t: 'Quoted from source', tone: 'info' as Tone },
  }[kind]
  return <Badge tone={m.tone}>{m.t}</Badge>
}
