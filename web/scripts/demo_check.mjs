// Demo safety net: walk the whole demo path in headless Chrome at 1440 px and 390 px and fail loudly on a
// console error, a failed API call, or a missing key number or label.
// usage: node scripts/demo_check.mjs http://127.0.0.1:8020   (scripts/demo_check.sh starts that server)
// v0.9-health: the planted team is team 4, "Lanford Med-Surg Night"; the headline KPI is late doses; the seeded plan is
// plan-lanford-med-surg-night. The counts asserted below (81 vs 51, 10.6, 76 days) are the v0.8 planted values the spec
// says the generator keeps under the new keys; the integrator confirms them after the first gate run.
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://127.0.0.1:8020'
const results = []
let failed = 0
const log = (ok, w, what) => { results.push(`${ok ? 'PASS' : 'FAIL'}  ${w}px  ${what}`); if (!ok) failed++ }

const browser = await chromium.launch({ channel: 'chrome', headless: true })
for (const width of [1440, 390]) {
  await fetch(base + '/api/demo', { method: 'DELETE' })
  const ctx = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 900 } })
  await ctx.addInitScript(() => { try { localStorage.setItem('ff.asof', '2026-09-15'); localStorage.setItem('ff.role', 'manager'); localStorage.setItem('ff.site', '1'); localStorage.setItem('ff.team', '4'); localStorage.removeItem('ff.demo') } catch {} })
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
  await see('Detect', ['Med-Surg Night needs attention', 'Excess operating cost', 'Teams needing attention'])
  await see('Detect numbers', ['81', 'late doses vs', '51'])
  await noOverflow('Detect')
  await see('Context strip', ['(demo clock)', 'demo CSV, synthetic'])
  for (const [from, to] of [['/teams', '/investigate'], ['/teams/4?tab=plan', '/investigate/4'], ['/impact/plan-lanford-med-surg-night', '/review/plan-lanford-med-surg-night'], ['/why/4', '/investigate/4'], ['/proof/plan-lanford-med-surg-night', '/review/plan-lanford-med-surg-night']]) {
    await page.goto(base + from, { waitUntil: 'networkidle' })
    log(new URL(page.url()).pathname === to, width, `Redirect ${from} -> ${to}${new URL(page.url()).pathname === to ? '' : ` (got ${new URL(page.url()).pathname})`}`)
  }

  await page.goto(base + '/investigate/4', { waitUntil: 'networkidle' })
  await see('Explain', ['Lanford Med-Surg Night', 'what comparable teams predict (81 vs 51)', 'Materials and equipment to do my work right', 'Show the evidence'])
  await noOverflow('Explain')
  await page.goto(base + '/investigate/4?tab=drivers', { waitUntil: 'networkidle' })
  await see('Explain · drivers', ['Association, not cause', 'Top vs bottom quartile', 'Linked.'])
  await page.goto(base + '/investigate/4?tab=evidence', { waitUntil: 'networkidle' })
  await see('Explain · evidence', ['Supported hypothesis', 'What staff wrote', 'rules mode'])

  await page.goto(base + '/investigate/4?tab=plan', { waitUntil: 'networkidle' })
  await see('Act', ['Draft action plan', 'Needs your decision', 'reviewed Nov 30'])
  await click('Act', 'Approve plan')
  await see('Act · approved', ['See if the plan worked', 'Approved', 'Useful?'])
  await noOverflow('Act')
  // ---- Oct 27 round: Execute. The approved plan is a checklist (task, responsible, due, status) with what happened at approval.
  const approvedPlans = (await (await fetch(base + '/api/plans')).json()).filter((p) => p.team_id === 4 && p.status === 'approved' && p.id !== 'plan-lanford-med-surg-night')
  const livePlan = approvedPlans[approvedPlans.length - 1]
  log(!!livePlan && livePlan.actions.every((a) => a.id && a.status === 'todo') && !!livePlan.execution && livePlan.execution.nothing_sent === true, width,
    `Execute · approval recorded owners (${livePlan?.execution?.assigned?.length ?? 0}), review ${livePlan?.execution?.review_scheduled?.date ?? '?'}, KPI watch, ${livePlan?.execution?.notices?.length ?? 0} notices, nothing sent`)
  if (livePlan) {
    const nTasks = livePlan.actions.length   // the plan drafter gives one action; a manager may add more
    await page.goto(base + '/plans/' + livePlan.id, { waitUntil: 'networkidle' })
    await see('Execute · checklist', ['Checklist', `0 of ${nTasks} done`, 'What happened when you approved', 'Owners assigned', 'Review scheduled', 'KPI watch set', 'Owner notices', 'Nothing is sent by this prototype', 'See if the plan worked', 'Approved', 'Useful?'])
    await noOverflow('Execute')
    try {
      await page.getByRole('checkbox', { name: 'Task 1 done' }).click({ timeout: 10000 })
      await page.getByText(`1 of ${nTasks} done`).first().waitFor({ state: 'visible', timeout: 10000 })
      log(true, width, `Execute · ticked task 1, progress 1 of ${nTasks}`)
    } catch { log(false, width, 'Execute · could not tick task 1') }
    const planAfter = await (await fetch(base + '/api/plans/' + livePlan.id)).json()
    log(planAfter.actions[0].status === 'done' && !!planAfter.actions[0].done_at && planAfter.progress.done === 1, width, 'Execute · tick persisted with a time')
    const repLive = await (await fetch(base + '/api/report/' + livePlan.id)).text()
    log(repLive.includes('Checklist') && repLive.includes('&#9745;') && repLive.includes('What happened when the plan was approved') && repLive.includes('Nothing is sent'), width, 'Execute · one-page report prints the checklist (ticked task) and the approval record')
    await page.goto(base + '/plans', { waitUntil: 'networkidle' })
    await see('Execute · Action plans', ['Checklist', `1 of ${nTasks} done`])
  }
  await page.goto(base + '/investigate/4?tab=plan', { waitUntil: 'networkidle' })
  await click('Act → Prove', 'See if the plan worked')
  await see('Review · countdown', ['Not ready', '76 days', 'Fast-forward to the review date'])
  await click('Prove', 'Fast-forward to the review date')
  await see('Review · result', ['Improved', '10.6 per 10 people a month', '95% CI', 'Synthetic data', 'Placebo check', 'inconclusive', 'Directional, not causal', 'two-month follow-up pulse'])
  // Oct 27 round: the money first, in full dollars, with each tier labelled (measured / projection / scenario)
  await see('Review · worth', ['What it is worth', 'Measured, this unit, per year', 'Projected, this unit, if engagement recovers', 'At hospital scale', '$228,270', 'Illustrative', 'Inputs and assumptions'])
  await noOverflow('Review')
  await page.goto(base + '/plans', { waitUntil: 'networkidle' })
  await see('Action plans', ['Due reviews', 'Missing follow-ups', 'Inconclusive outcomes', 'Operational measure', 'Success criterion', 'Approved', 'days to review'])
  await noOverflow('Action plans')
  // Oct 27 round (P14): the plan that needed revision shown next to the one that worked (Prof. Hall, Oct 21)
  await see('Action plans · revised', ['Revised', 'Superseded'])
  // every page.goto re-runs the init script, so the clock is Sept 15 again here: plan 2 is "Not ready" until the
  // in-app fast-forward, exactly as the Med-Surg Night plan was above
  await page.goto(base + '/review/plan-pine-hollow-med-surg-day-2', { waitUntil: 'networkidle' })
  await see('Review · revised plan', ['Revised plan', 'first plan', 'came back inconclusive', "See the first plan's review", 'Not ready'])
  await click('Review · revised plan', 'Fast-forward to the review date')
  await see('Review · revised plan at review', ['Improved', 'Unplanned overtime shifts', 'Measured, this unit, per year'])
  await noOverflow('Review · revised plan')
  await page.goto(base + '/review/plan-pine-hollow-med-surg-day-1', { waitUntil: 'networkidle' })
  await see('Review · first plan', ['Inconclusive', 'Superseded', 'See the revised plan'])
  await noOverflow('Review · first plan')

  await page.goto(base + '/value', { waitUntil: 'networkidle' })
  // the headline dollar figure depends on the hospital unit costs Agent A sources; labels are asserted, the figure is not
  await see('Business case', ['Voluntary turnover, per year', 'US hospitals', 'Unit costs', 'Pricing hypothesis', 'Sourced'])
  await noOverflow('Business case')

  await page.goto(base + '/trust', { waitUntil: 'networkidle' })
  await see('Under the hood · quality', ['Trust & method', 'Pass rate by test pack', 'Adversarial', 'Holdout', 'Numbers checked against the evidence'])
  await click('Under the hood', 'Assumptions')
  await see('Under the hood · assumptions', ['Minimum n', 'With real data we would need'])
  await click('Under the hood', 'Architecture')
  await see('Under the hood · architecture', ['An AI-assisted workflow', 'Why these techniques', 'Farid to confirm'])
  await noOverflow('Under the hood')

  await page.goto(base + '/ask?view=brief', { waitUntil: 'networkidle' })
  await page.getByPlaceholder("Why did the Lanford night shift's scores drop?").fill("Why did the Lanford Med-Surg Night team's scores drop?")
  await click('Ask (rules mode)', 'Ask')
  await see('Ask (rules mode)', ['Supported hypothesis', 'numbers checked against the evidence', 'Evidence register', 'How this answer was produced', 'Useful?'], 30000)
  await noOverflow('Ask')
  // a scripted question is served as a labelled prepared answer when data/prepared/answers.json exists
  const prepared = await (await fetch(base + '/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: "Why did the Lanford night shift's scores drop and why are doses late?" }) })).json()
  if (prepared.prepared) {
    await page.getByRole('button', { name: "Why did the Lanford night shift's scores drop and why are doses late?" }).first().click()
    await see('Ask (prepared)', ['Prepared answer', 'Run live'])
  } else log(true, width, 'Ask (prepared): no prepared answers on this machine; skipped')

  // one-page report and CSV export
  const rep = await (await fetch(base + '/api/report/plan-lanford-med-surg-night')).text()
  log(rep.includes('What we found') && rep.includes('Did it work?') && rep.includes('Directional, not causal') && rep.includes('&lt; 0.001'), width, 'One-page report: finding, plan, result, caveats')
  await page.goto(base + '/investigate', { waitUntil: 'networkidle' })
  try {
    const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 8000 }), page.getByRole('button', { name: 'CSV' }).locator('visible=true').first().click()])
    log(/^teams_Lanford_.*\.csv$/.test(dl.suggestedFilename()), width, `CSV export: ${dl.suggestedFilename()}`)
  } catch { log(false, width, 'CSV export: no download') }
  // upload: a bad file shows problems; a good file updates the board; Back to demo data restores it
  await page.goto(base + '/data', { waitUntil: 'networkidle' })
  const input = page.getByLabel('Operating records CSV')
  await input.setInputFiles({ name: 'bad.csv', mimeType: 'text/csv', buffer: Buffer.from('month,team_id\n2026-06,4\n') })
  await see('Upload · bad file', ['The file was not loaded', 'Missing columns'])
  const good = 'month,team_id,absence_days,late_doses,quits,injuries,overtime_shifts\n' + [6, 7, 8].map((m) => `2026-0${m},4,8,14,0,0,4`).join('\n') + '\n'
  await input.setInputFiles({ name: 'ops.csv', mimeType: 'text/csv', buffer: Buffer.from(good) })
  await see('Upload · good file', ['3 team-months loaded', 'your uploaded operating records'])
  const b2 = await (await fetch(base + '/api/board?site_id=1&as_of=2026-09-15')).json()
  log(b2.teams.find((t) => t.team_name === 'Med-Surg Night')?.status !== 'red', width, 'Upload · board updated (Med-Surg Night no longer flagged with normal late doses)')
  await click('Upload', 'Back to demo data')
  await see('Upload · reset', ['Back to the demo data'])

  // usability study mode (logs go to the scratch folder of this check)
  await page.goto(base + '/?study=1', { waitUntil: 'networkidle' })
  await see('Study mode', ['Study mode'])
  await page.getByLabel('Participant id').fill('P9')
  await click('Study mode', 'Begin')
  await click('Study mode', 'Task 1')
  await see('Study mode', ['Find the team that is costing the hospital the most'])
  await click('Study mode', 'Done')
  await page.evaluate(() => { try { sessionStorage.clear() } catch {} })

  // ---- v0.8: the investigation journey and three scripted investigations, keyless (rules mode)
  await fetch(base + '/api/demo', { method: 'DELETE' })
  const invs = []
  const onInv = async (r) => {
    if (!/\/api\/investigate(\/|$)/.test(new URL(r.url()).pathname) || r.status() >= 400) return
    try { const j = await r.json(); if (j && j.status && j.status !== 'running') invs.push(j) } catch { /* not JSON */ }
  }
  page.on('response', onInv)
  const panelOf = () => page.getByRole('region', { name: 'AI-assisted investigation' }).locator('visible=true').first()
  const askIn = async (label, question) => {
    const panel = panelOf()
    const before = await panel.getByRole('article').count()
    const n0 = invs.length
    try {
      await panel.getByLabel('Ask a question').fill(question)
      await panel.getByRole('button', { name: 'Ask', exact: true }).click()
      await panel.getByRole('article').nth(before).waitFor({ state: 'visible', timeout: 30000 })
      for (let i = 0; i < 40 && invs.length === n0; i++) await page.waitForTimeout(100)
      const inv = invs[invs.length - 1]
      const art = panel.getByRole('article').nth(before)
      const chip = await art.getByText(/^(Supported|Mixed|Insufficient|Unavailable)/).first().isVisible().catch(() => false)
      const cite = (await art.getByRole('button', { name: /^Evidence / }).count()) > 0
      const ok = inv && inv.status === 'answered' && inv.answer && inv.answer.conclusion && ['supported', 'mixed', 'insufficient', 'unavailable'].includes(inv.answer.evidence_state)
      log(!!ok, width, `${label}: answered "${question}" (${inv ? `${inv.status}, ${inv.answer?.evidence_state ?? 'no state'}, ${inv.mode}` : 'no response'})`)
      log(chip, width, `${label}: evidence state visible`)
      log(cite, width, `${label}: citation chip visible`)
      log(!!inv && inv.answer?.evidence_ids?.every((id) => inv.evidence.some((e) => e.id === id)), width, `${label}: every cited id resolves in the register`)
      log((await art.getByText('How this answer was produced').count()) > 0, width, `${label}: trace shown`)
      return inv
    } catch (e) { log(false, width, `${label}: "${question}" failed (${String(e.message).split('\n')[0]})`); return null }
  }
  const followUp = (label, first, second) => {
    log(!!first && !!second && second.conversation_id === first.conversation_id, width, `${label}: follow-up kept the conversation`)
    log(!!second && second.context?.team_id === 4 && /Med-Surg Night/.test(second.context?.team ?? ''), width, `${label}: follow-up kept the team context (${second?.context?.team ?? 'none'})`)
  }

  // the journey: Today -> Investigate -> a panel follow-up -> Draft a plan -> Approve -> reload -> Review
  await page.goto(base + '/', { waitUntil: 'networkidle' })
  await click('Journey · Today', 'Review Med-Surg Night and decide')
  await page.waitForURL(/\/investigate\/4/, { timeout: 10000 }).then(() => log(true, width, 'Journey · Today -> Investigate Med-Surg Night')).catch(() => log(false, width, 'Journey · did not reach /investigate/4'))
  await page.waitForLoadState('networkidle')
  const j1 = await askIn('Journey · panel', 'Why is Med-Surg Night flagged?')
  const j2 = await askIn('Journey · follow-up', 'Could staffing explain this?')
  followUp('Journey', j1, j2)
  const j3 = await askIn('Journey · draft', 'Draft a plan I can review')
  log(!!j3?.answer?.plan_draft, width, 'Journey · plan draft returned (owner, measure, review date, success criterion)')
  try {
    const panel = panelOf()
    await panel.getByRole('button', { name: 'Approve plan' }).last().click({ timeout: 10000 })
    await panel.getByText('Plan approved and recorded').waitFor({ state: 'visible', timeout: 10000 })
    log(true, width, 'Journey · approved in the panel')
  } catch { log(false, width, 'Journey · could not approve the drafted plan') }
  await page.reload({ waitUntil: 'networkidle' })
  await see('Journey · after reload', ['See if the plan worked', 'Approved'])
  await page.goto(base + '/plans', { waitUntil: 'networkidle' })
  await see('Journey · Action plans', ['Approved', 'days to review'])
  await page.goto(base + '/investigate/4', { waitUntil: 'networkidle' })
  await click('Journey · Review', 'See if the plan worked')
  await see('Journey · Review', ['Not ready', 'days', 'Fast-forward to the review date'])
  await noOverflow('Journey · Review')

  // scripted investigations with one follow-up each, on /ask (team context Med-Surg Night)
  await page.goto(base + '/ask', { waitUntil: 'networkidle' })
  const sb1 = await askIn('Scripted B', 'Compare it with the other night shifts')
  const sb2 = await askIn('Scripted B · follow-up', 'When did it start?')
  followUp('Scripted B', sb1, sb2)
  await page.goto(base + '/ask', { waitUntil: 'networkidle' })
  const sc1 = await askIn('Scripted C', 'Is this normal for teams like ours?')
  const sc2 = await askIn('Scripted C · follow-up', 'What is missing?')
  followUp('Scripted C', sc1, sc2)
  await noOverflow('Ask · investigation')
  page.off('response', onInv)

  const uniq = [...new Set(errors)]
  log(uniq.length === 0, width, `no console errors or failed API calls${uniq.length ? ': ' + uniq.slice(0, 3).join(' | ') : ''}`)
  await ctx.close()
}
await fetch(base + '/api/demo', { method: 'DELETE' })
await browser.close()
console.log(results.join('\n'))
console.log(`\n${results.length - failed} passed, ${failed} failed`)
process.exit(failed ? 1 : 0)
