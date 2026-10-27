// Which elements are wider than the viewport? usage: node web/scripts/overflow.mjs <base-url> <route> [clock] [width]
import { chromium } from 'playwright-core'

const [base = 'http://127.0.0.1:8040', route = '/value', clock = '2026-09-15', w = '1440'] = process.argv.slice(2)
const width = Number(w)
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width, height: 900 } })
await ctx.addInitScript((c) => { try { localStorage.setItem('ff.asof', c); localStorage.setItem('ff.role', 'manager'); localStorage.setItem('ff.site', '1'); localStorage.setItem('ff.team', '4'); localStorage.removeItem('ff.demo') } catch {} }, clock)
const page = await ctx.newPage()
await page.goto(base + route, { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
const out = await page.evaluate(() => {
  const vw = document.documentElement.clientWidth
  const rows = []
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect()
    if (r.right > vw + 1 || r.width > vw + 1) rows.push({ tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 90), w: Math.round(r.width), right: Math.round(r.right), text: (el.textContent || '').trim().slice(0, 50) })
  }
  return { overflow: document.documentElement.scrollWidth - vw, rows: rows.slice(0, 12) }
})
console.log(`overflow ${out.overflow}px at ${width}px, clock ${clock}, ${route}`)
for (const r of out.rows) console.log(`  <${r.tag}> w=${r.w} right=${r.right} ${r.cls} | ${r.text}`)
await browser.close()
