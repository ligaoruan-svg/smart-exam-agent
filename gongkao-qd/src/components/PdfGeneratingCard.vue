<script setup>
/**
 * PdfGeneratingCard.vue - PDF 生成轮询子组件
 *
 * 用法：
 *   <PdfGeneratingCard :card="card" />
 *
 * 收到 card 后立即开始每 2 秒轮询 /api/pdf/{task_id}/status，
 * 直到 status 变成 completed/failed 或超时。
 *
 * 状态机:
 *   pending  -> "⏳ 排队中..."
 *   running  -> "🔄 生成中... 约 30 秒"
 *   completed-> "✅ 已完成 [下载 PDF]"
 *   failed   -> "❌ 生成失败：xxx"
 */
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { pdfApi, getToken } from '@/api'

const props = defineProps({
  card: { type: Object, required: true },
})

const POLL_INTERVAL = 2000     // 2 秒
const POLL_MAX_MS   = 5 * 60 * 1000   // 5 分钟兜底

// 默认值用 card.data.status，不存在就当 pending
const status      = ref(props.card?.data?.status || 'pending')
const fileName    = ref(props.card?.data?.file_name || null)
const fileSizeKB  = ref(null)
const errorMsg    = ref(null)
const elapsed     = ref(0)
const downloadUrl = ref(null)

let timer = null
let startedAt = Date.now()

const taskId = computed(() => props.card?.task_id || props.card?.data?.task_id)
const count  = computed(() => props.card?.data?.count || 0)
const qtype  = computed(() => props.card?.data?.question_type || '混合')
const province = computed(() => props.card?.data?.province || '全部')
const title  = computed(() => props.card?.data?.title || '')
const estimatedSec = computed(() => props.card?.data?.estimated_seconds || 60)

const statusText = computed(() => {
  switch (status.value) {
    case 'pending':   return '⏳ 排队中…'
    case 'running':   return `🔄 生成中… 约 ${estimatedSec.value} 秒`
    case 'completed': return '✅ 已完成'
    case 'failed':    return '❌ 生成失败'
    default:          return status.value
  }
})

const statusClass = computed(() => [
  `pdf-status-${status.value}`,
  downloaded.value ? 'pdf-downloaded' : '',
])

async function poll() {
  const id = taskId.value
  if (!id) return
  try {
    const r = await pdfApi.status(id)
    status.value = r.status || status.value
    elapsed.value = r.elapsed_sec || 0
    if (r.file_name) fileName.value = r.file_name
    if (r.file_size) fileSizeKB.value = Math.round(r.file_size / 1024)
    if (r.error_msg) errorMsg.value = r.error_msg
    if (r.download_url) {
      // 后端返回的是相对路径，前端补上 host
      const base = (import.meta.env.VITE_API_BASE || 'http://localhost:8900')
      downloadUrl.value = r.download_url.startsWith('http')
        ? r.download_url
        : `${base}${r.download_url}`
    }
  } catch (e) {
    // 偶发错误不致命，继续轮询；连续失败 5 次后停
    console.warn('[PdfGeneratingCard] poll error', e)
  }
}

function startPolling() {
  poll()  // 立刻一次
  timer = setInterval(() => {
    if (status.value === 'completed' || status.value === 'failed') {
      stopPolling()
      return
    }
    if (Date.now() - startedAt > POLL_MAX_MS) {
      stopPolling()
      if (status.value !== 'completed') {
        errorMsg.value = '生成超时，请稍后到下载中心查看'
        status.value = 'failed'
      }
      return
    }
    poll()
  }, POLL_INTERVAL)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

// 下载状态用 sessionStorage 持久化（按 task_id 索引），刷新/切换会话也保留
const STORAGE_KEY = 'gk_card_state_v1'

function loadStates() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function isPdfDownloaded(tid) {
  if (!tid) return false
  const all = loadStates()
  return all[`pdf:${tid}`] === 'downloaded'
}

function markPdfDownloaded(tid) {
  if (!tid) return
  try {
    const all = loadStates()
    all[`pdf:${tid}`] = 'downloaded'
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  } catch {}
}

// 当前是否已下载（响应式）
const downloaded = ref(isPdfDownloaded(taskId.value))

async function downloadPdf() {
  if (!downloadUrl.value) return
  try {
    const resp = await fetch(downloadUrl.value, {
      headers: { 'Authorization': `Bearer ${getToken()}` },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName.value || 'quiz.pdf'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    // 标记并持久化
    downloaded.value = true
    markPdfDownloaded(taskId.value)
  } catch (e) {
    alert(`下载失败：${e.message}`)
  }
}

onMounted(() => {
  // 已经是终态就不轮询了（刷新页面回来时会走这里）
  if (status.value === 'completed' || status.value === 'failed') {
    // 但仍可能需要补一次去拿 download_url
    if (status.value === 'completed' && !downloadUrl.value && taskId.value) {
      poll()
    }
    return
  }
  startPolling()
})

onBeforeUnmount(() => stopPolling())
</script>

<template>
  <div class="pdf-card" :class="statusClass">
    <div class="pdf-head">
      <span class="pdf-icon">📄</span>
      <span class="pdf-title">
        {{ title || `${province} · ${qtype} · ${count} 题 PDF` }}
      </span>
    </div>
    <div class="pdf-meta">
      <span>{{ count }} 道</span>
      <span class="dot">·</span>
      <span>{{ qtype }}</span>
      <span class="dot">·</span>
      <span>{{ province }}</span>
      <span v-if="elapsed > 0" class="elapsed">已用 {{ elapsed }} 秒</span>
    </div>
    <div class="pdf-status">{{ statusText }}</div>

    <!-- 进度条（pending/running 时） -->
    <div v-if="status === 'pending' || status === 'running'" class="pdf-progress">
      <div class="pdf-bar"></div>
    </div>

    <!-- 完成 -->
    <div v-if="status === 'completed'" class="pdf-actions">
      <button
        class="pdf-btn primary"
        :class="{ done: downloaded }"
        :disabled="downloaded"
        @click="downloadPdf"
      >
        {{ downloaded ? '✓ 已下载' : '↓ 下载 PDF' }}
      </button>
      <span v-if="fileSizeKB" class="pdf-size">{{ fileSizeKB }} KB</span>
    </div>

    <!-- 失败 -->
    <div v-if="status === 'failed' && errorMsg" class="pdf-error">
      {{ errorMsg }}
    </div>
  </div>
</template>

<style scoped>
.pdf-card {
  background: #fff;
  border: 1px solid var(--gk-gray-200, #e5e7eb);
  border-left: 3px solid var(--gk-blue-500, #3b82f6);
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 6px;
  font-size: 13px;
  max-width: 360px;
}
.pdf-status-completed { border-left-color: var(--gk-green-500, #10b981); }
.pdf-status-failed    { border-left-color: var(--gk-red-500, #ef4444); }
.pdf-card.pdf-downloaded {
  opacity: .65;
  filter: grayscale(.5);
  border-left-color: var(--gk-gray-400, #9ca3af);
}

.pdf-head { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.pdf-icon { font-size: 16px; }
.pdf-title { color: var(--gk-gray-900, #111827); }

.pdf-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--gk-gray-500, #6b7280);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.pdf-meta .dot { opacity: 0.5; }
.pdf-meta .elapsed { margin-left: auto; font-size: 11px; }

.pdf-status {
  margin-top: 8px;
  font-size: 13px;
  color: var(--gk-gray-700, #374151);
}

.pdf-progress {
  margin-top: 8px;
  height: 4px;
  background: var(--gk-gray-100, #f3f4f6);
  border-radius: 2px;
  overflow: hidden;
}
.pdf-bar {
  width: 30%;
  height: 100%;
  background: var(--gk-blue-500, #3b82f6);
  border-radius: 2px;
  animation: pdf-slide 1.4s linear infinite;
}
@keyframes pdf-slide {
  0%   { margin-left: -30%; }
  100% { margin-left: 100%; }
}

.pdf-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.pdf-btn {
  border: 0;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.pdf-btn.primary {
  background: var(--gk-green-500, #10b981);
  color: #fff;
}
.pdf-btn.primary:hover { opacity: 0.92; }
.pdf-btn.primary.done {
  background: var(--gk-gray-300, #d1d5db);
  color: var(--gk-gray-500, #6b7280);
  cursor: not-allowed;
}
.pdf-btn.primary.done:hover { opacity: 1; }
.pdf-btn:disabled { pointer-events: none; }
.pdf-size {
  font-size: 11px;
  color: var(--gk-gray-500, #6b7280);
}
.pdf-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--gk-red-600, #dc2626);
  background: var(--gk-red-50, #fef2f2);
  padding: 8px 10px;
  border-radius: 6px;
  word-break: break-all;
}
</style>
