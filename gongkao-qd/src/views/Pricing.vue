<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../panels/TopNav.vue'
import { fetchPlans, fetchPricingFAQ } from '@/api'

const router = useRouter()
const plans = ref([])
const faq = ref([])
const openFaq = ref(0)

onMounted(async () => {
  plans.value = await fetchPlans()
  faq.value = await fetchPricingFAQ()
})

const formatPrice = (p) => {
  if (typeof p !== 'number') return '电话联系'
  return p === 0 ? '免费' : `¥${p}`
}

const handleCta = (plan) => {
  if (plan.key === 'free') return router.push('/chat')
  if (plan.key === 'enterprise') return alert('销售经理会在 1 个工作日内联系你 ✉️')
  router.push('/me')
}
</script>

<template>
  <TopNav active="" @change="(k) => router.push('/' + k)" @login="router.push('/login')" />
  <div class="pr-wrap">
    <!-- Hero -->
    <section class="pr-hero">
      <div class="pill">💎 升级会员 · 解锁全部能力</div>
      <h1>选择适合你的方案<br>用更高的效率上岸</h1>
      <p>全部方案均含 31 省 + 国考真题免费下载。会员升级后享受 AI 不限次、申论批改等更多专属能力。</p>
    </section>

    <!-- Plans -->
    <section class="pr-plans">
      <div
        v-for="p in plans"
        :key="p.key"
        :class="['plan', { highlight: p.highlight }]"
      >
        <div v-if="p.highlight" class="recommend-badge">⭐ 90% 用户都选这个</div>
        <div class="plan-name">{{ p.name }}</div>
        <div class="plan-price">
          <span class="amount">{{ formatPrice(p.price) }}</span>
          <span v-if="p.price === 0" class="cycle">/ 永久</span>
          <span v-else-if="typeof p.price === 'number'" class="cycle">/ 年</span>
        </div>
        <div class="plan-period">{{ p.period }}</div>
        <p class="plan-desc">{{ p.desc }}</p>
        <ul class="plan-features">
          <li v-for="(f, i) in p.features" :key="i" :class="{ disabled: !f.ok }">
            <span class="check">{{ f.ok ? '✓' : '×' }}</span>
            <span>{{ f.text }}</span>
          </li>
        </ul>
        <button :class="['plan-cta', { primary: p.highlight }]" @click="handleCta(p)">
          {{ p.cta }}
        </button>
      </div>
    </section>

    <!-- 对比表 -->
    <section class="pr-compare">
      <h2>更清晰的能力对比</h2>
      <div class="compare-table">
        <div class="ct-head">
          <div class="ct-cell">能力</div>
          <div class="ct-cell">免费版</div>
          <div class="ct-cell highlight">高级会员</div>
          <div class="ct-cell">机构版</div>
        </div>
        <div class="ct-row" v-for="row in [
          { name: '真题免费下载', a: '✓', b: '✓', c: '✓' },
          { name: 'AI 对话',     a: '20 次 / 天', b: '不限次数', c: '不限次数' },
          { name: '错题本',       a: '50 题',  b: '无上限',  c: '无上限' },
          { name: '随机出题',     a: '常识题', b: '全题型',  c: '全题型 · 自定义' },
          { name: '申论批改',     a: '-',     b: '100 篇 / 月', c: '不限' },
          { name: '学习计划',     a: '-',     b: '智能排课', c: '智能排课 + 班级管理' },
          { name: '数据看板',     a: '基础',   b: '完整',    c: '完整 + 班级数据' },
          { name: '设备数',       a: '1',     b: '3',      c: '按席位计费' },
          { name: '客服',         a: '社区',   b: '工单 24h', c: '专属 1v1' }
        ]" :key="row.name">
          <div class="ct-cell name">{{ row.name }}</div>
          <div class="ct-cell">{{ row.a }}</div>
          <div class="ct-cell highlight">{{ row.b }}</div>
          <div class="ct-cell">{{ row.c }}</div>
        </div>
      </div>
    </section>

    <!-- FAQ -->
    <section class="pr-faq">
      <h2>常见问题</h2>
      <div class="faq-list">
        <div
          v-for="(item, i) in faq"
          :key="i"
          :class="['faq-item', { open: openFaq === i }]"
          @click="openFaq = openFaq === i ? -1 : i"
        >
          <div class="faq-q">
            <span>{{ item.q }}</span>
            <span class="faq-toggle">{{ openFaq === i ? '−' : '+' }}</span>
          </div>
          <div v-if="openFaq === i" class="faq-a">{{ item.a }}</div>
        </div>
      </div>
    </section>

    <!-- Final CTA -->
    <section class="pr-cta">
      <h2>还在犹豫？先免费用一周看看</h2>
      <p>免费版本身就足以日常备考，等你觉得 AI 不限次数对你有帮助再升级也不迟。</p>
      <div class="pr-cta-row">
        <button class="btn-primary btn-lg" @click="router.push('/chat')">免费开始使用</button>
        <button class="btn-ghost btn-lg" @click="router.push('/welcome')">了解更多 →</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pr-wrap { background: linear-gradient(180deg, #ecfdf5 0%, #fff 350px); min-height: 100vh; }

/* Hero */
.pr-hero { max-width: 720px; margin: 0 auto; padding: 64px 32px 48px; text-align: center; }
.pill { display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1px solid var(--gk-green-200); color: var(--gk-green-700); font-size: 12px; font-weight: 500; padding: 6px 14px; border-radius: 9999px; margin-bottom: 20px; }
.pr-hero h1 { font-size: 40px; font-weight: 800; color: var(--gk-gray-900); line-height: 1.2; letter-spacing: -.02em; margin: 0 0 16px; }
.pr-hero p { font-size: 16px; color: var(--gk-gray-600); line-height: 1.7; margin: 0; }

/* Plans */
.pr-plans { max-width: 1080px; margin: 0 auto; padding: 0 32px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.plan { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 16px; padding: 32px 28px; position: relative; transition: all .25s; }
.plan:hover { transform: translateY(-3px); box-shadow: 0 12px 32px rgba(17,24,39,.08); }
.plan.highlight { border: 2px solid var(--gk-green-500); box-shadow: 0 12px 40px rgba(16,185,129,.18); transform: scale(1.02); }
.recommend-badge { position: absolute; top: -14px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #f59e0b, #fbbf24); color: #fff; font-size: 11px; font-weight: 600; padding: 5px 14px; border-radius: 12px; white-space: nowrap; }
.plan-name { font-size: 14px; font-weight: 600; color: var(--gk-gray-600); margin-bottom: 8px; }
.plan-price { display: flex; align-items: baseline; gap: 6px; margin-bottom: 4px; }
.plan-price .amount { font-size: 38px; font-weight: 800; color: var(--gk-gray-900); letter-spacing: -.02em; }
.plan-price .cycle { font-size: 14px; color: var(--gk-gray-500); }
.plan-period { font-size: 12px; color: var(--gk-gray-500); margin-bottom: 14px; }
.plan-desc { font-size: 13px; color: var(--gk-gray-600); margin: 0 0 24px; padding-bottom: 24px; border-bottom: 1px solid var(--gk-gray-100); line-height: 1.6; }

.plan-features { list-style: none; padding: 0; margin: 0 0 24px; display: flex; flex-direction: column; gap: 10px; }
.plan-features li { display: flex; align-items: flex-start; gap: 10px; font-size: 13px; color: var(--gk-gray-700); line-height: 1.5; }
.plan-features li.disabled { color: var(--gk-gray-400); text-decoration: line-through; }
.plan-features .check { width: 18px; height: 18px; border-radius: 50%; background: var(--gk-green-50); color: var(--gk-green-600); display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; margin-top: 1px; }
.plan-features li.disabled .check { background: var(--gk-gray-100); color: var(--gk-gray-400); }

.plan-cta { width: 100%; padding: 12px; background: #fff; border: 1px solid var(--gk-gray-200); color: var(--gk-gray-700); border-radius: 10px; font-family: inherit; font-size: 14px; font-weight: 500; cursor: pointer; transition: all .15s; }
.plan-cta:hover { background: var(--gk-gray-50); }
.plan-cta.primary { background: var(--gk-green-500); color: #fff; border-color: var(--gk-green-500); }
.plan-cta.primary:hover { background: var(--gk-green-600); }

/* Compare */
.pr-compare { max-width: 960px; margin: 80px auto 0; padding: 0 32px; }
.pr-compare h2 { font-size: 28px; font-weight: 700; color: var(--gk-gray-900); text-align: center; margin: 0 0 32px; letter-spacing: -.01em; }
.compare-table { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 14px; overflow: hidden; }
.ct-head, .ct-row { display: grid; grid-template-columns: 1.6fr 1fr 1fr 1fr; }
.ct-head { background: var(--gk-gray-50); font-size: 13px; font-weight: 600; color: var(--gk-gray-700); }
.ct-row { font-size: 13px; border-top: 1px solid var(--gk-gray-100); }
.ct-row:hover { background: var(--gk-gray-50); }
.ct-cell { padding: 14px 18px; color: var(--gk-gray-700); }
.ct-cell.name { color: var(--gk-gray-900); font-weight: 500; }
.ct-cell.highlight { background: var(--gk-green-50); color: var(--gk-green-700); font-weight: 500; }
.ct-head .ct-cell.highlight { background: linear-gradient(135deg, var(--gk-green-500), var(--gk-green-600)); color: #fff; }

/* FAQ */
.pr-faq { max-width: 720px; margin: 80px auto 0; padding: 0 32px; }
.pr-faq h2 { font-size: 28px; font-weight: 700; color: var(--gk-gray-900); text-align: center; margin: 0 0 32px; letter-spacing: -.01em; }
.faq-list { display: flex; flex-direction: column; gap: 10px; }
.faq-item { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 12px; padding: 18px 22px; cursor: pointer; transition: all .15s; }
.faq-item:hover { border-color: var(--gk-green-300); }
.faq-item.open { border-color: var(--gk-green-500); }
.faq-q { display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 500; color: var(--gk-gray-900); }
.faq-toggle { width: 24px; height: 24px; border-radius: 50%; background: var(--gk-gray-100); color: var(--gk-gray-600); display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 600; transition: all .15s; }
.faq-item.open .faq-toggle { background: var(--gk-green-500); color: #fff; }
.faq-a { font-size: 14px; color: var(--gk-gray-600); line-height: 1.7; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--gk-gray-100); }

/* Final CTA */
.pr-cta { max-width: 720px; margin: 80px auto 0; padding: 0 32px 80px; text-align: center; }
.pr-cta h2 { font-size: 28px; font-weight: 700; color: var(--gk-gray-900); margin: 0 0 12px; letter-spacing: -.01em; }
.pr-cta p { font-size: 15px; color: var(--gk-gray-600); margin: 0 0 24px; line-height: 1.7; }
.pr-cta-row { display: flex; gap: 12px; justify-content: center; }
.btn-primary, .btn-ghost { padding: 12px 28px; border-radius: 10px; font-family: inherit; font-size: 14px; font-weight: 500; cursor: pointer; border: 0; }
.btn-lg { padding: 14px 32px; font-size: 15px; }
.btn-primary { background: var(--gk-green-500); color: #fff; }
.btn-primary:hover { background: var(--gk-green-600); }
.btn-ghost { background: #fff; border: 1px solid var(--gk-gray-300); color: var(--gk-gray-700); }
.btn-ghost:hover { background: var(--gk-gray-50); }

@media (max-width: 768px) {
  .pr-plans { grid-template-columns: 1fr; }
  .plan.highlight { transform: none; }
  .ct-head, .ct-row { grid-template-columns: 1.4fr 1fr 1fr 1fr; font-size: 12px; }
  .ct-cell { padding: 10px 8px; }
}
</style>
