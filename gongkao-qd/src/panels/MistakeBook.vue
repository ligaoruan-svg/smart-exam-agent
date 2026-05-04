<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import Card from '../components/Card.vue'
import Chip from '../components/Chip.vue'
import Button from '../components/Button.vue'
import { getToken } from '@/api'

/* ============================================================
 * 内置 mistakeApi
 * ============================================================ */
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8900'

async function _request(path, opts = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(opts.headers || {}),
  }
  const resp = await fetch(API_BASE + path, { ...opts, headers })
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    try { const err = await resp.json(); msg = err.detail || err.message || msg } catch {}
    const e = new Error(msg); e.status = resp.status; throw e
  }
  return resp.json()
}

const mistakeApi = {
  list: ({ status='all', question_type=null, province=null, year=null, mode='review', page=1, page_size=20 } = {}) => {
    const qs = new URLSearchParams()
    if (status && status !== 'all') qs.set('status', status)
    if (question_type) qs.set('question_type', question_type)
    if (province) qs.set('province', province)
    if (year) qs.set('year', year)
    qs.set('mode', mode)
    qs.set('page', page)
    qs.set('page_size', page_size)
    return _request(`/api/mistake/list?${qs.toString()}`)
  },
  overview: ({ status='all', question_type=null, province=null, year=null, refresh=false, only_summary=false, skip_ai=false } = {}) => {
    const qs = new URLSearchParams()
    if (status && status !== 'all') qs.set('status', status)
    if (question_type) qs.set('question_type', question_type)
    if (province) qs.set('province', province)
    if (year) qs.set('year', year)
    if (refresh) qs.set('refresh', 'true')
    if (only_summary) qs.set('only_summary', 'true')
    if (skip_ai) qs.set('skip_ai', 'true')
    return _request(`/api/mistake/overview?${qs.toString()}`)
  },
  master:   (id) => _request(`/api/mistake/${id}/master`,   { method: 'POST' }),
  unmaster: (id) => _request(`/api/mistake/${id}/unmaster`, { method: 'POST' }),
  star:     (id) => _request(`/api/mistake/${id}/star`,     { method: 'POST' }),
  remove:   (id) => _request(`/api/mistake/${id}`, { method: 'DELETE' }),
  aiExplain: (id, refresh=false) =>
    _request(`/api/mistake/${id}/ai-explain${refresh ? '?refresh=true' : ''}`, { method: 'POST' }),
}

/* ============================================================
 * Toast 通知组件（替代 alert）
 * ============================================================ */
const toast = ref({ show: false, message: '', type: 'info' })
let toastTimer = null

function showToast(message, type = 'info') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { show: true, message, type }
  toastTimer = setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

/* ============================================================
 * 视图状态
 * ============================================================ */
const view = ref('review')

/* ============================================================
 * 共用筛选
 * ============================================================ */
const filterStatus = ref('unmastered')
const filterType = ref(null)
const filterProvince = ref(null)
const filterYear = ref(null)

const TYPE_TONE = {
  '判断推理': 'violet',
  '言语理解': 'indigo',
  '数量关系': 'green',
  '资料分析': 'amber',
  '常识判断': 'red',
}
const toneFg = {
  violet: '#6d28d9', indigo: '#4338ca', green: '#15803d',
  amber:  '#b45309', red:    '#dc2626', gray: '#4b5563',
}
const toneBg = {
  violet: '#f5f3ff', indigo: '#eef2ff', green: '#f0fdf4',
  amber:  '#fffbeb', red:    '#fef2f2', gray: '#f3f4f6',
}

/* ============================================================
 * 速复习视图：当前题 + 队列（支持分页加载）
 * ============================================================ */
const queue = ref([])
const queueLoading = ref(false)
const queueError = ref('')
const cursor = ref(0)
const contentScrollRef = ref(null)   // 内容滚动区的 ref，切题时重置滚到顶

// 切题时把内容滚动区重置到顶部
watch(cursor, () => {
  nextTick(() => {
    if (contentScrollRef.value) {
      contentScrollRef.value.scrollTop = 0
    }
  })
})
const aiPanel = ref({})

// 分页相关
const currentPage = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)
const isLoadingMore = ref(false)
const hasMore = computed(() => currentPage.value < totalPages.value)

const currentItem = computed(() => queue.value[cursor.value] || null)

// 组件卸载标志
let isUnmounted = false

async function loadQueue(reset = true, loadMore = false) {
  if (queueLoading.value || isLoadingMore.value) return

  if (loadMore) {
    if (!hasMore.value) return
    isLoadingMore.value = true
  } else {
    queueLoading.value = true
    if (reset) {
      currentPage.value = 1
      queue.value = []
      cursor.value = 0
    }
  }
  queueError.value = ''

  try {
    const r = await mistakeApi.list({
      status: filterStatus.value,
      question_type: filterType.value,
      province: filterProvince.value,
      year: filterYear.value,
      mode: 'review',
      page: loadMore ? currentPage.value + 1 : currentPage.value,
      page_size: 20,
    })

    if (loadMore) {
      queue.value.push(...(r.items || []))
      currentPage.value++
    } else {
      queue.value = r.items || []
      totalPages.value = r.total_pages || 1
      totalItems.value = r.total || 0
      cursor.value = 0
      aiPanel.value = {}
    }
  } catch (e) {
    queueError.value = e.message || '加载失败'
  } finally {
    if (loadMore) {
      isLoadingMore.value = false
    } else {
      queueLoading.value = false
    }
  }
}

// 加载更多（滚动触发）
async function loadMore() {
  if (hasMore.value && !isLoadingMore.value && !queueLoading.value) {
    await loadQueue(false, true)
  }
}

// 滚动监听
function handleScroll(e) {
  const target = e.target
  if (target.scrollHeight - target.scrollTop - target.clientHeight < 200) {
    loadMore()
  }
}

function nextCard() {
  if (cursor.value < queue.value.length - 1) {
    cursor.value++
  } else {
    // 尝试加载更多
    if (hasMore.value) {
      loadMore().then(() => {
        if (cursor.value < queue.value.length - 1) {
          cursor.value++
        } else {
          cursor.value = queue.value.length
        }
      })
    } else {
      cursor.value = queue.value.length
    }
  }
}

function prevCard() {
  if (cursor.value > 0) cursor.value--
}

// 安全的队列项移除（修复边界逻辑）
function removeFromQueue(itemId) {
  const index = queue.value.findIndex(x => x.id === itemId)
  if (index === -1) return false

  queue.value = queue.value.filter(x => x.id !== itemId)

  // 调整 cursor
  if (cursor.value > index) {
    cursor.value--
  } else if (cursor.value === index) {
    if (cursor.value >= queue.value.length) {
      cursor.value = Math.max(0, queue.value.length - 1)
    }
  }
  return true
}

async function markAsMastered(it) {
  try {
    await mistakeApi.master(it.id)
    removeFromQueue(it.id)
    showToast('✅ 已标记为掌握', 'success')
  } catch (e) {
    showToast('操作失败：' + e.message, 'error')
  }
}

async function deleteCurrentCard(it) {
  if (!confirm('确定删除这道错题？')) return
  try {
    await mistakeApi.remove(it.id)
    removeFromQueue(it.id)
    showToast('🗑️ 已删除', 'success')
  } catch (e) {
    showToast('删除失败：' + e.message, 'error')
  }
}

async function toggleStar(it) {
  try {
    const r = await mistakeApi.star(it.id)
    it.is_starred = r.is_starred
    showToast(r.is_starred ? '⭐ 已收藏' : '☆ 已取消收藏', 'info')
  } catch (e) {
    showToast('操作失败：' + e.message, 'error')
  }
}

async function fetchAIExplain(it, refresh = false) {
  const k = it.id
  if (!aiPanel.value[k]) aiPanel.value[k] = {}
  const p = aiPanel.value[k]
  if (p.expanded && !refresh && p.text) {
    p.expanded = false
    return
  }
  p.loading = true
  p.expanded = true
  p.error = ''
  try {
    const r = await mistakeApi.aiExplain(it.id, refresh)
    p.text = r.analysis || ''
    p.fromCache = !!r.from_cache
  } catch (e) {
    p.error = e.message || 'AI 解析失败'
    showToast('AI 解析失败：' + p.error, 'error')
  } finally {
    p.loading = false
  }
}

/* ============================================================
 * 全景图视图（修复数据竞态 + 遮罩层方案）
 * ============================================================ */
const overviewData = ref(null)
const chartLoading = ref(false)
const summaryLoading = ref(false)
const overviewError = ref('')
let currentOverviewRequestId = 0

async function loadOverview(refresh = false) {
  const requestId = ++currentOverviewRequestId
  overviewError.value = ''

  if (!overviewData.value) {
    chartLoading.value = true
  }

  try {
    const data = await mistakeApi.overview({
      status: filterStatus.value,
      question_type: filterType.value,
      province: filterProvince.value,
      year: filterYear.value,
      skip_ai: true,
    })

    if (requestId !== currentOverviewRequestId) return

    // 保留旧的 AI 总结内容，避免清空导致高度塌陷
    const oldSummary = overviewData.value?.ai_summary || { text: '', from_cache: false }
    overviewData.value = {
      ...data,
      ai_summary: { ...oldSummary, _pending: true },
    }
    chartLoading.value = false

    summaryLoading.value = true
    try {
      const r = await mistakeApi.overview({
        status: filterStatus.value,
        question_type: filterType.value,
        province: filterProvince.value,
        year: filterYear.value,
        refresh,
        only_summary: true,
      })

      if (requestId !== currentOverviewRequestId) return

      if (overviewData.value) {
        overviewData.value = {
          ...overviewData.value,
          ai_summary: r.ai_summary || { text: '', error: 'AI 暂无返回' },
        }
      }
    } catch (e) {
      if (requestId !== currentOverviewRequestId) return
      if (overviewData.value) {
        overviewData.value = {
          ...overviewData.value,
          ai_summary: { text: '', error: e.message || 'AI 总结失败' },
        }
      }
    } finally {
      summaryLoading.value = false
    }
  } catch (e) {
    if (requestId !== currentOverviewRequestId) return
    overviewError.value = e.message || '加载失败'
    chartLoading.value = false
    summaryLoading.value = false
  }
}

async function refreshSummaryOnly() {
  if (summaryLoading.value) return

  summaryLoading.value = true
  const requestId = ++currentOverviewRequestId

  try {
    const r = await mistakeApi.overview({
      status: filterStatus.value,
      question_type: filterType.value,
      province: filterProvince.value,
      year: filterYear.value,
      refresh: true,
      only_summary: true,
    })

    if (requestId !== currentOverviewRequestId) return

    if (overviewData.value && r.ai_summary) {
      overviewData.value = {
        ...overviewData.value,
        ai_summary: r.ai_summary,
      }
    }
    showToast('✨ AI 总结已更新', 'success')
  } catch (e) {
    if (requestId !== currentOverviewRequestId) return
    if (overviewData.value) {
      overviewData.value = {
        ...overviewData.value,
        ai_summary: { text: '', error: e.message || '生成失败' },
      }
    }
    showToast('AI 总结失败：' + e.message, 'error')
  } finally {
    summaryLoading.value = false
  }
}

function clickBarTo(kind, value) {
  if (kind === 'type') {
    filterType.value = filterType.value === value ? null : value
  }
  if (kind === 'province') {
    filterProvince.value = filterProvince.value === value ? null : value
  }
  if (kind === 'year') {
    filterYear.value = filterYear.value === value ? null : value
    loadOverview()
    return
  }
  view.value = 'review'
  loadQueue()
}

async function switchView(v) {
  view.value = v
  if (v === 'overview' && !overviewData.value) {
    await loadOverview()
  }
  if (v === 'review' && queue.value.length === 0) {
    await loadQueue()
  }
}

async function refreshCurrent() {
  if (view.value === 'review') await loadQueue()
  else await loadOverview()
}

let isInitialLoad = true
watch([filterStatus, filterType, filterProvince, filterYear], () => {
  if (isInitialLoad) return
  refreshCurrent()
}, { flush: 'post' })

/* ============================================================
 * 初始化
 * ============================================================ */
onMounted(async () => {
  isInitialLoad = true
  await loadQueue()
  isInitialLoad = false
})

onUnmounted(() => {
  isUnmounted = true
  currentOverviewRequestId++
  if (toastTimer) clearTimeout(toastTimer)
})

/* ============================================================
 * 极简 markdown 渲染
 * ============================================================ */
function renderMarkdown(md) {
  if (!md) return ''
  let s = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/`([^`]+)`/g, '<code style="background:#f3f4f6;padding:1px 5px;border-radius:3px;font-size:0.92em;">$1</code>')
  const lines = s.split('\n')
  const out = []
  let inList = false
  for (const raw of lines) {
    const line = raw.trimEnd()
    if (/^##\s+/.test(line)) {
      if (inList) { out.push('</ul>'); inList = false }
      out.push(`<h4 style="margin:14px 0 6px;font-size:14px;color:#111827;">${line.replace(/^##\s+/, '')}</h4>`)
    } else if (/^#\s+/.test(line)) {
      if (inList) { out.push('</ul>'); inList = false }
      out.push(`<h3 style="margin:16px 0 8px;font-size:15px;">${line.replace(/^#\s+/, '')}</h3>`)
    } else if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) { out.push('<ul style="margin:6px 0 6px 18px;padding:0;">'); inList = true }
      out.push(`<li style="margin:3px 0;">${line.replace(/^\s*[-*]\s+/, '')}</li>`)
    } else if (line.trim() === '') {
      if (inList) { out.push('</ul>'); inList = false }
      out.push('<div style="height:6px;"></div>')
    } else {
      if (inList) { out.push('</ul>'); inList = false }
      out.push(`<p style="margin:4px 0;line-height:1.7;">${line}</p>`)
    }
  }
  if (inList) out.push('</ul>')
  return out.join('')
}

function optionStyle(it, key) {
  const isCorrect = key === it.answer
  const isMine = key === it.my_answer
  let bg = '#fff', bd = '#e5e7eb', col = '#374151'
  if (isCorrect) { bg = '#f0fdf4'; bd = '#86efac'; col = '#15803d' }
  else if (isMine) { bg = '#fef2f2'; bd = '#fca5a5'; col = '#dc2626' }
  return {
    padding: '12px 16px', background: bg, border: `1px solid ${bd}`,
    borderRadius: '8px', color: col, fontSize: '14px',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  }
}

function optionTag(it, key) {
  if (key === it.answer) return { text: '✓ 正解', color: '#16a34a' }
  if (key === it.my_answer) return { text: '我答的', color: '#dc2626' }
  return null
}

function barPct(items, n) {
  if (!items || items.length === 0) return 0
  const max = Math.max(...items.map(x => x.n))
  if (max === 0) return 0
  return Math.max(8, (n / max) * 100)
}
function barWidth(items, n) {
  return barPct(items, n) + '%'
}
function barHeight(items, n) {
  return Math.max(6, barPct(items, n) * 0.6) + '%'
}
</script>

<template>
  <div style="max-width: 980px; margin: 0 auto; padding: 24px;">

    <!-- Toast 通知 -->
    <transition name="toast-fade">
      <div v-if="toast.show" :style="{
        position: 'fixed',
        bottom: '24px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        padding: '10px 20px',
        borderRadius: '8px',
        fontSize: '13px',
        fontWeight: 500,
        color: '#fff',
        background: toast.type === 'error' ? '#dc2626' : (toast.type === 'success' ? '#16a34a' : '#3b82f6'),
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        pointerEvents: 'none',
      }">
        {{ toast.message }}
      </div>
    </transition>

    <!-- 顶部标题和筛选区 -->
    <div style="margin-bottom:18px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;flex-wrap:wrap;">
        <div style="font-size:22px;font-weight:600;color:#111827;">错题本</div>
        <div style="display:flex;gap:4px;background:#f3f4f6;padding:3px;border-radius:8px;">
          <button @click="switchView('review')" :style="{ padding:'6px 14px',border:'none',borderRadius:'6px',background:view==='review'?'#fff':'transparent',fontSize:'13px',fontWeight:view==='review'?600:500,color:view==='review'?'#111827':'#6b7280',cursor:'pointer',boxShadow:view==='review'?'0 1px 2px rgba(0,0,0,0.05)':'none',fontFamily:'inherit' }">📖 速复习</button>
          <button @click="switchView('overview')" :style="{ padding:'6px 14px',border:'none',borderRadius:'6px',background:view==='overview'?'#fff':'transparent',fontSize:'13px',fontWeight:view==='overview'?600:500,color:view==='overview'?'#111827':'#6b7280',cursor:'pointer',boxShadow:view==='overview'?'0 1px 2px rgba(0,0,0,0.05)':'none',fontFamily:'inherit' }">📊 全景图</button>
        </div>
        <div style="flex:1;"></div>
        <div style="display:flex;gap:6px;">
          <Chip :active="filterStatus === 'unmastered'" @click="filterStatus = 'unmastered'">未掌握</Chip>
          <Chip :active="filterStatus === 'all'" @click="filterStatus = 'all'">全部</Chip>
          <Chip :active="filterStatus === 'mastered'" @click="filterStatus = 'mastered'">已掌握</Chip>
        </div>
      </div>
      <div style="font-size:12px;color:#9ca3af;">
        <template v-if="view === 'review'">📖 一题一屏，按优先级排序，滚动到底部自动加载更多</template>
        <template v-else>📊 看全局分布，AI 帮你定位薄弱点</template>
      </div>
      <div v-if="filterType || filterProvince || filterYear" style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;">
        <span v-if="filterType" style="padding:3px 10px;background:#eef2ff;color:#4338ca;border-radius:12px;font-size:12px;">题型：{{ filterType }}<a href="javascript:void(0)" @click="filterType = null" style="margin-left:4px;color:#6b7280;">×</a></span>
        <span v-if="filterProvince" style="padding:3px 10px;background:#eef2ff;color:#4338ca;border-radius:12px;font-size:12px;">省份：{{ filterProvince }}<a href="javascript:void(0)" @click="filterProvince = null" style="margin-left:4px;color:#6b7280;">×</a></span>
        <span v-if="filterYear" style="padding:3px 10px;background:#ede9fe;color:#6d28d9;border-radius:12px;font-size:12px;">年份：{{ filterYear }}<a href="javascript:void(0)" @click="filterYear = null" style="margin-left:4px;color:#6b7280;">×</a></span>
      </div>
    </div>

    <!-- 速复习视图 -->
    <div v-if="view === 'review'" style="min-height: 700px;width:880px;max-width:100%;margin:0 auto;">
      <div v-if="queueLoading" style="padding:60px 0;text-align:center;color:#9ca3af;">⏳ 加载中…</div>
      <div v-else-if="queueError" style="padding:14px;background:#fef2f2;color:#b91c1c;border-radius:8px;font-size:13px;">⚠️ {{ queueError }}</div>
      <div v-else-if="queue.length === 0" style="padding:120px 20px;text-align:center;">
        <div style="font-size:48px;margin-bottom:12px;">🎉</div>
        <div style="font-size:16px;color:#374151;font-weight:600;margin-bottom:6px;">当前条件下没有要复习的错题</div>
        <div style="font-size:13px;color:#9ca3af;">换个筛选条件试试，或者去做点新题再来</div>
      </div>
      <div v-else-if="cursor >= queue.length && !hasMore" style="padding:120px 20px;text-align:center;">
        <div style="font-size:48px;margin-bottom:12px;">✨</div>
        <div style="font-size:16px;color:#374151;font-weight:600;margin-bottom:6px;">这一轮复习完了！</div>
        <div style="font-size:13px;color:#9ca3af;margin-bottom:18px;">共复习 {{ totalItems }} 道错题，辛苦了</div>
        <Button variant="primary" @click="cursor = 0">↻ 再来一轮</Button>
      </div>

      <!-- 速复习：固定 580px 高，宽度由外层 880 容器控制，绝对统一 -->
      <div v-else-if="currentItem" style="background:#fff;border-radius:14px;border:1px solid #e5e7eb;height:580px;width:100%;box-sizing:border-box;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">

        <!-- ① 顶部条：恒定，不滚动 -->
        <div style="padding:16px 22px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;flex-shrink:0;border-bottom:1px solid #f3f4f6;">
          <span style="font-size:18px;font-weight:600;color:#111827;">第 {{ cursor + 1 }} 题</span>
          <span style="font-size:13px;color:#9ca3af;margin-left:-2px;">/ {{ totalItems }}</span>
          <span style="display:inline-block;width:1px;height:14px;background:#e5e7eb;margin:0 4px;"></span>
          <span :style="{ fontSize:'11px',padding:'3px 10px',borderRadius:'12px',background:toneBg[TYPE_TONE[currentItem.question_type]||'gray'],color:toneFg[TYPE_TONE[currentItem.question_type]||'gray'],fontWeight:600 }">{{ currentItem.question_type || '未分类' }}</span>
          <span style="font-size:12px;color:#6b7280;">{{ currentItem.province || '' }}{{ currentItem.year ? ' · ' + currentItem.year : '' }}</span>
          <span style="padding:2px 8px;font-size:11px;border-radius:10px;font-weight:500;" :style="currentItem.wrong_count >= 2 ? 'background:#fef2f2;color:#dc2626;' : 'background:#fef3c7;color:#92400e;'">错过 {{ currentItem.wrong_count || 1 }} 次</span>
          <div style="flex:1;"></div>
          <span @click="toggleStar(currentItem)" :style="{ cursor:'pointer',fontSize:'18px',userSelect:'none',color:currentItem.is_starred?'#f59e0b':'#d1d5db' }">★</span>
          <span @click="deleteCurrentCard(currentItem)" style="cursor:pointer;font-size:14px;color:#9ca3af;user-select:none;" title="删除">🗑️</span>
        </div>

        <!-- ② 进度条：4px 紫色渐变 -->
        <div style="height:4px;background:#f3f4f6;flex-shrink:0;">
          <div :style="{ width: ((cursor+1)/totalItems*100) + '%', height:'100%', background:'linear-gradient(90deg,#7F77DD,#534AB7)', transition:'width .3s' }"></div>
        </div>

        <!-- ③ 中间内容区：flex:1 + 内部滚动 → AI 解析展开不影响外框 -->
        <div ref="contentScrollRef" style="flex:1;overflow-y:auto;padding:20px 22px;">

          <!-- 题干（灰底框，对齐随机练习） -->
          <div style="background:#f9fafb;padding:16px 18px;border-radius:10px;margin-bottom:18px;">
            <div style="font-size:15px;line-height:1.75;color:#111827;white-space:pre-wrap;">{{ currentItem.stem }}</div>
          </div>

          <!-- 选项 -->
          <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:18px;">
            <div v-for="key in ['A','B','C','D']" :key="key" :style="optionStyle(currentItem, key)">
              <span><b style="margin-right:8px;">{{ key }}.</b>{{ currentItem.options[key] }}</span>
              <span v-if="optionTag(currentItem, key)" :style="{ fontSize:'12px',fontWeight:600,color:optionTag(currentItem,key).color }">{{ optionTag(currentItem, key).text }}</span>
            </div>
          </div>

          <!-- 题库解析 -->
          <div v-if="currentItem.analysis" style="margin-bottom:18px;padding:12px 16px;background:#f9fafb;border-left:3px solid #60a5fa;border-radius:0 8px 8px 0;">
            <div style="font-size:12px;color:#6b7280;margin-bottom:6px;font-weight:600;">📖 题库解析</div>
            <div style="font-size:13px;color:#374151;line-height:1.7;white-space:pre-wrap;">{{ currentItem.analysis }}</div>
          </div>

          <!-- AI 解析展开区（在内容滚动区内部，撑了不会拉外框） -->
          <div
            v-if="aiPanel[currentItem.id]?.expanded"
            style="padding:14px 16px;background:#EEEDFE;border:1px solid #CECBF6;border-radius:10px;margin-bottom:8px;"
          >
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
              <span style="font-size:13px;font-weight:600;color:#3C3489;">✨ AI 名师深度解析</span>
              <span v-if="aiPanel[currentItem.id]?.fromCache" style="font-size:10px;padding:1px 6px;background:#fff;color:#6b7280;border-radius:3px;">缓存</span>
              <div style="flex:1;"></div>
              <a v-if="!aiPanel[currentItem.id]?.loading" href="javascript:void(0)" @click="fetchAIExplain(currentItem, true)" style="font-size:11px;color:#2563eb;">↻ 重新生成</a>
            </div>
            <div v-if="aiPanel[currentItem.id]?.loading" style="padding:14px;text-align:center;color:#6b7280;font-size:13px;">🤔 AI 正在思考，预计 5-15 秒…</div>
            <div v-else-if="aiPanel[currentItem.id]?.error" style="padding:10px;color:#dc2626;font-size:13px;">⚠️ {{ aiPanel[currentItem.id].error }}</div>
            <div v-else style="font-size:13px;color:#1f2937;line-height:1.7;" v-html="renderMarkdown(aiPanel[currentItem.id]?.text)"></div>
          </div>

        </div>

        <!-- ④ 底部按钮区：恒定，不滚动 -->
        <div style="padding:14px 22px;background:#fafbfc;border-top:1px solid #f3f4f6;display:flex;gap:10px;align-items:center;flex-shrink:0;flex-wrap:wrap;">
          <Button
            variant="ai"
            :style="{ fontSize:'13px',padding:'8px 14px' }"
            @click="fetchAIExplain(currentItem)"
          >
            <template v-if="aiPanel[currentItem.id]?.loading">⏳ AI 思考中…</template>
            <template v-else-if="aiPanel[currentItem.id]?.expanded">收起 AI 解析</template>
            <template v-else>✨ AI 深度解析</template>
          </Button>
          <div style="flex:1;"></div>
          <Button variant="ghost" :style="{ fontSize:'13px',padding:'8px 14px' }" @click="prevCard" :disabled="cursor === 0">← 上一道</Button>
          <Button variant="primary" :style="{ fontSize:'13px',padding:'8px 16px',background:'#16a34a',borderColor:'#16a34a' }" @click="markAsMastered(currentItem)">✓ 我会了</Button>
          <Button variant="ghost" :style="{ fontSize:'13px',padding:'8px 14px' }" @click="nextCard">跳过 →</Button>
        </div>

      </div>

      <!-- 卡片下方提示（在卡片外，不影响卡片大小） -->
      <div v-if="currentItem" style="text-align:center;font-size:12px;color:#9ca3af;margin-top:12px;">
        💡 还有 {{ totalItems - cursor - 1 }} 道待复习
        <span v-if="hasMore"> · 向下滚动加载更多 ({{ currentPage }}/{{ totalPages }} 页)</span>
      </div>

      <div v-if="isLoadingMore" style="padding:20px;text-align:center;font-size:12px;color:#9ca3af;">⏳ 加载更多错题…</div>
    </div>

    <!-- 全景图视图 -->
    <div v-else-if="view === 'overview'" style="width:880px;max-width:100%;margin:0 auto;">
      <div v-if="chartLoading && !overviewData" style="padding:60px 0;text-align:center;color:#9ca3af;">⏳ 加载中…</div>
      <div v-else-if="overviewError" style="padding:14px;background:#fef2f2;color:#b91c1c;border-radius:8px;font-size:13px;">⚠️ {{ overviewError }}</div>
      <div v-else-if="overviewData">
        <div style="height:100px;margin-bottom:14px;background:linear-gradient(135deg,#faf5ff 0%,#eef2ff 100%);border:1px solid #ddd6fe;border-radius:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
          <div style="font-size:36px;font-weight:800;color:#6d28d9;line-height:1;">{{ overviewData.total }}</div>
          <div style="font-size:13px;color:#6b7280;margin-top:6px;">道错题待复习</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
          <div style="height:480px;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:16px;display:flex;flex-direction:column;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <div style="font-size:13px;font-weight:600;color:#111827;margin-bottom:12px;flex-shrink:0;">📚 按题型</div>
            <div v-if="overviewData.by_type.length === 0" style="font-size:12px;color:#9ca3af;text-align:center;padding:14px 0;flex:1;">无数据</div>
            <div v-else style="flex:1;overflow-y:auto;">
              <div v-for="t in overviewData.by_type" :key="t.k" @click="clickBarTo('type', t.k)" style="margin-bottom:8px;cursor:pointer;">
                <div style="display:flex;justify-content:space-between;font-size:12px;color:#374151;margin-bottom:3px;"><span>{{ t.k }}</span><b>{{ t.n }}</b></div>
                <div style="height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden;"><div :style="{ width:barWidth(overviewData.by_type,t.n),height:'100%',background:toneFg[TYPE_TONE[t.k]||'gray'],transition:'width .3s' }"></div></div>
              </div>
            </div>
          </div>
          <div style="height:480px;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:16px;display:flex;flex-direction:column;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <div style="font-size:13px;font-weight:600;color:#111827;margin-bottom:12px;flex-shrink:0;">🗺️ 按省份</div>
            <div v-if="overviewData.by_province.length === 0" style="font-size:12px;color:#9ca3af;text-align:center;padding:14px 0;flex:1;">无数据</div>
            <div v-else style="flex:1;overflow-y:auto;">
              <div v-for="p in overviewData.by_province" :key="p.k" @click="clickBarTo('province', p.k)" style="margin-bottom:8px;cursor:pointer;">
                <div style="display:flex;justify-content:space-between;font-size:12px;color:#374151;margin-bottom:3px;"><span>{{ p.k }}</span><b>{{ p.n }}</b></div>
                <div style="height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden;"><div :style="{ width:barWidth(overviewData.by_province,p.n),height:'100%',background:'#6366f1',transition:'width .3s' }"></div></div>
              </div>
            </div>
          </div>
        </div>

        <div style="height:160px;margin-bottom:14px;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:16px;display:flex;flex-direction:column;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
          <div style="display:flex;align-items:center;margin-bottom:12px;flex-shrink:0;"><div style="font-size:13px;font-weight:600;color:#111827;flex:1;">📅 按年份</div><span v-if="filterYear" @click="filterYear = null" style="font-size:11px;color:#6b7280;cursor:pointer;">清除年份筛选 ×</span></div>
          <div v-if="overviewData.by_year.length === 0" style="font-size:12px;color:#9ca3af;text-align:center;padding:14px 0;flex:1;">无数据</div>
          <div v-else style="display:flex;align-items:flex-end;gap:8px;height:80px;flex-shrink:0;">
            <div v-for="y in overviewData.by_year" :key="y.k" @click="clickBarTo('year', y.k)" :style="{ flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:'4px',cursor:'pointer',padding:'4px 2px',borderRadius:'6px',background:filterYear===y.k?'#ede9fe':'transparent',transition:'background .15s',height:'80px',justifyContent:'flex-end' }">
              <div :style="{ width:'100%',height:barHeight(overviewData.by_year,y.n),background:filterYear===y.k?'#7c3aed':'#a78bfa',borderRadius:'4px 4px 0 0',minHeight:'4px',transition:'background .15s' }" :title="`${y.n} 道`"></div>
              <div :style="{ fontSize:'11px',color:filterYear===y.k?'#6d28d9':'#6b7280',fontWeight:filterYear===y.k?600:400 }">{{ y.k }}</div>
              <div style="font-size:10px;color:#9ca3af;">{{ y.n }}</div>
            </div>
          </div>
        </div>

        <!-- AI 总结区：固定高度 400px，永不跳动 -->
        <div style="
          height: 400px;
          padding: 20px;
          border: 1px solid #ddd6fe;
          border-radius: 14px;
          background: linear-gradient(180deg, #faf5ff 0%, #fff 100%);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          box-sizing: border-box;
          margin-bottom: 14px;
        ">
          <!-- 标题行：固定顶部不收缩 -->
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-shrink: 0;">
            <span style="font-size: 14px; font-weight: 600; color: #6d28d9;">✨ AI 给你的话</span>
            <span v-if="overviewData.ai_summary?.from_cache && !summaryLoading" style="font-size: 10px; padding: 1px 6px; background: #f3f4f6; color: #6b7280; border-radius: 3px;">缓存 1h</span>
            <div style="flex: 1;"></div>
            <a v-if="!summaryLoading" href="javascript:void(0)" @click="refreshSummaryOnly" style="font-size: 11px; color: #2563eb;">↻ 重新生成</a>
            <span v-else style="font-size: 11px; color: #9ca3af;">⏳ 生成中…</span>
          </div>

          <!-- 内容区：flex:1 撑满剩余高度，内容从顶部开始，超出滚动 -->
          <div style="flex: 1; min-height: 0; overflow-y: auto; position: relative;">
            <!-- 加载遮罩层：覆盖但不改变 DOM 高度 -->
            <div v-if="summaryLoading || overviewData.ai_summary?._pending" style="
              position: absolute;
              top: 0; left: 0; right: 0; bottom: 0;
              display: flex;
              align-items: center;
              justify-content: center;
              background: rgba(250, 245, 255, 0.95);
              z-index: 5;
              border-radius: 8px;
            ">
              <div style="text-align: center; color: #6b7280; font-size: 13px;">
                🤔 AI 正在分析错题，预计 5-15 秒…
              </div>
            </div>

            <!-- 状态内容 -->
            <div>
              <div v-if="overviewData.ai_summary?.error && !summaryLoading" style="padding: 14px; background: #fef2f2; color: #b91c1c; border-radius: 8px; font-size: 13px;">
                ⚠️ AI 总结暂时不可用：{{ overviewData.ai_summary.error }}
                <a href="javascript:void(0)" @click="refreshSummaryOnly" style="margin-left: 10px; color: #2563eb;">点这里重试</a>
              </div>
              <div v-else-if="!overviewData.ai_summary?.text && !summaryLoading" style="padding: 40px 20px; text-align: center; color: #9ca3af; font-size: 13px;">
                <template v-if="overviewData.total === 0">🎉 没有错题，太棒了！</template>
                <template v-else>✨ 暂无总结，点击「重新生成」试试</template>
              </div>
              <div v-else-if="overviewData.ai_summary?.text" style="font-size: 13.5px; color: #1f2937; line-height: 1.7;" v-html="renderMarkdown(overviewData.ai_summary.text)"></div>
            </div>
          </div>

          <!-- 底部按钮：固定底部不收缩 -->
          <div style="padding-top: 14px; border-top: 1px solid #f3f4f6; display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0;">
            <Button variant="primary" :style="{ fontSize:'13px',padding:'8px 14px' }" @click="switchView('review')">
              📖 开始复习这些错题 →
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
}
</style>