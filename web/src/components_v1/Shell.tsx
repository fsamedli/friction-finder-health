import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { DETECT, REVIEW, SEED_PLAN, useStore } from '../lib/store'
import { longDate } from '../lib/format'

const LOOP = [
  { n: '01', verb: 'Detect', q: 'Which team is costing the site?', to: () => '/' },
  { n: '02', verb: 'Explain', q: 'What moved with what?', to: (t: number) => `/why/${t}` },
  { n: '03', verb: 'Act', q: 'One plan, one owner, one date', to: (t: number) => `/plan/${t}` },
  { n: '04', verb: 'Prove', q: 'Did the number move?', to: () => `/proof/${SEED_PLAN}` },
]

function stepOf(path: string) {
  if (path.startsWith('/why')) return 1
  if (path.startsWith('/plan')) return 2
  if (path.startsWith('/proof')) return 3
  if (path === '/') return 0
  return -1
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#1B3A4B" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="#1F8FA8" strokeWidth="3" strokeDasharray="40 14" transform="rotate(-40 16 16)" />
      <circle cx="23.5" cy="10.5" r="2.6" fill="#C8553D" />
    </svg>
  )
}

export default function Shell() {
  const { meta, siteId, setSiteId, asOf, setAsOf, teamId } = useStore()
  const loc = useLocation()
  const nav = useNavigate()
  const active = stepOf(loc.pathname)

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-paper/85 backdrop-blur-md">
        <div className="mx-auto max-w-[1280px] px-4 sm:px-8">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 py-3.5">
            <NavLink to="/" className="flex items-center gap-2.5">
              <Mark />
              <div className="leading-none">
                <div className="font-serif text-[1.3rem] font-semibold tracking-tight">Friction Finder</div>
                <div className="text-[11px] text-ink-mute mt-1">{meta?.company ?? 'Northline Logistics (fictional)'} · synthetic data</div>
              </div>
            </NavLink>

            <nav className="order-3 w-full lg:order-none lg:w-auto lg:flex-1 flex items-center justify-center">
              <ol className="flex w-full lg:w-auto items-stretch rounded-full border border-line bg-paper-card p-1 shadow-card overflow-x-auto">
                {LOOP.map((s, i) => {
                  const on = i === active
                  const done = active > i
                  return (
                    <li key={s.n} className="flex items-center">
                      <button onClick={() => nav(s.to(teamId))} title={s.q}
                        className={`group flex items-center gap-2 rounded-full px-3.5 py-1.5 transition-all whitespace-nowrap ${on ? 'bg-ink text-paper' : 'hover:bg-paper-deep'}`}>
                        <span className={`num text-[12px] ${on ? 'text-teal-soft' : done ? 'text-teal' : 'text-ink-mute'}`}>{s.n}</span>
                        <span className="text-[14px] font-semibold">{s.verb}</span>
                      </button>
                      {i < LOOP.length - 1 && <span className={`mx-0.5 h-px w-4 ${done ? 'bg-teal' : 'bg-line'}`} />}
                    </li>
                  )
                })}
              </ol>
            </nav>

            <div className="flex items-center gap-3 ml-auto">
              <select value={siteId} onChange={(e) => setSiteId(Number(e.target.value))}
                className="rounded-full border border-line bg-paper-card px-3 py-1.5 text-[13.5px] font-semibold focus:outline-none focus:ring-2 focus:ring-teal/30">
                {(meta?.sites ?? [{ site_id: 1, site_name: 'Richmond' }]).map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name}</option>)}
              </select>
              <div className="flex rounded-full border border-line bg-paper-card p-0.5 text-[12.5px]" role="group" aria-label="As of date">
                {[{ v: DETECT, l: 'Sept 15', h: 'Wave 2 in' }, { v: REVIEW, l: 'Nov 30', h: 'Review date' }].map((o) => (
                  <button key={o.v} onClick={() => setAsOf(o.v)}
                    className={`rounded-full px-3 py-1 font-semibold transition-colors ${asOf === o.v ? 'bg-teal text-white' : 'text-ink-soft hover:text-ink'}`}>
                    {o.l}<span className={`hidden sm:inline font-normal ${asOf === o.v ? 'text-white/80' : 'text-ink-mute'}`}> · {o.h}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main key={loc.pathname + asOf + siteId} className="mx-auto max-w-[1280px] px-4 sm:px-8 pt-10 pb-24">
        <Outlet />
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto max-w-[1280px] px-4 sm:px-8 py-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px] text-ink-mute">
          <span>As of <b className="text-ink">{longDate(asOf)}</b></span>
          <NavLink to="/value" className={({ isActive }) => isActive ? 'text-ink font-semibold' : 'hover:text-ink'}>Business case</NavLink>
          <NavLink to="/ask" className={({ isActive }) => isActive ? 'text-ink font-semibold' : 'hover:text-ink'}>Ask a question</NavLink>
          <NavLink to="/hood" className={({ isActive }) => isActive ? 'text-ink font-semibold' : 'hover:text-ink'}>Under the hood</NavLink>
          <span className="ml-auto flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-teal" />computed by code</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-rust" />needs a person</span>
            <span>Ranks obstacles, not managers.</span>
          </span>
        </div>
      </footer>
    </div>
  )
}
