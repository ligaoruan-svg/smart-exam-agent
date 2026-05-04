/**
 * src/api/index.js — 接口层
 *
 * 设计原则:
 *  1. 真实接口 (auth / chat / practice) 直接调后端
 *  2. 还没接通的接口 (admin / paper / mistake 等) 走 mock，
 *     真实接口实现后只需替换函数体
 *  3. 鉴权失败 (401) 自动跳登录
 *  4. SSE 流式对话用 async generator
 */

import * as M from '@/mock/data'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8900'
const delay = (ms = 200) => new Promise(r => setTimeout(r, ms))

/* ======================================================
 * Token 管理
 * ====================================================== */
export function getToken() {
  return localStorage.getItem('gk_token') || ''
}
export function setToken(t) {
  if (t) localStorage.setItem('gk_token', t)
  else localStorage.removeItem('gk_token')
}

/* ======================================================
 * 通用 request
 * ====================================================== */
async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  let resp
  try {
    resp = await fetch(url, { ...options, headers })
  } catch (e) {
    const err = new Error('网络错误：无法连接后端服务')
    err.response = { data: { detail: '后端未启动或不可达' } }
    throw err
  }

  if (resp.status === 401) {
    setToken(null)
    // 不在登录页才跳转，跳转后不抛错误（避免 Login 组件捕获后显示「请先登录」）
    if (typeof window !== 'undefined' && !location.pathname.startsWith('/login')) {
      location.href = '/login'
      return  // 跳转后直接返回，不抛错误
    }
    // 已在登录页（登录失败场景），抛出具体错误给组件处理
    const err = new Error('账号或密码错误，请检查后重试')
    err.response = { data: { detail: '账号或密码错误，请检查后重试' } }
    err.status = 401
    throw err
  }

  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    let detail = msg
    try {
      const j = await resp.json()
      detail = j.detail || j.message || msg
      msg = detail
    } catch {}
    const err = new Error(msg)
    err.response = { data: { detail } }
    err.status = resp.status
    throw err
  }

  const ct = resp.headers.get('content-type') || ''
  if (ct.includes('application/json')) return resp.json()
  return resp.text()
}

/* ======================================================
 * 真实接口 - Auth
 * ====================================================== */
export const authApi = {
  login: (username, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }).then(r => {
      setToken(r.token)
      return r
    }),

  register: (payload) =>
    request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }).then(r => {
      setToken(r.token)
      return r
    }),

  me: () => request('/api/auth/me'),

  logout: () => setToken(null),
}

/* ======================================================
 * 真实接口 - Chat (SSE)
 * ====================================================== */
export const chatApi = {
  listSessions: () => request('/api/chat/sessions'),

  newSession: (title) =>
    request('/api/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  deleteSession: (id) =>
    request(`/api/chat/sessions/${id}`, { method: 'DELETE' }),

  getMessages: (id) => request(`/api/chat/sessions/${id}/messages`),

  /**
   * SSE 流式发送。返回 async iterator，每个 yield 是 {event, data}。
   * 用法：
   *   for await (const ev of chatApi.stream(text, sid)) {
   *     if (ev.event === 'text_delta') ...
   *   }
   */
  async *stream(message, session_id = null) {
    const token = getToken()
    const resp = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ message, session_id }),
    })

    if (!resp.ok) {
      throw new Error(`SSE 请求失败: HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let idx
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)

          const lines = block.split('\n')
          let event = 'message'
          let dataStr = ''
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
          }
          if (!dataStr) continue
          let data = dataStr
          try {
            data = JSON.parse(dataStr)
          } catch {}
          yield { event, data }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
}

/* ======================================================
 * 真实接口 - Practice
 * ====================================================== */
export const practiceApi = {
  getPending: () => request('/api/practice/pending'),
  getSession: (id) => request(`/api/practice/session/${id}`),
  start: (id) => request(`/api/practice/start/${id}`, { method: 'POST' }),
  cancel: (id) => request(`/api/practice/cancel/${id}`, { method: 'POST' }),
  submitAnswer: (session_id, question_id, user_answer, time_spent = 0) =>
    request('/api/practice/answer', {
      method: 'POST',
      body: JSON.stringify({ session_id, question_id, user_answer, time_spent }),
    }),
  finish: (id) => request(`/api/practice/finish/${id}`, { method: 'POST' }),

  // 👇 新增：快速开始练习
  quickStart: ({ count = 20, question_type = null, province = null }) =>
    request('/api/practice/quick-start', {
      method: 'POST',
      body: JSON.stringify({ count, question_type, province }),
    }),
}

/* ======================================================
 * 真实接口 - Paper（真题下载，round 3 新增）
 * ====================================================== */
export const paperApi = {
  /** 列表，可按 province / year / exam_type / doc_type / keyword / page / page_size 过滤 */
  list: (params = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') qs.append(k, v)
    })
    const s = qs.toString()
    return request(`/api/paper/list${s ? `?${s}` : ''}`)
  },
  /** 32 省份统计（DownloadPanel 主表） */
  listProvinces: () => request('/api/paper/provinces'),
  /**
   * 单文件下载 URL（前端用 fetch + Authorization 拉，不要直接 window.open
   * 因为 token 不会带过去）
   */
  fileDownloadUrl: (paperId) => `/api/paper/file/${paperId}`,
  /** 省份整包 ZIP 下载 URL */
  zipDownloadUrl: (province) => `/api/paper/zip/${encodeURIComponent(province)}`,
}

/* ======================================================
 * 真实接口 - PDF 异步生成（round 3 新增）
 * ====================================================== */
export const pdfApi = {
  /** 查询任务状态，前端轮询用 */
  status: (taskId) => request(`/api/pdf/${encodeURIComponent(taskId)}/status`),
  /** 完成后下载（需要带 Authorization，让组件用 fetch 处理） */
  downloadUrl: (taskId) => `/api/pdf/${encodeURIComponent(taskId)}/download`,
}

/* ======================================================
 * UserCenter — 真接口 + 适配 UI 字段
 *
 * 后端 /api/auth/me 返回字段：
 *   id, username, nickname, email, plan, daily_limit, daily_used,
 *   total_answered, total_correct, role
 *
 * UI 期望字段（mock currentUser）：
 *   username, nickname, avatar, email, phone, joinedAt,
 *   membership: {plan, expiresAt, label}, points,
 *   stats: {practiced, correctRate, streak, studyDays, mistakes, aiChats}
 *
 * 这里做 adapter，缺的字段填合理默认值。
 * ====================================================== */
export async function fetchCurrentUser() {
  try {
    const me = await authApi.me()
    const planLabelMap = {
      free: '免费版',
      pro: '高级会员',
      enterprise: '机构版',
    }
    const correctRate = me.total_answered
      ? Math.round((me.total_correct / me.total_answered) * 100)
      : 0
    return {
      // 原始字段
      ...me,
      // UI 适配
      avatar: (me.nickname || me.username || '你').charAt(0),
      phone: '', // 后端暂无
      joinedAt: '', // 后端暂无
      membership: {
        plan: me.plan || 'free',
        expiresAt: '',
        label: planLabelMap[me.plan] || me.plan,
      },
      points: 0, // 暂无
      stats: {
        practiced: me.total_answered || 0,
        correctRate,
        streak: 0, // 暂无
        studyDays: 0, // 暂无
        mistakes: (me.total_answered || 0) - (me.total_correct || 0),
        aiChats: 0, // 暂无
        dailyUsed: me.daily_used || 0,
        dailyLimit: me.daily_limit || 20,
      },
    }
  } catch (e) {
    // 没登录或后端挂了 → 用 mock，不让页面崩
    console.warn('[fetchCurrentUser] 降级到 mock:', e.message)
    await delay(100)
    return M.currentUser
  }
}

/* ======================================================
 * 以下接口后端暂未实现 — 走 mock，带降级
 * 后端实现后只需把 try 块换成真实调用
 * ====================================================== */

// 个人 / 学习
export async function fetchOrders()       { await delay(); return M.orders }
export async function fetchWeekProgress() { await delay(); return M.weekProgress }
export async function fetchMistakeDist()  { await delay(); return M.mistakeDist }
export async function fetchHeatmap30()    { await delay(); return M.heatmap30 }

// 后台
export async function fetchAdminStats() {
  // TODO: 实现 /api/admin/stats 后改这里
  await delay()
  return M.stats
}
export async function fetchTrend14d()     { await delay(); return M.trend14d }
export async function fetchActivities()   { await delay(); return M.activities }
export async function fetchProvinces()    { await delay(); return M.provinces }
export async function fetchRecentPapers() { await delay(); return M.recentPapers }

/**
 * 后台用户列表 — 优先真接口，失败降级 mock
 * 后端用 /api/auth/me 已经能拿到 admin role；用户列表暂无接口，先 mock
 */
export async function fetchAdminUsers() {
  await delay()
  return M.adminUsers
}

// 题目 / 报告
export async function fetchQuestion(id) {
  await delay()
  return { ...M.sampleQuestion, id: id || M.sampleQuestion.id }
}
export async function fetchScoreReport(id) {
  await delay()
  return { ...M.scoreReport, id: id || M.scoreReport.id }
}

// 营销 / 套餐
export async function fetchPlans()      { await delay(); return M.plans }
export async function fetchPricingFAQ() { await delay(); return M.pricingFAQ }

/* ======================================================
 * 默认导出
 * ====================================================== */
export default {
  authApi,
  chatApi,
  practiceApi,
  paperApi,
  pdfApi,
  getToken,
  setToken,
  fetchCurrentUser,
}