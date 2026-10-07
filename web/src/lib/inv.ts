import { api, type FunctionId, type Investigation } from './api'
import { useFunctions, useLoad } from './store'

/** Runs one manager function keyless (rules mode) for a team, for the blocks on the Investigate screen.
 *  Returns data null while loading; `unavailable` true when this server has no investigation endpoints. */
export function useInv(fn: FunctionId, question: string, ctx: { team_id: number; site_id?: number | null; as_of: string }) {
  const fns = useFunctions()
  const enabled = !!fns?.some((f) => f.id === fn)
  const r = useLoad<Investigation | null>(
    () => (enabled ? api.investigate({ question, function: fn, mode: 'rules', context: { team_id: ctx.team_id, site_id: ctx.site_id ?? null, as_of: ctx.as_of } }) : Promise.resolve(null)),
    [fn, ctx.team_id, ctx.as_of, enabled],
  )
  return { ...r, unavailable: fns !== null && !enabled, probing: fns === null }
}

export const QUESTION: Partial<Record<FunctionId, (team: string) => string>> = {
  why_flagged: (t) => `Why is ${t} flagged?`,
  normal: () => 'Is this normal for teams like ours?',
  whats_missing: () => 'What is missing, and what would change the recommendation?',
  draft_plan: () => 'Draft a plan I can review',
}
