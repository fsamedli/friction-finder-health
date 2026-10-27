// One PNG of the Review page at 1440 px with the demo clock on the review date (2026-11-30).
// usage: node shot_review.mjs <base-url> <out.png> [route]
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'

const [base = 'http://127.0.0.1:8040', out = 'A_review.png', route = '/review/plan-lanford-med-surg-night'] = process.argv.slice(2)
mkdirSync(dirname(out), { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
await ctx.addInitScript(() => { try { localStorage.setItem('ff.asof', '2026-11-30'); localStorage.setItem('ff.role', 'manager'); localStorage.setItem('ff.site', '1'); localStorage.setItem('ff.team', '4'); localStorage.removeItem('ff.demo') } catch {} })
const page = await ctx.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
await page.goto(base + route, { waitUntil: 'networkidle' })
await page.waitForTimeout(900)
await page.screenshot({ path: out, fullPage: true, type: 'png' })
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
console.log(`saved ${out}; console errors: ${errors.length}; horizontal overflow: ${overflow}px`)
for (const e of errors) console.log('  ', e)
await browser.close()
