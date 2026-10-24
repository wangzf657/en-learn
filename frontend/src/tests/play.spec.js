import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithRouter, mockFetch, restoreFetch, dispatchTimeUpdate } from './helpers.js'

vi.mock('../utils/recorder.js', () => ({
  startRecording: vi.fn(),
}))

import Play from '../views/Play.vue'
import { startRecording } from '../utils/recorder.js'

// V2.0 提炼式练习卡(四板)
const sampleSubtitle = {
  words: [
    { w: 'doing', zh: '做；进行', note: 'How you doing 是美式问候' },
    { w: 'get started', zh: '开始' },
  ],
  sentences: [
    { start: 1.2, end: 4.5, en: 'How you doing?', zh: '你好吗？' },
    { start: 5.0, end: 8.0, en: "I'm doing great.", zh: '我很好。' },
  ],
  dialogues: [
    {
      scene: '见面问候',
      lines: [
        { speaker: 'parent', en: 'How you doing?', zh: '你好吗？' },
        { speaker: 'child', en: "I'm doing great, thanks!", zh: '我很好，谢谢！' },
      ],
      tip: '见面时互相问一遍',
    },
  ],
  guide: {
    goal: '听懂 How you doing，会说 I\'m doing great',
    before: ['跟孩子说：今天学怎么用英语打招呼'],
    after: ['How you doing 是什么意思？'],
  },
}

const sampleDay = {
  date: '2026-09-14',
  checked: false,
  materials: [
    { id: 1, title: '日常问候', videoUrl: '/mock/empty.mp4', srtUrl: '/api/materials/1/srt', subtitle: sampleSubtitle },
  ],
}

// 旧格式字幕(只有全量 sentences):练习面板的短句板照常渲染,验证兼容
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
<font color="#ffff00">How</font> you doing?

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

  it('renders practice panel: word chips, key sentences, dialogue (V2.0)', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    expect(wrapper.findAll('.tab').length).toBe(2)
    expect(wrapper.findAll('.word-chip').length).toBe(2)

    const cards = wrapper.findAll('.sentence-card')
    expect(cards.length).toBe(2)
    expect(cards[0].find('.en').text()).toBe('How you doing?')

    expect(wrapper.findAll('.line').length).toBe(2)
    expect(wrapper.findAll('.repeat-mini').length).toBe(1) // 每段对话一个「跟读本段」按钮
    expect(wrapper.text()).toContain('【见面问候】')
  })

  it('switches to the guide tab and shows the parent script', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    await wrapper.findAll('.tab')[1].trigger('click')
    expect(wrapper.find('.goal-card').text()).toContain('听懂 How you doing')
    expect(wrapper.text()).toContain('跟孩子说：今天学怎么用英语打招呼')
    expect(wrapper.text()).toContain('How you doing 是什么意思？')
    expect(wrapper.find('.sentence-card').exists()).toBe(false)

    await wrapper.findAll('.tab')[0].trigger('click')
    expect(wrapper.find('.sentence-card').exists()).toBe(true)
  })

  it('clicking a word chip opens the repeat modal with the word as reference', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    await wrapper.findAll('.word-chip')[0].trigger('click')
    expect(wrapper.find('.repeat-modal').exists()).toBe(true)
    expect(wrapper.find('.repeat-modal').text()).toContain('doing')

    await wrapper.find('.repeat-modal .icon-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.repeat-modal').exists()).toBe(false)
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

  it('switches materials via compact number chips and updates the practice panel', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-16' } }, '/play/2026-09-16')

    const chips = wrapper.findAll('.chip')
    expect(chips.length).toBe(2)
    // 紧凑分集:只显示序号,全集名进 title 悬停
    expect(chips[0].text()).toBe('1')
    expect(chips[1].text()).toBe('2')
    expect(chips[1].attributes('title')).toBe('餐厅对话')
    expect(chips[0].classes()).toContain('active')
    // 标题行显示选中素材的完整名称
    expect(wrapper.find('.drawer-title').text()).toBe('点餐用语')
    expect(wrapper.findAll('.sentence-card')[0].find('.en').text()).toBe('Can I have a menu?')

    await chips[1].trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(wrapper.findAll('.chip')[1].classes()).toContain('active')
    expect(wrapper.find('.drawer-title').text()).toBe('餐厅对话')
    expect(wrapper.findAll('.sentence-card')[0].find('.en').text()).toBe('Table for two.')
  })

  it('loads SRT cues and switches subtitle style via select (size fixed to large)', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')
    await new Promise((r) => setTimeout(r, 10))

    const overlay = wrapper.findComponent({ name: 'SubtitleOverlay' })
    expect(overlay.exists()).toBe(true)
    // 默认清晰字幕
    expect(overlay.classes()).toContain('sub-clean')
    expect(overlay.classes()).not.toContain('sub-off')
    // 字号固定为“大”,不再提供下拉
    expect(overlay.classes()).toContain('sub-size-lg')
    expect(wrapper.find('.size-select').exists()).toBe(false)

    await wrapper.find('.style-select').setValue('sub-opaque')
    expect(overlay.classes()).toContain('sub-opaque')
    expect(overlay.classes()).not.toContain('sub-off')
    expect(overlay.classes()).toContain('sub-size-lg')

    // 设置持久化,刷新后仍生效
    expect(localStorage.getItem('enlearn.subtitleStyle')).toBe('sub-opaque')
    expect(localStorage.getItem('enlearn.subtitleSize')).toBeNull()
  })

  it('overlay cue comes from srt (not embedded JSON) and renders karaoke font tags', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')
    await new Promise((r) => setTimeout(r, 10))

    await wrapper.find('.style-select').setValue('sub-clean')
    const video = wrapper.find('video').element
    await dispatchTimeUpdate(video, 2)

    const cue = wrapper.find('.subtitle-cue')
    expect(cue.exists()).toBe(true)
    expect(cue.element.innerHTML).toContain('<font color="#ffff00">How</font>')
    expect(cue.text()).toContain('you doing?')
  })

  it('does not fetch srt when material has no srtUrl (no sibling .srt)', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-16' } }, '/play/2026-09-16')
    await new Promise((r) => setTimeout(r, 10))

    // material 2 有 srtUrl 已请求;切到 material 3(srtUrl:null)不发 srt 请求
    await wrapper.findAll('.chip')[1].trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(fetchCalls.some((c) => c.url === '/api/materials/2/srt')).toBe(true)
    expect(fetchCalls.some((c) => c.url === '/api/materials/3/srt')).toBe(false)
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
