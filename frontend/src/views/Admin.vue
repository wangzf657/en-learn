<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { adminApi, scoringApi } from '../api.js'
import { loadTtsSettings, saveTtsSettings, listEnglishVoices, preview } from '../utils/tts.js'

const courses = ref([])
const courseDetails = ref({})
const loading = ref(false)
const error = ref('')
const saveHint = ref('')

const libraryRoot = ref('')
const libraryLoading = ref(false)

const importFolder = ref('')
const importLoading = ref(false)
const importError = ref('')
const importResult = ref(null)

const expandedCourseIds = ref(new Set())
const selectedCourseId = ref(null)
const materialPage = ref(1)
const materialPageSize = 10

const scheduleDateFrom = ref('')
const scheduleDateTo = ref('')
const scheduleCourseId = ref('')
const scheduleLoading = ref(false)
const scheduleResult = ref(null)

const scheduleMonth = ref('')
const scheduleDays = ref([])
const scheduleDaysLoading = ref(false)
const selectedCalendarDate = ref('')

const addingDate = ref('')
const selectedMaterialIds = ref(new Set())
const pickerCourseId = ref('')
const pickerExpanded = ref(true)

const scoringLoading = ref(false)
const scoringError = ref('')
const scoringSaved = ref(false)
const scoringProviders = ref([])
const scoringProvider = ref('mock')
const scoringOptions = ref({})

// 与后端 echoic/providers/unisound.py 的兜底值保持一致
const SCORING_DEFAULTS = { mode: 'E', base_url: 'http://edu.hivoice.cn/eval' }

// 浏览器端选声(纯前端,localStorage 持久化)
const ttsSettings = loadTtsSettings()
const ttsVoices = ref([])
const ttsVoiceURI = ref(ttsSettings.voiceURI)
const ttsRate = ref(ttsSettings.rate)
const ttsRates = [0.5, 0.75, 0.9, 1, 1.1, 1.25]
const ttsSaved = ref(false)

const activeTab = ref('settings')
const tabs = [
  { key: 'settings', label: '通用设置' },
  { key: 'courses', label: '课程管理' },
  { key: 'checkin', label: '打卡管理' },
]

const now = new Date()
const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
scheduleMonth.value = defaultMonth

onMounted(async () => {
  await loadLibrary()
  await loadCourses()
  await loadScheduleDays()
  await loadScoring()
  loadTtsVoices()
})

watch(scoringProvider, (next) => {
  if (next === 'mock') {
    scoringOptions.value = {}
    return
  }
  // 已填过的不动,缺的补默认值(切服务时让生效值直接可见)
  scoringOptions.value = { ...SCORING_DEFAULTS, ...scoringOptions.value }
})

watch(scheduleMonth, () => {
  loadScheduleDays()
})

watch(selectedCourseId, (id) => {
  materialPage.value = 1
  if (id && !courseDetails.value[id]) {
    const course = courses.value.find((c) => c.id === id)
    if (course) loadCourseDetail(course)
  }
})

watch(scheduleDays, (days) => {
  const month = scheduleMonth.value
  if (!month) return
  const daysWithMaterials = days.filter((d) => (d.materials || []).length > 0)
  const current = selectedCalendarDate.value
  if (current && current.startsWith(month + '-') && daysWithMaterials.some((d) => d.date === current)) {
    return
  }
  selectedCalendarDate.value = daysWithMaterials.length ? daysWithMaterials[0].date : null
})

watch(pickerCourseId, (id) => {
  if (!id) return
  const course = courses.value.find((c) => c.id === id)
  if (course) loadCourseDetail(course)
})

async function loadLibrary() {
  try {
    const data = await adminApi.getLibrary()
    libraryRoot.value = data.root || ''
  } catch (e) {
    error.value = e.detail || e.message
  }
}

async function saveLibrary() {
  libraryLoading.value = true
  saveHint.value = ''
  try {
    await adminApi.saveLibrary(libraryRoot.value)
    saveHint.value = '已保存'
    setTimeout(() => (saveHint.value = ''), 2200)
  } catch (e) {
    alert(e.detail || e.message)
  } finally {
    libraryLoading.value = false
  }
}

async function loadScoring() {
  scoringLoading.value = true
  scoringError.value = ''
  try {
    const data = await scoringApi.getScoring()
    scoringProviders.value = data.providers || []
    scoringProvider.value = data.provider || 'mock'
    scoringOptions.value = { ...SCORING_DEFAULTS, ...(data.options || {}) }
  } catch (e) {
    scoringError.value = e.detail || e.message
  } finally {
    scoringLoading.value = false
  }
}

async function saveScoring() {
  scoringError.value = ''
  scoringSaved.value = false
  const payload = {
    provider: scoringProvider.value,
    options: scoringProvider.value === 'mock' ? {} : { ...scoringOptions.value },
  }
  if (payload.provider !== 'mock') {
    if (!payload.options.appkey || !payload.options.secret) {
      scoringError.value = 'AppKey 和 Secret 不能为空'
      return
    }
  }
  try {
    await scoringApi.saveScoring(payload)
    scoringSaved.value = true
    setTimeout(() => (scoringSaved.value = false), 2200)
  } catch (e) {
    scoringError.value = e.detail || e.message
  }
}

function loadTtsVoices() {
  if (!('speechSynthesis' in window)) return
  const synth = window.speechSynthesis
  const update = () => {
    ttsVoices.value = listEnglishVoices()
  }
  update()
  if (typeof synth.addEventListener === 'function') {
    synth.addEventListener('voiceschanged', update)
  }
}

function previewTts() {
  preview('Hello, how are you today?', { voiceURI: ttsVoiceURI.value, rate: ttsRate.value })
}

function saveTts() {
  saveTtsSettings({ voiceURI: ttsVoiceURI.value, rate: ttsRate.value })
  ttsSaved.value = true
  setTimeout(() => (ttsSaved.value = false), 2200)
}

async function loadCourses() {
  loading.value = true
  error.value = ''
  try {
    const res = await adminApi.listCourses()
    courses.value = res.courses || []
  } catch (e) {
    error.value = e.detail || e.message
  } finally {
    loading.value = false
  }
}

async function loadCourseDetail(course) {
  if (courseDetails.value[course.id]) return
  try {
    const data = await adminApi.getCourse(course.id)
    courseDetails.value[data.id] = data
  } catch (e) {
    alert(e.detail || e.message)
  }
}

function toggleCourseExpanded(course) {
  const next = new Set(expandedCourseIds.value)
  if (next.has(course.id)) {
    next.delete(course.id)
    if (selectedCourseId.value === course.id) selectedCourseId.value = null
  } else {
    next.add(course.id)
    selectedCourseId.value = course.id
    loadCourseDetail(course)
  }
  expandedCourseIds.value = next
}

async function submitImport() {
  importLoading.value = true
  importError.value = ''
  importResult.value = null
  try {
    importResult.value = await adminApi.importCourse(importFolder.value)
    await loadCourses()
    await loadScheduleDays()
  } catch (e) {
    importError.value = e.detail || e.message
  } finally {
    importLoading.value = false
  }
}

async function removeCourse(course) {
  if (!confirm(`删除课程《${course.name}》会同时删除其 ${course.materialCount} 个素材及所有相关排班，确定继续吗？`)) return
  try {
    await adminApi.deleteCourse(course.id)
    delete courseDetails.value[course.id]
    if (selectedCourseId.value === course.id) selectedCourseId.value = null
    await loadCourses()
    await loadScheduleDays()
  } catch (e) {
    alert(e.detail || e.message)
  }
}

async function toggleMaterialRead(material) {
  try {
    const next = !material.read
    await adminApi.setMaterialRead(material.id, next)
    material.read = next
    await loadCourses()
  } catch (e) {
    alert(e.detail || e.message)
  }
}

async function submitSchedule() {
  scheduleLoading.value = true
  scheduleResult.value = null
  try {
    const res = await adminApi.createSchedule(scheduleCourseId.value, scheduleDateFrom.value, scheduleDateTo.value)
    scheduleResult.value = res
    await loadCourses()
    await loadScheduleDays()
  } catch (e) {
    alert(e.detail || e.message)
  } finally {
    scheduleLoading.value = false
  }
}

async function loadScheduleDays() {
  scheduleDaysLoading.value = true
  try {
    const res = await adminApi.getSchedule(scheduleMonth.value)
    scheduleDays.value = res.days || []
  } catch (e) {
    error.value = e.detail || e.message
    scheduleDays.value = []
  } finally {
    scheduleDaysLoading.value = false
  }
}

const selectedCourse = computed(() => courses.value.find((c) => c.id === selectedCourseId.value))
const selectedCourseDetail = computed(() => (selectedCourseId.value ? courseDetails.value[selectedCourseId.value] : null))

const paginatedMaterials = computed(() => {
  const materials = selectedCourseDetail.value?.materials || []
  const start = (materialPage.value - 1) * materialPageSize
  return materials.slice(start, start + materialPageSize)
})

const materialTotalPages = computed(() => {
  const materials = selectedCourseDetail.value?.materials || []
  return Math.ceil(materials.length / materialPageSize) || 1
})

const selectedCourseReadStats = computed(() => {
  const materials = selectedCourseDetail.value?.materials || []
  const read = materials.filter((m) => m.read).length
  return { read, total: materials.length }
})

const dayMaterialsMap = computed(() => {
  const map = {}
  for (const day of scheduleDays.value) {
    map[day.date] = day.materials || []
  }
  return map
})

const monthDays = computed(() => {
  const [y, m] = scheduleMonth.value.split('-').map(Number)
  if (!y || !m) return []
  const daysInMonth = new Date(y, m, 0).getDate()
  return Array.from({ length: daysInMonth }, (_, i) => {
    const day = String(i + 1).padStart(2, '0')
    return `${scheduleMonth.value}-${day}`
  })
})

const calendarCells = computed(() => {
  const [y, m] = scheduleMonth.value.split('-').map(Number)
  if (!y || !m) return []
  const firstDay = new Date(y, m - 1, 1)
  const daysInMonth = new Date(y, m, 0).getDate()
  const firstWeekday = firstDay.getDay()
  const leading = firstWeekday === 0 ? 6 : firstWeekday - 1

  const cells = []
  for (let i = 0; i < leading; i++) {
    cells.push({ date: null, day: null, materials: [] })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const date = `${scheduleMonth.value}-${String(d).padStart(2, '0')}`
    cells.push({ date, day: d, materials: dayMaterialsMap.value[date] || [] })
  }
  const trailing = (7 - (cells.length % 7)) % 7
  for (let i = 0; i < trailing; i++) {
    cells.push({ date: null, day: null, materials: [] })
  }
  return cells
})

const selectedDayMaterials = computed(() => {
  if (!selectedCalendarDate.value) return []
  return dayMaterialsMap.value[selectedCalendarDate.value] || []
})

const pickerCourse = computed(() => courses.value.find((c) => c.id === pickerCourseId.value))
const pickerCourseMaterials = computed(() => {
  if (!pickerCourse.value) return []
  return courseDetails.value[pickerCourse.value.id]?.materials || []
})

function openAddMaterials(date) {
  addingDate.value = date
  selectedMaterialIds.value = new Set()
  pickerCourseId.value = ''
  pickerExpanded.value = true
  const existing = dayMaterialsMap.value[date] || []
  for (const m of existing) {
    selectedMaterialIds.value.add(m.id)
  }
}

function closeAddMaterials() {
  addingDate.value = ''
  selectedMaterialIds.value = new Set()
  pickerCourseId.value = ''
  pickerExpanded.value = true
}

function toggleMaterialSelection(id) {
  const next = new Set(selectedMaterialIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedMaterialIds.value = next
}

async function confirmAddMaterials(date) {
  scheduleLoading.value = true
  try {
    await adminApi.addDayMaterials(date, Array.from(selectedMaterialIds.value))
    await loadScheduleDays()
    await loadCourses()
    closeAddMaterials()
  } catch (e) {
    alert(e.detail || e.message)
  } finally {
    scheduleLoading.value = false
  }
}

async function clearDay(date) {
  if (!confirm(`确定清空 ${date} 的所有打卡内容吗？`)) return
  scheduleLoading.value = true
  try {
    await adminApi.deleteDay(date)
    await loadScheduleDays()
    await loadCourses()
  } catch (e) {
    alert(e.detail || e.message)
  } finally {
    scheduleLoading.value = false
  }
}

async function clearMonth() {
  if (!confirm(`确定清空 ${scheduleMonth.value} 整月的打卡排期吗？`)) return
  scheduleLoading.value = true
  try {
    await adminApi.clearMonth(scheduleMonth.value)
    await loadScheduleDays()
    await loadCourses()
  } catch (e) {
    alert(e.detail || e.message)
  } finally {
    scheduleLoading.value = false
  }
}

async function removeDayMaterial(date, material) {
  if (!confirm(`确定从 ${date} 移除《${material.title}》吗？`)) return
  scheduleLoading.value = true
  try {
    await adminApi.removeDayMaterial(date, material.id)
    await loadScheduleDays()
    await loadCourses()
  } catch (e) {
    alert(e.detail || e.message)
  } finally {
    scheduleLoading.value = false
  }
}

function formatDates(dates) {
  if (!dates || dates.length === 0) return '—'
  return dates.join('、')
}

function selectCalendarDate(date) {
  if (date) selectedCalendarDate.value = date
}
</script>

<template>
  <div class="page admin-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">后台管理</h1>
        <p class="page-subtitle">管理课程、素材、打卡与评分服务</p>
      </div>
      <div class="actions">
        <router-link to="/" class="btn btn-secondary">回日历</router-link>
      </div>
    </header>

    <nav class="admin-tabs" aria-label="管理模块">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div v-if="error" class="error-detail">{{ error }}</div>

    <div v-show="activeTab === 'settings'" class="card settings-card">
      <h2>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19.14 12.94c.04.3.06.61.06.94 0 .32-.02.64-.07.94l2.03 1.58a.49.49 0 0 1 .12.61l-1.92 3.32a.488.488 0 0 1-.59.22l-2.39-.96a7.93 7.93 0 0 1-1.62.94l-.36 2.54a.484.484 0 0 1-.48.41H9.5a.484.484 0 0 1-.48-.41l-.36-2.54a7.597 7.597 0 0 1-1.62-.94l-2.39.96a.488.488 0 0 1-.59-.22L1.74 16.11a.49.49 0 0 1 .12-.61l2.03-1.58A7.93 7.93 0 0 1 3.78 12c0-.32.02-.64.07-.94L1.82 9.48a.49.49 0 0 1-.12-.61l1.92-3.32a.488.488 0 0 1 .59-.22l2.39.96c.5-.38 1.04-.7 1.62-.94l.36-2.54a.484.484 0 0 1 .48-.41H14.5c.24 0 .44.17.48.41l.36 2.54c.58.24 1.12.56 1.62.94l2.39-.96a.488.488 0 0 1 .59.22l1.92 3.32c.12.21.08.47-.12.61l-2.03 1.58zM12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"/>
        </svg>
        通用设置
      </h2>

      <div class="form-grid">
        <label class="full">
          <span>统一前缀</span>
          <input type="text" v-model="libraryRoot" placeholder="D:\videos" />
        </label>
        <div class="full form-actions">
          <button class="btn btn-primary" :disabled="libraryLoading" @click="saveLibrary">
            <span v-if="libraryLoading">保存中…</span>
            <span v-else>保存</span>
          </button>
          <span v-if="saveHint" class="save-hint">{{ saveHint }}</span>
        </div>
      </div>

      <div class="scoring-section">
        <h3>发音评分服务</h3>
        <div v-if="scoringLoading" class="empty-state" style="padding: 20px">
          <p>正在加载配置…</p>
        </div>
        <div v-else class="form-grid">
          <label>
            <span>评分服务</span>
            <select v-model="scoringProvider">
              <option v-for="p in scoringProviders" :key="p" :value="p">{{ p }}</option>
            </select>
          </label>
          <template v-if="scoringProvider !== 'mock'">
            <label>
              <span>AppKey</span>
              <input type="text" v-model="scoringOptions.appkey" placeholder="必填" />
            </label>
            <label>
              <span>Secret</span>
              <input type="password" v-model="scoringOptions.secret" placeholder="必填" />
            </label>
            <label>
              <span>模式</span>
              <input type="text" v-model="scoringOptions.mode" />
            </label>
            <label>
              <span>服务地址</span>
              <input type="text" v-model="scoringOptions.base_url" />
            </label>
          </template>
          <div class="full form-actions">
            <button class="btn btn-primary" @click="saveScoring">保存</button>
            <span v-if="scoringSaved" class="save-hint">已保存</span>
          </div>
          <div v-if="scoringError" class="full error-detail">{{ scoringError }}</div>
        </div>
      </div>

      <div class="tts-section">
        <h3>浏览器端选声</h3>
        <p class="tts-hint">选择系统内置的英语语音并试听，跟读与台词朗读将使用该音色。</p>
        <div class="form-grid">
          <label>
            <span>语音</span>
            <select v-model="ttsVoiceURI">
              <option value="">系统默认</option>
              <option v-for="v in ttsVoices" :key="v.voiceURI" :value="v.voiceURI">{{ v.name }}（{{ v.lang }}）</option>
            </select>
          </label>
          <label>
            <span>语速</span>
            <select v-model.number="ttsRate">
              <option v-for="r in ttsRates" :key="r" :value="r">{{ r }}</option>
            </select>
          </label>
          <div class="full form-actions">
            <button class="btn btn-primary" @click="previewTts">试听</button>
            <button class="btn btn-secondary" @click="saveTts">保存音色</button>
            <span v-if="ttsSaved" class="save-hint">已保存</span>
          </div>
        </div>
      </div>
    </div>

    <div v-show="activeTab === 'courses'" class="card course-card">
      <h2>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/>
        </svg>
        课程管理
      </h2>

      <div class="form-grid import-form">
        <label>
          <span>文件夹路径</span>
          <input type="text" v-model="importFolder" placeholder="前缀下的课程文件夹，如 wowEnglish\S01" />
        </label>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="importLoading" @click="submitImport">
            <span v-if="importLoading">导入中…</span>
            <span v-else>导入课程</span>
          </button>
        </div>
        <div v-if="importError" class="full error-detail">{{ importError }}</div>
      </div>

      <div v-if="importResult" class="import-result">
        <div class="result-section">
          <h3>课程 {{ importResult.course.name }} · {{ importResult.course.materialCount }} 个素材</h3>
          <ul>
            <li v-for="item in importResult.materials" :key="item.id">
              <span class="title">{{ item.title }}</span>
              <span v-if="item.updated" class="tag updated">覆盖</span>
              <span v-else class="tag created">新增</span>
            </li>
          </ul>
        </div>
        <div v-if="importResult.skipped.length" class="result-section">
          <h3>跳过 {{ importResult.skipped.length }} 条</h3>
          <ul>
            <li v-for="(item, idx) in importResult.skipped" :key="idx">
              <span class="file">{{ item.file }}</span>
              <span class="reason">{{ item.reason }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="loading" class="empty-state">
        <p>正在加载课程列表…</p>
      </div>
      <div v-else-if="courses.length === 0" class="empty-state">
        <h3>暂无课程</h3>
        <p>先在上方导入课程。</p>
      </div>
      <div v-else class="course-layout">
        <div class="course-list-panel">
          <div
            v-for="course in courses"
            :key="course.id"
            class="course-item"
            :class="{ active: selectedCourseId === course.id }"
          >
            <div class="course-header" @click="toggleCourseExpanded(course)">
              <div class="course-main">
                <span class="course-name">{{ course.name }}</span>
                <span class="course-meta">{{ course.materialCount }} 个素材 · 已读 {{ course.readCount }}/{{ course.materialCount }}</span>
                <span class="course-dates">打卡日期：{{ formatDates(course.dates) }}</span>
              </div>
              <div class="course-actions" @click.stop>
                <button class="btn btn-ghost btn-sm" @click.stop="removeCourse(course)">删除课程</button>
                <button class="btn btn-ghost btn-sm" @click.stop="toggleCourseExpanded(course)">
                  {{ expandedCourseIds.has(course.id) ? '收起' : '展开' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="material-panel">
          <div v-if="!selectedCourseId" class="empty-state">
            <p>在左侧选择一门课程查看素材</p>
          </div>
          <div v-else-if="!selectedCourseDetail" class="empty-state">
            <p>正在加载素材…</p>
          </div>
          <div v-else class="material-table-wrap">
            <div class="material-table-head">
              <h3>{{ selectedCourseDetail.name }}</h3>
              <span class="badge" :class="selectedCourseReadStats.read === selectedCourseReadStats.total ? 'badge-green' : 'badge-blue'">
                已读 {{ selectedCourseReadStats.read }}/{{ selectedCourseReadStats.total }}
              </span>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style="width: 64px">序号</th>
                    <th>标题</th>
                    <th style="width: 100px">状态</th>
                    <th style="width: 120px">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(m, idx) in paginatedMaterials"
                    :key="m.id"
                    class="material-row"
                  >
                    <td>{{ (materialPage - 1) * materialPageSize + idx + 1 }}</td>
                    <td class="material-title">{{ m.title }}</td>
                    <td>
                      <span class="badge" :class="m.read ? 'badge-green' : 'badge-blue'">
                        {{ m.read ? '已读' : '未读' }}
                      </span>
                    </td>
                    <td>
                      <button
                        class="btn btn-sm"
                        :class="m.read ? 'btn-secondary' : 'btn-primary'"
                        @click="toggleMaterialRead(m)"
                      >
                        {{ m.read ? '已读' : '未读' }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="materialTotalPages > 1" class="pagination">
              <button
                class="btn btn-secondary btn-sm"
                :disabled="materialPage === 1"
                @click="materialPage--"
              >
                上一页
              </button>
              <span class="page-info">{{ materialPage }} / {{ materialTotalPages }}</span>
              <button
                class="btn btn-secondary btn-sm"
                :disabled="materialPage === materialTotalPages"
                @click="materialPage++"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-show="activeTab === 'checkin'" class="card checkin-card">
      <h2>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM9 10H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z"/>
        </svg>
        打卡管理
      </h2>

      <div class="form-grid schedule-form">
        <label>
          <span>开始日期</span>
          <input type="date" v-model="scheduleDateFrom" />
        </label>
        <label>
          <span>结束日期</span>
          <input type="date" v-model="scheduleDateTo" />
        </label>
        <label>
          <span>课程</span>
          <select v-model="scheduleCourseId">
            <option value="">选择课程</option>
            <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="scheduleLoading || !scheduleCourseId" @click="submitSchedule">
            <span v-if="scheduleLoading">安排中…</span>
            <span v-else>添加课程</span>
          </button>
        </div>
      </div>

      <div v-if="scheduleResult" class="schedule-result">
        <span class="save-hint">已安排 {{ scheduleResult.added }} 个素材</span>
        <div v-for="day in scheduleResult.scheduled || []" :key="day.date" class="schedule-day">
          <span class="day-date">{{ day.date }}</span>
          <span class="day-materials">{{ (day.materialIds || []).length }} 个素材</span>
        </div>
      </div>

      <div class="calendar-section">
        <div class="month-row">
          <label class="month-picker">
            <span>月份</span>
            <input type="month" v-model="scheduleMonth" />
          </label>
          <button class="btn btn-ghost btn-sm" @click="clearMonth">清空当月</button>
        </div>

        <div v-if="scheduleDaysLoading" class="empty-state">
          <p>正在更新打卡…</p>
        </div>

        <div class="calendar-grid">
          <div v-for="d in ['一', '二', '三', '四', '五', '六', '日']" :key="d" class="calendar-weekday">{{ d }}</div>
          <div
            v-for="(cell, idx) in calendarCells"
            :key="idx"
            class="calendar-cell"
            :class="{
              empty: !cell.date,
              active: cell.date === selectedCalendarDate,
              'has-materials': cell.materials.length > 0,
            }"
            @click="selectCalendarDate(cell.date)"
          >
            <span v-if="cell.materials.length" class="cell-indicator" aria-hidden="true"></span>
            <span class="cell-day">{{ cell.day }}</span>
            <span v-if="cell.materials.length" class="cell-count">{{ cell.materials.length }} 个素材</span>
          </div>
        </div>

        <div v-if="selectedCalendarDate" class="day-detail">
          <div class="day-detail-head">
            <h3>{{ selectedCalendarDate }}</h3>
            <div class="day-actions">
              <button class="btn btn-ghost btn-sm" @click="openAddMaterials(selectedCalendarDate)">添加素材</button>
              <button class="btn btn-ghost btn-sm" @click="clearDay(selectedCalendarDate)">清空当天</button>
            </div>
          </div>
          <div class="day-materials">
            <div
              v-for="m in selectedDayMaterials"
              :key="m.id"
              class="material-chip"
            >
              <span class="chip-title">{{ m.title }}</span>
              <span class="chip-course">{{ m.courseName }}</span>
              <button class="remove-material" @click="removeDayMaterial(selectedCalendarDate, m)" title="移除">×</button>
            </div>
            <span v-if="!selectedDayMaterials.length" class="day-empty">当天无打卡</span>
          </div>

          <div v-if="addingDate === selectedCalendarDate" class="material-picker">
            <div class="picker-title">选择素材</div>
            <div class="picker-course-select">
              <select v-model="pickerCourseId">
                <option value="">选择课程</option>
                <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>
            <div v-if="pickerCourse" class="picker-course-materials">
              <div class="picker-course-header">
                <span class="picker-course-name">{{ pickerCourse.name }}</span>
                <button class="btn btn-ghost btn-sm" @click="pickerExpanded = !pickerExpanded">
                  {{ pickerExpanded ? '收起' : '展开' }}
                </button>
              </div>
              <div v-show="pickerExpanded" class="picker-options">
                <label
                  v-for="m in pickerCourseMaterials"
                  :key="m.id"
                  class="picker-option"
                  :class="{ disabled: (dayMaterialsMap[selectedCalendarDate] || []).some((x) => x.id === m.id) }"
                >
                  <input
                    type="checkbox"
                    :checked="selectedMaterialIds.has(m.id)"
                    :disabled="(dayMaterialsMap[selectedCalendarDate] || []).some((x) => x.id === m.id)"
                    @change="toggleMaterialSelection(m.id)"
                  />
                  <span class="option-title">{{ m.title }}</span>
                  <span class="option-read">{{ m.read ? '已读' : '未读' }}</span>
                </label>
                <div v-if="!pickerCourseMaterials.length" class="empty-state" style="padding: 24px">
                  <p>暂无素材</p>
                </div>
              </div>
            </div>
            <div class="picker-actions">
              <button class="btn btn-primary btn-sm" :disabled="scheduleLoading || !pickerCourseId" @click="confirmAddMaterials(selectedCalendarDate)">确认</button>
              <button class="btn btn-secondary btn-sm" @click="closeAddMaterials">取消</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page .page-header {
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 10px;
}

.admin-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  padding: 7px;
  background: var(--card);
  border: 2px solid var(--border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
}

.tab-btn {
  flex: 1;
  padding: 10px 18px;
  min-height: 46px;
  border-radius: var(--radius-pill);
  font-size: 15px;
  font-weight: 700;
  color: var(--muted);
  transition: background var(--transition), color var(--transition),
    transform var(--transition), box-shadow var(--transition);
}

.tab-btn:hover {
  color: var(--blue);
  background: var(--blue-bg);
}

.tab-btn.active {
  color: #fff;
  background: var(--grad-blue);
  box-shadow: var(--shadow-blue), var(--shadow-pop);
}

.settings-card,
.course-card,
.checkin-card {
  margin-top: 0;
  padding: 24px;
}

.settings-card h2,
.course-card h2,
.checkin-card h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  margin-bottom: 20px;
  color: var(--ink);
}

.settings-card h2 svg,
.course-card h2 svg,
.checkin-card h2 svg {
  color: var(--purple);
}

.scoring-section {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 2px dashed var(--border);
}

.scoring-section h3 {
  font-size: 17px;
  margin-bottom: 16px;
  color: var(--ink);
}

.tts-section {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 2px dashed var(--border);
}

.tts-section h3 {
  font-size: 17px;
  margin-bottom: 6px;
  color: var(--ink);
}

.tts-hint {
  font-size: 14px;
  color: var(--muted);
  margin-bottom: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-grid label span,
.month-picker span {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.form-grid .full {
  grid-column: 1 / -1;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.save-hint {
  color: var(--green);
  font-size: 14px;
  font-weight: 600;
}

.import-form {
  grid-template-columns: 1fr auto;
  align-items: end;
}

.import-form,
.schedule-form {
  margin-bottom: 20px;
}

.schedule-form {
  grid-template-columns: 1fr 1fr 1fr auto;
  align-items: end;
}

.import-result,
.schedule-result {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 2px dashed var(--border);
}

.result-section h3 {
  font-size: 15px;
  color: var(--muted);
  margin: 0 0 12px;
}

.result-section + .result-section {
  margin-top: 18px;
}

.import-result ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.import-result li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  font-size: 14px;
}

.import-result .title {
  color: var(--ink);
  font-weight: 600;
}

.import-result .file {
  font-family: var(--font-mono);
  color: var(--muted);
  min-width: 140px;
}

.import-result .reason {
  color: var(--red);
}

.import-result .tag,
.schedule-result .tag {
  font-size: 12px;
  font-weight: 600;
}

.import-result .tag.created {
  background: var(--green-bg);
  color: var(--green);
}

.import-result .tag.updated {
  background: var(--orange-bg);
  color: var(--orange-ink);
}

.schedule-result .schedule-day {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  font-size: 14px;
}

.schedule-result .day-date {
  font-family: var(--font-mono);
  color: var(--blue);
  font-weight: 600;
}

.course-card .empty-state {
  padding: 48px 24px;
}

.course-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: start;
}

.course-list-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 640px;
  overflow-y: auto;
  padding: 4px 10px 4px 4px;
  /* 滚到底不再带动整页一起滚 */
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

/* 滚动条:细、圆角胶囊、配色贴主题(Chrome/Edge/Safari) */
.course-list-panel::-webkit-scrollbar {
  width: 10px;
}

.course-list-panel::-webkit-scrollbar-track {
  background: transparent;
}

.course-list-panel::-webkit-scrollbar-thumb {
  background-color: var(--border);
  background-clip: content-box;
  border: 3px solid transparent;
  border-radius: var(--radius-pill);
}

.course-list-panel::-webkit-scrollbar-thumb:hover {
  background-color: var(--blue);
}

.course-item {
  background: var(--bg);
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.course-item.active {
  border-color: var(--blue);
  box-shadow: var(--shadow-sm);
}

.course-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
  cursor: pointer;
  transition: background var(--transition);
}

.course-header:hover {
  background: var(--blue-bg);
}

.course-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.course-name {
  font-weight: 700;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.course-meta,
.course-dates {
  font-size: 13px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.course-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.material-panel {
  min-height: 320px;
  background: linear-gradient(180deg, var(--bg), var(--card));
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
}

.material-table-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.material-table-head h3 {
  font-size: 17px;
  color: var(--ink);
}

.material-panel .empty-state {
  padding: 72px 24px;
  background: transparent;
}

.material-panel table .material-row {
  display: table-row;
}

.material-panel table .material-row td {
  vertical-align: middle;
}

.material-panel .material-title {
  font-weight: 600;
  color: var(--ink);
}

.material-panel .material-dates {
  font-size: 13px;
  color: var(--secondary);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
}

.page-info {
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  font-family: var(--font-mono);
}

.calendar-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.month-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.month-picker {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.month-picker input {
  width: auto;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
}

.calendar-weekday {
  text-align: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
  padding: 8px 4px;
}

.calendar-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 72px;
  padding: 8px;
  background: var(--bg);
  border: 2px solid transparent;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: background var(--transition), box-shadow var(--transition), transform var(--transition), border-color var(--transition);
}

.calendar-cell:hover:not(.empty) {
  background: var(--blue-bg);
  transform: translateY(-2px);
  box-shadow: var(--shadow-pop);
}

.calendar-cell.empty {
  background: transparent;
  cursor: default;
}

.calendar-cell.active {
  background: var(--blue-bg);
  box-shadow: inset 0 0 0 2px var(--blue);
}

.calendar-cell.has-materials {
  background: linear-gradient(180deg, var(--green-bg), #cdf4de);
  border-color: var(--green);
}

.calendar-cell.has-materials .cell-day {
  color: var(--green);
}

.calendar-cell.has-materials.active {
  background: var(--blue-bg);
  border-color: var(--blue);
}

.calendar-cell.has-materials.active .cell-day {
  color: var(--blue);
}

.cell-day {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}

.cell-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--green);
}

.cell-indicator {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
}

.day-detail {
  margin-top: 20px;
  padding: 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}

.day-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.day-detail-head h3 {
  font-size: 17px;
  color: var(--ink);
}

.day-actions {
  display: flex;
  gap: 8px;
}

.day-materials {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-height: 32px;
}

.material-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.material-chip .chip-course {
  font-size: 11px;
  color: var(--muted);
  font-weight: 500;
}

.material-chip .remove-material {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 14px;
  line-height: 1;
  color: var(--muted);
  background: var(--bg);
  cursor: pointer;
}

.material-chip .remove-material:hover {
  background: var(--red-bg);
  color: var(--red);
}

.day-empty {
  font-size: 13px;
  color: var(--secondary);
}

.material-picker {
  margin-top: 14px;
  padding: 14px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.picker-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 10px;
}

.picker-course-select {
  margin-bottom: 12px;
}

.picker-course-select select {
  width: 100%;
}

.picker-course-materials {
  margin-bottom: 12px;
}

.picker-course-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.picker-course-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}

.picker-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 320px;
  overflow-y: auto;
  margin-bottom: 12px;
}

.picker-group-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
  padding: 6px 0;
}

.picker-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: background var(--transition);
}

.picker-option:hover {
  background: var(--bg);
}

.picker-option.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.picker-option input {
  min-height: auto;
  padding: 0;
  margin: 0;
}

.option-title {
  font-weight: 600;
  color: var(--ink);
}

.option-read {
  margin-left: auto;
  font-size: 12px;
  color: var(--secondary);
}

.picker-actions {
  display: flex;
  gap: 10px;
}

.schedule-list {
  display: none;
}

@media (max-width: 768px) {
  .form-grid,
  .schedule-form {
    grid-template-columns: 1fr;
  }

  .admin-tabs {
    flex-wrap: wrap;
    border-radius: var(--radius-card);
  }

  .tab-btn {
    flex: 1 1 auto;
    padding: 10px 12px;
    font-size: 14px;
  }

  .course-layout {
    grid-template-columns: 1fr;
  }

  .course-list-panel {
    max-height: none;
  }

  .course-header {
    flex-wrap: wrap;
  }

  .course-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .material-table-head {
    flex-wrap: wrap;
  }

  .calendar-cell {
    min-height: 52px;
    padding: 4px;
  }

  .cell-count {
    display: none;
  }

  .day-detail-head {
    flex-wrap: wrap;
  }

  .day-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
