export function parseSrt(text) {
  if (!text) return []
  const cues = []
  // Strip BOM and normalize line endings.
  const normalized = text
    .replace(/^\uFEFF/, '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
  const blocks = normalized.split(/\n\s*\n/)

  for (const raw of blocks) {
    const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lines.length < 2) continue

    // The first non-empty line may be a numeric index. If it is, drop it.
    let timeLineIndex = 0
    if (/^\d+$/.test(lines[0])) {
      timeLineIndex = 1
    }
    if (timeLineIndex >= lines.length) continue

    const times = parseTimes(lines[timeLineIndex])
    if (!times) continue

    const textLines = lines.slice(timeLineIndex + 1)
    if (textLines.length === 0) continue

    cues.push({
      start: times.start,
      end: times.end,
      text: textLines.join('\n'),
    })
  }

  return cues
}

function parseTimes(line) {
  // SRT timestamps use a comma as the decimal separator.
  const m = line.match(
    /^(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})/,
  )
  if (!m) return null

  const start = tsToSeconds(m[1], m[2], m[3], m[4])
  const end = tsToSeconds(m[5], m[6], m[7], m[8])
  if (end <= start || Number.isNaN(start) || Number.isNaN(end)) return null
  return { start, end }
}

function tsToSeconds(h, m, s, ms) {
  return Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms) / 1000
}
