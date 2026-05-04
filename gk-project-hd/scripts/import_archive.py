#!/usr/bin/env python3
"""
scripts/import_archive.py - 把 data/exam_archive.json 灌到 papers 表

JSON 结构（每条记录 = 1 省份 × 1 年份）:
    {
      "安徽_2024": {
        "province": "安徽",
        "year": 2024,
        "sub_exam": null,                          // 或 "A" / "B"
        "行测_题目": "/data/pdf/.../xxx.pdf",        // 路径或 null
        "行测_答案": "/data/pdf/.../xxx.pdf",
        "申论_题目": "/data/pdf/.../xxx.pdf",
        "申论_答案": "/data/pdf/.../xxx.pdf"
      },
      ...
    }

每条记录最多拆成 4 行 papers（4 个文件位每个一行；不存在的跳过）。
省份 ZIP 路径 = zips/{province}公考真题.zip（如果该 zip 存在）

用法：
    cd ~/Desktop/项目/gk-project-hd
    conda activate gk
    python scripts/import_archive.py

可选参数：
    --dry-run       不写库，只打印将插入的统计
    --truncate      先 TRUNCATE papers 再导入（重新导入用）
"""
import os
import sys
import json
import argparse
from pathlib import Path

# 让脚本能 import api.* 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.config import get_logger          # noqa: E402
from api.db import execute, query_one, get_db   # noqa: E402

log = get_logger("api")

ARCHIVE_JSON = PROJECT_ROOT / "data" / "exam_archive.json"
ZIPS_DIR     = PROJECT_ROOT / "zips"
DATA_DIR     = PROJECT_ROOT / "data"

# 4 个文件位 → (exam_type, doc_type)
FILE_SLOTS = [
    ("行测_题目", "行测", "题目"),
    ("行测_答案", "行测", "答案"),
    ("申论_题目", "申论", "题目"),
    ("申论_答案", "申论", "答案"),
]


def normalize_path(raw: str) -> str | None:
    """
    archive JSON 里的路径形如 '/data/pdf/34省考.../xxx.pdf'，
    但实际文件位于 '公考资料知识库/34省考.../xxx.pdf'。
    本函数返回 *相对项目根* 的真实路径；None = 路径无效。
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    # 去掉开头的 /
    if s.startswith("/"):
        s = s[1:]
    # 关键映射：archive 里的 data/pdf/ → 真实根目录 公考资料知识库/
    if s.startswith("data/pdf/"):
        s = "公考资料知识库/" + s[len("data/pdf/"):]
    return s


def file_size(rel_path: str) -> int | None:
    """根据相对路径取真实文件大小（不存在返回 None，但仍允许入库）"""
    p = PROJECT_ROOT / rel_path
    if p.exists():
        try:
            return p.stat().st_size
        except OSError:
            return None
    return None


def find_zip_for_province(province: str) -> str | None:
    """zips/{province}公考真题.zip → 相对项目根的路径"""
    zip_path = ZIPS_DIR / f"{province}公考真题.zip"
    if zip_path.exists():
        return f"zips/{province}公考真题.zip"
    return None


def make_paper_name(province: str, year: int, exam_type: str,
                     doc_type: str, sub_exam: str | None) -> str:
    """{年}年 {省} 公考{行测/申论}{题目/答案}[A 卷]"""
    sub = f" {sub_exam}卷" if sub_exam else ""
    return f"{year}年 {province} 公考{exam_type}{doc_type}{sub}"


def _expand_paths(raw) -> list:
    """
    archive 里的路径字段，绝大多数是单 str，但少数（看到湖南 2021 申论_答案）会是 list，
    且 list 里偶尔有截断的损坏字符串。本函数返回**经过 normalize 的有效路径列表**。
    """
    out: list = []
    if isinstance(raw, str):
        n = normalize_path(raw)
        if n:
            out.append(n)
    elif isinstance(raw, list):
        for item in raw:
            n = normalize_path(item)
            if n:
                out.append(n)
    return out


def import_one_record(key: str, rec: dict, zip_lookup: dict, stats: dict) -> int:
    """
    导入一条 archive 记录，返回成功插入行数。
    stats 用来回传跳过文件数（找不到的 PDF）。
    """
    province = rec.get("province")
    year     = rec.get("year")
    sub_exam = rec.get("sub_exam")  # 可为 None

    if not province or not year:
        log.warning(f"跳过无效记录: {key}")
        return 0

    zip_rel = zip_lookup.get(province)  # 该省份是否有总包

    inserted = 0
    for slot_key, exam_type, doc_type in FILE_SLOTS:
        paths = _expand_paths(rec.get(slot_key))
        if not paths:
            continue

        # 一个 slot 里多个路径：每条都尝试，找得到文件就入库
        for idx, rel in enumerate(paths):
            full = PROJECT_ROOT / rel
            if not full.exists():
                stats["missing"] = stats.get("missing", 0) + 1
                stats["missing_samples"].append(rel)
                continue

            try:
                size = full.stat().st_size
            except OSError:
                size = None

            name = make_paper_name(province, year, exam_type, doc_type, sub_exam)
            # 同 slot 多份的话给个区分编号
            if len(paths) > 1:
                name = f"{name} ({idx + 1})"

            execute(
                "INSERT INTO papers "
                "  (name, province, year, exam_type, doc_type, sub_exam, "
                "   file_url, file_path, zip_path, file_size, status, total_questions) "
                "VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, 'published', 0)",
                (name, province, year, exam_type, doc_type, sub_exam,
                 rel, zip_rel, size),
            )
            inserted += 1
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="不写库，只统计")
    ap.add_argument("--truncate", action="store_true", help="先清空 papers 再导入")
    args = ap.parse_args()

    if not ARCHIVE_JSON.exists():
        log.error(f"❌ 找不到归档文件: {ARCHIVE_JSON}")
        sys.exit(1)

    log.info(f"📖 读取归档: {ARCHIVE_JSON}")
    with open(ARCHIVE_JSON, "r", encoding="utf-8") as f:
        archive = json.load(f)

    log.info(f"   共 {len(archive)} 条年份-省份记录")

    # 预扫一遍 zips/ 目录，看哪些省份有 ZIP 包
    zip_lookup: dict[str, str] = {}
    if ZIPS_DIR.exists():
        for zf in ZIPS_DIR.glob("*.zip"):
            name = zf.name
            # 形如 "广东公考真题.zip"
            if name.endswith("公考真题.zip"):
                province = name[: -len("公考真题.zip")]
                zip_lookup[province] = f"zips/{name}"
        log.info(f"📦 发现 {len(zip_lookup)} 个省份 ZIP 包")
    else:
        log.warning(f"⚠️  zips 目录不存在: {ZIPS_DIR}")

    # dry-run 仅统计
    if args.dry_run:
        total_files = 0
        missing_files = 0
        per_province: dict[str, int] = {}
        missing_samples: list = []
        for key, rec in archive.items():
            for slot_key, _, _ in FILE_SLOTS:
                paths = _expand_paths(rec.get(slot_key))
                for rel in paths:
                    full = PROJECT_ROOT / rel
                    if full.exists():
                        total_files += 1
                        prov = rec.get("province", "?")
                        per_province[prov] = per_province.get(prov, 0) + 1
                    else:
                        missing_files += 1
                        if len(missing_samples) < 5:
                            missing_samples.append(rel)
        log.info("=" * 50)
        log.info(f"DRY RUN:")
        log.info(f"   将插入 {total_files} 条 paper（文件实际存在）")
        log.info(f"   跳过   {missing_files} 个不存在的文件")
        if missing_samples:
            log.info("   找不到的样例（前 5 条）:")
            for s in missing_samples:
                log.info(f"      - {s}")
        log.info("各省份:")
        for p, n in sorted(per_province.items(), key=lambda x: -x[1]):
            log.info(f"   {p:8s} {n:5d}")
        return

    # 真插入
    if args.truncate:
        log.warning("⚠️  TRUNCATE papers")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE papers")

    # 先看现有数据
    existing = query_one("SELECT COUNT(*) AS n FROM papers")["n"]
    log.info(f"   导入前 papers 行数: {existing}")
    if existing > 0 and not args.truncate:
        log.warning("⚠️  papers 表已有数据，将累加插入。如需重导，加 --truncate")

    total = 0
    skipped = 0
    stats = {"missing": 0, "missing_samples": []}
    for i, (key, rec) in enumerate(archive.items(), 1):
        try:
            inserted = import_one_record(key, rec, zip_lookup, stats)
            total += inserted
            if inserted == 0:
                skipped += 1
            if i % 50 == 0:
                log.info(f"   进度 {i}/{len(archive)} | 已插入 {total} 行 | 跳过 {stats['missing']} 个缺失文件")
        except Exception as e:
            log.error(f"❌ 导入 {key} 失败: {e}")

    final = query_one("SELECT COUNT(*) AS n FROM papers")["n"]
    log.info("=" * 50)
    log.info(f"✅ 导入完成")
    log.info(f"   archive 记录: {len(archive)}")
    log.info(f"   插入 papers : {total}")
    log.info(f"   跳过缺失文件: {stats['missing']}")
    log.info(f"   未含任何文件位的记录: {skipped}")
    log.info(f"   导入后 papers 行数: {final}")
    if stats["missing_samples"]:
        log.info("   缺失文件样例（前 5 条）:")
        for s in stats["missing_samples"][:5]:
            log.info(f"      - {s}")


if __name__ == "__main__":
    main()