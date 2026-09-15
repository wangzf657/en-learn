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

const scoringConfig = { provider: "mock", options: {}, providers: ["mock", "azure", "iflytek"] }

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

        // DELETE /api/admin/videos/:id
        const delMatch = url.match(/^\/admin\/videos\/(\d+)$/)
        if (delMatch && req.method === "DELETE") {
          const id = Number(delMatch[1])
          videos = videos.filter((v) => v.id !== id)
          return sendJson(res, 200, { ok: true })
        }

        // POST /api/admin/videos/import
        if (url === "/admin/videos/import" && req.method === "POST") {
          const body = await readBody(req)
          if (body.path && body.path.includes("fail")) {
            return sendJson(res, 422, { detail: "路径不存在或格式错误" })
          }
          const month = body.month || "2026-09"
          return sendJson(res, 200, {
            imported: [
              { id: 10, date: `${month}-01`, title: "第一课", updated: false },
              { id: 11, date: `${month}-02`, title: "第二课", updated: true },
            ],
            skipped: [
              { file: "03_nosub.json", reason: "缺少对应视频" },
            ],
          })
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
          const wordScores = words.map((w, i) => ({
            word: w,
            accuracy_score: [82.5, 78, 90][i % 3],
            expected_phonemes: i % 2 === 0 ? "h ə l oʊ" : "w ɜːr l d",
            actual_phonemes: i % 2 === 0 ? "h ə l oʊ" : "w ə l d",
            phoneme_scores: [80, 85, 90].slice(0, Math.max(1, w.length % 3 + 1)),
          }))
          return sendJson(res, 200, {
            accuracy_score: 82.5,
            fluency_score: 78,
            completeness_score: 90,
            word_scores: wordScores,
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

        return sendJson(res, 404, { detail: "mock 未实现" })
      })
    },
  }
}
