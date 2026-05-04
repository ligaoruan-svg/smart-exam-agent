"""
agents/plan_agent.py - 学习计划 Agent
数据直接从数据库查询注入 prompt，不依赖 function calling
"""
import autogen
from tools.db_tools import get_user_stats, get_user_weakness


def create_plan_agent(llm_config: dict, user_id: int) -> autogen.AssistantAgent:

    # 直接查真实数据
    stats = get_user_stats(user_id)
    weakness = get_user_weakness(user_id)

    total = stats.get('total_answered', 0)
    rate = stats.get('correct_rate', 0)
    weakest = weakness.get("weakest") or "判断推理"
    rates = weakness.get("rates", {})

    # 构建每日时间分配建议
    time_alloc = ""
    if rates:
        sorted_rates = sorted(rates.items(), key=lambda x: -x[1])
        for qt, r in sorted_rates:
            pct = round(r * 100)
            extra = "⚠️重点突破" if r > 0.5 else ""
            time_alloc += f"  · {qt}（错误率{pct}%）{extra}\n"
    else:
        time_alloc = "  · 各模块均衡练习\n"

    data_summary = f"""【用户真实数据，必须基于此制定计划，禁止编造】
- 总答题数：{total} 题
- 综合正确率：{rate}%
- 最弱模块：{weakest}
- 各模块错误率排序：
{time_alloc}"""

    system_msg = f"""你是公考备考规划师。

{data_summary}

你的职责：
1. 根据用户提供的考试时间和每日学习时长，制定个性化备考计划
2. 重点针对薄弱模块分配更多时间
3. 计划要分阶段（基础→强化→冲刺），每阶段有具体目标
4. 每日安排要具体可执行，不要太理想化

制定计划时：
- 如果用户告诉你距离考试多久，基于那个时间制定
- 如果没有告诉你，默认60天
- 每日目标不要太高，保持可持续性
- 弱的模块多分配时间，强的模块维持即可
"""

    agent = autogen.AssistantAgent(
        name="PlanAgent",
        system_message=system_msg,
        llm_config=llm_config,
    )

    return agent
