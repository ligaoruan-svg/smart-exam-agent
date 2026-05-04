<script setup>
import { marked } from 'marked'
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { chatApi, practiceApi, getToken } from '@/api'
import { useAuthStore } from '@/stores/auth'
import PdfGeneratingCard from '@/components/PdfGeneratingCard.vue'

const router = useRouter()
const auth = useAuthStore()

/* ============================================================
 * 数据
 * ============================================================ */
const conversations = ref([])         // [{id, title, ...}]
const activeId = ref(null)
const messagesMap = reactive({})      // { sessionId: [msg, msg, ...] }
const draft = ref('')
const sending = ref(false)

const streamEl = ref(null)
const inputEl = ref(null)
const sidebarOpen = ref(true)

const suggestions = [
  { emoji: '📝', text: '帮我准备 5 道判断推理' },
  { emoji: '📊', text: '分析一下我的学习情况' },
  { emoji: '🎯', text: '随机出 5 道言语理解题' },
  { emoji: '🗺', text: '广东有哪些年份的真题' },
]

const currentMessages = computed(() => {
  if (!activeId.value) return []
  return messagesMap[activeId.value] || []
})

/* ============================================================
 * 卡片交互状态（跨刷新持久化）
 *
 * sessionStorage 存"用户已操作过的卡片"，让：
 *   - 点击瞬间立即变色（响应式触发）
 *   - 跳到做题页再回来 → 状态还在
 *   - 切换会话再切回来 → 状态还在
 *   - 后端返回的真实状态会覆盖本地状态
 *
 * key 设计：
 *   practice:<session_id>  →  'started' | 'cancelled' | 'finished'
 *   pack:<task_id>         →  'downloaded'
 * ============================================================ */
const STORAGE_KEY = 'gk_card_state_v1'

function loadCardStates() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

// reactive 让模板能响应式重渲染
const cardStates = reactive(loadCardStates())

function saveCardStates() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cardStates))
  } catch {
    // localStorage 满了就算了
  }
}

function setCardState(key, value) {
  cardStates[key] = value
  saveCardStates()
}

// 给 practice 卡片用的状态获取函数（模板里调）
function practiceState(card) {
  if (!card?.session_id) return null
  return cardStates[`practice:${card.session_id}`] || null
}

function packDownloaded(card) {
  const tid = card?.task_id || card?.data?.task_id
  if (!tid) return false
  return cardStates[`pack:${tid}`] === 'downloaded'
}

/* ============================================================
 * 初始化：拉历史对话
 * ============================================================ */
onMounted(async () => {
  await loadConversations()

  // 用户从练习页回来 / 切到这个 tab 时，刷新当前会话的 practice 卡片状态
  // 这样"已完成"的旧卡片立刻变灰，不会让用户再点错
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && activeId.value) {
      const msgs = messagesMap[activeId.value]
      if (msgs) refreshAllPracticeCards(msgs)
    }
  })
})

async function loadConversations() {
  try {
    const r = await chatApi.listSessions()
    conversations.value = r.sessions || []
    if (conversations.value.length > 0 && !activeId.value) {
      await switchConv(conversations.value[0].id)
    }
  } catch (e) {
    console.warn('[loadConversations]', e)
  }
}

async function switchConv(id) {
  if (sending.value) return
  activeId.value = id
  // 已加载过 → 仍要刷新一遍 practice 卡片状态（用户可能刚做完题回来）
  if (messagesMap[id] && messagesMap[id].length > 0) {
    refreshAllPracticeCards(messagesMap[id])
    await scrollBottom()
    return
  }
  try {
    const r = await chatApi.getMessages(id)
    const msgs = []
    for (const m of (r.messages || [])) {
      msgs.push({
        role: m.role === 'user' ? 'me' : 'ai',
        text: m.content || '',
        cards: Array.isArray(m.ui_cards) ? m.ui_cards : [],
        think: null,
        thinkOpen: false,
        streaming: false,
      })
    }
    messagesMap[id] = msgs
    await scrollBottom()
    refreshAllPracticeCards(msgs)
  } catch (e) {
    console.error('[switchConv]', e)
  }
}

/** 扫一组 messages 里所有 practice 卡片去刷新状态 */
function refreshAllPracticeCards(msgs) {
  for (const m of (msgs || [])) {
    for (const c of (m.cards || [])) {
      if (c.type === 'practice_ready' && c.session_id) {
        refreshPracticeCardStatus(c)
      }
    }
  }
}

async function newChat() {
  try {
    const r = await chatApi.newSession('新对话')
    conversations.value.unshift({
      id: r.id,
      title: r.title || '新对话',
      pinned: 0,
      updated_at: new Date().toISOString(),
    })
    activeId.value = r.id
    messagesMap[r.id] = []
  } catch (e) {
    alert('创建对话失败：' + e.message)
  }
}

async function deleteConv(id) {
  if (!confirm('确定删除此对话？')) return
  try {
    await chatApi.deleteSession(id)
    conversations.value = conversations.value.filter(c => c.id !== id)
    delete messagesMap[id]
    if (activeId.value === id) {
      activeId.value = conversations.value[0]?.id || null
      if (activeId.value) await switchConv(activeId.value)
    }
  } catch (e) {
    alert('删除失败：' + e.message)
  }
}

/* ============================================================
 * 发送 + SSE
 * ============================================================ */
async function quickAsk(text) {
  draft.value = text
  await send()
}

async function send() {
  const text = draft.value.trim()
  if (!text || sending.value) return
  draft.value = ''
  sending.value = true

  // 没有对话时先建一个
  if (!activeId.value) {
    try {
      const r = await chatApi.newSession(text.slice(0, 20))
      conversations.value.unshift({
        id: r.id,
        title: r.title || text.slice(0, 20),
        pinned: 0,
        updated_at: new Date().toISOString(),
      })
      activeId.value = r.id
      messagesMap[r.id] = []
    } catch (e) {
      sending.value = false
      alert('创建对话失败：' + e.message)
      return
    }
  }

  const sid = activeId.value
  if (!messagesMap[sid]) messagesMap[sid] = []

  // 1. 用户消息
  messagesMap[sid].push({
    role: 'me',
    text,
    cards: [],
    think: null,
    streaming: false,
  })
  await scrollBottom()

  // 2. AI 占位消息（流式 reactive 更新）
  const aiMsg = reactive({
    role: 'ai',
    text: '',
    cards: [],
    think: {
      steps: [],         // [{label, details:[], toolCalls:[]}]
      elapsedMs: 0,
      done: false,
    },
    thinkOpen: true,     // 默认展开
    streaming: true,
  })
  messagesMap[sid].push(aiMsg)
  await scrollBottom()

  // 3. SSE
  let currentStep = null
  try {
    for await (const ev of chatApi.stream(text, sid)) {
      const { event, data } = ev

      if (event === 'session') {
        // 后端可能返回新 session_id
        if (data.session_id && data.session_id !== sid) {
          activeId.value = data.session_id
        }
      } else if (event === 'thinking_start') {
        currentStep = {
          label: data.label,
          details: [],
          toolCalls: [],
        }
        aiMsg.think.steps.push(currentStep)
      } else if (event === 'thinking_step') {
        if (currentStep) currentStep.details.push(data.detail)
      } else if (event === 'tool_call_start') {
        if (currentStep) {
          currentStep.toolCalls.push({
            name: data.name,
            arguments: data.arguments,
            elapsed_ms: null,
            ok: null,
            summary: null,
            error: null,
            open: false,
          })
        }
      } else if (event === 'tool_call_done') {
        if (currentStep && currentStep.toolCalls.length > 0) {
          const tc = currentStep.toolCalls[currentStep.toolCalls.length - 1]
          tc.elapsed_ms = data.elapsed_ms
          tc.ok = data.ok
          tc.summary = data.summary
          tc.error = data.error
        }
      } else if (event === 'ui_card') {
        aiMsg.cards.push(data.card)
        await scrollBottom()
      } else if (event === 'text_delta') {
        aiMsg.text += data.delta
        await scrollBottom()
      } else if (event === 'done') {
        aiMsg.think.elapsedMs = data.total_ms
        aiMsg.think.done = true
        aiMsg.streaming = false
        // 思考完默认收起，让对话主体更清爽
        aiMsg.thinkOpen = false
        // 刷新用户配额
        auth.fetchMe()
      } else if (event === 'error') {
        aiMsg.text += `\n\n⚠️ 错误：${data.message}`
        aiMsg.streaming = false
      }
    }
  } catch (e) {
    console.error('[stream]', e)
    aiMsg.text += `\n\n⚠️ 连接失败：${e.message}`
    aiMsg.streaming = false
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

/* ============================================================
 * UI 卡片交互
 * ============================================================ */
function startPractice(card) {
  if (!card?.session_id) return
  // 立即写持久化状态（响应式 + sessionStorage）
  // 即使马上跳走，回来时仍是 started
  setCardState(`practice:${card.session_id}`, 'started')
  router.push(`/practice?session=${card.session_id}`)
}

async function cancelPractice(card) {
  if (!card?.session_id) return
  if (!confirm('取消这次练习？')) return
  try {
    await practiceApi.cancel(card.session_id)
    setCardState(`practice:${card.session_id}`, 'cancelled')
  } catch (e) {
    alert('取消失败：' + e.message)
  }
}

/**
 * 异步检查练习卡片对应的 session 当前状态。
 * 进入会话时跑一遍 - 让"已完成/已取消"的卡片不再像"待办"。
 */
async function refreshPracticeCardStatus(card) {
  if (!card?.session_id) return
  const sid = card.session_id
  const cur = cardStates[`practice:${sid}`]
  // 已经是终态就不再查
  if (cur === 'cancelled' || cur === 'finished') return
  try {
    const s = await practiceApi.getSession(sid)
    const status = s?.session?.status || s?.status
    if (status === 'finished' || status === 'completed') {
      setCardState(`practice:${sid}`, 'finished')
    } else if (status === 'cancelled') {
      setCardState(`practice:${sid}`, 'cancelled')
    } else if (status === 'in_progress' || status === 'started') {
      // 后端有进度 → 标 started
      if (cur !== 'started') setCardState(`practice:${sid}`, 'started')
    }
  } catch (e) {
    // 静默：session 可能已清理
  }
}

/* 下载省份整包 / 子集 ZIP（pack_ready 卡片用） */
async function downloadPackZip(card) {
  const url = card?.data?.download_url
  const label = card?.data?.file_label
              || `${card?.data?.province || '试卷'}公考真题`
  if (!url) return
  try {
    const resp = await fetch(url, {
      headers: { 'Authorization': `Bearer ${getToken()}` },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = `${label}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(objUrl), 1500)
    // 标记已下载（视觉灰化，仍可重下）
    const tid = card?.task_id || card?.data?.task_id
    if (tid) setCardState(`pack:${tid}`, 'downloaded')
  } catch (e) {
    alert(`下载失败：${e.message}`)
  }
}

function fmtSec(ms) {
  if (ms == null) return '0'
  return (ms / 1000).toFixed(1)
}
function fmtMs(ms) {
  if (ms == null) return '...'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

/* ============================================================
 * 输入区
 * ============================================================ */
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function scrollBottom() {
  await nextTick()
  if (streamEl.value) {
    streamEl.value.scrollTop = streamEl.value.scrollHeight
  }
}
</script>

<template>
  <div class="chat-layout">
    <!-- 左侧会话列表 -->
    <aside :class="['chat-sidebar', { collapsed: !sidebarOpen }]">
      <!-- 收起时只显示 toggle 按钮 -->
      <template v-if="!sidebarOpen">
        <button class="sidebar-toggle collapsed-toggle" @click="sidebarOpen = true" title="展开侧边栏">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="3"/>
            <line x1="9" y1="3" x2="9" y2="21"/>
            <polyline points="13 9 16 12 13 15"/>
          </svg>
        </button>
      </template>

      <template v-else>
        <div class="sidebar-top">
          <button class="new-chat-btn" @click="newChat">
            <span class="plus">+</span>
            <span>新对话</span>
          </button>
          <button class="sidebar-toggle" @click="sidebarOpen = false" title="收起侧边栏">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="3"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
              <polyline points="13 15 10 12 13 9"/>
            </svg>
          </button>
        </div>

        <div class="convs-label">对话</div>
        <div class="convs">
          <div
            v-for="c in conversations"
            :key="c.id"
            :class="['conv-item', { active: c.id === activeId }]"
            @click="switchConv(c.id)"
          >
            <span class="conv-icon">💬</span>
            <span class="conv-title">{{ c.title || '新对话' }}</span>
            <button class="conv-del" title="删除" @click.stop="deleteConv(c.id)">×</button>
          </div>
          <div v-if="conversations.length === 0" class="convs-empty">暂无对话</div>
        </div>
      </template>
    </aside>

    <!-- 主区 -->
    <main class="chat-main">
      <!-- 空态 -->
      <div v-if="currentMessages.length === 0" class="empty-state">
        <div class="logo-big">智</div>
        <h1 class="greeting">有什么想问的？</h1>
        <p class="sub">公考真题、行测技巧、申论范文，随便聊</p>
        <div class="suggestion-grid">
          <button
            v-for="s in suggestions"
            :key="s.text"
            class="sug-card"
            @click="quickAsk(s.text)"
          >
            <span class="sug-emoji">{{ s.emoji }}</span>
            <span class="sug-text">{{ s.text }}</span>
          </button>
        </div>
      </div>

      <!-- 消息流 -->
      <div v-else class="chat-stream" ref="streamEl">
        <div
          v-for="(m, i) in currentMessages"
          :key="i"
          :class="['msg', m.role]"
        >
          <div class="msg-inner">
            <div class="msg-avatar">{{ m.role === 'me' ? '你' : '智' }}</div>
            <div class="msg-body">
              <!-- 思考过程 -->
              <div v-if="m.think && m.think.steps.length > 0" class="think-box">
                <div class="think-head" @click="m.thinkOpen = !m.thinkOpen">
                  <span v-if="m.think.done">
                    ✓ 已思考 (用时 {{ fmtSec(m.think.elapsedMs) }} 秒)
                  </span>
                  <span v-else>
                    💭 正在思考...
                  </span>
                  <span class="think-toggle">{{ m.thinkOpen ? '▲' : '▼' }}</span>
                </div>
                <div v-if="m.thinkOpen" class="think-steps">
                  <div v-for="(s, j) in m.think.steps" :key="j" class="think-step">
                    <div class="step-label">✓ {{ s.label }}</div>
                    <!-- 步骤细节文字 -->
                    <div v-for="(d, k) in s.details" :key="`d-${k}`" class="step-detail">
                      ↳ {{ d }}
                    </div>
                    <!-- 工具调用 -->
                    <div
                      v-for="(tc, k) in s.toolCalls"
                      :key="`tc-${k}`"
                      class="tool-call"
                    >
                      <div class="tc-head" @click="tc.open = !tc.open">
                        <span class="tc-icon">🔧</span>
                        <span class="tc-name">{{ tc.name }}</span>
                        <span
                          v-if="tc.elapsed_ms != null"
                          :class="['tc-time', { failed: tc.ok === false }]"
                        >
                          {{ tc.ok === false ? '✗' : '✓' }} {{ fmtMs(tc.elapsed_ms) }}
                        </span>
                        <span class="tc-caret">{{ tc.open ? '▼' : '▶' }}</span>
                      </div>
                      <div v-if="tc.summary && !tc.open" class="tc-summary">
                        {{ tc.summary }}
                      </div>
                      <div v-if="tc.open" class="tc-detail">
                        <div class="tc-section">
                          <div class="tc-label">参数</div>
                          <pre>{{ JSON.stringify(tc.arguments || {}, null, 2) }}</pre>
                        </div>
                        <div v-if="tc.summary" class="tc-section">
                          <div class="tc-label">结果</div>
                          <div class="tc-result">{{ tc.summary }}</div>
                        </div>
                        <div v-if="tc.error" class="tc-section">
                          <div class="tc-label tc-label-err">错误</div>
                          <pre class="tc-err">{{ tc.error }}</pre>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 文本 -->
              <div v-if="m.text" class="msg-text">
                <div class="msg-text-md" v-html="marked(m.text || '')"></div>
                <span v-if="m.streaming" class="cursor">▌</span>
              </div>

              <!-- UI 卡片 -->
              <div v-for="(card, ci) in (m.cards || [])" :key="`c-${ci}`" class="ui-card-wrap">
                <!-- practice_ready 卡片 -->
                <div
                  v-if="card.type === 'practice_ready'"
                  :class="['card-practice', {
                    cancelled: practiceState(card) === 'cancelled',
                    finished:  practiceState(card) === 'finished',
                    started:   practiceState(card) === 'started',
                  }]"
                >
                  <div class="cp-head">
                    <span class="cp-icon">📝</span>
                    <span class="cp-title">
                      <template v-if="practiceState(card) === 'cancelled'">已取消</template>
                      <template v-else-if="practiceState(card) === 'finished'">✓ 已完成</template>
                      <template v-else-if="practiceState(card) === 'started'">⌛ 进行中</template>
                      <template v-else>AI 已为你准备好练习</template>
                    </span>
                  </div>
                  <div class="cp-body">
                    <div class="cp-row"><span>题数</span><b>{{ card.data?.count }} 道</b></div>
                    <div class="cp-row"><span>题型</span><b>{{ card.data?.question_type || '混合' }}</b></div>
                    <div v-if="card.data?.source" class="cp-row">
                      <span>来源</span><b class="src">{{ card.data.source }}</b>
                    </div>
                    <div v-if="card.data?.estimated_minutes" class="cp-row">
                      <span>预计</span><b>约 {{ card.data.estimated_minutes }} 分钟</b>
                    </div>
                  </div>
                  <!-- 仅在"未取消 + 未完成"时显示按钮 -->
                  <div
                    v-if="practiceState(card) !== 'cancelled' && practiceState(card) !== 'finished'"
                    class="cp-actions"
                  >
                    <button class="cp-btn primary" @click="startPractice(card)">
                      <template v-if="practiceState(card) === 'started'">继续练习 →</template>
                      <template v-else>开始练习 →</template>
                    </button>
                    <button
                      v-if="practiceState(card) !== 'started'"
                      class="cp-btn ghost"
                      @click="cancelPractice(card)"
                    >
                      取消
                    </button>
                  </div>
                </div>

                <!-- pack_ready 卡片：省份/子集 ZIP，简洁单行风格 -->
                <div
                  v-else-if="card.type === 'pack_ready'"
                  class="pack-card"
                  :class="{
                    [`pack-${card.data?.status || 'preparing'}`]: true,
                    'pack-done': packDownloaded(card),
                  }"
                >
                  <div class="pack-line">
                    <span class="pack-icon">📦</span>
                    <span class="pack-title">
                      {{ card.data?.file_label || `${card.data?.province}公考真题` }}
                    </span>
                    <span class="pack-size" v-if="card.data?.size_mb">
                      （{{ card.data.size_mb }} MB）
                    </span>
                    <template v-if="card.data?.status === 'ready' && card.data?.download_url">
                      <span class="pack-arrow">→</span>
                      <a
                        v-if="!packDownloaded(card)"
                        class="pack-link"
                        href="javascript:void(0)"
                        @click="downloadPackZip(card)"
                      >
                        点击下载
                      </a>
                      <span v-else class="pack-done-tag">✓ 已下载</span>
                    </template>
                    <span v-else class="pack-status">⏳ 准备中…</span>
                  </div>
                  <div class="pack-sub" v-if="card.data?.paper_count">
                    {{ card.data.paper_count }} 份文件<template v-if="card.data?.filter_desc"> · {{ card.data.filter_desc }}</template>
                  </div>
                </div>

                <!-- pdf_generating 卡片：用子组件，自带轮询 -->
                <PdfGeneratingCard
                  v-else-if="card.type === 'pdf_generating'"
                  :card="card"
                />

                <!-- 未知类型兜底 -->
                <div v-else class="card-fallback">
                  <div>⚠️ 未知卡片：{{ card.type }}</div>
                  <pre>{{ JSON.stringify(card, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区，吸底 -->
      <div class="input-dock">
        <div class="input-wrap">
          <textarea
            ref="inputEl"
            v-model="draft"
            rows="1"
            placeholder="问公考小智任何问题…"
            :disabled="sending"
            @keydown="handleKey"
          />
          <button
            class="send-btn"
            :disabled="!draft.trim() || sending"
            @click="send"
            title="发送 (Enter)"
          >↑</button>
        </div>
        <div class="input-hint">
          <span v-if="sending">思考中…</span>
          <span v-else>Enter 发送 · Shift+Enter 换行</span>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ============================================================
 * 布局
 * ============================================================ */
.chat-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  height: calc(100vh - 64px);
  background: #fff;
  transition: grid-template-columns .22s ease;
}

/* ============================================================
 * 侧边栏
 * ============================================================ */
.chat-sidebar {
  border-right: 1px solid #e5e7eb;
  padding: 16px 12px;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all .22s ease;
  min-width: 0;
}
.chat-sidebar.collapsed {
  padding: 16px 8px;
  width: 48px;
  min-width: 48px;
  align-items: center;
}
/* 让父 grid 响应收起 */
.chat-layout:has(.chat-sidebar.collapsed) {
  grid-template-columns: 48px 1fr;
}
.sidebar-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 18px;
}
.sidebar-top .new-chat-btn {
  flex: 1;
  margin-bottom: 0;
}
.sidebar-toggle {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
  font-family: inherit;
  padding: 0;
}
.sidebar-toggle:hover {
  color: #374151;
  background: #f3f4f6;
}
.collapsed-toggle {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
  font-family: inherit;
  padding: 0;
  margin-top: 2px;
}
.collapsed-toggle:hover {
  color: #374151;
  background: #f3f4f6;
}
.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #111827;
  cursor: pointer;
  transition: all .18s;
  margin-bottom: 18px;
  font-family: inherit;
}
.new-chat-btn:hover {
  border-color: #10b981;
  color: #10b981;
}
.new-chat-btn .plus {
  font-size: 18px;
  line-height: 1;
}
.convs-label {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 600;
  letter-spacing: .04em;
  padding: 0 10px 6px;
  text-transform: uppercase;
}
.convs {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
  transition: background .15s;
  position: relative;
}
.conv-item:hover {
  background: #f3f4f6;
}
.conv-item.active {
  background: #ecfdf5;
  color: #047857;
}
.conv-icon {
  flex-shrink: 0;
  font-size: 14px;
}
.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-del {
  background: none;
  border: none;
  color: #9ca3af;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  visibility: hidden;
  font-family: inherit;
}
.conv-item:hover .conv-del {
  visibility: visible;
}
.conv-del:hover {
  color: #ef4444;
}
.convs-empty {
  text-align: center;
  color: #9ca3af;
  padding: 20px 0;
  font-size: 13px;
}

/* ============================================================
 * 主区
 * ============================================================ */
.chat-main {
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

/* 空态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px 120px;
  text-align: center;
}
.logo-big {
  width: 60px;
  height: 60px;
  border-radius: 16px;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  font-weight: 900;
  font-size: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  box-shadow: 0 8px 20px rgba(16, 185, 129, .3);
}
.greeting {
  font-size: 28px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 6px;
}
.sub {
  color: #6b7280;
  font-size: 14px;
  margin: 0 0 32px;
}
.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 600px;
  width: 100%;
}
.sug-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  transition: all .18s;
  font-family: inherit;
  text-align: left;
}
.sug-card:hover {
  border-color: #10b981;
  background: #f0fdf4;
  color: #047857;
  transform: translateY(-1px);
}
.sug-emoji {
  font-size: 18px;
  flex-shrink: 0;
}

/* 消息流 */
.chat-stream {
  flex: 1;
  overflow-y: auto;
  padding: 32px 24px 140px;
  scroll-behavior: smooth;
}
.msg {
  margin-bottom: 24px;
}
.msg-inner {
  display: flex;
  gap: 12px;
  max-width: 820px;
  margin: 0 auto;
}
.msg.me .msg-inner {
  flex-direction: row-reverse;
}
.msg-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}
.msg.ai .msg-avatar {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
}
.msg-body {
  flex: 1;
  min-width: 0;
  max-width: 100%;
}
.msg.me .msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.msg-text {
  background: #f9fafb;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.7;
  color: #1f2937;
  font-size: 14px;
  display: inline-block;
  max-width: 100%;
  word-wrap: break-word;
}
.msg.me .msg-text {
  background: #ecfdf5;
  color: #064e3b;
}
.cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: #10b981;
  font-weight: 600;
  margin-left: 1px;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ============================================================
 * 思考过程
 * ============================================================ */
.think-box {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  margin-bottom: 8px;
  overflow: hidden;
  background: #fafafa;
  font-size: 13px;
}
.think-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  color: #4b5563;
  font-weight: 500;
  user-select: none;
  transition: background .15s;
}
.think-head:hover {
  background: #f3f4f6;
}
.think-toggle {
  font-size: 11px;
  color: #9ca3af;
}
.think-steps {
  border-top: 1px solid #e5e7eb;
  padding: 10px 14px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.think-step {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.step-label {
  color: #1f2937;
  font-weight: 500;
  font-size: 13px;
}
.step-detail {
  margin-left: 16px;
  color: #6b7280;
  font-size: 12px;
}

/* 工具调用 */
.tool-call {
  margin-left: 16px;
  margin-top: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
}
.tc-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
  user-select: none;
}
.tc-head:hover {
  background: #f3f4f6;
}
.tc-icon {
  font-size: 11px;
}
.tc-name {
  font-family: ui-monospace, "Menlo", monospace;
  color: #4338ca;
  flex: 1;
  font-size: 12px;
}
.tc-time {
  color: #6b7280;
  font-size: 11px;
}
.tc-time.failed {
  color: #dc2626;
}
.tc-caret {
  color: #9ca3af;
  font-size: 10px;
}
.tc-summary {
  padding: 0 10px 6px 28px;
  color: #6b7280;
  font-size: 12px;
}
.tc-detail {
  padding: 6px 10px 8px;
  border-top: 1px solid #f3f4f6;
}
.tc-section {
  margin: 6px 0;
}
.tc-label {
  font-size: 10px;
  color: #9ca3af;
  margin-bottom: 2px;
  text-transform: uppercase;
  letter-spacing: .05em;
  font-weight: 600;
}
.tc-label-err {
  color: #dc2626;
}
.tc-section pre {
  background: #fff;
  border: 1px solid #f3f4f6;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
  max-height: 200px;
  overflow: auto;
  margin: 0;
  font-family: ui-monospace, "Menlo", monospace;
  white-space: pre-wrap;
  word-break: break-word;
}
.tc-result {
  background: #fff;
  border: 1px solid #f3f4f6;
  padding: 6px 8px;
  border-radius: 4px;
  color: #374151;
  font-size: 12px;
}
.tc-err {
  background: #fef2f2 !important;
  border-color: #fecaca !important;
  color: #991b1b;
}

/* ============================================================
 * UI 卡片：练习准备好
 * ============================================================ */
.ui-card-wrap {
  margin-top: 12px;
}
.card-practice {
  border: 1px solid #d1f0d6;
  background: linear-gradient(180deg, #f0fff4 0%, #ffffff 100%);
  border-radius: 12px;
  padding: 16px;
  max-width: 460px;
  transition: opacity .3s;
  box-shadow: 0 1px 4px rgba(16, 185, 129, .08);
}
.card-practice.cancelled {
  opacity: .5;
  filter: grayscale(.6);
}
.card-practice.finished {
  opacity: .7;
  filter: grayscale(.4);
  background: linear-gradient(180deg, #f9fafb 0%, #ffffff 100%);
}
.card-practice.finished .cp-head {
  color: #6b7280;
}
.card-practice.started {
  background: linear-gradient(180deg, #fefce8 0%, #ffffff 100%);
  border-color: #fde68a;
}
.card-practice.started .cp-head {
  color: #92400e;
}
.cp-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
  color: #047857;
}
.cp-icon {
  font-size: 18px;
}
.cp-body {
  margin-bottom: 14px;
}
.cp-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}
.cp-row span {
  color: #6b7280;
}
.cp-row b {
  color: #111827;
  font-weight: 500;
}
.cp-row b.src {
  font-size: 12px;
  color: #4b5563;
  max-width: 280px;
  text-align: right;
  word-break: break-all;
  font-weight: 400;
}
.cp-actions {
  display: flex;
  gap: 8px;
}
.cp-btn {
  flex: 1;
  padding: 9px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  border: 1px solid transparent;
  transition: all .15s;
}
.cp-btn.primary {
  background: #10b981;
  color: #fff;
  border-color: #10b981;
}
.cp-btn.primary:hover {
  background: #059669;
  border-color: #059669;
}
.cp-btn.ghost {
  background: #fff;
  color: #6b7280;
  border-color: #e5e7eb;
  flex: 0 0 auto;
  padding: 9px 18px;
}
.cp-btn.ghost:hover {
  background: #f9fafb;
  color: #374151;
}

/* 通用 info 卡片（pack_ready / pdf_generating） */
.card-info {
  border: 1px solid #fde68a;
  background: #fffbeb;
  border-radius: 10px;
  padding: 12px 14px;
  max-width: 420px;
  font-size: 13px;
}
.ci-head {
  font-weight: 600;
  color: #92400e;
  margin-bottom: 6px;
}
.ci-meta {
  color: #78350f;
  font-size: 12px;
  margin-bottom: 6px;
}
.ci-status {
  font-size: 12px;
  color: #92400e;
  background: #fef3c7;
  padding: 4px 10px;
  border-radius: 6px;
  display: inline-block;
}

.card-fallback {
  border: 1px dashed #fca5a5;
  background: #fef2f2;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  color: #991b1b;
  max-width: 480px;
}
.card-fallback pre {
  margin: 6px 0 0;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  background: #fff;
  padding: 6px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 160px;
}

/* ============================================================
 * 输入区
 * ============================================================ */
.input-dock {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 24px 20px;
  background: linear-gradient(180deg, transparent, #fff 30%);
  pointer-events: none;
}
.input-wrap {
  max-width: 820px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 10px 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, .04);
  pointer-events: auto;
}
.input-wrap:focus-within {
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, .12);
}
.input-wrap textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  background: transparent;
  color: #111827;
  max-height: 200px;
  padding: 6px 4px;
}
.input-wrap textarea:disabled {
  color: #9ca3af;
}
.send-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #111827;
  color: #fff;
  border: none;
  font-size: 16px;
  cursor: pointer;
  font-family: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background .15s;
}
.send-btn:hover:not(:disabled) {
  background: #10b981;
}
.send-btn:disabled {
  background: #d1d5db;
  cursor: not-allowed;
}
.input-hint {
  max-width: 820px;
  margin: 6px auto 0;
  font-size: 11px;
  color: #9ca3af;
  text-align: center;
  pointer-events: auto;
}

/* pack_ready 卡片（省份/子集整包下载，简洁单行风） */
.pack-card {
  background: #fff;
  border: 1px solid var(--gk-gray-200, #e5e7eb);
  border-left: 3px solid var(--gk-green-500, #10b981);
  border-radius: 8px;
  padding: 10px 14px;
  margin-top: 6px;
  font-size: 13px;
  max-width: 480px;
  transition: opacity .25s, filter .25s;
}
.pack-card.pack-done {
  opacity: .6;
  filter: grayscale(.55);
  border-left-color: var(--gk-gray-400, #9ca3af);
}
.pack-card.pack-done .pack-link {
  color: var(--gk-gray-500, #6b7280);
}
.pack-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  line-height: 1.5;
}
.pack-icon { font-size: 15px; }
.pack-title {
  font-weight: 600;
  color: var(--gk-gray-900, #111827);
}
.pack-size {
  color: var(--gk-gray-500, #6b7280);
  font-size: 12px;
}
.pack-arrow {
  color: var(--gk-gray-400, #9ca3af);
  margin: 0 2px;
}
.pack-link {
  color: var(--gk-green-600, #059669);
  text-decoration: none;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 1px solid currentColor;
}
.pack-link:hover { opacity: 0.85; }
.pack-done-tag {
  color: var(--gk-gray-500, #6b7280);
  font-weight: 500;
}
.pack-status {
  color: var(--gk-gray-500, #6b7280);
  font-size: 12px;
}
.pack-sub {
  margin-top: 4px;
  font-size: 11px;
  color: var(--gk-gray-500, #6b7280);
}

.msg-text-md { line-height: 1.7; }
.msg-text-md h1, .msg-text-md h2, .msg-text-md h3, .msg-text-md h4 {
  font-weight: bold; margin: 10px 0 6px;
}
.msg-text-md h3 { font-size: 15px; }
.msg-text-md strong { font-weight: 600; }
.msg-text-md ul, .msg-text-md ol { padding-left: 18px; margin: 4px 0; }
.msg-text-md li { margin: 3px 0; }
.msg-text-md p { margin: 6px 0; }
.msg-text-md hr { border: none; border-top: 1px solid #eee; margin: 10px 0; }
.msg-text-md table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; }
.msg-text-md th, .msg-text-md td { border: 1px solid #e0e0e0; padding: 6px 10px; text-align: left; }
.msg-text-md th { background: #f5f5f5; font-weight: 600; }

</style>
