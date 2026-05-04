<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../panels/TopNav.vue'
import { fetchCurrentUser, fetchOrders, fetchWeekProgress, fetchMistakeDist } from '@/api'

const router = useRouter()
const user = ref(null)
const orders = ref([])
const weekData = ref([])
const mistakes = ref([])
const tab = ref('profile')

const tabs = [
  { k: 'profile', icon: '👤', label: '我的资料' },
  { k: 'member',  icon: '👑', label: '会员中心' },
  { k: 'orders',  icon: '📋', label: '订单记录' },
  { k: 'study',   icon: '📊', label: '学习数据' }
]

onMounted(async () => {
  user.value = await fetchCurrentUser()
  orders.value = await fetchOrders()
  weekData.value = await fetchWeekProgress()
  mistakes.value = await fetchMistakeDist()
})

const goPricing = () => router.push('/pricing')
const goDashboard = () => router.push('/dashboard')

function statusLabel(s) {
  return s === 'paid' ? '已支付' : s === 'pending' ? '待支付' : '已退款'
}
</script>

<template>
  <TopNav active="" @change="(k) => router.push('/' + k)" @login="router.push('/login')" />
  <div class="uc-wrap" v-if="user">
    <!-- 头部卡片 -->
    <div class="uc-hero">
      <div class="avatar">{{ user.avatar }}</div>
      <div class="hero-meta">
        <div class="row1">
          <h1>{{ user.nickname }}</h1>
          <span class="badge-pro" v-if="user.membership.plan === 'pro'">👑 {{ user.membership.label }}</span>
        </div>
        <div class="row2">
          <span>📧 {{ user.email }}</span>
          <span>📱 {{ user.phone }}</span>
          <span>🗓 加入于 {{ user.joinedAt }}</span>
        </div>
      </div>
      <div class="hero-stats">
        <div class="hs-item">
          <div class="hs-n">{{ user.stats.studyDays }}</div>
          <div class="hs-l">学习天数</div>
        </div>
        <div class="hs-item">
          <div class="hs-n">{{ user.stats.streak }}</div>
          <div class="hs-l">连续打卡</div>
        </div>
        <div class="hs-item">
          <div class="hs-n">{{ user.points }}</div>
          <div class="hs-l">学习积分</div>
        </div>
      </div>
    </div>

    <!-- 主体 -->
    <div class="uc-body">
      <!-- 左：tabs -->
      <aside class="uc-tabs">
        <button
          v-for="t in tabs"
          :key="t.k"
          :class="['tab', { active: tab === t.k }]"
          @click="tab = t.k"
        >
          <span class="t-ic">{{ t.icon }}</span>
          <span>{{ t.label }}</span>
        </button>
      </aside>

      <!-- 右：内容 -->
      <section class="uc-content">
        <!-- 资料 -->
        <div v-if="tab === 'profile'" class="card">
          <h2>我的资料</h2>
          <div class="form-row">
            <label>昵称</label>
            <input :value="user.nickname" />
          </div>
          <div class="form-row">
            <label>用户名</label>
            <input :value="user.username" disabled />
          </div>
          <div class="form-row">
            <label>邮箱</label>
            <input :value="user.email" />
          </div>
          <div class="form-row">
            <label>手机</label>
            <input :value="user.phone" />
          </div>
          <div class="form-row">
            <label>简介</label>
            <textarea rows="3" placeholder="一句话介绍下自己…"></textarea>
          </div>
          <div class="form-actions">
            <button class="btn-primary">保存修改</button>
            <button class="btn-ghost">修改密码</button>
          </div>
        </div>

        <!-- 会员 -->
        <div v-else-if="tab === 'member'" class="card">
          <h2>会员中心</h2>
          <div class="member-card">
            <div class="mc-left">
              <div class="mc-plan">👑 {{ user.membership.label }}</div>
              <div class="mc-expire">有效期至 {{ user.membership.expiresAt }}</div>
              <div class="mc-features">
                <div>✓ AI 对话不限次数</div>
                <div>✓ 错题本无上限 + 自动归类</div>
                <div>✓ 随机出题全科目全题型</div>
                <div>✓ 申论范文批改 100 篇 / 月</div>
              </div>
            </div>
            <div class="mc-right">
              <div class="mc-points">
                <div class="mc-points-n">{{ user.points }}</div>
                <div class="mc-points-l">学习积分</div>
              </div>
              <button class="btn-primary" @click="goPricing">续费会员</button>
              <button class="btn-ghost">兑换商城</button>
            </div>
          </div>
          <div class="member-perks">
            <h3>专属权益</h3>
            <div class="perks-grid">
              <div class="perk"><div class="perk-ic">🎯</div><div><b>每周精选题包</b><p>编辑团队精选 200 题</p></div></div>
              <div class="perk"><div class="perk-ic">📚</div><div><b>申论范文库</b><p>解锁 500+ 优秀范文</p></div></div>
              <div class="perk"><div class="perk-ic">🎓</div><div><b>名师直播课</b><p>每月 4 节免费直播</p></div></div>
              <div class="perk"><div class="perk-ic">🛟</div><div><b>1v1 答疑</b><p>每月 5 次专属答疑</p></div></div>
            </div>
          </div>
        </div>

        <!-- 订单 -->
        <div v-else-if="tab === 'orders'" class="card">
          <h2>订单记录</h2>
          <table class="orders-table">
            <thead>
              <tr><th>订单号</th><th>商品</th><th>金额</th><th>状态</th><th>下单日期</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="o in orders" :key="o.id">
                <td style="color:var(--gk-gray-900);font-weight:500;">{{ o.id }}</td>
                <td>{{ o.plan }}</td>
                <td>¥{{ o.amount }}</td>
                <td>
                  <span :class="['order-status', o.status]">
                    {{ statusLabel(o.status) }}
                  </span>
                </td>
                <td>{{ o.date }}</td>
                <td>
                  <a class="link">详情</a>
                  <a v-if="o.status === 'paid'" class="link">开发票</a>
                  <a v-if="o.status === 'pending'" class="link">支付</a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 学习数据 -->
        <div v-else-if="tab === 'study'" class="card">
          <h2>学习数据 <a class="link" @click="goDashboard" style="float:right;font-size:13px;font-weight:400;">查看完整看板 →</a></h2>
          <div class="study-grid">
            <div class="sg-item">
              <div class="sg-n">{{ user.stats.practiced }}</div>
              <div class="sg-l">累计做题</div>
            </div>
            <div class="sg-item">
              <div class="sg-n">{{ user.stats.correctRate }}%</div>
              <div class="sg-l">平均正确率</div>
            </div>
            <div class="sg-item">
              <div class="sg-n">{{ user.stats.mistakes }}</div>
              <div class="sg-l">错题总数</div>
            </div>
            <div class="sg-item">
              <div class="sg-n">{{ user.stats.aiChats }}</div>
              <div class="sg-l">AI 对话次数</div>
            </div>
          </div>

          <h3 style="margin:32px 0 16px;font-size:15px;">本周完成情况</h3>
          <div class="week-bars">
            <div v-for="d in weekData" :key="d.day" class="week-bar">
              <div class="bar-wrap">
                <div
                  class="bar"
                  :style="{
                    height: Math.min(100, (d.value / d.target) * 100) + '%',
                    background: d.value >= d.target ? '#10b981' : d.value > 0 ? '#a7f3d0' : '#e5e7eb'
                  }"
                ></div>
              </div>
              <div class="bar-label">{{ d.day }}</div>
              <div class="bar-value">{{ d.value }}</div>
            </div>
          </div>

          <h3 style="margin:32px 0 16px;font-size:15px;">错题分布</h3>
          <div class="mistake-bars">
            <div v-for="m in mistakes" :key="m.type" class="mb-row">
              <span class="mb-name">{{ m.type }}</span>
              <div class="mb-track">
                <div class="mb-fill" :style="{ width: (m.count / 30 * 100) + '%', background: m.color }"></div>
              </div>
              <span class="mb-val">{{ m.count }} 题</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.uc-wrap { max-width: 1100px; margin: 0 auto; padding: 24px 32px 48px; }

/* Hero */
.uc-hero {
  background: linear-gradient(135deg, #ecfdf5 0%, #fff 60%);
  border: 1px solid var(--gk-gray-200);
  border-radius: 14px;
  padding: 28px 32px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 24px;
  align-items: center;
  margin-bottom: 20px;
}
.avatar { width: 72px; height: 72px; border-radius: 50%; background: linear-gradient(135deg, #10b981, #059669); color: #fff; font-size: 28px; font-weight: 700; display: flex; align-items: center; justify-content: center; box-shadow: 0 6px 16px rgba(16,185,129,.25); }
.hero-meta .row1 { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.hero-meta h1 { font-size: 22px; font-weight: 700; color: var(--gk-gray-900); margin: 0; }
.badge-pro { background: linear-gradient(135deg, #f59e0b, #fbbf24); color: #fff; font-size: 11px; padding: 2px 10px; border-radius: 12px; font-weight: 600; }
.hero-meta .row2 { display: flex; gap: 18px; font-size: 12px; color: var(--gk-gray-600); }
.hero-stats { display: flex; gap: 36px; }
.hs-item { text-align: center; }
.hs-n { font-size: 24px; font-weight: 700; color: var(--gk-green-600); }
.hs-l { font-size: 11px; color: var(--gk-gray-500); margin-top: 4px; }

/* Body grid */
.uc-body { display: grid; grid-template-columns: 200px 1fr; gap: 20px; }

/* Tabs */
.uc-tabs { display: flex; flex-direction: column; gap: 4px; }
.tab { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 10px; cursor: pointer; font-family: inherit; font-size: 14px; color: var(--gk-gray-700); transition: all .15s; }
.tab:hover { background: var(--gk-green-50); color: var(--gk-green-700); }
.tab.active { background: var(--gk-green-500); color: #fff; border-color: var(--gk-green-500); font-weight: 500; }
.t-ic { font-size: 16px; }

/* Card */
.card { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 12px; padding: 28px; }
.card h2 { font-size: 18px; font-weight: 600; color: var(--gk-gray-900); margin: 0 0 20px; }

/* Form */
.form-row { display: grid; grid-template-columns: 100px 1fr; gap: 12px; align-items: center; margin-bottom: 14px; }
.form-row label { font-size: 13px; color: var(--gk-gray-600); }
.form-row input, .form-row textarea { padding: 9px 12px; border: 1px solid var(--gk-gray-200); border-radius: 8px; font-family: inherit; font-size: 13px; outline: 0; resize: vertical; }
.form-row input:focus, .form-row textarea:focus { border-color: var(--gk-green-500); box-shadow: 0 0 0 3px rgba(16,185,129,.1); }
.form-row input:disabled { background: var(--gk-gray-50); color: var(--gk-gray-500); }
.form-actions { display: flex; gap: 10px; margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--gk-gray-100); }

.btn-primary, .btn-ghost { padding: 9px 20px; border-radius: 8px; font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; border: 0; }
.btn-primary { background: var(--gk-green-500); color: #fff; }
.btn-primary:hover { background: var(--gk-green-600); }
.btn-ghost { background: #fff; border: 1px solid var(--gk-gray-200); color: var(--gk-gray-700); }
.btn-ghost:hover { background: var(--gk-gray-50); }

/* Member */
.member-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px;
  background: linear-gradient(135deg, #064e3b, #047857);
  color: #fff;
  border-radius: 14px;
  padding: 28px;
  position: relative;
  overflow: hidden;
}
.member-card::before { content: ""; position: absolute; top: -30%; right: -10%; width: 220px; height: 220px; border-radius: 50%; background: rgba(255,255,255,.06); }
.mc-plan { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.mc-expire { font-size: 12px; opacity: .85; margin-bottom: 16px; }
.mc-features { display: flex; flex-direction: column; gap: 6px; font-size: 13px; opacity: .95; }
.mc-right { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; position: relative; z-index: 1; }
.mc-points { background: rgba(255,255,255,.15); padding: 10px 18px; border-radius: 10px; text-align: center; backdrop-filter: blur(4px); margin-bottom: 8px; }
.mc-points-n { font-size: 20px; font-weight: 700; }
.mc-points-l { font-size: 10px; opacity: .85; }
.mc-right .btn-primary { background: #fff; color: var(--gk-green-700); }
.mc-right .btn-ghost { background: rgba(255,255,255,.1); border-color: rgba(255,255,255,.3); color: #fff; }

.member-perks { margin-top: 28px; }
.member-perks h3 { font-size: 15px; font-weight: 600; color: var(--gk-gray-900); margin: 0 0 16px; }
.perks-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.perk { display: flex; gap: 12px; padding: 16px; border: 1px solid var(--gk-gray-200); border-radius: 10px; }
.perk-ic { width: 40px; height: 40px; border-radius: 10px; background: var(--gk-green-50); color: var(--gk-green-600); display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.perk b { font-size: 14px; color: var(--gk-gray-900); }
.perk p { font-size: 12px; color: var(--gk-gray-500); margin: 4px 0 0; }

/* Orders */
.orders-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.orders-table thead th { text-align: left; padding: 10px 12px; background: var(--gk-gray-50); color: var(--gk-gray-600); font-weight: 500; font-size: 12px; }
.orders-table tbody td { padding: 14px 12px; border-bottom: 1px solid var(--gk-gray-100); color: var(--gk-gray-700); }
.order-status { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.order-status.paid { background: #d1fae5; color: #047857; }
.order-status.pending { background: #fef3c7; color: #a16207; }
.order-status.refunded { background: #fee2e2; color: #b91c1c; }
.link { color: var(--gk-green-600); margin-right: 10px; cursor: pointer; font-size: 12px; }
.link:hover { text-decoration: underline; }

/* Study */
.study-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.sg-item { text-align: center; padding: 18px; background: var(--gk-gray-50); border-radius: 10px; }
.sg-n { font-size: 26px; font-weight: 700; color: var(--gk-gray-900); }
.sg-l { font-size: 12px; color: var(--gk-gray-500); margin-top: 4px; }

.week-bars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
.week-bar { text-align: center; }
.bar-wrap { height: 100px; display: flex; align-items: flex-end; padding: 0 12px; }
.bar { width: 100%; background: var(--gk-green-500); border-radius: 6px 6px 0 0; transition: all .3s; min-height: 4px; }
.bar-label { font-size: 11px; color: var(--gk-gray-500); margin-top: 6px; }
.bar-value { font-size: 13px; font-weight: 600; color: var(--gk-gray-900); }

.mistake-bars { display: flex; flex-direction: column; gap: 12px; }
.mb-row { display: grid; grid-template-columns: 90px 1fr 60px; align-items: center; gap: 12px; }
.mb-name { font-size: 13px; color: var(--gk-gray-700); }
.mb-track { height: 8px; background: var(--gk-gray-100); border-radius: 4px; overflow: hidden; }
.mb-fill { height: 100%; border-radius: 4px; transition: width .3s; }
.mb-val { font-size: 12px; color: var(--gk-gray-500); text-align: right; }

@media (max-width: 768px) {
  .uc-hero { grid-template-columns: 1fr; text-align: center; }
  .hero-meta .row2 { justify-content: center; flex-wrap: wrap; }
  .uc-body { grid-template-columns: 1fr; }
  .uc-tabs { flex-direction: row; overflow-x: auto; }
  .study-grid { grid-template-columns: repeat(2, 1fr); }
  .perks-grid { grid-template-columns: 1fr; }
  .member-card { grid-template-columns: 1fr; }
  .mc-right { align-items: stretch; }
}
</style>
