import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const emptyMp4Path = path.join(__dirname, 'public', 'mock', 'empty.mp4')

const sampleSubtitle = {
  sentences: [
    {
      start: 1.2,
      end: 4.5,
      en: "How you doing?",
      zh: "你好吗？",
      words: [{ w: "doing", phonetic: "ˈduːɪŋ", note: "How you doing 是美式口语常用问候" }],
    },
    {
      start: 5.0,
      end: 8.0,
      en: "I'm doing great, thanks.",
      zh: "我很好，谢谢。",
      words: [{ w: "great", phonetic: "ɡreɪt", note: "表示很棒、很好" }],
    },
    {
      start: 8.5,
      end: 12.0,
      en: "Let's get started.",
      zh: "我们开始吧。",
    },
  ],
}

const sampleSrt = `1
00:00:01,200 --> 00:00:04,500
How you doing?

2
00:00:05,000 --> 00:00:08,000
I'm doing great, thanks.

3
00:00:08,500 --> 00:00:12,000
Let's get started.`

let libraryRoot = "D:\\videos"

let courses = [
  { id: 1, name: "日常系列" },
  { id: 2, name: "餐厅系列" },
]

let materials = [
  { id: 1, courseId: 1, title: "日常问候", relPath: "greetings.mp4", sentenceCount: 3, read: false, readAt: null, dates: ["2026-09-14", "2026-09-15"] },
  { id: 2, courseId: 1, title: "自我介绍", relPath: "intro.mp4", sentenceCount: 2, read: true, readAt: "2026-09-10T08:00:00Z", dates: [] },
  { id: 3, courseId: 2, title: "点餐用语", relPath: "order.mp4", sentenceCount: 2, read: false, readAt: null, dates: ["2026-09-16"] },
  { id: 4, courseId: 2, title: "餐厅对话", relPath: "dialog.mp4", sentenceCount: 0, read: false, readAt: null, dates: [] },
]

const scoringConfig = { provider: "mock", options: {}, providers: ["mock", "azure", "iflytek"] }

function sendJson(res, status, data) {
  res.statusCode = status
  res.setHeader("Content-Type", "application/json")
  res.end(JSON.stringify(data))
}

function sendText(res, status, text) {
  res.statusCode = status
  res.setHeader("Content-Type", "text/plain")
  res.end(text)
}

function sendBinary(res, status, buffer, contentType) {
  res.statusCode = status
  res.setHeader("Content-Type", contentType)
  res.end(buffer)
}

async function readBody(req) {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  const raw = Buffer.concat(chunks).toString("utf8")
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

function courseDto(c) {
  const mats = materials.filter((m) => m.courseId === c.id)
  const allDates = mats.flatMap((m) => m.dates || [])
  const uniqueDates = [...new Set(allDates)].sort()
  const readCount = mats.filter((m) => m.read).length
  return { id: c.id, name: c.name, materialCount: mats.length, readCount, dates: uniqueDates }
}

function listCourses() {
  return [...courses].sort((a, b) => a.name.localeCompare(b.name)).map(courseDto)
}

function materialDto(m) {
  return {
    id: m.id,
    title: m.title,
    relPath: m.relPath,
    sentenceCount: m.sentenceCount,
    read: m.read,
    readAt: m.readAt,
    dates: m.dates || [],
    subtitle: m.sentenceCount > 0 ? sampleSubtitle : { sentences: [] },
  }
}

function getCourse(id) {
  const c = courses.find((x) => x.id === id)
  if (!c) return null
  const mats = materials
    .filter((m) => m.courseId === id)
    .sort((a, b) => a.relPath.localeCompare(b.relPath))
  return { id: c.id, name: c.name, materials: mats.map(materialDto) }
}

function makeDayMaterial(m) {
  return {
    id: m.id,
    title: m.title,
    videoUrl: `/api/materials/${m.id}/stream`,
    srtUrl: `/api/materials/${m.id}/srt`,
    subtitle: m.sentenceCount > 0 ? sampleSubtitle : { sentences: [] },
  }
}

function today() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export default function mockApiPlugin() {
  return {
    name: "mock-api",
    configureServer(server) {
      server.middlewares.use("/api", async (req, res, next) => {
        const url = req.url || ""

        // GET /api/calendar?month=YYYY-MM
        const calMatch = url.match(/^\/calendar\?month=(\d{4}-\d{2})$/)
        if (calMatch) {
          const month = calMatch[1]
          const dayMap = {}
          for (const m of materials) {
            for (const date of m.dates || []) {
              if (date.startsWith(month)) {
                const c = courses.find((x) => x.id === m.courseId)
                if (!dayMap[date]) {
                  dayMap[date] = { date, materialId: m.id, title: m.title, checked: false, materialCount: 0 }
                }
                dayMap[date].materialCount += 1
                if (dayMap[date].materialCount > 1) {
                  dayMap[date].title = `${dayMap[date].materialCount} 个素材`
                }
              }
            }
          }
          return sendJson(res, 200, { days: Object.values(dayMap) })
        }

        // GET /api/day/:date
        const dayMatch = url.match(/^\/day\/([\d-]+)$/)
        if (dayMatch && req.method === "GET") {
          const date = dayMatch[1]
          const dayMaterials = materials.filter((m) => (m.dates || []).includes(date))
          if (dayMaterials.length === 0) {
            return sendJson(res, 404, { detail: "当天没有学习任务" })
          }
          const checked = date === today()
          return sendJson(res, 200, {
            date,
            checked,
            materials: dayMaterials.map(makeDayMaterial),
          })
        }

        // GET /api/materials/:id/srt
        const srtMatch = url.match(/^\/materials\/(\d+)\/srt$/)
        if (srtMatch && req.method === "GET") {
          return sendText(res, 200, sampleSrt)
        }

        // GET /api/materials/:id/stream
        const streamMatch = url.match(/^\/materials\/(\d+)\/stream$/)
        if (streamMatch && req.method === "GET") {
          try {
            const buf = fs.readFileSync(emptyMp4Path)
            return sendBinary(res, 200, buf, "video/mp4")
          } catch {
            return sendJson(res, 404, { detail: "stream 未找到" })
          }
        }

        // POST /api/day/:date/checkin
        const checkinMatch = url.match(/^\/day\/([\d-]+)\/checkin$/)
        if (checkinMatch && req.method === "POST") {
          return sendJson(res, 200, { ok: true })
        }

        // GET /api/admin/library
        if (url === "/admin/library" && req.method === "GET") {
          return sendJson(res, 200, { root: libraryRoot })
        }

        // PUT /api/admin/library
        if (url === "/admin/library" && req.method === "PUT") {
          const body = await readBody(req)
          libraryRoot = body.root ?? libraryRoot
          return sendJson(res, 200, { root: libraryRoot })
        }

        // POST /api/admin/courses/import
        if (url === "/admin/courses/import" && req.method === "POST") {
          const body = await readBody(req)
          if (body.folder && body.folder.includes("fail")) {
            return sendJson(res, 422, { detail: "导入文件夹必须在统一前缀 D:\\videos 之下" })
          }
          const courseId = courses.length ? Math.max(...courses.map((c) => c.id)) + 1 : 1
          const newCourse = { id: courseId, name: body.folder || "新课程" }
          courses.push(newCourse)
          const newMaterials = [
            { id: materials.length ? Math.max(...materials.map((m) => m.id)) + 1 : 1, courseId, title: "第一课", relPath: "01.mp4", sentenceCount: 3, read: false, readAt: null, dates: [] },
            { id: materials.length ? Math.max(...materials.map((m) => m.id)) + 2 : 2, courseId, title: "第二课", relPath: "02.mp4", sentenceCount: 2, read: false, readAt: null, dates: [] },
          ]
          materials.push(...newMaterials)
          return sendJson(res, 200, {
            course: { id: newCourse.id, name: newCourse.name, materialCount: newMaterials.length },
            materials: newMaterials.map((m, i) => ({ id: m.id, title: m.title, updated: i === 1 })),
            skipped: [{ file: "03_nosub.json", reason: "缺少对应视频" }],
          })
        }

        // GET /api/admin/courses
        if (url === "/admin/courses" && req.method === "GET") {
          return sendJson(res, 200, { courses: listCourses() })
        }

        // GET /api/admin/courses/:id
        const courseMatch = url.match(/^\/admin\/courses\/(\d+)$/)
        if (courseMatch && req.method === "GET") {
          const id = Number(courseMatch[1])
          const data = getCourse(id)
          if (!data) return sendJson(res, 404, { detail: "课程不存在" })
          return sendJson(res, 200, data)
        }

        // DELETE /api/admin/courses/:id
        if (courseMatch && req.method === "DELETE") {
          const id = Number(courseMatch[1])
          const removedMaterials = materials.filter((m) => m.courseId === id).length
          const removedSchedules = materials.filter((m) => m.courseId === id).reduce((sum, m) => sum + (m.dates || []).length, 0)
          materials = materials.filter((m) => m.courseId !== id)
          courses = courses.filter((c) => c.id !== id)
          return sendJson(res, 200, { ok: true, removedMaterials, removedSchedules })
        }

        // DELETE /api/admin/materials/:id
        const materialMatch = url.match(/^\/admin\/materials\/(\d+)$/)
        if (materialMatch && req.method === "DELETE") {
          const id = Number(materialMatch[1])
          const m = materials.find((x) => x.id === id)
          const removedSchedules = m ? (m.dates || []).length : 0
          materials = materials.filter((x) => x.id !== id)
          return sendJson(res, 200, { ok: true, removedSchedules })
        }

        // PUT /api/admin/materials/:id/read
        const readMatch = url.match(/^\/admin\/materials\/(\d+)\/read$/)
        if (readMatch && req.method === "PUT") {
          const id = Number(readMatch[1])
          const body = await readBody(req)
          const m = materials.find((x) => x.id === id)
          if (m) {
            m.read = !!body.read
            m.readAt = m.read ? new Date().toISOString() : null
          }
          return sendJson(res, 200, { id, read: m?.read || false, readAt: m?.readAt || null })
        }

        // POST /api/admin/schedule
        if (url === "/admin/schedule" && req.method === "POST") {
          const body = await readBody(req)
          const courseId = Number(body.courseId)
          const c = courses.find((x) => x.id === courseId)
          if (!c) return sendJson(res, 404, { detail: "课程不存在" })
          const from = new Date(body.dateFrom)
          const to = new Date(body.dateTo)
          if (isNaN(from.getTime()) || isNaN(to.getTime()) || from > to) {
            return sendJson(res, 422, { detail: "日期范围无效" })
          }
          const courseMaterials = materials
            .filter((m) => m.courseId === courseId)
            .sort((a, b) => a.relPath.localeCompare(b.relPath))
          const dates = []
          const d = new Date(from)
          while (d <= to) {
            dates.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`)
            d.setDate(d.getDate() + 1)
          }
          const scheduled = []
          courseMaterials.forEach((m, i) => {
            if (i < dates.length) {
              const date = dates[i]
              if (!(m.dates || []).includes(date)) {
                m.dates = [...(m.dates || []), date]
              }
              scheduled.push({ date, materialIds: [m.id] })
            }
          })
          return sendJson(res, 200, { added: scheduled.length, scheduled })
        }

        // GET /api/admin/schedule?month=YYYY-MM
        const adminScheduleMatch = url.match(/^\/admin\/schedule\?month=(\d{4}-\d{2})$/)
        if (adminScheduleMatch && req.method === "GET") {
          const month = adminScheduleMatch[1]
          const dayMap = {}
          for (const m of materials) {
            for (const date of m.dates || []) {
              if (date.startsWith(month)) {
                if (!dayMap[date]) {
                  dayMap[date] = { date, checked: false, materials: [] }
                }
                const c = courses.find((x) => x.id === m.courseId)
                dayMap[date].materials.push({ id: m.id, title: m.title, courseName: c?.name || "" })
              }
            }
          }
          return sendJson(res, 200, { days: Object.values(dayMap) })
        }

        // DELETE /api/admin/schedule?month=YYYY-MM
        if (adminScheduleMatch && req.method === "DELETE") {
          const month = adminScheduleMatch[1]
          let removed = 0
          for (const m of materials) {
            const before = (m.dates || []).length
            m.dates = (m.dates || []).filter((d) => !d.startsWith(month))
            removed += before - (m.dates || []).length
          }
          return sendJson(res, 200, { ok: true, removed })
        }

        // POST /api/admin/day/:date/materials
        const dayMaterialsMatch = url.match(/^\/admin\/day\/([\d-]+)\/materials$/)
        if (dayMaterialsMatch && req.method === "POST") {
          const date = dayMaterialsMatch[1]
          const body = await readBody(req)
          const ids = body.materialIds || []
          if (ids.length === 0) return sendJson(res, 422, { detail: "materialIds 不能为空" })
          for (const id of ids) {
            const m = materials.find((x) => x.id === id)
            if (!m) return sendJson(res, 422, { detail: `素材不存在: ${id}` })
            if (!(m.dates || []).includes(date)) {
              m.dates = [...(m.dates || []), date]
            }
          }
          return sendJson(res, 200, { added: ids.length })
        }

        // DELETE /api/admin/day/:date
        const clearDayMatch = url.match(/^\/admin\/day\/([\d-]+)$/)
        if (clearDayMatch && req.method === "DELETE") {
          const date = clearDayMatch[1]
          let removed = 0
          for (const m of materials) {
            const before = (m.dates || []).length
            m.dates = (m.dates || []).filter((d) => d !== date)
            removed += before - (m.dates || []).length
          }
          return sendJson(res, 200, { ok: true, removed })
        }

        // DELETE /api/admin/day/:date/materials/:materialId
        const removeDayMaterialMatch = url.match(/^\/admin\/day\/([\d-]+)\/materials\/(\d+)$/)
        if (removeDayMaterialMatch && req.method === "DELETE") {
          const date = removeDayMaterialMatch[1]
          const id = Number(removeDayMaterialMatch[2])
          const m = materials.find((x) => x.id === id)
          if (m) {
            m.dates = (m.dates || []).filter((d) => d !== date)
          }
          return sendJson(res, 200, { ok: true })
        }

        // POST /api/score
        if (url === "/score" && req.method === "POST") {
          const chunks = []
          for await (const chunk of req) chunks.push(chunk)
          const raw = Buffer.concat(chunks)
          const ct = req.headers["content-type"] || ""
          const boundaryMatch = ct.match(/boundary=([^;]+)/)
          let reference = "Hello world"
          if (boundaryMatch) {
            const text = raw.toString("binary")
            const m = text.match(/name="reference"\r\n\r\n([\s\S]*?)\r\n--/)
            if (m) reference = m[1]
          }
          const words = reference.match(/\b[\w']+\b/g) || ["Hello", "world"]
          const phonemeSets = [
            { text: ["h", "ə", "l", "oʊ"], score: [85, 88, 80, 90] },
            { text: ["w", "ɜːr", "l", "d"], score: [70, 55, 80, 60] },
          ]
          const wordScores = words.map((w, i) => {
            const set = phonemeSets[i % phonemeSets.length]
            const isBad = i === 1 // 第二个词演示「错词」低分 + 重音错
            return {
              word: w,
              accuracy_score: isBad ? 45 : 88,
              expected_phonemes: set.text.join(" "),
              actual_phonemes: set.text.join(""),
              phoneme_scores: set.score,
              phonemes: set.text,
              type: isBad ? 3 : 2,
              stress: isBad ? 0 : 1,
            }
          })
          return sendJson(res, 200, {
            accuracy_score: 82.5,
            fluency_score: 78,
            completeness_score: 90,
            word_scores: wordScores,
            sample: reference,
            usertext: reference,
            audio_quality: { volume: false, clipping: false, noise: true, cut: false, too_short: false, empty_audio: false },
          })
        }

        // GET /api/admin/scoring
        if (url === "/admin/scoring" && req.method === "GET") {
          return sendJson(res, 200, scoringConfig)
        }

        // PUT /api/admin/scoring
        if (url === "/admin/scoring" && req.method === "PUT") {
          const body = await readBody(req)
          scoringConfig.provider = body.provider ?? scoringConfig.provider
          scoringConfig.options = body.options ?? {}
          return sendJson(res, 200, { ok: true })
        }

        // GET /api/review
        if (url === "/review" && req.method === "GET") {
          const svgImg = "data:image/svg+xml," + encodeURIComponent(
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240">' +
            '<rect width="100%" height="100%" rx="16" fill="#ffe0ec"/>' +
            '<text x="50%" y="50%" font-size="30" text-anchor="middle" fill="#b04b8f">示例复习卡</text></svg>'
          )
          const groups = []
          const readMats = materials.filter((m) => m.read)
          const courseIds = [...new Set(readMats.map((m) => m.courseId))]
          for (const cid of courseIds) {
            const c = courses.find((x) => x.id === cid)
            if (!c) continue
            groups.push({ kind: "course", courseId: cid, courseName: c.name, materialId: null, title: c.name, files: [{ name: "课程总览.svg", url: svgImg, kind: "image" }] })
          }
          for (const m of readMats) {
            groups.push({ kind: "material", courseId: m.courseId, courseName: courses.find((x) => x.id === m.courseId)?.name || "", materialId: m.id, title: m.title, files: [{ name: "笔记.svg", url: svgImg, kind: "image" }] })
          }
          return sendJson(res, 200, { groups })
        }

        return sendJson(res, 404, { detail: "mock 未实现" })
      })
    },
  }
}
