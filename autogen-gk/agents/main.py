"""
autogen-gk/main.bak.py - 公考多 Agent 系统主入口

架构：
  用户 → Coordinator → QuizAgent / StudyAgent / PlanAgent

运行：
  python main.bak.py

依赖：
  pip install pyautogen pymysql python-dotenv
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import autogen
from agents.coordinator import create_coordinator
from agents.quiz_agent import create_quiz_agent
from agents.study_agent import create_study_agent
from agents.plan_agent import create_plan_agent

# ── 配置 DeepSeek ──
LLM_CONFIG = {
    "config_list": [
        {
            "model": "deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        }
    ],
    "temperature": 0.3,
}

# 测试用 user_id（改成你数据库里的实际用户ID）
USER_ID = 1


def route_to_agent(message: str, user_proxy: autogen.UserProxyAgent) -> None:
    """
    根据 Coordinator 的路由结果，分发给对应的子 Agent
    """
    coordinator = create_coordinator(LLM_CONFIG)

    # 先让 coordinator 判断意图
    user_proxy.initiate_chat(
        coordinator,
        message=message,
        max_turns=1,
        silent=True,
    )

    last_msg = coordinator.last_message()["content"]
    print(f"\n[Coordinator 路由] → {last_msg[:60]}...\n")

    # 根据路由结果选 Agent
    if last_msg.startswith("QUIZ_AGENT:"):
        task = last_msg.replace("QUIZ_AGENT:", "").strip()
        agent = create_quiz_agent(LLM_CONFIG, USER_ID)
        print("📝 转交给 QuizAgent 处理...\n")
    elif last_msg.startswith("STUDY_AGENT:"):
        task = last_msg.replace("STUDY_AGENT:", "").strip()
        agent = create_study_agent(LLM_CONFIG, USER_ID)
        print("📊 转交给 StudyAgent 处理...\n")
    elif last_msg.startswith("PLAN_AGENT:"):
        task = last_msg.replace("PLAN_AGENT:", "").strip()
        agent = create_plan_agent(LLM_CONFIG, USER_ID)
        print("📅 转交给 PlanAgent 处理...\n")
    else:
        # Coordinator 直接回答了
        print(f"[Coordinator 直接回答]\n{last_msg}")
        return

    # 子 Agent 处理
    user_proxy.initiate_chat(
        agent,
        message=task,
        max_turns=3,
    )


def main():
    # UserProxy 代表用户，不需要真人输入
    user_proxy = autogen.UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )

    print("=" * 50)
    print("公考多 Agent 系统启动")
    print("=" * 50)

    # 测试三个场景
    test_cases = [
        "帮我出5道判断推理题练练手",
        "分析一下我现在的学习情况，我哪里最弱",
        "帮我制定一个备考计划，我3个月后考试，每天能学2小时",
    ]

    for i, msg in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        print(f"测试 {i}: {msg}")
        print("=" * 50)
        route_to_agent(msg, user_proxy)
        print()

    # 交互模式
    print("\n" + "=" * 50)
    print("进入交互模式（输入 quit 退出）")
    print("=" * 50)
    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        route_to_agent(user_input, user_proxy)


if __name__ == "__main__":
    main()
