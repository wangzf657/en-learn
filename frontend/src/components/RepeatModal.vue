<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { startRecording } from '../utils/recorder.js'
import { scoringApi } from '../api.js'
import { configureUtterance } from '../utils/tts.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  sentence: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close'])

const customText = ref('')
const status = ref('idle')
const result = ref(null)
const error = ref('')
const recordingController = ref(null)
const recordedUrl = ref('')
const audioEl = ref(null)
const playingRecording = ref(false)
let alive = true

const defaultText = computed(() => props.sentence?.en || '')
const reference = computed(() => customText.value.trim() || defaultText.value)

// 把整句按常用标点切成独立断句(保留标点),用于逐句朗读 + 选中快速填入
const segments = computed(() => {
  const text = (defaultText.value || '').trim()
  if (!text) return []
  return text
    .split(/(?<=[.,!?;:…—])\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
})

// 正在朗读的条目:'sentence' | 'words' | 'custom' | null
const speakingKey = ref(null)

const overallScore = computed(() => {
  if (!result.value) return 0
  const r = result.value
  return Math.round((r.accuracy_score + r.fluency_score + r.completeness_score) / 3)
})

const stars = computed(() => {
  const count = Math.min(5, Math.max(0, Math.round(overallScore.value / 20)))
  return Array.from({ length: 5 }, (_, i) => i < count)
})

function wordScoreClass(score) {
  if (score >= 80) return 'word-good'
  if (score >= 60) return 'word-ok'
  return 'word-bad'
}

// 综合分 → 等级标签 + 颜色档
const levelLabel = computed(() => {
  const s = overallScore.value
  if (s >= 90) return '优秀'
  if (s >= 80) return '良好'
  if (s >= 70) return '一般'
  if (s >= 60) return '及格'
  return '待加强'
})

const levelClass = computed(() => {
  const s = overallScore.value
  if (s >= 90) return 'lvl-excellent'
  if (s >= 80) return 'lvl-good'
  if (s >= 70) return 'lvl-ok'
  if (s >= 60) return 'lvl-pass'
  return 'lvl-bad'
})

function barWidth(v) {
  if (v == null) return '0%'
  return `${Math.min(100, Math.max(0, v))}%`
}

// 词类型徽章:0 多词 / 1 漏词 / 3 错词(2 正常不展示)
const WORD_TYPE_BADGES = {
  0: { label: '多词', cls: 'ws-extra' },
  1: { label: '漏词', cls: 'ws-miss' },
  3: { label: '错词', cls: 'ws-wrong' },
}

function wordTypeBadge(ws) {
  return WORD_TYPE_BADGES[ws.type] || null
}

function hasStress(ws) {
  return typeof ws.stress === 'number' && ws.stress >= 0
}

// 逐词音素:优先用 phonemes(与 phoneme_scores 对齐);退化到 actual_phonemes 整串
function wordPhonemes(ws) {
  if (Array.isArray(ws.phonemes) && ws.phonemes.length) return ws.phonemes
  const ap = ws.actual_phonemes || ''
  return ap ? [ap] : []
}

function phoneClass(score) {
  if (score >= 80) return 'ph-good'
  if (score >= 60) return 'ph-ok'
  return 'ph-bad'
}

const QUALITY_ISSUES = [
  ['volume', '音量偏小'],
  ['clipping', '削波'],
  ['noise', '有噪声'],
  ['cut', '截断'],
  ['too_short', '过短'],
  ['empty_audio', '空音频'],
]

const qualityIssues = computed(() => {
  const aq = result.value?.audio_quality
  if (!aq) return []
  return QUALITY_ISSUES.filter(([key]) => aq[key]).map(([, label]) => label)
})

/* ---------------- 朗读(TTS) ---------------- */

function stopSpeaking() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  speakingKey.value = null
}

function makeUtterance(text, onDone) {
  const utter = configureUtterance(new SpeechSynthesisUtterance(text))
  utter.onend = onDone
  utter.onerror = onDone
  return utter
}

// 点击台词区域即朗读整句,再点一次停止
function toggleSpeakSentence() {
  const key = 'sentence'
  if (speakingKey.value === key) return stopSpeaking()
  if (!('speechSynthesis' in window) || !defaultText.value) return
  const synth = window.speechSynthesis
  synth.cancel()
  speakingKey.value = key
  synth.speak(makeUtterance(defaultText.value, () => {
    if (speakingKey.value === key) speakingKey.value = null
  }))
}

// 点原始台词区:直接填入完整台词并朗读(与词块/断句交互一致)
function fillAndSpeakSentence() {
  customText.value = defaultText.value
  toggleSpeakSentence()
}

// 朗读文本框内容(自定义跟读文本),再点一次停止
function toggleSpeakCustom() {
  const key = 'custom'
  if (speakingKey.value === key) return stopSpeaking()
  if (!('speechSynthesis' in window) || !reference.value) return
  const synth = window.speechSynthesis
  synth.cancel()
  speakingKey.value = key
  synth.speak(makeUtterance(reference.value, () => {
    if (speakingKey.value === key) speakingKey.value = null
  }))
}

// 点词块即播放该词(单条),再点一次停止
function toggleSpeakWord(w, idx) {
  const key = `w-${idx}`
  if (speakingKey.value === key) return stopSpeaking()
  if (!('speechSynthesis' in window) || !w) return
  const synth = window.speechSynthesis
  synth.cancel()
  speakingKey.value = key
  synth.speak(makeUtterance(w, () => {
    if (speakingKey.value === key) speakingKey.value = null
  }))
}

// 点词块:直接填入文本框并朗读
function fillAndSpeakWord(w, idx) {
  customText.value = w
  toggleSpeakWord(w, idx)
}

// 点断句块:直接填入文本框并朗读该段(与词块交互一致)
function fillAndSpeakSegment(i) {
  const seg = segments.value[i]
  if (!seg) return
  customText.value = seg
  toggleSpeakSegment(i)
}

// 点断句块朗读该段,再点一次停止
function toggleSpeakSegment(i) {
  const seg = segments.value[i]
  if (!seg) return
  const key = `seg-${i}`
  if (speakingKey.value === key) return stopSpeaking()
  if (!('speechSynthesis' in window)) return
  const synth = window.speechSynthesis
  synth.cancel()
  speakingKey.value = key
  synth.speak(makeUtterance(seg, () => {
    if (speakingKey.value === key) speakingKey.value = null
  }))
}

/* ---------------- 录音回放(阅后即焚) ---------------- */

function stopPlayback() {
  const a = audioEl.value
  if (a) {
    a.pause?.()
    a.currentTime = 0
  }
  playingRecording.value = false
}

function releaseRecording() {
  stopPlayback()
  if (recordedUrl.value) {
    URL.revokeObjectURL?.(recordedUrl.value)
    recordedUrl.value = ''
  }
}

function togglePlayback() {
  const a = audioEl.value
  if (!a) return
  if (playingRecording.value) {
    a.pause?.()
    playingRecording.value = false
    return
  }
  a.currentTime = 0
  playingRecording.value = true
  a.play?.()?.catch?.(() => {
    playingRecording.value = false
  })
}

function reset() {
  releaseRecording()
  customText.value = defaultText.value
  status.value = 'idle'
  result.value = null
  error.value = ''
  recordingController.value = null
}

function cleanup() {
  const controller = recordingController.value
  if (controller) {
    recordingController.value = null
    controller.stop().catch(() => {})
  }
  releaseRecording()
  stopSpeaking()
}

watch(
  () => props.open,
  (open) => {
    if (open) reset()
    else cleanup()
  },
  { immediate: true },
)

function isInput(el) {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}

function onKeyDown(e) {
  if (!props.open) return
  if (e.key === ' ' && !e.repeat && !isInput(e.target)) {
    e.preventDefault()
    toggleRecording()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  alive = false
  window.removeEventListener('keydown', onKeyDown)
  cleanup()
})

// 切换式录音:空闲→开始,录音中→停止评分,'starting' 时再点即取消启动
function toggleRecording() {
  if (status.value === 'scoring') return
  if (status.value === 'starting') {
    status.value = 'idle'
    return
  }
  if (status.value === 'recording') return stopRecordingFlow()
  startRecordingFlow()
}

async function startRecordingFlow() {
  if (status.value === 'recording' || status.value === 'starting' || status.value === 'scoring') return
  status.value = 'starting'
  error.value = ''
  result.value = null
  try {
    const controller = await startRecording()
    // 启动期间被取消(状态已不是 starting)或组件已卸载,丢弃这次录音
    if (!alive || status.value !== 'starting') {
      try { await controller.stop() } catch {}
      return
    }
    recordingController.value = controller
    status.value = 'recording'
  } catch (e) {
    if (!alive || status.value !== 'starting') return
    recordingController.value = null
    status.value = 'error'
    error.value = e.message
  }
}

async function stopRecordingFlow() {
  const controller = recordingController.value
  if (!controller) {
    status.value = 'idle'
    return
  }
  status.value = 'scoring'
  try {
    const blob = await controller.stop()
    recordingController.value = null
    // 存下这条录音供试听;覆盖前先释放上一条
    releaseRecording()
    recordedUrl.value = URL.createObjectURL?.(blob) || ''
    const res = await scoringApi.score(blob, reference.value)
    if (!alive) return
    result.value = res
    status.value = 'result'
  } catch (e) {
    if (!alive) return
    recordingController.value = null
    status.value = 'error'
    error.value = e.detail || e.message
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <transition name='modal-fade'>
    <div v-if='open' class='repeat-modal'>
      <div class='repeat-card card' role='dialog' aria-modal='true' aria-label='跟读练习'>
        <header class='repeat-header'>
          <h3><span class='header-emoji' aria-hidden='true'>🎤</span>跟读练习</h3>
          <button class='icon-btn' type='button' aria-label='关闭' @click='close'>
            <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'>
              <path d='M18 6L6 18'/>
              <path d='M6 6l12 12'/>
            </svg>
          </button>
        </header>

        <div class='repeat-body'>
          <!-- 左 30% 学习(单词+拆分短句) + 右 70% 操作(台词+跟读+录音+评分) -->
          <div class='content-row'>
            <section class='material-section'>
              <div v-if='sentence.words?.length' class='word-chips'>
                <button
                  v-for='(w, idx) in sentence.words'
                  :key='idx'
                  type='button'
                  class='chip word-chip-btn'
                  :class='{ speaking: speakingKey === `w-${idx}` }'
                  :title='`点按填入并播放 ${w.w}`'
                  @click='fillAndSpeakWord(w.w, idx)'
                >
                  <span class='wc-w'>
                    {{ w.w }}
                    <svg class='speak-hint' width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>
                      <polygon points='11 5 6 9 2 9 2 15 6 15 11 19 11 5'></polygon>
                      <path d='M15.54 8.46a5 5 0 0 1 0 7.07'></path>
                    </svg>
                  </span>
                  <span v-if='w.note' class='wc-note'>{{ w.note }}</span>
                </button>
              </div>

              <div v-if='segments.length' class='word-chips segment-chips'>
                <button
                  v-for='(seg, i) in segments'
                  :key='`seg-${i}`'
                  type='button'
                  class='chip word-chip-btn'
                  :class='{ speaking: speakingKey === `seg-${i}` }'
                  :title='`点击播放并填入：${seg}`'
                  @click='fillAndSpeakSegment(i)'
                >
                  <span class='wc-w seg-line'>
                    <span class='seg-text'>{{ seg }}</span>
                    <svg class='speak-hint' width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>
                      <polygon points='11 5 6 9 2 9 2 15 6 15 11 19 11 5'></polygon>
                      <path d='M15.54 8.46a5 5 0 0 1 0 7.07'></path>
                    </svg>
                  </span>
                </button>
              </div>
            </section>

            <section class='action-section'>
              <div
                class='sentence-line'
                :class='{ speaking: speakingKey === "sentence" }'
                role='button'
                tabindex='0'
                :title='speakingKey === "sentence" ? "停止朗读整句" : "播放并填入整句"'
                @click='fillAndSpeakSentence'
              >
                <p class='sentence-text'>{{ defaultText }}</p>
                <p v-if='sentence.zh' class='target-zh'>{{ sentence.zh }}</p>
              </div>

          <div class='custom-input'>
            <label for='repeat-custom'>跟读文本</label>
            <input
              id='repeat-custom'
              v-model.trim='customText'
              type='text'
              placeholder='输入想跟读的内容'
              @keydown.space.stop
            />
            <button
              type='button'
              class='speak-custom-btn'
              :class='{ speaking: speakingKey === "custom" }'
              :title='speakingKey === "custom" ? "停止朗读" : "朗读文本框内容"'
              :aria-label='speakingKey === "custom" ? "停止朗读" : "朗读文本框内容"'
              @click='toggleSpeakCustom'
            >
              <svg v-if='speakingKey !== "custom"' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <polygon points='11 5 6 9 2 9 2 15 6 15 11 19 11 5'></polygon>
                <path d='M15.54 8.46a5 5 0 0 1 0 7.07'></path>
                <path d='M19.07 4.93a10 10 0 0 1 0 14.14'></path>
              </svg>
              <svg v-else width='12' height='12' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>
                <rect x='7' y='7' width='10' height='10' rx='2'></rect>
              </svg>
              <span>{{ speakingKey === "custom" ? '停' : '读' }}</span>
            </button>
          </div>

          <div class='record-area'>
            <div class='record-row'>
              <button
                class='record-btn'
                type='button'
                :class='{ recording: status === "recording", scoring: status === "scoring" }'
                :disabled='status === "scoring"'
                @click='toggleRecording'
              >
                <span v-if='status === "scoring"' class='spinner'></span>
                <span v-else-if='status === "recording"' class='rec-dot'></span>
                <svg v-else width='22' height='22' viewBox='0 0 24 24' fill='currentColor'>
                  <path d='M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z'/>
                  <path d='M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z'/>
                </svg>
                <span class='record-label'>
                  {{ status === 'recording' ? '点击停止' : status === 'scoring' ? '评分中…' : status === 'starting' ? '准备中…' : '点击开始录音' }}
                </span>
              </button>

              <button
                v-if='recordedUrl'
                type='button'
                class='playback-btn'
                :class='{ playing: playingRecording }'
                :title='playingRecording ? "停止回放" : "听我刚才录的音"'
                @click='togglePlayback'
              >
                <svg v-if='playingRecording' width='14' height='14' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>
                  <rect x='6' y='5' width='4' height='14' rx='1'></rect>
                  <rect x='14' y='5' width='4' height='14' rx='1'></rect>
                </svg>
                <svg v-else width='14' height='14' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>
                  <path d='M8 5v14l11-7z'></path>
                </svg>
                <span>{{ playingRecording ? '停止' : '回放' }}</span>
              </button>
              <audio
                ref='audioEl'
                class='playback-audio'
                :src='recordedUrl'
                preload='metadata'
                @play='playingRecording = true'
                @pause='playingRecording = false'
                @ended='playingRecording = false'
                @error='playingRecording = false'
              ></audio>
            </div>
            <p class='record-hint'>按空格或点击按钮开始,再按一次结束</p>
          </div>

          <div v-if='status === "error"' class='error-detail'>{{ error }}</div>

          <div v-if='status === "result" && result' class='score-result'>
            <div class='score-hero'>
              <div class='score-number'>
                {{ overallScore }}<span class='score-unit'>分</span>
              </div>
              <div class='score-hero-side'>
                <div class='score-stars'>
                  <svg
                    v-for='(filled, i) in stars'
                    :key='i'
                    class='star'
                    :style='{ "--i": i }'
                    width='28'
                    height='28'
                    viewBox='0 0 24 24'
                    :fill='filled ? "currentColor" : "none"'
                    :stroke='filled ? "none" : "currentColor"'
                    stroke-width='2'
                  >
                    <path d='M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z'/>
                  </svg>
                </div>
                <span :class='["score-level", levelClass]'>{{ levelLabel }}</span>
              </div>
            </div>

            <div class='score-dims'>
              <div class='dim'>
                <span class='dim-label'>准 {{ Math.round(result.accuracy_score) }}</span>
                <div class='dim-bar'><span class='dim-fill fill-blue' :style='{ width: barWidth(result.accuracy_score) }'></span></div>
              </div>
              <div class='dim'>
                <span class='dim-label'>流 {{ Math.round(result.fluency_score) }}</span>
                <div class='dim-bar'><span class='dim-fill fill-green' :style='{ width: barWidth(result.fluency_score) }'></span></div>
              </div>
              <div class='dim'>
                <span class='dim-label'>完 {{ Math.round(result.completeness_score) }}</span>
                <div class='dim-bar'><span class='dim-fill fill-orange' :style='{ width: barWidth(result.completeness_score) }'></span></div>
              </div>
            </div>

            <div v-if='result.sample || result.usertext' class='score-asr'>
              <div class='asr-row'>
                <span class='asr-tag asr-std'>标准</span>
                <span class='asr-text'>{{ result.sample || reference }}</span>
              </div>
              <div class='asr-row'>
                <span class='asr-tag asr-you'>你读</span>
                <span class='asr-text' :class='{ "asr-none": !result.usertext }'>{{ result.usertext || '未识别到人声' }}</span>
              </div>
            </div>

            <div class='score-footer'>
              <div v-if='qualityIssues.length' class='score-quality'>
                <span class='q-title'>音质</span>
                <span v-for='(q, i) in qualityIssues' :key='i' class='q-badge'>{{ q }}</span>
              </div>
              <div v-else class='score-quality'>
                <span class='q-title'>音质</span>
                <span class='q-ok'>良好</span>
              </div>
            </div>

            <div class='word-detail'>
              <div
                v-for='(ws, k) in result.word_scores'
                :key='k'
                class='ws-row'
              >
                <span :class='["ws-word", wordScoreClass(ws.accuracy_score)]'>
                  {{ ws.word }}
                  <span v-if='wordTypeBadge(ws)' :class='["ws-badge", wordTypeBadge(ws).cls]'>{{ wordTypeBadge(ws).label }}</span>
                </span>
                <span v-if='hasStress(ws)' :class='["ws-stress", ws.stress === 1 ? "stress-ok" : "stress-bad"]'>
                  {{ ws.stress === 1 ? '重音✓' : '重音✗' }}
                </span>
                <span v-if='wordPhonemes(ws).length' class='ws-phonemes'>
                  <span
                    v-for='(p, pi) in wordPhonemes(ws)'
                    :key='pi'
                    :class='["ph", phoneClass(ws.phoneme_scores[pi])]'
                  >{{ p }}</span>
                </span>
              </div>
            </div>
          </div>
            </section>
          </div>
        </div>
      </div>

      </div>
  </transition>
</template>

<style scoped>
.repeat-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(43, 37, 69, 0.42);
  backdrop-filter: blur(7px);
  -webkit-backdrop-filter: blur(7px);
}

.repeat-card {
  width: 100%;
  max-width: 1200px;
  height: min(880px, calc(100svh - 32px));
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-width: 3px;
}

/* ---------- Header(压缩) ---------- */
.repeat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: linear-gradient(120deg, var(--yellow-bg), var(--pink-bg) 55%, var(--purple-bg));
  border-bottom: 2px solid var(--border);
  flex: none;
}

.repeat-header h3 {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
}

.header-emoji {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #fff;
  font-size: 17px;
  box-shadow: var(--shadow-sm);
  animation: wiggle 3.2s ease-in-out infinite;
}

.repeat-header .icon-btn {
  width: 32px;
  height: 32px;
}

/* ---------- Body ---------- */
.repeat-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ---------- 左 30% 学习区 + 右 70% 操作区 ---------- */
.content-row {
  display: flex;
  gap: 12px;
  flex: 1 1 auto;
  min-height: 0;
}

/* 左 30%:单词 + 拆分短句,固定高度内部滚动 + 快速填入 */
.material-section {
  flex: 0 0 30%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, var(--yellow-bg), var(--pink-bg));
  border: 2px dashed rgba(255, 143, 171, 0.4);
  overflow-y: auto;
  overflow-x: hidden;
}

/* 右 70%:台词原内容 + 跟读 + 录音 + 评分,固定高度不滚动 */
.action-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

/* 右侧整句台词:点击播放并填入(与词块/断句交互一致) */
.sentence-line {
  flex: none;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, var(--yellow-bg), var(--pink-bg));
  border: 2px dashed rgba(255, 143, 171, 0.4);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition),
    transform var(--transition), box-shadow var(--transition);
}

.sentence-line:hover {
  border-color: rgba(255, 143, 171, 0.8);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.sentence-line.speaking {
  background: var(--grad-blue);
  border-color: transparent;
}

.sentence-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
  margin: 0;
  color: var(--ink);
  word-break: break-word;
}

.sentence-line.speaking .sentence-text,
.sentence-line.speaking .target-zh {
  color: #fff;
}

/* 断句块:与词块一致的样式/交互(纵向排列,点击填入并朗读) */
.segment-chips {
  margin-top: 4px;
}

.wc-w.seg-line {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.seg-text {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}

.target-zh {
  font-size: 14px;
  color: var(--muted);
  margin: 4px 0 0;
  line-height: 1.4;
}

/* 关键词区:位于左列学习区内,纵向排列 */
.word-chips {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.word-chip-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  width: 100%;
  padding: 6px 10px;
  border-radius: var(--radius-xs);
  text-align: left;
  color: var(--ink);
  background: var(--purple-bg);
  border: 2px solid transparent;
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition), box-shadow var(--transition);
}

.word-chip-btn:hover {
  border-color: rgba(160, 107, 255, 0.45);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.word-chip-btn.speaking {
  background: #fff;
  border-color: var(--purple);
  box-shadow: 0 0 0 3px rgba(160, 107, 255, 0.18), var(--shadow-sm);
}

.wc-w {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.2;
}

.speak-hint {
  flex: none;
  color: var(--purple);
  opacity: 0;
  transform: translateX(-2px);
  transition: opacity var(--transition), transform var(--transition);
}

.word-chip-btn:hover .speak-hint,
.word-chip-btn.speaking .speak-hint {
  opacity: 0.8;
  transform: none;
}

.wc-note {
  font-size: 12px;
  line-height: 1.3;
  color: var(--muted);
}

/* ---------- 自定义跟读文本(主要教学窗口) ---------- */
.custom-input {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, var(--blue-bg), #fff);
  border: 2px solid rgba(63, 140, 255, 0.22);
  box-shadow: var(--shadow-sm);
}

.custom-input label {
  flex: none;
  font-size: 16px;
  font-weight: 800;
  color: var(--blue);
}

.custom-input input {
  flex: 1;
  min-width: 0;
  min-height: 64px;
  padding: 12px 20px;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.3;
  border-radius: var(--radius-sm);
  background: #fff;
  border: 2px solid var(--border);
}

.custom-input input:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 4px rgba(63, 140, 255, 0.15);
}

.speak-custom-btn {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 56px;
  padding: 8px 16px;
  border-radius: var(--radius-pill);
  font-size: 16px;
  font-weight: 700;
  color: var(--blue);
  background: var(--blue-bg);
  border: 2px solid transparent;
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition), box-shadow var(--transition);
}

.speak-custom-btn:hover {
  border-color: var(--blue);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.speak-custom-btn:active {
  transform: scale(0.96);
}

.speak-custom-btn.speaking {
  color: #fff;
  background: var(--grad-blue);
  border-color: transparent;
  animation: speak-ring 1.1s ease-in-out infinite;
}

/* ---------- 录音长条按钮 ---------- */
.record-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: none;
}

.record-row {
  display: flex;
  align-items: stretch;
  gap: 10px;
  width: 100%;
}

.record-btn {
  position: relative;
  flex: 1;
  height: 52px;
  border-radius: var(--radius-pill);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
  background: var(--grad-blue);
  box-shadow: var(--shadow-blue), var(--shadow-pop);
  transition: transform 180ms var(--ease-bounce), background 200ms ease, box-shadow 200ms ease;
}

.record-btn:hover {
  transform: translateY(-2px);
}

.record-btn:active {
  transform: translateY(1px) scale(0.99);
  box-shadow: var(--shadow-sm);
}

.record-btn.recording {
  background: linear-gradient(180deg, #ff8089, var(--red));
  box-shadow: 0 0 0 8px rgba(255, 95, 109, 0.16);
  animation: pulse 1.2s ease-in-out infinite;
}

.record-btn.scoring {
  background: var(--secondary);
  box-shadow: none;
  cursor: not-allowed;
}

.record-btn:disabled {
  cursor: not-allowed;
}

.record-btn svg {
  width: 22px;
  height: 22px;
}

.record-label {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
}

.rec-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  animation: pulse 1.2s ease-in-out infinite;
}

.record-hint {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.spinner {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}

/* ---------- 评分区(核心系统,富反馈) ---------- */
.score-result {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  background: linear-gradient(160deg, var(--yellow-bg), var(--orange-bg) 60%, var(--pink-bg));
  border: 2px solid rgba(255, 159, 69, 0.35);
  box-shadow: var(--shadow-sm);
  animation: pop-in 480ms var(--ease-bounce) backwards;
  overflow: hidden;
}

/* 头部:总分 + 星级/等级 */
.score-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex: none;
}

.score-hero-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.score-stars {
  display: flex;
  gap: 3px;
  color: var(--yellow);
}

.star {
  filter: drop-shadow(0 2px 3px rgba(255, 159, 69, 0.45));
  animation: star-pop 460ms var(--ease-bounce) backwards;
  animation-delay: calc(var(--i, 0) * 90ms + 120ms);
}

.score-number {
  font-family: var(--font-display);
  font-size: 64px;
  font-weight: 800;
  line-height: 1;
  color: var(--orange-ink);
  text-shadow:
    0 0 14px rgba(255, 170, 60, 0.65),
    0 0 34px rgba(255, 159, 69, 0.4);
  animation:
    score-pop 560ms var(--ease-bounce) backwards,
    score-glow 1.8s ease-in-out 560ms infinite;
}

.score-unit {
  font-size: 22px;
  margin-left: 3px;
}

.score-level {
  padding: 3px 14px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  box-shadow: var(--shadow-pop);
}

.lvl-excellent { background: linear-gradient(180deg, #ffcf3f, var(--orange)); }
.lvl-good { background: linear-gradient(180deg, #63e39b, var(--green)); }
.lvl-ok { background: linear-gradient(180deg, #63a5ff, var(--blue)); }
.lvl-pass { background: linear-gradient(180deg, #b98bff, var(--purple)); }
.lvl-bad { background: linear-gradient(180deg, #ff8089, var(--red)); }

/* 三维度进度条(准/流/完) */
.score-dims {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  flex: none;
}

.dim {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 10px;
  border-radius: var(--radius-xs);
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 159, 69, 0.22);
}

.dim-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}

.dim-bar {
  height: 8px;
  border-radius: 999px;
  background: rgba(43, 37, 69, 0.08);
  overflow: hidden;
}

.dim-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  animation: grow-bar 700ms var(--ease-soft) backwards;
}

.fill-blue { background: linear-gradient(90deg, var(--blue), #63a5ff); }
.fill-green { background: linear-gradient(90deg, #2fca77, #63e39b); }
.fill-orange { background: linear-gradient(90deg, var(--orange), #ffc07a); }

/* ASR 识别对比:标准 vs 你读 */
.score-asr {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  border-radius: var(--radius-xs);
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 159, 69, 0.22);
}

.asr-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.asr-tag {
  flex: none;
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.6;
}

.asr-std { background: var(--blue-bg); color: var(--blue); }
.asr-you { background: var(--pink-bg); color: #c93a83; }

.asr-text {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  word-break: break-word;
}

.asr-none {
  font-family: var(--font-body);
  font-weight: 600;
  color: var(--muted);
}

/* 底部:音质 */
.score-footer {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
}

.score-quality {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.q-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}

.q-badge {
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 700;
  background: var(--red-bg);
  color: #c93a48;
}

.q-ok {
  font-size: 12px;
  font-weight: 700;
  color: #17914f;
}

.playback-audio {
  display: none;
}

.playback-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: none;
  min-height: 52px;
  padding: 8px 18px;
  border-radius: var(--radius-pill);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(180deg, #b98bff, var(--purple));
  box-shadow: 0 10px 20px -10px rgba(160, 107, 255, 0.6), var(--shadow-pop);
  transition: transform var(--transition), box-shadow var(--transition);
}

.playback-btn:hover {
  transform: translateY(-1px);
}

.playback-btn:active {
  transform: scale(0.97);
}

.playback-btn.playing {
  background: linear-gradient(180deg, #a273ff, #8a4dff);
  animation: playback-wave 1.4s ease-in-out infinite;
}

@keyframes playback-wave {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(160, 107, 255, 0.45), var(--shadow-pop);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(160, 107, 255, 0), var(--shadow-pop);
  }
}

@keyframes grow-bar {
  from { width: 0; }
}

@keyframes score-pop {
  0% { transform: scale(0.45); opacity: 0; }
  60% { transform: scale(1.12); opacity: 1; }
  100% { transform: scale(1); }
}

@keyframes score-glow {
  0%, 100% {
    text-shadow:
      0 0 14px rgba(255, 170, 60, 0.55),
      0 0 34px rgba(255, 159, 69, 0.35);
  }
  50% {
    text-shadow:
      0 0 22px rgba(255, 170, 60, 0.9),
      0 0 52px rgba(255, 159, 69, 0.65);
  }
}

/* 逐词详情(可滚动) */
.word-detail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 2px 4px 2px 0;
  overflow-y: auto;
}

.ws-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.ws-word {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ws-badge {
  padding: 0 7px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.5;
}

.ws-extra { background: var(--purple-bg); color: #7b3fe0; }
.ws-miss { background: var(--red-bg); color: #c93a48; }
.ws-wrong { background: var(--pink-bg); color: #c93a83; }

.ws-stress {
  padding: 0 7px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.5;
}

.stress-ok { background: var(--green-bg); color: #17914f; }
.stress-bad { background: var(--orange-bg); color: var(--orange-ink); }

.ws-phonemes {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 2px;
}

.ph {
  padding: 1px 5px;
  border-radius: 6px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
}

.ph-good { background: var(--green-bg); color: #17914f; }
.ph-ok { background: var(--yellow-bg); color: var(--amber-ink); }
.ph-bad { background: var(--red-bg); color: #c93a48; }

@keyframes speak-ring {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(63, 140, 255, 0.45);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(63, 140, 255, 0);
  }
}

/* ---------- 弹窗过渡 ---------- */
.modal-fade-enter-active {
  transition: opacity 250ms ease;
}

.modal-fade-leave-active {
  transition: opacity 200ms ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .repeat-card {
  transition: transform 340ms var(--ease-bounce);
}

.modal-fade-leave-active .repeat-card {
  transition: transform 180ms ease;
}

.modal-fade-enter-from .repeat-card,
.modal-fade-leave-to .repeat-card {
  transform: scale(0.86) translateY(22px) rotate(-1.5deg);
}

/* ---------- 窄屏响应 ---------- */
@media (max-width: 640px) {
  .repeat-card {
    max-width: 100%;
  }
  .repeat-header h3 {
    font-size: 18px;
  }
  .word-chips {
    min-width: 0;
  }
}
</style>
