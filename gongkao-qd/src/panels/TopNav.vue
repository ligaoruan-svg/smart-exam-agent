<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import Logomark from '../components/Logomark.vue'
import { useAuthStore } from '@/stores/auth'

defineProps({
  active: { type: String, required: true }
})
const emit = defineEmits(['change', 'login'])

const router = useRouter()
const auth = useAuthStore()

const items = [
  { k: 'chat', label: 'AI 对话', emoji: '📚' },
  { k: 'practice', label: '随机练习', emoji: '🎲' },
  { k: 'download', label: '真题下载', emoji: '📦' },
  { k: 'mistakes', label: '错题本', emoji: '📒' },
  { k: 'plan', label: '学习计划', emoji: '📅' }
]

const btnStyle = (isActive) => ({
  padding: '8px 14px',
  borderRadius: '8px',
  border: 0,
  background: isActive ? 'var(--gk-green-50)' : 'transparent',
  color: isActive ? 'var(--gk-green-700)' : 'var(--gk-gray-600)',
  fontSize: '14px',
  fontWeight: isActive ? 600 : 500,
  cursor: 'pointer',
  fontFamily: 'inherit',
  display: 'flex',
  alignItems: 'center',
  gap: '6px'
})

const menuOpen = ref(false)
const userInitial = computed(() => {
  const u = auth.user?.username
  if (!u) return '你'
  return u.charAt(0).toUpperCase()
})

const toggleMenu = (e) => {
  e?.stopPropagation()
  menuOpen.value = !menuOpen.value
}
const closeMenu = () => { menuOpen.value = false }

const go = (path) => {
  closeMenu()
  router.push(path)
}

const handleLogout = () => {
  auth.logout()
  closeMenu()
  router.push('/welcome')
}

onMounted(() => document.addEventListener('click', closeMenu))
onBeforeUnmount(() => document.removeEventListener('click', closeMenu))
</script>

<template>
  <div class="topnav">
    <Logomark :size="32" />
    <div class="nav-tabs">
      <button
        v-for="it in items"
        :key="it.k"
        @click="emit('change', it.k)"
        :style="btnStyle(active === it.k)"
      >
        <span>{{ it.emoji }}</span>{{ it.label }}
      </button>
    </div>
    <div class="nav-right">
      <span class="status-text">在线 · 2579 份真题</span>

      <!-- 未登录：登录按钮 -->
      <button v-if="!auth.isLoggedIn" class="login-btn" @click="emit('login')">
        登录 / 注册
      </button>

      <!-- 落地页入口（始终可见） -->
      <button class="ghost-btn" @click="go('/welcome')" title="官网首页">
        🏠
      </button>

      <!-- 已登录：头像 + 下拉菜单 -->
      <div class="avatar-wrap" @click.stop>
        <div class="avatar" @click="toggleMenu">
          {{ userInitial }}
        </div>
        <transition name="menu">
          <div v-if="menuOpen" class="menu">
            <div class="menu-head" v-if="auth.isLoggedIn">
              <div class="mh-avatar">{{ userInitial }}</div>
              <div class="mh-info">
                <div class="mh-name">{{ auth.user?.username || '同学' }}</div>
                <div class="mh-tag">高级会员</div>
              </div>
            </div>
            <div class="menu-head guest" v-else>
              <div class="mh-info">
                <div class="mh-name">未登录</div>
                <div class="mh-tag" style="color:var(--gk-gray-500);">登录后查看个人数据</div>
              </div>
            </div>

            <div class="menu-divider"></div>

            <div class="menu-item" @click="go('/me')"><span>👤</span>个人中心</div>
            <div class="menu-item" @click="go('/dashboard')"><span>📊</span>学习数据看板</div>
            <div class="menu-item" @click="go('/pricing')"><span>💎</span>会员中心</div>
            <div v-if="auth.isAdmin" class="menu-item" @click="go('/admin')"><span>🛠️</span>管理后台</div>

            <div class="menu-divider"></div>

            <div class="menu-item" @click="go('/welcome')"><span>🏠</span>返回首页</div>
            <div v-if="auth.isLoggedIn" class="menu-item danger" @click="handleLogout"><span>🚪</span>退出登录</div>
            <div v-else class="menu-item" @click="go('/login')"><span>🔑</span>登录 / 注册</div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topnav {
  background: #fff;
  border-bottom: 1px solid var(--gk-gray-200);
  padding: 12px 32px;
  display: flex;
  align-items: center;
  gap: 32px;
}
.nav-tabs { display: flex; gap: 4px; flex: 1; }
.nav-right { display: flex; align-items: center; gap: 10px; }
.status-text { font-size: 12px; color: var(--gk-gray-500); }

.login-btn {
  border: 1px solid var(--gk-green-500);
  background: var(--gk-green-50);
  color: var(--gk-green-700);
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
}
.login-btn:hover { background: var(--gk-green-100); }

.ghost-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--gk-gray-200);
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ghost-btn:hover { background: var(--gk-gray-50); border-color: var(--gk-green-400); }

.avatar-wrap { position: relative; }
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--gk-green-500);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
}
.avatar:hover { background: var(--gk-green-600); }

.menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 240px;
  background: #fff;
  border: 1px solid var(--gk-gray-200);
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, .12);
  z-index: 50;
  overflow: hidden;
}
.menu-head {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
}
.menu-head.guest { background: var(--gk-gray-50); }
.mh-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--gk-green-500);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}
.mh-name { font-size: 14px; font-weight: 600; color: var(--gk-gray-900); }
.mh-tag { font-size: 11px; color: var(--gk-green-600); margin-top: 2px; }

.menu-divider { height: 1px; background: var(--gk-gray-100); }

.menu-item {
  padding: 10px 16px;
  font-size: 13px;
  color: var(--gk-gray-700);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: background .12s;
}
.menu-item:hover { background: var(--gk-green-50); color: var(--gk-green-700); }
.menu-item.danger { color: var(--gk-red-500); }
.menu-item.danger:hover { background: #fef2f2; color: var(--gk-red-600); }
.menu-item span { font-size: 15px; }

.menu-enter-active, .menu-leave-active {
  transition: opacity .15s, transform .15s;
}
.menu-enter-from, .menu-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
