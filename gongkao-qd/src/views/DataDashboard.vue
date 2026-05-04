<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../panels/TopNav.vue'
import { fetchCurrentUser, fetchWeekProgress, fetchMistakeDist, fetchHeatmap30, fetchTrend14d } from '@/api'

const router = useRouter()
const user = ref(null)
const week = ref([])
const mistakes = ref([])
const heat = ref([])
const trend = ref({ dau: [], newUsers: [], labels: [] })

onMounted(async () => {
  user.value = await fetchCurrentUser()
  week.value = await fetchWeekProgress()
  mistakes.value = await fetchMistakeDist()
  heat.value = await fetchHeatmap30()
  trend.value = await fetchTrend14d()
})

// ===== 环形图：正确率 =====
const ringR = 60
const ringC = 2 * Math.PI * ringR
const ringDash = computed(() => {
  const v = user.value?.stats.correctRate || 0
  return `${(v / 100) * ringC} ${ringC}`
})

// ===== 错题饼图（SVG）=====
const pie = computed(() => {
  if (!mistakes.value.length) return []
  const total = mistakes.value.reduce((s, m) => s + m.count, 0)
  let acc = 0
  const r = 70
  const cx = 90, cy = 90
  return mistakes.value.map(m => {
    const pct = m.count / total
    const start = acc
    const end = acc + pct
    acc = end
    const x1 = cx + r * Math.sin(2 * Math.PI * start)
    const y1 = cy - r * Math.cos(2 * Math.PI * start)
    const x2 = cx + r * Math.sin(2 * Math.PI * end)
    const y2 = cy - r * Math.cos(2 * Math.PI * end)
    const large = pct > .5 ? 1 : 0
    return {
      d: `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`,
      color: m.color,
      label: m.type,
      count: m.count,
      pct: Math.round(pct * 100)
    }
  })
})

// ===== 14 天趋势：正确率上升 =====
const trendPath = computed(() => {
  const W = 600, H = 160, PAD = 20
  const values = trend.value.dau.map(v => Math.min(95, 60 + v / 1000))
  if (!values.length) return ''
  const max = 100
  return values.map((v, i) => {
    const x = PAD + (i / (values.length - 1)) * (W - PAD * 2)
    const y = H - 10 - (v / max) * (H - 30)
    return (i === 0 ? 'M' : 'L') + ` ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
})

// 热力图颜色映射
const heatColor = (l) => ['#f3f4f6', '#a7f3d0', '#6ee7b7', '#34d399', '#10b981'][l]

const goPractice = () => router.push('/practice')
const goMistakes = () => router.push('/mistakes')
</script>

<template>
  <TopNav active="" @change="(k) => router.push('/' + k)" @login="router.push('/login')" />
  <div class="dd-wrap" v-if="user">
    <header class="dd-head">
      <div>
        <h1>学习数据看板</h1>
        <p>{{ user.nickname }} · 第 {{ user.stats.studyDays }} 天 · 距离 2026 国考还有 218 天</p>
      </div>
      <div class="dd-actions">
        <button class="btn-ghost">📅 切换时间段</button>
        <button class="btn-ghost">📥 导出报告</button>
      </div>
    </header>

    <!-- 4 个核心指标 -->
    <div class="kpi-grid">
      <div class="kpi" style="--c:#10b981">
        <div class="kpi-ic">📝</div>
        <div class="kpi-n">{{ user.stats.practiced }}</div>
        <div class="kpi-l">累计做题</div>
        <div class="kpi-d">↑ 38 本周新增</div>
      </div>
      <div class="kpi" style="--c:#3b82f6">
        <div class="kpi-ic">🎯</div>
        <div class="kpi-n">{{ user.stats.correctRate }}%</div>
        <div class="kpi-l">平均正确率</div>
        <div class="kpi-d">↑ 4.2 较上周</div>
      </div>
      <div class="kpi" style="--c:#f59e0b">
        <div class="kpi-ic">🔥</div>
        <div class="kpi-n">{{ user.stats.streak }}</div>
        <div class="kpi-l">连续打卡天</div>
        <div class="kpi-d">坚持就是胜利</div>
      </div>
      <div class="kpi" style="--c:#ef4444">
        <div class="kpi-ic">📒</div>
        <div class="kpi-n">{{ user.stats.mistakes }}</div>
        <div class="kpi-l">错题待巩固</div>
        <div class="kpi-d">本周新增 8 题</div>
      </div>
    </div>

    <!-- 环形图 + 折线 -->
    <div class="row-2 row-2--main">
      <div class="panel">
        <div class="panel-head">
          <h3>正确率</h3>
          <a class="link">本月</a>
        </div>
        <div class="panel-body" style="display:flex;align-items:center;gap:24px;">
          <svg viewBox="0 0 160 160" style="width:160px;height:160px;flex-shrink:0;">
            <circle cx="80" cy="80" :r="ringR" stroke="#f3f4f6" stroke-width="14" fill="none"/>
            <circle
              cx="80" cy="80" :r="ringR"
              stroke="#10b981" stroke-width="14" fill="none"
              :stroke-dasharray="ringDash"
              stroke-linecap="round"
              transform="rotate(-90 80 80)"
            />
            <text x="80" y="78" text-anchor="middle" font-size="32" font-weight="700" fill="#111827">{{ user.stats.correctRate }}%</text>
            <text x="80" y="98" text-anchor="middle" font-size="11" fill="#6b7280">正确率</text>
          </svg>
          <div style="flex:1;">
            <div class="ring-side">
              <span>已答对</span>
              <b style="color:#10b981;">{{ Math.round(user.stats.practiced * user.stats.correctRate / 100) }} 题</b>
            </div>
            <div class="ring-side">
              <span>答错</span>
              <b style="color:#ef4444;">{{ user.stats.practiced - Math.round(user.stats.practiced * user.stats.correctRate / 100) }} 题</b>
            </div>
            <div class="ring-side">
              <span>本周目标</span>
              <b>200 题</b>
            </div>
            <button class="btn-primary" style="margin-top:12px;width:100%;" @click="goPractice">去做练习 →</button>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h3>近 14 天正确率走势</h3>
          <a class="link">月度报表</a>
        </div>
        <div class="panel-body">
          <svg viewBox="0 0 600 180" style="width:100%;height:180px;">
            <g stroke="#f3f4f6" stroke-width="1">
              <line x1="0" y1="40"  x2="600" y2="40"/>
              <line x1="0" y1="80"  x2="600" y2="80"/>
              <line x1="0" y1="120" x2="600" y2="120"/>
              <line x1="0" y1="160" x2="600" y2="160"/>
            </g>
            <path :d="trendPath" stroke="#10b981" stroke-width="2.5" fill="none"/>
            <g font-size="10" fill="#9ca3af">
              <text x="0" y="38">100%</text>
              <text x="0" y="78">85%</text>
              <text x="0" y="118">70%</text>
              <text x="0" y="158">55%</text>
            </g>
          </svg>
          <div style="font-size:12px;color:var(--gk-gray-500);text-align:right;margin-top:8px;">较上周 ↑ 4.2 个百分点 🎉</div>
        </div>
      </div>
    </div>

    <!-- 错题分布 + 本周完成 -->
    <div class="row-2">
      <div class="panel">
        <div class="panel-head">
          <h3>错题分布</h3>
          <a class="link" @click="goMistakes">全部错题 →</a>
        </div>
        <div class="panel-body" style="display:flex;align-items:center;gap:32px;">
          <svg viewBox="0 0 180 180" style="width:180px;height:180px;flex-shrink:0;">
            <path v-for="(s, i) in pie" :key="i" :d="s.d" :fill="s.color"/>
            <circle cx="90" cy="90" r="36" fill="#fff"/>
            <text x="90" y="92" text-anchor="middle" font-size="18" font-weight="700" fill="#111827">{{ user.stats.mistakes }}</text>
            <text x="90" y="108" text-anchor="middle" font-size="10" fill="#6b7280">总错题</text>
          </svg>
          <div style="flex:1;">
            <div v-for="s in pie" :key="s.label" class="legend-row">
              <span class="legend-dot" :style="{ background: s.color }"></span>
              <span class="legend-name">{{ s.label }}</span>
              <span class="legend-pct">{{ s.pct }}%</span>
              <span class="legend-cnt">{{ s.count }} 题</span>
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h3>本周完成情况</h3>
          <a class="link">查看全部</a>
        </div>
        <div class="panel-body">
          <div class="week-bars">
            <div v-for="d in week" :key="d.day" class="wb">
              <div class="wb-bar-wrap">
                <div
                  class="wb-bar"
                  :style="{
                    height: Math.min(100, (d.value / d.target) * 100) + '%',
                    background: d.value >= d.target ? '#10b981' : d.value > 0 ? '#a7f3d0' : '#e5e7eb'
                  }"
                ></div>
              </div>
              <div class="wb-label">{{ d.day }}</div>
              <div class="wb-val">{{ d.value }}</div>
            </div>
          </div>
          <div style="font-size:12px;color:var(--gk-gray-500);text-align:center;margin-top:12px;">
            目标 30 题 / 天 · 本周已完成 <b style="color:var(--gk-green-600);">{{ week.reduce((s, d) => s + d.value, 0) }}</b> / {{ week.length * 30 }} 题
          </div>
        </div>
      </div>
    </div>

    <!-- 学习热力 -->
    <div class="panel">
      <div class="panel-head">
        <h3>近 30 天学习热力</h3>
        <div style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--gk-gray-500);">
          少
          <span class="heat-cell" :style="{ background: '#f3f4f6' }"></span>
          <span class="heat-cell" :style="{ background: '#a7f3d0' }"></span>
          <span class="heat-cell" :style="{ background: '#6ee7b7' }"></span>
          <span class="heat-cell" :style="{ background: '#34d399' }"></span>
          <span class="heat-cell" :style="{ background: '#10b981' }"></span>
          多
        </div>
      </div>
      <div class="panel-body">
        <div class="heat-grid">
          <div
            v-for="(h, i) in heat"
            :key="i"
            class="heat-cell heat-cell--lg"
            :style="{ background: heatColor(h.level) }"
            :title="`第 ${h.day} 天 · 等级 ${h.level}`"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dd-wrap { max-width: 1100px; margin: 0 auto; padding: 24px 32px 48px; display: flex; flex-direction: column; gap: 16px; }

.dd-head { display: flex; align-items: flex-end; justify-content: space-between; }
.dd-head h1 { font-size: 24px; font-weight: 700; color: var(--gk-gray-900); margin: 0 0 6px; }
.dd-head p { font-size: 13px; color: var(--gk-gray-500); margin: 0; }
.dd-actions { display: flex; gap: 8px; }
.btn-ghost { padding: 8px 14px; background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 8px; font-size: 13px; color: var(--gk-gray-700); cursor: pointer; font-family: inherit; }
.btn-ghost:hover { background: var(--gk-gray-50); }
.btn-primary { padding: 9px 16px; background: var(--gk-green-500); color: #fff; border: 0; border-radius: 8px; font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; }
.btn-primary:hover { background: var(--gk-green-600); }

/* KPI grid */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.kpi { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 12px; padding: 20px; position: relative; overflow: hidden; }
.kpi::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--c, #10b981); }
.kpi-ic { width: 36px; height: 36px; border-radius: 8px; background: color-mix(in srgb, var(--c) 12%, #fff); color: var(--c); font-size: 18px; display: flex; align-items: center; justify-content: center; margin-bottom: 12px; }
.kpi-n { font-size: 30px; font-weight: 700; color: var(--gk-gray-900); letter-spacing: -.02em; line-height: 1; }
.kpi-l { font-size: 12px; color: var(--gk-gray-500); margin-top: 6px; }
.kpi-d { font-size: 11px; color: var(--gk-green-600); margin-top: 8px; padding: 2px 8px; background: var(--gk-green-50); display: inline-block; border-radius: 8px; }

/* Row-2 */
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.row-2--main { grid-template-columns: 1.1fr 1.4fr; }

.panel { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 12px; }
.panel-head { display: flex; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--gk-gray-100); }
.panel-head h3 { flex: 1; font-size: 14px; font-weight: 600; color: var(--gk-gray-900); margin: 0; }
.panel-head .link { font-size: 12px; color: var(--gk-green-600); cursor: pointer; }
.panel-body { padding: 18px; }

/* Ring */
.ring-side { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; color: var(--gk-gray-600); }
.ring-side b { color: var(--gk-gray-900); }

/* Pie legend */
.legend-row { display: grid; grid-template-columns: 12px 1fr auto auto; gap: 10px; align-items: center; padding: 7px 0; font-size: 13px; }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; }
.legend-name { color: var(--gk-gray-700); }
.legend-pct { color: var(--gk-gray-500); font-size: 12px; }
.legend-cnt { font-weight: 600; color: var(--gk-gray-900); width: 60px; text-align: right; }

/* Week bars */
.week-bars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
.wb { text-align: center; }
.wb-bar-wrap { height: 100px; display: flex; align-items: flex-end; padding: 0 12px; }
.wb-bar { width: 100%; border-radius: 6px 6px 0 0; min-height: 4px; transition: all .3s; }
.wb-label { font-size: 11px; color: var(--gk-gray-500); margin-top: 6px; }
.wb-val { font-size: 13px; font-weight: 600; color: var(--gk-gray-900); }

/* Heat */
.heat-cell { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.heat-cell--lg { width: 100%; aspect-ratio: 1; border-radius: 4px; }
.heat-grid { display: grid; grid-template-columns: repeat(15, 1fr); gap: 4px; max-width: 600px; margin: 0 auto; }

@media (max-width: 768px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .row-2, .row-2--main { grid-template-columns: 1fr; }
  .heat-grid { grid-template-columns: repeat(10, 1fr); }
  .dd-head { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
