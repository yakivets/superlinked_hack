// Screenshot harness for the impeccable inspection round. Not part of the app.
import { chromium } from 'playwright'

const OUT = process.argv[2] ?? '../.impeccable/review'
const BASE = 'http://localhost:5173'

const browser = await chromium.launch()

async function shoot(name, viewport, fn) {
  const page = await browser.newPage({ viewport })
  await fn(page)
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  await page.close()
  console.log(name)
}

const meetings = await (await fetch('http://localhost:8000/meetings')).json()
const firstId = meetings.meetings[0]?.id

const desktop = { width: 1440, height: 900 }
const mobile = { width: 390, height: 844 }

for (const [tag, vp] of [['desktop', desktop], ['mobile', mobile]]) {
  await shoot(tag, vp, async (p) => {
    await p.goto(BASE)
    await p.waitForSelector('h2')
  })
  await shoot(`${tag}-meeting`, vp, async (p) => {
    await p.goto(`${BASE}#/meeting/${firstId}`)
    await p.waitForSelector('h1')
    const rec = p.locator('button', { hasText: 'Transcript' })
    if (await rec.count()) await rec.click()
  })
  await shoot(`${tag}-threads`, vp, async (p) => {
    await p.goto(`${BASE}#/threads`)
    await p.waitForTimeout(2500)
  })
}

await shoot('desktop-search', desktop, async (p) => {
  await p.goto(BASE)
  await p.waitForSelector('input[type=text]')
  await p.fill('input[type=text]', 'payment bugs')
  await p.waitForTimeout(1500)
})

await shoot('desktop-answer', desktop, async (p) => {
  await p.goto(BASE)
  await p.waitForSelector('input[type=text]')
  await p.fill('input[type=text]', 'What was decided about shipping the onboarding flow?')
  await p.press('input[type=text]', 'Enter')
  await p.waitForSelector('section', { timeout: 60000 })
})

await browser.close()
