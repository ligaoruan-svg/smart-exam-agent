<template>
  <div class="login-page">
    <canvas ref="canvas" class="bg-canvas" />
    <div class="overlay" />

    <div class="card">
      <!-- 左侧 -->
      <div class="left">
        <div class="brand">
          <div class="brand-mark">智</div>
          <span class="brand-name">公考小智</span>
        </div>
        <div class="floats">
          <div class="circle c1">📚</div>
          <div class="circle c2" />
          <div class="circle c3" />
          <div class="circle c4" />
        </div>
        <div class="left-bottom">
          <div class="tagline">你的公考智慧搭子 🌱</div>
          <div class="chips">
            <span class="chip">📁 2,579 份真题</span>
            <span class="chip">🗺 32 个省份</span>
            <span class="chip">✨ AI 出题</span>
          </div>
        </div>
      </div>

      <!-- 右侧 -->
      <div class="right">

        <!-- ====== 登录 ====== -->
        <template v-if="mode === 'login'">
          <h1 class="title">欢迎回来 👋</h1>
          <p class="sub">登录后开始备考</p>
          <div class="tabs">
            <button class="tab active">登录</button>
            <button class="tab" @click="switchMode('register')">注册</button>
          </div>
          <form @submit.prevent="doLogin" class="form">
            <div class="field">
              <label>用户名</label>
              <input v-model="form.username" type="text" placeholder="用户名 或 邮箱" autocomplete="username" />
            </div>
            <div class="field">
              <label>密码</label>
              <div class="pw-wrap">
                <input v-model="form.password" :type="showPw ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password" />
                <span class="eye" @click="showPw = !showPw">{{ showPw ? '🙈' : '👁' }}</span>
              </div>
            </div>
            <div class="forgot-link">
              <span @click="switchMode('forgot')">忘记密码？</span>
            </div>
            <button type="submit" class="submit-btn" :disabled="loading || !form.username || !form.password">
              <span v-if="loading" class="spinner" />
              {{ loading ? '登录中...' : '登录' }}
            </button>
          </form>
        </template>

        <!-- ====== 注册 - 分步式 ====== -->
        <template v-else-if="mode === 'register'">
          <h1 class="title">创建账号 ✨</h1>
          <p class="sub">加入公考小智，开始备考之旅</p>
          <div class="tabs">
            <button class="tab" @click="switchMode('login')">登录</button>
            <button class="tab active">注册</button>
          </div>

          <!-- 步骤指示器 -->
          <div class="steps">
            <div v-for="n in 3" :key="n" class="step-item">
              <div :class="['step-dot', { done: regStep > n, active: regStep === n }]">
                <span v-if="regStep > n">✓</span>
                <span v-else>{{ n }}</span>
              </div>
              <div v-if="n < 3" :class="['step-line', { done: regStep > n }]"></div>
            </div>
          </div>
          <p class="step-hint">
            {{ regStep === 1 ? '第 1 步：验证邮箱' : regStep === 2 ? '第 2 步：输入验证码' : '第 3 步：设置账号' }}
          </p>

          <!-- 第1步：填邮箱 -->
          <div v-if="regStep === 1" class="form">
            <div class="field">
              <label>邮箱地址</label>
              <input v-model="form.email" type="email" placeholder="请输入常用邮箱" autocomplete="email" />
            </div>
            <p class="field-hint">验证码将发送至此邮箱，请确保地址正确</p>
            <button class="submit-btn" :disabled="loading || !form.email" @click="doSendCode">
              <span v-if="loading" class="spinner" />
              {{ loading ? '发送中...' : '发送验证码 →' }}
            </button>
          </div>

          <!-- 第2步：输入验证码 -->
          <div v-else-if="regStep === 2" class="form">
            <div class="field">
              <label>验证码 <em>已发送至 {{ form.email }}</em></label>
              <div class="otp-wrap">
                <input
                  v-for="(_, i) in 6" :key="i"
                  :ref="el => otpInputs[i] = el"
                  v-model="otpDigits[i]"
                  type="text" maxlength="1" inputmode="numeric"
                  class="otp-input"
                  @input="onOtpInput(i, $event)"
                  @keydown="onOtpKeydown(i, $event)"
                  @paste="onOtpPaste($event)"
                />
              </div>
            </div>
            <div class="resend-row">
              <span v-if="codeCooldown > 0" class="resend-hint">{{ codeCooldown }}s 后可重新发送</span>
              <span v-else class="resend-link" @click="doSendCode">重新发送</span>
            </div>
            <button class="submit-btn" :disabled="otpDigits.join('').length < 6" @click="regStep = 3">
              下一步 →
            </button>
            <button class="back-btn" @click="regStep = 1">← 修改邮箱</button>
          </div>

          <!-- 第3步：设置账号 -->
          <div v-else-if="regStep === 3" class="form">
            <div class="field">
              <label>用户名 <em>（3-20位字母/数字/下划线）</em></label>
              <input v-model="form.username" type="text" placeholder="设置你的用户名" autocomplete="username" />
            </div>
            <div class="row-fields">
              <div class="field" style="flex:1">
                <label>密码 <em>（至少6位）</em></label>
                <div class="pw-wrap">
                  <input v-model="form.password" :type="showPw ? 'text' : 'password'" placeholder="设置密码" autocomplete="new-password" />
                  <span class="eye" @click="showPw = !showPw">{{ showPw ? '🙈' : '👁' }}</span>
                </div>
              </div>
              <div class="field" style="flex:1">
                <label>确认密码</label>
                <input v-model="form.password2" type="password" placeholder="再输一次" autocomplete="new-password" />
              </div>
            </div>
            <button class="submit-btn" :disabled="loading" @click="doRegister">
              <span v-if="loading" class="spinner" />
              {{ loading ? '注册中...' : '完成注册 🎉' }}
            </button>
            <button class="back-btn" @click="regStep = 2">← 返回上一步</button>
          </div>
        </template>

        <!-- ====== 忘记密码 - 分步式 ====== -->
        <template v-else-if="mode === 'forgot'">
          <h1 class="title">重置密码 🔑</h1>
          <p class="sub">通过邮箱验证重置你的密码</p>
          <div class="tabs">
            <button class="tab" @click="switchMode('login')">← 返回登录</button>
          </div>

          <!-- 步骤指示器 -->
          <div class="steps">
            <div v-for="n in 3" :key="n" class="step-item">
              <div :class="['step-dot', { done: resetStep > n, active: resetStep === n }]">
                <span v-if="resetStep > n">✓</span>
                <span v-else>{{ n }}</span>
              </div>
              <div v-if="n < 3" :class="['step-line', { done: resetStep > n }]"></div>
            </div>
          </div>
          <p class="step-hint">
            {{ resetStep === 1 ? '第 1 步：验证邮箱' : resetStep === 2 ? '第 2 步：输入验证码' : '第 3 步：设置新密码' }}
          </p>

          <!-- 第1步：填邮箱 -->
          <div v-if="resetStep === 1" class="form">
            <div class="field">
              <label>注册邮箱</label>
              <input v-model="resetForm.email" type="email" placeholder="请输入注册时的邮箱" />
            </div>
            <button class="submit-btn" :disabled="loading || !resetForm.email" @click="doSendResetCode">
              <span v-if="loading" class="spinner" />
              {{ loading ? '发送中...' : '发送验证码 →' }}
            </button>
          </div>

          <!-- 第2步：输入验证码 -->
          <div v-else-if="resetStep === 2" class="form">
            <div class="field">
              <label>验证码 <em>已发送至 {{ resetForm.email }}</em></label>
              <div class="otp-wrap">
                <input
                  v-for="(_, i) in 6" :key="i"
                  :ref="el => resetOtpInputs[i] = el"
                  v-model="resetOtpDigits[i]"
                  type="text" maxlength="1" inputmode="numeric"
                  class="otp-input"
                  @input="onResetOtpInput(i, $event)"
                  @keydown="onResetOtpKeydown(i, $event)"
                  @paste="onResetOtpPaste($event)"
                />
              </div>
            </div>
            <div class="resend-row">
              <span v-if="resetCooldown > 0" class="resend-hint">{{ resetCooldown }}s 后可重新发送</span>
              <span v-else class="resend-link" @click="doSendResetCode">重新发送</span>
            </div>
            <button class="submit-btn" :disabled="resetOtpDigits.join('').length < 6" @click="resetStep = 3">
              下一步 →
            </button>
            <button class="back-btn" @click="resetStep = 1">← 修改邮箱</button>
          </div>

          <!-- 第3步：设置新密码 -->
          <div v-else-if="resetStep === 3" class="form">
            <div class="field">
              <label>新密码 <em>（至少6位）</em></label>
              <div class="pw-wrap">
                <input v-model="resetForm.password" :type="showPw ? 'text' : 'password'" placeholder="设置新密码" />
                <span class="eye" @click="showPw = !showPw">{{ showPw ? '🙈' : '👁' }}</span>
              </div>
            </div>
            <div class="field">
              <label>确认新密码</label>
              <input v-model="resetForm.password2" type="password" placeholder="再输一次新密码" />
            </div>
            <button class="submit-btn" :disabled="loading" @click="doResetPassword">
              <span v-if="loading" class="spinner" />
              {{ loading ? '重置中...' : '确认重置 →' }}
            </button>
            <button class="back-btn" @click="resetStep = 2">← 返回上一步</button>
          </div>
        </template>

        <div v-if="errMsg" class="err">{{ errMsg }}</div>
        <div v-if="okMsg" class="ok">{{ okMsg }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8900'

// ===== 全局状态 =====
const mode = ref('login')          // login | register | forgot
const showPw = ref(false)
const loading = ref(false)
const errMsg = ref('')
const okMsg = ref('')

// ===== 注册状态 =====
const regStep = ref(1)
const form = ref({ username: '', password: '', password2: '', email: '' })
const otpDigits = reactive(['', '', '', '', '', ''])
const otpInputs = reactive([])
const codeCooldown = ref(0)
let cooldownTimer = null

// ===== 重置密码状态 =====
const resetStep = ref(1)
const resetForm = ref({ email: '', password: '', password2: '' })
const resetOtpDigits = reactive(['', '', '', '', '', ''])
const resetOtpInputs = reactive([])
const resetCooldown = ref(0)
let resetCooldownTimer = null

function switchMode(m) {
  mode.value = m
  errMsg.value = ''
  okMsg.value = ''
  form.value = { username: '', password: '', password2: '', email: '' }
  regStep.value = 1
  resetStep.value = 1
  showPw.value = false
}

// ===== OTP 输入逻辑（注册）=====
function onOtpInput(i, e) {
  const val = e.target.value.replace(/\D/g, '')
  otpDigits[i] = val ? val[0] : ''
  if (val && i < 5) otpInputs[i + 1]?.focus()
}
function onOtpKeydown(i, e) {
  if (e.key === 'Backspace' && !otpDigits[i] && i > 0) otpInputs[i - 1]?.focus()
}
function onOtpPaste(e) {
  const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
  text.split('').forEach((c, i) => { otpDigits[i] = c })
  otpInputs[Math.min(text.length, 5)]?.focus()
  e.preventDefault()
}

// ===== OTP 输入逻辑（重置）=====
function onResetOtpInput(i, e) {
  const val = e.target.value.replace(/\D/g, '')
  resetOtpDigits[i] = val ? val[0] : ''
  if (val && i < 5) resetOtpInputs[i + 1]?.focus()
}
function onResetOtpKeydown(i, e) {
  if (e.key === 'Backspace' && !resetOtpDigits[i] && i > 0) resetOtpInputs[i - 1]?.focus()
}
function onResetOtpPaste(e) {
  const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
  text.split('').forEach((c, i) => { resetOtpDigits[i] = c })
  resetOtpInputs[Math.min(text.length, 5)]?.focus()
  e.preventDefault()
}

// ===== 倒计时 =====
function startCooldown(target, timerRef) {
  target.value = 60
  const timer = setInterval(() => {
    target.value--
    if (target.value <= 0) clearInterval(timer)
  }, 1000)
  return timer
}

// ===== 注册流程 =====
async function doSendCode() {
  if (!form.value.email) { errMsg.value = '请输入邮箱'; return }
  errMsg.value = ''; loading.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/auth/send-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: form.value.email }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || '发送失败')
    okMsg.value = '✅ 验证码已发送，请查收邮件'
    regStep.value = 2
    cooldownTimer = startCooldown(codeCooldown, cooldownTimer)
    setTimeout(() => otpInputs[0]?.focus(), 100)
  } catch(e) {
    errMsg.value = e.message
  } finally { loading.value = false }
}

async function doRegister() {
  const { username, password, password2, email } = form.value
  if (!username) { errMsg.value = '请填写用户名'; return }
  if (password !== password2) { errMsg.value = '两次密码不一致'; return }
  if (password.length < 6) { errMsg.value = '密码至少6位'; return }
  errMsg.value = ''; loading.value = true
  try {
    await auth.register(username, password, email, otpDigits.join(''))
    okMsg.value = '🎉 注册成功，正在跳转...'
    setTimeout(() => router.push('/chat'), 800)
  } catch(e) {
    errMsg.value = e.response?.data?.detail || e.message || '注册失败'
  } finally { loading.value = false }
}

// ===== 登录 =====
async function doLogin() {
  const { username, password } = form.value
  // 前端先校验，不浪费请求次数
  if (!username) { errMsg.value = '请输入用户名或邮箱'; return }
  if (!password) { errMsg.value = '请输入密码'; return }
  if (password.length < 6) { errMsg.value = '密码至少6位，请检查输入'; return }
  errMsg.value = ''; okMsg.value = ''; loading.value = true
  try {
    const data = await auth.login(username, password)
    okMsg.value = `✅ 欢迎回来 ${data.user.username}！`
    setTimeout(() => router.push('/chat'), 600)
  } catch(e) {
    const detail = e.response?.data?.detail || e.message || ''
    // 把后端错误转成更友好的提示
    if (detail.includes('用户名或密码错误')) {
      errMsg.value = '账号或密码错误，请检查后重试'
    } else if (detail.includes('尝试过多') || detail.includes('频繁')) {
      errMsg.value = detail  // 限速提示直接显示
    } else {
      errMsg.value = detail || '登录失败，请稍后重试'
    }
  } finally { loading.value = false }
}

// ===== 忘记密码流程 =====
async function doSendResetCode() {
  if (!resetForm.value.email) { errMsg.value = '请输入邮箱'; return }
  errMsg.value = ''; loading.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/auth/send-reset-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: resetForm.value.email }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || '发送失败')
    okMsg.value = '✅ 验证码已发送'
    resetStep.value = 2
    resetCooldownTimer = startCooldown(resetCooldown, resetCooldownTimer)
    setTimeout(() => resetOtpInputs[0]?.focus(), 100)
  } catch(e) {
    errMsg.value = e.message
  } finally { loading.value = false }
}

async function doResetPassword() {
  if (resetForm.value.password !== resetForm.value.password2) { errMsg.value = '两次密码不一致'; return }
  if (resetForm.value.password.length < 6) { errMsg.value = '密码至少6位'; return }
  errMsg.value = ''; loading.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: resetForm.value.email,
        code: resetOtpDigits.join(''),
        new_password: resetForm.value.password,
      }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || '重置失败')
    okMsg.value = '✅ 密码重置成功，请重新登录'
    setTimeout(() => switchMode('login'), 1500)
  } catch(e) {
    errMsg.value = e.message
  } finally { loading.value = false }
}

// ===== 粒子背景 =====
const canvas = ref(null)
let animId, ctx, W, H, particles = []

class Particle {
  constructor() { this.reset() }
  reset() {
    this.x = Math.random() * W
    this.y = Math.random() * H
    this.r = Math.random() * 1.5 + 0.5
    this.vx = (Math.random() - .5) * .4
    this.vy = (Math.random() - .5) * .4
    this.alpha = Math.random() * .5 + .1
    this.color = Math.random() > .6 ? '#10b981' : Math.random() > .5 ? '#4f46e5' : '#6ee7b7'
  }
  update() {
    this.x += this.vx; this.y += this.vy
    if (this.x < 0 || this.x > W || this.y < 0 || this.y > H) this.reset()
  }
  draw() {
    ctx.save(); ctx.globalAlpha = this.alpha; ctx.fillStyle = this.color
    ctx.beginPath(); ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2); ctx.fill(); ctx.restore()
  }
}
function initCanvas() {
  ctx = canvas.value.getContext('2d')
  W = canvas.value.width = window.innerWidth
  H = canvas.value.height = window.innerHeight
  particles = Array.from({ length: 120 }, () => new Particle())
}
function animate() {
  ctx.clearRect(0, 0, W, H)
  particles.forEach(p => { p.update(); p.draw() })
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y
      const d = Math.sqrt(dx*dx + dy*dy)
      if (d < 100) {
        ctx.save(); ctx.globalAlpha = (1 - d/100) * .08; ctx.strokeStyle = '#10b981'
        ctx.lineWidth = .5; ctx.beginPath(); ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y); ctx.stroke(); ctx.restore()
      }
    }
  }
  animId = requestAnimationFrame(animate)
}
function handleResize() {
  W = canvas.value.width = window.innerWidth
  H = canvas.value.height = window.innerHeight
  particles = Array.from({ length: 120 }, () => new Particle())
}
onMounted(() => {
  initCanvas(); animate(); window.addEventListener('resize', handleResize)
  // 如果路由带了 redirect 参数说明是被守卫拦截过来的，显示友好提示
  if (route.query.redirect) {
    errMsg.value = ''
    okMsg.value = ''
  }
  // 清除 URL 里的 query 参数，避免显示乱七八糟的信息
  if (Object.keys(route.query).length > 0) {
    router.replace({ path: '/login' })
  }
})
onUnmounted(() => { cancelAnimationFrame(animId); window.removeEventListener('resize', handleResize) })
</script>

<style scoped>
.login-page { position: fixed; inset: 0; background: #0a0f1e; display: flex; align-items: center; justify-content: center; padding: 24px; overflow: hidden; }
.bg-canvas { position: fixed; inset: 0; width: 100%; height: 100%; z-index: 0; }
.overlay { position: fixed; inset: 0; background: radial-gradient(ellipse at 60% 50%, rgba(16,185,129,.12) 0%, transparent 60%), radial-gradient(ellipse at 20% 80%, rgba(79,70,229,.10) 0%, transparent 50%); z-index: 1; pointer-events: none; }
.card { position: relative; z-index: 2; display: grid; grid-template-columns: 1fr 1fr; width: 900px; max-width: 100%; min-height: 560px; background: rgba(255,255,255,.97); border-radius: 20px; overflow: hidden; box-shadow: 0 25px 60px rgba(0,0,0,.35); animation: fadeIn .5s cubic-bezier(.22,1,.36,1) both; }
@keyframes fadeIn { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:none; } }

.left { background: linear-gradient(135deg,#ecfdf5,#d1fae5 40%,#a7f3d0); display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; position: relative; overflow: hidden; }
.left::before { content:''; position:absolute; width:300px; height:300px; border-radius:50%; background:rgba(16,185,129,.12); top:-80px; right:-80px; }
.left::after  { content:''; position:absolute; width:200px; height:200px; border-radius:50%; background:rgba(79,70,229,.08); bottom:-60px; left:-60px; }
.brand { position:absolute; top:28px; left:28px; display:flex; align-items:center; gap:10px; z-index:1; }
.brand-mark { width:38px; height:38px; background:linear-gradient(135deg,#10b981,#059669); border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:18px; color:#fff; box-shadow:0 4px 12px rgba(16,185,129,.4); }
.brand-name { font-size:16px; font-weight:700; color:#111827; }
.floats { position:relative; width:220px; height:220px; z-index:1; }
.circle { position:absolute; border-radius:50%; animation:float 4s ease-in-out infinite; }
.c1 { width:140px; height:140px; background:linear-gradient(135deg,#10b981,#34d399); top:40px; left:40px; display:flex; align-items:center; justify-content:center; font-size:56px; box-shadow:0 10px 30px rgba(16,185,129,.3); }
.c2 { width:70px; height:70px; background:linear-gradient(135deg,#4f46e5,#818cf8); top:0; right:10px; animation-delay:.8s; }
.c3 { width:50px; height:50px; background:linear-gradient(135deg,#f59e0b,#fbbf24); bottom:10px; right:0; animation-delay:1.4s; }
.c4 { width:36px; height:36px; background:linear-gradient(135deg,#10b981,#6ee7b7); bottom:30px; left:10px; animation-delay:2s; }
@keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
.left-bottom { position:absolute; bottom:28px; left:28px; right:28px; z-index:1; }
.tagline { font-size:15px; font-weight:600; color:#111827; margin-bottom:8px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { display:inline-flex; align-items:center; gap:4px; background:rgba(255,255,255,.7); border:1px solid rgba(16,185,129,.2); border-radius:20px; padding:3px 10px; font-size:12px; color:#059669; }

.right { padding:40px 48px; display:flex; flex-direction:column; justify-content:center; background:#fff; }
.title { font-size:24px; font-weight:700; color:#111827; margin-bottom:4px; }
.sub { font-size:13px; color:#6b7280; margin-bottom:20px; }
.tabs { display:flex; border-bottom:1px solid #e5e7eb; margin-bottom:20px; }
.tab { padding:8px 0; margin-right:24px; font-size:14px; font-weight:500; color:#6b7280; background:none; border:none; border-bottom:2px solid transparent; cursor:pointer; font-family:inherit; transition:all .18s; }
.tab.active { color:#111827; border-bottom-color:#10b981; }

/* 步骤指示器 */
.steps { display:flex; align-items:center; margin-bottom:8px; }
.step-item { display:flex; align-items:center; flex:1; }
.step-item:last-child { flex:none; }
.step-dot { width:28px; height:28px; border-radius:50%; border:2px solid #e5e7eb; background:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600; color:#9ca3af; transition:all .25s; flex-shrink:0; }
.step-dot.active { border-color:#10b981; background:#10b981; color:#fff; }
.step-dot.done { border-color:#10b981; background:#10b981; color:#fff; }
.step-line { flex:1; height:2px; background:#e5e7eb; margin:0 4px; transition:background .25s; }
.step-line.done { background:#10b981; }
.step-hint { font-size:12px; color:#6b7280; margin-bottom:14px; }

.form { display:flex; flex-direction:column; gap:12px; }
.field { display:flex; flex-direction:column; gap:5px; }
.field label { font-size:12px; font-weight:500; color:#4b5563; }
.field label em { font-style:normal; color:#9ca3af; font-weight:400; }
.field input { padding:10px 13px; border:1px solid #e5e7eb; border-radius:10px; font-size:14px; font-family:inherit; color:#111827; outline:none; transition:border-color .18s, box-shadow .18s; }
.field input:focus { border-color:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.12); }
.field-hint { font-size:11px; color:#9ca3af; margin:-4px 0 0; }
.pw-wrap { position:relative; }
.pw-wrap input { width:100%; box-sizing:border-box; padding-right:38px; }
.eye { position:absolute; right:11px; top:50%; transform:translateY(-50%); cursor:pointer; font-size:14px; user-select:none; }
.forgot-link { text-align:right; margin-top:-4px; }
.forgot-link span { font-size:12px; color:#10b981; cursor:pointer; }
.forgot-link span:hover { text-decoration:underline; }

/* OTP */
.otp-wrap { display:flex; gap:8px; }
.otp-input { width:40px !important; height:48px; text-align:center; font-size:20px; font-weight:600; padding:0 !important; border:1.5px solid #e5e7eb; border-radius:10px; transition:all .18s; }
.otp-input:focus { border-color:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.12); }

.resend-row { display:flex; justify-content:flex-end; margin-top:-4px; }
.resend-hint { font-size:12px; color:#9ca3af; }
.resend-link { font-size:12px; color:#10b981; cursor:pointer; }
.resend-link:hover { text-decoration:underline; }

.row-fields { display:flex; gap:10px; }
.submit-btn { padding:12px; background:#111827; color:#fff; border:none; border-radius:9999px; font-size:14px; font-weight:600; font-family:inherit; cursor:pointer; transition:background .18s; display:flex; align-items:center; justify-content:center; gap:8px; }
.submit-btn:hover:not(:disabled) { background:#059669; }
.submit-btn:disabled { background:#9ca3af; cursor:not-allowed; }
.back-btn { padding:8px; background:none; border:none; color:#9ca3af; font-size:12px; font-family:inherit; cursor:pointer; text-align:center; }
.back-btn:hover { color:#374151; }
.spinner { width:14px; height:14px; border:2px solid rgba(255,255,255,.4); border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.err { background:#fef2f2; border:1px solid #fecaca; color:#dc2626; padding:10px 14px; border-radius:8px; font-size:13px; margin-top:8px; }
.ok  { background:#ecfdf5; border:1px solid #a7f3d0; color:#059669; padding:10px 14px; border-radius:8px; font-size:13px; margin-top:8px; }
@media (max-width:640px) { .card { grid-template-columns:1fr; } .left { display:none; } .right { padding:36px 24px; } }
</style>
