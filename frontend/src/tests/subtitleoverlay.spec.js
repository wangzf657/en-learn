import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SubtitleOverlay from '../components/SubtitleOverlay.vue'

// 真实库里的卡拉OK srt:相邻 cue 同句、仅 <font> 高亮词移动
const karaokeCues = [
  { start: 1, end: 1.5, text: '<font color="#ffff00">Eddy</font> rolled onto the school lot.' },
  { start: 1.5, end: 2, text: 'Eddy <font color="#ffff00">rolled</font> onto the school lot.' },
  { start: 5, end: 6, text: 'His tires were new.' },
]

function mountOverlay(props = {}) {
  return mount(SubtitleOverlay, {
    props: { cues: karaokeCues, currentTime: 1.2, enabled: true, styleClass: 'sub-clean', ...props },
  })
}

describe('SubtitleOverlay srt 原样渲染', () => {
  it('把 <font> 高亮渲染成 HTML,而非字面文本', () => {
    const wrapper = mountOverlay()
    const cue = wrapper.find('.subtitle-cue')
    expect(cue.exists()).toBe(true)
    expect(cue.element.innerHTML).toContain('<font color="#ffff00">Eddy</font>')
    expect(cue.text()).not.toContain('<font')
    expect(cue.text()).toContain('Eddy rolled onto the school lot.')
  })

  it('高亮词移动时同一节点原位更新,不重挂载(key 取去标签纯文本)', async () => {
    const wrapper = mountOverlay()
    const el = wrapper.find('.subtitle-cue').element
    await wrapper.setProps({ currentTime: 1.7 })
    const elAfter = wrapper.find('.subtitle-cue').element
    expect(elAfter).toBe(el)
    expect(elAfter.innerHTML).toContain('<font color="#ffff00">rolled</font>')
  })

  it('换句时正常切换到新句', async () => {
    const wrapper = mountOverlay()
    await wrapper.setProps({ currentTime: 5.5 })
    expect(wrapper.find('.subtitle-cue').text()).toBe('His tires were new.')
  })

  it('句间空隙、disabled、无 cue 时都不渲染', async () => {
    const wrapper = mountOverlay({ currentTime: 3 })
    expect(wrapper.find('.subtitle-cue').exists()).toBe(false)

    await wrapper.setProps({ enabled: false, currentTime: 1.2 })
    expect(wrapper.find('.subtitle-cue').exists()).toBe(false)

    await wrapper.setProps({ enabled: true, cues: [] })
    expect(wrapper.find('.subtitle-cue').exists()).toBe(false)
  })

  it('普通 srt 文本照常显示', () => {
    const wrapper = mountOverlay({ cues: [{ start: 0, end: 9, text: 'Hello world' }], currentTime: 1 })
    expect(wrapper.find('.subtitle-cue').text()).toBe('Hello world')
  })
})
