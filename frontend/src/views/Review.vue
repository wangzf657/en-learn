<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { reviewApi } from '../api.js'
import mascotUrl from '../assets/mascot.jpg'

const groups = ref([])
const loading = ref(false)
const error = ref('')

// 三级导航(单页内部状态):null = L1 课程列表, courseId = L2, groupKey = L3
const selectedCourseId = ref(null)
const selectedGroupKey = ref(null)

// 弹窗大图预览:null = 关闭,否则为 selectedGroup.files 的下标
const lightboxIndex = ref(null)

const courseSections = computed(() => {
  const map = new Map()
  for (const g of groups.value) {
    let sec = map.get(g.courseId)
    if (!sec) {
      sec = { courseId: g.courseId, courseName: g.courseName, courseGroup: null, materialGroups: [] }
      map.set(g.courseId, sec)
    }
    if (g.kind === 'course') sec.courseGroup = g
    else sec.materialGroups.push(g)
  }
  return [...map.values()]
})

const selectedCourse = computed(
  () => courseSections.value.find((s) => s.courseId === selectedCourseId.value) || null,
)

const selectedGroup = computed(() => {
  if (!selectedCourse.value || !selectedGroupKey.value) return null
  return courseItems(selectedCourse.value).find((g) => groupKey(g) === selectedGroupKey.value) || null
})

const lightboxFile = computed(() => {
  const files = selectedGroup.value?.files
  if (lightboxIndex.value == null || !files) return null
  return files[lightboxIndex.value] || null
})

function groupKey(g) {
  return `${g.kind}-${g.materialId ?? 'course'}`
}

function courseItems(sec) {
  return [sec.courseGroup, ...sec.materialGroups].filter(Boolean)
}

function summaryOf(sec) {
  const parts = []
  if (sec.courseGroup) parts.push(`课程资料 ${sec.courseGroup.files.length} 份`)
  if (sec.materialGroups.length) parts.push(`素材资料 ${sec.materialGroups.length} 个`)
  return parts.join(' · ')
}

function openCourse(courseId) {
  selectedCourseId.value = courseId
  selectedGroupKey.value = null
  lightboxIndex.value = null
}

function openGroup(key) {
  selectedGroupKey.value = key
  lightboxIndex.value = null
}

function closeGroup() {
  selectedGroupKey.value = null
  lightboxIndex.value = null
}

/* ---------------- 弹窗大图预览 ---------------- */

function openLightbox(index) {
  lightboxIndex.value = index
}

function closeLightbox() {
  lightboxIndex.value = null
}

function stepLightbox(delta) {
  const files = selectedGroup.value?.files
  if (!files || files.length < 2) return
  lightboxIndex.value = (lightboxIndex.value + delta + files.length) % files.length
}

function onKeyDown(e) {
  if (lightboxIndex.value == null) return
  if (e.key === 'Escape') {
    e.preventDefault()
    closeLightbox()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    stepLightbox(-1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    stepLightbox(1)
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)
  loading.value = true
  error.value = ''
  try {
    const res = await reviewApi.get()
    groups.value = res.groups || []
  } catch (e) {
    error.value = e.detail || e.message
    groups.value = []
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div class="page review-page">

    <div v-if="error" class="error-detail">{{ error }}</div>

    <div v-else-if="loading" class="card empty-state">
      <p>正在加载复习资料…</p>
    </div>

    <template v-else>
      <header class="hero">
        <div class="hero-mascot-wrap">
          <img :src="mascotUrl" alt="" class="hero-mascot" />
          <span class="hero-spark hero-spark-a" aria-hidden="true">✦</span>
          <span class="hero-spark hero-spark-b" aria-hidden="true">✦</span>
        </div>
        <div class="hero-text">
          <h1 class="hero-title">复习中心</h1>
          <p class="hero-sub">
            共 <strong>{{ courseSections.length }}</strong> 门课程 ·
            <strong>{{ groups.length }}</strong> 份复习资料
          </p>
        </div>
      </header>

      <div v-if="groups.length === 0" class="card empty-state">
        <img :src="mascotUrl" alt="" class="mascot" />
        <h3>还没有复习资料</h3>
        <p>把学过的素材标为已读，它们就会出现在这里。</p>
        <router-link to="/admin" class="btn btn-primary btn-lg" style="margin-top: 22px">去后台看看</router-link>
      </div>

      <!-- L3 详情:文件预览 -->
      <template v-else-if="selectedGroup">
        <nav class="crumbs">
          <button class="crumb-back" @click="closeGroup">
            <span aria-hidden="true">‹</span> {{ selectedCourse.courseName }}
          </button>
          <span class="crumb-current">{{ selectedGroup.title }}</span>
        </nav>

        <section class="card group-card">
          <header class="group-head">
            <span class="badge" :class="selectedGroup.kind === 'course' ? 'badge-blue' : 'badge-purple'">
              {{ selectedGroup.kind === 'course' ? '课程资料' : '素材资料' }}
            </span>
            <h2 class="group-title">{{ selectedGroup.title }}</h2>
            <span v-if="selectedGroup.kind === 'material'" class="group-course">{{ selectedGroup.courseName }}</span>
            <span class="group-count">{{ selectedGroup.files.length }} 份</span>
          </header>

          <div class="file-grid">
            <figure
              v-for="(file, fi) in selectedGroup.files"
              :key="file.url"
              class="file-card"
              @click="openLightbox(fi)"
            >
              <img v-if="file.kind === 'image'" :src="file.url" :alt="file.name" loading="lazy" />
              <iframe v-else-if="file.kind === 'pdf'" :src="file.url" :title="file.name"></iframe>
              <figcaption class="file-name">{{ file.name }}</figcaption>
              <button
                type="button"
                class="file-zoom"
                :aria-label="`放大预览 ${file.name}`"
                @click.stop="openLightbox(fi)"
              >⤢</button>
            </figure>
          </div>
        </section>
      </template>

      <!-- L2 课程页:复习项列表 -->
      <template v-else-if="selectedCourse">
        <nav class="crumbs">
          <button class="crumb-back" @click="selectedCourseId = null">
            <span aria-hidden="true">‹</span> 全部课程
          </button>
          <span class="crumb-current">{{ selectedCourse.courseName }}</span>
        </nav>

        <div class="review-rows">
          <button
            v-for="(item, i) in courseItems(selectedCourse)"
            :key="groupKey(item)"
            class="card review-row"
            :style="{ '--i': i }"
            @click="openGroup(groupKey(item))"
          >
            <span class="badge" :class="item.kind === 'course' ? 'badge-blue' : 'badge-purple'">
              {{ item.kind === 'course' ? '课程资料' : '素材资料' }}
            </span>
            <span class="row-title">{{ item.title }}</span>
            <span class="row-count">{{ item.files.length }} 份</span>
            <span class="row-go" aria-hidden="true">›</span>
          </button>
        </div>
      </template>

      <!-- L1 首页:课程卡片 -->
      <div v-else class="course-grid">
        <button
          v-for="(sec, i) in courseSections"
          :key="sec.courseId"
          class="card course-card"
          :style="{ '--i': i }"
          @click="openCourse(sec.courseId)"
        >
          <h2 class="course-card-name">{{ sec.courseName }}</h2>
          <p class="course-card-meta">{{ summaryOf(sec) }}</p>
          <span class="course-card-go">进入复习 <span aria-hidden="true">›</span></span>
        </button>
      </div>

      <!-- 弹窗大图预览 -->
      <transition name="lightbox-fade">
        <div
          v-if="lightboxFile"
          class="review-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="资料预览"
          @click.self="closeLightbox"
        >
          <div class="lightbox-card card">
            <header class="lightbox-head">
              <span class="lightbox-name">{{ lightboxFile.name }}</span>
              <span class="lightbox-count">
                {{ lightboxIndex + 1 }} / {{ selectedGroup.files.length }}
              </span>
              <button
                type="button"
                class="icon-btn lightbox-close"
                aria-label="关闭预览"
                @click="closeLightbox"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 6L6 18" />
                  <path d="M6 6l12 12" />
                </svg>
              </button>
            </header>

            <div class="lightbox-body">
              <button
                type="button"
                class="lightbox-nav prev"
                aria-label="上一份"
                :disabled="selectedGroup.files.length < 2"
                @click="stepLightbox(-1)"
              >‹</button>

              <img
                v-if="lightboxFile.kind === 'image'"
                :src="lightboxFile.url"
                :alt="lightboxFile.name"
                class="lightbox-media"
              />
              <iframe
                v-else-if="lightboxFile.kind === 'pdf'"
                :src="lightboxFile.url"
                :title="lightboxFile.name"
                class="lightbox-media lightbox-frame"
              ></iframe>

              <button
                type="button"
                class="lightbox-nav next"
                aria-label="下一份"
                :disabled="selectedGroup.files.length < 2"
                @click="stepLightbox(1)"
              >›</button>
            </div>
          </div>
        </div>
      </transition>
    </template>
  </div>
</template>

<style scoped>
/* ---------- 顶部问候(与首页同一套结构) ---------- */
.hero {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 26px;
  margin-bottom: 24px;
  border-radius: var(--radius-card);
  border: 3px solid #fff;
  background:
    radial-gradient(circle at 88% 20%, rgba(255, 255, 255, 0.55), transparent 45%),
    linear-gradient(120deg, var(--blue-bg), var(--purple-bg) 52%, var(--pink-bg));
  box-shadow: var(--shadow);
}

.hero-mascot-wrap {
  position: relative;
  flex: 0 0 auto;
}

.hero-mascot {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  object-fit: cover;
  border: 5px solid #fff;
  box-shadow: var(--shadow-blue);
  animation: float-y 3.4s var(--ease-soft) infinite;
}

.hero-spark {
  position: absolute;
  color: var(--pink);
  font-size: 15px;
  animation: pulse 2.2s ease-in-out infinite;
}

.hero-spark-a {
  top: -4px;
  right: 0;
}

.hero-spark-b {
  bottom: 2px;
  left: -6px;
  color: var(--purple);
  animation-delay: 0.7s;
}

.hero-text {
  flex: 1 1 auto;
  min-width: 0;
}

.hero-title {
  font-size: 30px;
  line-height: 1.25;
  background: linear-gradient(90deg, var(--blue), var(--purple) 70%, var(--pink));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-sub {
  margin: 6px 0 0;
  font-size: 16px;
  color: var(--muted);
}

.hero-sub strong {
  font-family: var(--font-display);
  font-size: 20px;
  color: var(--purple);
}

/* ---------- 返回入口 ---------- */
.crumbs {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.crumb-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border-radius: var(--radius-pill);
  background: #fff;
  border: 2px solid var(--border);
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 800;
  color: var(--muted);
  transition: transform 180ms var(--ease-bounce), color 200ms ease,
    border-color 200ms ease, box-shadow 200ms ease;
}

.crumb-back:hover {
  color: var(--blue);
  border-color: var(--blue);
  box-shadow: var(--shadow-sm);
  transform: translateX(-3px);
}

.crumb-back:active {
  transform: translateX(-3px) scale(0.97);
}

.crumb-current {
  font-size: 14px;
  font-weight: 800;
  color: var(--secondary);
}

/* ---------- L1 课程卡片 ---------- */
.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}

.course-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 22px 24px;
  cursor: pointer;
  border: 2px solid var(--border);
  animation: pop-in 420ms var(--ease-bounce) backwards;
  animation-delay: calc(var(--i, 0) * 60ms);
  transition: transform 200ms var(--ease-bounce), border-color 200ms ease,
    box-shadow 200ms ease;
}

.course-card:hover {
  transform: translateY(-4px);
  border-color: var(--blue);
  box-shadow: var(--shadow), var(--shadow-pop);
}

.course-card:active {
  transform: translateY(1px) scale(0.99);
}

.course-card-name {
  font-size: 20px;
  line-height: 1.3;
  word-break: break-word;
}

.course-card-meta {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
}

.course-card-go {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 800;
  color: var(--blue);
}

/* ---------- L2 复习项列表 ---------- */
.review-rows {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.review-row {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  text-align: left;
  padding: 18px 22px;
  cursor: pointer;
  border: 2px solid transparent;
  animation: pop-in 420ms var(--ease-bounce) backwards;
  animation-delay: calc(var(--i, 0) * 50ms);
  transition: transform 200ms var(--ease-bounce), border-color 200ms ease,
    box-shadow 200ms ease;
}

.review-row:hover {
  transform: translateY(-3px);
  border-color: var(--purple);
  box-shadow: var(--shadow-sm);
}

.review-row:active {
  transform: translateY(1px) scale(0.99);
}

.row-title {
  flex: 1 1 auto;
  min-width: 0;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  word-break: break-word;
}

.row-count {
  font-size: 13px;
  font-weight: 800;
  color: var(--secondary);
  white-space: nowrap;
}

.row-go {
  font-size: 22px;
  line-height: 1;
  font-weight: 800;
  color: var(--purple);
}

/* ---------- L3 资料分组(沿用原预览样式) ---------- */
.group-card {
  padding: 22px 24px;
  margin-bottom: 24px;
  animation: pop-in 420ms var(--ease-bounce) backwards;
}

.group-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.group-title {
  font-size: 22px;
  line-height: 1.3;
}

.group-course {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
}

.group-count {
  margin-left: auto;
  font-size: 13px;
  font-weight: 700;
  color: var(--secondary);
}

.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.file-card {
  position: relative;
  margin: 0;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  background: var(--bg);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  transition: transform 200ms var(--ease-bounce), border-color 200ms ease,
    box-shadow 200ms ease;
}

.file-card:hover {
  transform: translateY(-3px);
  border-color: var(--blue);
  box-shadow: var(--shadow-sm);
}

.file-card img {
  width: 100%;
  height: 200px;
  object-fit: contain;
  border-radius: var(--radius-xs);
  background: #fff;
}

.file-card iframe {
  width: 100%;
  height: 360px;
  border: 0;
  border-radius: var(--radius-xs);
  background: #fff;
}

.file-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
  text-align: center;
  word-break: break-all;
}

.file-zoom {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 16px;
  font-weight: 800;
  color: var(--blue);
  background: rgba(255, 255, 255, 0.92);
  border: 2px solid rgba(63, 140, 255, 0.35);
  box-shadow: var(--shadow-sm);
  transition: transform 180ms var(--ease-bounce), background 200ms ease,
    color 200ms ease, border-color 200ms ease;
}

.file-zoom:hover {
  color: #fff;
  background: var(--blue);
  border-color: var(--blue);
  transform: translateY(-2px) rotate(-6deg);
}

.file-zoom:active {
  transform: translateY(1px) scale(0.95);
}

/* ---------- 弹窗大图预览 ---------- */
.review-lightbox {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  background: rgba(43, 37, 69, 0.42);
  backdrop-filter: blur(7px);
  -webkit-backdrop-filter: blur(7px);
}

.lightbox-card {
  width: 90vw;
  max-width: 1400px;
  height: 90vh;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-width: 3px;
}

.lightbox-head {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: none;
  padding: 10px 16px;
  border-bottom: 2px solid var(--border);
  background: linear-gradient(120deg, var(--blue-bg), var(--purple-bg) 55%, var(--pink-bg));
}

.lightbox-name {
  flex: 1 1 auto;
  min-width: 0;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lightbox-count {
  flex: none;
  padding: 3px 14px;
  border-radius: var(--radius-pill);
  background: #fff;
  font-size: 14px;
  font-weight: 800;
  color: var(--purple);
  box-shadow: var(--shadow-pop);
}

.lightbox-close {
  flex: none;
  width: 38px;
  height: 38px;
}

.lightbox-body {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px;
  background: var(--bg);
}

.lightbox-media {
  max-width: 100%;
  max-height: 100%;
  border-radius: var(--radius-sm);
  background: #fff;
}

img.lightbox-media {
  object-fit: contain;
}

.lightbox-frame {
  width: 100%;
  height: 100%;
  border: 0;
}

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(160deg, var(--purple), #8a4dff);
  box-shadow: var(--shadow), var(--shadow-pop);
  transition: transform 180ms var(--ease-bounce), opacity 200ms ease,
    box-shadow 200ms ease;
}

.lightbox-nav.prev {
  left: 18px;
}

.lightbox-nav.next {
  right: 18px;
}

.lightbox-nav:hover:not(:disabled) {
  transform: translateY(-50%) scale(1.08);
}

.lightbox-nav:active:not(:disabled) {
  transform: translateY(-50%) scale(0.94);
}

.lightbox-nav:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: var(--shadow-sm);
}

.lightbox-fade-enter-active {
  transition: opacity 250ms ease;
}

.lightbox-fade-leave-active {
  transition: opacity 200ms ease;
}

.lightbox-fade-enter-from,
.lightbox-fade-leave-to {
  opacity: 0;
}

.lightbox-fade-enter-active .lightbox-card {
  transition: transform 340ms var(--ease-bounce);
}

.lightbox-fade-leave-active .lightbox-card {
  transition: transform 180ms ease;
}

.lightbox-fade-enter-from .lightbox-card,
.lightbox-fade-leave-to .lightbox-card {
  transform: scale(0.9) translateY(18px);
}

@media (max-width: 768px) {
  .hero {
    flex-wrap: wrap;
    padding: 16px 18px;
    gap: 12px;
  }
  .hero-mascot {
    width: 62px;
    height: 62px;
    border-width: 4px;
  }
  .hero-title {
    font-size: 22px;
  }
  .course-grid {
    grid-template-columns: 1fr;
  }
  .review-row {
    padding: 15px 18px;
    gap: 10px;
  }
  .row-title {
    font-size: 16px;
  }
  .group-card {
    padding: 16px;
  }
  .file-grid {
    grid-template-columns: 1fr;
  }
  .lightbox-card {
    width: 94vw;
    height: 92vh;
  }
  .lightbox-head {
    padding: 8px 12px;
    gap: 10px;
  }
  .lightbox-name {
    font-size: 15px;
  }
  .lightbox-body {
    padding: 8px;
  }
  .lightbox-nav {
    width: 42px;
    height: 42px;
    font-size: 22px;
  }
  .lightbox-nav.prev {
    left: 8px;
  }
  .lightbox-nav.next {
    right: 8px;
  }
}
</style>
