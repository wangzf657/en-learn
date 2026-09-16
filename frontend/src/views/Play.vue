<script setup>
import { ref, computed, watch, reactive, onMounted, onBeforeUnmount } from 'vue'
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

const cues = ref([])
const subtitleStyle = ref('sub-clean')

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

const scoreMap = ref(new Map())

const subtitleOpen = ref(true)
const isFullscreen = ref(false)
const layoutRef = ref(null)

const repeatOpen = ref(false)
const repeatSentence = ref(null)
const repeatIndex = ref(-1)

watch(
  sentences,
  (list) => {
    scoreMap.value = new Map()
    list.forEach((_, i) => {
      scoreMap.value.set(i, reactive({ status: 'idle', result: null, error: '' }))
    })
  },
  { immediate: true },
)

watch(currentMaterialIndex, () => {
  cues.value = []
  currentTime.value = 0
  duration.value = 0
  loadSrtForCurrentMaterial()
  const v = videoEl.value
  if (v) {
    v.pause()
    v.load()
  }
})

function scoreState(i) {
  return scoreMap.value.get(i) || { status: 'idle', result: null, error: '' }
}

function wordScoreClass(score) {
  if (score >= 80) return 'word-good'
  if (score >= 60) return 'word-ok'
  return 'word-bad'
}

function openRepeat(s, i) {
  repeatSentence.value = s
  repeatIndex.value = i
  repeatOpen.value = true
  videoEl.value?.pause()
}

function closeRepeat() {
  repeatOpen.value = false
}

function onRepeatResult(i, result) {
  const state = scoreState(i)
  state.result = result
  state.error = ''
}

function onRepeatError(i, message) {
  const state = scoreState(i)
  state.error = message
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
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await dayApi.get(props.date)
    day.value = data
    currentMaterialIndex.value = 0
    checkedIn.value = !!data.checked
    await loadSrtForCurrentMaterial()
  } catch (e) {
    error.value = e.detail || e.message
    day.value = null
  } finally {
    loading.value = false
  }
}

async function loadSrtForCurrentMaterial() {
  const url = srtUrl.value
  if (!url) {
    cues.value = []
    return
  }
  try {
    const res = await fetch(url)
    if (!res.ok) {
      cues.value = []
      return
    }
    const text = await res.text()
    cues.value = parseSrt(text)
  } catch {
    cues.value = []
  }
}

function togglePlay() {
  const v = videoEl.value
  if (!v) return
  if (v.paused) v.play()
  else v.pause()
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

function cycleRate() {
  const v = videoEl.value
  if (!v) return
  let i = rates.indexOf(playbackRate.value)
  if (i < 0) i = 1
  const next = rates[(i + 1) % rates.length]
  playbackRate.value = next
  v.playbackRate = next
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
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<template>
  <div class="page play-page">
    <header class="page-header">
      <button class="btn btn-ghost btn-sm" @click="$router.push('/')">‹ 返回日历</button>
      <div class="title-group">
        <h1 class="page-title">{{ pageTitle }}</h1>
        <span v-if="checkedIn" class="badge badge-blue">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          已打卡
        </span>
        <span v-else class="badge badge-yellow">未打卡</span>
        <button
          v-if="!checkedIn"
          class="btn btn-primary btn-sm checkin-btn"
          :disabled="checkinLoading"
          @click="doCheckin"
        >
          <span v-if="checkinLoading">打卡中…</span>
          <span v-else>已完成打卡</span>
        </button>
      </div>
    </header>

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

    <div v-if="loading" class="card empty-state">
      <p>正在加载学习内容…</p>
    </div>

    <div v-else-if="error" class="card empty-state">
      <h3>{{ error }}</h3>
      <button class="btn btn-primary" style="margin-top: 16px" @click="router.push('/')">回日历</button>
    </div>

    <div v-else ref="layoutRef" class="play-layout">
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

          <div class="progress-area">
            <div
              ref="progressEl"
              class="progress-track"
              @click="seekFromEvent"
              @mousedown="startDrag"
            >
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
              <div class="progress-thumb" :style="{ left: progressPercent + '%' }"></div>
            </div>
            <div class="time-row">
              <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
              <button class="rate-btn" @click="cycleRate" title="切换倍速">{{ playbackRate }}×</button>
            </div>
          </div>

          <div class="volume-area">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
              <path v-if="volume > 0" d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
              <path v-if="volume > 0.5" d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
            </svg>
            <input id="volume" type="range" min="0" max="1" step="0.05" v-model.number="volume" @input="setVolume" />
          </div>

          <div class="controls-extras">
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

            <SubtitleStylePicker v-model="subtitleStyle" />
          </div>
        </div>
      </section>

      <div class="subtitle-drawer" :class="{ open: subtitleOpen }">
        <SubtitlePanel
          title="今日台词"
          :sentences="sentences"
          :current-index="currentIndex"
          empty-text="暂无字幕数据"
          @seek="seekToSentence"
        >
          <template #actions="{ s, i }">
            <div class="repeat-row">
              <button
                class="btn btn-sm repeat-btn"
                :class="scoreState(i).result ? 'btn-secondary' : 'btn-primary'"
                @click.stop="openRepeat(s, i)"
              >
                <svg v-if="scoreState(i).result" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                </svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
                <span>{{ scoreState(i).result ? '重新跟读' : '跟读一下' }}</span>
              </button>
            </div>

            <div v-if="scoreState(i).error" class="error-detail score-error">{{ scoreState(i).error }}</div>

            <div v-if="scoreState(i).result" class="score-detail">
              <div class="score-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                </svg>
                <span>本次得分</span>
              </div>
              <div class="score-pills">
                <span class="pill pill-blue">准确度 {{ Math.round(scoreState(i).result.accuracy_score) }}</span>
                <span class="pill pill-green">流利度 {{ Math.round(scoreState(i).result.fluency_score) }}</span>
                <span class="pill pill-orange">完整度 {{ Math.round(scoreState(i).result.completeness_score) }}</span>
              </div>
              <div class="word-scores">
                <span
                  v-for="(ws, k) in scoreState(i).result.word_scores"
                  :key="k"
                  :class="['ws-word', wordScoreClass(ws.accuracy_score)]"
                  :title="`分数: ${Math.round(ws.accuracy_score)}\n预期音素: ${ws.expected_phonemes || '-'}\n实际音素: ${ws.actual_phonemes || '-'}`"
                >
                  {{ ws.word }}
                </span>
              </div>
            </div>
          </template>
        </SubtitlePanel>
      </div>
    </div>

    <RepeatModal
      :open="repeatOpen"
      :sentence="repeatSentence"
      @close="closeRepeat"
      @result="onRepeatResult(repeatIndex, $event)"
      @error="onRepeatError(repeatIndex, $event)"
    />

    <transition name="fade">
      <div v-if="toast" class="toast">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
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
  padding: 20px 24px 80px;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.checkin-btn {
  margin-left: 4px;
}

.video-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.chip {
  padding: 8px 16px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  background: var(--card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  transition: background var(--transition), color var(--transition), border-color var(--transition);
}

.chip:hover {
  border-color: var(--blue);
  color: var(--blue);
}

.chip.active {
  background: var(--blue);
  color: #fff;
  border-color: var(--blue);
}

.play-layout {
  display: flex;
  gap: 0;
  align-items: stretch;
}

.play-layout:fullscreen {
  width: 100vw;
  height: 100vh;
  padding: 0;
  background: var(--bg);
}

.play-layout:fullscreen .video-section {
  position: static;
  border-radius: 0;
  border: none;
}

.play-layout:fullscreen .video-wrap {
  border-radius: 0;
  max-height: none;
}

.video-section {
  flex: 1 1 auto;
  min-width: 0;
  position: sticky;
  top: 84px;
  padding: 0;
  overflow: hidden;
}

.subtitle-drawer {
  flex: 0 0 auto;
  width: 0;
  overflow: hidden;
  transition: width 300ms cubic-bezier(0.32, 0.72, 0, 1), margin-left 300ms cubic-bezier(0.32, 0.72, 0, 1);
}

.subtitle-drawer.open {
  width: 25%;
  min-width: 220px;
  margin-left: 24px;
}

.video-wrap {
  position: relative;
  background: #000;
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: calc(100svh - 168px);
  display: flex;
  align-items: center;
  justify-content: center;
}

video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  background: var(--bg);
}

.play-btn {
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--blue);
  color: #fff;
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-blue);
  transition: transform var(--transition), background var(--transition);
}

.play-btn:hover {
  background: var(--blue-hover);
  transform: scale(1.05);
}

.play-btn:active {
  transform: scale(0.98);
}

.progress-area {
  flex: 1 1 auto;
  min-width: 0;
}

.progress-track {
  position: relative;
  height: 10px;
  background: var(--border);
  border-radius: 999px;
  cursor: pointer;
}

.progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--blue);
  border-radius: 999px;
  pointer-events: none;
}

.progress-thumb {
  position: absolute;
  top: 50%;
  width: 18px;
  height: 18px;
  margin-top: -9px;
  margin-left: -9px;
  background: #fff;
  border: 3px solid var(--blue);
  border-radius: 50%;
  pointer-events: none;
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.35);
}

.time-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.time {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--muted);
}

.rate-btn {
  padding: 5px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--blue);
  transition: border-color var(--transition), background var(--transition);
}

.rate-btn:hover {
  border-color: var(--blue);
  background: var(--blue-bg);
}

.volume-area {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--muted);
}

.volume-area input[type='range'] {
  width: 80px;
  padding: 0;
  min-height: auto;
  accent-color: var(--blue);
}

.controls-extras {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.repeat-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.repeat-btn {
  min-width: 100px;
}

.score-error {
  margin-top: 12px;
}

.score-detail {
  margin-top: 14px;
  padding: 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}

.score-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-weight: 700;
  color: var(--yellow);
}

.score-header svg {
  color: var(--yellow);
  filter: drop-shadow(0 1px 2px rgba(255, 204, 0, 0.35));
}

.score-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.pill {
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
}

.pill-blue {
  background: var(--blue-bg);
  color: var(--blue);
}

.pill-green {
  background: var(--green-bg);
  color: var(--green);
}

.pill-orange {
  background: var(--orange-bg);
  color: #c46a00;
}

.word-scores {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 1.6;
}

.ws-word {
  padding: 4px 10px;
  border-radius: var(--radius-xs);
  font-size: 14px;
  font-weight: 600;
  cursor: help;
}

.word-good {
  background: var(--green-bg);
  color: var(--green);
}

.word-ok {
  background: var(--yellow-bg);
  color: #a67c00;
}

.word-bad {
  background: var(--red-bg);
  color: var(--red);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: var(--radius-pill);
  background: var(--ink);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow);
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.toast svg {
  color: var(--yellow);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}

@media (max-width: 1024px) {
  .play-layout {
    flex-direction: column;
  }
  .video-section {
    position: static;
  }
  .subtitle-drawer.open {
    width: 100%;
    min-width: auto;
    margin-left: 0;
    margin-top: 20px;
  }
}

@media (max-width: 640px) {
  .controls {
    flex-wrap: wrap;
    gap: 12px;
  }
  .volume-area {
    width: 100%;
    justify-content: flex-end;
  }
  .title-group {
    width: 100%;
  }
}
</style>
