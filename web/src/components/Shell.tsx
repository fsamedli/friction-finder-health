import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell, BookOpenCheck, Building2, CalendarClock, ChevronDown, ClipboardList, Database, LayoutDashboard, LineChart,
  Menu, Network, RotateCcw, ShieldCheck, Sparkles, TrendingUp, Users, X,
} from 'lucide-react'
import { api, type Board, type Plan } from '../lib/api'
import { longDate } from '../lib/format'
import { DETECT, PERSONA, REVIEW, useStore, visiblePlans, type Role } from '../lib/store'
import { cx } from './ui'
import DemoGuide, { StartDemo, useDemo } from './DemoGuide'
import StudyBar, { studyOn } from './Study'

/** The v1 mark, refined: an ink tile, a teal ring (computed) with a gap, and a rust dot (the decision). */
export function Logo({ className = 'h-7 w-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#1B3A4B" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" fill="none" stroke="#2F5468" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="#12A594" strokeWidth="3" strokeLinecap="round" strokeDasharray="40 14" transform="rotate(-40 16 16)" />
      <circle cx="23.5" cy="10.5" r="2.7" fill="#E0703E" />
    </svg>
  )
}

const NAV: { to: string; label: string; icon: ReactNode; end?: boolean; group?: string }[] = [
  { to: '/', label: 'Today', icon: <LayoutDashboard size={17} />, end: true },
  { to: '/teams', label: 'Teams', icon: <Users size={17} /> },
  { to: '/plans', label: 'Action plans', icon: <ClipboardList size={17} /> },
  { to: '/impact', label: 'Impact', icon: <TrendingUp size={17} /> },
  { to: '/insights', label: 'Insights', icon: <Network size={17} /> },
  { to: '/ask', label: 'Ask', icon: <Sparkles size={17} /> },
  { to: '/data', label: 'Data sources', icon: <Database size={17} />, group: 'Workspace' },
  { to: '/value', label: 'Business case', icon: <LineChart size={17} />, group: 'Workspace' },
  { to: '/trust', label: 'Trust & method', icon: <ShieldCheck size={17} />, group: 'Workspace' },
]

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const loc = useLocation()
  const isActive = (to: string, end?: boolean) => (end ? loc.pathname === to : loc.pathname.startsWith(to))
  return (
    <div className="flex h-full flex-col bg-side text-side-fg">
      <div className="flex items-center gap-2.5 px-4 h-16 border-b border-side-line">
        <Logo />
        <div className="leading-tight">
          <div className="text-[15px] font-semibold text-white tracking-tight">Friction Finder</div>
          <div className="text-[11px] text-side-mute">Engagement × operations</div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {NAV.map((n, i) => {
          const header = n.group && n.group !== NAV[i - 1]?.group ? n.group : null
          const on = isActive(n.to, n.end)
          return (
            <div key={n.to}>
              {header && <div className="px-2.5 pt-5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-side-mute">{header}</div>}
              <NavLink to={n.to} end={n.end} onClick={onNavigate}
                className={cx('flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium transition-colors', on ? 'bg-side-active text-white' : 'text-side-fg hover:bg-side-hover hover:text-white')}>
                <span className={on ? 'text-brand-500' : 'text-side-mute'}>{n.icon}</span>{n.label}
              </NavLink>
            </div>
          )
        })}
      </nav>
      <div className="m-3 rounded-xl border border-side-line bg-side-hover/60 p-3 text-[12px] text-side-mute">
        <div className="flex items-center gap-1.5 text-side-fg font-medium"><BookOpenCheck size={14} /> Demo workspace</div>
        <p className="mt-1 leading-snug">Northline Logistics is fictional. All data is synthetic.</p>
        <ul className="mt-2.5 space-y-1.5">
          <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-brand-500" />Teal: computed by code</li>
          <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-act" />Rust: needs your decision</li>
          <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-ai" />Purple: written by AI, checked</li>
        </ul>
      </div>
    </div>
  )
}

function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close() }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [open, close])
  return ref
}

function Dropdown({ trigger, children, align = 'right', width = 300 }: { trigger: (open: boolean) => ReactNode; children: (close: () => void) => ReactNode; align?: 'left' | 'right'; width?: number }) {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const ref = useOutside(open, close)
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} className="focus:outline-none">{trigger(open)}</button>
      {open && (
        <div className={cx('absolute top-11 z-40 rounded-xl border border-border bg-surface shadow-pop animate-in', align === 'right' ? 'right-0' : 'left-0')} style={{ width: `min(${width}px, calc(100vw - 24px))` }}>
          {children(close)}
        </div>
      )}
    </div>
  )
}

function Notifications() {
  const { asOf, siteId } = useStore()
  const nav = useNavigate()
  const [items, setItems] = useState<{ tone: 'crit' | 'warn' | 'brand'; title: string; sub: string; to: string }[]>([])
  useEffect(() => {
    let live = true
    Promise.all([api.board(siteId, asOf), api.plans()]).then(async ([b, all]: [Board, Plan[]]) => {
      const plans = visiblePlans(all, asOf)
      const results = await Promise.all(plans.map((p) => api.result(p.id, asOf)))
      if (!live) return
      const out: typeof items = []
      b.teams.filter((t) => t.status === 'red').forEach((t) => out.push({ tone: 'crit', title: `${t.team_name}: operations and engagement both moved`, sub: `${b.site} · ${t.signal}`, to: `/teams/${t.team_id}` }))
      b.teams.filter((t) => t.status === 'amber').slice(0, 2).forEach((t) => out.push({ tone: 'warn', title: `${t.team_name}: watch`, sub: `${b.site} · ${t.signal}`, to: `/teams/${t.team_id}` }))
      plans.forEach((p, i) => {
        const r = results[i]
        if (r.status === 'ok') out.push({ tone: 'brand', title: `Review ready: ${p.team_label}`, sub: `${r.kpi_label}: ${r.verdict}`, to: `/impact/${p.id}` })
        else if (r.status === 'not_reached') out.push({ tone: 'brand', title: `Plan in progress: ${p.team_label}`, sub: `Review in ${r.days_to_go} days`, to: `/impact/${p.id}` })
      })
      setItems(out)
    }).catch(() => setItems([]))
    return () => { live = false }
  }, [asOf, siteId])
  const dot = { crit: 'bg-crit', warn: 'bg-warn', brand: 'bg-brand' }
  return (
    <Dropdown width={360} trigger={() => (
      <span className="relative flex h-9 w-9 items-center justify-center rounded-lg text-fg-mute hover:bg-canvas hover:text-fg">
        <Bell size={18} />
        {items.length > 0 && <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-crit px-1 text-[10px] font-semibold text-white">{items.length}</span>}
      </span>
    )}>
      {(close) => (
        <div>
          <div className="px-4 py-3 border-b border-border font-semibold text-[13.5px]">Notifications</div>
          {items.length === 0 ? <div className="px-4 py-6 text-[13px] text-fg-mute">Nothing needs attention.</div> : (
            <ul className="max-h-80 overflow-y-auto scroll-thin">
              {items.map((i, k) => (
                <li key={k}>
                  <button onClick={() => { nav(i.to); close() }} className="flex w-full gap-3 px-4 py-3 text-left hover:bg-canvas">
                    <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', dot[i.tone])} />
                    <span><span className="block text-[13px] font-medium text-fg">{i.title}</span><span className="block text-[12px] text-fg-mute">{i.sub}</span></span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Dropdown>
  )
}

function DemoClock() {
  const { asOf, setAsOf } = useStore()
  const opts = [{ v: DETECT, t: 'Sept 15, 2026', s: 'Wave 2 survey results arrive' }, { v: REVIEW, t: 'Nov 30, 2026', s: 'Night A plan review date' }]
  return (
    <Dropdown width={300} trigger={(open) => (
      <span className={cx('flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px] font-medium', open ? 'border-brand ring-4 ring-brand/10' : 'border-border-strong hover:bg-canvas')}>
        <CalendarClock size={15} className="text-brand-700" />
        <span className="hidden sm:inline text-fg-mute">As of</span> {longDate(asOf).replace(', 2026', '')}
        <ChevronDown size={14} className="text-fg-faint" />
      </span>
    )}>
      {(close) => (
        <div className="p-1.5">
          <div className="px-2.5 pt-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-faint">Demo clock</div>
          {opts.map((o) => (
            <button key={o.v} onClick={() => { setAsOf(o.v); close() }}
              className={cx('flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-canvas', asOf === o.v && 'bg-brand-50')}>
              <span className={cx('mt-1.5 h-2 w-2 rounded-full', asOf === o.v ? 'bg-brand' : 'bg-border-strong')} />
              <span><span className="block text-[13px] font-medium">{o.t}</span><span className="block text-[12px] text-fg-mute">{o.s}</span></span>
            </button>
          ))}
          <p className="px-2.5 py-2 text-[11.5px] text-fg-mute border-t border-border mt-1">Moves the whole workspace in time. Follow-up months after Sept are synthetic.</p>
        </div>
      )}
    </Dropdown>
  )
}

function UserMenu() {
  const { role, setRole, setSiteId } = useStore()
  const p = PERSONA[role]
  const pick = (r: Role) => { setRole(r); if (r === 'manager') setSiteId(1) }
  return (
    <Dropdown width={280} trigger={() => (
      <span className="flex items-center gap-2 rounded-lg p-1 sm:pr-2 hover:bg-canvas">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-[12px] font-semibold text-brand-900">{p.initials}</span>
        <span className="hidden md:block text-left leading-tight"><span className="block text-[13px] font-medium">{p.name}</span><span className="block text-[11.5px] text-fg-mute">{role === 'manager' ? 'Site manager' : 'People analytics'}</span></span>
        <ChevronDown size={14} className="hidden sm:block text-fg-faint" />
      </span>
    )}>
      {(close) => (
        <div className="p-1.5">
          <div className="px-2.5 pt-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-faint">View as</div>
          {(['manager', 'hr'] as Role[]).map((r) => (
            <button key={r} onClick={() => { pick(r); close() }} className={cx('flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-canvas', role === r && 'bg-brand-50')}>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-canvas ring-1 ring-border text-[11px] font-semibold">{PERSONA[r].initials}</span>
              <span><span className="block text-[13px] font-medium">{PERSONA[r].name}</span><span className="block text-[11.5px] text-fg-mute">{PERSONA[r].title}</span></span>
            </button>
          ))}
          <p className="px-2.5 py-2 text-[11.5px] text-fg-mute border-t border-border mt-1">The user is the site manager; the buyer is the people-analytics or operations leader.</p>
          <button onClick={async () => { await api.resetDemo(); close(); window.location.assign('/') }}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[12.5px] text-fg-mute hover:bg-canvas hover:text-fg">
            <RotateCcw size={14} /> Reset demo (remove plans approved in the app, restore unit costs)
          </button>
        </div>
      )}
    </Dropdown>
  )
}

function Topbar({ onMenu, onDemo }: { onMenu: () => void; onDemo: () => void }) {
  const { meta, siteId, setSiteId, role } = useStore()
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-2 sm:gap-3 border-b border-border bg-surface px-4 lg:px-6">
      <button onClick={onMenu} className="lg:hidden rounded-lg p-1.5 sm:p-2 text-fg-mute hover:bg-canvas" aria-label="Open menu"><Menu size={20} /></button>
      <div className="hidden sm:flex items-center gap-2 text-[13px]">
        <span className="flex items-center gap-1.5 rounded-lg bg-canvas px-2.5 py-1.5 font-medium ring-1 ring-border"><Building2 size={14} className="text-fg-mute" />Northline Logistics</span>
        <span className="text-fg-faint">/</span>
      </div>
      <select value={siteId} onChange={(e) => setSiteId(Number(e.target.value))} disabled={role === 'manager'}
        title={role === 'manager' ? 'A site manager sees their own site' : 'Choose a site'}
        className="h-9 min-w-0 max-w-[132px] sm:max-w-none rounded-lg border border-border-strong bg-surface px-2 sm:px-2.5 text-[13px] font-medium disabled:bg-canvas disabled:text-fg-soft focus:outline-none focus:ring-4 focus:ring-brand/10">
        {(meta?.sites ?? [{ site_id: 1, site_name: 'Richmond' }]).map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name} DC</option>)}
      </select>
      <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
        <StartDemo onStart={onDemo} />
        <DemoClock />
        <Notifications />
        <div className="hidden sm:block h-6 w-px bg-border mx-1" />
        <UserMenu />
      </div>
    </header>
  )
}

export default function Shell() {
  const [menu, setMenu] = useState(false)
  const loc = useLocation()
  const { asOf, siteId, role, setAsOf, setSiteId, setRole } = useStore()
  const demo = useDemo()
  const nav = useNavigate()
  const startDemo = () => { setRole('manager'); setSiteId(1); setAsOf(DETECT); nav('/'); demo.set(0) }
  useEffect(() => { window.scrollTo(0, 0) }, [loc.pathname])  // the mobile menu closes itself via onNavigate
  return (
    <div className="min-h-full lg:pl-[248px]">
      <aside className="hidden lg:block fixed inset-y-0 left-0 w-[248px]"><Sidebar /></aside>
      {menu && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-fg/40" onClick={() => setMenu(false)} />
          <div className="absolute inset-y-0 left-0 w-[264px] animate-in">
            <Sidebar onNavigate={() => setMenu(false)} />
            <button onClick={() => setMenu(false)} className="absolute right-3 top-4 text-side-mute" aria-label="Close menu"><X size={18} /></button>
          </div>
        </div>
      )}
      <Topbar onMenu={() => setMenu(true)} onDemo={startDemo} />
      <main key={loc.pathname + asOf + siteId + role} className="mx-auto max-w-[1360px] px-4 py-6 lg:px-8 lg:py-8">
        <Outlet />
      </main>
      <DemoGuide step={demo.step} set={demo.set} />
      {studyOn() && <StudyBar />}
    </div>
  )
}
