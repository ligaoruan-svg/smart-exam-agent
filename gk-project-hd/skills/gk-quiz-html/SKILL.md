---
name: gk-quiz-html
description: 公考小智出题并生成HTML试卷再转PDF。当用户需要生成格式美观的公考模拟试卷PDF时使用。输出包含完整题目的试卷页和独立答案解析页，通过weasyprint转为PDF。
license: Internal
---

# 公考小智 HTML试卷生成 Skill

## 流程

```
random_quiz() → JSON题目列表 → render_quiz_html() → HTML字符串 → html_to_pdf() → PDF文件
```

## 安装依赖

```bash
conda activate gk
pip install weasyprint -i https://mirrors.aliyun.com/pypi/simple/
```

## 调用方式

```python
from quiz_html_skill.render import render_quiz_html
from quiz_html_skill.to_pdf import html_to_pdf

questions = random_quiz(n=20)
html = render_quiz_html(questions, title="2024广东行测模拟卷")
html_to_pdf(html, "output.pdf")
```

## 题目JSON必须包含的字段

```json
{
  "id": 1,
  "type": "言语理解",
  "source": "2023年广东行测",
  "stem": "完整题干，不能为空，不能是占位符",
  "options": {
    "A": "具体选项内容，不能是占位符",
    "B": "具体选项内容",
    "C": "具体选项内容",
    "D": "具体选项内容"
  },
  "answer": "B",
  "analysis": "解析内容"
}
```

## PDF结构规范

```
封面 → 全部题目（不含答案）→ 答案与解析（独立最后页）
```

答案页与题目页用 page-break 强制分页，用户做完题再翻到最后对答案。

## 文件结构

```
quiz_html_skill/
├── SKILL.md       ← 本文件
├── render.py      ← HTML渲染，render_quiz_html()
├── to_pdf.py      ← PDF转换，html_to_pdf()
└── template.html  ← HTML模板
```
