const BASE = '/api'

async function request(path, { headers: userHeaders, ...options } = {}) {
  const headers = { 'Content-Type': 'application/json', ...userHeaders }
  if (options.body instanceof FormData) {
    delete headers['Content-Type']
  }

  const res = await fetch(BASE + path, {
    headers,
    ...options,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {
      // ignore
    }
    const err = new Error(`${res.status}: ${detail}`)
    err.status = res.status
    err.detail = detail
    throw err
  }

  if (res.status === 204) return null
  return res.json()
}

export const calendarApi = {
  getMonth(month) {
    return request(`/calendar?month=${encodeURIComponent(month)}`)
  },
}

export const dayApi = {
  get(date) {
    return request(`/day/${date}`)
  },
  checkin(date) {
    return request(`/day/${date}/checkin`, { method: 'POST' })
  },
}

export const adminApi = {
  list() {
    return request('/admin/videos')
  },
  remove(id) {
    return request(`/admin/videos/${id}`, { method: 'DELETE' })
  },
  importVideos(path, month) {
    return request('/admin/videos/import', {
      method: 'POST',
      body: JSON.stringify({ path, month }),
    })
  },
}

export const scoringApi = {
  score(audioBlob, reference) {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    form.append('reference', reference)
    return request('/score', { method: 'POST', body: form })
  },
  getScoring() {
    return request('/admin/scoring')
  },
  saveScoring(cfg) {
    return request('/admin/scoring', {
      method: 'PUT',
      body: JSON.stringify(cfg),
    })
  },
}
