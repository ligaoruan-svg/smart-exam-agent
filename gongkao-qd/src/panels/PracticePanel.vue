<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from '../components/Card.vue'
import GkInput from '../components/GkInput.vue'
import GkSelect from '../components/GkSelect.vue'
import Button from '../components/Button.vue'
import { practiceApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/* ============================================================
 * 模式：
 *   'setup'      显示出题表单
 *   'loading'    出题中
 *   'answering'  做题中
 *   'review'     已提交，展示结算
 * ============================================================ */
const phase = ref('setup')
const errorMsg = ref('')
const autoJump = ref(true)

/* ============================================================
 * 表单
 * ============================================================ */
const count = ref(20)
const type = ref('混合')
const province = ref('全部')
const typeOpts = ['混合', '言语理解', '数量关系', '判断推理', '资料分析', '常识判断']
const provinceOpts = [
  '全部', '国考',
  '北京', '上海', '天津', '重庆',
  '广东', '江苏', '浙江', '山东', '福建', '安徽', '江西',
  '河南', '湖北', '湖南', '河北', '山西', '内蒙古',
  '四川', '贵州', '云南', '西藏',
  '陕西', '甘肃', '青海', '宁夏', '新疆',
  '广西', '海南', '辽宁', '吉林', '黑龙江'
]

/* ============================================================
 * Session 数据
 * ============================================================ */
const session = ref(null)
const questions = ref([])
const userAnswers = ref({})
const startTimes = ref({})
const submitting = ref(false)
const pendingHint = ref(null)
const autoJumpTimeout = ref(null)

const currentIndex = ref(0)
const reviewMode = ref(false)

// 题目反馈
const showFeedback = ref(false)
const feedbackType = ref('')
const feedbackNote = ref('')
const feedbackSubmitting = ref(false)
const feedbackDone = ref(false)

// AI 深度解析
const aiAnalysis = ref({})
const aiLoading = ref({})

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8900'

/* ============================================================
 * 持久化存储 Key
 * ============================================================ */
const STORAGE_KEY = 'gk_practice_state'

function savePracticeState() {
  if (phase.value !== 'answering' || !session.value) return

  const state = {
    sessionId: session.value.id,
    currentIndex: currentIndex.value,
    userAnswers: userAnswers.value,
    startTimes: startTimes.value,
    questions: questions.value,
    session: session.value,
    phase: phase.value,
    reviewMode: reviewMode.value,
    savedAt: Date.now()
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

async function restorePracticeState() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (!saved) return false

  try {
    const state = JSON.parse(saved)
    if (Date.now() - state.savedAt > 24 * 60 * 60 * 1000) {
      localStorage.removeItem(STORAGE_KEY)
      return false
    }

    try {
      const check = await practiceApi.getSession(state.sessionId)
      if (check && check.status === 'active') {
        session.value = state.session
        questions.value = state.questions
        userAnswers.value = state.userAnswers
        startTimes.value = state.startTimes
        currentIndex.value = state.currentIndex
        phase.value = state.phase
        reviewMode.value = state.reviewMode
        router.replace({ path: '/practice', query: { session: state.sessionId } })
        return true
      }
    } catch (e) {
      console.warn('恢复的 session 已失效', e)
    }
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    console.error('恢复状态失败', e)
  }
  return false
}

function clearPracticeState() {
  localStorage.removeItem(STORAGE_KEY)
}

/* ============================================================
 * 初始化
 * ============================================================ */
onMounted(async () => {
  const sid = route.query.session
  const restored = await restorePracticeState()
  if (restored) return

  if (sid) {
    await launchFromSession(sid)
  } else {
    await checkPending()
  }
})

window.addEventListener('beforeunload', () => {
  if (phase.value === 'answering') {
    savePracticeState()
  }
})

onBeforeUnmount(() => {
  if (autoJumpTimeout.value) clearTimeout(autoJumpTimeout.value)
})

watch(() => route.query.session, async (sid) => {
  if (sid && sid !== session.value?.id) {
    clearPracticeState()
    await launchFromSession(sid)
  } else if (!sid && phase.value !== 'setup') {
    resetToSetup()
  }
})

async function checkPending() {
  try {
    const r = await practiceApi.getPending()
    if (r.has_pending) pendingHint.value = r.session
  } catch {}
}

async function launchFromSession(sid) {
  phase.value = 'loading'
  errorMsg.value = ''
  try {
    const r = await practiceApi.start(sid)
    finalizeSessionStart(sid, r)
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || '加载失败'
    phase.value = 'setup'
  }
}

async function startManualPractice() {
  errorMsg.value = ''
  phase.value = 'loading'
  try {
    const payload = {
      count: Number(count.value) || 20,
      question_type: type.value === '混合' ? null : type.value,
      province: province.value === '全部' ? null : province.value,
    }
    const r = await practiceApi.quickStart(payload)
    finalizeSessionStart(r.session_id, r)
    auth.fetchMe()
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || '出题失败'
    phase.value = 'setup'
  }
}

function finalizeSessionStart(sid, r) {
  session.value = { id: sid, status: r.status, total_count: r.total_count }
  questions.value = r.questions || []
  userAnswers.value = {}
  currentIndex.value = 0
  reviewMode.value = false
  for (const q of questions.value) {
    startTimes.value[q.id] = Date.now()
  }
  phase.value = questions.value.length > 0 ? 'answering' : 'setup'
  if (route.query.session !== sid) {
    router.replace({ path: '/practice', query: { session: sid } })
  }
  savePracticeState()
}

function startPending() {
  if (pendingHint.value) {
    router.push(`/practice?session=${pendingHint.value.id}`)
  }
}

function resetToSetup() {
  phase.value = 'setup'
  session.value = null
  questions.value = []
  userAnswers.value = {}
  currentIndex.value = 0
  reviewMode.value = false
  errorMsg.value = ''
  if (autoJumpTimeout.value) clearTimeout(autoJumpTimeout.value)
  clearPracticeState()
  checkPending()
}

/* ============================================================
 * 答题
 * ============================================================ */
async function clickOption(q, letter) {
  if (reviewMode.value) return
  if (userAnswers.value[q.id]) return
  if (submitting.value) return

  submitting.value = true
  const timeSpent = Math.floor((Date.now() - (startTimes.value[q.id] || Date.now())) / 1000)

  try {
    const r = await practiceApi.submitAnswer(session.value.id, q.id, letter, timeSpent)
    userAnswers.value[q.id] = {
      answer: letter,
      is_correct: r.is_correct,
      correct_answer: r.correct_answer,
      time_spent: timeSpent,
    }
    savePracticeState()

    if (autoJump.value && r.is_correct && currentIndex.value < questions.value.length - 1) {
      autoJumpTimeout.value = setTimeout(() => {
        goTo(currentIndex.value + 1)
        autoJumpTimeout.value = null
      }, 400)
    }
  } catch (e) {
    alert('提交失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

function goTo(idx) {
  if (autoJumpTimeout.value) {
    clearTimeout(autoJumpTimeout.value)
    autoJumpTimeout.value = null
  }
  if (idx < 0 || idx >= questions.value.length) return
  currentIndex.value = idx
  savePracticeState()
  const q = questions.value[idx]
  if (q && !userAnswers.value[q.id]) {
    startTimes.value[q.id] = Date.now()
  }
}

/* ============================================================
 * 提交 / 退出
 * ============================================================ */
async function submitPractice() {
  if (!session.value) return
  const remain = totalCount.value - answeredCount.value
  if (remain > 0) {
    if (!confirm(`还有 ${remain} 道题没做，确定要提交吗？\n\n未做的题会标记为"未答"。`)) return
  }
  try {
    await practiceApi.finish(session.value.id)
    reviewMode.value = true
    phase.value = 'review'
    auth.fetchMe()
    clearPracticeState()
  } catch (e) {
    alert('提交失败：' + (e.response?.data?.detail || e.message))
  }
}

async function exitPractice() {
  if (!confirm('确定退出本次练习？\n\n退出后进度将被清空，下次需要重新开始。')) return
  try {
    if (session.value) await practiceApi.cancel(session.value.id)
  } catch {}
  clearPracticeState()
  router.replace({ path: '/practice' })
  resetToSetup()
}

function newPractice() {
  router.replace({ path: '/practice' })
  resetToSetup()
}

/* ============================================================
 * 当前题
 * ============================================================ */
const currentQuestion = computed(() => questions.value[currentIndex.value] || null)
const isAnswered = (q) => !!userAnswers.value[q?.id]
const correctAnswer = (q) => userAnswers.value[q?.id]?.correct_answer || q?.answer

function optionStyle(q, key) {
  const ans = userAnswers.value[q.id]
  const answered = !!ans
  const isRight = answered && key === correctAnswer(q)
  const isSel = answered && ans.answer === key

  let bg = '#ffffff'
  let bd = '#e5e7eb'
  let col = '#374151'
  let icon = null

  if (answered) {
    if (isRight) {
      bg = '#f0fdf4'
      bd = '#86efac'
      col = '#166534'
      icon = '✓'
    } else if (isSel) {
      bg = '#fef2f2'
      bd = '#fca5a5'
      col = '#991b1b'
      icon = '✗'
    }
  }

  return { style: { background: bg, border: `1.5px solid ${bd}`, color: col }, icon, answered }
}

// ===== 题目反馈 =====
async function submitFeedback() {
  if (!feedbackType.value) return
  feedbackSubmitting.value = true
  try {
    const token = localStorage.getItem('gk_token') || ''
    await fetch(`${API_BASE}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({
        question_id: currentQuestion.value?.id,
        feedback_type: feedbackType.value,
        description: feedbackNote.value || feedbackType.value,
      }),
    })
    feedbackDone.value = true
    setTimeout(() => {
      showFeedback.value = false
      feedbackDone.value = false
      feedbackType.value = ''
      feedbackNote.value = ''
    }, 1500)
  } catch(e) {
    console.error(e)
  } finally { feedbackSubmitting.value = false }
}

// ===== AI 深度解析 =====
async function loadAiAnalysis(q) {
  const qid = q.id
  if (aiAnalysis.value[qid] || aiLoading.value[qid]) return
  aiLoading.value[qid] = true
  try {
    const token = localStorage.getItem('gk_token') || ''
    // 第1步：先查该题目对应的错题本 wrong_id
    const listResp = await fetch(`${API_BASE}/api/mistake/list?page_size=200`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    const listData = await listResp.json()
    const wrongItem = (listData.items || []).find(item => item.question_id === qid)

    if (!wrongItem) {
      aiAnalysis.value[qid] = '⚠️ 该题暂无错题记录，请先答错一次再使用 AI 解析'
      return
    }

    // 第2步：用 wrong_id 调 POST 接口
    const resp = await fetch(`${API_BASE}/api/mistake/${wrongItem.id}/ai-explain`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    })
    const data = await resp.json()
    if (resp.ok) aiAnalysis.value[qid] = data.analysis || '（AI 解析生成失败）'
    else aiAnalysis.value[qid] = '⚠️ ' + (data.detail || '生成失败，请稍后重试')
  } catch(e) {
    aiAnalysis.value[qid] = '（网络错误，请稍后重试）'
  } finally { aiLoading.value[qid] = false }
}

function gridStateOf(q, idx) {
  const ans = userAnswers.value[q.id]
  const isCurrent = idx === currentIndex.value
  if (reviewMode.value) {
    if (!ans) return 'unansweredReview'
    return ans.is_correct ? 'correct' : 'wrong'
  }
  if (isCurrent) return 'current'
  if (ans) return 'answered'
  return 'unanswered'
}

/* ============================================================
 * 右侧统计
 * ============================================================ */
const answeredCount = computed(() => Object.keys(userAnswers.value).length)
const correctCount  = computed(() => Object.values(userAnswers.value).filter(a => a.is_correct).length)
const wrongCount    = computed(() => answeredCount.value - correctCount.value)
const totalCount    = computed(() => questions.value.length)
const correctRate   = computed(() => {
  if (answeredCount.value === 0) return '0%'
  return Math.round(correctCount.value / answeredCount.value * 100) + '%'
})
const avgTime = computed(() => {
  const items = Object.values(userAnswers.value)
  if (items.length === 0) return '0s'
  const total = items.reduce((s, a) => s + (a.time_spent || 0), 0)
  return Math.round(total / items.length) + 's'
})

const progressPercent = computed(() => (currentIndex.value / totalCount.value) * 100)
</script>

<template>
  <div class="practice-container">
    <!-- ============== 模式 1: 出题表单 ============== -->
    <div v-if="phase === 'setup'" class="setup-wrapper">
      <Card class="setup-card">
        <div class="setup-content">
          <div class="setup-header">
            <h2>🎲 随机练习</h2>
            <p>直接从题库随机抽题，每道题都带解析和真题来源</p>
          </div>

          <div v-if="pendingHint" class="pending-banner">
            <span>💡 你还有一份未开始的练习：{{ pendingHint.preset_question_count || pendingHint.total_count }} 道</span>
            <Button size="sm" @click="startPending">继续上次</Button>
          </div>

          <div class="setup-form">
            <div class="form-field">
              <label>📝 题数</label>
              <GkInput v-model="count" type="number" min="1" max="200" />
            </div>
            <div class="form-field">
              <label>📚 题型</label>
              <GkSelect v-model="type" :options="typeOpts" />
            </div>
            <div class="form-field">
              <label>📍 省份</label>
              <GkSelect v-model="province" :options="provinceOpts" />
            </div>
            <Button variant="primary" class="start-btn" @click="startManualPractice">▶ 开始出题</Button>
          </div>

          <div class="setup-tip">💡 也可以通过左上角「AI 对话」让 AI 智能出题</div>
          <div v-if="errorMsg" class="error-msg">⚠️ {{ errorMsg }}</div>
        </div>
      </Card>
    </div>

    <!-- ============== 模式 2: 加载中 ============== -->
    <div v-else-if="phase === 'loading'" class="loading-wrapper">
      <Card class="loading-card">
        <div class="loading-content">
          <div class="loading-spinner"></div>
          <div>正在准备题目…</div>
        </div>
      </Card>
    </div>

    <!-- ============== 模式 3 & 4: 答题 / 查看 ============== -->
    <div v-else class="practice-layout">
      <!-- 左侧题目区 -->
      <div class="question-area">
        <Card class="question-card">
          <div v-if="currentQuestion" class="question-inner">
            <!-- 头部 -->
            <div class="question-header">
              <div class="question-meta">
                <span class="q-num">第 {{ currentIndex + 1 }} 题</span>
                <span class="q-total">/ {{ totalCount }}</span>
                <span v-if="currentQuestion.question_type" class="badge type">{{ currentQuestion.question_type }}</span>
                <span v-if="currentQuestion.province" class="badge province">{{ currentQuestion.province }} {{ currentQuestion.year }}</span>
              </div>
              <div class="header-right">
                <button class="feedback-trigger" @click="showFeedback = true; feedbackDone = false" title="题目有问题？点击反馈">
                  ⚑ 反馈问题
                </button>
              </div>
            </div>

            <!-- 进度条 -->
            <div class="progress-bar"><div class="progress-fill" :style="{ width: progressPercent + '%' }"></div></div>

            <!-- 题干 -->
            <div class="stem">{{ currentQuestion.stem }}</div>

            <!-- 选项 -->
            <div class="options">
              <div v-for="key in ['A','B','C','D']" :key="key" class="option" :style="optionStyle(currentQuestion, key).style" @click="clickOption(currentQuestion, key)">
                <span><b>{{ key }}.</b> {{ currentQuestion.options[key] }}</span>
                <span v-if="optionStyle(currentQuestion, key).icon" class="option-icon">{{ optionStyle(currentQuestion, key).icon }}</span>
              </div>
            </div>

            <!-- 解析 -->
            <div v-if="isAnswered(currentQuestion) || reviewMode" class="analysis">
              <div class="analysis-title">📖 解析（正确答案：<b class="correct-ans">{{ correctAnswer(currentQuestion) }}</b>）</div>
              <div class="analysis-text">{{ currentQuestion.analysis || '（暂无解析）' }}</div>
            </div>

            <!-- AI 深度解析 -->
            <div v-if="isAnswered(currentQuestion) || reviewMode" class="ai-analysis-section">
              <button class="ai-btn" @click="loadAiAnalysis(currentQuestion)" :disabled="aiLoading[currentQuestion.id]">
                <span v-if="aiLoading[currentQuestion.id]">⏳ AI 解析生成中...</span>
                <span v-else-if="aiAnalysis[currentQuestion.id]">✨ 已生成 AI 深度解析</span>
                <span v-else>✨ AI 深度解析</span>
              </button>
              <div v-if="aiAnalysis[currentQuestion.id]" class="ai-content">{{ aiAnalysis[currentQuestion.id] }}</div>
            </div>



            <!-- 翻页 -->
            <div class="nav-buttons">
              <Button size="sm" variant="ghost" :disabled="currentIndex === 0" @click="goTo(currentIndex - 1)">← 上一题</Button>
              <Button size="sm" variant="ghost" :disabled="currentIndex === totalCount - 1" @click="goTo(currentIndex + 1)">下一题 →</Button>
            </div>
          </div>
        </Card>
      </div>

      <!-- 右侧统计区 -->
      <div class="stats-area">
        <Card class="stats-card">
          <div class="stats-title">📊 本次数据</div>
          <div class="stats-grid">
            <div class="stat"><span>已答</span><b>{{ answeredCount }}/{{ totalCount }}</b></div>
            <div class="stat"><span>正确率</span><b class="green">{{ correctRate }}</b></div>
            <div class="stat"><span>平均用时</span><b>{{ avgTime }}</b></div>
            <div class="stat"><span>错题</span><b class="red">{{ wrongCount }}</b></div>
          </div>
        </Card>

        <Card class="nav-card">
          <div class="stats-title">📌 题目导航</div>
          <div class="grid">
            <button v-for="(q, idx) in questions" :key="q.id" :class="['grid-btn', gridStateOf(q, idx)]" @click="goTo(idx)">{{ idx + 1 }}</button>
          </div>
          <div class="legend">
            <template v-if="!reviewMode">
              <span><i class="dot current"></i>当前</span>
              <span><i class="dot answered"></i>已答</span>
              <span><i class="dot unanswered"></i>未答</span>
            </template>
            <template v-else>
              <span><i class="dot correct"></i>答对</span>
              <span><i class="dot wrong"></i>答错</span>
              <span><i class="dot unansweredReview"></i>未做</span>
            </template>
          </div>
        </Card>

        <!-- 底部按钮组 -->
        <div class="action-buttons">
          <Button v-if="!reviewMode" variant="primary" class="submit-btn" @click="submitPractice">
            提交（{{ answeredCount }}/{{ totalCount }}）
          </Button>
          <template v-else>
            <Button variant="primary" @click="newPractice">再来一组 ↻</Button>
            <Button variant="ghost" @click="exitPractice">退出练习</Button>
          </template>
        </div>
      </div>
    </div>

  <!-- 题目反馈弹窗（全屏遮罩） -->
  <div v-if="showFeedback" class="feedback-mask" @click.self="showFeedback = false">
      <div class="feedback-modal">
        <div class="feedback-header">
          <div class="feedback-title">
            <span class="feedback-icon">⚑</span>
            <span>反馈题目问题</span>
          </div>
          <button class="feedback-close" @click="showFeedback = false">✕</button>
        </div>

        <div v-if="feedbackDone" class="feedback-success">
          <div class="success-icon">✅</div>
          <div class="success-text">反馈已提交，感谢你的帮助！</div>
          <div class="success-sub">我们会尽快核实并处理</div>
        </div>

        <template v-else>


          <div class="feedback-label">问题类型 <span class="required">*</span></div>
          <div class="feedback-options">
            <div v-for="opt in [
              {val:'answer_wrong',      label:'✗ 答案有误',   desc:'正确答案标注错误'},
              {val:'stem_incomplete',   label:'✎ 题干缺失',   desc:'题目文字不完整'},
              {val:'option_error',      label:'⊙ 选项有误',   desc:'选项内容错误或缺失'},
              {val:'analysis_error',    label:'📖 解析有误',   desc:'解析内容存在错误'},
              {val:'other',             label:'… 其他问题',   desc:'其他需要反馈的问题'},
            ]" :key="opt.val"
              class="feedback-option"
              :class="{active: feedbackType === opt.val}"
              @click="feedbackType = opt.val">
              <div class="opt-label">{{ opt.label }}</div>
              <div class="opt-desc">{{ opt.desc }}</div>
            </div>
          </div>

          <div class="feedback-label">补充说明</div>
          <textarea v-model="feedbackNote" class="feedback-note" placeholder="请描述具体问题，方便我们快速定位修复..." rows="3" />

          <div class="feedback-actions">
            <button class="feedback-cancel" @click="showFeedback = false">取消</button>
            <button class="feedback-submit" :disabled="!feedbackType || feedbackSubmitting" @click="submitFeedback">
              <span v-if="feedbackSubmitting">提交中...</span>
              <span v-else>提交反馈</span>
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.practice-container {
  min-height: calc(100vh - 64px);
  background: linear-gradient(135deg, #f5f7fa 0%, #eef2f6 100%);
  padding: 24px;
}

/* 出题表单 */
.setup-wrapper { display: flex; justify-content: center; align-items: center; min-height: 60vh; }
.setup-card { width: 100%; max-width: 640px; border-radius: 28px; box-shadow: 0 20px 35px -12px rgba(0,0,0,0.1); }
.setup-content { padding: 28px 24px; }
.setup-header { text-align: center; margin-bottom: 28px; }
.setup-header h2 { margin: 0 0 8px; font-size: 28px; background: linear-gradient(135deg, #1e293b, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.setup-header p { color: #64748b; margin: 0; font-size: 14px; }
.pending-banner { background: #fffbeb; border: 1px solid #fde68a; border-radius: 16px; padding: 12px 16px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.setup-form { display: grid; grid-template-columns: repeat(3, 1fr) auto; gap: 16px; margin-bottom: 20px; }
.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label { font-size: 12px; font-weight: 500; color: #64748b; }
.start-btn { height: 42px; font-weight: 600; padding: 0 24px; }
.setup-tip { color: #94a3b8; font-size: 12px; text-align: center; margin-top: 16px; }
.error-msg { margin-top: 20px; padding: 12px 16px; background: #fef2f2; color: #dc2626; border-radius: 14px; font-size: 13px; }

/* 加载 */
.loading-wrapper { display: flex; justify-content: center; align-items: center; min-height: 60vh; }
.loading-card { border-radius: 28px; }
.loading-content { padding: 60px 40px; text-align: center; color: #64748b; }
.loading-spinner { width: 48px; height: 48px; border: 3px solid #e2e8f0; border-top-color: #3b82f6; border-radius: 50%; margin: 0 auto 20px; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 双栏布局 */
.practice-layout { max-width: 1400px; margin: 0 auto; display: grid; grid-template-columns: 1fr 320px; gap: 24px; align-items: start; }
.question-area { position: sticky; top: 24px; }
.question-card { border-radius: 28px; box-shadow: 0 8px 30px rgba(0,0,0,0.08); overflow: hidden; }
.question-inner { padding: 28px; }

/* 头部 */
.question-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.question-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.q-num { font-size: 22px; font-weight: 700; color: #0f172a; }
.q-total { color: #94a3b8; font-size: 14px; }
.badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 500; }
.badge.type { background: #eff6ff; color: #1d4ed8; }
.badge.province { background: #f1f5f9; color: #475569; }
.header-right { display: flex; align-items: center; gap: 16px; }

.switch { position: relative; display: inline-block; width: 40px; height: 20px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: 0.2s; border-radius: 20px; }
.slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 2px; bottom: 2px; background-color: white; transition: 0.2s; border-radius: 50%; }
input:checked + .slider { background-color: #3b82f6; }
input:checked + .slider:before { transform: translateX(20px); }

/* 进度条 */
.progress-bar { background: #f1f5f9; border-radius: 10px; height: 6px; margin-bottom: 24px; overflow: hidden; }
.progress-fill { background: linear-gradient(90deg, #3b82f6, #8b5cf6); height: 100%; transition: width 0.3s; border-radius: 10px; }

/* 题干 */
.stem { font-size: 16px; line-height: 1.7; color: #1e293b; background: #f8fafc; padding: 20px; border-radius: 20px; margin-bottom: 24px; white-space: pre-wrap; }

/* 选项 */
.options { display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; }
.option { padding: 14px 18px; border-radius: 14px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s; font-size: 14px; }
.option:active { transform: scale(0.98); }
.option-icon { font-size: 18px; font-weight: 600; }

/* 解析 */
.analysis { margin-top: 24px; padding: 18px 20px; background: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 16px; }
.analysis-title { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.correct-ans { color: #16a34a; }
.analysis-text { font-size: 13px; line-height: 1.6; color: #334155; white-space: pre-wrap; }

/* 翻页 */
.nav-buttons { display: flex; gap: 12px; justify-content: space-between; margin-top: 24px; padding-top: 20px; border-top: 1px solid #e2e8f0; }

/* 右侧 */
.stats-area { display: flex; flex-direction: column; gap: 20px; }
.stats-card, .nav-card { border-radius: 20px; padding: 18px 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
.stats-title { font-weight: 600; font-size: 14px; color: #1e293b; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0; margin-bottom: 14px; }
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.stat { display: flex; justify-content: space-between; font-size: 13px; color: #64748b; }
.stat b { color: #1e293b; font-size: 16px; }
.stat .green { color: #16a34a; }
.stat .red { color: #dc2626; }

/* 题号网格 */
.grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 18px; }
.grid-btn { padding: 10px 0; border-radius: 12px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; transition: all 0.15s; background: white; }
.grid-btn.unanswered { background: #f9fafb; color: #9ca3af; border: 1.5px solid #f1f5f9; }
.grid-btn.current { background: #eef2ff; color: #4338ca; border: 2px solid #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,0.2); }
.grid-btn.answered { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.grid-btn.correct { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.grid-btn.wrong { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
.grid-btn.unansweredReview { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
.grid-btn:hover { transform: scale(1.02); }

.legend { display: flex; gap: 16px; font-size: 11px; color: #64748b; padding-top: 12px; border-top: 1px solid #f1f5f9; }
.legend .dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: middle; }
.dot.current { background: #eef2ff; border: 2px solid #6366f1; }
.dot.answered { background: #dcfce7; border: 1px solid #86efac; }
.dot.unanswered { background: #f9fafb; border: 1.5px solid #e2e8f0; }
.dot.correct { background: #dcfce7; border: 1px solid #86efac; }
.dot.wrong { background: #fee2e2; border: 1px solid #fca5a5; }
.dot.unansweredReview { background: #fffbeb; border: 1px solid #fde68a; }

/* 底部按钮组 */
.action-buttons { display: flex; gap: 12px; }
.submit-btn, .action-buttons button { flex: 1; padding: 14px 0; font-weight: 600; font-size: 15px; border-radius: 24px; }
.action-buttons button:last-child { flex: 0.5; }

/* 反馈触发按钮 */
.feedback-trigger { background: none; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 12px; font-size: 12px; color: #94a3b8; cursor: pointer; font-family: inherit; transition: all .15s; }
.feedback-trigger:hover { border-color: #f59e0b; color: #d97706; background: #fffbeb; }

/* 反馈弹窗遮罩 */
.feedback-mask { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.5); z-index: 9999; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(2px); animation: maskIn .2s ease; }
@keyframes maskIn { from { opacity:0; } to { opacity:1; } }

.feedback-modal { background: #fff; border-radius: 20px; padding: 28px; width: 460px; max-width: 92vw; max-height: 90vh; overflow-y: auto; box-shadow: 0 24px 80px rgba(0,0,0,.25); animation: modalIn .25s cubic-bezier(.22,1,.36,1); }
@keyframes modalIn { from { opacity:0; transform:translateY(16px) scale(.97); } to { opacity:1; transform:none; } }

.feedback-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.feedback-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 700; color: #0f172a; }
.feedback-icon { font-size: 18px; }
.feedback-close { background: #f1f5f9; border: none; width: 30px; height: 30px; border-radius: 8px; font-size: 14px; cursor: pointer; color: #64748b; display: flex; align-items: center; justify-content: center; transition: background .15s; }
.feedback-close:hover { background: #e2e8f0; color: #0f172a; }

.feedback-q-info { font-size: 12px; color: #94a3b8; margin-bottom: 20px; padding: 8px 12px; background: #f8fafc; border-radius: 8px; }

.feedback-label { font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 10px; }
.required { color: #ef4444; margin-left: 2px; }

.feedback-options { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 20px; }
.feedback-option { padding: 12px 14px; border: 1.5px solid #e2e8f0; border-radius: 12px; cursor: pointer; transition: all .15s; user-select: none; }
.feedback-option:hover { border-color: #93c5fd; background: #f0f9ff; }
.feedback-option.active { border-color: #3b82f6; background: #eff6ff; }
.opt-label { font-size: 13px; font-weight: 500; color: #1e293b; margin-bottom: 2px; }
.feedback-option.active .opt-label { color: #2563eb; }
.opt-desc { font-size: 11px; color: #94a3b8; }

.feedback-note { width: 100%; box-sizing: border-box; border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; font-size: 13px; font-family: inherit; resize: none; outline: none; margin-bottom: 20px; color: #374151; transition: border-color .15s; }
.feedback-note:focus { border-color: #3b82f6; }

.feedback-actions { display: flex; gap: 10px; }
.feedback-cancel { flex: 1; padding: 11px; background: #f1f5f9; color: #64748b; border: none; border-radius: 10px; font-size: 14px; font-weight: 500; font-family: inherit; cursor: pointer; transition: background .15s; }
.feedback-cancel:hover { background: #e2e8f0; }
.feedback-submit { flex: 2; padding: 11px; background: #3b82f6; color: #fff; border: none; border-radius: 10px; font-size: 14px; font-weight: 600; font-family: inherit; cursor: pointer; transition: background .15s; }
.feedback-submit:hover:not(:disabled) { background: #2563eb; }
.feedback-submit:disabled { background: #cbd5e1; color: #94a3b8; cursor: not-allowed; }

/* 成功状态 */
.feedback-success { text-align: center; padding: 32px 20px; }
.success-icon { font-size: 48px; margin-bottom: 12px; }
.success-text { font-size: 16px; font-weight: 600; color: #059669; margin-bottom: 6px; }
.success-sub { font-size: 13px; color: #94a3b8; }

/* AI 深度解析 */
.ai-analysis-section { margin-top: 16px; border-top: 1px solid #f1f5f9; padding-top: 16px; }
.ai-btn { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; border: none; border-radius: 10px; padding: 10px 20px; font-size: 13px; font-weight: 500; font-family: inherit; cursor: pointer; transition: opacity .15s; }
.ai-btn:hover:not(:disabled) { opacity: .9; }
.ai-btn:disabled { opacity: .6; cursor: not-allowed; }
.ai-content { margin-top: 12px; padding: 16px; background: #f8f7ff; border-radius: 10px; font-size: 14px; color: #374151; line-height: 1.7; white-space: pre-wrap; border: 1px solid #e0e7ff; }
</style>