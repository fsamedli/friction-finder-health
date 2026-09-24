import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type Meta } from './api'

export const DETECT = '2026-09-15'
export const REVIEW = '2026-11-30'
export const SEED_PLAN = 'plan-richmond-night-a'

interface Ctx {
  meta: Meta | null
  siteId: number; setSiteId: (n: number) => void
  asOf: string; setAsOf: (d: string) => void
  teamId: number; setTeamId: (n: number) => void
}
const C = createContext<Ctx | null>(null)

const read = (k: string, d: string) => { try { return localStorage.getItem(k) ?? d } catch { return d } }
const write = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } }

export function StoreProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [siteId, setSite] = useState(Number(read('ff.site', '1')))
  const [asOf, setAs] = useState(read('ff.asof', DETECT))
  const [teamId, setTeam] = useState(Number(read('ff.team', '4')))
  useEffect(() => { api.meta().then(setMeta).catch(() => setMeta(null)) }, [])
  return (
    <C.Provider value={{
      meta,
      siteId, setSiteId: (n) => { setSite(n); write('ff.site', String(n)) },
      asOf, setAsOf: (d) => { setAs(d); write('ff.asof', d) },
      teamId, setTeamId: (n) => { setTeam(n); write('ff.team', String(n)) },
    }}>{children}</C.Provider>
  )
}

export const useStore = () => {
  const c = useContext(C)
  if (!c) throw new Error('StoreProvider missing')
  return c
}

/** Fetch helper: re-runs when deps change; exposes loading and error. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let live = true
    setLoading(true); setError(null)
    fn().then((d) => { if (live) setData(d) }).catch((e) => { if (live) setError(String(e.message ?? e)) }).finally(() => { if (live) setLoading(false) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, error, loading, setData }
}
