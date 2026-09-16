import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'

vi.mock('../utils/recorder.js', () => ({ startRecording: vi.fn() }))
vi.mock('../api.js', () => ({ scoringApi: { score: vi.fn() } }))

import RepeatModal from '../components/RepeatModal.vue'
import { startRecording } from '../utils/recorder.js'
import { scoringApi } from '../api.js'

const sentence = {
  en: 'Hello world',
  zh: '你好世界',
  words: [
    { w: 'hello', phonetic: 'həˈloʊ', note: '打招呼' },
    { w: 'world', phonetic: 'wɜːrld', note: '世界' },
  ],
}

describe('RepeatModal 朗读 / 文本同步 / 录音切换', () => {
  let synth
  let utterances
  let origCreateObjectURL
  let origRevokeObjectURL
  let origPlay
  let origPause
  let playMock

  // 弹窗在 window 上挂 keydown,测试间必须卸载,否则空格会打到上一个组件
  enableAutoUnmount(afterEach)

  const mountModal = () => mount(RepeatModal, { props: { open: true, sentence } })

  const space = () => window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ' }))

  beforeEach(() => {
    utterances = []
    synth = { speak: vi.fn((u) => utterances.push(u)), cancel: vi.fn() }
    window.speechSynthesis = synth
    window.SpeechSynthesisUtterance = class {
      constructor(text) {
        this.text = text
      }
    }
    // jsdom/happy-dom 没实现 ObjectURL 与媒体播控,只在本文件范围内打桩
    origCreateObjectURL = URL.createObjectURL
    origRevokeObjectURL = URL.revokeObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    origPlay = window.HTMLMediaElement.prototype.play
    origPause = window.HTMLMediaElement.prototype.pause
    playMock = vi.fn(() => Promise.resolve())
    window.HTMLMediaElement.prototype.play = playMock
    window.HTMLMediaElement.prototype.pause = vi.fn()

    startRecording.mockResolvedValue({ stop: vi.fn(async () => 'blob') })
    scoringApi.score.mockResolvedValue({
      accuracy_score: 80,
      fluency_score: 80,
      completeness_score: 80,
      word_scores: [],
    })
  })

  afterEach(() => {
    delete window.speechSynthesis
    delete window.SpeechSynthesisUtterance
    URL.createObjectURL = origCreateObjectURL
    URL.revokeObjectURL = origRevokeObjectURL
    window.HTMLMediaElement.prototype.play = origPlay
    window.HTMLMediaElement.prototype.pause = origPause
    vi.clearAllMocks()
  })

  it('默认把完整台词填进文本框,词块展示音标与笔记', () => {
    const wrapper = mountModal()
    expect(wrapper.find('#repeat-custom').element.value).toBe('Hello world')
    expect(wrapper.find('.wc-phonetic').text()).toBe('/həˈloʊ/')
    expect(wrapper.find('.wc-note').text()).toBe('打招呼')
  })

  it('手改文本 → 台词框保持完整台词;出现恢复按钮,点击后还原', async () => {
    const wrapper = mountModal()
    await wrapper.find('#repeat-custom').setValue('hello')
    // 台词框始终展示完整台词,不随文本框变化
    expect(wrapper.find('.target-en').text()).toBe('Hello world')
    expect(wrapper.find('#repeat-custom').element.value).toBe('hello')
    expect(wrapper.find('.restore-btn').exists()).toBe(true)

    await wrapper.find('.restore-btn').trigger('click')
    expect(wrapper.find('#repeat-custom').element.value).toBe('Hello world')
    expect(wrapper.find('.restore-btn').exists()).toBe(false)
  })

  it('点词块播放该词(不改文本框),再点一次停止', async () => {
    const wrapper = mountModal()
    const chips = () => wrapper.findAll('.word-chip-btn')

    await chips()[1].trigger('click')
    expect(utterances.map((u) => u.text)).toEqual(['world'])
    expect(utterances[0].lang).toBe('en-US')
    expect(utterances[0].rate).toBe(0.9)
    expect(wrapper.find('#repeat-custom').element.value).toBe('Hello world')
    expect(chips()[1].classes()).toContain('speaking')
    expect(chips()[0].classes()).not.toContain('speaking')

    await chips()[1].trigger('click')
    expect(synth.cancel).toHaveBeenCalled()
    await flushPromises()
    expect(chips()[1].classes()).not.toContain('speaking')

    // 再点一次:重新播放,播完状态归位
    await chips()[1].trigger('click')
    expect(utterances.map((u) => u.text)).toEqual(['world', 'world'])
    utterances[1].onend()
    await flushPromises()
    expect(chips()[1].classes()).not.toContain('speaking')
  })

  it('点台词区域朗读整句:单条 utterance,lang=en-US / rate=0.9,再点一次取消', async () => {
    const wrapper = mountModal()
    const target = () => wrapper.find('.target-section')

    await target().trigger('click')
    expect(utterances[0].text).toBe('Hello world')
    expect(utterances[0].lang).toBe('en-US')
    expect(utterances[0].rate).toBe(0.9)
    expect(target().classes()).toContain('speaking')

    await target().trigger('click')
    expect(synth.cancel).toHaveBeenCalled()
    expect(wrapper.find('.target-section').classes()).not.toContain('speaking')
  })

  it('朗读台词与词块互斥:读句后读词会 cancel 上一条', async () => {
    const wrapper = mountModal()
    const target = () => wrapper.find('.target-section')

    await target().trigger('click')
    expect(utterances.map((u) => u.text)).toEqual(['Hello world'])
    expect(target().classes()).toContain('speaking')

    await wrapper.findAll('.word-chip-btn')[0].trigger('click')
    expect(synth.cancel).toHaveBeenCalled()
    expect(utterances.map((u) => u.text)).toEqual(['Hello world', 'hello'])
    expect(target().classes()).not.toContain('speaking')
    expect(wrapper.findAll('.word-chip-btn')[0].classes()).toContain('speaking')
  })

  it('空格与按钮都是「按一下开始、再按一下结束」', async () => {
    const wrapper = mountModal()
    expect(wrapper.find('.record-btn').text()).toBe('点击开始录音')

    space()
    await flushPromises()
    expect(startRecording).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.record-btn').text()).toBe('点击停止')

    space()
    await flushPromises()
    expect(synth.cancel).not.toHaveBeenCalled() // 空格不应误触发朗读
    expect(wrapper.find('.score-number').exists()).toBe(true)
  })

  it('录音后出现回放播放器:点一下播放、再点停止;关闭时释放 blob', async () => {
    const wrapper = mountModal()
    space()
    await flushPromises()
    space()
    await flushPromises()

    expect(wrapper.find('.score-number').exists()).toBe(true)
    const audio = wrapper.find('audio')
    expect(audio.exists()).toBe(true)
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(audio.attributes('src')).toBe('blob:mock')

    const btn = () => wrapper.find('.playback-btn')
    expect(btn().text()).toBe('回放')

    await btn().trigger('click')
    expect(playMock).toHaveBeenCalled()
    expect(btn().classes()).toContain('playing')
    expect(btn().text()).toBe('停止')

    await btn().trigger('click')
    expect(btn().classes()).not.toContain('playing')

    wrapper.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })

  it('无 speechSynthesis 时点击朗读不报错', async () => {
    delete window.speechSynthesis
    const wrapper = mountModal()
    await wrapper.find('.target-section').trigger('click')
    await wrapper.findAll('.word-chip-btn')[0].trigger('click')
    expect(wrapper.find('.target-en').text()).toBe('Hello world')
  })
})
