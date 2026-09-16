import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Admin from '../views/Admin.vue'
import { mountWithRouter, mockFetch, restoreFetch } from './helpers.js'

function defaultLibrary() {
  return { body: { root: 'D:\\videos' } }
}

function defaultCourses() {
  return {
    body: {
      courses: [
        { id: 1, name: '日常系列', materialCount: 2, readCount: 1, dates: ['2026-09-14'] },
        { id: 2, name: '餐厅系列', materialCount: 2, readCount: 0, dates: [] },
      ],
    },
  }
}

function courseDetail(id) {
  if (id === 1) {
    return {
      body: {
        id: 1,
        name: '日常系列',
        materials: [
          { id: 1, title: '日常问候', relPath: 'greetings.mp4', sentenceCount: 3, read: false, readAt: null, dates: ['2026-09-14'] },
          { id: 2, title: '自我介绍', relPath: 'intro.mp4', sentenceCount: 2, read: true, readAt: '2026-09-10T08:00:00Z', dates: [] },
        ],
      },
    }
  }
  return { status: 404, body: { detail: 'not found' } }
}

function defaultScoring() {
  return { body: { provider: 'mock', options: {}, providers: ['mock'] } }
}

describe('Admin.vue general settings', () => {
  beforeEach(() => {
    mockFetch((url, options) => {
      if (url === '/api/admin/library' && (!options.method || options.method === 'GET')) return defaultLibrary()
      if (url === '/api/admin/library' && options.method === 'PUT') return { body: { root: 'D:\\videos' } }
      if (url === '/api/admin/courses' && (!options.method || options.method === 'GET')) return defaultCourses()
      if (url.match(/^\/api\/admin\/courses\/\d+$/) && (!options.method || options.method === 'GET')) return courseDetail(Number(url.split('/').pop()))
      if (url.match(/^\/api\/admin\/schedule\?month=/) && (!options.method || options.method === 'GET')) return { body: { days: [] } }
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) {
        return { body: { provider: 'azure', options: { appkey: 'ak', secret: 'sk' }, providers: ['mock', 'azure'] } }
      }
      if (url === '/api/admin/scoring' && options.method === 'PUT') return { body: { ok: true } }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('loads current scoring config and saves changes', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    expect(wrapper.text()).toContain('发音评分服务')

    const select = wrapper.find('.scoring-section select')
    expect(select.element.value).toBe('azure')

    const inputs = wrapper.findAll('.scoring-section input')
    expect(inputs[0].element.value).toBe('ak')
    expect(inputs[1].element.value).toBe('sk')

    await select.setValue('mock')
    const saveBtn = wrapper.findAll('.scoring-section button').find((b) => b.text() === '保存')
    await saveBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(wrapper.text()).toContain('已保存')
  })
})

describe('Admin.vue course import', () => {
  beforeEach(() => {
    mockFetch((url, options) => {
      if (url === '/api/admin/library' && (!options.method || options.method === 'GET')) return defaultLibrary()
      if (url === '/api/admin/courses' && (!options.method || options.method === 'GET')) return defaultCourses()
      if (url.match(/^\/api\/admin\/courses\/\d+$/) && (!options.method || options.method === 'GET')) return courseDetail(Number(url.split('/').pop()))
      if (url.match(/^\/api\/admin\/schedule\?month=/) && (!options.method || options.method === 'GET')) return { body: { days: [] } }
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) return defaultScoring()
      if (url === '/api/admin/courses/import' && options.method === 'POST') {
        return {
          body: {
            course: { id: 3, name: 'D:\\videos\\2026-09', materialCount: 2 },
            materials: [
              { id: 10, title: '第一课', updated: false },
              { id: 11, title: '第二课', updated: true },
            ],
            skipped: [{ file: '03_nosub.json', reason: '缺少对应视频' }],
          },
        }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('submits course import without date params and shows course, materials and skipped', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    const folderInput = wrapper.find('.course-card input[type="text"]')
    await folderInput.setValue('D:\\videos\\2026-09')

    const importBtn = wrapper.findAll('.course-card button').find((b) => b.text().includes('导入课程'))
    await importBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(wrapper.text()).toContain('D:\\videos\\2026-09')
    expect(wrapper.text()).toContain('2 个素材')
    expect(wrapper.text()).toContain('第一课')
    expect(wrapper.text()).toContain('第二课')
    expect(wrapper.text()).toContain('新增')
    expect(wrapper.text()).toContain('覆盖')
    expect(wrapper.text()).toContain('跳过 1 条')
    expect(wrapper.text()).toContain('03_nosub.json')
  })
})

describe('Admin.vue course management', () => {
  let fetchCalls = []

  beforeEach(() => {
    fetchCalls = []
    mockFetch((url, options) => {
      fetchCalls.push({ url, method: options?.method || 'GET' })
      if (url === '/api/admin/library' && (!options.method || options.method === 'GET')) return defaultLibrary()
      if (url === '/api/admin/courses' && (!options.method || options.method === 'GET')) return defaultCourses()
      if (url.match(/^\/api\/admin\/courses\/\d+$/) && (!options.method || options.method === 'GET')) return courseDetail(Number(url.split('/').pop()))
      if (url.match(/^\/api\/admin\/schedule\?month=/) && (!options.method || options.method === 'GET')) return { body: { days: [] } }
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) return defaultScoring()
      if (url.match(/^\/api\/admin\/materials\/\d+\/read$/) && options.method === 'PUT') {
        return { body: { id: Number(url.split('/')[3]), read: true, readAt: '2026-09-15T08:00:00Z' } }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('expands course and toggles material read state', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    expect(wrapper.text()).toContain('日常系列')

    const expandBtn = wrapper.findAll('.course-header button').find((b) => b.text() === '展开')
    await expandBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('日常问候')
    expect(wrapper.text()).toContain('自我介绍')

    const readBtn = wrapper.findAll('.material-row button').find((b) => b.text() === '未读')
    await readBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    const readCall = fetchCalls.find((c) => c.method === 'PUT' && c.url.match(/^\/api\/admin\/materials\/\d+\/read$/))
    expect(readCall).toBeTruthy()
  })

  it('deletes course after confirm', async () => {
    const confirmSpy = vi.fn().mockReturnValue(true)
    vi.stubGlobal('confirm', confirmSpy)

    let deleted = false
    mockFetch((url, options) => {
      fetchCalls.push({ url, method: options?.method || 'GET' })
      if (url === '/api/admin/library' && (!options.method || options.method === 'GET')) return defaultLibrary()
      if (url === '/api/admin/courses' && (!options.method || options.method === 'GET')) {
        return deleted ? { body: { courses: [{ id: 2, name: '餐厅系列', materialCount: 2, readCount: 0, dates: [] }] } } : defaultCourses()
      }
      if (url.match(/^\/api\/admin\/courses\/\d+$/) && (!options.method || options.method === 'GET')) return courseDetail(Number(url.split('/').pop()))
      if (url.match(/^\/api\/admin\/schedule\?month=/) && (!options.method || options.method === 'GET')) return { body: { days: [] } }
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) return defaultScoring()
      if (url === '/api/admin/courses/1' && options.method === 'DELETE') {
        deleted = true
        return { body: { ok: true, removedMaterials: 2, removedSchedules: 1 } }
      }
      return { status: 404, body: { detail: 'not found' } }
    })

    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    const deleteBtn = wrapper.findAll('.course-actions button').find((b) => b.text().includes('删除课程'))
    await deleteBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(confirmSpy).toHaveBeenCalled()
    expect(deleted).toBe(true)
    expect(wrapper.text()).not.toContain('日常系列')

    vi.unstubAllGlobals()
  })
})

describe('Admin.vue checkin management', () => {
  let fetchCalls = []

  beforeEach(() => {
    fetchCalls = []
    mockFetch((url, options) => {
      fetchCalls.push({ url, method: options?.method || 'GET' })
      if (url === '/api/admin/library' && (!options.method || options.method === 'GET')) return defaultLibrary()
      if (url === '/api/admin/courses' && (!options.method || options.method === 'GET')) return defaultCourses()
      if (url.match(/^\/api\/admin\/courses\/\d+$/) && (!options.method || options.method === 'GET')) return courseDetail(Number(url.split('/').pop()))
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) return defaultScoring()
      if (url === '/api/admin/schedule' && options.method === 'POST') {
        return {
          body: {
            added: 2,
            scheduled: [
              { date: '2026-09-20', materialIds: [1] },
              { date: '2026-09-21', materialIds: [2] },
            ],
          },
        }
      }
      if (url.match(/^\/api\/admin\/schedule\?month=/) && (!options.method || options.method === 'GET')) {
        return {
          body: {
            days: [
              { date: '2026-09-14', checked: false, materials: [{ id: 1, title: '日常问候', courseName: '日常系列' }] },
            ],
          },
        }
      }
      if (url.match(/^\/api\/admin\/schedule\?month=/) && options.method === 'DELETE') {
        return { body: { ok: true, removed: 2 } }
      }
      if (url.match(/^\/api\/admin\/day\/[\d-]+$/) && options.method === 'DELETE') {
        return { body: { ok: true, removed: 1 } }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('creates schedule and shows scheduled days', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    const inputs = wrapper.findAll('.checkin-card input[type="date"]')
    await inputs[0].setValue('2026-09-20')
    await inputs[1].setValue('2026-09-21')

    const select = wrapper.find('.checkin-card select')
    await select.setValue('1')

    const scheduleBtn = wrapper.findAll('.checkin-card button').find((b) => b.text() === '添加课程')
    await scheduleBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(wrapper.text()).toContain('已安排 2 个素材')
    expect(wrapper.text()).toContain('2026-09-20')
    expect(wrapper.text()).toContain('2026-09-21')

    const scheduleCall = fetchCalls.find((c) => c.method === 'POST' && c.url === '/api/admin/schedule')
    expect(scheduleCall).toBeTruthy()
  })

  it('clears a day after confirm', async () => {
    const confirmSpy = vi.fn().mockReturnValue(true)
    vi.stubGlobal('confirm', confirmSpy)

    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    expect(wrapper.text()).toContain('日常问候')

    const clearBtn = wrapper.findAll('.day-actions button').find((b) => b.text() === '清空当天')
    await clearBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(confirmSpy).toHaveBeenCalled()

    const deleteCall = fetchCalls.find((c) => c.method === 'DELETE' && c.url.match(/^\/api\/admin\/day\/[\d-]+$/))
    expect(deleteCall).toBeTruthy()

    vi.unstubAllGlobals()
  })

  it('clears a month after confirm', async () => {
    const confirmSpy = vi.fn().mockReturnValue(true)
    vi.stubGlobal('confirm', confirmSpy)

    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    const clearBtn = wrapper.findAll('.calendar-section button').find((b) => b.text() === '清空当月')
    await clearBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(confirmSpy).toHaveBeenCalled()

    const deleteCall = fetchCalls.find((c) => c.method === 'DELETE' && c.url.match(/^\/api\/admin\/schedule\?month=/))
    expect(deleteCall).toBeTruthy()

    vi.unstubAllGlobals()
  })
})
