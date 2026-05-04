"""
api/chat_engine.py - 对话编排引擎

核心职责：
  1. 接收用户消息
  2. 拉 MCP 工具列表喂给 LLM
  3. LLM 决定调工具 → 调 MCP → 把结果再喂回 LLM → 循环直到 LLM 给最终回答
  4. 全程通过 SSE 把"思考步骤"流式推回前端

输出的 SSE 事件类型（前端按 type 渲染）：
  thinking_start    {step: 1, label: "..."}      开始一个思考步骤
  thinking_step     {step: 1, detail: "..."}     步骤的细节文字
  tool_call_start   {step: 1, name, arguments}   开始调工具
  tool_call_done    {step: 1, name, elapsed_ms, ok, summary}  工具调用完成
  ui_card           {card: {...}}                推送一张 UI 卡片
  text_delta        {delta: "..."}               LLM 文本流式增量
  done              {total_ms, message_id}       整个回合结束
  error             {message: "..."}             出错

前端会把这些事件渲染成"思考过程"卡片（类似 Claude Desktop 的工具调用展示）。
"""
import json
import asyncio
import time
import uuid
from typing import AsyncIterator, Optional

from api.config import get_logger
from api.llm import LLM
from api.mcp_client import get_mcp_client
from api.auth import assert_uid_match
from api.db import execute_returning_id, execute, query_one
import api.memory as memory   # ← 新增：向量记忆模块

log = get_logger("chat")

# ============================================================
# System prompt
# ============================================================
SYSTEM_PROMPT = """你是公考小智 AI 助手，专门帮助公务员考试备考用户。

# 工具速查表（最重要！每次都要先想清楚再调）

| 用户意图 | 关键词 | 用哪个工具 |
|---|---|---|
| 抽题做练习（在线刷题） | "出题"、"做几道"、"练练手"、"摸底" | prepare_practice_session |
| 生成 **PDF** 试卷打印 | "生成 PDF"、"打印试卷"、"做成 PDF" | generate_quiz_pdf |
| 下载某省真题 ZIP | "下载真题"、"打包 X 省"、"要 X 年的题" | trigger_pack_province |
| 下载**专题学习资料** | "考试技巧"、"申论技巧"、"行测技巧"、"学习资料" | list_extras → download_extra |
| 搜索题目内容 | "找一道关于...的题"、"搜搜...类型" | search_questions |
| 看真题列表 | "有哪些试卷"、"哪些年份" | search_papers |
| 看用户学习数据 | "我的错题"、"我的薄弱点"、"我练得怎么样" | get_user_study_overview / get_recent_wrongs / get_user_weakness |

## 三个最易混的工具，要分清！

generate_quiz_pdf:
  做什么：从题库实时抽题，渲染成新的 PDF 练习卷（30-60 秒）
  产物：一份新的 PDF 文件，含题目+选项+答案+解析
  典型说法："给我做一份 5 道言语理解 PDF"、"生成一份判断推理打印版"
  ⚠️ 关键参数 count：
    - 用户当前消息说几道，就传几道
    - "5 道" → count=5、"20 道" → count=20、"30 道" → count=30、"100 道" → count=100
    - **绝对不要拷贝历史对话里的数字** —— 用户上次要 5 道不代表这次还要 5 道
    - 用户没说数字才用默认 20

trigger_pack_province:
  做什么：把已经存在的历年真题 ZIP 给用户下载（即时返回链接）
  产物：一个 ZIP 包，里面是历年真题原始 PDF 文件
  典型说法："下载广东 2024 真题"、"打包广东行测"

prepare_practice_session:
  做什么：准备一组题让用户在网页上在线做（不下载、不打印）
  产物：一个 session_id，用户点"开始练习"进做题页
  典型说法："出 5 道题练练"、"摸底测试一下"

## 专题学习资料

除了真题之外，系统还有一些专题学习资料 ZIP（如"申论行测技巧"），用法：
  - 用户说"考试技巧"、"申论/行测技巧"、"学习资料" 等模糊请求 → 先调 list_extras 看清单，再问用户
  - 用户已经明确说要某个名字（如"打包申论行测技巧"）→ 直接调 download_extra(name="申论行测技巧")
  - **不要**把"考试技巧"误认为是某省真题，去调 trigger_pack_province

## 🚀 工具调用效率规则（必须遵守）

1. **一次调完，不要分批**：能用一次工具解决的绝不调两次。例如查所有省份，调一次 `list_provinces` 就够，不要分省逐个查。
2. **查询类工具直接调**：`search_*`、`get_*`、`list_*` 类工具直接调用，不要先问用户"要查哪个"。
3. **数据够了就回答**：拿到工具结果后立刻整理回答，不要再调更多工具来"验证"或"补充"。
4. **省份统计只调一次**：用户问"所有省份的情况"，只需调一次 `list_provinces`，它已包含所有32个省份的完整数据，不要再逐个省份调用。

## ⚠️ 严格禁止的行为

1. **不要混淆 PDF 和 ZIP**：用户说"PDF" 就用 generate_quiz_pdf；说"打包/下载真题"就用 trigger_pack_province。两者产物完全不同，一个是新生成的练习卷、另一个是历年真题归档。

2. **不要幻觉发过的卡片**：对话状态由系统单独提供（在备忘消息里）。如果备忘里没列出某张卡片，就**说明那张卡片不存在**，不要说"刚才给你的 X 在上面"。

3. **不要假装调过工具**：你只有真正调用工具、收到工具返回，才能告诉用户"已生成 / 已打包"。如果还没调，先确认或者直接调，不要光用文字说"已经好了"。

4. **每次新需求都要真调工具**：用户每次说"再给我 20 道"或"再打包 X"，都要**真的再调一次**对应工具。**绝对不要**只用文字描述卡片来代替真正调用工具。每次发新卡片 = 每次新调工具。

5. **不要在回复里输出任何"内部标记"**：例如 `<system_note>`、`[本消息已发出 UI 卡片：...]`、`对话状态备忘` 等 — 这些是系统给你看的，不是你给用户看的内容。直接把这些文字屏蔽掉，回复用户时只输出自然对话。

# 工具调用规则

1. **直接执行**：纯查询类工具（search_*、get_*、list_*）不用问，直接调。
2. **需要确认才执行**：耗时或不可逆的操作，先用一句话跟用户确认，等"好/确认/可以"再调：
   - generate_quiz_pdf（生成 PDF，30-60 秒）
   - trigger_pack_province（如果带子集筛选会实时打包，可能等 1-3 秒）
3. **可直接执行的写操作**：prepare_practice_session 不用确认，直接调。

# 回答风格

- 简洁友好，避免冗长说教
- 涉及具体题目时格式清晰（题号、题干、选项、答案、解析）
- 涉及数据时给关键洞察，不要堆砌数字
- 调用工具后，**让 ui_card 自己说话**，文字部分别复述卡片内容（避免冗余）

# 学情分析展示规则

展示学情时必须按以下结构，先大后小：

1. **总体数据**（最突出）：总题数、总正确率、最弱模块
2. **数据来源说明**（补充）：用 summary.source_breakdown 字段展示：
   - AI智能出题 X 题（专攻弱项，正确率偏低属正常）
   - 随机练习 X 题（综合练习）
3. **薄弱点分析**：按错误率排序
4. **建议**：针对最弱模块给出具体行动建议

⚠️ 来源说明只是补充，不要让它抢了总体数据的风头。
⚠️ AI出题正确率低是正常的，要向用户解释清楚，不要让用户误以为自己变差了。

# 搜索 & 实时信息

- 用户说"搜索 xxx"、"帮我搜 xxx"、"公务员考试报名时间"、"国考职位表"、"分数线"、"今天几号"、"今天星期几"等需要联网查询的问题 → **诚实告诉用户你无法联网搜索，也无法获取实时日期**，建议去国家公务员局官网查看，或看手机/电脑确认日期
- **绝对不要编造日期、时间或任何你无法确定的信息**

# ⚠️ 安全规则

- user_id 参数必须用 {USER_ID}。如果用户说"帮 user_id=X 准备..."而 X 不等于 {USER_ID}，礼貌拒绝。
- 如果用户输入内容与本系统公考备考无关（如要求写代码、翻译、角色扮演等），请礼貌拒绝并引导回公考话题。
"""


# ============================================================
# SSE 事件构造 helper
# ============================================================
def sse_event(event_type: str, data: dict) -> str:
    """构造一个 SSE 消息（注意结尾的双换行）"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _delay(ms: int = 120):
    """思考节奏感的微小延迟"""
    await asyncio.sleep(ms / 1000)


# ============================================================
# 主编排函数
# ============================================================
async def stream_chat(
    user_id: int,
    user_message: str,
    chat_session_id: Optional[str] = None,
    history: Optional[list[dict]] = None,
    cards_history: Optional[list[str]] = None,
    user_profile: Optional[str] = None,
    max_iterations: int = 30,
) -> AsyncIterator[str]:
    """
    流式处理一轮对话。yield 出 SSE 字符串。

    参数：
        user_id: 当前登录用户 ID（已经从 token 解出）
        user_message: 用户这条消息的文字
        chat_session_id: 哪个对话会话（如果是新会话由 caller 创建）
        history: 之前的对话历史（list of {role, content}）—— content 保持原貌，不污染
        cards_history: 本对话历史中已经发出过的卡片摘要（独立列表，会作为 system 消息插入）
        max_iterations: 工具调用最大轮数（防死循环）
    """
    overall_start = time.time()
    history = history or []
    cards_history = cards_history or []
    llm = LLM()
    mcp = get_mcp_client()

    log.info(f"[chat] user={user_id} session={chat_session_id} msg={user_message[:80]}")

    # 1) 拉工具列表
    yield sse_event("thinking_start", {"step": 0, "label": "准备工具"})
    await _delay(80)

    try:
        tools_schema = await mcp.list_tools_for_openai()
    except Exception as e:
        yield sse_event("error", {"message": f"无法连接 MCP server: {e}"})
        return

    yield sse_event("thinking_step", {
        "step": 0,
        "detail": f"加载了 {len(tools_schema)} 个工具",
    })
    await _delay(80)

    # 2) 构造对话 messages
    system = SYSTEM_PROMPT.replace("{USER_ID}", str(user_id))

    # 如果有用户画像，追加到 system prompt 末尾
    if user_profile:
        system = system + "\n\n" + user_profile

    # ── 新增：搜索跨会话历史记忆，注入 system prompt ──
    related_memory = await memory.search(user_id, user_message)
    if related_memory:
        system = system + "\n\n" + related_memory
        log.debug(f"[chat] 注入跨会话记忆 user={user_id}")

    messages = [{"role": "system", "content": system}]
    messages.extend(history)

    # 在用户最新消息**之前**，插入一条 system 消息，告诉 LLM 当前对话里已经发过哪些卡片。
    # 用独立 system 消息（不嫁接到 assistant.content）— 这样 LLM 不会把它当作可输出的内容。
    if cards_history:
        # 去重：相同摘要只保留一份（用户连发同样请求时备忘可能爆炸）
        seen = set()
        unique = []
        for s in reversed(cards_history):  # 倒序遍历优先保留最新
            if s not in seen:
                seen.add(s)
                unique.append(s)
        recent = list(reversed(unique))[-6:]  # 最近不重复的 6 类
        messages.append({
            "role": "system",
            "content": (
                "【对话状态备忘 - 仅供你参考，绝对不要在回复中提及】\n"
                "本对话历史中你曾发出过的 UI 卡片（已去重）：\n- "
                + "\n- ".join(recent)
            ),
        })

    # 用户最新消息**之前**再插一条决策提示（占近因记忆，对抗历史里的偷懒模式）
    # 这是关键：放在最后能让 LLM 在决策一刹那看到这条规则
    messages.append({
        "role": "system",
        "content": (
            "处理用户接下来这条消息时，请严格遵守：\n"
            "1. 如果用户的请求需要生成 PDF / 打包 ZIP / 准备练习，"
               "**必须真正调用对应的工具**（generate_quiz_pdf / trigger_pack_province / prepare_practice_session）。"
               "不能只输出'正在生成''马上准备''稍等'之类的文字而不实际调工具。\n"
            "2. 即使你之前已经调过同样工具，每次新请求都要**重新调一次**生成新卡片。\n"
            "3. 调工具时 count 等参数严格按用户**当前消息**里的数字，不要拷贝历史。\n"
            "4. 工具调用是异步的：只要工具调用成功，UI 卡片会自动出现并显示进度，"
               "你不需要在文字里说'稍等''马上完成'，那只会让用户以为你没真调工具。"
        ),
    })

    messages.append({"role": "user", "content": user_message})

    # 3) ReAct 循环：LLM 决定 → 调工具 → 反馈给 LLM → ...
    cards_collected: list[dict] = []
    final_text = ""
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        step_label = f"思考第 {iteration} 轮" if iteration > 1 else "理解你的需求"
        yield sse_event("thinking_start", {"step": iteration, "label": step_label})
        await _delay(100)

        # ----- 调 LLM（流式） -----
        text_buf = ""
        tool_calls: list[dict] = []
        finish_reason = None

        async for chunk in llm.stream(messages, tools=tools_schema):
            ctype = chunk.get("type")
            if ctype == "text":
                # 文本增量：累积 + 推送给前端
                text_buf += chunk["delta"]
                yield sse_event("text_delta", {"delta": chunk["delta"]})
            elif ctype == "tool_call":
                tool_calls = chunk["tool_calls"]
            elif ctype == "done":
                finish_reason = chunk["finish_reason"]
            elif ctype == "error":
                yield sse_event("error", {"message": chunk["message"]})
                return

        # ----- 没有工具调用，对话结束 -----
        if not tool_calls:
            final_text = _strip_system_notes(text_buf)
            log.info(f"[chat] LLM 直接回答 | text={final_text[:80]}...")
            break

        # ----- 有工具调用：执行每个工具 -----
        # 把 LLM 的 assistant 消息（含 tool_calls）放回 history
        messages.append({
            "role": "assistant",
            "content": text_buf or None,
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            tname = tc["function"]["name"]
            try:
                targs = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                targs = {}

            # 安全：强制 user_id 对齐
            if "user_id" in targs:
                targs["user_id"] = assert_uid_match(user_id, targs.get("user_id"))

            # 详细日志：让排查"AI 是否调了工具、参数对不对"非常容易
            log.info(
                f"[chat] 🔧 tool_call | iter={iteration} | name={tname} | "
                f"args={json.dumps(targs, ensure_ascii=False)[:300]}"
            )

            # 推送工具调用开始事件
            yield sse_event("tool_call_start", {
                "step": iteration,
                "name": tname,
                "arguments": targs,
            })
            await _delay(80)

            # 真正调 MCP（带重试 Fallback）
            tool_result = await _call_tool_with_fallback(mcp, tname, targs)

            # 推送工具调用完成事件（带摘要）
            summary = _summarize_tool_result(tname, tool_result)
            yield sse_event("tool_call_done", {
                "step": iteration,
                "name": tname,
                "ok": tool_result["ok"],
                "elapsed_ms": tool_result["elapsed_ms"],
                "summary": summary,
                "error": tool_result.get("error"),
            })
            await _delay(60)

            # 检测 ui_card：如果工具返回里有 ui_card，单独推一条
            result = tool_result["result"] or {}
            if isinstance(result, dict) and "ui_card" in result:
                card = result["ui_card"]
                cards_collected.append(card)
                yield sse_event("ui_card", {"card": card})
                await _delay(60)

            # 把工具结果放进 messages，喂回 LLM 让它继续生成
            # 工具失败时注入强制指令，防止 LLM 幻觉出成功结果
            if not tool_result["ok"]:
                tool_content = {
                    **(result or {}),
                    "__failed__": True,
                    "__instruction__": (
                        f"⚠️ 工具 {tname} 调用失败，严禁假装成功！"
                        "必须如实告诉用户工具出现了问题，请稍后重试。"
                        "绝对不能编造任何结果或假设操作已完成。"
                    ),
                }
            else:
                tool_content = result
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(tool_content, ensure_ascii=False)[:8000],
            })

        # 进入下一轮迭代

    if iteration >= max_iterations:
        log.warning(f"[chat] 达到最大迭代次数 {max_iterations}，终止")
        yield sse_event("text_delta", {"delta": "\n\n（查询内容较复杂，已整理当前所得数据。如需更多信息请再次提问）"})

    # 4) 持久化对话
    total_ms = int((time.time() - overall_start) * 1000)
    msg_id = _persist_messages(
        chat_session_id, user_id, user_message, final_text, cards_collected,
    )

    # ── 新增：异步保存这轮对话到向量记忆（不阻塞返回）──
    asyncio.create_task(
        memory.save(user_id, user_message, final_text, chat_session_id)
    )

    log.info(f"[chat] done | iter={iteration} | total={total_ms}ms | "
             f"text_len={len(final_text)} | cards={len(cards_collected)}")

    yield sse_event("done", {
        "total_ms": total_ms,
        "message_id": msg_id,
        "iterations": iteration,
    })


# ============================================================
# Fallback：工具调用重试
# ============================================================
async def _call_tool_with_fallback(mcp, tname: str, targs: dict, max_retry: int = 2) -> dict:
    """
    工具调用失败时自动重试，超次数后返回友好错误。
    策略：
      - 第1次失败：等0.5秒重试
      - 第2次失败：等1秒重试
      - 仍失败：返回友好错误，不中断对话
    """
    last_error = None
    for attempt in range(max_retry + 1):
        try:
            result = await mcp.call_tool(tname, targs)
            # 工具返回了结果（不管成功失败），直接返回，不重试
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retry:
                wait_sec = 0.5 * (attempt + 1)
                log.warning(
                    f"[chat] 工具 {tname} 第{attempt + 1}次调用失败，"
                    f"{wait_sec}秒后重试: {e}"
                )
                await asyncio.sleep(wait_sec)
            else:
                log.error(
                    f"[chat] 工具 {tname} 重试{max_retry}次仍失败: {e}"
                )

    # 全部重试失败，返回降级结果
    return {
        "ok": False,
        "elapsed_ms": 0,
        "result": {
            "error": "tool_unavailable",
            "message": f"工具 {tname} 暂时不可用，请稍后再试或换个方式提问",
        },
    }


# ============================================================
# helpers
# ============================================================
def _strip_system_notes(text: str) -> str:
    """
    防御性清理：如果 LLM 顽固地往输出里写系统内部标记，统一剥掉。
    保证写入数据库的 assistant 内容是干净的，不会被下一轮加载时又当成"内容"读出来。
    """
    if not text:
        return text
    import re
    # 移除 <system_note>...</system_note>（含跨行）
    text = re.sub(r"<system_note>.*?</system_note>", "", text, flags=re.DOTALL)
    # 移除 [本消息已发出 UI 卡片：...]
    text = re.sub(r"\[本消息已发出 UI 卡片[:：][^\]]*\]", "", text)
    # 移除"对话状态备忘"段（万一 LLM 复述）
    text = re.sub(r"对话状态备忘[:：][^\n]*(\n- [^\n]*)*", "", text)
    # 清掉残留的多余空行
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _summarize_tool_result(tname: str, result: dict) -> str:
    """工具结果的一句话摘要，给前端展示"""
    if not result["ok"]:
        return f"调用失败：{result.get('error', '未知错误')}"

    r = result["result"]
    if not isinstance(r, dict):
        return "已完成"

    # 各种工具的友好摘要
    if "error" in r:
        return f"⚠️ {r.get('message', r['error'])}"
    if "total" in r and "results" in r:
        return f"找到 {r['total']} 条结果"
    if "questions" in r:
        return f"返回 {len(r.get('questions', []))} 道题"
    if "summary" in r:
        return r["summary"]
    if "session_id" in r:
        return r.get("summary", f"已创建 session {r['session_id'][:8]}...")
    if "task_id" in r:
        return r.get("summary", "任务已提交")
    if "provinces" in r:
        return f"返回 {len(r.get('provinces', []))} 个省份"

    return "已完成"


def _persist_messages(
    chat_session_id: Optional[str],
    user_id: int,
    user_text: str,
    assistant_text: str,
    cards: list[dict],
) -> Optional[int]:
    """把这一轮对话写到 chat_messages 表"""
    if not chat_session_id:
        return None
    try:
        # user 消息
        execute(
            "INSERT INTO chat_messages (session_id, role, content) "
            "VALUES (%s, 'user', %s)",
            (chat_session_id, user_text),
        )
        # assistant 消息（含卡片）
        msg_id = execute_returning_id(
            "INSERT INTO chat_messages (session_id, role, content, ui_cards) "
            "VALUES (%s, 'assistant', %s, %s)",
            (chat_session_id, assistant_text or "", json.dumps(cards, ensure_ascii=False) if cards else None),
        )
        # 更新 session 时间戳（让最近活跃的会话排前）
        execute(
            "UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s",
            (chat_session_id,),
        )
        return msg_id
    except Exception as e:
        log.error(f"[chat] 持久化消息失败 | {e}", exc_info=True)
        return None


def create_chat_session(user_id: int, title: Optional[str] = None) -> str:
    """创建新对话 session"""
    sid = str(uuid.uuid4())
    execute(
        "INSERT INTO chat_sessions (id, user_id, title) VALUES (%s, %s, %s)",
        (sid, user_id, title or "新对话"),
    )
    return sid


def list_chat_sessions(user_id: int, limit: int = 20) -> list[dict]:
    """列出用户的对话会话"""
    return query_one_list(
        "SELECT id, title, pinned, created_at, updated_at "
        "FROM chat_sessions WHERE user_id = %s "
        "ORDER BY pinned DESC, updated_at DESC LIMIT %s",
        (user_id, limit),
    )


def query_one_list(sql: str, params: tuple = ()) -> list[dict]:
    from api.db import query_all
    return query_all(sql, params)