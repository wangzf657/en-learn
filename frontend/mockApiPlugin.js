const sampleSubtitle = {
  sentences: [
    {
      start: 1.2,
      end: 4.5,
      en: "How you doing?",
      zh: "你好吗？",
      words: [
        { w: "doing", phonetic: "ˈduːɪŋ", note: "How you doing 是美式口语常用问候" },
      ],
    },
    {
      start: 5.0,
      end: 8.0,
      en: "I'm doing great, thanks.",
      zh: "我很好，谢谢。",
      words: [
        { w: "great", phonetic: "ɡreɪt", note: "表示很棒、很好" },
      ],
    },
    {
      start: 8.5,
      end: 12.0,
      en: "Let's get started.",
      zh: "我们开始吧。",
    },
  ],
}

const sampleDay = {
  videoId: 1,
  title: "日常问候",
  videoUrl: "/mock/empty.mp4",
  checked: false,
  subtitle: sampleSubtitle,
}

let videos = [
  { id: 1, date: "2026-09-14", title: "日常问候", videoPath: "D:\\videos\\demo.mp4", sentenceCount: 3, checked: false },
]

function today() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

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
          const days = []
          if (month === "2026-09") {
            days.push({ date: "2026-09-14", videoId: 1, title: "日常问候", checked: false })
            days.push({ date: "2026-09-15", videoId: 2, title: "点餐用语", checked: true })
          }
          return sendJson(res, 200, { days })
        }

        // GET /api/day/:date
        const dayMatch = url.match(/^\/day\/([\d-]+)$/)
        if (dayMatch && req.method === "GET") {
          const date = dayMatch[1]
          if (date === "2026-09-14") return sendJson(res, 200, sampleDay)
          if (date === "2026-09-15") {
            return sendJson(res, 200, { ...sampleDay, videoId: 2, title: "点餐用语", checked: true })
          }
          return sendJson(res, 404, { detail: "当天没有学习任务" })
        }

        // POST /api/day/:date/checkin
        const checkinMatch = url.match(/^\/day\/([\d-]+)\/checkin$/)
        if (checkinMatch && req.method === "POST") {
          return sendJson(res, 200, { ok: true })
        }

        // GET /api/admin/videos
        if (url === "/admin/videos" && req.method === "GET") {
          return sendJson(res, 200, { videos })
        }

        // POST /api/admin/videos
        if (url === "/admin/videos" && req.method === "POST") {
          const body = await readBody(req)
          const existing = videos.find((v) => v.date === body.date)
          if (existing) return sendJson(res, 409, { detail: `日期 ${body.date} 已经存在` })
          let subtitle
          try {
            subtitle = typeof body.subtitleJson === "string" ? JSON.parse(body.subtitleJson) : body.subtitleJson
          } catch {
            return sendJson(res, 422, { detail: "JSON 解析失败" })
          }
          const id = videos.length ? Math.max(...videos.map((v) => v.id)) + 1 : 1
          const sentenceCount = subtitle?.sentences?.length || 0
          videos.push({ id, date: body.date, title: body.title, videoPath: body.videoPath, sentenceCount, checked: false })
          return sendJson(res, 201, { id })
        }

        // PUT /api/admin/videos/:id
        const putMatch = url.match(/^\/admin\/videos\/(\d+)$/)
        if (putMatch && req.method === "PUT") {
          const id = Number(putMatch[1])
          const body = await readBody(req)
          const idx = videos.findIndex((v) => v.id === id)
          if (idx < 0) return sendJson(res, 404, { detail: "视频不存在" })
          if (body.date) videos[idx].date = body.date
          if (body.title) videos[idx].title = body.title
          if (body.videoPath) videos[idx].videoPath = body.videoPath
          if (body.subtitleJson) {
            const subtitle = typeof body.subtitleJson === "string" ? JSON.parse(body.subtitleJson) : body.subtitleJson
            videos[idx].sentenceCount = subtitle?.sentences?.length || 0
          }
          return sendJson(res, 200, { ok: true })
        }

        // DELETE /api/admin/videos/:id
        const delMatch = url.match(/^\/admin\/videos\/(\d+)$/)
        if (delMatch && req.method === "DELETE") {
          const id = Number(delMatch[1])
          videos = videos.filter((v) => v.id !== id)
          return sendJson(res, 200, { ok: true })
        }

        // POST /api/admin/validate-path
        if (url === "/admin/validate-path" && req.method === "POST") {
          const body = await readBody(req)
          const exists = body.path && body.path.toLowerCase().endsWith(".mp4")
          return sendJson(res, 200, { exists, size: exists ? 12_345_678 : 0 })
        }

        return sendJson(res, 404, { detail: "mock 未实现" })
      })
    },
  }
}
