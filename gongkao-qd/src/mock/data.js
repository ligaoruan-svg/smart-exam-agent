// ===== 假数据中心 — 所有页面共用 =====

export const stats = {
  totalUsers: 86420,
  dau: 12308,
  totalPapers: 2579,
  aiCalls: 48621,
  deltas: { totalUsers: 12.4, dau: 5.1, totalPapers: 23, aiCalls: -2.3 }
}

export const trend14d = {
  dau:      [9000,  9800, 10200, 10400, 10100, 10800, 11000, 11500, 11200, 12000, 11800, 12200, 12100, 12308],
  newUsers: [380,   410,  450,   480,   460,   520,   540,   580,   570,   620,   650,   680,   720,   760],
  labels: ['04-11','04-12','04-13','04-14','04-15','04-16','04-17','04-18','04-19','04-20','04-21','04-22','04-23','04-24']
}

export const provinces = [
  { name: '国考', count: 412, downloads: 28400, hot: true,  share: '#047857' },
  { name: '广东', count: 104, downloads: 18200, hot: true,  share: '#059669' },
  { name: '江苏', count:  88, downloads: 15600, hot: true,  share: '#10b981' },
  { name: '山东', count:  92, downloads: 14900, hot: true,  share: '#10b981' },
  { name: '浙江', count:  81, downloads: 12300, hot: false, share: '#34d399' },
  { name: '北京', count:  58, downloads:  9800, hot: false, share: '#6ee7b7' },
  { name: '上海', count:  62, downloads:  9100, hot: false, share: '#6ee7b7' },
  { name: '四川', count:  84, downloads:  8700, hot: false, share: '#6ee7b7' },
  { name: '河南', count:  86, downloads:  7200, hot: false, share: '#a7f3d0' },
  { name: '湖北', count:  78, downloads:  6800, hot: false, share: '#a7f3d0' },
  { name: '安徽', count:  74, downloads:  6100, hot: false, share: '#a7f3d0' },
  { name: '福建', count:  69, downloads:  5300, hot: false, share: '#d1fae5' },
  { name: '湖南', count:  76, downloads:  4800, hot: false, share: '#d1fae5' },
  { name: '河北', count:  72, downloads:  4600, hot: false, share: '#d1fae5' },
  { name: '陕西', count:  68, downloads:  4100, hot: false, share: '#d1fae5' }
]

export const recentPapers = [
  { id: 'p001', name: '2024 年广东省公务员考试行测真题 (含解析).pdf', province: '广东', year: 2024, subject: '行测', size: '4.2 MB', downloads: 18240, status: 'ok',   uploader: '张老师' },
  { id: 'p002', name: '2024 年国考行测副省级真题.pdf',                 province: '国考', year: 2024, subject: '行测', size: '5.1 MB', downloads: 28410, status: 'ok',   uploader: '张老师' },
  { id: 'p003', name: '2023 年江苏省考申论 A 类真题.pdf',               province: '江苏', year: 2023, subject: '申论', size: '2.8 MB', downloads: 12108, status: 'warn', uploader: '李编辑' },
  { id: 'p004', name: '2024 年浙江省考行测 A 类真题.pdf',               province: '浙江', year: 2024, subject: '行测', size: '4.0 MB', downloads: 10892, status: 'ok',   uploader: '王老师' },
  { id: 'p005', name: '2023 年山东省考行测真题 (含答案).pdf',            province: '山东', year: 2023, subject: '行测', size: '3.9 MB', downloads:  9512, status: 'bad',  uploader: '张老师' },
  { id: 'p006', name: '2024 年北京市考行测真题.pdf',                    province: '北京', year: 2024, subject: '行测', size: '3.5 MB', downloads:  7824, status: 'warn', uploader: '陈编辑' }
]

export const activities = [
  { id: 1, av: { ch: '张', bg: '#10b981' }, msg: '<b>张老师</b> 上传了 3 份 <b>江苏 2024 行测真题</b>', time: '2 分钟前' },
  { id: 2, av: { ch: '举', bg: '#ef4444' }, msg: '<b>用户举报</b>: 题目 #8291 答案有误, 待审核', time: '14 分钟前' },
  { id: 3, av: { ch: '系', bg: '#6366f1' }, msg: '<b>AI 服务</b> 响应延迟回落至 5.2s', time: '38 分钟前' },
  { id: 4, av: { ch: '王', bg: '#8b5cf6' }, msg: '<b>王同学</b> 完成了第 100 次答题, 达成成就', time: '1 小时前' },
  { id: 5, av: { ch: '📢', bg: '#f59e0b' }, msg: '<b>公告</b> "每日刷题 20 题" 活动上线', time: '3 小时前' }
]

// ===== 当前用户假数据（个人中心 / 数据看板用）=====
export const currentUser = {
  username: 'wangtongxue',
  nickname: '王同学',
  avatar: '王',
  email: 'wang****@example.com',
  phone: '138****6789',
  joinedAt: '2025-09-12',
  membership: { plan: 'pro', expiresAt: '2026-09-12', label: '高级会员' },
  points: 1280,
  stats: {
    practiced: 1342,
    correctRate: 78,
    streak: 14,
    studyDays: 96,
    mistakes: 27,
    aiChats: 213
  }
}

// 周做题数据（数据看板）
export const weekProgress = [
  { day: '周一', value: 32, target: 30 },
  { day: '周二', value: 28, target: 30 },
  { day: '周三', value: 45, target: 30 },
  { day: '周四', value: 40, target: 30 },
  { day: '周五', value: 18, target: 30 },
  { day: '周六', value:  0, target: 30 },
  { day: '周日', value:  0, target: 30 }
]

// 错题分布
export const mistakeDist = [
  { type: '判断推理', count: 12, color: '#8b5cf6' },
  { type: '言语理解', count:  7, color: '#3b82f6' },
  { type: '数量关系', count:  5, color: '#f59e0b' },
  { type: '资料分析', count:  3, color: '#10b981' }
]

// 30 天热力图（0-4 等级）
export const heatmap30 = (() => {
  const levels = [0, 1, 1, 2, 2, 3, 3, 4]
  return Array.from({ length: 30 }, (_, i) => ({
    day: i + 1,
    level: levels[Math.floor(Math.random() * levels.length)]
  }))
})()

// ===== 订单（个人中心 + 后台共用）=====
export const orders = [
  { id: 'GK20260315001', plan: '高级会员·年付', amount: 298, status: 'paid',    date: '2025-09-12' },
  { id: 'GK20260120042', plan: '错题本 PDF 导出', amount:  19, status: 'paid',    date: '2026-01-20' },
  { id: 'GK20260408173', plan: '申论范文集',     amount:  39, status: 'pending', date: '2026-04-08' }
]

// ===== 题目（题目详情页用）=====
export const sampleQuestion = {
  id: 'q8291',
  province: '广东',
  year: 2024,
  subject: '行测',
  type: '数量关系 · 行程问题',
  difficulty: 3,
  stem: '甲、乙两人同时从 A 地出发去 B 地，甲的速度是乙的 1.5 倍。当甲到达 B 地时，乙距离 B 地还有 20 公里。已知 A、B 两地相距多少公里？',
  options: [
    { key: 'A', text: '40 公里' },
    { key: 'B', text: '50 公里' },
    { key: 'C', text: '60 公里' },
    { key: 'D', text: '80 公里' }
  ],
  answer: 'C',
  analysis: '设乙的速度为 v，甲的速度为 1.5v，时间为 t，则 1.5v · t = AB（甲到 B），同一时间内乙走了 v · t = AB - 20。两式相除得 1.5 = AB / (AB - 20)，解得 AB = 60 公里，故选 C。',
  knowledge: ['行程问题', '比例与方程', '追及与相遇'],
  similar: [
    { id: 'q8233', stem: '甲乙两车同向行驶，甲速 60、乙速 40，乙先行 1 小时…', subject: '行测' },
    { id: 'q8345', stem: '一项工程甲单独做 12 天完成，乙单独做 18 天…',     subject: '行测' },
    { id: 'q8412', stem: '某车间生产零件，第一组每天比第二组多生产 30 个…', subject: '行测' }
  ]
}

// ===== 会员套餐（Pricing）=====
export const plans = [
  {
    key: 'free', name: '免费版', price: 0, period: '永久免费', desc: '适合刚开始备考的同学',
    features: [
      { ok: true,  text: '2,579 份真题免费下载' },
      { ok: true,  text: 'AI 对话每天 20 次' },
      { ok: true,  text: '基础错题本（最多 50 题）' },
      { ok: false, text: '随机出题（仅常识题型）' },
      { ok: false, text: '申论范文批改' },
      { ok: false, text: '学习计划自动生成' }
    ],
    cta: '当前方案', highlight: false
  },
  {
    key: 'pro', name: '高级会员', price: 298, period: '298 元 / 年（约 0.8 元 / 天）', desc: '90% 用户都选这个',
    features: [
      { ok: true, text: '免费版全部权益' },
      { ok: true, text: 'AI 对话不限次数' },
      { ok: true, text: '错题本无上限 + 自动归类' },
      { ok: true, text: '随机出题全科目全题型' },
      { ok: true, text: '申论范文批改 100 篇 / 月' },
      { ok: true, text: '学习计划智能排课' }
    ],
    cta: '立即开通', highlight: true
  },
  {
    key: 'enterprise', name: '机构版', price: 'custom', period: '按席位计费', desc: '适合培训机构、学校',
    features: [
      { ok: true, text: '高级会员全部权益' },
      { ok: true, text: '多账号管理后台' },
      { ok: true, text: '学员学情数据看板' },
      { ok: true, text: '专属题库定制' },
      { ok: true, text: '一对一客服' },
      { ok: true, text: 'API 集成支持' }
    ],
    cta: '联系销售', highlight: false
  }
]

export const pricingFAQ = [
  { q: '可以先试用再决定升级吗？', a: '当然，免费版本身就足够日常使用。如果你觉得 AI 不限次数和申论批改对你有帮助，再升级也不迟。' },
  { q: '会员可以退款吗？',           a: '开通后 7 天内未深度使用（AI 对话 < 50 次）可全额退款，请联系客服处理。' },
  { q: '一个账号能在几台设备登录？', a: '高级会员支持同时 3 台设备登录，机构版按席位数计算。' },
  { q: '机构版怎么收费？',           a: '按席位 / 年计费，10 席起售，越多越便宜。具体方案请联系销售获取报价。' }
]

// ===== 成绩分享 =====
export const scoreReport = {
  id: 'rep20260424001',
  user: '王同学',
  paperName: '广东 2024 行测模拟卷',
  date: '2026-04-24',
  totalQuestions: 30,
  correct: 25,
  wrong: 5,
  duration: '38 分 12 秒',
  percentile: 92,
  modules: [
    { name: '判断推理', correct:  9, total: 10, color: '#8b5cf6' },
    { name: '言语理解', correct:  8, total:  8, color: '#3b82f6' },
    { name: '数量关系', correct:  3, total:  6, color: '#f59e0b' },
    { name: '资料分析', correct:  5, total:  6, color: '#10b981' }
  ],
  wrongList: [
    { id: 'q1', stem: '某商品按成本价加价 40% 后又打 8 折出售…',     yours: 'B', answer: 'A' },
    { id: 'q2', stem: '甲乙两人同时从 A 地出发，速度比 3:2…',         yours: 'D', answer: 'C' },
    { id: 'q3', stem: '工程问题：甲、乙、丙合作 6 天可以…',           yours: 'A', answer: 'C' },
    { id: 'q4', stem: '一个圆柱体的体积是 V，将其切成 8 等份…',        yours: 'B', answer: 'D' },
    { id: 'q5', stem: '某次会议出席人员中，男性比女性多 24 人…',       yours: 'C', answer: 'B' }
  ]
}

// ===== 后台用户列表（管理员后台 - 用户管理 tab）=====
export const adminUsers = [
  { id: 'u8201', nickname: '王同学', plan: 'pro',  joinedAt: '2025-09-12', studyDays: 96, status: 'active' },
  { id: 'u8202', nickname: '李同学', plan: 'free', joinedAt: '2025-11-03', studyDays: 42, status: 'active' },
  { id: 'u8203', nickname: '张同学', plan: 'pro',  joinedAt: '2026-01-18', studyDays: 28, status: 'active' },
  { id: 'u8204', nickname: '陈同学', plan: 'free', joinedAt: '2026-02-22', studyDays:  9, status: 'inactive' },
  { id: 'u8205', nickname: '刘同学', plan: 'pro',  joinedAt: '2026-03-08', studyDays: 18, status: 'active' }
]
