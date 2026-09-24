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
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`) })
  page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 400) errors.push(`API ${r.status()} ${r.url().replace(base, '')}`) })

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

  await page.goto(base + '/teams/4', { waitUntil: 'networkidle' })
  await see('Explain', ['Richmond Night A', 'what comparable teams predict (81 vs 51)', 'Materials and equipment to do my work right', 'Survey change, wave 1'])
  await noOverflow('Explain')
  await page.goto(base + '/teams/4?tab=drivers', { waitUntil: 'networkidle' })
  await see('Explain · drivers', ['Association, not cause', 'Top vs bottom quartile', 'Linked.'])
  await page.goto(base + '/teams/4?tab=evidence', { waitUntil: 'networkidle' })
  await see('Explain · evidence', ['Supported hypothesis', 'What employees wrote', 'rules mode'])

  await page.goto(base + '/teams/4?tab=plan', { waitUntil: 'networkidle' })
  await see('Act', ['Draft action plan', 'Needs your decision', 'reviewed Nov 30'])
  await click('Act', 'Approve plan')
  await see('Act · approved', ['See if the plan worked', 'Approved'])
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
  await see('Ask (rules mode)', ['Supported hypothesis', 'numbers checked against the evidence', 'Evidence register', 'How this answer was produced'], 30000)
  await noOverflow('Ask')
  // a scripted question is served as a labelled prepared answer when data/prepared/answers.json exists
  const prepared = await (await fetch(base + '/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: "Why did the Richmond night shift's scores drop and why are deliveries late?" }) })).json()
  if (prepared.prepared) {
    await page.getByRole('button', { name: "Why did the Richmond night shift's scores drop and why are deliveries late?" }).first().click()
    await see('Ask (prepared)', ['Prepared answer', 'Run live'])
  } else log(true, width, 'Ask (prepared): no prepared answers on this machine; skipped')

  const uniq = [...new Set(errors)]
  log(uniq.length === 0, width, `no console errors or failed API calls${uniq.length ? ': ' + uniq.slice(0, 3).join(' | ') : ''}`)
  await ctx.close()
}
await fetch(base + '/api/demo', { method: 'DELETE' })
await browser.close()
console.log(results.join('\n'))
console.log(`\n${results.length - failed} passed, ${failed} failed`)
process.exit(failed ? 1 : 0)
