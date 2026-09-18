// 浏览器端 TTS 音色/语速配置:用 localStorage 持久化,供朗读与设置页共用
const STORAGE_KEY = 'enlearn:tts'
const RATE_DEFAULT = 0.9
const LANG = 'en-US'

function readSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { voiceURI: '', rate: RATE_DEFAULT }
    const data = JSON.parse(raw)
    return {
      voiceURI: typeof data.voiceURI === 'string' ? data.voiceURI : '',
      rate: typeof data.rate === 'number' ? data.rate : RATE_DEFAULT,
    }
  } catch {
    return { voiceURI: '', rate: RATE_DEFAULT }
  }
}

export function loadTtsSettings() {
  return readSettings()
}

export function saveTtsSettings(patch) {
  const next = { ...readSettings(), ...patch }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // ignore
  }
  return next
}

// 返回本机所有以 en 开头的合成音;jsdom/测试无 getVoices 时安全返回空数组
export function listEnglishVoices() {
  if (!('speechSynthesis' in window)) return []
  const synth = window.speechSynthesis
  if (!synth || typeof synth.getVoices !== 'function') return []
  return (synth.getVoices() || []).filter(
    (v) => v && typeof v.lang === 'string' && v.lang.toLowerCase().startsWith('en'),
  )
}

export function resolveVoice(voiceURI) {
  if (!voiceURI) return null
  return listEnglishVoices().find((v) => v.voiceURI === voiceURI) || null
}

// 给已创建的 utterance 应用配置的音色 + 语速,onend/onerror 由调用方自行设置
export function configureUtterance(utter) {
  const s = readSettings()
  utter.lang = LANG
  utter.rate = s.rate
  const voice = resolveVoice(s.voiceURI)
  if (voice) utter.voice = voice
  return utter
}

// 设置页试听:显式指定音色/语速,不写回配置
export function preview(text, { voiceURI, rate } = {}) {
  if (!('speechSynthesis' in window) || !text) return
  const synth = window.speechSynthesis
  synth.cancel()
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = LANG
  utter.rate = typeof rate === 'number' ? rate : RATE_DEFAULT
  const voice = resolveVoice(voiceURI)
  if (voice) utter.voice = voice
  synth.speak(utter)
}

// 预热:用指定(或当前保存)音色静默播一个空句,触发引擎初始化,消除首次朗读/试听的延迟。
// 对本地音色有效(引擎冷启动);同时 resume() 规避 Chrome 长期闲置后首句不出声的问题。
export function warmupTts({ voiceURI } = {}) {
  if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') return
  const synth = window.speechSynthesis
  if (!synth) return
  try {
    if (typeof synth.resume === 'function') synth.resume()
    const utter = new SpeechSynthesisUtterance(' ')
    utter.volume = 0
    utter.rate = 1
    utter.pitch = 1
    const voice = resolveVoice(voiceURI)
    if (voice) utter.voice = voice
    else utter.lang = LANG
    synth.speak(utter)
  } catch {
    // 引擎不可用时静默忽略
  }
}