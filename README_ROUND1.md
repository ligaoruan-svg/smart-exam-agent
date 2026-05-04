# 公考小智 v2 — MCP Server

第一轮交付：**SQL 全表 + MCP server**。FastAPI 改造和 Vue 前端改造在下一轮。

---

## 目录结构

```
gk-project-v2/
├── sql/
│   ├── cs_full.sql           # 19 张表完整建表脚本
│   └── seed.sql              # 初始数据：3 个套餐 + 32 个省份 + 1 个 admin
├── mcp/
│   ├── __init__.py
│   ├── db.py                 # 数据库连接 + 字典缓存
│   ├── auth.py               # 用户校验、配额检查
│   └── mcp_server.py         # 主入口，17 个工具
├── requirements.txt
└── README.md
```

---

## 5 分钟跑起来

### 1. 建库 + 初始化数据

```bash
# 建一个新库，跟你现有 cs 库共存（不影响老业务）
mysql -u root -p -e "CREATE DATABASE cs_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 建表
mysql -u root -p cs_v2 < sql/cs_full.sql

# 初始数据（套餐字典 + 省份字典 + admin 用户）
mysql -u root -p cs_v2 < sql/seed.sql
```

跑完应该有 **19 张表 + 3 个套餐 + 32 个省份 + 1 个 admin 用户**。

> ⚠️ **必须改 admin 密码**！默认是 `admin123`，生产环境绝对不能用：
> ```bash
> python3 -c "import hashlib; print(hashlib.sha256(('gk2026你的新密码').encode()).hexdigest())"
> # 把输出的 hash 更新到数据库
> mysql -u root -p cs_v2 -e "UPDATE users SET password_hash='...新hash...' WHERE username='admin';"
> ```

### 2. 灌题目数据（从老库 cs 复制过来）

```bash
mysql -u root -p << 'EOF'
-- 把现有清洗好的 38K 题目灌进新库
INSERT INTO cs_v2.questions
SELECT * FROM cs.questions;

-- 申论题
INSERT INTO cs_v2.shenglun_questions
SELECT * FROM cs.shenglun_questions;

-- 老用户（如果有）
INSERT INTO cs_v2.users
  (id, username, email, password_hash, avatar, plan, plan_expires_at,
   daily_limit, daily_used, daily_reset_at, total_answered, total_correct,
   created_at, last_login_at, role)
SELECT id, username, email, password_hash, avatar, plan, plan_expires_at,
       daily_limit, daily_used, daily_reset_at, total_answered, total_correct,
       created_at, last_login_at, 'user'
FROM cs.users
WHERE id NOT IN (SELECT id FROM cs_v2.users);

-- 答题记录、错题、薄弱点（如果有）
INSERT INTO cs_v2.answer_records SELECT * FROM cs.answer_records;
INSERT INTO cs_v2.wrong_questions
  (id, user_id, question_id, wrong_count, last_wrong_at, is_mastered,
   is_starred, note, created_at, updated_at)
SELECT id, user_id, question_id, wrong_count, last_wrong_at, is_mastered,
       0, note, created_at, updated_at
FROM cs.wrong_questions;
INSERT INTO cs_v2.user_weaknesses
  (id, user_id, rate_yanyu, rate_panduan, rate_shuliang, rate_changshi,
   rate_shenglun, weakness_provinces, updated_at)
SELECT id, user_id, rate_yanyu, rate_panduan, rate_shuliang, rate_changshi,
       rate_shenglun, weakness_provinces, updated_at
FROM cs.user_weaknesses;

-- 回填省份字典的题数缓存
UPDATE cs_v2.provinces p
LEFT JOIN (
    SELECT province, COUNT(*) AS cnt FROM cs_v2.questions
    WHERE is_valid = 1 GROUP BY province
) q ON p.code = q.province
SET p.total_papers = COALESCE(q.cnt, 0);
EOF
```

### 3. 装依赖

```bash
cd gk-project-v2
pip install -r requirements.txt
```

主要是两个：`fastmcp` 和 `pymysql`。

### 4. 启动 MCP server

**stdio 模式（给 Claude Desktop 用）**：
```bash
cd gk-project-v2/mcp
python mcp_server.py
```

**SSE 模式（给 FastAPI BFF / RAGFlow 用）**：
```bash
MCP_MODE=sse MCP_PORT=8765 python mcp_server.py
# 启动后访问 http://localhost:8765/sse
```

**首次启动时数据库连接信息从环境变量读**，缺省值适用于本地：

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=cs_v2

python mcp_server.py
```

启动成功的标志：
```
✅ 字典缓存加载完成：32 省份，3 套餐
🚀 MCP Server (stdio) 启动
```

---

## 接入 Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "gk-xiaozhi": {
      "command": "python",
      "args": ["/绝对路径/到/gk-project-v2/mcp/mcp_server.py"],
      "env": {
        "DB_HOST": "localhost",
        "DB_PORT": "3306",
        "DB_USER": "root",
        "DB_PASSWORD": "你的密码",
        "DB_NAME": "cs_v2"
      }
    }
  }
}
```

完全重启 Claude Desktop（菜单栏退出再开），下方应该能看到 `gk-xiaozhi` 的工具图标。

---

## 17 个工具速查

| 类别 | 工具名 | 说明 |
|---|---|---|
| 字典 | `list_provinces(hot_only?)` | 省份列表 |
| 字典 | `list_years(province?)` | 可用年份 |
| 字典 | `list_question_types()` | 题型/子题型 |
| 题库 | `search_questions(...)` | 题库搜索（精简列表） |
| 题库 | `get_random_questions(count, ...)` | 随机抽题（完整内容） |
| 题库 | `get_question_by_id(id)` | 单题详情 |
| 申论 | `get_shenglun_questions(...)` | 申论题搜索 |
| 申论 | `get_shenglun_by_id(id)` | 申论题详情 |
| 试卷 | `search_papers(...)` | 试卷文件查询 |
| 试卷 | `get_paper_by_id(id)` | 单份试卷详情 |
| 学情 | `get_user_study_overview(user_id)` | **核心**：一次拿全诊断 |
| 学情 | `get_recent_wrongs(user_id, ...)` | 错题列表 |
| 学情 | `get_recent_sessions(user_id, ...)` | 练习记录 |
| 学情 | `get_user_weakness(user_id)` | 薄弱点 |
| 写 | `prepare_practice_session(user_id, ...)` | **核心**：AI 准备练习 |
| 写 | `trigger_pack_province(province, ...)` | 打包下载 |
| 写 | `generate_quiz_pdf(user_id, ...)` | 生成 PDF |

---

## 在 Claude Desktop 里测试

接入后直接对话，下面是建议的测试用例（按从简到繁的顺序）：

| 你说的话 | 应该调用的工具 | 验证什么 |
|---|---|---|
| 列出所有省份 | `list_provinces` | 字典缓存生效，返回 32 个省份 |
| 国考有哪些年份 | `list_years(province="国考")` | 年份过滤 |
| 行测有哪些题型 | `list_question_types` | 嵌套返回结构 |
| 找几道 2023 广东的言语理解 | `search_questions` | 多条件筛选 |
| 随机出 5 道判断推理题 | `get_random_questions(count=5, question_type="判断推理")` | 返回完整题目 |
| 第 1 题怎么做 | `get_question_by_id(question_id=1)` | 单题详情（如果你库里有 id=1） |
| 找几道申论 | `get_shenglun_questions` | 申论表 |
| 我的学习情况怎么样（user_id=1） | `get_user_study_overview(user_id=1)` | 学情聚合 |
| 我的错题（user_id=1） | `get_recent_wrongs(user_id=1)` | 错题查询 |
| 我哪里薄弱（user_id=1） | `get_user_weakness(user_id=1)` | 薄弱点 |
| 帮我准备 10 道判断推理（user_id=1） | `prepare_practice_session(user_id=1, count=10, question_type="判断推理")` | **核心**：写 pending session + 返回 ui_card |
| 把广东打包给我 | `trigger_pack_province(province="广东")` | 打包请求 + ui_card |
| 帮我出一份 20 道题的 PDF（user_id=1） | `generate_quiz_pdf(user_id=1, count=20)` | PDF 任务 + ui_card |

> **注意**：现在还没有真正的"用户登录态"传递机制，工具里 user_id 是 LLM 看你输入猜的。下一轮 FastAPI BFF 会用 JWT 解出 user_id 并强制覆盖 LLM 传的，这一轮先用 `user_id=1`（admin）测试。

---

## 验证 prepare_practice_session 真的写了数据库

跟 Claude 说"帮我准备 5 道言语理解，user_id=1"，然后查数据库：

```sql
SELECT id, user_id, session_type, question_type, total_count,
       JSON_LENGTH(preset_question_ids) AS qcount, status, started_at
FROM cs_v2.quiz_sessions
WHERE user_id = 1
ORDER BY started_at DESC
LIMIT 3;
```

应该看到一条 `status='pending'`、`session_type='ai_prepared'`、`qcount=5` 的记录。

再跟 Claude 说一次"帮我准备 8 道判断推理"，再查：旧那条应该变成 `cancelled`，新的是 `pending`（**一用户一活跃 pending** 规则生效）。

---

## 常见问题

### Q1: 启动报 `ImportError: No module named 'fastmcp'`
```bash
pip install fastmcp pymysql
```

### Q2: 报 `pymysql.err.OperationalError: (1045, "Access denied")`
检查环境变量 `DB_PASSWORD` 是不是对的，或者直接改 `mcp/db.py` 里 `DB_CONFIG` 的默认值（开发用）。

### Q3: 工具返回 `{"error": "auth_failed", "message": "用户 X 不存在"}`
确认 `users` 表里有 id 为 X 的用户。默认 seed.sql 只建了 `admin`（id 一般是 1）。

### Q4: 工具返回 `{"error": "no_questions"}`
- 检查 `questions` 表是否真的灌了数据（`SELECT COUNT(*) FROM cs_v2.questions WHERE is_valid=1`）
- 默认会排除 `图形推理` 和 `资料分析`（你说还没清洗），如果你测试题型是这俩会查不到
- 如果想测全部题型，临时改 `mcp_server.py` 里 `EXCLUDED_QUESTION_TYPES = ()` 设为空

### Q5: Claude Desktop 看不到工具
- 检查 `claude_desktop_config.json` 路径是否绝对路径
- Claude Desktop 完全退出（不只是关窗）再启动
- 看 Claude Desktop 的日志：`~/Library/Logs/Claude/`

### Q6: SSE 模式启动后 RAGFlow 连不上
你说这个项目不打算给 RAGFlow 用，但如果哪天要，注意：
- RAGFlow MCP 配置类型选 **sse**（不是 streamable-http）
- URL 填 `http://你的IP:8765/sse`（结尾带 `/sse`）

### Q7: stdio 模式下能不能看到日志？
stdio 模式下，stdout 是给 MCP 协议用的，print 调试信息会污染协议。所以本工具内的日志全部写到 `stderr`，Claude Desktop 的日志文件能看到。

### Q8: 怎么测试某个工具是不是真的被 LLM 调对了？
跟 Claude 说"用 SQL 模式回答我"或者"详细告诉我你调了什么工具，传了什么参数"，它会展开调用细节给你看。

---

## 下一轮要做什么

第二轮交付（等你测通这一轮再开始）：

1. **FastAPI BFF 改造**
   - `/api/chat/stream` 改成 MCP 客户端
   - 加业务接口：papers/orders/favorites/study-plan/announcements/admin/...
   - 替换 Vue mock 用的真接口
   - PDF 异步生成 worker（接 `generate_quiz_pdf` 工具的 task）
   - 省份打包异步 worker（接 `trigger_pack_province` 工具的 task）

2. **Vue 前端改造**
   - `src/api/index.js` 替换 mock
   - ChatPanel 接 SSE + 卡片渲染（type 分发架构）
   - PracticeReadyCard / PackReadyCard 等卡片组件
   - PracticePanel 接 session（`?session=xxx` 启动模式）
   - DownloadPanel/MistakeBook/StudyPlan 接真接口
   - 管理后台权限隔离（路由守卫 + 菜单过滤，role!=admin 不能进）
   - Login/Register 接真接口

3. **Docker 部署**（你说不要 Docker，跳过；如果改主意了再说）

---

## 下一轮开始前我需要你给我

你测通这一轮后，把这些发我：

1. ✅ 测试结果 — 哪些工具调通了、哪些有问题
2. ✅ 你 MySQL 真实的连接信息（host/port/user）— 我会写到生产配置里，密码用环境变量不写死
3. ✅ FastAPI 部署在哪台机器上、Vue 静态文件在哪 — 决定 nginx 配置
4. ✅ DeepSeek API Key 还用现在的还是换 — 决定 BFF 配置

---

**问题反馈直接告诉我，别自己改。我们这一轮的目标是 MCP server 跑通 + 在 Claude Desktop 里能正常对话调工具。其他下一轮再说。**
