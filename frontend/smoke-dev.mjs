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
  return status === 200 && body.days?.length >= 1 && body.days[0].title === '日常问候' && body.days[0].materialCount != null
})

await check('day', `${base}/api/day/2026-09-14`, (status, body) => {
  return status === 200 && body.materials?.length === 1 && body.materials[0].subtitle?.sentences?.length === 3 && body.materials[0].title === '日常问候'
})

await check('srt', `${base}/api/materials/1/srt`, (status, body) => {
  return status === 200 && typeof body === 'string' && body.includes('How you doing?')
})

{
  const streamRes = await fetch(`${base}/api/materials/1/stream`)
  const streamBuf = await streamRes.arrayBuffer()
  const ok = streamRes.status === 200 && streamBuf.byteLength > 0 && streamRes.headers.get('content-type') === 'video/mp4'
  results.push({ name: 'stream', status: streamRes.status, ok })
  if (!ok) console.error('FAIL stream', streamBuf.byteLength)
}

await check('day 404', `${base}/api/day/2026-09-01`, (status, body) => {
  return status === 404 && body.detail === '当天没有学习任务'
})

await check('library', `${base}/api/admin/library`, (status, body) => {
  return status === 200 && body.root === 'D:\\videos'
})

await check('courses list', `${base}/api/admin/courses`, (status, body) => {
  return status === 200 && body.courses?.length >= 2 && body.courses.some((c) => c.materialCount > 0) && body.courses.some((c) => c.dates?.length > 0)
})

await check('course detail', `${base}/api/admin/courses/1`, (status, body) => {
  return status === 200 && body.materials?.length >= 1 && body.materials[0].read != null && body.materials[0].dates != null
})

await check('admin import', `${base}/api/admin/courses/import`, (status, body) => {
  return status === 200 && body.course?.materialCount >= 1 && body.materials?.length >= 1 && body.skipped?.length >= 1
}, 'POST', JSON.stringify({ folder: 'D:\\videos\\2026-09' }))

await check('admin schedule', `${base}/api/admin/schedule`, (status, body) => {
  return status === 200 && body.added >= 1 && Array.isArray(body.scheduled)
}, 'POST', JSON.stringify({ courseId: 1, dateFrom: '2026-09-20', dateTo: '2026-09-25' }))

await check('admin schedule month', `${base}/api/admin/schedule?month=2026-09`, (status, body) => {
  return status === 200 && body.days?.length >= 1 && body.days[0].materials?.length >= 1 && body.days[0].materials[0].courseName != null
})

await check('admin day materials', `${base}/api/admin/day/2026-09-20/materials`, (status, body) => {
  return status === 200 && body.added === 1
}, 'POST', JSON.stringify({ materialIds: [2] }))

await check('admin delete day material', `${base}/api/admin/day/2026-09-20/materials/2`, (status, body) => {
  return status === 200 && body.ok === true
}, 'DELETE')

await check('material read', `${base}/api/admin/materials/1/read`, (status, body) => {
  return status === 200 && body.read === true && body.readAt != null
}, 'PUT', JSON.stringify({ read: true }))

// Page shells
const homeHtml = await fetch(`${base}/`).then((r) => r.text())
results.push({ name: 'home page shell', status: 200, ok: homeHtml.includes('<div id="app"></div>') && homeHtml.includes('每日英语') })

const playHtml = await fetch(`${base}/play/2026-09-14`).then((r) => r.text())
results.push({ name: 'play page shell', status: 200, ok: playHtml.includes('<div id="app"></div>') })

const localHtml = await fetch(`${base}/local`).then((r) => r.text())
results.push({ name: 'local page shell', status: 200, ok: localHtml.includes('<div id="app"></div>') })

await server.close()

console.log('smoke results:')
for (const r of results) {
  console.log(`  ${r.ok ? '✓' : '✗'} ${r.name} (${r.status})`)
}

if (results.some((r) => !r.ok)) {
  process.exit(1)
}
console.log('all smoke checks passed')
