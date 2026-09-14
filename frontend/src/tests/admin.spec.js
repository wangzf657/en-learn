import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Admin from '../views/Admin.vue'
import { mountWithRouter, mockFetch, restoreFetch } from './helpers.js'

describe('Admin.vue form validation', () => {
  beforeEach(() => {
    mockFetch((url, options) => {
      if (url === '/api/admin/videos' && options.method === 'GET') {
        return { body: { videos: [] } }
      }
      if (url === '/api/admin/validate-path' && options.method === 'POST') {
        return { body: { exists: true, size: 12345678 } }
      }
      if (url === '/api/admin/videos' && options.method === 'POST') {
        return { status: 409, body: { detail: '日期 2026-09-14 已经存在' } }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('shows path validation result and displays backend error detail', async () => {
    const { wrapper } = await mountWithRouter(Admin, {}, '/admin')
    await wrapper.find('button').trigger('click')

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('2026-09-14')
    await inputs[2].setValue('D:\\videos\\demo.mp4')

    const validateBtn = wrapper.findAll('button').find((b) => b.text() === '验证路径')
    await validateBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))
    expect(wrapper.text()).toContain('文件存在')

    const saveBtn = wrapper.findAll('button').find((b) => b.text() === '保存')
    await saveBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 50))
    expect(wrapper.text()).toContain('日期 2026-09-14 已经存在')
  })
})
