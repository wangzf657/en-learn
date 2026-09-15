import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Admin from '../views/Admin.vue'
import { mountWithRouter, mockFetch, restoreFetch } from './helpers.js'

describe('Admin.vue scoring config', () => {
  beforeEach(() => {
    mockFetch((url, options) => {
      if (url === '/api/admin/videos' && options.method === 'GET') {
        return { body: { videos: [] } }
      }
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) {
        return { body: { provider: 'azure', options: { appkey: 'ak', secret: 'sk' }, providers: ['mock', 'azure'] } }
      }
      if (url === '/api/admin/scoring' && options.method === 'PUT') {
        return { body: { ok: true } }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('loads current scoring config and saves changes', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    expect(wrapper.text()).toContain('发音评分服务')

    const select = wrapper.find('.scoring-card select')
    expect(select.element.value).toBe('azure')

    const inputs = wrapper.findAll('.scoring-card input')
    expect(inputs[0].element.value).toBe('ak')
    expect(inputs[1].element.value).toBe('sk')

    await select.setValue('mock')
    const saveBtn = wrapper.findAll('.scoring-card button').find((b) => b.text() === '保存')
    await saveBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(wrapper.text()).toContain('已保存')
  })
})

describe('Admin.vue monthly import', () => {
  beforeEach(() => {
    mockFetch((url, options) => {
      if (url === '/api/admin/videos' && (!options.method || options.method === 'GET')) {
        return { body: { videos: [] } }
      }
      if (url === '/api/admin/scoring' && (!options.method || options.method === 'GET')) {
        return { body: { provider: 'mock', options: {}, providers: ['mock'] } }
      }
      if (url === '/api/admin/videos/import' && options.method === 'POST') {
        return {
          body: {
            imported: [
              { id: 10, date: '2026-09-01', title: '第一课', updated: false },
              { id: 11, date: '2026-09-02', title: '第二课', updated: true },
            ],
            skipped: [{ file: '03_nosub.json', reason: '缺少对应视频' }],
          },
        }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('submits monthly import and shows imported and skipped lists', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await flushPromises()

    const pathInput = wrapper.find('.import-card input[type="text"]')
    const monthInput = wrapper.find('.import-card input[type="month"]')
    await pathInput.setValue('D:\\videos\\2026-09')
    await monthInput.setValue('2026-09')

    const importBtn = wrapper.findAll('.import-card button').find((b) => b.text().includes('导入'))
    await importBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))

    expect(wrapper.text()).toContain('导入成功 2 条')
    expect(wrapper.text()).toContain('2026-09-01')
    expect(wrapper.text()).toContain('第二课')
    expect(wrapper.text()).toContain('新增')
    expect(wrapper.text()).toContain('覆盖')
    expect(wrapper.text()).toContain('跳过 1 条')
    expect(wrapper.text()).toContain('03_nosub.json')
    expect(wrapper.text()).toContain('缺少对应视频')
  })
})
