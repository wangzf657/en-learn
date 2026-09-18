import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import Review from '../views/Review.vue'
import { mountWithRouter, mockFetch, restoreFetch } from './helpers.js'

const groups = [
  {
    kind: 'course',
    courseId: 1,
    courseName: 'wow_s1',
    materialId: null,
    title: 'wow_s1',
    files: [{ name: '01_overview.jpg', url: '/api/review/file/1/0/01_overview.jpg', kind: 'image' }],
  },
  {
    kind: 'material',
    courseId: 1,
    courseName: 'wow_s1',
    materialId: 12,
    title: 'beta',
    files: [{ name: 'muddy.pdf', url: '/api/review/file/1/12/muddy.pdf', kind: 'pdf' }],
  },
]

describe('Review.vue', () => {
  beforeEach(() => {
    mockFetch((url) => {
      if (url === '/api/review') return { body: { groups } }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('L1 shows only course cards, no file previews', async () => {
    const { wrapper } = await mountWithRouter(Review, {}, '/review')

    const cards = wrapper.findAll('.course-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].text()).toContain('wow_s1')
    expect(cards[0].text()).toContain('课程资料 1 份 · 素材资料 1 个')

    // 首页不得出现任何文件预览
    expect(wrapper.find('.file-grid').exists()).toBe(false)
    expect(wrapper.find('.file-card').exists()).toBe(false)
    expect(wrapper.find('iframe').exists()).toBe(false)
  })

  it('clicking a course card opens L2 with course + material rows and no previews', async () => {
    const { wrapper } = await mountWithRouter(Review, {}, '/review')
    await wrapper.find('.course-card').trigger('click')

    const rows = wrapper.findAll('.review-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('课程资料')
    expect(rows[0].text()).toContain('wow_s1')
    expect(rows[1].text()).toContain('beta')
    expect(rows[1].text()).toContain('1 份')

    // L2 仍不得出现文件预览
    expect(wrapper.find('.file-grid').exists()).toBe(false)
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('.crumb-current').text()).toBe('wow_s1')
  })

  it('clicking a material row opens L3 with the matching iframe src', async () => {
    const { wrapper } = await mountWithRouter(Review, {}, '/review')
    await wrapper.find('.course-card').trigger('click')
    await wrapper.findAll('.review-row')[1].trigger('click')

    expect(wrapper.find('.group-title').text()).toBe('beta')
    expect(wrapper.find('.file-card iframe').attributes('src')).toBe(
      '/api/review/file/1/12/muddy.pdf',
    )
    expect(wrapper.find('.badge').text()).toBe('素材资料')
  })

  it('course-level row opens L3 with the matching image src', async () => {
    const { wrapper } = await mountWithRouter(Review, {}, '/review')
    await wrapper.find('.course-card').trigger('click')
    await wrapper.findAll('.review-row')[0].trigger('click')

    expect(wrapper.find('.file-card img').attributes('src')).toBe(
      '/api/review/file/1/0/01_overview.jpg',
    )
    expect(wrapper.find('.badge').text()).toBe('课程资料')
  })

  it('back buttons walk L3 → L2 → L1', async () => {
    const { wrapper } = await mountWithRouter(Review, {}, '/review')
    await wrapper.find('.course-card').trigger('click')
    await wrapper.findAll('.review-row')[1].trigger('click')
    expect(wrapper.find('.file-grid').exists()).toBe(true)

    await wrapper.find('.crumb-back').trigger('click')
    expect(wrapper.find('.file-grid').exists()).toBe(false)
    expect(wrapper.findAll('.review-row')).toHaveLength(2)

    await wrapper.find('.crumb-back').trigger('click')
    expect(wrapper.findAll('.review-row')).toHaveLength(0)
    expect(wrapper.findAll('.course-card')).toHaveLength(1)
  })

  it('shows guide text when there is nothing to review', async () => {
    mockFetch(() => ({ body: { groups: [] } }))
    const { wrapper } = await mountWithRouter(Review, {}, '/review')
    expect(wrapper.find('.empty-state h3').text()).toBe('还没有复习资料')
    expect(wrapper.find('.course-card').exists()).toBe(false)
  })

  describe('lightbox', () => {
    const multiGroups = [
      {
        kind: 'material',
        courseId: 1,
        courseName: 'wow_s1',
        materialId: 12,
        title: 'beta',
        files: [
          { name: 'p1.jpg', url: '/api/review/file/1/12/p1.jpg', kind: 'image' },
          { name: 'p2.jpg', url: '/api/review/file/1/12/p2.jpg', kind: 'image' },
          { name: 'p3.pdf', url: '/api/review/file/1/12/p3.pdf', kind: 'pdf' },
        ],
      },
    ]

    async function openL3Lightbox() {
      mockFetch(() => ({ body: { groups: multiGroups } }))
      const { wrapper } = await mountWithRouter(Review, {}, '/review')
      await wrapper.find('.course-card').trigger('click')
      await wrapper.find('.review-row').trigger('click')
      await wrapper.findAll('.file-card')[0].trigger('click')
      return wrapper
    }

    function pressKey(key) {
      window.dispatchEvent(new KeyboardEvent('keydown', { key }))
      return nextTick()
    }

    it('opens a big preview from a file card with name and count', async () => {
      const wrapper = await openL3Lightbox()

      expect(wrapper.find('.review-lightbox').exists()).toBe(true)
      expect(wrapper.find('.lightbox-name').text()).toBe('p1.jpg')
      expect(wrapper.find('.lightbox-count').text()).toBe('1 / 3')
      expect(wrapper.find('img.lightbox-media').attributes('src')).toBe(
        '/api/review/file/1/12/p1.jpg',
      )
    })

    it('switches files with the arrows and arrow keys', async () => {
      const wrapper = await openL3Lightbox()

      await wrapper.find('.lightbox-nav.next').trigger('click')
      expect(wrapper.find('.lightbox-count').text()).toBe('2 / 3')
      expect(wrapper.find('img.lightbox-media').attributes('src')).toBe(
        '/api/review/file/1/12/p2.jpg',
      )

      await wrapper.find('.lightbox-nav.next').trigger('click')
      expect(wrapper.find('.lightbox-count').text()).toBe('3 / 3')
      expect(wrapper.find('iframe.lightbox-frame').attributes('src')).toBe(
        '/api/review/file/1/12/p3.pdf',
      )

      // 末尾循环回第一份
      await pressKey('ArrowRight')
      expect(wrapper.find('.lightbox-count').text()).toBe('1 / 3')
      expect(wrapper.find('img.lightbox-media').attributes('src')).toBe(
        '/api/review/file/1/12/p1.jpg',
      )

      // 开头循环到末尾
      await pressKey('ArrowLeft')
      expect(wrapper.find('.lightbox-count').text()).toBe('3 / 3')
      expect(wrapper.find('iframe.lightbox-frame').attributes('src')).toBe(
        '/api/review/file/1/12/p3.pdf',
      )
    })

    it('closes with Esc and the close button, keeping the grid', async () => {
      const wrapper = await openL3Lightbox()

      await pressKey('Escape')
      expect(wrapper.find('.review-lightbox').exists()).toBe(false)
      expect(wrapper.findAll('.file-card')).toHaveLength(3)

      await wrapper.findAll('.file-card')[1].trigger('click')
      expect(wrapper.find('.review-lightbox').exists()).toBe(true)
      await wrapper.find('.lightbox-close').trigger('click')
      expect(wrapper.find('.review-lightbox').exists()).toBe(false)
      expect(wrapper.findAll('.file-card')).toHaveLength(3)
    })

    it('closes when clicking the backdrop', async () => {
      const wrapper = await openL3Lightbox()

      await wrapper.find('.review-lightbox').trigger('click')
      expect(wrapper.find('.review-lightbox').exists()).toBe(false)
      expect(wrapper.findAll('.file-card')).toHaveLength(3)
    })
  })
})
