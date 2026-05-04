# 公考小智 · Vue 前端

基于上传的设计系统（公考小智 Design System）完整移植为 Vue 3 + Vite 项目。

## 目录结构

```
gongkao-xiaozhi/
├─ index.html               ← Vite 入口
├─ package.json
├─ vite.config.js
├─ public/
│  ├─ logo-mark.svg
│  ├─ logo-horizontal.svg
│  └─ auth-illustration.svg
└─ src/
   ├─ main.js               ← 挂载入口
   ├─ App.vue               ← 顶层路由/Tab 切换
   ├─ assets/
   │  ├─ colors_and_type.css  设计 token（原样复用）
   │  └─ global.css
   ├─ components/           ← 通用组件
   │  ├─ Button.vue  IconButton.vue  Chip.vue  StatusPill.vue
   │  ├─ Card.vue    SectionHeader.vue
   │  ├─ GkInput.vue GkSelect.vue
   │  ├─ Avatar.vue  Logomark.vue
   └─ panels/               ← 业务面板
      ├─ TopNav.vue         顶部导航
      ├─ ChatPanel.vue      AI 对话
      ├─ PracticePanel.vue  随机练习
      ├─ DownloadPanel.vue  真题下载（32 个省份）
      ├─ MistakeBook.vue    错题本
      ├─ StudyPlan.vue      本周学习计划
      └─ AuthScreen.vue     登录 / 注册
```

## 跑起来

需要 Node 18+：

```bash
cd gongkao-xiaozhi
npm install
npm run dev
```

然后浏览器打开 http://localhost:5173 。

### 生产构建

```bash
npm run build
npm run preview
```

## 零依赖快速预览

如果暂时不想装 npm 依赖，仓库根目录还附了一个 `standalone.html`，
通过 CDN 直接加载 Vue 3 + 内联模板，用任意静态服务器即可：

```bash
npx serve .        # 或 python3 -m http.server 8080
```

然后打开 http://localhost:8080/standalone.html 。

## 色彩与排版 token

全部在 `src/assets/colors_and_type.css`（直接来自设计系统），以 CSS 变量暴露，
比如 `--gk-green-500`、`--gk-blue-600`、`--gk-font-sans`。新增组件请统一使用变量。

## 切换页面

顶部导航包含 5 个 Tab：
- **AI 对话**（默认）  左右两栏布局：左侧 ChatPanel + 右侧 StudyPlan/MistakeBook
- **随机练习**          答题流 + 右侧统计栏
- **真题下载**          32 个省份卡片 + 最近更新 PDF
- **错题本**            完整错题本
- **学习计划**          本周打卡

右上角有「登录 / 注册」，点击进入全屏手机号验证码流程。
