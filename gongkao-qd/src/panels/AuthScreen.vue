<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const emit = defineEmits(['switch'])

const phone = ref('')
const code = ref('')
const agree = ref(true)
const sent = ref(0)
let timer = null

const canSubmit = computed(() => phone.value.length === 11 && code.value.length >= 4 && agree.value)

const startCountdown = () => {
  if (sent.value > 0) return
  if (phone.value.length < 11) return
  sent.value = 60
  timer = setInterval(() => {
    sent.value -= 1
    if (sent.value <= 0) clearInterval(timer)
  }, 1000)
}

onBeforeUnmount(() => timer && clearInterval(timer))

const codeDisabled = computed(() => phone.value.length < 11 || sent.value > 0)

const codeBtnStyle = computed(() => ({
  whiteSpace: 'nowrap',
  border: 0,
  background: codeDisabled.value ? 'var(--gk-gray-100)' : 'var(--gk-green-50)',
  color: codeDisabled.value ? 'var(--gk-gray-400)' : 'var(--gk-green-700)',
  padding: '0 16px',
  borderRadius: '10px',
  fontSize: '13px',
  fontWeight: 500,
  cursor: codeDisabled.value ? 'default' : 'pointer',
  fontFamily: 'inherit'
}))

const submitStyle = computed(() => ({
  border: 0,
  background: !canSubmit.value ? 'var(--gk-gray-200)' : 'var(--gk-gray-900)',
  color: '#fff',
  padding: '14px 0',
  borderRadius: '9999px',
  fontSize: '15px',
  fontWeight: 600,
  cursor: !canSubmit.value ? 'not-allowed' : 'pointer',
  fontFamily: 'inherit',
  transition: 'all 180ms'
}))

const onPhone = (e) => { phone.value = e.target.value.replace(/\D/g, '') }
const onCode = (e) => { code.value = e.target.value.replace(/\D/g, '') }

const onFocusBox = (e) => {
  e.currentTarget.style.borderColor = 'var(--gk-green-500)'
  e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.18)'
}
const onBlurBox = (e) => {
  e.currentTarget.style.borderColor = 'var(--gk-gray-200)'
  e.currentTarget.style.boxShadow = 'none'
}
</script>

<template>
  <div style="min-height:100vh;background:#fafafa;display:flex;align-items:center;justify-content:center;padding:24px;">
    <div style="display:grid;grid-template-columns:1fr 1fr;width:900px;max-width:100%;min-height:560px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 20px 50px rgba(17,24,39,0.08);border:1px solid var(--gk-gray-200);">
      <div style="background:#ecfdf5;display:flex;align-items:center;justify-content:center;padding:40px;position:relative;overflow:hidden;">
        <div style="position:absolute;top:28px;left:28px;display:flex;align-items:center;gap:10px;">
          <img src="/logo-mark.svg" width="36" height="36" style="border-radius:9px;" />
          <span style="font-size:16px;font-weight:700;color:var(--gk-gray-900);">公考小智</span>
        </div>
        <img src="/auth-illustration.svg" style="width:100%;max-width:380px;display:block;" />
        <div style="position:absolute;bottom:28px;left:28px;right:28px;font-size:13px;color:var(--gk-gray-600);line-height:1.7;">
          <div style="font-size:15px;font-weight:600;color:var(--gk-gray-900);margin-bottom:4px;">你的公考智慧搭子 🌱</div>
          2,579 份真题 · 32 个省份 · 全部免费
        </div>
        <button
          @click="emit('switch', null)"
          style="position:absolute;top:28px;right:28px;border:1px solid var(--gk-gray-200);background:#fff;color:var(--gk-gray-600);padding:6px 12px;border-radius:8px;font-size:12px;cursor:pointer;font-family:inherit;"
        >← 返回</button>
      </div>

      <div style="padding:64px 56px;display:flex;flex-direction:column;justify-content:center;">
        <div style="font-size:26px;font-weight:700;color:var(--gk-gray-900);margin-bottom:6px;">欢迎回来 👋</div>
        <div style="font-size:13px;color:var(--gk-gray-500);margin-bottom:32px;">输入手机号，开始 / 继续备考</div>

        <div style="display:flex;flex-direction:column;gap:16px;">
          <div>
            <div style="font-size:12px;color:var(--gk-gray-600);font-weight:500;margin-bottom:6px;">手机号</div>
            <div
              style="display:flex;align-items:center;border:1px solid var(--gk-gray-200);border-radius:10px;padding:2px 0 2px 14px;background:#fff;transition:all 180ms;"
              @focusin="onFocusBox"
              @focusout="onBlurBox"
            >
              <span style="font-size:14px;color:var(--gk-gray-700);font-weight:500;">+86</span>
              <div style="width:1px;height:18px;background:var(--gk-gray-200);margin:0 12px;"></div>
              <input
                :value="phone"
                @input="onPhone"
                placeholder="请输入手机号"
                maxlength="11"
                style="flex:1;border:0;outline:0;padding:10px 14px 10px 0;font-size:15px;font-family:inherit;background:transparent;color:var(--gk-gray-900);"
              />
            </div>
          </div>

          <div>
            <div style="font-size:12px;color:var(--gk-gray-600);font-weight:500;margin-bottom:6px;">验证码</div>
            <div style="display:flex;gap:8px;">
              <input
                :value="code"
                @input="onCode"
                placeholder="6 位验证码"
                maxlength="6"
                :style="{
                  flex: 1,
                  border: '1px solid var(--gk-gray-200)',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  fontSize: '15px',
                  fontFamily: 'inherit',
                  outline: 0,
                  letterSpacing: code ? '4px' : 0
                }"
                @focus="e => { e.target.style.borderColor = 'var(--gk-green-500)'; e.target.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.18)' }"
                @blur="e => { e.target.style.borderColor = 'var(--gk-gray-200)'; e.target.style.boxShadow = 'none' }"
              />
              <button :disabled="codeDisabled" @click="startCountdown" :style="codeBtnStyle">
                {{ sent > 0 ? `${sent}s 后重发` : '获取验证码' }}
              </button>
            </div>
          </div>

          <label style="display:flex;align-items:flex-start;gap:8px;font-size:12px;color:var(--gk-gray-500);cursor:pointer;line-height:1.6;margin-top:4px;">
            <input type="checkbox" v-model="agree" style="accent-color:var(--gk-green-500);margin-top:2px;" />
            <span>我已阅读并同意 <a style="color:var(--gk-green-600);">《用户协议》</a> 和 <a style="color:var(--gk-green-600);">《隐私政策》</a></span>
          </label>

          <button :disabled="!canSubmit" :style="submitStyle" @click="emit('switch', null)">登录 / 注册</button>

          <div style="font-size:12px;color:var(--gk-gray-400);text-align:center;line-height:1.6;margin-top:4px;">
            未注册的手机号将自动创建账号
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
