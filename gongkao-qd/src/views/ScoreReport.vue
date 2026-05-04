<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchScoreReport } from '@/api'

const route = useRoute()
const router = useRouter()

const report = ref(null)
const copied = ref(false)

onMounted(async () => {
  report.value = await fetchScoreReport(route.params.id)
})

const score = computed(() => {
  if (!report.value) return 0
  return Math.round((report.value.correct / report.value.totalQuestions) * 100)
})

const grade = computed(() => {
  const s = score.value
  if (s >= 90) return { label: '优秀', emoji: '🏆', color: '#f59e0b' }
  if (s >= 80) return { label: '良好', emoji: '🎯', color: '#10b981' }
  if (s >= 60) return { label: '及格', emoji: '👍', color: '#3b82f6' }
  return { label: '加油', emoji: '💪', color: '#ef4444' }
})

// 圆环参数
const RING_R = 70
const RING_C = 2 * Math.PI * RING_R
const ringDash = computed(() => {
  const v = score.value
  return `${(v / 100) * RING_C} ${RING_C}`
})

const copyLink = async () => {
  const url = window.location.origin + '/report/' + report.value.id
  try {
    await navigator.clipboard.writeText(url)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (e) {
    alert('请手动复制链接：' + url)
  }
}

const generatePoster = () => {
  alert('生成海报功能正在开发中～\n敬请期待！')
}

const goPractice = () => router.push('/practice')
const goQuestion = (id) => router.push('/question/' + id)
</script>

<template>
  <div class="report-page" v-if="report">
    <!-- 顶部导航条 -->
    <header class="rp-nav">
      <div class="rp-nav-inner">
        <div class="rp-brand" @click="router.push('/')">
          <div class="rp-logo">公</div>
          <span>公考小智</span>
        </div>
        <div class="rp-nav-actions">
          <button class="btn-ghost" @click="router.push('/chat')">回到首页</button>
        </div>
      </div>
    </header>

    <main class="rp-main">
      <!-- 主报告卡 -->
      <section class="rp-card">
        <!-- 头部信息 -->
        <div class="rp-head">
          <div class="rp-meta">
            <div class="rp-id">#{{ report.id }}</div>
            <div class="rp-paper">{{ report.paperName }}</div>
            <div class="rp-info">
              <span>👤 {{ report.user }}</span>
              <span>📅 {{ report.date }}</span>
              <span>⏱️ 用时 {{ report.duration }}</span>
            </div>
          </div>
          <div class="rp-grade" :style="{ background: `${grade.color}15`, color: grade.color }">
            {{ grade.emoji }} {{ grade.label }}
          </div>
        </div>

        <!-- 大分数 + 数据条 -->
        <div class="rp-score">
          <div class="ring-wrap">
            <svg viewBox="0 0 160 160" width="160" height="160">
              <circle cx="80" cy="80" :r="RING_R" fill="none" stroke="var(--gk-gray-100)" stroke-width="14" />
              <circle
                cx="80" cy="80" :r="RING_R" fill="none"
                :stroke="grade.color" stroke-width="14" stroke-linecap="round"
                :stroke-dasharray="ringDash"
                transform="rotate(-90 80 80)"
              />
            </svg>
            <div class="ring-center">
              <div class="ring-num">{{ score }}</div>
              <div class="ring-unit">分</div>
            </div>
          </div>
          <div class="rp-kpis">
            <div class="kpi-item">
              <div class="kpi-label">答对</div>
              <div class="kpi-val ok">{{ report.correct }}<span>/{{ report.totalQuestions }}</span></div>
            </div>
            <div class="kpi-item">
              <div class="kpi-label">答错</div>
              <div class="kpi-val bad">{{ report.wrong }}<span>题</span></div>
            </div>
            <div class="kpi-item">
              <div class="kpi-label">超过</div>
              <div class="kpi-val hl">{{ report.percentile }}%<span>考生</span></div>
            </div>
            <div class="kpi-item">
              <div class="kpi-label">用时</div>
              <div class="kpi-val">{{ report.duration }}</div>
            </div>
          </div>
        </div>

        <!-- 模块分析 -->
        <div class="rp-section">
          <h3>📊 各模块表现</h3>
          <div class="modules">
            <div v-for="m in report.modules" :key="m.name" class="mod-row">
              <div class="mod-name">{{ m.name }}</div>
              <div class="mod-bar">
                <div
                  class="mod-fill"
                  :style="{
                    width: ((m.correct / m.total) * 100) + '%',
                    background: m.color
                  }"
                ></div>
              </div>
              <div class="mod-val">
                <b>{{ m.correct }}</b><span>/{{ m.total }}</span>
                <em :style="{ color: m.color }">{{ Math.round((m.correct / m.total) * 100) }}%</em>
              </div>
            </div>
          </div>
        </div>

        <!-- 错题清单 -->
        <div class="rp-section">
          <h3>❌ 错题回顾 <span class="sec-sub">{{ report.wrongList.length }} 题</span></h3>
          <div class="wrong-list">
            <div v-for="(w, idx) in report.wrongList" :key="w.id" class="wrong-item" @click="goQuestion(w.id)">
              <div class="wrong-idx">{{ idx + 1 }}</div>
              <div class="wrong-body">
                <div class="wrong-stem">{{ w.stem }}</div>
                <div class="wrong-ans">
                  <span class="ans-bad">你的答案：<b>{{ w.yours }}</b></span>
                  <span class="ans-ok">正确答案：<b>{{ w.answer }}</b></span>
                </div>
              </div>
              <div class="wrong-arrow">→</div>
            </div>
          </div>
        </div>

        <!-- 总结 / 建议 -->
        <div class="rp-summary">
          <div class="sum-icon">💡</div>
          <div class="sum-text">
            <div class="sum-title">智能学习建议</div>
            <p>
              本次成绩超过了 <b>{{ report.percentile }}%</b> 的考生，整体表现优秀。
              <span v-if="report.modules.find(m => m.correct / m.total < 0.6)">
                建议重点加强 <b>{{ report.modules.filter(m => m.correct / m.total < 0.6).map(m => m.name).join('、') }}</b> 模块的训练。
              </span>
              <span v-else>各模块均衡发展，可适当挑战更高难度题目。</span>
            </p>
          </div>
        </div>
      </section>

      <!-- 操作栏 -->
      <section class="rp-actions">
        <button class="action-btn primary" @click="copyLink">
          <span class="ab-icon">🔗</span>
          <span class="ab-text">{{ copied ? '已复制!' : '复制分享链接' }}</span>
        </button>
        <button class="action-btn" @click="generatePoster">
          <span class="ab-icon">🖼️</span>
          <span class="ab-text">生成成绩海报</span>
        </button>
        <button class="action-btn" @click="goPractice">
          <span class="ab-icon">📝</span>
          <span class="ab-text">再来一套</span>
        </button>
      </section>

      <!-- 底部 -->
      <footer class="rp-footer">
        <div class="rp-tip">
          🎯 来 <a @click="router.push('/welcome')">公考小智</a> 一起刷题，AI 智慧搭子陪你上岸
        </div>
      </footer>
    </main>
  </div>

  <!-- Loading -->
  <div v-else class="loading-state">
    <div class="spinner"></div>
    <p>报告加载中…</p>
  </div>
</template>

<style scoped>
.report-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f0fdf4 0%, #f9fafb 280px, #f9fafb 100%);
}

/* Nav */
.rp-nav {
  background: rgba(255, 255, 255, .85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--gk-gray-100);
  position: sticky;
  top: 0;
  z-index: 10;
}
.rp-nav-inner {
  max-width: 920px;
  margin: 0 auto;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rp-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 700;
  font-size: 16px;
  color: var(--gk-gray-900);
}
.rp-logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--gk-green-500), var(--gk-green-600));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}
.btn-ghost {
  padding: 8px 16px;
  border: 1px solid var(--gk-gray-200);
  background: #fff;
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  color: var(--gk-gray-700);
}
.btn-ghost:hover { background: var(--gk-gray-50); border-color: var(--gk-green-400); }

/* Main */
.rp-main {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

/* Card */
.rp-card {
  background: #fff;
  border: 1px solid var(--gk-gray-200);
  border-radius: 18px;
  padding: 36px 40px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, .04);
}

.rp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px dashed var(--gk-gray-200);
}
.rp-id {
  font-size: 11px;
  color: var(--gk-gray-400);
  letter-spacing: .08em;
  margin-bottom: 6px;
}
.rp-paper {
  font-size: 22px;
  font-weight: 700;
  color: var(--gk-gray-900);
  margin-bottom: 10px;
}
.rp-info {
  display: flex;
  gap: 18px;
  font-size: 13px;
  color: var(--gk-gray-600);
}
.rp-grade {
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

/* Score */
.rp-score {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 32px;
  align-items: center;
  margin-bottom: 36px;
  padding: 24px;
  background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
  border-radius: 14px;
  border: 1px solid var(--gk-green-100);
}
.ring-wrap {
  position: relative;
  width: 160px;
  height: 160px;
  margin: 0 auto;
}
.ring-center {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ring-num {
  font-size: 56px;
  font-weight: 800;
  color: var(--gk-gray-900);
  line-height: 1;
}
.ring-unit {
  font-size: 13px;
  color: var(--gk-gray-500);
  margin-top: 4px;
}

.rp-kpis {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}
.kpi-item {
  background: #fff;
  border-radius: 10px;
  padding: 14px 16px;
  border: 1px solid var(--gk-gray-100);
}
.kpi-label {
  font-size: 12px;
  color: var(--gk-gray-500);
  margin-bottom: 6px;
}
.kpi-val {
  font-size: 22px;
  font-weight: 700;
  color: var(--gk-gray-900);
}
.kpi-val span {
  font-size: 13px;
  color: var(--gk-gray-500);
  font-weight: 500;
  margin-left: 3px;
}
.kpi-val.ok { color: var(--gk-green-600); }
.kpi-val.bad { color: var(--gk-red-500); }
.kpi-val.hl { color: var(--gk-amber-500); }

/* Sections */
.rp-section { margin-bottom: 32px; }
.rp-section h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--gk-gray-900);
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sec-sub {
  font-size: 12px;
  color: var(--gk-gray-500);
  font-weight: 400;
  background: var(--gk-gray-100);
  padding: 2px 8px;
  border-radius: 8px;
}

/* Modules */
.modules { display: flex; flex-direction: column; gap: 14px; }
.mod-row {
  display: grid;
  grid-template-columns: 90px 1fr 130px;
  align-items: center;
  gap: 16px;
}
.mod-name {
  font-size: 13px;
  color: var(--gk-gray-700);
  font-weight: 500;
}
.mod-bar {
  height: 14px;
  background: var(--gk-gray-100);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}
.mod-fill {
  height: 100%;
  border-radius: 8px;
  transition: width .6s ease;
}
.mod-val {
  font-size: 13px;
  text-align: right;
  color: var(--gk-gray-700);
}
.mod-val b { color: var(--gk-gray-900); font-size: 15px; }
.mod-val span { color: var(--gk-gray-400); }
.mod-val em {
  font-style: normal;
  font-weight: 600;
  margin-left: 8px;
  font-size: 13px;
}

/* Wrong list */
.wrong-list { display: flex; flex-direction: column; gap: 10px; }
.wrong-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px solid var(--gk-gray-100);
  border-radius: 10px;
  cursor: pointer;
  transition: all .15s;
}
.wrong-item:hover {
  background: #fef2f2;
  border-color: #fecaca;
  transform: translateX(2px);
}
.wrong-idx {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--gk-red-500);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.wrong-body { flex: 1; min-width: 0; }
.wrong-stem {
  font-size: 13px;
  color: var(--gk-gray-800);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wrong-ans {
  display: flex;
  gap: 16px;
  font-size: 12px;
}
.ans-bad { color: var(--gk-red-600); }
.ans-bad b { font-weight: 700; }
.ans-ok { color: var(--gk-green-600); }
.ans-ok b { font-weight: 700; }
.wrong-arrow {
  color: var(--gk-gray-400);
  font-size: 16px;
  flex-shrink: 0;
}

/* Summary */
.rp-summary {
  display: flex;
  gap: 14px;
  padding: 20px;
  background: linear-gradient(135deg, #fffbeb, #fef3c7);
  border: 1px solid #fde68a;
  border-radius: 12px;
}
.sum-icon { font-size: 32px; line-height: 1; }
.sum-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--gk-gray-900);
  margin-bottom: 6px;
}
.sum-text p {
  font-size: 13px;
  line-height: 1.7;
  color: var(--gk-gray-700);
  margin: 0;
}
.sum-text b { color: var(--gk-gray-900); }

/* Actions */
.rp-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 24px;
}
.action-btn {
  padding: 16px 20px;
  background: #fff;
  border: 1px solid var(--gk-gray-200);
  border-radius: 12px;
  cursor: pointer;
  font-family: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: all .15s;
}
.action-btn:hover {
  border-color: var(--gk-green-400);
  background: var(--gk-green-50);
  transform: translateY(-2px);
}
.action-btn.primary {
  background: linear-gradient(135deg, var(--gk-green-500), var(--gk-green-600));
  border-color: transparent;
  color: #fff;
}
.action-btn.primary:hover {
  background: linear-gradient(135deg, var(--gk-green-600), var(--gk-green-700));
}
.ab-icon { font-size: 18px; }
.ab-text { font-size: 14px; font-weight: 500; }

/* Footer */
.rp-footer {
  margin-top: 32px;
  text-align: center;
}
.rp-tip {
  font-size: 13px;
  color: var(--gk-gray-500);
}
.rp-tip a {
  color: var(--gk-green-600);
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}
.rp-tip a:hover { text-decoration: underline; }

/* Loading */
.loading-state {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--gk-gray-500);
}
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--gk-gray-200);
  border-top-color: var(--gk-green-500);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .rp-card { padding: 24px 20px; }
  .rp-head { flex-direction: column; gap: 12px; }
  .rp-paper { font-size: 18px; }
  .rp-info { flex-wrap: wrap; gap: 10px; font-size: 12px; }
  .rp-score { grid-template-columns: 1fr; gap: 20px; }
  .rp-kpis { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .mod-row { grid-template-columns: 70px 1fr 110px; gap: 10px; }
  .rp-actions { grid-template-columns: 1fr; }
  .wrong-stem { white-space: normal; }
}
</style>
