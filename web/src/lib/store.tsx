import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, type ManagerFunction, type Meta, type Plan } from './api'

export const DETECT = '2026-09-15'
export const REVIEW = '2026-11-30'
export const SEED_PLAN = 'plan-lanford-med-surg-night'

/** Plans as they exist on the demo clock. The seeded Med-Surg Night plan is a fallback: it appears once the clock passes
 *  its start date, unless a plan for that team was approved live in the app (the demo path). */
export function visiblePlans(plans: Plan[], asOf: string): Plan[] {
  const live = plans.filter((p) => p.id !== SEED_PLAN && p.status === 'approved')
  return plans.filter((p) => p.status === 'approved' && (p.id !== SEED_PLAN || (asOf >= p.start && !live.some((l) => l.team_id === p.team_id))))
}

interface Ctx {
  meta: Meta | null
  siteId: number; setSiteId: (n: number) => void
  asOf: string; setAsOf: (d: string) => void
  teamId: number; setTeamId: (n: number) => void
  role: Role; setRole: (r: Role) => void
}
export type Role = 'manager' | 'hr'
export const PERSONA: Record<Role, { name: string; title: string; initials: string }> = {
  manager: { name: 'Priya Singh', title: 'Nurse Manager, Med-Surg · Lanford', initials: 'PS' },
  hr: { name: 'Jordan Ellis', title: 'Director, People Analytics · all sites', initials: 'JE' },
}
const C = createContext<Ctx | null>(null)

const read = (k: string, d: string) => { try { return localStorage.getItem(k) ?? d } catch { return d } }
const write = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } }

export function StoreProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [siteId, setSite] = useState(Number(read('ff.site', '1')))
  const [asOf, setAs] = useState(read('ff.asof', DETECT))
  const [teamId, setTeam] = useState(Number(read('ff.team', '4')))
  const [role, setRoleS] = useState<Role>((read('ff.role', 'manager') as Role))
  useEffect(() => { api.meta().then(setMeta).catch(() => setMeta(null)) }, [])
  return (
    <C.Provider value={{
      meta,
      siteId, setSiteId: (n) => { setSite(n); write('ff.site', String(n)) },
      asOf, setAsOf: (d) => { setAs(d); write('ff.asof', d) },
      teamId, setTeamId: (n) => { setTeam(n); write('ff.team', String(n)) },
      role, setRole: (r) => { setRoleS(r); write('ff.role', r) },
    }}>{children}</C.Provider>
  )
}

export const useStore = () => {
  const c = useContext(C)
  if (!c) throw new Error('StoreProvider missing')
  return c
}

/** Fetch helper: re-runs when deps change; exposes loading and error. Keeps the last data while reloading. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const key = JSON.stringify(deps)
  const fnRef = useRef(fn)
  useEffect(() => { fnRef.current = fn })
  const [st, setSt] = useState<{ key: string | null; data: T | null; error: string | null }>({ key: null, data: null, error: null })
  useEffect(() => {
    let live = true
    fnRef.current()
      .then((d) => { if (live) setSt({ key, data: d, error: null }) })
      .catch((e) => { if (live) setSt((p) => ({ key, data: p.data, error: String(e?.message ?? e) })) })
    return () => { live = false }
  }, [key])
  const setData = (d: T | null) => setSt((p) => ({ ...p, data: d }))
  return { data: st.data, error: st.error, loading: st.key !== key, setData }
}

/** The manager functions the server ships (GET /api/functions). null while loading; [] when this server has no
 *  investigation endpoints, in which case the screens show "unavailable" and never call them. Loaded once. */
let fnCache: Promise<ManagerFunction[]> | null = null
export function useFunctions(): ManagerFunction[] | null {
  const [fns, setFns] = useState<ManagerFunction[] | null>(null)
  useEffect(() => {
    fnCache ??= api.functions().then((x) => (Array.isArray(x) ? x : [])).catch(() => [])
    let live = true
    fnCache.then((x) => { if (live) setFns(x) })
    return () => { live = false }
  }, [])
  return fns
}

/** True while the media query matches (e.g. the xl breakpoint), so a component can be placed once, not twice. */
export function useMedia(query: string): boolean {
  const get = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false)
  const [m, setM] = useState(get)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const h = () => setM(mq.matches)
    mq.addEventListener('change', h); h()
    return () => mq.removeEventListener('change', h)
  }, [query])
  return m
}
