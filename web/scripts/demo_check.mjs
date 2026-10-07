// Demo safety net: walk the whole demo path in headless Chrome at 1440 px and 390 px and fail loudly on a
// console error, a failed API call, or a missing key number or label.
// usage: node scripts/demo_check.mjs http://127.0.0.1:8010   (scripts/demo_check.sh starts that server)
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:8010'
const results = []
let failed = 0
const log = (ok, w, what) => { results.push(`${ok ? 'PASS' : 'FAIL'}  ${w}px  ${what}`); if (!ok) failed++ }

const browser = await chromium.launch({ channel: 'chrome', headless: true })
for (const width of [1440, 390]) {
  await fetch(base + '/api/demo', { method: 'DELETE' })
  const ctx = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 900 } })
  await ctx.addInitScript(() => { try { localStorage.setItem('ff.asof', '2026-09-15'); localStorage.setItem('ff.role', 'manager'); localStorage.setItem('ff.site', '1'); localStorage.removeItem('ff.demo') } catch {} })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(`page error: ${e.message}`))
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes('422')) errors.push(`console: ${m.text()}`) })
  // the one expected failure: the deliberately bad upload below must be rejected with 422
  const expected = (u, s) => u.endsWith('/api/ops-upload') && s === 422
  page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 400 && !expected(r.url(), r.status())) errors.push(`API ${r.status()} ${r.url().replace(base, '')}`) })

  const see = async (label, texts, timeout = 15000) => {
    for (const t of [].concat(texts)) {
      try { await page.getByText(t, { exact: false }).locator('visible=true').first().waitFor({ state: 'visible', timeout }); log(true, width, `${label}: "${t}"`) }
      catch { log(false, width, `${label}: missing "${t}"`) }
    }
  }
  const click = async (label, name) => {
    try { await page.getByRole('button', { name }).locator('visible=true').first().click({ timeout: 10000 }); log(true, width, `${label}: clicked ${name}`) }
    catch { log(false, width, `${label}: could not click ${name}`) }
  }
  const noOverflow = async (label) => {
    const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    log(o <= 0, width, `${label}: no horizontal scroll${o > 0 ? ` (overflow ${o}px)` : ''}`)
  }

  await page.goto(base + '/', { waitUntil: 'networkidle' })
  await see('Detect', ['Night A needs attention', 'Excess operating cost', 'Teams needing attention'])
  await see('Detect numbers', ['81', 'late departures vs', '51'])
  await noOverflow('Detect')
  await see('Context strip', ['(demo clock)', 'demo CSV, synthetic'])
  for (const [from, to] of [['/teams', '/investigate'], ['/teams/4?tab=plan', '/investigate/4'], ['/impact/plan-richmond-night-a', '/review/plan-richmond-night-a'], ['/why/4', '/investigate/4'], ['/proof/plan-richmond-night-a', '/review/plan-richmond-night-a']]) {
    await page.goto(base + from, { waitUntil: 'networkidle' })
    log(new URL(page.url()).pathname === to, width, `Redirect ${from} -> ${to}${new URL(page.url()).pathname === to ? '' : ` (got ${new URL(page.url()).pathname})`}`)
  }

  await page.goto(base + '/investigate/4', { waitUntil: 'networkidle' })
  await see('Explain', ['Richmond Night A', 'what comparable teams predict (81 vs 51)', 'Materials and equipment to do my work right', 'Survey change, wave 1'])
  await noOverflow('Explain')
  await page.goto(base + '/investigate/4?tab=drivers', { waitUntil: 'networkidle' })
  await see('Explain · drivers', ['Association, not cause', 'Top vs bottom quartile', 'Linked.'])
  await page.goto(base + '/investigate/4?tab=evidence', { waitUntil: 'networkidle' })
  await see('Explain · evidence', ['Supported hypothesis', 'What employees wrote', 'rules mode'])

  await page.goto(base + '/investigate/4?tab=plan', { waitUntil: 'networkidle' })
  await see('Act', ['Draft action plan', 'Needs your decision', 'reviewed Nov 30'])
  await click('Act', 'Approve plan')
  await see('Act · approved', ['See if the plan worked', 'Approved', 'Useful?'])
  await noOverflow('Act')
  await click('Act → Prove', 'See if the plan worked')
  await see('Prove · countdown', ['76 days', 'Fast-forward to the review date'])
  await click('Prove', 'Fast-forward to the review date')
  await see('Prove · result', ['It worked', '10.6 per 10 people a month', '95% CI', 'Synthetic data', 'Placebo check', 'inconclusive'])
  await noOverflow('Prove')

  await page.goto(base + '/value', { waitUntil: 'networkidle' })
  await see('Business case', ['$80.1K', 'Unit costs', 'Pricing hypothesis', 'Sourced'])
  await noOverflow('Business case')

  await page.goto(base + '/trust', { waitUntil: 'networkidle' })
  await see('Under the hood · quality', ['Trust & method', 'Pass rate by test pack', 'Adversarial', 'Holdout', 'Numbers checked against the evidence'])
  await click('Under the hood', 'Assumptions')
  await see('Under the hood · assumptions', ['Minimum n', 'With real data we would need'])
  await click('Under the hood', 'Architecture')
  await see('Under the hood · architecture', ['An AI-assisted workflow', 'Why these techniques', 'Farid to confirm'])
  await noOverflow('Under the hood')

  await page.goto(base + '/ask', { waitUntil: 'networkidle' })
  await page.getByPlaceholder("Why did the Richmond night shift's scores drop?").fill("Why did the Richmond Night A team's scores drop?")
  await click('Ask (rules mode)', 'Ask')
  await see('Ask (rules mode)', ['Supported hypothesis', 'numbers checked against the evidence', 'Evidence register', 'How this answer was produced', 'Useful?'], 30000)
  await noOverflow('Ask')
  // a scripted question is served as a labelled prepared answer when data/prepared/answers.json exists
  const prepared = await (await fetch(base + '/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: "Why did the Richmond night shift's scores drop and why are deliveries late?" }) })).json()
  if (prepared.prepared) {
    await page.getByRole('button', { name: "Why did the Richmond night shift's scores drop and why are deliveries late?" }).first().click()
    await see('Ask (prepared)', ['Prepared answer', 'Run live'])
  } else log(true, width, 'Ask (prepared): no prepared answers on this machine; skipped')

  // one-page report and CSV export
  const rep = await (await fetch(base + '/api/report/plan-richmond-night-a')).text()
  log(rep.includes('What we found') && rep.includes('Did it work?') && rep.includes('Directional, not causal') && rep.includes('&lt; 0.001'), width, 'One-page report: finding, plan, result, caveats')
  await page.goto(base + '/investigate', { waitUntil: 'networkidle' })
  try {
    const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 8000 }), page.getByRole('button', { name: 'CSV' }).locator('visible=true').first().click()])
    log(/^teams_Richmond_.*\.csv$/.test(dl.suggestedFilename()), width, `CSV export: ${dl.suggestedFilename()}`)
  } catch { log(false, width, 'CSV export: no download') }
  // upload: a bad file shows problems; a good file updates the board; Back to demo data restores it
  await page.goto(base + '/data', { waitUntil: 'networkidle' })
  const input = page.getByLabel('Operating records CSV')
  await input.setInputFiles({ name: 'bad.csv', mimeType: 'text/csv', buffer: Buffer.from('month,team_id\n2026-06,4\n') })
  await see('Upload · bad file', ['The file was not loaded', 'Missing columns'])
  const good = 'month,team_id,absence_days,late_departures,quits,injuries,rework\n' + [6, 7, 8].map((m) => `2026-0${m},4,8,14,0,0,4`).join('\n') + '\n'
  await input.setInputFiles({ name: 'ops.csv', mimeType: 'text/csv', buffer: Buffer.from(good) })
  await see('Upload · good file', ['3 team-months loaded', 'your uploaded operating records'])
  const b2 = await (await fetch(base + '/api/board?site_id=1&as_of=2026-09-15')).json()
  log(b2.teams.find((t) => t.team_name === 'Night A')?.status !== 'red', width, 'Upload · board updated (Night A no longer flagged with normal late departures)')
  await click('Upload', 'Back to demo data')
  await see('Upload · reset', ['Back to the demo data'])

  // usability study mode (logs go to the scratch folder of this check)
  await page.goto(base + '/?study=1', { waitUntil: 'networkidle' })
  await see('Study mode', ['Study mode'])
  await page.getByLabel('Participant id').fill('P9')
  await click('Study mode', 'Begin')
  await click('Study mode', 'Task 1')
  await see('Study mode', ['Find the team that is costing the site the most'])
  await click('Study mode', 'Done')
  await page.evaluate(() => { try { sessionStorage.clear() } catch {} })

  const uniq = [...new Set(errors)]
  log(uniq.length === 0, width, `no console errors or failed API calls${uniq.length ? ': ' + uniq.slice(0, 3).join(' | ') : ''}`)
  await ctx.close()
}
await fetch(base + '/api/demo', { method: 'DELETE' })
await browser.close()
console.log(results.join('\n'))
console.log(`\n${results.length - failed} passed, ${failed} failed`)
process.exit(failed ? 1 : 0)
