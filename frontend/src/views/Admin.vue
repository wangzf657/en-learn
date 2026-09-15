<script setup>
import { ref, watch, onMounted } from 'vue'
import { adminApi, scoringApi } from '../api.js'

const videos = ref([])
const loading = ref(false)
const error = ref('')

const scoringLoading = ref(false)
const scoringError = ref('')
const scoringSaved = ref(false)
const scoringProviders = ref([])
const scoringProvider = ref('mock')
const scoringOptions = ref({})

const now = new Date()
const importPath = ref('')
const importMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const importLoading = ref(false)
const importError = ref('')
const importResult = ref(null)

onMounted(async () => {
  await load()
  await loadScoring()
})

watch(scoringProvider, (next) => {
  if (next === 'mock') {
    scoringOptions.value = {}
  }
})

async function loadScoring() {
  scoringLoading.value = true
  scoringError.value = ''
  try {
    const data = await scoringApi.getScoring()
    scoringProviders.value = data.providers || []
    scoringProvider.value = data.provider || 'mock'
    scoringOptions.value = data.options || {}
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

async function submitImport() {
  importLoading.value = true
  importError.value = ''
  importResult.value = null
  try {
    importResult.value = await adminApi.importVideos(importPath.value, importMonth.value)
  } catch (e) {
    importError.value = e.detail || e.message
  } finally {
    importLoading.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await adminApi.list()
    videos.value = res.videos || []
  } catch (e) {
    error.value = e.detail || e.message
  } finally {
    loading.value = false
  }
}

async function remove(item) {
  if (!confirm(`确定删除 ${item.date} 的《${item.title}》吗？`)) return
  try {
    await adminApi.remove(item.id)
    await load()
  } catch (e) {
    alert(e.detail || e.message)
  }
}
</script>

<template>
  <div class="page admin-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">后台管理</h1>
        <p class="page-subtitle">管理视频、导入课程与配置评分服务</p>
      </div>
      <div class="actions">
        <router-link to="/" class="btn btn-secondary">回日历</router-link>
      </div>
    </header>

    <div v-if="error" class="error-detail">{{ error }}</div>

    <div v-if="loading" class="card empty-state">
      <p>正在加载视频列表…</p>
    </div>

    <div v-else-if="videos.length === 0" class="card empty-state">
      <h3>暂无视频</h3>
      <p>在下方按月快捷导入第一条学习内容。</p>
    </div>

    <div v-else class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>标题</th>
            <th>句数</th>
            <th>打卡</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in videos" :key="v.id">
            <td>{{ v.date }}</td>
            <td>{{ v.title }}</td>
            <td>{{ v.sentenceCount }}</td>
            <td>
              <span v-if="v.checked" class="tag checked">已打卡</span>
              <span v-else class="tag">未打卡</span>
            </td>
            <td>
              <div class="row-actions">
                <button class="btn btn-ghost btn-sm" @click="remove(v)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card import-card">
      <h2>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19.35 10.04A7.49 7.49 0 0 0 12 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/>
        </svg>
        按月快捷导入
      </h2>
      <div class="form-grid">
        <label class="full">
          <span>文件夹路径</span>
          <input type="text" v-model="importPath" placeholder="D:\videos\2026-09" />
        </label>
        <label>
          <span>月份</span>
          <input type="month" v-model="importMonth" />
        </label>
        <div class="full form-actions">
          <button class="btn btn-primary" :disabled="importLoading" @click="submitImport">
            <span v-if="importLoading">导入中…</span>
            <span v-else>导入</span>
          </button>
        </div>
        <div v-if="importError" class="full error-detail">{{ importError }}</div>
      </div>

      <div v-if="importResult" class="import-result">
        <div v-if="importResult.imported.length" class="result-section">
          <h3>导入成功 {{ importResult.imported.length }} 条</h3>
          <ul>
            <li v-for="item in importResult.imported" :key="item.id">
              <span class="date">{{ item.date }}</span>
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
        <div v-if="!importResult.imported.length && !importResult.skipped.length" class="result-empty">
          没有匹配的文件
        </div>
      </div>
    </div>

    <div class="card scoring-card">
      <h2>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
        发音评分服务
      </h2>
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
            <input type="text" v-model="scoringOptions.mode" placeholder="默认 E" />
          </label>
          <label>
            <span>服务地址</span>
            <input type="text" v-model="scoringOptions.base_url" placeholder="默认官方地址" />
          </label>
        </template>
        <div class="full form-actions">
          <button class="btn btn-primary" @click="saveScoring">保存</button>
          <span v-if="scoringSaved" class="save-hint">已保存</span>
        </div>
        <div v-if="scoringError" class="full error-detail">{{ scoringError }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page .page-header {
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
}

.actions {
  display: flex;
  gap: 10px;
}

.import-card,
.scoring-card {
  margin-top: 28px;
  padding: 24px;
}

.import-card h2,
.scoring-card h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  margin-bottom: 20px;
  color: var(--ink);
}

.import-card h2 svg,
.scoring-card h2 svg {
  color: var(--blue);
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

.form-grid label span {
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

.import-result {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
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
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  font-size: 14px;
}

.import-result .date {
  font-family: var(--font-mono);
  color: var(--blue);
  min-width: 90px;
  font-weight: 600;
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

.import-result .tag {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
}

.import-result .tag.created {
  background: var(--green-bg);
  color: var(--green);
}

.import-result .tag.updated {
  background: var(--orange-bg);
  color: #c46a00;
}

.result-empty {
  color: var(--muted);
  font-size: 14px;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
