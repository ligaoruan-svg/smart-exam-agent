"""
to_pdf.py - HTML转PDF（playwright无头浏览器）
安装：pip install playwright && playwright install chromium
"""
import os
import tempfile
from pathlib import Path


def html_to_pdf(html: str, output_path: str) -> str:
    """HTML字符串 → PDF文件"""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(html)
    tmp.close()

    try:
        _playwright_pdf(tmp.name, output_path)
    except Exception as e:
        os.unlink(tmp.name)
        raise RuntimeError(
            f"PDF生成失败: {e}\n"
            f"请运行以下命令安装依赖：\n"
            f"  pip install playwright\n"
            f"  playwright install chromium"
        )
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    print(f"✅ PDF已生成: {output_path}")
    return output_path


def _playwright_pdf(html_path: str, pdf_path: str):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        browser.close()


def save_html(html: str, output_path: str) -> str:
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ HTML已保存: {output_path}")
    return output_path
