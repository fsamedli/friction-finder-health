// Accessibility audit: axe-core (WCAG 2.1 A/AA rules) on every route. usage: node scripts/a11y.mjs http://127.0.0.1:8000
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
const axeSrc = readFileSync(createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8')
const base = process.argv[2] ?? 'http://127.0.0.1:8000'
const routes = ['/', '/investigate', '/investigate/4', '/investigate/4?tab=drivers', '/investigate/4?tab=evidence', '/investigate/4?tab=plan', '/plans', '/review/plan-richmond-night-a', '/insights', '/ask', '/ask?view=brief', '/data', '/value', '/trust']
const b = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } })
const byRule = {}
for (const r of routes) {
  const p = await ctx.newPage()
  await p.goto(base + r, { waitUntil: 'networkidle' }); await p.waitForTimeout(600)
  await p.addScriptTag({ content: axeSrc })
  const res = await p.evaluate(async () => await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }))
  for (const v of res.violations) {
    byRule[v.id] ??= { impact: v.impact, help: v.help, nodes: 0, routes: new Set(), samples: [] }
    byRule[v.id].nodes += v.nodes.length; byRule[v.id].routes.add(r)
    if (byRule[v.id].samples.length < 4) byRule[v.id].samples.push(...v.nodes.slice(0, 2).map((n) => (n.any[0]?.message ?? n.failureSummary ?? '').slice(0, 150) + ' @ ' + n.target.join(' ').slice(0, 80)))
  }
  await p.close()
}
await b.close()
const rules = Object.entries(byRule)
for (const [id, v] of rules) console.log(`${id} [${v.impact}] ${v.nodes} nodes on ${v.routes.size} routes — ${v.help}\n   ${v.samples.slice(0, 4).join('\n   ')}`)
console.log(`\n${rules.length} rules violated, ${rules.reduce((s, [, v]) => s + v.nodes, 0)} nodes`)
