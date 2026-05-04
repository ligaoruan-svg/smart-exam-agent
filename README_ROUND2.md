# 公考小智 v2 — 第二轮交付（小轮 2.1）

**这一轮目标**：跑通"用户对话 → AI 准备练习 → 用户做题"完整闭环。

---

## 📦 这一轮交付了什么

```
gk-project-v2-round2/
├── api/                          ★ FastAPI BFF（全新，11 个文件）
│   ├── config.py                 集中配置 + 日志系统
│   ├── db.py                     数据库连接
│   ├── auth.py                   JWT + 鉴权
│   ├── auth_routes.py            /api/auth/* 路由
│   ├── llm.py                    DeepSeek 客户端
│   ├── mcp_client.py             FastAPI 端的 MCP 客户端
│   ├── chat_engine.py            ★ 对话编排引擎（思考步骤推送）
│   ├── chat_routes.py            /api/chat/* 路由（含 SSE）
│   ├── practice.py               /api/practice/* 路由
│   └── main.py                   FastAPI 入口
├── frontend/src/                 Vue 改动文件（覆盖你现有项目对应位置）
│   ├── api/index.js              ★ 替换原 mock
│   ├── components/
│   │   ├── ThinkingSteps.vue     思考步骤组件
│   │   └── cards/
│   │       ├── UICard.vue        卡片分发器
│   │       ├── PracticeReadyCard.vue
│   │       ├── PackReadyCard.vue
│   │       ├── PdfGeneratingCard.vue
│   │       └── FallbackCard.vue
│   └── panels/
│       ├── ChatPanel.vue         ★ 全新，接 SSE
│       └── PracticePanel.vue     ★ 改造，支持 ?session=xxx 启动
├── gk_mcp/                       ← 第一轮交付，不改
├── sql/                          ← 第一轮交付，不改
├── .env.example                  环境变量模板
├── requirements.txt              Python 依赖（含新增的）
├── start_all.sh                  一键启动 3 个服务
├── stop_all.sh                   一键停止
└── README_ROUND2.md              本文件
```

---

## 🚀 5 步跑起来

### 1. 准备环境变量

```bash
cd gk-project-v2-round2
cp .env.example .env
# 用你顺手的编辑器改 .env，至少改 DB_PASSWORD 和 JWT_SECRET
```

### 2. 安装依赖

```bash
# 在你的 conda gk 环境下
conda activate gk
pip install -r requirements.txt
```

新装的关键包：`fastapi==0.115.0`、`uvicorn`、`openai`、`mcp>=1.0.0`、`sse-starlette`、`python-dotenv`

### 3. 把前端文件覆盖到你现有 Vue 项目

> **注意**：`frontend/src/` 下的文件**不是完整 Vue 项目**，是要覆盖到你现有 Vue 项目（gongkao-xiaozhi 17.50.20）对应位置的。

具体覆盖清单：

| 我交付的 | 覆盖到你现有的 |
|---|---|
| `frontend/src/api/index.js` | `gongkao-xiaozhi/src/api/index.js` |
| `frontend/src/components/ThinkingSteps.vue` | `gongkao-xiaozhi/src/components/ThinkingSteps.vue` (新增) |
| `frontend/src/components/cards/*` | `gongkao-xiaozhi/src/components/cards/*` (新增整个目录) |
| `frontend/src/panels/ChatPanel.vue` | `gongkao-xiaozhi/src/panels/ChatPanel.vue` |
| `frontend/src/panels/PracticePanel.vue` | `gongkao-xiaozhi/src/panels/PracticePanel.vue` |

**简单粗暴的复制命令**（假设你 Vue 项目在 `~/Desktop/gongkao-xiaozhi 17.50.20/`）：

```bash
VUE_DIR="$HOME/Desktop/gongkao-xiaozhi 17.50.20"
SRC="/path/to/gk-project-v2-round2/frontend/src"

cp $SRC/api/index.bak.js              "$VUE_DIR/src/api/index.js"
cp $SRC/panels/ChatPanel.bak.vue      "$VUE_DIR/src/panels/ChatPanel.vue"
cp $SRC/panels/PracticePanel.bak.vue  "$VUE_DIR/src/panels/PracticePanel.vue"
mkdir -p "$VUE_DIR/src/components/cards"
cp $SRC/components/ThinkingSteps.vue "$VUE_DIR/src/components/"
cp $SRC/components/cards/*.vue       "$VUE_DIR/src/components/cards/"
```

⚠️ 覆盖前**先备份你现有的**这几个文件！

### 4. 给 Vue 项目加上 API 地址环境变量

在你 Vue 项目根目录建 `.env.local`：

```
VITE_API_BASE=http://localhost:8900
```

### 5. 启动所有服务

**方式 A：一键启动（推荐）**

```bash
cd gk-project-v2-round2
./start_all.sh
```

会自动启动 MCP server (8765) + FastAPI (8900)。Vue 需要在你 Vue 项目目录单独跑：

```bash
cd "$HOME/Desktop/gongkao-xiaozhi 17.50.20"
npm run dev
```

**方式 B：手动启动 3 个进程**（要 3 个终端窗口）

```bash
# 终端 1：MCP server
cd gk-project-v2-round2
MCP_MODE=sse python gk_mcp/mcp_server.py

# 终端 2：FastAPI
cd gk-project-v2-round2
uvicorn api.main:app --reload --port 8900

# 终端 3：Vue
cd "$HOME/Desktop/gongkao-xiaozhi 17.50.20"
npm run dev
```

启动成功标志：
- MCP server: `🚀 MCP Server (SSE) 启动: http://0.0.0.0:8765/sse`
- FastAPI: `INFO: ✅ 数据库连接成功 | INFO: ✅ MCP server 连接成功`
- Vue: `Local: http://localhost:5173/`

---

## 🧪 测试核心闭环

### 准备：先登录

打开浏览器 http://localhost:5173，跳转到登录页，用 admin / admin123 登录。

或者直接 API 测试：

```bash
curl -X POST http://localhost:8900/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

返回里有个 `token`，后面要用。

### 测试 1：health check

```bash
curl http://localhost:8900/api/health
# 期待：{"ok":true,"db":true,"mcp":true}
```

### 测试 2：me 接口

```bash
TOKEN="..."  # 上面登录拿到的
curl -H "Authorization: Bearer $TOKEN" http://localhost:8900/api/auth/me
# 期待：返回 admin 用户信息
```

### 测试 3：流式对话（命令行）

```bash
curl -N -X POST http://localhost:8900/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"列出所有省份"}'
```

**期待**：看到一连串 SSE 事件涌出来：
```
event: session
data: {"session_id": "..."}

event: thinking_start
data: {"step": 0, "label": "准备工具"}

event: thinking_step
data: {"step": 0, "detail": "加载了 17 个工具"}

event: thinking_start
data: {"step": 1, "label": "理解你的需求"}

event: tool_call_start
data: {"step": 1, "name": "list_provinces", "arguments": {}}

event: tool_call_done
data: {"step": 1, "name": "list_provinces", "ok": true, "elapsed_ms": 28, ...}

event: text_delta
data: {"delta": "公考"}

event: text_delta
data: {"delta": "题库"}

... (LLM 文字流式增量)

event: done
data: {"total_ms": 2340, "message_id": 12, ...}
```

### 测试 4：浏览器跑核心闭环 ★

打开 http://localhost:5173/chat（或者跳转到聊天页面）：

1. **新对话**：左侧 "+ 新对话" 按钮
2. **发消息**："帮我准备 5 道判断推理"
3. **看到效果**：
   - 上方先出现"💭 正在思考..." 折叠卡片
   - 点开能看到"准备工具 → 理解需求 → 调用 prepare_practice_session"
   - LLM 文字逐字流出"已为你准备好 5 道判断推理..."
   - 下方出现一张 **绿色 PracticeReadyCard 卡片**，带"开始练习"按钮
4. **点"开始练习"** → 跳转到 PracticePanel，显示第 1 道题
5. **选答案 → 提交** → 显示对错和解析
6. **点"下一题"循环 5 道** → 完成提示

### 测试 5：完成后回 SQL 查

```sql
-- 看 session 状态
SELECT id, status, answered_count, correct_count, total_count, duration_seconds
FROM cs_v2.quiz_sessions
WHERE user_id = 1 ORDER BY started_at DESC LIMIT 3;
-- 期待：刚完成的那条 status='completed'，answered_count=5

-- 看答题记录
SELECT * FROM cs_v2.answer_records
WHERE user_id = 1 ORDER BY created_at DESC LIMIT 5;

-- 看错题
SELECT * FROM cs_v2.wrong_questions
WHERE user_id = 1 ORDER BY last_wrong_at DESC LIMIT 5;

-- 看用户统计
SELECT total_answered, total_correct, daily_used FROM cs_v2.users WHERE id = 1;
```

---

## 📖 日志位置

按天分割，30 天滚动：

| 文件 | 内容 |
|---|---|
| `logs/api.log` | FastAPI 主进程业务日志 |
| `logs/mcp.log` | 每次 MCP 工具调用（入参、耗时、结果摘要） |
| `logs/chat.log` | 对话流水（用户消息、LLM 响应） |
| `logs/error.log` | **所有 ERROR 级别日志聚合** |
| `logs/mcp_server.out` | MCP server 进程的 stdout/stderr |
| `logs/fastapi.out` | FastAPI 进程的 stdout/stderr |

排查问题先看 `logs/error.log`。

---

## ⚠️ 常见问题

### Q1: FastAPI 启动报错 `MCP server 不可达`
**先启动 MCP server**，再启动 FastAPI。`start_all.sh` 已经按顺序处理了，手动启动要注意。

### Q2: 浏览器 fetch 报 CORS 错误
`api/main.py` 已经配了 `allow_origins=["*"]`，应该没问题。如果你改了 frontend 端口或者反代了域名，确认下。

### Q3: SSE 看不到流式效果，等很久一次性出来
- 检查浏览器 devtools Network → 找那个 stream 请求 → response 应该是 `text/event-stream`
- 如果你前面挂了 nginx，加 `proxy_buffering off;`
- `api/chat_routes.py` 已经设了 `X-Accel-Buffering: no`

### Q4: 工具调用返回 401 Unauthorized
token 过期了。重新登录拿新 token。前端 api 层已经处理：401 自动跳 /login。

### Q5: LLM 调用超时
DeepSeek 偶尔会慢。看 `logs/chat.log` 里有没有具体错误。

### Q6: 思考步骤折叠卡片不展开
点击卡片上方的灰色横条，应该能展开。每个工具调用也是可以单独点开的。

### Q7: PracticePanel 不显示题目
- 看浏览器 console 有没有报错
- 查 `logs/api.log` 看 `/api/practice/start/xxx` 有没有调成功
- SQL 查一下 `quiz_sessions` 那条 session 的 `preset_question_ids` 字段是不是空的

---

## 🎯 这一轮没做什么（小轮 2.2 / 2.3 做）

- DownloadPanel / MistakeBook / StudyPlan 接真接口（小轮 2.2）
- Login / Register / UserCenter 完整页面（小轮 2.2）
- 管理后台权限隔离（小轮 2.2）
- PDF 异步生成 worker（小轮 2.3）
- 省份打包异步 worker（小轮 2.3）
- 申论批改（小轮 2.3）
- 离线 PDF→题入库管道（你说要单独讨论）

---

## ✅ 这一轮验收标准

- [ ] 三个服务都能启动
- [ ] `/api/health` 返回 `{ok: true}`
- [ ] 登录拿到 token
- [ ] SSE 命令行能看到事件流
- [ ] 浏览器在 ChatPanel 发消息，能看到思考步骤展开
- [ ] AI 准备练习卡片能正常渲染
- [ ] 点"开始练习"能跳到 PracticePanel
- [ ] PracticePanel 能做题、提交、显示对错
- [ ] SQL 里能看到 answer_records 和 quiz_sessions 状态变化

7 项过了就算这一轮通过。

---

## 🔜 验收后告诉我什么

测完后：

1. ✅ 哪些通过、哪些卡住
2. 卡住的话贴 `logs/error.log` 最后 50 行 + 浏览器 console 截图
3. 体验上有什么不顺手的（思考步骤太多/太少、卡片样式、节奏感等）

我会根据反馈微调，**没问题就开干小轮 2.2**。
