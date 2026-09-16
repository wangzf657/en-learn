import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Home from '../views/Home.vue'
import { mountWithRouter, mockFetch, restoreFetch } from './helpers.js'

describe('Home.vue calendar', () => {
  beforeEach(() => {
    mockFetch((url) => {
      if (url.startsWith('/api/calendar?month=')) {
        return {
          body: {
            days: [
              { date: '2026-09-14', materialId: 1, title: '日常问候', checked: false, materialCount: 1 },
            ],
          },
        }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('renders calendar cells and shows video title on matching date', async () => {
    const { wrapper } = await mountWithRouter(Home, {}, '/')
    expect(wrapper.find('.calendar').exists()).toBe(true)
    const cell = wrapper.findAll('.day-cell').find((c) => c.find('.day-title').exists())
    expect(cell).toBeTruthy()
    expect(cell.find('.day-title').text()).toBe('日常问候')
  })
})
