// Screenshot at 1440 px with a chosen demo clock (Oct 27 polish): node scripts/shot_asof.mjs <base> <out.png> <route> <asof> [viewportOnly]
import { chromium } from 'playwright-core'
const [base, out, route, asof, vpOnly] = process.argv.slice(2)
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
await ctx.addInitScript((d) => { try { localStorage.setItem('ff.asof', d); localStorage.setItem('ff.role', 'manager'); localStorage.setItem('ff.site', '1'); localStorage.setItem('ff.team', '4'); localStorage.removeItem('ff.demo') } catch {} }, asof)
const page = await ctx.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message)); page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
await page.goto(base + route, { waitUntil: 'networkidle' }); await page.waitForTimeout(900)
await page.screenshot({ path: out, fullPage: !vpOnly, type: 'png' })
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
console.log(`saved ${out}; console errors: ${errors.length}; overflow ${overflow}px`); for (const e of errors) console.log('  ', e)
await browser.close()
