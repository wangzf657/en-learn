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

export const reviewApi = {
  get() {
    return request('/review')
  },
}

export const adminApi = {
  getLibrary() {
    return request('/admin/library')
  },
  saveLibrary(root) {
    return request('/admin/library', {
      method: 'PUT',
      body: JSON.stringify({ root }),
    })
  },
  importCourse(folder) {
    return request('/admin/courses/import', {
      method: 'POST',
      body: JSON.stringify({ folder }),
    })
  },
  listCourses() {
    return request('/admin/courses')
  },
  getCourse(id) {
    return request(`/admin/courses/${id}`)
  },
  deleteCourse(id) {
    return request(`/admin/courses/${id}`, { method: 'DELETE' })
  },
  deleteMaterial(id) {
    return request(`/admin/materials/${id}`, { method: 'DELETE' })
  },
  setMaterialRead(id, read) {
    return request(`/admin/materials/${id}/read`, {
      method: 'PUT',
      body: JSON.stringify({ read }),
    })
  },
  createSchedule(courseId, dateFrom, dateTo) {
    return request('/admin/schedule', {
      method: 'POST',
      body: JSON.stringify({ courseId, dateFrom, dateTo }),
    })
  },
  getSchedule(month) {
    return request(`/admin/schedule?month=${encodeURIComponent(month)}`)
  },
  clearMonth(month) {
    return request(`/admin/schedule?month=${encodeURIComponent(month)}`, { method: 'DELETE' })
  },
  addDayMaterials(date, materialIds) {
    return request(`/admin/day/${date}/materials`, {
      method: 'POST',
      body: JSON.stringify({ materialIds }),
    })
  },
  deleteDay(date) {
    return request(`/admin/day/${date}`, { method: 'DELETE' })
  },
  removeDayMaterial(date, materialId) {
    return request(`/admin/day/${date}/materials/${materialId}`, { method: 'DELETE' })
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
