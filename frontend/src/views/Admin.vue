<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '../api.js'

const videos = ref([])
const loading = ref(false)
const error = ref('')
const formError = ref('')

const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  date: '',
  title: '',
  videoPath: '',
  subtitleJson: '',
})

const pathResult = ref(null)
const fileInput = ref(null)

onMounted(load)

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

function resetForm() {
  editingId.value = null
  form.value = { date: '', title: '', videoPath: '', subtitleJson: '' }
  pathResult.value = null
  formError.value = ''
}

function openCreate() {
  resetForm()
  showForm.value = true
}

function edit(item) {
  editingId.value = item.id
  form.value = {
    date: item.date,
    title: item.title,
    videoPath: item.videoPath,
    subtitleJson: typeof item.subtitleJson === 'string'
      ? item.subtitleJson
      : JSON.stringify(item.subtitleJson, null, 2),
  }
  pathResult.value = null
  formError.value = ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  resetForm()
}

async function submit() {
  formError.value = ''
  const payload = {
    date: form.value.date,
    title: form.value.title,
    videoPath: form.value.videoPath,
    subtitleJson: form.value.subtitleJson,
  }
  try {
    if (editingId.value) {
      await adminApi.update(editingId.value, payload)
    } else {
      await adminApi.create(payload)
    }
    await load()
    closeForm()
  } catch (e) {
    formError.value = e.detail || e.message
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

async function validatePath() {
  pathResult.value = null
  if (!form.value.videoPath) return
  try {
    pathResult.value = await adminApi.validatePath(form.value.videoPath)
  } catch (e) {
    pathResult.value = { exists: false, error: e.detail || e.message }
  }
}

function triggerFile() {
  fileInput.value?.click()
}

function importFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    form.value.subtitleJson = String(reader.result)
  }
  reader.readAsText(file)
  e.target.value = ''
}
</script>

<template>
  <div class="page admin-page">
    <header class="page-header">
      <h1 class="page-title">后台管理</h1>
      <div class="actions">
        <button class="btn btn-primary" @click="openCreate">新增视频</button>
        <router-link to="/" class="btn btn-secondary">回日历</router-link>
      </div>
    </header>

    <div v-if="error" class="error-detail">{{ error }}</div>

    <div v-if="showForm" class="card form-card">
      <h2>{{ editingId ? '编辑视频' : '新增视频' }}</h2>
      <div class="form-grid">
        <label>
          <span>日期</span>
          <input type="date" v-model="form.date" />
        </label>
        <label>
          <span>标题</span>
          <input type="text" v-model="form.title" placeholder="例如：老友记 S01E01" />
        </label>
        <label class="full">
          <span>本地视频路径</span>
          <div class="path-row">
            <input type="text" v-model="form.videoPath" placeholder="D:\\videos\\lesson.mp4" />
            <button type="button" class="btn btn-secondary" @click="validatePath">验证路径</button>
          </div>
          <div v-if="pathResult" class="path-result">
            <span v-if="pathResult.exists">✓ 文件存在，大小 {{ Math.round(pathResult.size / 1024 / 1024 * 100) / 100 }} MB</span>
            <span v-else class="path-missing">✗ 文件不存在{{ pathResult.error ? '：' + pathResult.error : '' }}</span>
          </div>
        </label>
        <label class="full">
          <span>字幕 JSON</span>
          <div class="textarea-actions">
            <button type="button" class="btn btn-secondary btn-sm" @click="triggerFile">导入 JSON 文件</button>
            <input ref="fileInput" type="file" accept=".json,application/json" @change="importFile" style="display: none" />
          </div>
          <textarea v-model="form.subtitleJson" placeholder='{"sentences": [{"start": 1.2, "end": 4.5, "en": "...", "zh": "..."}]}'></textarea>
        </label>
      </div>
      <div v-if="formError" class="error-detail">{{ formError }}</div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="submit">保存</button>
        <button class="btn btn-ghost" @click="closeForm">取消</button>
      </div>
    </div>

    <div v-if="loading" class="empty-state">加载中…</div>

    <div v-else-if="videos.length === 0" class="card empty-state">
      <h3>暂无视频</h3>
      <p>点击“新增视频”添加第一条学习内容。</p>
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
                <button class="btn btn-secondary btn-sm" @click="edit(v)">编辑</button>
                <button class="btn btn-ghost btn-sm" @click="remove(v)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.admin-page .page-header {
  flex-wrap: wrap;
  gap: 12px;
}

.actions {
  display: flex;
  gap: 10px;
}

.form-card {
  padding: 24px;
  margin-bottom: 28px;
}

.form-card h2 {
  font-size: 22px;
  margin-bottom: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-grid label span {
  font-size: 14px;
  color: var(--ink-light);
}

.form-grid .full {
  grid-column: 1 / -1;
}

.path-row {
  display: flex;
  gap: 10px;
}

.path-row input {
  flex: 1;
}

.path-result {
  margin-top: 6px;
  font-size: 13px;
  color: var(--sage);
}

.path-missing {
  color: var(--accent);
}

.textarea-actions {
  display: flex;
  justify-content: flex-end;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 18px;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 15px;
}

th, td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

th {
  background: var(--paper-2);
  font-weight: 700;
  color: var(--ink-light);
}

tbody tr:hover {
  background: #fffaf5;
}

.tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: var(--paper-2);
  color: var(--ink-light);
}

.tag.checked {
  background: var(--sage-bg);
  color: var(--sage);
}

.row-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .path-row {
    flex-direction: column;
  }
}
</style>
