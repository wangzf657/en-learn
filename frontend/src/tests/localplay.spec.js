import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mountWithRouter, mockFetch, restoreFetch, dispatchTimeUpdate } from './helpers.js'
import LocalPlay from '../views/LocalPlay.vue'

describe('LocalPlay.vue course playback', () => {
  const courses = [
    { id: 1, name: 'Course A', materialCount: 2, readCount: 0, dates: [] },
  ]

  const materials = [
    {
      id: 101,
      title: 'Lesson 1',
      relPath: 'a/lesson1.mp4',
      sentenceCount: 1,
      read: false,
      readAt: null,
      dates: [],
      subtitle: {
        sentences: [{ start: 1, end: 3, en: 'Hello', zh: '你好' }],
      },
    },
  ]

  let fullscreenElement = null
  let requestFullscreenSpy
  let exitFullscreenSpy
  let originalRequestFullscreen
  let originalExitFullscreen

  beforeEach(() => {
    mockFetch((url) => {
      if (url === '/api/admin/courses') {
        return { status: 200, body: { courses } }
      }
      if (url === '/api/admin/courses/1') {
        return { status: 200, body: { id: 1, name: 'Course A', materials } }
      }
      if (url === '/api/materials/101/srt') {
        return { status: 200, body: '1\n00:00:01,000 --> 00:00:03,000\nHello\n' }
      }
      return { status: 404, body: { detail: 'not found' } }
    })

    fullscreenElement = null
    requestFullscreenSpy = vi.fn(async function () {
      fullscreenElement = this
      document.fullscreenElement = this
      document.dispatchEvent(new Event('fullscreenchange'))
    })
    exitFullscreenSpy = vi.fn(async () => {
      fullscreenElement = null
      document.fullscreenElement = null
      document.dispatchEvent(new Event('fullscreenchange'))
    })
    originalRequestFullscreen = Element.prototype.requestFullscreen
    originalExitFullscreen = document.exitFullscreen
    Element.prototype.requestFullscreen = requestFullscreenSpy
    document.exitFullscreen = exitFullscreenSpy
  })

  afterEach(() => {
    restoreFetch()
    Element.prototype.requestFullscreen = originalRequestFullscreen
    document.exitFullscreen = originalExitFullscreen
    document.fullscreenElement = null
  })

  it('lists courses and plays material on click', async () => {
    const { wrapper } = await mountWithRouter(LocalPlay, {}, '/local')

    const courseItems = wrapper.findAll('.course-group')
    expect(courseItems.length).toBe(1)
    expect(courseItems[0].find('.course-name').text()).toBe('Course A')

    await courseItems[0].find('.course-header').trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    const materialItems = wrapper.findAll('.material-item')
    expect(materialItems.length).toBe(1)
    expect(materialItems[0].find('.material-title').text()).toBe('Lesson 1')

    await materialItems[0].trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    const video = wrapper.find('video')
    expect(video.exists()).toBe(true)
    expect(video.element.src).toContain('/api/materials/101/stream')

    const sentences = wrapper.findAll('.sentence-card')
    expect(sentences.length).toBe(1)
    expect(sentences[0].find('.en').text()).toBe('Hello')
  })

  it('shows an empty state when course library is empty', async () => {
    mockFetch(() => ({ status: 200, body: { courses: [] } }))
    const { wrapper } = await mountWithRouter(LocalPlay, {}, '/local')
    await new Promise((r) => setTimeout(r, 10))

    expect(wrapper.findAll('.course-group').length).toBe(0)
    expect(wrapper.text()).toContain('课程库为空')
  })

  it('switches subtitle style classes', async () => {
    const { wrapper } = await mountWithRouter(LocalPlay, {}, '/local')

    await wrapper.find('.course-header').trigger('click')
    await new Promise((r) => setTimeout(r, 10))
    await wrapper.find('.material-item').trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    const overlay = wrapper.findComponent({ name: 'SubtitleOverlay' })
    expect(overlay.classes()).toContain('sub-clean')

    const offBtn = wrapper.findAll('.style-btn').find((b) => b.text() === '关闭')
    await offBtn.trigger('click')
    expect(overlay.classes()).toContain('sub-off')
  })

  it('plays a sentence segment and pauses at its end', async () => {
    const { wrapper } = await mountWithRouter(LocalPlay, {}, '/local')

    await wrapper.find('.course-header').trigger('click')
    await new Promise((r) => setTimeout(r, 10))
    await wrapper.find('.material-item').trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    const video = wrapper.find('video').element
    const pauseSpy = vi.fn()
    video.play = () => Promise.resolve()
    video.pause = pauseSpy

    await wrapper.find('.sentence-card').trigger('click')
    expect(video.currentTime).toBe(1)

    await dispatchTimeUpdate(video, 2.5)
    expect(pauseSpy).not.toHaveBeenCalled()

    await dispatchTimeUpdate(video, 3)
    expect(pauseSpy).toHaveBeenCalledTimes(1)

    await dispatchTimeUpdate(video, 4)
    expect(pauseSpy).toHaveBeenCalledTimes(1)
  })

  it('toggles sidebar collapsed state', async () => {
    const { wrapper } = await mountWithRouter(LocalPlay, {}, '/local')

    expect(wrapper.find('.play-layout').classes()).not.toContain('sidebar-collapsed')

    const sidebarBtn = wrapper.findAll('.icon-btn').find((b) => b.attributes('title') === '收起面板')
    await sidebarBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(wrapper.find('.play-layout').classes()).toContain('sidebar-collapsed')
  })

  it('toggles fullscreen on the play stage', async () => {
    const { wrapper } = await mountWithRouter(LocalPlay, {}, '/local')

    const fullscreenBtn = wrapper.findAll('.icon-btn').find((b) => b.attributes('title') === '全屏播放')
    await fullscreenBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(requestFullscreenSpy).toHaveBeenCalled()

    const exitBtn = wrapper.findAll('.icon-btn').find((b) => b.attributes('title') === '退出全屏')
    await exitBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(exitFullscreenSpy).toHaveBeenCalled()
  })
})
