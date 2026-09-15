process.env.MOCK = '1'

const { createServer } = await import('vite')

const server = await createServer({ root: '.', logLevel: 'silent' })
await server.listen()
const port = server.config.server.port || 5173
const base = `http://localhost:${port}`

const results = []

async function check(name, url, expect, method = 'GET', body = null) {
  const opts = { method }
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' }
    opts.body = body
  }
  const res = await fetch(url, opts)
  const text = await res.text()
  let data
  try { data = JSON.parse(text) } catch { data = text }
  const ok = expect(res.status, data)
  results.push({ name, status: res.status, ok })
  if (!ok) console.error('FAIL', name, data)
}

await check('calendar', `${base}/api/calendar?month=2026-09`, (status, body) => {
  return status === 200 && body.days?.length === 2 && body.days[0].title === '日常问候'
})

await check('day', `${base}/api/day/2026-09-14`, (status, body) => {
  return status === 200 && body.subtitle?.sentences?.length === 3 && body.title === '日常问候'
})

await check('day 404', `${base}/api/day/2026-09-01`, (status, body) => {
  return status === 404 && body.detail === '当天没有学习任务'
})

await check('admin list', `${base}/api/admin/videos`, (status, body) => {
  return status === 200 && body.videos?.length === 1
})

await check('admin import', `${base}/api/admin/videos/import`, (status, body) => {
  return status === 200 && body.imported?.length === 2 && body.imported.some((i) => i.updated)
}, 'POST', JSON.stringify({ path: 'D:\\videos\\2026-09', month: '2026-09' }))

// Page shells
const homeHtml = await fetch(`${base}/`).then((r) => r.text())
results.push({ name: 'home page shell', status: 200, ok: homeHtml.includes('<div id="app"></div>') && homeHtml.includes('每日英语') })

const playHtml = await fetch(`${base}/play/2026-09-14`).then((r) => r.text())
results.push({ name: 'play page shell', status: 200, ok: playHtml.includes('<div id="app"></div>') })

await server.close()

console.log('smoke results:')
for (const r of results) {
  console.log(`  ${r.ok ? '✓' : '✗'} ${r.name} (${r.status})`)
}

if (results.some((r) => !r.ok)) {
  process.exit(1)
}
console.log('all smoke checks passed')
