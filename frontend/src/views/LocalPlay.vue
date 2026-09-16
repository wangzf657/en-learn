<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { adminApi } from '../api.js'
import { parseSrt } from '../utils/srt.js'
import SubtitleOverlay from '../components/SubtitleOverlay.vue'
import SubtitleStylePicker from '../components/SubtitleStylePicker.vue'
import SubtitlePanel from '../components/SubtitlePanel.vue'

const videoEl = ref(null)
const stageRef = ref(null)
const courses = ref([])
const selectedCourseId = ref(null)
const courseMaterials = ref({})
const expandedCourses = ref(new Set())
const selectedMaterial = ref(null)
const currentTime = ref(0)
const duration = ref(0)
const playing = ref(false)
const cues = ref([])
const sentences = ref([])
const error = ref('')
const subtitleStyle = ref('sub-clean')
const loadingCourses = ref(false)
const loadingMaterials = ref(new Set())
const isFullscreen = ref(false)
const sidebarExpanded = ref(true)

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

const selectedCourseMaterials = computed(() => {
  if (!selectedCourseId.value) return []
  return courseMaterials.value[selectedCourseId.value] || []
})

function isExpanded(courseId) {
  return expandedCourses.value.has(courseId)
}

function toggleCourse(courseId) {
  const next = new Set(expandedCourses.value)
  if (next.has(courseId)) {
    next.delete(courseId)
  } else {
    next.add(courseId)
    loadCourseMaterials(courseId)
  }
  expandedCourses.value = next
}

function selectCourse(courseId) {
  selectedCourseId.value = courseId
  if (!isExpanded(courseId)) {
    toggleCourse(courseId)
  }
}

async function loadCourses() {
  loadingCourses.value = true
  error.value = ''
  try {
    const res = await adminApi.listCourses()
    courses.value = res.courses || []
  } catch (e) {
    error.value = `课程库加载失败：${e.message}`
  } finally {
    loadingCourses.value = false
  }
}

async function loadCourseMaterials(courseId) {
  if (courseMaterials.value[courseId]) return
  loadingMaterials.value.add(courseId)
  try {
    const res = await adminApi.getCourse(courseId)
    courseMaterials.value[courseId] = res.materials || []
  } catch (e) {
    error.value = `课程素材加载失败：${e.message}`
  } finally {
    loadingMaterials.value.delete(courseId)
  }
}

async function playMaterial(material) {
  error.value = ''
  selectedMaterial.value = material
  currentTime.value = 0
  duration.value = 0
  cues.value = []
  sentences.value = []

  const v = videoEl.value
  if (v) {
    v.pause()
    v.src = `/api/materials/${material.id}/stream`
    v.load()
  }

  if (material.subtitle?.sentences) {
    sentences.value = material.subtitle.sentences
  }

  try {
    const res = await fetch(`/api/materials/${material.id}/srt`)
    if (res.ok) {
      const text = await res.text()
      cues.value = parseSrt(text)
    } else if (res.status !== 404) {
      cues.value = []
    }
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

function toggleSidebar() {
  sidebarExpanded.value = !sidebarExpanded.value
}

function toggleFullscreen() {
  if (!stageRef.value) return
  if (document.fullscreenElement) {
    document.exitFullscreen?.().catch(() => {})
  } else {
    stageRef.value.requestFullscreen?.().catch(() => {})
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  loadCourses()
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  videoEl.value?.pause()
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (document.fullscreenElement === stageRef.value) {
    document.exitFullscreen?.().catch(() => {})
  }
})
</script>

<template>
  <div class="page local-page">
    <header class="page-header">
      <button class="btn btn-secondary" @click="$router.push('/')">‹ 返回日历</button>
      <div class="title-group">
        <h1 class="page-title">自由播放</h1>
        <p class="page-subtitle">从课程库选择课程与素材进行播放</p>
      </div>
    </header>

    <div ref="stageRef" class="play-layout" :class="{ 'sidebar-collapsed': !sidebarExpanded }">
      <section class="video-section card">
        <div class="video-wrap">
          <video
            v-if="selectedMaterial"
            ref="videoEl"
            :src="`/api/materials/${selectedMaterial.id}/stream`"
            preload="metadata"
            @timeupdate="onTimeUpdate"
            @loadedmetadata="onLoadedMetadata"
            @play="playing = true"
            @pause="playing = false"
          ></video>
          <div v-else class="video-placeholder">
            <span class="placeholder-emoji" aria-hidden="true">🎬</span>
            <p>选择课程和素材后开始播放</p>
          </div>
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
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>

          <div class="time-row">
            <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
          </div>

          <button
            class="icon-btn"
            :title="sidebarExpanded ? '收起面板' : '展开面板'"
            :aria-label="sidebarExpanded ? '收起面板' : '展开面板'"
            @click="toggleSidebar"
          >
            <svg v-if="sidebarExpanded" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="15" y1="3" x2="15" y2="21"></line>
              <polyline points="9 9 6 12 9 15"></polyline>
            </svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="9" y1="3" x2="9" y2="21"></line>
              <polyline points="15 9 18 12 15 15"></polyline>
            </svg>
          </button>

          <button
            class="icon-btn"
            :title="isFullscreen ? '退出全屏' : '全屏播放'"
            :aria-label="isFullscreen ? '退出全屏' : '全屏播放'"
            @click="toggleFullscreen"
          >
            <svg v-if="isFullscreen" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="4 14 10 14 10 20"></polyline>
              <polyline points="20 10 14 10 14 4"></polyline>
              <line x1="14" y1="10" x2="21" y2="3"></line>
              <line x1="3" y1="21" x2="10" y2="14"></line>
            </svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 3 21 3 21 9"></polyline>
              <polyline points="9 21 3 21 3 15"></polyline>
              <line x1="21" y1="3" x2="14" y2="10"></line>
              <line x1="3" y1="21" x2="10" y2="14"></line>
            </svg>
          </button>

          <SubtitleStylePicker v-model="subtitleStyle" />
        </div>

        <div v-if="error" class="error-detail" style="margin: 0 20px 16px">{{ error }}</div>
      </section>

      <aside class="right-panel card">
        <div v-if="loadingCourses" class="empty-state" style="padding: 48px 20px">
          <p>正在加载课程库…</p>
        </div>

        <div v-else-if="courses.length === 0" class="empty-state" style="padding: 48px 20px">
          <p>课程库为空</p>
          <p class="hint">请先在“课程管理”页面导入本地文件夹</p>
        </div>

        <div v-else class="course-list">
          <div
            v-for="course in courses"
            :key="course.id"
            class="course-group"
            :class="{ active: selectedCourseId === course.id }"
          >
            <div class="course-header" @click="selectCourse(course.id)">
              <button
                class="toggle-btn"
                :class="{ expanded: isExpanded(course.id) }"
                @click.stop="toggleCourse(course.id)"
                :aria-label="isExpanded(course.id) ? '收起' : '展开'"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
              </button>
              <span class="course-name">{{ course.name }}</span>
              <span class="badge badge-soft">{{ course.materialCount }} 个素材</span>
            </div>

            <div v-if="isExpanded(course.id)" class="material-list">
              <div v-if="loadingMaterials.has(course.id)" class="empty-state" style="padding: 20px">
                <p>正在加载素材…</p>
              </div>

              <ul v-else-if="selectedCourseMaterials.length > 0">
                <li
                  v-for="m in selectedCourseMaterials"
                  :key="m.id"
                  class="material-item"
                  :class="{ active: selectedMaterial?.id === m.id }"
                  @click="playMaterial(m)"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  <span class="material-title">{{ m.title }}</span>
                  <span v-if="m.read" class="badge badge-success">已读</span>
                </li>
              </ul>

              <div v-else class="empty-state" style="padding: 20px">
                <p>暂无素材</p>
              </div>
            </div>
          </div>
        </div>

        <SubtitlePanel
          v-if="selectedMaterial"
          title="台词"
          :sentences="sentences"
          :current-index="currentIndex"
          empty-text="该素材暂无台词数据"
          @seek="seekToSentence"
        />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.local-page {
  width: auto;
  max-width: none;
  padding-top: 20px;
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-group .page-subtitle {
  margin: 0;
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(0, 75%) minmax(0, 25%);
  gap: 24px;
  align-items: start;
}

.play-layout.sidebar-collapsed {
  grid-template-columns: 1fr;
}

.play-layout.sidebar-collapsed .right-panel {
  display: none;
}

.video-section {
  position: sticky;
  top: 92px;
  padding: 0;
  overflow: hidden;
}

.video-wrap {
  position: relative;
  background: #16102b;
  aspect-ratio: 16 / 9;
  width: 100%;
  max-height: calc(100svh - 176px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-placeholder {
  color: #cdc4e6;
  text-align: center;
}

.placeholder-emoji {
  display: block;
  font-size: 56px;
  margin-bottom: 12px;
  animation: float-y 3.4s var(--ease-soft) infinite;
}

.video-placeholder p {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
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
  padding: 16px 20px;
  background: linear-gradient(180deg, var(--card), var(--bg));
}

.play-btn {
  flex: 0 0 auto;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--grad-blue);
  color: #fff;
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

.icon-btn {
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: var(--card);
  color: var(--muted);
  border: 2px solid var(--border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition);
}

.icon-btn:hover {
  background: var(--blue-bg);
  color: var(--blue);
  border-color: var(--blue);
  transform: translateY(-2px);
}

.time-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1 1 auto;
  min-width: 0;
  margin-top: 0;
}

.time {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--muted);
}

.right-panel {
  padding: 18px;
  max-height: calc(100svh - 176px);
  overflow-y: auto;
}

.course-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.course-group {
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--card);
  transition: box-shadow var(--transition), border-color var(--transition), transform var(--transition);
}

.course-group:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.course-group.active {
  border-color: var(--blue);
  box-shadow: 0 0 0 4px rgba(63, 140, 255, 0.16);
}

.course-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  cursor: pointer;
  background: var(--bg);
  transition: background var(--transition);
}

.course-header:hover {
  background: var(--blue-bg);
}

.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: var(--card);
  color: var(--muted);
  cursor: pointer;
  box-shadow: var(--shadow-pop);
  transition: transform 220ms var(--ease-bounce), color var(--transition), background var(--transition);
}

.toggle-btn:hover {
  color: var(--blue);
  background: var(--blue-bg);
}

.toggle-btn.expanded {
  transform: rotate(90deg);
}

.course-name {
  flex: 1 1 auto;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  word-break: break-all;
}

.material-list {
  border-top: 2px solid var(--border);
}

.material-list ul {
  list-style: none;
  margin: 0;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.material-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  min-height: 46px;
  border-radius: var(--radius-xs);
  background: var(--bg);
  color: var(--ink);
  cursor: pointer;
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.material-item:hover {
  background: var(--blue-bg);
  color: var(--blue);
  transform: translateX(3px);
}

.material-item.active {
  background: var(--grad-blue);
  color: #fff;
  box-shadow: var(--shadow-blue), var(--shadow-pop);
}

.material-title {
  flex: 1 1 auto;
  font-size: 14px;
  font-weight: 700;
  word-break: break-all;
}

.hint {
  font-size: 13px;
  color: var(--secondary);
}

.play-layout:fullscreen {
  width: 100vw;
  height: 100vh;
  padding: 0;
  gap: 0;
  background: #000;
  align-items: stretch;
}

.play-layout:fullscreen .video-section {
  position: static;
  border-radius: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.play-layout:fullscreen .video-wrap {
  flex: 1 1 auto;
  aspect-ratio: auto;
  max-height: none;
}

.play-layout:fullscreen .right-panel {
  max-height: none;
  height: 100vh;
  border-radius: 0;
  border-left: 1px solid var(--border);
  background: var(--bg);
}

@media (max-width: 1024px) {
  .play-layout,
  .play-layout.sidebar-collapsed {
    grid-template-columns: 1fr;
  }
  .play-layout.sidebar-collapsed .right-panel {
    display: block;
  }
  .video-section {
    position: static;
  }
  .right-panel {
    max-height: none;
  }
}

@media (max-width: 640px) {
  .controls {
    flex-wrap: wrap;
    gap: 12px;
  }
  .time-row {
    flex: 1 1 100%;
    order: -1;
  }
  .title-group {
    width: 100%;
  }
}
</style>
