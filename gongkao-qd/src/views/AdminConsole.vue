<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchAdminStats, fetchTrend14d, fetchActivities,
  fetchProvinces, fetchRecentPapers, fetchAdminUsers
} from '@/api'

const router = useRouter()

const menu = [
  { group: '数据概览', items: [
    { k: 'dashboard', icon: '📊', label: '仪表盘' },
    { k: 'analytics', icon: '📈', label: '数据分析' }
  ]},
  { group: '内容管理', items: [
    { k: 'papers',    icon: '📄', label: '真题管理', badge: 23 },
    { k: 'zips',      icon: '📦', label: '省份 ZIP 包' },
    { k: 'questions', icon: '❓', label: '题库管理' },
    { k: 'notice',    icon: '📢', label: '公告管理' }
  ]},
  { group: '用户与审核', items: [
    { k: 'users',    icon: '👥', label: '用户管理' },
    { k: 'review',   icon: '🚩', label: '内容审核', badge: 5 },
    { k: 'feedback', icon: '💬', label: '反馈中心' }
  ]},
  { group: 'AI 与系统', items: [
    { k: 'ai',       icon: '🤖', label: 'AI 配置' },
    { k: 'settings', icon: '⚙️', label: '系统设置' }
  ]}
]

const active = ref('dashboard')
const stats = ref({ totalUsers: 0, dau: 0, totalPapers: 0, aiCalls: 0, deltas: {} })
const trend = ref({ dau: [], newUsers: [], labels: [] })
const acts = ref([])
const provinces = ref([])
const papers = ref([])
const users = ref([])

const filterStatus = ref('all')

const filteredPapers = computed(() => {
  if (filterStatus.value === 'all') return papers.value
  return papers.value.filter(p => p.status === filterStatus.value)
})

const activeLabel = computed(() => {
  for (const g of menu) {
    const f = g.items.find(it => it.k === active.value)
    if (f) return f.label
  }
  return ''
})

// 14 天折线 → SVG 路径
const dauPath = computed(() => buildPath(trend.value.dau, 16000))
const dauArea = computed(() => buildArea(trend.value.dau, 16000))
const regPath = computed(() => buildPath(trend.value.newUsers, 800))

function buildPath(values, max) {
  if (!values?.length) return ''
  const n = values.length
  const W = 640, H = 200, PAD = 20
  return values.map((v, i) => {
    const x = PAD + (i / (n - 1)) * (W - PAD * 2)
    const y = H - 10 - (v / max) * (H - 30)
    return (i === 0 ? 'M' : 'L') + ` ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
}
function buildArea(values, max) {
  if (!values?.length) return ''
  return buildPath(values, max) + ` L 620 190 L 20 190 Z`
}

onMounted(async () => {
  stats.value = await fetchAdminStats()
  trend.value = await fetchTrend14d()
  acts.value = await fetchActivities()
  provinces.value = await fetchProvinces()
  papers.value = await fetchRecentPapers()
  users.value = await fetchAdminUsers()
})

const goSite = () => router.push('/welcome')
const fmt = (n) => n.toLocaleString()
</script>

<template>
  <div class="shell">
    <!-- SIDEBAR -->
    <aside class="side">
      <div class="brand" @click="goSite">
        <img src="/logo-mark.svg" width="32" height="32" style="border-radius:8px;cursor:pointer;"/>
        <div>
          <div class="t">公考小智</div>
          <div class="sub">Admin</div>
        </div>
      </div>
      <template v-for="g in menu" :key="g.group">
        <div class="grp">{{ g.group }}</div>
        <a
          v-for="it in g.items"
          :key="it.k"
          :class="{ active: active === it.k }"
          @click="active = it.k"
        >
          <span class="ic">{{ it.icon }}</span>{{ it.label }}
          <span v-if="it.badge" class="badge">{{ it.badge }}</span>
        </a>
      </template>
    </aside>

    <!-- MAIN -->
    <main>
      <div class="top">
        <div class="crumb">管理后台 / <b>{{ activeLabel }}</b></div>
        <div class="search">
          <input placeholder="搜索真题、用户、题目 ID..." />
        </div>
        <div class="top-right">
          <span style="font-size:12px;">服务正常</span>
          <span class="bell">🔔</span>
          <div class="me">
            <div class="av">管</div>
            <span style="font-size:13px;color:#111827;font-weight:500;">admin</span>
          </div>
        </div>
      </div>

      <div class="content">
        <!-- ===== 仪表盘 ===== -->
        <template v-if="active === 'dashboard'">
          <div class="page-title">
            <h1>仪表盘</h1>
            <span class="sub">今日 2026-04-24 · 最近更新 3 分钟前</span>
            <div class="spacer"></div>
            <button class="btn btn-ghost">⟳ 刷新</button>
            <button class="btn btn-ghost">📥 导出数据</button>
            <button class="btn btn-primary">+ 上传真题</button>
          </div>

          <!-- 4 个核心指标 -->
          <div class="stats">
            <div class="stat">
              <div class="label">累计注册用户</div>
              <div class="n">{{ fmt(stats.totalUsers) }}</div>
              <span class="delta up">↑ {{ stats.deltas.totalUsers }}% 较上周</span>
              <div class="ico" style="background:#ecfdf5;color:#10b981;">👥</div>
            </div>
            <div class="stat">
              <div class="label">今日活跃用户 (DAU)</div>
              <div class="n">{{ fmt(stats.dau) }}</div>
              <span class="delta up">↑ {{ stats.deltas.dau }}% 较昨日</span>
              <div class="ico" style="background:#eef2ff;color:#6366f1;">⚡</div>
            </div>
            <div class="stat">
              <div class="label">真题总数</div>
              <div class="n">{{ fmt(stats.totalPapers) }}</div>
              <span class="delta up">↑ {{ stats.deltas.totalPapers }} 本周新增</span>
              <div class="ico" style="background:#f5f3ff;color:#8b5cf6;">📄</div>
            </div>
            <div class="stat">
              <div class="label">AI 对话次数 (今日)</div>
              <div class="n">{{ fmt(stats.aiCalls) }}</div>
              <span class="delta down">↓ {{ Math.abs(stats.deltas.aiCalls) }}% 较昨日</span>
              <div class="ico" style="background:#fef3c7;color:#d97706;">🤖</div>
            </div>
          </div>

          <!-- 趋势图 + 动态 -->
          <div class="row">
            <div class="panel">
              <div class="panel-head">
                <h3>近 14 天日活 · 新增注册趋势</h3>
                <a>查看完整报表 →</a>
              </div>
              <div class="panel-body">
                <svg viewBox="0 0 640 220" preserveAspectRatio="none" style="width:100%;height:220px;">
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0" stop-color="#10b981" stop-opacity="0.3"/>
                      <stop offset="1" stop-color="#10b981" stop-opacity="0"/>
                    </linearGradient>
                  </defs>
                  <g stroke="#f3f4f6" stroke-width="1">
                    <line x1="0" y1="40" x2="640" y2="40"/>
                    <line x1="0" y1="90" x2="640" y2="90"/>
                    <line x1="0" y1="140" x2="640" y2="140"/>
                    <line x1="0" y1="190" x2="640" y2="190"/>
                  </g>
                  <path :d="dauArea" fill="url(#g1)"/>
                  <path :d="dauPath" stroke="#10b981" stroke-width="2" fill="none"/>
                  <path :d="regPath" stroke="#6366f1" stroke-width="2" fill="none" stroke-dasharray="4 4"/>
                  <g font-size="10" fill="#9ca3af" font-family="inherit">
                    <text x="0" y="38">16k</text>
                    <text x="0" y="88">12k</text>
                    <text x="0" y="138">8k</text>
                    <text x="0" y="188">4k</text>
                    <text v-for="(l, i) in [trend.labels[0], trend.labels[3], trend.labels[6], trend.labels[9], trend.labels[13]]"
                          :key="i"
                          :x="20 + i * 150"
                          y="210">{{ l }}</text>
                  </g>
                  <g font-size="11" font-family="inherit">
                    <circle cx="20" cy="14" r="4" fill="#10b981"/>
                    <text x="30" y="17" fill="#374151">DAU</text>
                    <circle cx="80" cy="14" r="4" fill="#6366f1"/>
                    <text x="90" y="17" fill="#374151">新增注册</text>
                  </g>
                </svg>
              </div>
            </div>
            <div class="panel">
              <div class="panel-head">
                <h3>最近动态</h3>
                <a>全部 →</a>
              </div>
              <div class="panel-body">
                <div v-for="a in acts" :key="a.id" class="act">
                  <div class="av" :style="{ background: a.av.bg }">{{ a.av.ch }}</div>
                  <div>
                    <div class="msg" v-html="a.msg"></div>
                    <div class="t">{{ a.time }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 省份热力 -->
          <div class="panel" style="margin-bottom:20px;">
            <div class="panel-head">
              <h3>各省份下载量 (近 30 天)</h3>
              <a>查看详细 →</a>
            </div>
            <div class="panel-body">
              <div class="heat">
                <div
                  v-for="p in provinces"
                  :key="p.name"
                  class="cell"
                  :style="{ background: p.share, color: p.downloads > 12000 ? '#fff' : '#065f46' }"
                >
                  {{ p.name }}<br><b>{{ (p.downloads/1000).toFixed(1) }}k</b>
                </div>
                <div class="cell">更多 17 个省 →</div>
              </div>
            </div>
          </div>

          <!-- 真题表 -->
          <div class="panel">
            <div class="panel-head">
              <h3>最近上传的真题 <span style="color:#9ca3af;font-weight:400;margin-left:6px;">(共 {{ fmt(stats.totalPapers) }} 份)</span></h3>
              <a @click="active = 'papers'">管理真题库 →</a>
            </div>
            <div class="filter">
              <span :class="['pill', { active: filterStatus==='all' }]"  @click="filterStatus='all'">全部</span>
              <span :class="['pill', { active: filterStatus==='warn' }]" @click="filterStatus='warn'">待审核 (23)</span>
              <span :class="['pill', { active: filterStatus==='ok' }]"   @click="filterStatus='ok'">已发布</span>
              <span :class="['pill', { active: filterStatus==='bad' }]"  @click="filterStatus='bad'">已下架</span>
              <div style="flex:1"></div>
              <select><option>全部省份</option><option>国考</option><option>广东</option></select>
              <select><option>全部科目</option><option>行测</option><option>申论</option></select>
              <input placeholder="搜索文件名..." style="width:180px;"/>
            </div>
            <table>
              <thead>
                <tr>
                  <th style="width:30px;"><input type="checkbox" class="check"/></th>
                  <th>文件名</th><th>省份</th><th>年份</th><th>科目</th>
                  <th>大小</th><th>下载量</th><th>状态</th><th>上传者</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in filteredPapers" :key="p.id">
                  <td><input type="checkbox" class="check"/></td>
                  <td style="color:#111827;font-weight:500;">{{ p.name }}</td>
                  <td>{{ p.province }}</td>
                  <td>{{ p.year }}</td>
                  <td>{{ p.subject }}</td>
                  <td>{{ p.size }}</td>
                  <td>{{ fmt(p.downloads) }}</td>
                  <td>
                    <span :class="['status', p.status]">
                      <span class="dot"></span>
                      {{ p.status === 'ok' ? '已发布' : p.status === 'warn' ? '待审核' : '已下架' }}
                    </span>
                  </td>
                  <td>{{ p.uploader }}</td>
                  <td class="row-actions">
                    <a v-if="p.status==='warn'">审核</a>
                    <a v-else>编辑</a>
                    <a>预览</a>
                    <a class="del">{{ p.status==='bad' ? '删除' : '下架' }}</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <!-- ===== 真题管理 ===== -->
        <template v-else-if="active === 'papers'">
          <div class="page-title">
            <h1>真题管理</h1>
            <span class="sub">共 {{ fmt(stats.totalPapers) }} 份真题，23 份待审核</span>
            <div class="spacer"></div>
            <button class="btn btn-ghost">📥 批量导入</button>
            <button class="btn btn-primary">+ 上传真题</button>
          </div>
          <div class="panel">
            <div class="filter">
              <span :class="['pill', { active: filterStatus==='all' }]"  @click="filterStatus='all'">全部</span>
              <span :class="['pill', { active: filterStatus==='warn' }]" @click="filterStatus='warn'">待审核 (23)</span>
              <span :class="['pill', { active: filterStatus==='ok' }]"   @click="filterStatus='ok'">已发布</span>
              <span :class="['pill', { active: filterStatus==='bad' }]"  @click="filterStatus='bad'">已下架</span>
              <div style="flex:1"></div>
              <select><option>全部省份</option></select>
              <select><option>全部科目</option></select>
              <input placeholder="搜索文件名..." style="width:180px;"/>
            </div>
            <table>
              <thead>
                <tr>
                  <th style="width:30px;"><input type="checkbox" class="check"/></th>
                  <th>文件名</th><th>省份</th><th>年份</th><th>科目</th>
                  <th>大小</th><th>下载量</th><th>状态</th><th>上传者</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in filteredPapers" :key="p.id">
                  <td><input type="checkbox" class="check"/></td>
                  <td style="color:#111827;font-weight:500;">{{ p.name }}</td>
                  <td>{{ p.province }}</td>
                  <td>{{ p.year }}</td>
                  <td>{{ p.subject }}</td>
                  <td>{{ p.size }}</td>
                  <td>{{ fmt(p.downloads) }}</td>
                  <td>
                    <span :class="['status', p.status]">
                      <span class="dot"></span>
                      {{ p.status === 'ok' ? '已发布' : p.status === 'warn' ? '待审核' : '已下架' }}
                    </span>
                  </td>
                  <td>{{ p.uploader }}</td>
                  <td class="row-actions">
                    <a>编辑</a><a>预览</a><a class="del">下架</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <!-- ===== 用户管理 ===== -->
        <template v-else-if="active === 'users'">
          <div class="page-title">
            <h1>用户管理</h1>
            <span class="sub">共 {{ fmt(stats.totalUsers) }} 位注册用户</span>
            <div class="spacer"></div>
            <button class="btn btn-ghost">📥 导出</button>
            <button class="btn btn-primary">+ 邀请用户</button>
          </div>
          <div class="panel">
            <table>
              <thead>
                <tr>
                  <th>用户 ID</th><th>昵称</th><th>套餐</th>
                  <th>注册日期</th><th>学习天数</th><th>状态</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in users" :key="u.id">
                  <td style="color:#111827;font-weight:500;">{{ u.id }}</td>
                  <td>{{ u.nickname }}</td>
                  <td>
                    <span :class="['status', u.plan === 'pro' ? 'ok' : 'warn']">
                      <span class="dot"></span>{{ u.plan === 'pro' ? '高级会员' : '免费' }}
                    </span>
                  </td>
                  <td>{{ u.joinedAt }}</td>
                  <td>{{ u.studyDays }}</td>
                  <td>
                    <span :class="['status', u.status === 'active' ? 'ok' : 'bad']">
                      <span class="dot"></span>{{ u.status === 'active' ? '活跃' : '不活跃' }}
                    </span>
                  </td>
                  <td class="row-actions">
                    <a>详情</a><a>重置密码</a><a class="del">封号</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <!-- ===== 占位 ===== -->
        <template v-else>
          <div class="page-title">
            <h1>{{ activeLabel }}</h1>
            <span class="sub">该模块仍在开发中</span>
          </div>
          <div class="panel" style="padding:80px 24px;text-align:center;">
            <div style="font-size:48px;margin-bottom:16px;">🚧</div>
            <h3 style="margin:0 0 8px;font-size:18px;color:#111827;">{{ activeLabel }} · 即将上线</h3>
            <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">这一模块的设计稿与功能正在打磨，预计下个版本上线。</p>
            <button class="btn btn-ghost" @click="active = 'dashboard'">← 返回仪表盘</button>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; background: #f5f6f8; }

/* ===== Sidebar ===== */
.side { background: #0f172a; color: #cbd5e1; padding: 18px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
.side .brand { display: flex; align-items: center; gap: 10px; padding: 4px 20px 22px; border-bottom: 1px solid #1e293b; margin-bottom: 14px; cursor: pointer; }
.side .brand .t { color: #fff; font-weight: 700; font-size: 15px; }
.side .brand .sub { color: #64748b; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; margin-top: 2px; }
.side .grp { font-size: 10px; letter-spacing: .12em; color: #64748b; text-transform: uppercase; padding: 12px 20px 6px; }
.side a { display: flex; align-items: center; gap: 10px; padding: 9px 20px; color: #cbd5e1; font-size: 13.5px; text-decoration: none; border-left: 3px solid transparent; cursor: pointer; }
.side a:hover { background: #1e293b; color: #fff; }
.side a.active { background: #064e3b; color: #fff; border-left-color: #10b981; }
.side a .ic { width: 18px; display: inline-flex; justify-content: center; font-size: 15px; opacity: .9; }
.side a .badge { margin-left: auto; font-size: 10px; padding: 1px 6px; border-radius: 10px; background: #dc2626; color: #fff; }

/* ===== Topbar ===== */
.top { display: flex; align-items: center; gap: 16px; padding: 14px 28px; background: #fff; border-bottom: 1px solid #e5e7eb; position: sticky; top: 0; z-index: 10; }
.crumb { font-size: 13px; color: #6b7280; }
.crumb b { color: #111827; }
.search { flex: 1; max-width: 420px; }
.search input { width: 100%; padding: 8px 14px 8px 34px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 13px; font-family: inherit; outline: 0; background: #f9fafb url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2'><circle cx='11' cy='11' r='8'/><line x1='21' y1='21' x2='16.65' y2='16.65'/></svg>") no-repeat 12px center; }
.top-right { display: flex; align-items: center; gap: 14px; font-size: 13px; color: #6b7280; }
.top-right .bell { position: relative; cursor: pointer; font-size: 17px; }
.top-right .bell::after { content: ""; position: absolute; top: -2px; right: -2px; width: 7px; height: 7px; background: #ef4444; border-radius: 50%; border: 1.5px solid #fff; }
.top-right .me { display: flex; align-items: center; gap: 8px; }
.top-right .me .av { width: 30px; height: 30px; border-radius: 50%; background: #10b981; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }

/* ===== Content ===== */
.content { padding: 24px 28px 48px; }
.page-title { display: flex; align-items: flex-end; margin-bottom: 20px; gap: 16px; }
.page-title h1 { font-size: 22px; font-weight: 600; color: #111827; margin: 0; letter-spacing: -.01em; }
.page-title .sub { font-size: 13px; color: #6b7280; margin-left: 12px; }
.page-title .spacer { flex: 1; }

.btn { border: 0; font-family: inherit; font-weight: 500; font-size: 13px; padding: 8px 16px; border-radius: 7px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all .15s; }
.btn-primary { background: #10b981; color: #fff; }
.btn-primary:hover { background: #059669; }
.btn-ghost { background: #fff; border: 1px solid #e5e7eb; color: #374151; }
.btn-ghost:hover { background: #f9fafb; }

/* Stats */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.stat { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 18px 20px; position: relative; overflow: hidden; }
.stat .label { font-size: 12px; color: #6b7280; margin-bottom: 10px; }
.stat .n { font-size: 28px; font-weight: 700; color: #111827; letter-spacing: -.02em; line-height: 1; }
.stat .delta { font-size: 11px; margin-top: 8px; display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 10px; }
.stat .delta.up { background: #d1fae5; color: #047857; }
.stat .delta.down { background: #fee2e2; color: #b91c1c; }
.stat .ico { position: absolute; top: 18px; right: 18px; width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 16px; }

/* Row */
.row { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; margin-bottom: 20px; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; }
.panel-head { display: flex; align-items: center; padding: 14px 18px; border-bottom: 1px solid #f3f4f6; }
.panel-head h3 { font-size: 14px; font-weight: 600; color: #111827; margin: 0; flex: 1; }
.panel-head a { font-size: 12px; color: #10b981; cursor: pointer; text-decoration: none; }
.panel-body { padding: 18px; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { text-align: left; font-weight: 500; color: #6b7280; font-size: 12px; padding: 10px 18px; background: #f9fafb; border-bottom: 1px solid #e5e7eb; }
tbody td { padding: 12px 18px; border-bottom: 1px solid #f3f4f6; color: #374151; }
tbody tr:hover { background: #f9fafb; }
.check { accent-color: #10b981; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; padding: 2px 10px; border-radius: 10px; font-weight: 500; }
.status.ok { background: #d1fae5; color: #047857; }
.status.warn { background: #fef3c7; color: #a16207; }
.status.bad { background: #fee2e2; color: #b91c1c; }
.status .dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.row-actions a { color: #6b7280; margin-right: 10px; font-size: 12px; cursor: pointer; text-decoration: none; }
.row-actions a:hover { color: #10b981; }
.row-actions a.del:hover { color: #dc2626; }

/* Filter bar */
.filter { display: flex; gap: 8px; padding: 12px 18px; border-bottom: 1px solid #f3f4f6; align-items: center; flex-wrap: wrap; }
.filter input, .filter select { padding: 6px 10px; font-size: 12.5px; border: 1px solid #e5e7eb; border-radius: 6px; font-family: inherit; background: #fff; }
.filter .pill { padding: 4px 12px; font-size: 12px; border-radius: 999px; background: #f3f4f6; color: #374151; cursor: pointer; border: 1px solid transparent; }
.filter .pill.active { background: #d1fae5; color: #047857; border-color: #a7f3d0; font-weight: 500; }

/* Activity list */
.act { display: flex; gap: 10px; padding: 10px 0; border-top: 1px solid #f3f4f6; }
.act:first-child { border-top: 0; padding-top: 0; }
.act .av { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.act .msg { font-size: 13px; color: #374151; line-height: 1.55; }
.act .msg :deep(b) { color: #111827; font-weight: 600; }
.act .t { font-size: 11px; color: #9ca3af; margin-top: 2px; }

/* Heat */
.heat { display: grid; grid-template-columns: repeat(8, 1fr); gap: 6px; }
.heat .cell { padding: 8px 0; border-radius: 6px; text-align: center; font-size: 11.5px; font-weight: 500; background: #ecfdf5; color: #065f46; }
.heat .cell b { font-size: 13px; }
</style>
