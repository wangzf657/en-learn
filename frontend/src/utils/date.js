export function pad(n) {
  return String(n).padStart(2, '0')
}

export function formatMonth(year, month) {
  return `${year}-${pad(month)}`
}

export function dateKey(date) {
  const d = new Date(date)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function todayKey() {
  return dateKey(new Date())
}

export function getMonthGrid(year, month) {
  const first = new Date(year, month - 1, 1)
  const last = new Date(year, month, 0)
  const daysInMonth = last.getDate()
  // Monday-first: 0=Mon ... 6=Sun
  const startOffset = (first.getDay() + 6) % 7
  const cells = []

  for (let i = 0; i < startOffset; i++) {
    cells.push(null)
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(`${year}-${pad(month)}-${pad(d)}`)
  }

  // Pad to complete weeks
  while (cells.length % 7 !== 0) {
    cells.push(null)
  }

  return cells
}

export function addMonth(year, month, delta) {
  const m = month - 1 + delta
  const next = new Date(year, m, 1)
  return { year: next.getFullYear(), month: next.getMonth() + 1 }
}
