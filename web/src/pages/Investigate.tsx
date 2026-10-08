import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowRight, ClipboardPlus, FileText, Lock, MessageSquareQuote, Sparkles, UserRound } from 'lucide-react'
import { api, KPI_ORDER, type AskResult, type EvidenceState, type Investigation, type Kpi, type Plan, type Why } from '../lib/api'
import { longDate, money, monthRange, num, per10, pval, signed } from '../lib/format'
import { KPI_SHORT } from '../lib/labels'
import { DETECT, useLoad, useMedia, useStore, visiblePlans } from '../lib/store'
import { QUESTION, useInv } from '../lib/inv'
import { ItemChanges, LinkScatter, QuartileBars, TrendChart } from '../components/charts'
import { Cites, SpecChart, SpecTable } from '../components/InvParts'
import PlanEditor, { type DraftSeed, seedFromDraft } from '../components/PlanEditor'
import Journey from '../components/Journey'
import InvestigationPanel from '../components/InvestigationPanel'
import Useful from '../components/Useful'
import {
  Badge, Button, Card, CardHeader, Details, Empty, ErrorState, EvidenceChip, Loading, Method, PageHeader, PageSkeleton, Provenance,
  Segmented, Stat, StateNote, StatusBadge, cx,
} from '../components/ui'

const Q = [
  { id: 'real', label: 'Is it real?' },
  { id: 'normal', label: 'Is this normal for teams like ours?' },
  { id: 'explain', label: 'What explains it?' },
  { id: 'missing', label: 'What is missing?' },
  { id: 'act', label: 'What do I do?' },
] as const

function conclusion(w: Why) {
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const drops = w.item_changes.filter((c) => c.delta <= -0.3).slice(0, 2)
  if (!flagged.length && !w.engagement?.biggest_drop?.significant) return 'Operations and engagement are within the range comparable teams would predict.'
  const parts: string[] = []
  if (flagged.length) { const e = w.excess![flagged[0]]!; parts.push(`${KPI_SHORT[flagged[0]].toLowerCase()} ran ${(e.observed / Math.max(1, e.expected)).toFixed(1)}× what comparable teams predict (${num(e.observed)} vs ${num(e.expected)})`) }
  else parts.push('operating KPIs stayed within normal range')
  if (drops.length) parts.push(`${drops.map((d) => `“${d.label}”`).join(' and ')} fell`)
  const out = parts.join(', while ') + '.'
  return out.charAt(0).toUpperCase() + out.slice(1)
}

/** One manager question: one sentence and one evidence state first, the chart or table under it, method one click down. */
function Block({ id, q, sentence, state, children, details }: { id: string; q: string; sentence: ReactNode; state?: EvidenceState | null; children?: ReactNode; details?: ReactNode }) {
  return (
    <section id={id} data-anchor aria-labelledby={`${id}-q`} className="rounded-2xl border border-border bg-surface p-5 sm:p-6 shadow-card">
      <div id={`${id}-q`} className="eyebrow">{q}</div>
      <div className="mt-1.5 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <p className="min-w-0 flex-1 text-[16px] font-semibold leading-snug text-fg">{sentence}</p>
        {state && <EvidenceChip state={state} />}
      </div>
      {children && <div className="mt-5">{children}</div>}
      {details && <div className="mt-4">{details}</div>}
    </section>
  )
}

function InvFailure({ inv, what }: { inv: { error: string | null; unavailable: boolean }; what: string }) {
  if (inv.unavailable) return <StateNote kind="unavailable" title={`${what} is unavailable on this server`}>The investigation service did not answer, so this check was not run. Everything else on this screen still works.</StateNote>
  if (inv.error) return <StateNote kind="fallback" title={`${what} could not be loaded`}>{inv.error}</StateNote>
  return null
}

function AnswerBody({ inv }: { inv: Investigation }) {
  const a = inv.answer
  if (inv.status !== 'answered' || !a) return <StateNote kind="insufficient" title={inv.message ?? 'No answer'} />
  return (
    <div className="space-y-4">
      {a.chart && <SpecChart spec={a.chart} />}
      {a.table && <SpecTable spec={a.table} />}
      {a.evidence_ids.length > 0 && <p className="text-[12px] text-fg-mute">Evidence: <Cites ids={a.evidence_ids} register={inv.evidence} /></p>}
      {a.competing && (
        <div className="rounded-lg bg-canvas px-3 py-2.5 text-[13px]">
          <div className="flex flex-wrap items-center gap-2"><span className="label">Competing explanation</span><EvidenceChip state={a.competing.evidence_state} /></div>
          <p className="mt-1 text-fg-soft">{a.competing.text} <Cites ids={a.competing.evidence_ids} register={inv.evidence} /></p>
        </div>
      )}
      {a.next_step && a.next_step.kind === 'gather' && (
        <p className="text-[13px] text-fg-soft"><b className="text-fg">To find out:</b> {a.next_step.text} <span className="text-fg-mute">· {a.next_step.owner}</span></p>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ Is it real?
function RealBlock({ w, ev }: { w: Why; ev: AskResult | null }) {
  const [k, setK] = useState<Kpi>(KPI_ORDER.find((x) => w.excess?.[x]?.flagged) ?? 'late_doses')
  const e = w.excess?.[k]
  const flagged = KPI_ORDER.filter((x) => w.excess?.[x]?.flagged)
  const f = flagged[0] ? w.excess![flagged[0]] : undefined
  const drop = w.engagement?.biggest_drop
  const marks = [{ m: '2026-03', label: 'Wave 1' }, { m: '2026-09', label: 'Wave 2' }].filter((x) => w.kpi_trend.some((d) => d.month === x.m))
  const state: EvidenceState = flagged.length && drop?.significant ? 'supported' : flagged.length || drop?.significant ? 'mixed' : 'insufficient'
  const mix = ev?.evidence.find((x) => x.kind === 'tenure_mix' || x.kind === 'signal_check')
  return (
    <Block id="real" q="Is it real?" state={state} sentence={conclusion(w)}
      details={<Details summary="Method: how 'beyond normal variation' is decided">
        <div className="space-y-2 text-[12.5px] text-fg-soft">
          {KPI_ORDER.map((x) => { const v = w.excess?.[x]; return v ? <p key={x}><b className="text-fg">{KPI_SHORT[x]}</b>: {num(v.observed)} observed vs {num(v.expected, 1)} expected · {v.judgeable ? `${pval(v.p)} (flagged below p = 0.01)` : 'too rare to judge (fewer than 3 expected)'}</p> : null })}
          {drop && <p>Largest survey change, adjusted for who responded: {signed(drop.delta)} pts ({pval(drop.p)}; must be below 0.0042 after choosing the worst of 12 items).</p>}
          <p>Comparable teams: the same shift at every hospital, 4 or more people, excluding this team. Expected = their pooled rate × this team's head-months. Poisson upper tail.</p>
        </div>
      </Details>}>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-5">
        <Stat label={f ? `${KPI_SHORT[flagged[0]]} · 3 months` : 'Operating KPIs'} value={f ? <>{num(f.observed)}<span className="text-[16px] text-fg-faint"> vs {num(f.expected)}</span></> : 'Normal'} tone={f ? 'crit' : 'ok'} sub={f ? 'expected from comparable teams' : 'within normal variation'} />
        <Stat label="Excess operating cost" value={money(w.excess_cost ?? 0)} tone={(w.excess_cost ?? 0) > 0 ? 'crit' : undefined} sub="last 3 months · unit costs editable" />
        <Stat label="Largest survey change" value={drop ? `${signed(drop.delta)}` : '—'} tone={drop?.significant ? 'crit' : undefined} sub={drop ? <span className="line-clamp-2">{drop.label}</span> : 'hidden: small wave'} />
        <Stat label="Respondents" value={`${w.engagement?.n_w1 ?? '—'} → ${w.engagement?.n_w2 ?? '—'}`} sub="wave 1 → wave 2 · minimum 4" />
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.45fr_1fr]">
        <div className="min-w-0">
          <CardHeader title="Operating KPIs" sub="Per 10 people per month · this team vs comparable teams" right={<Provenance kind="computed" />} />
          <Segmented value={k} onChange={setK} options={KPI_ORDER.map((x) => ({ id: x, label: <span className={w.excess?.[x]?.flagged ? 'text-crit-700' : ''}>{KPI_SHORT[x]}</span> }))} />
          <div className="mt-3"><TrendChart data={w.kpi_trend} k={k} window={w.window} marks={marks} teamLabel={w.team.team_name} /></div>
          <p className="mt-1 text-[11.5px] text-fg-mute">Unit: events per 10 people per month · period: {monthRange(w.kpi_trend.map((d) => String(d.month)))} · baseline: comparable teams' pooled rate (dashed)</p>
          {e && <p className="mt-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px] text-fg-soft">
            {monthRange(w.window ?? [])}: <b className="text-fg">{num(e.observed)}</b> observed vs <b className="text-fg">{num(e.expected, 1)}</b> expected
            {e.judgeable ? <> — {e.flagged ? <b className="text-crit-700">beyond normal variation{e.dollars > 0 ? `, ${money(e.dollars)}` : ''}</b> : 'within normal variation'}</> : ' — too rare to judge in three months'}.
          </p>}
        </div>
        <div className="min-w-0">
          <CardHeader title="Survey change, wave 1 → wave 2" sub={`Points on a 5-point scale · n = ${w.engagement?.n_w1} → ${w.engagement?.n_w2} respondents`} right={<Provenance kind="computed" />} />
          {w.item_changes.length ? <ItemChanges items={w.item_changes} /> : <StateNote kind="suppressed" title="Item changes hidden">{w.reason ?? ''}</StateNote>}
          {mix && <p className="mt-3 rounded-lg bg-canvas px-3 py-2.5 text-[12.5px] text-fg-soft"><b className="text-fg">Is the drop real?</b> {mix.statement}</p>}
        </div>
      </div>
    </Block>
  )
}

// ------------------------------------------------------------------ Is this normal?
function NormalBlock({ w, asOf }: { w: Why; asOf: string }) {
  const inv = useInv('normal', QUESTION.normal!(w.team.team_name), { team_id: w.team.team_id, site_id: w.team.site_id, as_of: asOf })
  const a = inv.data?.answer
  return (
    <Block id="normal" q="Is this normal for teams like ours?" state={a?.evidence_state ?? (inv.unavailable ? 'unavailable' : null)}
      sentence={a?.conclusion ?? (inv.data?.message ?? (inv.unavailable || inv.error ? 'The comparison with teams like this one could not be run here.' : 'Comparing with teams like this one…'))}
      details={<Details summary="What “teams like ours” means here">
        <p className="text-[12.5px] text-fg-soft">The internal norm uses the teams on the same shift at the other hospitals and at this one, with 4 or more people. An external Gallup benchmark is an assumed data source: it is not in this prototype, and the answer says “unavailable” rather than guess.</p>
      </Details>}>
      {inv.data ? <AnswerBody inv={inv.data} /> : inv.unavailable || inv.error ? <InvFailure inv={inv} what="The comparison with teams like ours" /> : <Loading label="Comparing with teams like this one" />}
    </Block>
  )
}

// ------------------------------------------------------------------ What explains it?
function useEvidence(w: Why) {
  const [r, setR] = useState<AskResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (!w.team.site) return
    let live = true
    api.ask(`Why did the ${w.team.site} ${w.team.team_name} team's scores drop?`, true).then((x) => { if (live) setR(x) }).catch((e) => { if (live) setErr(String(e.message)) })
    return () => { live = false }
  }, [w.team.site, w.team.team_name])
  return { r, err }
}

function Drivers({ w }: { w: Why }) {
  const { meta } = useStore()
  const flagged = KPI_ORDER.filter((k) => w.excess?.[k]?.flagged)
  const best = [...w.links].filter((l) => l.verdict === 'association' && (!flagged.length || flagged.includes(l.kpi))).sort((a, b) => (a.p ?? 1) - (b.p ?? 1))[0]
  const firstDrop = w.item_changes.find((c) => c.delta <= -0.3)?.item ?? 'grand'
  const [sel, setSel] = useState<{ kpi: Kpi; item: string }>(best ? { kpi: best.kpi, item: best.item } : { kpi: flagged[0] ?? 'late_doses', item: firstDrop })
  const one = useLoad(() => api.link(sel.kpi, sel.item), [sel.kpi, sel.item])
  const a = one.data?.association, q = one.data?.quartile
  const itemLabel = sel.item === 'grand' ? 'Overall engagement' : `${sel.item.toUpperCase()} · ${meta?.items[sel.item] ?? ''}`
  return (
    <div className="space-y-5">
      <div>
        <CardHeader title="Is this bigger than one team?" sub="The same comparison across every reportable team-wave at Lanford Health: does this engagement item move with this KPI?"
          right={<Badge tone="neutral">Association, not cause</Badge>} />
        <div className="flex flex-wrap gap-2">
          {w.links.map((l) => (
            <button key={l.kpi + l.item} onClick={() => setSel({ kpi: l.kpi, item: l.item })}
              className={cx('rounded-lg border px-2.5 py-1.5 text-[12.5px]', sel.kpi === l.kpi && sel.item === l.item ? 'border-brand bg-brand-50 text-brand-900' : 'border-border hover:bg-canvas')}>
              {l.item === 'grand' ? 'Overall' : l.item.toUpperCase()} × {KPI_SHORT[l.kpi]} · <span className={l.verdict === 'association' ? 'text-brand-700 font-medium' : 'text-fg-mute'}>{l.verdict === 'association' ? 'linked' : l.verdict === 'too rare to test' ? 'too rare' : 'no link'}</span>
            </button>
          ))}
        </div>
      </div>
      {one.error && <ErrorState error={one.error} />}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="min-w-0 rounded-xl border border-border p-4">
          <CardHeader title={`${KPI_SHORT[sel.kpi]} vs ${itemLabel}`} sub={`Each dot is one team in one survey wave · ${a?.n_cells ?? '…'} team-waves`} right={<span className="text-[12px] text-fg-mute"><span className="text-crit">◆</span> {w.team.team_name}</span>} />
          {!a ? <Loading /> : a.verdict === 'too rare to test' ? <Empty title="Too rare to test" sub="Most team-quarters have zero events. Needs a year or more of history." />
            : <LinkScatter a={a} teamId={w.team.team_id} xLabel={`${sel.item === 'grand' ? 'Overall engagement' : sel.item.toUpperCase()} (mean, 1–5)`} yLabel="per 10 people / month" />}
          {a?.slope != null && (
            <p className="mt-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px] text-fg-soft">
              <b className="text-fg">{a.verdict === 'association' ? 'Linked.' : 'No link detected.'}</b> Each 1-point lower score goes with {per10(Math.abs(a.slope))} {a.slope < 0 ? 'more' : 'fewer'} {KPI_SHORT[sel.kpi].toLowerCase()} per 10 people a month
              {' '}(95% CI {signed(a.ci_low! * 10, 1)} to {signed(a.ci_high! * 10, 1)}; {a.n_teams} teams). <Method>OLS of each team-wave's KPI rate (the quarter the survey closed in) on the item mean, standard errors clustered by team because each team appears twice. Team-waves under 4 respondents are excluded. With 24 teams this detects strong links only.</Method>
            </p>
          )}
        </div>
        <div className="min-w-0 rounded-xl border border-border p-4">
          <CardHeader title="Top vs bottom quartile" sub={`Median ${KPI_SHORT[sel.kpi].toLowerCase()} per 10 people a month, by ${sel.item === 'grand' ? 'overall engagement' : sel.item.toUpperCase()} quartile — the comparison Gallup's own research uses`} />
          {q ? <QuartileBars q={q} /> : <Loading />}
          {q?.pct_diff != null && <p className="mt-2 text-[13px] text-fg-soft">Top-quartile team-waves have <b className="text-fg">{num(Math.abs(q.pct_diff))}% {q.pct_diff >= 0 ? 'fewer' : 'more'}</b> {KPI_SHORT[sel.kpi].toLowerCase()} than bottom-quartile ones ({q.n_per_quartile} per quartile).</p>}
        </div>
      </div>
    </div>
  )
}

function ExplainBlock({ w, asOf, ev }: { w: Why; asOf: string; ev: { r: AskResult | null; err: string | null } }) {
  const inv = useInv('why_flagged', QUESTION.why_flagged!(w.team.team_name), { team_id: w.team.team_id, site_id: w.team.site_id, as_of: asOf })
  const a = inv.data?.answer
  const r = ev.r
  const themes = r?.evidence.find((e) => e.kind === 'comment_themes')
  const comments = r?.evidence.filter((e) => e.kind === 'comment') ?? []
  const owner = r?.evidence.find((e) => e.kind === 'owner')
  const ops = r?.evidence.find((e) => e.kind === 'ops_hour')
  const staffing = r?.evidence.find((e) => e.kind === 'staffing')
  const quote = (s: string) => s.match(/"(.+)"/)?.[1] ?? s
  const meta = (s: string) => s.match(/\(([^)]*wave \d[^)]*)\)/)?.[1] ?? ''
  return (
    <Block id="explain" q="What explains it?" state={a?.evidence_state ?? null}
      sentence={a?.conclusion ?? r?.assessment?.label ?? (ev.err ? 'The explanation could not be loaded.' : 'Checking the explanations…')}>
      <div className="space-y-6">
        {inv.data && a?.hypotheses && a.hypotheses.length > 0 && (
          <div>
            <div className="label mb-2">Possible explanations, ranked</div>
            <ol className="space-y-2">
              {a.hypotheses.map((h, i) => (
                <li key={h.id} className="rounded-lg border border-border px-3.5 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="flex items-center gap-2 font-medium text-[14px]"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-canvas text-[11px] text-fg-mute ring-1 ring-border">{i + 1}</span>{h.label}</span>
                    <EvidenceChip state={h.evidence_state} />
                  </div>
                  <p className="mt-1 text-[13px] text-fg-soft">{h.text} <Cites ids={h.evidence_ids} register={inv.data!.evidence} /></p>
                </li>
              ))}
            </ol>
          </div>
        )}
        {inv.data && !a?.hypotheses?.length && <AnswerBody inv={inv.data} />}
        {!inv.data && (inv.unavailable || inv.error) && <InvFailure inv={inv} what="The ranked explanations" />}
        {!inv.data && !inv.unavailable && !inv.error && <Loading label="Ranking the explanations" />}

        {ev.err && <ErrorState error={ev.err} />}
        {r && (
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.2fr_1fr]">
            <div className="min-w-0 rounded-xl border border-border p-4">
              <CardHeader title={r.assessment?.label ?? r.message} sub="Verdict computed by rules from survey, operating records and comments" right={<><Provenance kind="computed" /><Badge tone="neutral">rules mode · {r.seconds.toFixed(1)} s</Badge></>} />
              <ul className="space-y-2 text-[13.5px]">
                {(r.assessment?.reasons ?? []).map((x) => <li key={x} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 rounded-full bg-brand shrink-0" /><span className="text-fg-soft">{x}</span></li>)}
              </ul>
              <div className="mt-4 border-t border-border pt-3 text-[13px]"><div className="label mb-1">Operating detail</div><p className="text-fg-soft">{ops?.statement ?? '—'}</p>{staffing && <p className="text-fg-soft mt-2">{staffing.statement}</p>}</div>
              {owner && <div className="mt-4 flex items-center gap-3 rounded-lg bg-canvas px-3 py-2.5 text-[13px]"><UserRound size={16} className="text-fg-mute" /><span>{owner.statement}</span></div>}
            </div>
            <div className="min-w-0 rounded-xl border border-border p-4">
              <CardHeader title="What staff wrote" sub={themes?.statement} icon={<MessageSquareQuote size={16} />} right={<Provenance kind="retrieved" />} />
              <ul className="space-y-3">
                {comments.map((c) => (
                  <li key={c.id} className="rounded-lg border border-border p-3">
                    <p className="text-[13.5px] text-fg">“{quote(c.statement)}”</p>
                    <p className="mt-1 text-[11.5px] text-fg-mute">{meta(c.statement)}</p>
                  </li>
                ))}
                {comments.length === 0 && <Empty title="No comments retrieved" />}
              </ul>
            </div>
          </div>
        )}
        {!r && !ev.err && <Loading label="Reading the evidence" />}
        <Drivers w={w} />
      </div>
    </Block>
  )
}

// ------------------------------------------------------------------ What is missing?
function MissingBlock({ w, asOf }: { w: Why; asOf: string }) {
  const inv = useInv('whats_missing', QUESTION.whats_missing!(w.team.team_name), { team_id: w.team.team_id, site_id: w.team.site_id, as_of: asOf })
  const a = inv.data?.answer
  return (
    <Block id="missing" q="What is missing?" state={a?.evidence_state ?? (inv.unavailable ? 'unavailable' : null)}
      sentence={a?.conclusion ?? (inv.data?.message ?? (inv.unavailable || inv.error ? 'The list of gaps could not be produced here.' : 'Listing what the data cannot tell us…'))}>
      {inv.data ? (
        <div className="space-y-3">
          {a?.gaps && a.gaps.length > 0 ? (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {a.gaps.map((g, i) => (
                <li key={i} className="grid grid-cols-1 gap-1 px-4 py-3 text-[13px] md:grid-cols-[1.2fr_1.4fr_auto] md:gap-4">
                  <span className="font-medium text-fg">{g.gap}</span>
                  <span className="text-fg-soft">{g.step}</span>
                  <span className="text-fg-mute md:text-right">{g.owner}</span>
                </li>
              ))}
            </ul>
          ) : <AnswerBody inv={inv.data} />}
          {a?.evidence_ids && a.evidence_ids.length > 0 && <p className="text-[12px] text-fg-mute">Evidence: <Cites ids={a.evidence_ids} register={inv.data.evidence} /></p>}
        </div>
      ) : inv.unavailable || inv.error ? <InvFailure inv={inv} what="The list of gaps" /> : <Loading label="Listing the gaps" />}
    </Block>
  )
}

// ------------------------------------------------------------------ What do I do?
function deriveSeed(w: Why, ev: AskResult | null): DraftSeed {
  const kpi: Kpi = KPI_ORDER.find((k) => w.excess?.[k]?.flagged) ?? 'late_doses'
  const dropped = w.item_changes.filter((c) => c.delta <= -0.3)
  const linked = w.links.filter((l) => l.kpi === kpi && l.verdict === 'association').sort((a, b) => (a.p ?? 1) - (b.p ?? 1))
  const drop = dropped.find((c) => linked.some((l) => l.item === c.item)) ?? dropped[0]
  const owner = ev?.evidence.find((e) => e.kind === 'owner')?.statement.match(/: (.+?) \(/)?.[1] ?? 'Owner needed'
  const theme = ev?.assessment?.label.match(/: ([^.]+)\./)?.[1] ?? drop?.label.toLowerCase() ?? 'the obstacle behind the drop'
  const start = '2026-09-21'
  const add = (n: number) => { const x = new Date(start + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }
  return {
    team_id: w.team.team_id, team_label: `${w.team.site} ${w.team.team_name}`, kpi, item: drop?.item ?? 'grand',
    focus: drop ? `${drop.label} (${drop.item})` : 'Overall engagement', obstacle: theme.charAt(0).toUpperCase() + theme.slice(1), start, owner,
    measure: `${KPI_SHORT[kpi]} per 10 people a month`,
    success: `${KPI_SHORT[kpi]} back inside the range of comparable teams by the review date`,
    actions: [
      { text: `Fix the ${theme} step the comments describe, and write the new routine down`, owner, due: add(7) },
      { text: `Ask the unit in the next huddle what gets in the way of “${drop?.label ?? 'doing the work right'}”`, owner: `${w.team.team_name} nurse manager`, due: add(14) },
      { text: 'Ten-minute check-in every other Monday: did the actions happen, did they help?', owner: `${w.team.team_name} nurse manager`, due: add(21) },
    ],
  }
}

function ActBlock({ w, ev, existing, onSaved, asOf }: { w: Why; ev: AskResult | null; existing?: Plan; onSaved: (p: Plan) => void; asOf: string }) {
  const nav = useNavigate()
  const inv = useInv('draft_plan', QUESTION.draft_plan!(w.team.team_name), { team_id: w.team.team_id, site_id: w.team.site_id, as_of: asOf })
  const draft = inv.data?.answer?.plan_draft
  const waiting = !existing && !draft && !inv.unavailable && !inv.error && !inv.data
  const seed = useMemo(() => (draft ? seedFromDraft(draft, inv.data?.id) : deriveSeed(w, ev)), [draft, inv.data?.id, w, ev])
  if (existing) {
    return (
      <Block id="act" q="What do I do?" sentence={<>A plan is approved: {existing.obstacle}</>}>
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.5fr_1fr]">
          <div className="min-w-0 rounded-xl border border-border p-4">
            <CardHeader title={existing.obstacle} sub={`Focus item: ${existing.focus} · KPI to watch: ${KPI_SHORT[existing.kpi]}`} right={<Badge tone="ok" dot>Approved</Badge>} />
            {(existing.owner || existing.measure || existing.success) && (
              <dl className="mb-3 grid grid-cols-1 gap-2 text-[12.5px] sm:grid-cols-3">
                {existing.owner && <div><dt className="label">Owner</dt><dd className="text-fg-soft">{existing.owner}</dd></div>}
                {existing.measure && <div><dt className="label">Operational measure</dt><dd className="text-fg-soft">{existing.measure}</dd></div>}
                {existing.success && <div><dt className="label">Success criterion</dt><dd className="text-fg-soft">{existing.success}</dd></div>}
              </dl>
            )}
            <ol className="divide-y divide-border rounded-lg border border-border">
              {existing.actions.map((a, i) => (
                <li key={i} className="flex gap-3 p-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-[12px] font-semibold text-brand-700">{i + 1}</span>
                  <div><div className="text-[13.5px] font-medium">{a.text}</div><div className="text-[12px] text-fg-mute">{a.owner} · due {longDate(a.due)}</div></div>
                </li>
              ))}
            </ol>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => nav(`/review/${existing.id}`)} icon={<ArrowRight size={15} />}>See if the plan worked</Button>
              <a href={`/api/report/${existing.id}`} target="_blank" rel="noreferrer"><Button variant="secondary" icon={<FileText size={15} />}>One-page report</Button></a>
            </div>
            <div className="mt-4 border-t border-border pt-3"><Useful target="plan" id={existing.id} /></div>
          </div>
          <div className="min-w-0 rounded-xl border border-border p-4">
            <CardHeader title="Review date" sub={`Plan starts ${longDate(existing.start)}`} />
            <div className="text-[26px] font-semibold tracking-tight">{longDate(existing.review)}</div>
            <p className="text-[13px] text-fg-mute mt-1">On this date the {KPI_SHORT[existing.kpi].toLowerCase()} before and after the plan are compared with similar teams that did not act.</p>
            <div className="mt-4 label">Every other Monday, ten minutes</div>
            <ul className="mt-1.5 space-y-1 text-[13px] text-fg-soft"><li>Did we complete the actions?</li><li>Did completing them make a difference?</li><li>What do we keep, change, or stop?</li></ul>
            <p className="mt-2 text-[11.5px] text-fg-faint">Check-in questions follow Gallup's State of the Team handout.</p>
          </div>
        </div>
      </Block>
    )
  }
  return (
    <Block id="act" q="What do I do?" sentence={draft ? <>Draft one plan from the evidence; you edit it and approve it.</> : <>Draft one plan from this team's evidence; you edit it and approve it.</>}>
      {inv.data && draft && <p className="mb-3 text-[12px] text-fg-mute">Prefilled by the plan drafter (code, rules mode). Evidence: <Cites ids={draft.evidence_ids} register={inv.data.evidence} /></p>}
      {(inv.unavailable || inv.error) && <div className="mb-3"><StateNote kind="fallback" title="Prefilled from this screen's evidence">The plan drafter did not answer, so the draft below is built from the numbers on this screen.</StateNote></div>}
      {waiting ? <Loading label="Drafting the plan" /> : <PlanEditor key={draft ? `draft-${inv.data?.id}` : ev ? 'with-evidence' : 'drafting'} seed={seed} onSaved={onSaved} />}
    </Block>
  )
}

// ------------------------------------------------------------------ page
export default function Investigate() {
  const { teamId } = useParams()
  const id = Number(teamId)
  const [sp] = useSearchParams()
  const focus = sp.get('focus')
  const { asOf, setTeamId } = useStore()
  const nav = useNavigate()
  useEffect(() => { if (id) setTeamId(id) }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  const why = useLoad(() => api.why(id, asOf), [id, asOf])
  const detect = useLoad(() => api.why(id, DETECT), [id])
  const plans = useLoad(() => api.plans(), [id])
  const ev = useEvidence(detect.data ?? ({ team: { site: '', team_name: '' } } as Why))
  const existing = useMemo(() => (plans.data ? visiblePlans(plans.data, asOf) : []).filter((p) => p.team_id === id).slice(-1)[0], [plans.data, id, asOf])
  const ready = !!why.data && !!detect.data
  const wide = useMedia('(min-width: 1280px)')
  const panelCtx = useMemo(() => ({ site_id: why.data?.team.site_id ?? null, team_id: id, as_of: asOf }), [why.data?.team.site_id, id, asOf])
  useEffect(() => {
    if (!ready || !focus) return
    const t = setTimeout(() => document.getElementById(focus)?.scrollIntoView({ block: 'start' }), 150)
    return () => clearTimeout(t)
  }, [ready, focus])
  if (why.error) return <ErrorState error={why.error} onRetry={() => window.location.reload()} />
  if (!why.data || !detect.data) return <PageSkeleton />
  const w = why.data
  const crumbs = <><button onClick={() => nav('/investigate')} className="hover:text-fg">Investigate</button><span>/</span><span>{w.team.site} {w.team.team_name}</span></>
  if (w.suppressed) {
    return (
      <div>
        <PageHeader crumbs={crumbs} title={`${w.team.site} ${w.team.team_name}`} sub={`${w.team.shift} shift · ${w.team.headcount} people`} />
        <Card><Empty icon={<Lock size={20} />} title="Too small to report on its own" sub={`Fewer than 4 people. Survey answers and operating counts are included in the ${w.team.site} hospital totals only, so no one on this team can be identified. Gallup's reporting threshold is 4.`}
          action={<Button variant="secondary" onClick={() => nav('/investigate')}>Back to the team list</Button>} /></Card>
      </div>
    )
  }
  return (
    <div>
      <PageHeader crumbs={crumbs}
        title={<span className="flex flex-wrap items-center gap-3">{w.team.site} {w.team.team_name} {w.status && <StatusBadge s={w.status} />}</span>}
        sub={<>{w.team.shift} shift · {w.team.headcount} people · {monthRange(w.window ?? [])}</>}
        actions={existing
          ? <Button variant="primary" onClick={() => nav(`/review/${existing.id}`)} icon={<ArrowRight size={15} />}>See if the plan worked</Button>
          : <Button variant="decide" onClick={() => document.getElementById('act')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} icon={<ClipboardPlus size={15} />}>Draft a plan</Button>} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0">
          <nav aria-label="Questions on this page" className="sticky top-16 z-20 -mx-4 mb-5 border-b border-border bg-canvas/90 px-4 py-2 backdrop-blur lg:-mx-8 lg:px-8 xl:mx-0 xl:rounded-xl xl:border xl:px-2">
            <ul className="flex gap-2 overflow-x-auto scroll-thin">
              {Q.map((q) => <li key={q.id} className="shrink-0"><a href={`#${q.id}`} className={cx('inline-block rounded-full px-3 py-1 text-[12.5px] font-medium ring-1 ring-border hover:bg-surface', focus === q.id ? 'bg-surface text-fg' : 'text-fg-soft')}>{q.label}</a></li>)}
              {!wide && <li className="shrink-0"><a href="#ask" className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12.5px] font-medium text-ai-700 ring-1 ring-ai-100 hover:bg-surface"><Sparkles size={12} /> Ask</a></li>}
            </ul>
          </nav>
          <div className="space-y-6">
            <RealBlock w={w} ev={ev.r} />
            <NormalBlock w={detect.data} asOf={asOf} />
            <ExplainBlock w={detect.data} asOf={asOf} ev={ev} />
            <MissingBlock w={detect.data} asOf={asOf} />
            <ActBlock w={detect.data} ev={ev.r} existing={existing} asOf={asOf} onSaved={(p) => { plans.setData([...(plans.data ?? []), p]) }} />
            {!wide && <div id="ask" data-anchor><InvestigationPanel initial={panelCtx} /></div>}
            <Journey at={existing ? 'act' : 'explain'} teamId={w.team.team_id} planId={existing?.id} />
          </div>
        </div>
        {wide && (
          <aside aria-label="Investigation panel" className="min-w-0">
            <div className="sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto scroll-thin pb-4"><InvestigationPanel initial={panelCtx} /></div>
          </aside>
        )}
      </div>
    </div>
  )
}
