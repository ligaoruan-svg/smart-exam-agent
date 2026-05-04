<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProvinces, fetchPlans } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const userInitial = computed(() => {
  const u = auth.user?.username
  return u ? u.charAt(0).toUpperCase() : ''
})
const provinces = ref([])
const plans = ref([])

const features = [
  { icon: '🤖', cls: 'i', title: 'AI 智能问答',  desc: '接入 DeepSeek 大模型，理解公考题目并给出清晰解析。自动识别意图，无需繁琐提示。' },
  { icon: '🎲', cls: 'v', title: '随机出题练习', desc: '按省份、科目、题数自定义配置，一键生成专属练习卷。支持行测、申论、常识全科。' },
  { icon: '📦', cls: 'g', title: '真题免费下载', desc: '31 省 + 国考共 2,579 份真题，PDF 单份或省份 ZIP 包下载，随时备考、离线复习。' },
  { icon: '📒', cls: 'r', title: '错题自动归类', desc: '做错的题自动进错题本，按知识点聚类，支持定期重做 · 遵循艾宾浩斯复习曲线。' },
  { icon: '📅', cls: 'a', title: '学习计划',     desc: '根据目标省份和考试日期自动排课，每日推送今日重点，完成率可视化。' },
  { icon: '📊', cls: 'b', title: '数据分析',     desc: '每科目、每模块正确率一目了然，薄弱环节针对性训练，每次进步都看得见。' }
]

const testimonials = [
  { stars: 5, q: 'AI 出题功能太好用了，可以按省份按题型配置，上岸前三个月基本没离开过这个 App。最后成功上岸广东省考。', name: '王同学', sub: '广东省考 · 综合管理 · 已上岸', avatar: '王', bg: '#10b981' },
  { stars: 5, q: '真题下载全部免费真的很良心，其他 App 都要会员。错题本按知识点自动归类这点比我自己整理还强。',         name: '李同学', sub: '国考 · 副省级 · 备考中',     avatar: '李', bg: '#6366f1' },
  { stars: 5, q: '问 AI 数量关系的题比刷视频课省时间多了，思考过程也能看到，不是黑盒。申论范文也能解析到点上。',     name: '张同学', sub: '江苏省考 · 备考 120 天',     avatar: '张', bg: '#f59e0b' }
]

onMounted(async () => {
  provinces.value = (await fetchProvinces()).slice(0, 16)
  plans.value = await fetchPlans()
})

const goLogin    = () => router.push('/login')
const goRegister = () => router.push('/login')
const goApp      = () => router.push('/chat')
const goPricing  = () => router.push('/pricing')
const goDownload = () => router.push('/download')
</script>

<template>
  <div class="landing">
    <!-- NAV -->
    <nav class="nav">
      <div class="container row">
        <div class="nav-logo">
          <img src="/logo-mark.svg" width="32" height="32" style="border-radius:8px"/>
          公考小智
        </div>
        <div class="nav-links">
          <a href="#features">功能</a>
          <a href="#showcase">产品演示</a>
          <a href="#provinces">真题库</a>
          <a href="#testimonials">用户评价</a>
          <a href="#download">下载</a>
        </div>
        <div class="nav-cta">
          <!-- 未登录：显示登录/注册按钮 -->
          <template v-if="!auth.isLoggedIn">
            <button class="btn btn-ghost" @click="goLogin">登录</button>
            <button class="btn btn-primary" @click="goRegister">免费使用</button>
          </template>
          <!-- 已登录：用户信息 + 进入应用 -->
          <template v-else>
            <div class="nav-user-card" @click="goApp">
              <div class="nav-avatar">{{ userInitial }}</div>
              <div class="nav-user-info">
                <div class="nav-user-name">{{ auth.user?.username || '同学' }}</div>
                <div class="nav-user-sub">点击进入应用</div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </nav>

    <!-- HERO -->
    <section class="hero">
      <div class="container hero-grid">
        <div>
          <div class="pill"><span class="dot"></span>AI 驱动 · 覆盖 32 省份</div>
          <h1>你的公考备考 <span class="hl">智慧搭子</span><br>从刷题开始</h1>
          <p class="lead">2,579 份历年真题免费下载，AI 助教 7×24 随问随答，精准出题、智能整理错题，让每分钟复习都更高效。</p>
          <div class="hero-cta">
            <button class="btn btn-primary btn-lg" @click="goApp">立即免费体验 →</button>
            <button class="btn btn-ghost btn-lg">▶ 观看演示</button>
          </div>
          <div class="hero-trust">
            <div class="avatars">
              <div class="a" style="background:#10b981">王</div>
              <div class="a" style="background:#6366f1">李</div>
              <div class="a" style="background:#f59e0b">张</div>
              <div class="a" style="background:#ef4444">陈</div>
              <div class="a" style="background:#8b5cf6;font-size:10px">+9k</div>
            </div>
            <div>已有 <b style="color:var(--gk-gray-700)">86,420+</b> 考生使用 · ⭐ 4.9</div>
          </div>
        </div>
        <div class="hero-visual">
          <div class="float f1">
            <div class="ic" style="background:var(--gk-green-50);color:var(--gk-green-600)">✓</div>
            <div>
              <div style="font-weight:600;color:var(--gk-gray-900)">今日已完成</div>
              <div style="color:var(--gk-gray-500)">30 / 30 题 · 正确率 83%</div>
            </div>
          </div>
          <div class="card-frame">
            <div class="card-head">📚 AI 对话测试 – 公考小智</div>
            <div class="msg right"><div class="b">我要出20道广东行测题</div><div class="av me">你</div></div>
            <div class="msg"><div class="av ai">智</div><div class="b">好的! 确认一下：<br>· 省份：广东<br>· 科目：行测<br>· 数量：20 道<br>60 秒内生成 PDF ✓</div></div>
            <div class="msg right"><div class="b">开始</div><div class="av me">你</div></div>
          </div>
          <div class="float f2">
            <div class="ic" style="background:var(--gk-indigo-50);color:var(--gk-indigo-600)">⚡</div>
            <div>
              <div style="font-weight:600;color:var(--gk-gray-900)">AI 响应 5.9 秒</div>
              <div style="color:var(--gk-gray-500)">DeepSeek 驱动</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- STATS -->
    <section class="stats">
      <div class="container stats-grid">
        <div class="stat"><div class="n">2,579</div><div class="l">历年真题</div></div>
        <div class="stat"><div class="n">32</div><div class="l">省份覆盖</div></div>
        <div class="stat"><div class="n">86,420+</div><div class="l">考生在学</div></div>
        <div class="stat"><div class="n">100%</div><div class="l">免费下载</div></div>
      </div>
    </section>

    <!-- FEATURES -->
    <section class="block" id="features">
      <div class="container">
        <div class="sec-head">
          <div class="eyebrow">核心功能</div>
          <h2>一个 App，搞定公考备考</h2>
          <p>从真题下载到 AI 讲解，从每日刷题到错题复盘，全流程覆盖 · 全部免费</p>
        </div>
        <div class="features">
          <div class="feat" v-for="f in features" :key="f.title">
            <div :class="['ficon', f.cls]">{{ f.icon }}</div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- SHOWCASES -->
    <section class="block" id="showcase" style="background:#fafafa">
      <div class="container">
        <div class="sec-head">
          <div class="eyebrow">产品演示</div>
          <h2>简洁好用，专注备考本身</h2>
        </div>

        <div class="showcase">
          <div class="text">
            <div class="eyebrow">AI 对话</div>
            <h3>像跟老师聊天一样，解答每道难题</h3>
            <p>不用翻书、不用百度。一句话提问，AI 自动识别意图、调用题库并给出讲解，响应平均仅需 6 秒。</p>
            <ul class="bullets">
              <li><span class="check">✓</span> 支持多轮上下文，追问不掉线</li>
              <li><span class="check">✓</span> 自动展示"思考过程"，结果可追溯</li>
              <li><span class="check">✓</span> 一键清空 / 重开对话</li>
            </ul>
          </div>
          <div class="mockup">
            <div class="mockup-head">
              <div class="d" style="background:#ef4444"></div>
              <div class="d" style="background:#f59e0b"></div>
              <div class="d" style="background:#10b981"></div>
            </div>
            <div class="mockup-body" style="background:#f3f4f6">
              <div class="msg right"><div class="b">追及问题怎么解?</div><div class="av me">你</div></div>
              <div class="msg"><div class="av ai">智</div><div class="b">✓ 已思考 (5.9 秒)<br>追及问题核心: <b>速度差 × 时间 = 距离差</b>。常见题型有三类...</div></div>
              <div class="msg right"><div class="b">举个例题</div><div class="av me">你</div></div>
            </div>
          </div>
        </div>

        <div class="showcase rev">
          <div class="mockup">
            <div class="mockup-head">
              <div class="d" style="background:#ef4444"></div>
              <div class="d" style="background:#f59e0b"></div>
              <div class="d" style="background:#10b981"></div>
            </div>
            <div class="mockup-body">
              <div style="display:flex;gap:10px;margin-bottom:14px;">
                <div style="flex:1;padding:8px 12px;border:1px solid var(--gk-gray-200);border-radius:8px;font-size:13px;">20 题</div>
                <div style="flex:1;padding:8px 12px;border:1px solid var(--gk-gray-200);border-radius:8px;font-size:13px;">行测</div>
                <div style="flex:1;padding:8px 12px;border:1px solid var(--gk-gray-200);border-radius:8px;font-size:13px;">广东</div>
              </div>
              <div style="padding:16px;border:1px solid var(--gk-gray-200);border-radius:10px;background:#fafafa;">
                <div style="font-size:11px;color:var(--gk-gray-500);margin-bottom:8px;">第 1 / 20 题</div>
                <div style="font-size:13px;color:var(--gk-gray-900);line-height:1.6;margin-bottom:12px;">甲乙两人同时出发，甲速度是乙的 1.5 倍，到达终点时乙还剩 20 公里...</div>
                <div style="display:flex;flex-direction:column;gap:6px">
                  <div style="padding:7px 12px;background:#fff;border:1px solid var(--gk-gray-200);border-radius:6px;font-size:12px;">A. 40 公里</div>
                  <div style="padding:7px 12px;background:var(--gk-green-50);border:1px solid var(--gk-green-400);border-radius:6px;font-size:12px;color:var(--gk-green-700);">C. 60 公里 ✓</div>
                </div>
              </div>
            </div>
          </div>
          <div class="text">
            <div class="eyebrow">随机出题</div>
            <h3>按省份、科目定制，专属题目瞬间生成</h3>
            <p>告别盲目刷题，按你的目标岗位出题。每道题配套解析和知识点，错题自动归档。</p>
            <ul class="bullets">
              <li><span class="check">✓</span> 覆盖 32 省份 · 五大模块</li>
              <li><span class="check">✓</span> 计时作答、难度自动平衡</li>
              <li><span class="check">✓</span> 做错即入错题本</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- PROVINCES -->
    <section class="block" id="provinces">
      <div class="container">
        <div class="sec-head">
          <div class="eyebrow">真题库</div>
          <h2>31 省 + 国考，2,579 份真题全部免费</h2>
          <p>覆盖近十年历年真题 · PDF 单份下载或按省份打包 · 持续每周更新</p>
        </div>
        <div class="prov-grid">
          <div
            v-for="p in provinces"
            :key="p.name"
            :class="['prov', { hot: p.hot }]"
            @click="goDownload"
          >
            <div class="n">{{ p.name }}</div>
            <div class="c">{{ p.count }} 份</div>
          </div>
          <div class="prov" @click="goDownload">
            <div class="n">更多</div>
            <div class="c">16 省 →</div>
          </div>
        </div>
        <div style="text-align:center;margin-top:32px;">
          <button class="btn btn-primary btn-lg" @click="goDownload">浏览全部真题库 →</button>
        </div>
      </div>
    </section>

    <!-- TESTIMONIALS -->
    <section class="block" id="testimonials" style="background:#fafafa">
      <div class="container">
        <div class="sec-head">
          <div class="eyebrow">用户评价</div>
          <h2>86,420+ 考生正在使用</h2>
        </div>
        <div class="tgrid">
          <div class="tcard" v-for="(t, i) in testimonials" :key="i">
            <div class="stars">{{ '★'.repeat(t.stars) }}</div>
            <p class="q">"{{ t.q }}"</p>
            <div class="who">
              <div class="av" :style="{ background: t.bg }">{{ t.avatar }}</div>
              <div>
                <div class="name">{{ t.name }}</div>
                <div class="sub">{{ t.sub }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- PRICING TEASE -->
    <section class="block" style="padding:64px 0;">
      <div class="container">
        <div class="sec-head">
          <div class="eyebrow">付费方案</div>
          <h2>免费够用，进阶随心</h2>
          <p>免费版即可下载全部真题；高级会员解锁 AI 不限次数、申论批改、智能学习计划。</p>
        </div>
        <div style="text-align:center;">
          <button class="btn btn-primary btn-lg" @click="goPricing">查看会员方案 →</button>
        </div>
      </div>
    </section>

    <!-- CTA / DOWNLOAD -->
    <section class="block" id="download">
      <div class="container">
        <div class="cta-block">
          <div>
            <h2>现在开始，免费备考</h2>
            <p>支持 iOS · Android · 微信小程序 · Web 端 — 多端数据实时同步，进度永不丢失。</p>
            <div class="dl-row">
              <a class="dl-btn"><div class="ic">🍎</div><div class="label"><div class="s">下载 App</div><div class="b">App Store</div></div></a>
              <a class="dl-btn"><div class="ic">🤖</div><div class="label"><div class="s">下载 App</div><div class="b">Android APK</div></div></a>
              <a class="dl-btn" @click="goApp"><div class="ic">💻</div><div class="label"><div class="s">网页版</div><div class="b">立即使用</div></div></a>
            </div>
          </div>
          <div class="qr">
            <div class="qr-box"></div>
            <div class="t">扫码打开微信小程序</div>
          </div>
        </div>
      </div>
    </section>

    <!-- FOOTER -->
    <footer>
      <div class="container">
        <div class="foot-grid">
          <div class="foot-col">
            <div class="foot-brand">
              <img src="/logo-mark.svg" width="28" height="28" style="border-radius:6px"/>
              公考小智
            </div>
            <div class="foot-desc">你的公考备考智慧搭子。AI 驱动 · 真题免费 · 全流程陪跑。</div>
          </div>
          <div class="foot-col">
            <h4>产品</h4>
            <ul><li><a>AI 对话</a></li><li><a>随机出题</a></li><li><a>真题下载</a></li><li><a>错题本</a></li><li><a>学习计划</a></li></ul>
          </div>
          <div class="foot-col">
            <h4>资源</h4>
            <ul><li><a>帮助中心</a></li><li><a>备考指南</a></li><li><a>考试时间表</a></li><li><a>更新日志</a></li></ul>
          </div>
          <div class="foot-col">
            <h4>关于</h4>
            <ul><li><a>关于我们</a></li><li><a>联系方式</a></li><li><a>用户协议</a></li><li><a>隐私政策</a></li></ul>
          </div>
        </div>
        <div class="foot-bottom">
          <div>© 2026 公考小智. 保留所有权利.</div>
          <div>京 ICP 备 2026XXXXXX 号</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing { background: #fff; }
.container { max-width: 1120px; margin: 0 auto; padding: 0 24px; }
a { color: inherit; text-decoration: none; }
ul { padding-left: 0; margin: 0; }

/* Nav */
.nav { position: sticky; top: 0; z-index: 50; background: rgba(255,255,255,.9); backdrop-filter: blur(10px); border-bottom: 1px solid var(--gk-gray-200); }
.nav .row { display: flex; align-items: center; gap: 36px; height: 64px; }
.nav-logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 17px; color: var(--gk-gray-900); }
.nav-links { display: flex; gap: 28px; flex: 1; }
.nav-links a { font-size: 14px; color: var(--gk-gray-600); font-weight: 500; cursor: pointer; }
.nav-links a:hover { color: var(--gk-green-600); }
.nav-cta { display: flex; gap: 10px; align-items: center; }

/* 已登录用户卡片 */
.nav-user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 14px 5px 6px;
  border-radius: 40px;
  border: 1.5px solid var(--gk-green-200);
  background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
  cursor: pointer;
  transition: all .2s;
  user-select: none;
}
.nav-user-card:hover {
  border-color: var(--gk-green-400);
  background: linear-gradient(135deg, #dcfce7, #d1fae5);
  box-shadow: 0 4px 12px rgba(16,185,129,.15);
  transform: translateY(-1px);
}
.nav-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--gk-green-500), var(--gk-green-600));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(16,185,129,.4);
}
.nav-user-info { display: flex; flex-direction: column; gap: 1px; }
.nav-user-name { font-size: 13px; font-weight: 600; color: var(--gk-gray-800); line-height: 1.2; }
.nav-user-sub { font-size: 11px; color: var(--gk-green-600); font-weight: 500; line-height: 1.2; }

.btn { border: 0; font-family: inherit; font-weight: 500; font-size: 14px; padding: 9px 18px; border-radius: 8px; cursor: pointer; transition: all .18s; display: inline-flex; align-items: center; gap: 6px; }
.btn-primary { background: var(--gk-green-500); color: #fff; }
.btn-primary:hover { background: var(--gk-green-600); }
.btn-ghost { background: transparent; border: 1px solid var(--gk-gray-300); color: var(--gk-gray-700); }
.btn-ghost:hover { background: var(--gk-gray-50); }
.btn-lg { padding: 13px 26px; font-size: 15px; border-radius: 10px; }

/* Hero */
.hero { background: linear-gradient(180deg, #ecfdf5 0%, #fff 100%); padding: 72px 0 96px; position: relative; overflow: hidden; }
.hero-grid { display: grid; grid-template-columns: 1.05fr 1fr; gap: 48px; align-items: center; }
.pill { display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1px solid var(--gk-green-200); color: var(--gk-green-700); font-size: 12px; font-weight: 500; padding: 5px 12px; border-radius: 9999px; margin-bottom: 20px; }
.pill .dot { width: 6px; height: 6px; background: var(--gk-green-500); border-radius: 50%; }
.hero h1 { font-size: 44px; font-weight: 800; line-height: 1.15; letter-spacing: -.02em; color: var(--gk-gray-900); margin: 0 0 20px; }
.hero h1 .hl { color: var(--gk-green-600); }
.hero p.lead { font-size: 17px; line-height: 1.7; color: var(--gk-gray-600); margin: 0 0 28px; max-width: 520px; }
.hero-cta { display: flex; gap: 12px; margin-bottom: 28px; }
.hero-trust { display: flex; gap: 24px; font-size: 12px; color: var(--gk-gray-500); align-items: center; }
.avatars { display: flex; }
.avatars .a { width: 28px; height: 28px; border-radius: 50%; border: 2px solid #fff; margin-left: -8px; font-size: 11px; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 600; }
.hero-visual { position: relative; padding: 28px 32px; }
.hero-visual .card-frame { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 16px; padding: 18px; box-shadow: 0 20px 40px -12px rgba(17,24,39,.1); }
.hero-visual .card-head { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: var(--gk-gray-900); padding-bottom: 12px; border-bottom: 1px solid var(--gk-gray-100); margin-bottom: 14px; }

.msg { display: flex; gap: 10px; margin-bottom: 12px; }
.msg.right { justify-content: flex-end; }
.msg .av { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.msg .av.ai { background: var(--gk-indigo-600); }
.msg .av.me { background: var(--gk-green-500); }
.msg .b { padding: 8px 12px; border-radius: 14px; font-size: 13px; line-height: 1.5; max-width: 320px; }
.msg.right .b { background: var(--gk-blue-600); color: #fff; border-top-right-radius: 3px; }
.msg:not(.right) .b { background: var(--gk-gray-50); color: var(--gk-gray-800); border: 1px solid var(--gk-gray-200); border-top-left-radius: 3px; }

.float { position: absolute; background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 12px; padding: 10px 14px; box-shadow: 0 10px 20px rgba(17,24,39,.08); font-size: 12px; display: flex; align-items: center; gap: 8px; animation: floaty 3.6s ease-in-out infinite; }
@keyframes floaty { 0%,100%{ transform: translateY(0); } 50%{ transform: translateY(-8px); } }
.float.f1 { top: -6px; left: -28px; animation-delay: 0s; }
.float.f2 { bottom: -6px; right: -28px; animation-delay: 1.5s; }
.float .ic { width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; }

/* Stats */
.stats { border-top: 1px solid var(--gk-gray-100); border-bottom: 1px solid var(--gk-gray-100); padding: 36px 0; background: #fafafa; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; text-align: center; }
.stat .n { font-size: 36px; font-weight: 800; color: var(--gk-green-600); letter-spacing: -.02em; line-height: 1; }
.stat .l { font-size: 13px; color: var(--gk-gray-500); margin-top: 8px; }

/* Sections */
section.block { padding: 88px 0; }
.sec-head { text-align: center; margin-bottom: 56px; }
.sec-head .eyebrow { font-size: 13px; color: var(--gk-green-600); font-weight: 600; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 12px; }
.sec-head h2 { font-size: 36px; font-weight: 700; color: var(--gk-gray-900); letter-spacing: -.01em; margin: 0 0 12px; line-height: 1.2; }
.sec-head p { font-size: 15px; color: var(--gk-gray-500); max-width: 540px; margin: 0 auto; line-height: 1.7; }

/* Features */
.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.feat { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 14px; padding: 28px 24px; transition: all .2s; }
.feat:hover { border-color: var(--gk-green-300); transform: translateY(-2px); box-shadow: 0 10px 20px -4px rgba(16,185,129,.1); }
.feat .ficon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; margin-bottom: 18px; }
.feat .ficon.g { background: var(--gk-green-50); color: var(--gk-green-600); }
.feat .ficon.b { background: var(--gk-blue-50); color: var(--gk-blue-600); }
.feat .ficon.i { background: var(--gk-indigo-50); color: var(--gk-indigo-600); }
.feat .ficon.v { background: var(--gk-violet-50); color: var(--gk-violet-600); }
.feat .ficon.a { background: var(--gk-amber-50); color: var(--gk-amber-600); }
.feat .ficon.r { background: var(--gk-red-50); color: var(--gk-red-600); }
.feat h3 { font-size: 18px; font-weight: 600; color: var(--gk-gray-900); margin: 0 0 8px; }
.feat p { font-size: 13.5px; color: var(--gk-gray-500); line-height: 1.7; margin: 0; }

/* Showcase */
.showcase { display: grid; grid-template-columns: 1fr 1fr; gap: 72px; align-items: center; margin-bottom: 88px; }
.showcase.rev .text { order: 2; }
.showcase .text h3 { font-size: 30px; font-weight: 700; color: var(--gk-gray-900); line-height: 1.25; margin: 12px 0 16px; letter-spacing: -.01em; }
.showcase .text p { font-size: 15px; color: var(--gk-gray-600); line-height: 1.8; margin: 0 0 20px; }
.showcase .text .bullets { display: flex; flex-direction: column; gap: 10px; margin: 20px 0 24px; }
.showcase .text .bullets li { display: flex; align-items: flex-start; gap: 10px; font-size: 14px; color: var(--gk-gray-700); list-style: none; }
.showcase .text .bullets .check { width: 20px; height: 20px; border-radius: 50%; background: var(--gk-green-500); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; margin-top: 1px; }
.showcase .text .eyebrow { font-size: 12px; color: var(--gk-green-600); font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
.mockup { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px -12px rgba(17,24,39,.08); }
.mockup-head { display: flex; gap: 6px; padding: 12px 14px; border-bottom: 1px solid var(--gk-gray-100); background: var(--gk-gray-50); }
.mockup-head .d { width: 10px; height: 10px; border-radius: 50%; }
.mockup-body { padding: 20px; min-height: 260px; }

/* Province strip */
.prov-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; }
.prov { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 10px; padding: 12px 8px; text-align: center; transition: all .18s; cursor: pointer; position: relative; }
.prov:hover { border-color: var(--gk-green-400); background: var(--gk-green-50); }
.prov .n { font-size: 14px; font-weight: 600; color: var(--gk-gray-900); }
.prov .c { font-size: 11px; color: var(--gk-gray-500); margin-top: 2px; }
.prov.hot::after { content: "热"; position: absolute; top: 4px; right: 4px; font-size: 9px; padding: 1px 4px; border-radius: 3px; background: var(--gk-red-500); color: #fff; font-weight: 600; }

/* Testimonials */
.tgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.tcard { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 14px; padding: 24px; }
.tcard .stars { color: var(--gk-amber-500); margin-bottom: 12px; font-size: 14px; letter-spacing: 2px; }
.tcard .q { font-size: 14px; line-height: 1.7; color: var(--gk-gray-700); margin: 0 0 18px; }
.tcard .who { display: flex; align-items: center; gap: 10px; }
.tcard .who .av { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 13px; font-weight: 600; }
.tcard .who .name { font-size: 13px; font-weight: 600; color: var(--gk-gray-900); }
.tcard .who .sub { font-size: 11px; color: var(--gk-gray-500); margin-top: 1px; }

/* CTA */
.cta-block { background: linear-gradient(135deg, #059669 0%, #047857 100%); border-radius: 20px; padding: 56px; color: #fff; display: grid; grid-template-columns: 1.2fr 1fr; gap: 40px; align-items: center; position: relative; overflow: hidden; }
.cta-block::before { content: ""; position: absolute; top: -40%; right: -10%; width: 400px; height: 400px; border-radius: 50%; background: rgba(255,255,255,.05); }
.cta-block h2 { font-size: 32px; font-weight: 700; margin: 0 0 12px; line-height: 1.25; }
.cta-block p { font-size: 14px; opacity: .92; line-height: 1.7; margin: 0 0 24px; }
.dl-row { display: flex; gap: 10px; flex-wrap: wrap; }
.dl-btn { background: #fff; color: var(--gk-gray-900); border-radius: 12px; padding: 10px 14px; display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 500; transition: all .18s; cursor: pointer; text-decoration: none; white-space: nowrap; }
.dl-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,.15); }
.dl-btn .ic { font-size: 22px; flex-shrink: 0; }
.dl-btn .label { display: flex; flex-direction: column; gap: 1px; align-items: flex-start; white-space: nowrap; }
.dl-btn .label .s { font-size: 10px; color: var(--gk-gray-500); }
.dl-btn .label .b { font-size: 13px; font-weight: 600; }
.qr { background: #fff; padding: 16px; border-radius: 16px; text-align: center; position: relative; z-index: 1; }
.qr-box { width: 140px; height: 140px; background: repeating-conic-gradient(#111 0 25%, #fff 0 50%) 50% / 14px 14px; border-radius: 8px; margin: 0 auto 10px; position: relative; }
.qr-box::before, .qr-box::after { content: ""; position: absolute; width: 28px; height: 28px; background: #fff; border: 4px solid #111; border-radius: 3px; }
.qr-box::before { top: 6px; left: 6px; }
.qr-box::after  { top: 6px; right: 6px; }
.qr .t { font-size: 12px; color: var(--gk-gray-700); font-weight: 500; }

/* Footer */
footer { background: var(--gk-gray-900); color: var(--gk-gray-400); padding: 56px 0 28px; font-size: 13px; }
.foot-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 40px; margin-bottom: 36px; }
.foot-col h4 { font-size: 13px; color: #fff; font-weight: 600; margin: 0 0 14px; }
.foot-col ul { display: flex; flex-direction: column; gap: 8px; list-style: none; }
.foot-col a { color: var(--gk-gray-400); cursor: pointer; }
.foot-col a:hover { color: #fff; }
.foot-brand { display: flex; align-items: center; gap: 10px; color: #fff; font-weight: 700; font-size: 16px; margin-bottom: 12px; }
.foot-desc { color: var(--gk-gray-500); line-height: 1.7; max-width: 280px; }
.foot-bottom { border-top: 1px solid #374151; padding-top: 24px; display: flex; justify-content: space-between; color: var(--gk-gray-500); font-size: 12px; }

@media (max-width: 900px) {
  .hero-grid, .showcase, .cta-block, .foot-grid { grid-template-columns: 1fr; gap: 36px; }
  .hero h1 { font-size: 36px; }
  .features, .tgrid { grid-template-columns: 1fr; }
  .prov-grid { grid-template-columns: repeat(4, 1fr); }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .showcase.rev .text { order: 0; }
}
</style>