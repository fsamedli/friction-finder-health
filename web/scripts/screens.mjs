// Full-page screenshots of a list of routes at 1440 px and 390 px, on both demo-clock dates.
// usage: node web/scripts/screens.mjs <base-url> <out-dir> <route,route,...>
//   file name: <width>_<MM-DD>_<slug>.jpg, slug = route with '/', '?', '=' and '&' turned into '_'
// Writes <out-dir>/report.json (route, width, clock, file, console errors). Reset the demo before running.
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'

const [base = 'http://127.0.0.1:8012', out = 'screens', list = '/'] = process.argv.slice(2)
const routes = list.split(',').filter(Boolean)
mkdirSync(out, { recursive: true })
const slug = (r) => (r === '/' ? 'home' : r.replace(/^\//, '').replace(/[/?=&]+/g, '_'))
const report = []
const browser = await chromium.launch({ channel: 'chrome', headless: true })
for (const width of [1440, 390]) {
  for (const clock of ['2026-09-15', '2026-11-30']) {
    const ctx = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 900 }, deviceScaleFactor: 1 })
    await ctx.addInitScript((c) => { try { localStorage.setItem('ff.asof', c); localStorage.setItem('ff.role', 'manager'); localStorage.setItem('ff.site', '1'); localStorage.removeItem('ff.demo') } catch {} }, clock)
    for (const r of routes) {
      const page = await ctx.newPage()
      const errors = []
      page.on('pageerror', (e) => errors.push(e.message))
      page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
      await page.goto(base + r, { waitUntil: 'networkidle' })
      await page.waitForTimeout(700)
      const file = `${width}_${clock.slice(5)}_${slug(r)}.jpg`
      await page.screenshot({ path: `${out}/${file}`, fullPage: true, type: 'jpeg', quality: 70 })
      report.push({ route: r, width, clock, file, errors })
      await page.close()
    }
    await ctx.close()
  }
}
await browser.close()
writeFileSync(`${out}/report.json`, JSON.stringify(report, null, 2))
console.log(`${report.length} screenshots, ${report.filter((x) => x.errors.length).length} with console errors -> ${out}`)
