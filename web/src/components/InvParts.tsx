import { useState } from 'react'
import { Code2, X } from 'lucide-react'
import type { ChartSpec, InvEvidence, TableSpec, TraceStep } from '../lib/api'
import { Badge, Provenance, cx } from './ui'

const fmt = (v: unknown) => (typeof v === 'number' ? (Number.isInteger(v) ? v.toLocaleString('en-US') : v.toLocaleString('en-US', { maximumFractionDigits: 2 })) : v == null ? '—' : String(v))

/** Renders a chart the API describes (ChartSpec). Every value comes from the tool rows in the response. */
export function SpecChart({ spec }: { spec: ChartSpec }) {
  const caption = <p className="mt-2 text-[11.5px] text-fg-mute">{spec.unit} · {spec.period}{spec.baseline ? ` · baseline: ${spec.baseline}` : ''}</p>
  const vals = spec.rows.flatMap((r) => spec.series.map((s) => Number(r[s.key]))).filter((v) => Number.isFinite(v))
  const max = Math.max(1e-9, ...vals.map(Math.abs))
  const color = (role: string, hot: boolean) => (role === 'team' || hot ? 'bg-crit' : role === 'comparison' ? 'bg-fg-faint' : 'bg-brand-500')
  if (spec.type === 'range') {
    // one row per entity: the comparison range as a band, the team as a marker
    const lo = Math.min(...vals), hi = Math.max(...vals)
    const pos = (v: number) => `${((v - lo) / Math.max(1e-9, hi - lo)) * 100}%`
    return (
      <figure>
        <figcaption className="text-[13px] font-medium text-fg">{spec.title}</figcaption>
        <ul className="mt-3 space-y-2" role="img" aria-label={`${spec.title}: ${spec.rows.map((r) => `${r[spec.x]} ${spec.series.map((s) => fmt(r[s.key])).join(' ')}`).join('; ')}`}>
          {spec.rows.map((r, i) => {
            const hot = spec.highlight != null && String(r[spec.x]) === String(spec.highlight)
            return (
              <li key={i} className="grid grid-cols-[minmax(0,140px)_1fr_auto] items-center gap-3 text-[12.5px]">
                <span className={cx('truncate', hot ? 'font-semibold text-fg' : 'text-fg-soft')} title={String(r[spec.x])}>{String(r[spec.x])}</span>
                <span className="relative h-3 rounded-full bg-canvas">
                  {spec.series.map((s) => Number.isFinite(Number(r[s.key])) && <span key={s.key} className={cx('absolute top-0.5 h-2 w-2 -translate-x-1/2 rounded-full', color(s.role, hot))} style={{ left: pos(Number(r[s.key])) }} />)}
                </span>
                <span className="tnum text-fg-mute">{spec.series.map((s) => fmt(r[s.key])).join(' · ')}</span>
              </li>
            )
          })}
        </ul>
        {caption}
      </figure>
    )
  }
  // bars (and a compact fallback for 'line'): one row per x value, one bar per series
  return (
    <figure>
      <figcaption className="text-[13px] font-medium text-fg">{spec.title}</figcaption>
      <div className="mt-2 flex flex-wrap gap-3 text-[11.5px] text-fg-mute">
        {spec.series.map((s) => <span key={s.key} className="flex items-center gap-1.5"><span className={cx('h-2 w-3 rounded-sm', color(s.role, false))} />{s.label}</span>)}
      </div>
      <div className="mt-2 space-y-1.5" role="img" aria-label={`${spec.title}, ${spec.unit}: ${spec.rows.map((r) => `${r[spec.x]} ${spec.series.map((s) => `${s.label} ${fmt(r[s.key])}`).join(', ')}`).join('; ')}`}>
        {spec.rows.map((r, i) => {
          const hot = spec.highlight != null && String(r[spec.x]) === String(spec.highlight)
          return (
            <div key={i} className="grid grid-cols-[minmax(0,120px)_1fr] items-center gap-3 text-[12.5px]">
              <span className={cx('truncate', hot ? 'font-semibold text-fg' : 'text-fg-soft')} title={String(r[spec.x])}>{String(r[spec.x])}</span>
              <span className="space-y-0.5">
                {spec.series.map((s) => {
                  const v = Number(r[s.key])
                  return (
                    <span key={s.key} className="flex items-center gap-2">
                      <span className="h-2.5 flex-1 rounded-sm bg-canvas"><span className={cx('block h-2.5 rounded-sm', color(s.role, hot && s.role !== 'comparison'))} style={{ width: Number.isFinite(v) ? `${(Math.abs(v) / max) * 100}%` : '0%' }} /></span>
                      <span className="w-14 text-right tnum text-fg-mute">{fmt(r[s.key])}</span>
                    </span>
                  )
                })}
              </span>
            </div>
          )
        })}
      </div>
      {caption}
    </figure>
  )
}

export function SpecTable({ spec }: { spec: TableSpec }) {
  return (
    <figure className="min-w-0">
      <div className="overflow-x-auto scroll-thin">
        <table className="w-full text-[12.5px]">
          <caption className="caption-top pb-1.5 text-left text-[12px] text-fg-mute">{spec.caption}</caption>
          <thead><tr className="border-b border-border text-left text-[11.5px] text-fg-mute">{spec.columns.map((c) => <th key={c.key} className="py-1.5 pr-3 font-medium whitespace-nowrap">{c.label}{c.unit ? <span className="text-fg-faint"> ({c.unit})</span> : null}</th>)}</tr></thead>
          <tbody>{spec.rows.map((r, i) => <tr key={i} className="border-b border-border last:border-0">{spec.columns.map((c) => <td key={c.key} className="py-1.5 pr-3 tnum text-fg-soft">{fmt(r[c.key])}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </figure>
  )
}

/** A citation: opens the passage, or the SQL and rows behind a number. */
export function Cite({ id, register }: { id: string; register: InvEvidence[] }) {
  const [open, setOpen] = useState(false)
  const e = register.find((x) => x.id === id)
  return (
    <span className="relative inline-flex">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={`Evidence ${id}${e ? '' : ' (not in the register)'}`}
        className={cx('rounded px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-inset', e ? 'bg-canvas text-fg-soft ring-border hover:bg-surface hover:text-fg' : 'bg-crit-50 text-crit-700 ring-crit-100')}>{id}</button>
      {open && (
        <span className="fixed inset-x-3 bottom-3 z-50 block max-h-[70vh] overflow-y-auto rounded-xl border border-border bg-surface p-4 text-left text-[12.5px] shadow-pop sm:absolute sm:inset-x-auto sm:bottom-auto sm:left-0 sm:top-7 sm:w-[440px] scroll-thin">
          <span className="mb-2 flex items-center justify-between gap-2">
            <span className="flex items-center gap-2"><b className="font-mono text-[12px]">{id}</b>{e && <Provenance kind={e.origin === 'retrieved' ? 'retrieved' : 'computed'} />}{e?.stale && <Badge tone="warn">from an earlier context</Badge>}</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="text-fg-faint hover:text-fg"><X size={14} /></button>
          </span>
          {e ? <EvidenceBody e={e} /> : <span className="text-crit-700">This citation is not in the evidence register.</span>}
        </span>
      )}
    </span>
  )
}

export function EvidenceBody({ e }: { e: InvEvidence }) {
  const [sql, setSql] = useState(false)
  const cols = e.rows.length ? Object.keys(e.rows[0]).slice(0, 8) : []
  return (
    <span className="block">
      <span className="block text-fg-soft">{e.statement}</span>
      <span className="mt-1 block text-[11px] text-fg-faint">{e.tool ? `tool: ${e.tool}` : ''}{e.source ? ` · source: ${e.source}` : ''}{e.turn ? ` · turn ${e.turn}` : ''}</span>
      {(e.sql || e.rows.length > 0) && (
        <button type="button" onClick={() => setSql((o) => !o)} className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-fg-mute hover:text-fg"><Code2 size={13} />{sql ? 'Hide SQL and rows' : 'Show SQL and rows'}</button>
      )}
      {sql && (
        <span className="mt-2 block space-y-2">
          {e.sql && <pre className="overflow-x-auto rounded-lg bg-side p-3 font-mono text-[11px] leading-relaxed text-side-fg scroll-thin">{e.sql}</pre>}
          {e.rows.length > 0 && (
            <span className="block overflow-x-auto scroll-thin">
              <table className="text-[11px]">
                <thead><tr>{cols.map((c) => <th key={c} className="pr-3 text-left font-medium text-fg-mute">{c}</th>)}</tr></thead>
                <tbody>{e.rows.slice(0, 12).map((r, i) => <tr key={i}>{cols.map((c) => <td key={c} className="pr-3 tnum text-fg-soft">{fmt(r[c])}</td>)}</tr>)}</tbody>
              </table>
              {e.rows.length > 12 && <span className="text-[11px] text-fg-faint">{e.rows.length - 12} more rows</span>}
            </span>
          )}
        </span>
      )}
    </span>
  )
}

export function Cites({ ids, register }: { ids: string[]; register: InvEvidence[] }) {
  if (!ids?.length) return null
  return <span className="inline-flex flex-wrap items-center gap-1 align-middle">{ids.map((id) => <Cite key={id} id={id} register={register} />)}</span>
}

/** What the run did, in order: real steps with real seconds. */
export function TraceList({ trace }: { trace: TraceStep[] }) {
  return (
    <ol className="space-y-2">
      {trace.map((t, i) => (
        <li key={i} className="grid grid-cols-[18px_1fr_auto] gap-2.5 text-[12.5px]">
          <span className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-canvas text-[10.5px] font-medium text-fg-mute ring-1 ring-border">{i + 1}</span>
          <div className="min-w-0"><div className="font-medium text-fg">{t.step}</div>{t.detail && <div className="text-fg-mute break-words">{t.detail}</div>}</div>
          <div className="flex items-start gap-1.5 whitespace-nowrap">
            <Badge tone={t.mode === 'model' ? 'ai' : t.mode === 'code' ? 'brand' : 'neutral'}>{t.mode === 'model' ? 'AI model' : t.mode === 'code' ? 'code' : 'rules'}</Badge>
            {t.seconds != null && <span className="tnum text-[11.5px] text-fg-mute">{t.seconds.toFixed(1)} s</span>}
          </div>
        </li>
      ))}
    </ol>
  )
}
