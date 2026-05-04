"""
render.py - 将题目JSON渲染成HTML试卷
"""
import math
from pathlib import Path
from jinja2 import Template

TEMPLATE_PATH = Path(__file__).parent / "template.html"


def render_quiz_html(
    questions: list,
    title: str = "公考模拟试卷",
    time_limit: int = None,
) -> str:
    """
    将题目列表渲染为HTML字符串

    参数：
        questions   - random_quiz() 返回的题目列表
        title       - 试卷标题
        time_limit  - 建议用时（分钟），不传则按题数自动计算

    返回：
        HTML字符串
    """
    # 自动计算用时（每题约1.5分钟）
    if time_limit is None:
        time_limit = math.ceil(len(questions) * 1.5)

    # 提取省份列表
    provinces = list({q.get("province", q.get("source", "")[:4]) for q in questions})

    # 过滤掉不完整的题目
    valid = []
    for q in questions:
        opts = q.get("options", {})
        if (
            q.get("stem", "").strip()
            and len(opts) == 4
            and all(opts.get(k, "").strip() not in ("", f"选项{k}") for k in "ABCD")
            and q.get("answer", "") in "ABCD"
        ):
            valid.append(q)
        else:
            print(f"  ⚠️  第{q.get('id')}题不完整，已过滤")

    # 重新编号
    for i, q in enumerate(valid, 1):
        q["id"] = i

    template_str = TEMPLATE_PATH.read_text(encoding="utf-8")
    tmpl = Template(template_str)

    html = tmpl.render(
        title=title,
        questions=valid,
        provinces=provinces,
        time_limit=time_limit,
    )
    return html
