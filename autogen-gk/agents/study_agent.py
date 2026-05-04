"""
agents/study_agent.py - 学情分析 Agent
数据直接从数据库查询注入 prompt，不依赖 function calling
"""
import autogen
from tools.db_tools import get_user_stats, get_user_weakness, get_recent_wrong_questions


def create_study_agent(llm_config: dict, user_id: int) -> autogen.AssistantAgent:

    # 直接查真实数据
    stats = get_user_stats(user_id)
    weakness = get_user_weakness(user_id)
    wrongs = get_recent_wrong_questions(user_id, 3)

    total = stats.get('total_answered', 0)
    rate = stats.get('correct_rate', 0)

    data_lines = [
        "【用户真实学习数据，必须基于以下数据分析，禁止编造任何数字】",
        f"- 总答题数：{total} 题",
        f"- 综合正确率：{rate}%",
    ]

    if weakness.get("has_data"):
        data_lines.append("- 各模块错误率：")
        for qt, r in weakness["rates"].items():
            bar = "🔴危险" if r > 0.6 else "🟡偏弱" if r > 0.3 else "🟢良好"
            data_lines.append(f"  · {qt}：{round(r * 100)}% 错误率 {bar}")
        data_lines.append(f"- 最弱模块：{weakness['weakest']}")
    else:
        data_lines.append("- 薄弱点数据：暂无（答题数不足）")

    if wrongs:
        data_lines.append("- 最近错题：")
        for w in wrongs:
            data_lines.append(
                f"  · [{w['question_type']}] {w['stem'][:30]}...（已错{w['wrong_count']}次）"
            )
    else:
        data_lines.append("- 最近错题：暂无")

    data_summary = "\n".join(data_lines)

    system_msg = f"""你是公考学情分析师。

{data_summary}

你的职责：
1. 严格基于上方真实数据进行分析，不能编造或推测任何数字
2. 深度分析用户的薄弱点，给出针对性建议
3. 建议要具体可操作，不要空话
4. 语气鼓励，帮助用户建立信心

分析框架：
- 总体情况（用真实数字）
- 各模块诊断（基于真实错误率）
- 重点突破方向
- 具体行动建议
"""

    agent = autogen.AssistantAgent(
        name="StudyAgent",
        system_message=system_msg,
        llm_config=llm_config,
    )

    return agent
