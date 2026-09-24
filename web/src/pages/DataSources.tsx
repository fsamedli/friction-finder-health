import { useRef, useState } from 'react'
import { CircleDashed, Download, FileSpreadsheet, Lock, Upload } from 'lucide-react'
import { api } from '../lib/api'
import { longDate, num } from '../lib/format'
import { useLoad } from '../lib/store'
import { Badge, Button, Card, CardHeader, ErrorState, PageHeader, PageSkeleton } from '../components/ui'

const TEMPLATE = 'date,site_id,shift,hour_band,departures,late_departures,rework_count\n2026-09-11,1,Night,06-07,24,4,1\n'

export default function DataSources() {
  const src = useLoad(() => api.sources(), [])
  const file = useRef<HTMLInputElement>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  if (src.error) return <ErrorState error={src.error} />
  if (!src.data) return <PageSkeleton />
  const upload = async (f: File) => {
    setBusy(true); setMsg(null)
    try { const r = await api.upload(f); setMsg({ ok: true, text: `${num(r.rows_added)} rows added to Dispatch / WMS for this session.` }); src.setData(await api.sources()) }
    catch (e) { setMsg({ ok: false, text: String((e as Error).message) }) } finally { setBusy(false) }
  }
  const templateHref = URL.createObjectURL(new Blob([TEMPLATE], { type: 'text/csv' }))
  return (
    <div>
      <PageHeader title="Data sources" sub="The client owns both halves: the survey export and its own operating records. In this demo every source is a synthetic CSV; nothing is connected to a live system. In a deployment, Friction Finder runs on the client's side and operating data never goes to Gallup."
        actions={<Badge tone="info" dot>{src.data.filter((s) => s.status === 'demo_csv').length} sources · synthetic demo files</Badge>} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 stagger">
        {src.data.map((s) => (
          <Card key={s.id}>
            <div className="flex items-start justify-between gap-3">
              <div><div className="font-semibold">{s.name}</div><div className="text-[12.5px] text-fg-mute">{s.vendor}</div></div>
              {s.status === 'demo_csv' ? <Badge tone="info"><FileSpreadsheet size={12} /> Demo CSV (synthetic)</Badge> : <Badge tone="neutral"><CircleDashed size={12} /> Not connected</Badge>}
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-y-2 text-[12.5px]">
              <dt className="text-fg-mute">Data owner</dt><dd className="text-right">{s.owner}</dd>
              <dt className="text-fg-mute">Method</dt><dd className="text-right">{s.method}</dd>
              <dt className="text-fg-mute">Records</dt><dd className="text-right tnum font-medium">{s.rows ? num(s.rows) : '—'}</dd>
              <dt className="text-fg-mute">Latest data</dt><dd className="text-right">{s.last ? longDate(s.last) : '—'}</dd>
            </dl>
            <p className="mt-3 border-t border-border pt-3 text-[12px] text-fg-mute">{s.detail}</p>
          </Card>
        ))}
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="Upload operating records" sub="A site can start with a CSV export — no integration project. Uploaded rows are used by the Ask flow in this session." />
          <div className="rounded-xl border-2 border-dashed border-border-strong bg-canvas/50 px-6 py-8 text-center">
            <Upload size={22} className="mx-auto text-fg-mute" />
            <p className="mt-2 text-[13.5px]">Dispatch records by date, shift and hour band</p>
            <div className="mt-4 flex justify-center gap-2">
              <Button variant="brand" disabled={busy} onClick={() => file.current?.click()}>{busy ? 'Uploading…' : 'Choose CSV'}</Button>
              <a href={templateHref} download="ops_template.csv"><Button variant="secondary" icon={<Download size={15} />}>Template</Button></a>
            </div>
            <input ref={file} type="file" accept=".csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = '' }} />
          </div>
          {msg && <p className={`mt-3 text-[13px] ${msg.ok ? 'text-ok-700' : 'text-crit-700'}`}>{msg.text}</p>}
        </Card>
        <Card>
          <CardHeader title="Privacy rules" sub="Enforced in the database and in code, before any AI call" icon={<Lock size={16} />} />
          <ul className="space-y-3 text-[13px]">
            <li className="flex justify-between gap-4"><span className="text-fg-soft">Minimum respondents per team-wave</span><b>4</b></li>
            <li className="flex justify-between gap-4"><span className="text-fg-soft">Teams under 4 people</span><b>Site totals only</b></li>
            <li className="flex justify-between gap-4"><span className="text-fg-soft">Individual survey answers shown</span><b>Never</b></li>
            <li className="flex justify-between gap-4"><span className="text-fg-soft">Comments from small teams</span><b>Not indexed</b></li>
            <li className="flex justify-between gap-4"><span className="text-fg-soft">Manager scorecards</span><b>None — ranks obstacles, not people</b></li>
          </ul>
          <p className="mt-4 text-[11.5px] text-fg-faint">The threshold follows Gallup's reporting minimum. It cannot be lowered from the app.</p>
        </Card>
      </div>
    </div>
  )
}
