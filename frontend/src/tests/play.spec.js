import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithRouter, mockFetch, restoreFetch, dispatchTimeUpdate } from './helpers.js'

vi.mock('../utils/recorder.js', () => ({
  startRecording: vi.fn(),
}))

import Play from '../views/Play.vue'
import { startRecording } from '../utils/recorder.js'

const sampleSubtitle = {
  sentences: [
    { start: 1.2, end: 4.5, en: 'How you doing?', zh: '你好吗？', words: [{ w: 'doing', phonetic: 'ˈduːɪŋ', note: '美式问候' }] },
    { start: 5.0, end: 8.0, en: "I'm doing great.", zh: '我很好。' },
    { start: 8.5, end: 12.0, en: "Let's get started.", zh: '我们开始吧。' },
  ],
}

const sampleDay = {
  date: '2026-09-14',
  checked: false,
  materials: [
    { id: 1, title: '日常问候', videoUrl: '/mock/empty.mp4', srtUrl: '/api/materials/1/srt', subtitle: sampleSubtitle },
  ],
}

const multiMaterialDay = {
  date: '2026-09-16',
  checked: false,
  materials: [
    { id: 2, title: '点餐用语', videoUrl: '/mock/empty.mp4', srtUrl: '/api/materials/2/srt', subtitle: { sentences: [{ start: 1, end: 3, en: 'Can I have a menu?', zh: '菜单？' }] } },
    { id: 3, title: '餐厅对话', videoUrl: '/mock/empty.mp4', srtUrl: null, subtitle: { sentences: [{ start: 1, end: 3, en: 'Table for two.', zh: '两人桌。' }] } },
  ],
}

function makeScoreResponse(reference) {
  const words = reference ? reference.match(/\b[\w']+\b/g) || ['hello'] : ['hello']
  return {
    accuracy_score: 82.5,
    fluency_score: 78,
    completeness_score: 90,
    word_scores: words.map((w) => ({
      word: w,
      accuracy_score: 85,
      expected_phonemes: 'h ə l oʊ',
      actual_phonemes: 'h ə l oʊ',
      phoneme_scores: [80],
    })),
  }
}

function srtResponse(text) {
  return new Response(text, { status: 200, headers: { 'Content-Type': 'text/plain' } })
}

const sampleSrt = `1
00:00:01,200 --> 00:00:04,500
How you doing?

2
00:00:05,000 --> 00:00:08,000
I'm doing great.`

describe('Play.vue core interactions', () => {
  let fetchCalls = []
  let origCreateObjectURL
  let origRevokeObjectURL

  beforeEach(() => {
    fetchCalls = []
    localStorage.clear()
    origCreateObjectURL = URL.createObjectURL
    origRevokeObjectURL = URL.revokeObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    startRecording.mockResolvedValue({
      stop: vi.fn().mockResolvedValue(new Blob(['fake wav'], { type: 'audio/wav' })),
    })

    mockFetch((url, options) => {
      fetchCalls.push({ url, method: options?.method || 'GET' })
      if (url === '/api/day/2026-09-14') return { body: sampleDay }
      if (url === '/api/day/2026-09-16') return { body: multiMaterialDay }
      if (url.endsWith('/checkin')) return { body: { ok: true } }
      if (url === '/api/score' && options.method === 'POST') {
        const reference = options.body?.get?.('reference') || 'hello'
        return { body: makeScoreResponse(reference) }
      }
      if (url === '/api/materials/1/srt' || url === '/api/materials/2/srt') return srtResponse(sampleSrt)
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => {
    URL.createObjectURL = origCreateObjectURL
    URL.revokeObjectURL = origRevokeObjectURL
    restoreFetch()
  })

  it('renders sentences and highlights current sentence by video time', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const cards = wrapper.findAll('.sentence-card')
    expect(cards.length).toBe(3)
    expect(cards[0].find('.en').text()).toBe('How you doing?')

    const video = wrapper.find('video').element
    await dispatchTimeUpdate(video, 6.5)
    expect(wrapper.findAll('.sentence-card')[1].classes()).toContain('active')

    await dispatchTimeUpdate(video, 10)
    expect(wrapper.findAll('.sentence-card')[2].classes()).toContain('active')
  })

  it('clicking the timestamp button seeks video to its start and plays', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const video = wrapper.find('video').element
    let played = false
    video.play = () => { played = true; return Promise.resolve() }

    const secondCardBtn = wrapper.findAll('.sentence-card')[1].find('.seek-btn')
    await secondCardBtn.trigger('click')

    expect(video.currentTime).toBe(5.0)
    expect(played).toBe(true)
  })

  it('keeps playing past the clicked timestamp end', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const video = wrapper.find('video').element
    const pauseSpy = vi.fn()
    video.play = () => Promise.resolve()
    video.pause = pauseSpy

    await wrapper.findAll('.sentence-card')[1].find('.seek-btn').trigger('click')
    expect(video.currentTime).toBe(5.0)

    // 新行为:不在句尾自动暂停,越过该句 end 继续往下播
    await dispatchTimeUpdate(video, 7.9)
    await dispatchTimeUpdate(video, 8.0)
    await dispatchTimeUpdate(video, 9.5)
    expect(pauseSpy).not.toHaveBeenCalled()
  })

  it('records repeat in modal: score stays inside the modal, card remains clickable', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const firstCard = wrapper.findAll('.sentence-card')[0]
    expect(firstCard.find('.seek-btn').exists()).toBe(true)

    await firstCard.trigger('click')
    expect(wrapper.find('.repeat-modal').exists()).toBe(true)

    const recordBtn = wrapper.find('.record-btn')
    expect(recordBtn.text()).toBe('点击开始录音')

    await recordBtn.trigger('click')
    await flushPromises()
    expect(startRecording).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.record-btn').text()).toBe('点击停止')

    await wrapper.find('.record-btn').trigger('click')
    await flushPromises()

    // 得分只活在弹窗里,外层卡片不再展示
    const modal = wrapper.find('.repeat-modal')
    expect(modal.find('.score-number').exists()).toBe(true)
    expect(modal.find('.score-stars').exists()).toBe(true)
    expect(modal.text()).toContain('准 83')
    expect(modal.text()).toContain('流 78')
    expect(modal.text()).toContain('完 90')
    expect(modal.findAll('.ws-word').length).toBeGreaterThan(0)
    expect(modal.findAll('.word-good').length).toBeGreaterThan(0)
    expect(modal.find('audio').attributes('src')).toBe('blob:mock')
    expect(modal.find('.playback-btn').exists()).toBe(true)

    expect(firstCard.text()).not.toContain('准确度')
    expect(firstCard.text()).not.toContain('本次得分')
    expect(firstCard.find('.seek-btn').exists()).toBe(true)

    // 关掉弹窗:得分随之消失,数据不出弹窗
    await wrapper.find('.repeat-modal .icon-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.repeat-modal').exists()).toBe(false)
    expect(firstCard.text()).not.toContain('准确度')
  })

  it('shows repeat error in modal without blocking the page', async () => {
    startRecording.mockRejectedValueOnce(new Error('麦克风权限被拒绝'))

    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const firstCard = wrapper.findAll('.sentence-card')[0]
    await firstCard.trigger('click')

    const recordBtn = wrapper.find('.record-btn')
    await recordBtn.trigger('click')
    await flushPromises()

    expect(wrapper.find('.repeat-modal').text()).toContain('麦克风权限被拒绝')
    expect(wrapper.find('video').exists()).toBe(true)
  })

  it('switches materials and updates the sentence panel', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-16' } }, '/play/2026-09-16')

    const chips = wrapper.findAll('.chip')
    expect(chips.length).toBe(2)
    expect(chips[0].classes()).toContain('active')
    expect(wrapper.findAll('.sentence-card')[0].find('.en').text()).toBe('Can I have a menu?')

    await chips[1].trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(wrapper.findAll('.chip')[1].classes()).toContain('active')
    expect(wrapper.findAll('.sentence-card')[0].find('.en').text()).toBe('Table for two.')
  })

  it('loads SRT cues and switches subtitle style and size via selects', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')
    await new Promise((r) => setTimeout(r, 10))

    const overlay = wrapper.findComponent({ name: 'SubtitleOverlay' })
    expect(overlay.exists()).toBe(true)
    expect(overlay.classes()).toContain('sub-cinema')
    expect(overlay.classes()).toContain('sub-size-lg')

    await wrapper.find('.style-select').setValue('sub-opaque')
    expect(overlay.classes()).toContain('sub-opaque')

    await wrapper.find('.size-select').setValue('sub-size-xl')
    expect(overlay.classes()).toContain('sub-size-xl')

    // 设置持久化,刷新后仍生效
    expect(localStorage.getItem('enlearn.subtitleStyle')).toBe('sub-opaque')
    expect(localStorage.getItem('enlearn.subtitleSize')).toBe('sub-size-xl')
  })

  it('clicks manual checkin button, calls checkin endpoint and shows checked badge', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')
    await flushPromises()

    expect(wrapper.text()).toContain('未打卡')
    const checkinBtn = wrapper.findAll('button').find((b) => b.text().includes('已完成打卡'))
    expect(checkinBtn).toBeTruthy()

    await checkinBtn.trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    const checkinCall = fetchCalls.find((c) => c.method === 'POST' && c.url === '/api/day/2026-09-14/checkin')
    expect(checkinCall).toBeTruthy()
    expect(wrapper.text()).toContain('已打卡')
    expect(wrapper.text()).not.toContain('已完成打卡')
  })

  it('does not auto-checkin on timeupdate past 90% or ended event', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')
    await flushPromises()

    const video = wrapper.find('video').element
    await dispatchTimeUpdate(video, 19)
    await new Promise((r) => setTimeout(r, 10))

    let checkinCalls = fetchCalls.filter((c) => c.method === 'POST' && c.url.endsWith('/checkin'))
    expect(checkinCalls.length).toBe(0)

    video.dispatchEvent(new Event('ended'))
    await new Promise((r) => setTimeout(r, 10))

    checkinCalls = fetchCalls.filter((c) => c.method === 'POST' && c.url.endsWith('/checkin'))
    expect(checkinCalls.length).toBe(0)
    expect(wrapper.text()).toContain('未打卡')
  })
})
