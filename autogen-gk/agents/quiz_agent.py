"""
agents/quiz_agent.py - 出题 Agent
直接从数据库抽题注入 prompt，不依赖 function calling
"""
import autogen
from tools.db_tools import get_random_questions, get_user_weakness, get_recent_wrong_questions


def create_quiz_agent(llm_config: dict, user_id: int) -> autogen.AssistantAgent:

    # 预加载薄弱点
    weakness = get_user_weakness(user_id)
    weakest = weakness.get("weakest") or "判断推理"

    def _format_question(q: dict, idx: int) -> str:
        return (
            f"\n**第{idx}题** [{q['question_type']}]\n"
            f"{q['stem']}\n"
            f"A. {q['option_a']}\n"
            f"B. {q['option_b']}\n"
            f"C. {q['option_c']}\n"
            f"D. {q['option_d']}\n"
            f"**答案：{q['answer']}**\n"
            f"**解析：{q['analysis']}**\n"
        )

    # 直接抽题
    questions = get_random_questions(weakest, 5)
    wrongs = get_recent_wrong_questions(user_id, 3)

    questions_text = ""
    if questions:
        questions_text = f"📝 以下是从题库抽取的 {len(questions)} 道{weakest}题：\n"
        for i, q in enumerate(questions, 1):
            questions_text += _format_question(q, i)
    else:
        questions_text = f"题库中暂无{weakest}题目。"

    wrongs_text = ""
    if wrongs:
        wrongs_text = "\n\n📚 用户最近错题（供参考）：\n"
        for i, w in enumerate(wrongs, 1):
            wrongs_text += f"{i}. [{w['question_type']}] {w['stem'][:50]}...（错{w['wrong_count']}次）\n"

    system_msg = f"""你是公考出题助手。

用户最弱题型：{weakest}

【已从题库抽取的真实题目，直接展示给用户】
{questions_text}
{wrongs_text}

你的职责：
1. 把上方题目清晰展示给用户
2. 提示用户先自己作答再看答案
3. 对用户可能的薄弱点给出针对性提示
4. 鼓励用户坚持练习

注意：直接展示上方题目，不要重新编题。
"""

    agent = autogen.AssistantAgent(
        name="QuizAgent",
        system_message=system_msg,
        llm_config=llm_config,
    )

    return agent
