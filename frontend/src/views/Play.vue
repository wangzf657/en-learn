<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { dayApi } from '../api.js'
import { parseSrt } from '../utils/srt.js'
import SubtitleOverlay from '../components/SubtitleOverlay.vue'
import SubtitleStylePicker from '../components/SubtitleStylePicker.vue'
import SubtitlePanel from '../components/SubtitlePanel.vue'
import RepeatModal from '../components/RepeatModal.vue'

const props = defineProps({ date: String })
const router = useRouter()

const day = ref(null)
const currentMaterialIndex = ref(0)
const loading = ref(true)
const error = ref('')
const checkedIn = ref(false)
const checkinLoading = ref(false)
const toast = ref('')
const celebrate = ref(false)

const srtCues = ref([])
const subtitleStyle = ref('sub-cinema')
const subtitleSize = ref('sub-size-lg')

const videoEl = ref(null)
const progressEl = ref(null)

const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const playbackRate = ref(1)
const rates = [0.5, 0.75, 1, 1.25, 1.5, 2]

const currentMaterial = computed(() => day.value?.materials?.[currentMaterialIndex.value] || null)
const sentences = computed(() => currentMaterial.value?.subtitle?.sentences || [])
const videoSrc = computed(() => currentMaterial.value?.videoUrl || '')
const srtUrl = computed(() => currentMaterial.value?.srtUrl || null)
const pageTitle = computed(() => currentMaterial.value?.title || props.date)

// 浮层字幕优先同步派生自内存中的 sentences(已带 start/end/en),切换素材立即有数据不闪空;
// 仅当 sentences 为空才用 srt 文本兜底。
const cues = computed(() =>
  sentences.value.length
    ? sentences.value.map((s) => ({ start: s.start, end: s.end, text: s.en || '' }))
    : srtCues.value,
)

const subtitleOpen = ref(true)
const isFullscreen = ref(false)
const layoutRef = ref(null)

const repeatOpen = ref(false)
const repeatSentence = ref(null)

watch(currentMaterialIndex, () => {
  currentTime.value = 0
  duration.value = 0
  loadCuesFallback()
  const v = videoEl.value
  if (v) {
    v.pause()
    v.load()
  }
})

function openRepeat(s) {
  repeatSentence.value = s
  repeatOpen.value = true
  videoEl.value?.pause()
}

function closeRepeat() {
  repeatOpen.value = false
}

function toggleSubtitle() {
  subtitleOpen.value = !subtitleOpen.value
}

async function toggleFullscreen() {
  const el = layoutRef.value
  if (!el) return
  try {
    if (!document.fullscreenElement) {
      await el.requestFullscreen?.()
    } else {
      await document.exitFullscreen?.()
    }
  } catch {}
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  // 进入全屏时默认收起台词栏(仍可经回车/收起按钮自行展开)
  if (document.fullscreenElement) subtitleOpen.value = false
}

const currentIndex = computed(() => {
  const list = sentences.value
  if (!list.length) return -1
  const t = currentTime.value
  for (let i = 0; i < list.length; i++) {
    if (t >= list[i].start && t < list[i].end) return i
  }
  if (t >= list[list.length - 1].end) return list.length - 1
  return -1
})

const progressPercent = computed(() => {
  if (!duration.value) return 0
  return Math.min(100, Math.max(0, (currentTime.value / duration.value) * 100))
})

onMounted(() => {
  load()
  document.addEventListener('fullscreenchange', onFullscreenChange)
  window.addEventListener('keydown', onKeyDown)
  // 播放页固定一屏,禁用页面整体滚动(离开时恢复)
  document.documentElement.style.overflow = 'hidden'
  document.body.style.overflow = 'hidden'
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await dayApi.get(props.date)
    day.value = data
    currentMaterialIndex.value = 0
    checkedIn.value = !!data.checked
    await loadCuesFallback()
  } catch (e) {
    error.value = e.detail || e.message
    day.value = null
  } finally {
    loading.value = false
  }
}

let srtReqId = 0

// sentences 为空时才拉 srt;序号校验丢弃切换素材后迟到的响应
async function loadCuesFallback() {
  const reqId = ++srtReqId
  srtCues.value = []
  const url = srtUrl.value
  if (!url || sentences.value.length) return
  try {
    const res = await fetch(url)
    if (reqId !== srtReqId) return
    if (!res.ok) return
    const text = await res.text()
    if (reqId !== srtReqId) return
    srtCues.value = parseSrt(text)
  } catch {
    if (reqId !== srtReqId) return
  }
}

function togglePlay() {
  const v = videoEl.value
  if (!v) return
  if (v.paused) v.play()
  else v.pause()
}

function isEditableTarget(el) {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || el.isContentEditable
}

// 全局快捷键:空格=播放/暂停,F11=全屏,回车=收起/展开单词栏
// 弹窗打开或焦点在输入控件(输入框/下拉/可编辑)时除外;普通按钮聚焦时也走全局,
// 并用 preventDefault 阻止按钮自身的默认激活,避免“点了一次全屏后空格/回车都变成全屏”。
function onKeyDown(e) {
  if (repeatOpen.value) return
  if (e.code === 'F11') {
    e.preventDefault()
    toggleFullscreen()
    return
  }
  if (e.repeat || isEditableTarget(e.target)) return
  if (e.code === 'Space') {
    e.preventDefault()
    togglePlay()
  } else if (e.code === 'Enter') {
    e.preventDefault()
    toggleSubtitle()
  }
}

function onTimeUpdate() {
  const v = videoEl.value
  if (!v) return
  currentTime.value = v.currentTime
  if (v.duration && !isNaN(v.duration)) duration.value = v.duration
}

function onLoadedMetadata() {
  const v = videoEl.value
  if (v && !isNaN(v.duration)) duration.value = v.duration
}

function onEnded() {
  playing.value = false
}

async function doCheckin() {
  if (checkinLoading.value || checkedIn.value) return
  checkinLoading.value = true
  try {
    await dayApi.checkin(props.date)
    checkedIn.value = true
    toast.value = '今日已打卡'
    celebrate.value = true
    setTimeout(() => (celebrate.value = false), 2000)
    setTimeout(() => (toast.value = ''), 2200)
  } catch (e) {
    toast.value = e.detail || e.message || '打卡失败'
    setTimeout(() => (toast.value = ''), 2200)
  } finally {
    checkinLoading.value = false
  }
}

function seekToRatio(ratio) {
  const v = videoEl.value
  if (!v || !duration.value) return
  const t = Math.max(0, Math.min(duration.value, ratio * duration.value))
  v.currentTime = t
  currentTime.value = t
}

function seekFromEvent(e) {
  if (!progressEl.value || !duration.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  seekToRatio(ratio)
}

const dragging = ref(false)
function startDrag(e) {
  dragging.value = true
  seekFromEvent(e)
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}
function onDrag(e) {
  if (!dragging.value) return
  seekFromEvent(e)
}
function stopDrag() {
  dragging.value = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

function applyRate(e) {
  const next = Number(e.target.value)
  playbackRate.value = next
  const v = videoEl.value
  if (v) v.playbackRate = next
}

function setVolume() {
  const v = videoEl.value
  if (v) v.volume = volume.value
}

function seekToSentence(s) {
  const v = videoEl.value
  if (!v) return
  v.currentTime = s.start
  currentTime.value = s.start
  v.play()
}

function formatTime(s) {
  if (!s && s !== 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

onBeforeUnmount(() => {
  const v = videoEl.value
  if (v) v.pause()
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.documentElement.style.overflow = ''
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="page play-page">
    <div v-if="loading" class="card empty-state play-empty">
      <p>正在加载学习内容…</p>
    </div>

    <div v-else-if="error" class="card empty-state play-empty">
      <h3>{{ error }}</h3>
      <button class="btn btn-primary" style="margin-top: 16px" @click="router.push('/')">回日历</button>
    </div>

    <div v-else ref="layoutRef" class="play-layout" :class="{ 'panel-on': subtitleOpen }">
      <section class="video-section card">
        <div class="video-wrap">
          <video
            ref="videoEl"
            :src="videoSrc"
            preload="metadata"
            @timeupdate="onTimeUpdate"
            @loadedmetadata="onLoadedMetadata"
            @play="playing = true"
            @pause="playing = false"
            @ended="onEnded"
          ></video>
          <SubtitleOverlay
            :cues="cues"
            :current-time="currentTime"
            :enabled="subtitleStyle !== 'sub-off'"
            :style-class="subtitleStyle"
            :size="subtitleSize"
          />
        </div>

        <div class="controls">
          <button class="play-btn" @click="togglePlay" :aria-label="playing ? '暂停' : '播放'">
            <svg v-if="playing" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>

          <div class="volume-area">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
              <path v-if="volume > 0" d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
              <path v-if="volume > 0.5" d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
            </svg>
            <input id="volume" type="range" min="0" max="1" step="0.05" v-model.number="volume" @input="setVolume" />
          </div>

          <div
            ref="progressEl"
            class="progress-track"
            @click="seekFromEvent"
            @mousedown="startDrag"
          >
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            <div class="progress-thumb" :style="{ left: progressPercent + '%' }"></div>
          </div>

          <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>

          <div class="controls-right">
            <select
              class="rate-select"
              :value="playbackRate"
              aria-label="播放倍速"
              title="播放倍速"
              @change="applyRate"
            >
              <option v-for="r in rates" :key="r" :value="r">{{ r }}×</option>
            </select>

            <button
              class="icon-btn drawer-toggle"
              type="button"
              :title="subtitleOpen ? '收起台词' : '展开台词'"
              @click="toggleSubtitle"
            >
              <svg v-if="subtitleOpen" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <path d="M9 3v18"/>
                <path d="M14 9l3 3-3 3"/>
              </svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <path d="M15 3v18"/>
                <path d="M10 9l-3 3 3 3"/>
              </svg>
            </button>

            <button
              class="icon-btn fullscreen-btn"
              type="button"
              :title="isFullscreen ? '退出全屏' : '全屏'"
              @click="toggleFullscreen"
            >
              <svg v-if="isFullscreen" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 14v5a1 1 0 0 0 1 1h5"/>
                <path d="M20 14v5a1 1 0 0 1-1 1h-5"/>
                <path d="M15 4h5a1 1 0 0 1 1 1v5"/>
                <path d="M9 4H4a1 1 0 0 0-1 1v5"/>
              </svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M8 3H3v5"/>
                <path d="M16 3h5v5"/>
                <path d="M21 16v5h-5"/>
                <path d="M3 16v5h5"/>
              </svg>
            </button>

            <SubtitleStylePicker v-model="subtitleStyle" v-model:size="subtitleSize" />
          </div>
        </div>
      </section>

      <div class="subtitle-drawer" :class="{ open: subtitleOpen }">
        <div class="drawer-header">
          <h1 class="drawer-title" :title="pageTitle">{{ pageTitle }}</h1>

          <div class="drawer-meta">
            <span v-if="checkedIn" class="badge badge-green">已打卡</span>
            <span v-else class="badge badge-yellow">未打卡</span>
            <button
              v-if="!checkedIn"
              class="btn btn-primary checkin-btn"
              :disabled="checkinLoading"
              @click="doCheckin"
            >
              <span v-if="checkinLoading">打卡中…</span>
              <template v-else>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                <span>已完成打卡</span>
              </template>
            </button>
          </div>

          <div v-if="day?.materials?.length > 1" class="video-chips" role="tablist" aria-label="素材切换">
            <button
              v-for="(m, i) in day.materials"
              :key="m.id ?? i"
              type="button"
              class="chip"
              :class="{ active: i === currentMaterialIndex }"
              role="tab"
              :aria-selected="i === currentMaterialIndex"
              @click="currentMaterialIndex = i"
            >
              {{ m.title || `素材 ${i + 1}` }}
            </button>
          </div>
        </div>

        <SubtitlePanel
          class="panel-fill"
          title="今日台词"
          card-action="repeat"
          :sentences="sentences"
          :current-index="currentIndex"
          empty-text="暂无字幕数据"
          @seek="seekToSentence"
          @repeat="openRepeat"
        />
      </div>
    </div>

    <RepeatModal
      :open="repeatOpen"
      :sentence="repeatSentence"
      @close="closeRepeat"
    />

    <transition name="pop">
      <div v-if="celebrate" class="confetti-layer" aria-hidden="true">
        <span
          v-for="i in 24"
          :key="i"
          class="confetti-piece"
          :style="{ '--i': i }"
        ></span>
      </div>
    </transition>

    <transition name="pop">
      <div v-if="toast" class="toast">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
        {{ toast }}
      </div>
    </transition>
  </div>
</template>

<style scoped>
.play-page {
  width: 100%;
  max-width: none;
  height: calc(100svh - var(--appbar-h, 70px));
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.play-empty {
  margin: auto;
  max-width: 560px;
}

.play-layout {
  --controls-h: 64px;
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  gap: 0;
  align-items: stretch;
  padding: 16px 20px 20px;
}

.play-layout:fullscreen {
  width: 100vw;
  height: 100vh;
  padding: 0;
  background: #000;
  gap: 0;
}

.play-layout:fullscreen .video-section {
  position: static;
  border-radius: 0;
  border: none;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  width: auto;
}

.play-layout:fullscreen .video-wrap {
  height: calc(100% - var(--controls-h));
  width: 100%;
  aspect-ratio: auto;
  border-radius: 0;
}

.play-layout:fullscreen .subtitle-drawer.open {
  flex: 0 0 auto;
  width: clamp(420px, 30vw, 640px);
  margin-left: 0;
}

.play-layout:fullscreen .subtitle-drawer :deep(.panel-section) {
  max-height: 100vh;
  height: 100vh;
  border-radius: 0;
  border: none;
  border-left: 1px solid var(--border);
  box-shadow: none;
}

.video-section {
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: var(--card);
}

.subtitle-drawer {
  flex: 0 0 auto;
  width: 0;
  overflow: hidden;
  transition: width 300ms var(--ease-bounce), margin-left 300ms var(--ease-bounce);
  display: flex;
  flex-direction: column;
}

.subtitle-drawer.open {
  flex: 1 1 auto;
  width: auto;
  min-width: 0;
  margin-left: 20px;
}

.drawer-header {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px 14px;
  background: var(--card);
  border: 2px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
  margin-bottom: 16px;
}

.drawer-title {
  font-size: 22px;
  line-height: 1.3;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.drawer-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.checkin-btn {
  min-height: 40px;
  padding: 8px 16px;
  font-size: 14px;
}

.video-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 8px;
  border-top: 2px dashed var(--border);
}

.chip {
  padding: 8px 16px;
  min-height: 38px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
  background: var(--card);
  border: 2px solid var(--border);
  box-shadow: var(--shadow-pop);
  transition: transform var(--transition), background var(--transition),
    color var(--transition), border-color var(--transition);
}

.chip:hover {
  border-color: var(--blue);
  color: var(--blue);
  transform: translateY(-2px);
}

.chip:active {
  transform: translateY(1px) scale(0.97);
}

.chip.active {
  background: var(--grad-blue);
  color: #fff;
  border-color: transparent;
  box-shadow: var(--shadow-blue), var(--shadow-pop);
}

.video-wrap {
  position: relative;
  background: #16102b;
  height: calc(100% - var(--controls-h));
  width: 100%;
  aspect-ratio: auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 台词面板展开时,视频保持 16:9 等比,把剩余宽度留给台词区(仅宽屏并排布局) */
@media (min-width: 1025px) {
  .play-layout.panel-on:not(:fullscreen) .video-section {
    flex: 0 0 auto;
    width: fit-content;
  }

  .play-layout.panel-on:not(:fullscreen) .video-wrap {
    aspect-ratio: 16 / 9;
  }
}

video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--controls-h);
  box-sizing: border-box;
  padding: 0 16px;
  background: linear-gradient(180deg, var(--card), var(--bg));
  border-top: 2px solid var(--border);
}

.controls-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.play-btn {
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: var(--grad-blue);
  color: #fff;
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-blue), var(--shadow-pop);
  transition: transform 180ms var(--ease-bounce), background 200ms ease, box-shadow 200ms ease;
}

.play-btn:hover {
  transform: scale(1.08) rotate(-4deg);
}

.play-btn:active {
  transform: translateY(2px) scale(0.96);
  box-shadow: var(--shadow-sm);
}

.progress-track {
  position: relative;
  flex: 1 1 auto;
  min-width: 60px;
  height: 14px;
  background: var(--border);
  border-radius: 999px;
  cursor: pointer;
  box-shadow: inset 0 2px 4px rgba(43, 37, 69, 0.12);
}

.progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, var(--cyan), var(--blue) 60%, var(--purple));
  border-radius: 999px;
  pointer-events: none;
  transition: width 120ms linear;
}

.progress-thumb {
  position: absolute;
  top: 50%;
  width: 24px;
  height: 24px;
  margin-top: -12px;
  margin-left: -12px;
  background: #fff;
  border: 4px solid var(--blue);
  border-radius: 50%;
  pointer-events: none;
  box-shadow: 0 4px 10px rgba(63, 140, 255, 0.45);
  transition: transform 160ms var(--ease-bounce);
}

.progress-track:hover .progress-thumb {
  transform: scale(1.15);
}

.time {
  flex: 0 0 auto;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--secondary);
  white-space: nowrap;
}

.rate-select {
  min-height: 40px;
  padding: 6px 34px 6px 14px;
  border-radius: 999px;
  background-color: #fff;
  border: 2px solid var(--border);
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 700;
  color: var(--blue);
  box-shadow: var(--shadow-pop);
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.rate-select:hover {
  border-color: var(--blue);
}

.volume-area {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}

.volume-area input[type='range'] {
  width: 80px;
  padding: 0;
  min-height: auto;
  border: none;
  background: transparent;
  accent-color: var(--blue);
  box-shadow: none;
}

.toast {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 40px;
  margin: 0 auto;
  width: fit-content;
  max-width: calc(100% - 32px);
  padding: 14px 28px;
  border-radius: var(--radius-pill);
  background: linear-gradient(180deg, #6b5cd6, var(--ink));
  color: #fff;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  box-shadow: var(--shadow), var(--shadow-pop);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  z-index: 200;
}

.toast svg {
  color: var(--yellow);
}

/* 打卡庆祝彩纸 */
.confetti-layer {
  position: fixed;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 300;
}

.confetti-piece {
  position: absolute;
  top: 0;
  left: calc(var(--i) * 3.9%);
  width: 12px;
  height: 16px;
  border-radius: 3px;
  background: var(--blue);
  animation: confetti-fall 1.6s var(--ease-soft) forwards;
  animation-delay: calc(var(--i) * -0.09s);
  --drift: 0px;
  --spin: 540deg;
}

.confetti-piece:nth-child(4n + 1) {
  background: var(--yellow);
  border-radius: 50%;
}

.confetti-piece:nth-child(4n + 2) {
  background: var(--pink);
  --drift: 90px;
  --spin: -720deg;
}

.confetti-piece:nth-child(4n + 3) {
  background: var(--green);
  --drift: -80px;
  --spin: 900deg;
  width: 14px;
  height: 10px;
}

.confetti-piece:nth-child(4n) {
  background: var(--purple);
  --drift: 40px;
}

/* 弹性出现:提示条与彩纸共用 */
.pop-enter-active {
  transition: opacity 200ms ease, transform 320ms var(--ease-bounce);
}

.pop-leave-active {
  transition: opacity 200ms ease, transform 180ms ease;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(24px) scale(0.7);
}

@media (max-width: 1024px) {
  .play-layout {
    flex-direction: column;
    overflow: hidden;
  }
  .video-section {
    position: static;
    min-height: 0;
    width: 100%;
    height: 100%;
  }
  .video-wrap {
    width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
  }
  .controls {
    height: auto;
  }
  .subtitle-drawer {
    display: none;
  }
  .subtitle-drawer.open {
    display: flex;
    position: absolute;
    right: 20px;
    top: 16px;
    bottom: 20px;
    width: 360px;
    min-width: 320px;
    max-width: none;
    margin-left: 0;
    z-index: 50;
  }
}

@media (max-width: 640px) {
  .play-layout {
    padding: 12px;
  }
  .controls {
    flex-wrap: wrap;
    gap: 10px;
    height: auto;
    min-height: var(--controls-h);
    padding: 10px 14px;
  }
  .progress-track {
    order: 10;
    flex-basis: 100%;
  }
  .controls-right {
    justify-content: flex-start;
    margin-left: auto;
  }
  .volume-area {
    flex: 1;
  }
  .subtitle-drawer.open {
    inset: 12px;
    width: auto;
    min-width: auto;
  }
  .drawer-header {
    padding: 14px 16px 12px;
  }
  .drawer-title {
    font-size: 20px;
  }
}
</style>
