const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
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
  create(data) {
    return request('/admin/videos', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  update(id, data) {
    return request(`/admin/videos/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },
  remove(id) {
    return request(`/admin/videos/${id}`, { method: 'DELETE' })
  },
  validatePath(path) {
    return request('/admin/validate-path', {
      method: 'POST',
      body: JSON.stringify({ path }),
    })
  },
}
